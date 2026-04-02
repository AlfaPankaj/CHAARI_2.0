# CHAARI 2.0 – audio/ - TTS Engine
# Edge TTS (neural voices) + pygame playback with echo effect
# Streaming mode: generate + play in parallel for low-latency speech
# Response Cache: pre-cached audio for instant playback of common phrases
# Fallback: pyttsx3 when Edge TTS fails

import os
import re
import time
import queue
import hashlib
import asyncio
import threading

import pygame
import edge_tts

try:
    from config.voice import (
        ASSISTANT_VOICE, HINDI_VOICE, TTS_RATE, TTS_PITCH,
        INSTANT_MODE_MAX_WORDS, ECHO_ENABLED, ECHO_DELAY_MS,
        ECHO_VOLUME, MAIN_VOLUME, AUDIO_CACHE_DIR,
        MIXER_FREQUENCY, MIXER_CHANNELS, MIXER_BUFFER, MIXER_NUM_CHANNELS,
    )
except ImportError:
    ASSISTANT_VOICE = "en-US-AriaNeural"
    HINDI_VOICE = "hi-IN-SwaraNeural"
    TTS_RATE = "+5%"
    TTS_PITCH = "-20Hz"
    INSTANT_MODE_MAX_WORDS = 25
    ECHO_ENABLED = True
    ECHO_DELAY_MS = 100
    ECHO_VOLUME = 0.3
    MAIN_VOLUME = 1.0
    AUDIO_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "audio_cache")
    MIXER_FREQUENCY = 24000
    MIXER_CHANNELS = 1
    MIXER_BUFFER = 512
    MIXER_NUM_CHANNELS = 8

os.makedirs(AUDIO_CACHE_DIR, exist_ok=True)


PHRASE_CACHE_DIR = os.path.join(AUDIO_CACHE_DIR, "phrases")
os.makedirs(PHRASE_CACHE_DIR, exist_ok=True)

PRECACHE_PHRASES = [
    "Done, Boss!", "Action completed!", "File created!", "File deleted!",
    "App opened!", "App closed!", "Window minimized!", "Window maximized!",
    "Window restored!", "Process killed!", "Text typed!",
    "Message sent!", "Call started!",

    "Something went wrong.", "I couldn't do that.", "Action cancelled.",
    "That's not allowed, Boss.", "Access denied.",
    "Hey Boss, kya haal hai?", "Hello! How can I help?",
    "Good morning, Boss!", "Good night, take care!",
    "Bye Boss, see you soon!",
    "Okay!", "Sure!", "Got it!", "Right away!", "On it!",
    "Haan Boss!", "Bilkul!", "Theek hai!",
]

def _phrase_cache_path(text: str) -> str:
    """Get cache file path for a phrase (hash-based filename)."""
    h = hashlib.md5(text.lower().strip().encode()).hexdigest()[:16]
    return os.path.join(PHRASE_CACHE_DIR, f"phrase_{h}.mp3")

def _run_coro_blocking(coro):
    """Run an async coroutine, blocking until done.
    Handles nested event loops (e.g. from Selenium)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result = {"value": None, "exc": None}

    def runner():
        try:
            result["value"] = asyncio.run(coro)
        except Exception as e:
            result["exc"] = e

    t = threading.Thread(target=runner, daemon=True)
    t.start()
    t.join()

    if result["exc"] is not None:
        raise result["exc"]
    return result["value"]

def _ensure_mixer():
    """Initialize pygame mixer if not already done."""
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init(
                frequency=MIXER_FREQUENCY,
                size=-16,
                channels=MIXER_CHANNELS,
                buffer=MIXER_BUFFER,
            )
            pygame.mixer.set_num_channels(MIXER_NUM_CHANNELS)
        return True
    except Exception:
        return False

async def _warmup_tts():
    """Pre-warm Edge TTS to reduce first-speak latency."""
    try:
        warmup_path = os.path.join(AUDIO_CACHE_DIR, "_warmup.mp3")
        communicate = edge_tts.Communicate("hi", ASSISTANT_VOICE, rate="+18%")
        await communicate.save(warmup_path)
        if os.path.exists(warmup_path):
            os.remove(warmup_path)
    except Exception as e:
        print(f"  [TTS] Warmup failed: {e}")

async def _precache_phrases():
    """Pre-generate audio for common phrases (background, non-blocking)."""
    cached = 0
    for phrase in PRECACHE_PHRASES:
        path = _phrase_cache_path(phrase)
        if os.path.exists(path):
            cached += 1
            continue
        try:
            communicate = edge_tts.Communicate(phrase, ASSISTANT_VOICE, pitch="-20Hz", rate="+5%")
            await communicate.save(path)
            cached += 1
        except Exception:
            pass
    return cached


class TTSEngine:
    """Edge TTS engine with streaming, echo effect, and pyttsx3 fallback.
    Supports pre-emptive chunk streaming: push partial phrases for immediate
    audio generation while the LLM is still producing tokens."""

    def __init__(self):
        self.chunk_queue = queue.Queue()
        self._speaking = False
        self.stop_flag = False
        self._generation_thread = None
        self._playback_thread = None
        self._lock = threading.Lock()
        self._fallback_engine = None
        self._text_queue = queue.Queue()
        self._chunk_stream_active = False

    def load(self):
        """Initialize mixer, warm up Edge TTS, and start phrase pre-caching."""
        _ensure_mixer()
        try:
            _run_coro_blocking(_warmup_tts())
            print("  [TTS] Edge TTS warmed up.")
        except Exception as e:
            print(f"  [TTS] Edge TTS warmup failed: {e}")
        def _bg_precache():
            try:
                count = _run_coro_blocking(_precache_phrases())
                print(f"  [TTS] Pre-cached {count}/{len(PRECACHE_PHRASES)} phrases.")
            except Exception:
                pass
        threading.Thread(target=_bg_precache, daemon=True).start()

    async def _generate_audio(self, text: str, file_path: str) -> bool:
        """Generate audio with Edge TTS. Auto-detect Hindi."""
        try:
            voice = ASSISTANT_VOICE
            communicate = edge_tts.Communicate(
                text, voice, pitch=TTS_PITCH, rate=TTS_RATE,
            )
            await communicate.save(file_path)
            return True
        except Exception:
            return False

    def _play_audio_chunk(self, file_path: str) -> bool:
        """Play audio with echo effect.
        Channel 0: main voice (immediate).
        Channel 1: echo voice (delayed + lower volume)."""
        try:
            if not os.path.exists(file_path):
                return False

            if not _ensure_mixer():
                return False

            try:
                sound = pygame.mixer.Sound(file_path)
            except Exception:
                pygame.mixer.music.load(file_path)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    if self.stop_flag:
                        pygame.mixer.music.stop()
                        break
                    time.sleep(0.05)
                return True

            chan_main = pygame.mixer.Channel(0)
            chan_main.set_volume(MAIN_VOLUME)
            chan_main.play(sound)

            if ECHO_ENABLED:
                time.sleep(ECHO_DELAY_MS / 1000.0)
                chan_echo = pygame.mixer.Channel(1)
                chan_echo.set_volume(ECHO_VOLUME)
                chan_echo.play(sound)

            while chan_main.get_busy():
                if self.stop_flag:
                    chan_main.stop()
                    if ECHO_ENABLED:
                        pygame.mixer.Channel(1).stop()
                    break
                time.sleep(0.05)

            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass

            return True

        except Exception as e:
            print(f"  [TTS] Play error: {e}")
            return False

    def _split_into_sentences(self, text: str) -> list[str]:
        """Smart sentence splitting for streaming."""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        if sentences:
            sentences[0] = " " + sentences[0]
        return sentences

    def _generate_chunks_worker(self, sentences: list[str]):
        """Background: generate audio chunks and queue them."""
        for f in os.listdir(AUDIO_CACHE_DIR):
            if f.startswith("fast_") and f.endswith(".mp3"):
                try:
                    os.remove(os.path.join(AUDIO_CACHE_DIR, f))
                except Exception:
                    pass

        for i, sentence in enumerate(sentences):
            if self.stop_flag:
                break
            timestamp = int(time.time() * 1000)
            file_path = os.path.join(AUDIO_CACHE_DIR, f"fast_{i}_{timestamp}.mp3")

            success = _run_coro_blocking(self._generate_audio(sentence, file_path))
            if success:
                self.chunk_queue.put(file_path)

        self.chunk_queue.put(None) 

    def _playback_worker(self):
        """Background: play audio chunks as they arrive."""
        while True:
            if self.stop_flag:
                break
            try:
                file_path = self.chunk_queue.get(timeout=0.05)
                if file_path is None:
                    self.chunk_queue.task_done()
                    break
                try:
                    self._play_audio_chunk(file_path)
                finally:
                    self.chunk_queue.task_done()
            except queue.Empty:
                continue

    def _speak_streaming(self, text: str) -> bool:
        """Generate and play simultaneously — starts after first sentence ready."""
        try:
            sentences = self._split_into_sentences(text)
            if not sentences:
                return False

            self.stop_flag = False
            self.chunk_queue = queue.Queue()

            self._generation_thread = threading.Thread(
                target=self._generate_chunks_worker,
                args=(sentences,), daemon=True,
            )
            self._generation_thread.start()

            self._playback_thread = threading.Thread(
                target=self._playback_worker, daemon=True,
            )
            self._playback_thread.start()

            self._generation_thread.join()
            self._playback_thread.join()
            return True

        except Exception as e:
            print(f"  [TTS] Streaming error: {e}")
            return False

    def _speak_instant(self, text: str) -> bool:
        """Single generation + play for short text."""
        try:
            file_path = os.path.join(AUDIO_CACHE_DIR, "instant.mp3")
            success = _run_coro_blocking(self._generate_audio(text, file_path))
            if not success:
                return False
            self._play_audio_chunk(file_path)
            return True
        except Exception as e:
            print(f"  [TTS] Instant error: {e}")
            return False

    def _speak_fallback(self, text: str) -> bool:
        """Offline fallback using pyttsx3."""
        try:
            if self._fallback_engine is None:
                import pyttsx3
                self._fallback_engine = pyttsx3.init()
                self._fallback_engine.setProperty("rate", 175)
                self._fallback_engine.setProperty("volume", 0.9)
            self._fallback_engine.say(text)
            self._fallback_engine.runAndWait()
            return True
        except Exception as e:
            print(f"  [TTS] Fallback error: {e}")
            return False

    def speak(self, text: str) -> bool:
        """Smart speak: cached → instant → streaming → fallback.
        Checks phrase cache first for instant playback (<50ms)."""
        text = text.strip()
        if not text:
            return False

        with self._lock:
            self._speaking = True
            self.stop_flag = False

        try:
            cache_path = _phrase_cache_path(text)
            if os.path.exists(cache_path):
                ok = self._play_audio_chunk_keep(cache_path)
                if ok:
                    return True

            words = text.split()
            if len(words) <= INSTANT_MODE_MAX_WORDS:
                ok = self._speak_instant(text)
            else:
                ok = self._speak_streaming(text)

            if not ok:
                print("  [TTS] Edge TTS failed, using offline fallback...")
                ok = self._speak_fallback(text)

            if ok and len(words) <= 10 and not os.path.exists(cache_path):
                self._bg_cache_phrase(text)

            return ok
        finally:
            with self._lock:
                self._speaking = False

    def _play_audio_chunk_keep(self, file_path: str) -> bool:
        """Play cached audio WITHOUT deleting the file."""
        try:
            if not os.path.exists(file_path) or not _ensure_mixer():
                return False
            try:
                sound = pygame.mixer.Sound(file_path)
            except Exception:
                pygame.mixer.music.load(file_path)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    if self.stop_flag:
                        pygame.mixer.music.stop()
                        break
                    time.sleep(0.05)
                return True
            chan_main = pygame.mixer.Channel(0)
            chan_main.set_volume(MAIN_VOLUME)
            chan_main.play(sound)
            if ECHO_ENABLED:
                time.sleep(ECHO_DELAY_MS / 1000.0)
                chan_echo = pygame.mixer.Channel(1)
                chan_echo.set_volume(ECHO_VOLUME)
                chan_echo.play(sound)
            while chan_main.get_busy():
                if self.stop_flag:
                    chan_main.stop()
                    if ECHO_ENABLED:
                        pygame.mixer.Channel(1).stop()
                    break
                time.sleep(0.05)
            return True
        except Exception:
            return False

    def _bg_cache_phrase(self, text: str):
        """Cache a phrase in background for future instant playback."""
        def _do():
            try:
                path = _phrase_cache_path(text)
                if not os.path.exists(path):
                    _run_coro_blocking(self._generate_audio(text, path))
            except Exception:
                pass
        threading.Thread(target=_do, daemon=True).start()

    def _chunk_gen_worker(self):
        """Background: read text chunks from _text_queue, generate audio, feed chunk_queue."""
        idx = 0
        while True:
            if self.stop_flag:
                break
            try:
                text = self._text_queue.get(timeout=0.1)
                if text is None:
                    self._text_queue.task_done()
                    break
                timestamp = int(time.time() * 1000)
                file_path = os.path.join(AUDIO_CACHE_DIR, f"chunk_{idx}_{timestamp}.mp3")
                success = _run_coro_blocking(self._generate_audio(text, file_path))
                if success:
                    self.chunk_queue.put(file_path)
                idx += 1
                self._text_queue.task_done()
            except queue.Empty:
                continue
        self.chunk_queue.put(None)  

    def start_chunk_stream(self):
        """Begin a pre-emptive chunk stream session.
        Call push_chunk() to feed text, finish_chunk_stream() when done."""
        self.stop_flag = False
        self._chunk_stream_active = True
        self._text_queue = queue.Queue()
        self.chunk_queue = queue.Queue()

        with self._lock:
            self._speaking = True

        for f in os.listdir(AUDIO_CACHE_DIR):
            if f.startswith("chunk_") and f.endswith(".mp3"):
                try:
                    os.remove(os.path.join(AUDIO_CACHE_DIR, f))
                except Exception:
                    pass

        self._generation_thread = threading.Thread(
            target=self._chunk_gen_worker, daemon=True,
        )
        self._generation_thread.start()

        self._playback_thread = threading.Thread(
            target=self._playback_worker, daemon=True,
        )
        self._playback_thread.start()

    def push_chunk(self, text: str):
        """Push a partial text chunk for immediate audio generation.
        Must be called between start_chunk_stream() and finish_chunk_stream()."""
        text = text.strip()
        if text and self._chunk_stream_active and not self.stop_flag:
            self._text_queue.put(text)

    def finish_chunk_stream(self):
        """Signal end of chunk stream and wait for all audio to finish playing."""
        if not self._chunk_stream_active:
            return
        self._text_queue.put(None)  
        if self._generation_thread and self._generation_thread.is_alive():
            self._generation_thread.join()
        if self._playback_thread and self._playback_thread.is_alive():
            self._playback_thread.join()
        self._chunk_stream_active = False
        with self._lock:
            self._speaking = False

    def speak_async(self, text: str):
        """Speak text in a background thread (non-blocking)."""
        t = threading.Thread(target=self.speak, args=(text,), daemon=True)
        t.start()

    def stop(self):
        """Stop all playback immediately."""
        self.stop_flag = True
        try:
            if pygame.mixer.get_init():
                for i in range(MIXER_NUM_CHANNELS):
                    try:
                        pygame.mixer.Channel(i).stop()
                    except Exception:
                        pass
                try:
                    pygame.mixer.music.stop()
                except Exception:
                    pass
        except Exception:
            pass
        with self._lock:
            self._speaking = False

    def is_speaking(self) -> bool:
        """Check if TTS is currently speaking."""
        with self._lock:
            return self._speaking

    def is_loaded(self) -> bool:
        """Check if mixer is ready."""
        try:
            return pygame.mixer.get_init() is not None
        except Exception:
            return False

    def wait_until_done(self):
        """Block until current speech finishes."""
        if self._playback_thread and self._playback_thread.is_alive():
            self._playback_thread.join()
        if self._generation_thread and self._generation_thread.is_alive():
            self._generation_thread.join()
