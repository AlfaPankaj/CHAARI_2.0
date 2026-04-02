# CHAARI 2.0 — Dell Execution Node — Voice Interface
# Provides voice I/O on Dell, routes commands to ASUS for LLM processing
#
# Architecture:
#   User speaks → Dell STT (speech_recognition) → text
#   text → send to ASUS over TCP → ASUS processes with LLM → response
#   response → Dell TTS (Edge TTS + pygame) → speaks to user

import os
import sys
import time
import json
import threading

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chaari_dell.audio.voice_config import (
    STT_BACKEND, INPUT_LANGUAGE, ASSISTANT_VOICE, WAKE_WORD_ENABLED,
    VOICE_HOTKEY, HOTKEY_ENABLED, ASUS_HOST, ASUS_PORT,
    AUDIO_CACHE_DIR, MIXER_FREQUENCY, MIXER_CHANNELS, MIXER_BUFFER,
    MIXER_NUM_CHANNELS, ECHO_ENABLED, ECHO_DELAY_MS, ECHO_VOLUME,
    MAIN_VOLUME, TTS_RATE, TTS_PITCH, INSTANT_MODE_MAX_WORDS,
    STT_TIMEOUT, WAKE_WORD_THRESHOLD,
)


class DellVoiceInterface:
    """Voice interface for Dell — STT + TTS with ASUS as backend brain."""

    def __init__(self, asus_host: str = ASUS_HOST, asus_port: int = ASUS_PORT):
        self.asus_host = asus_host
        self.asus_port = asus_port
        self._stt = None
        self._tts = None
        self._wake = None
        self._hotkey = None
        self._running = False

    def boot(self) -> bool:
        """Initialize voice subsystems on Dell."""
        print("\n  [Dell-Voice] Booting voice interface...")

        # ── TTS: reuse ASUS TTS engine (Edge TTS + pygame) ──
        try:
            # Inline the same TTS engine — it's self-contained
            sys.path.insert(0, os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "chaari_2_0",
            ))
            from audio.tts_engine import TTSEngine
            self._tts = TTSEngine()
            self._tts.load()
            print("  [Dell-Voice] TTS: Edge TTS + pygame ✓")
        except Exception as e:
            print(f"  [Dell-Voice] TTS failed: {e}")
            return False

        # ── STT: speech_recognition (lightweight) ──
        try:
            from audio.stt_engine import STTEngine
            self._stt = STTEngine(backend="speech_recognition", language=INPUT_LANGUAGE)
            self._stt.load()
            print("  [Dell-Voice] STT: speech_recognition ✓")
        except Exception as e:
            print(f"  [Dell-Voice] STT failed: {e}")
            return False

        # ── Wake Word ──
        if WAKE_WORD_ENABLED:
            try:
                from audio.wake_word import WakeWordDetector
                self._wake = WakeWordDetector(
                    on_wake=self._on_wake,
                    threshold=WAKE_WORD_THRESHOLD,
                )
                print("  [Dell-Voice] Wake word: ready ✓")
            except Exception as e:
                print(f"  [Dell-Voice] Wake word unavailable: {e}")

        # ── Keyboard Trigger ──
        if HOTKEY_ENABLED:
            try:
                from audio.keyboard_trigger import KeyboardTrigger
                self._hotkey = KeyboardTrigger(
                    on_trigger=self._on_wake,
                    hotkey=VOICE_HOTKEY,
                )
                print(f"  [Dell-Voice] Hotkey: {VOICE_HOTKEY.upper()} ✓")
            except Exception as e:
                print(f"  [Dell-Voice] Hotkey unavailable: {e}")

        print("  [Dell-Voice] Boot complete.\n")
        return True

    def _on_wake(self):
        """Callback when wake word detected or hotkey pressed."""
        try:
            from audio.sound_effects import play_wake_sfx
            play_wake_sfx()
        except Exception:
            pass
        self._do_voice_turn()

    def _do_voice_turn(self):
        """One voice interaction: listen → send to ASUS → speak response."""
        if self._wake:
            self._wake.pause()

        try:
            # Listen
            text = self._stt.listen()
            if not text:
                print("  [Dell-Voice] Didn't catch that.")
                return

            print(f"  You (voice): {text}")

            # Send to ASUS for processing
            response = self._send_to_asus(text)
            if response:
                print(f"  Chaari: {response}")
                self._tts.speak(response)
            else:
                msg = "Sorry Boss, couldn't reach the brain. ASUS might be offline."
                print(f"  Chaari: {msg}")
                self._tts.speak(msg)

        finally:
            if self._wake:
                self._wake.resume()

    def _send_to_asus(self, text: str) -> str:
        """Send user text to ASUS over TCP and get response."""
        import socket

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(30.0)
            sock.connect((self.asus_host, self.asus_port))

            # Simple protocol: send JSON with type "voice_query"
            request = json.dumps({
                "type": "voice_query",
                "text": text,
                "source": "dell-voice",
            }).encode("utf-8")

            # Length-prefix
            length = len(request)
            sock.sendall(length.to_bytes(4, "big") + request)

            # Read response (length-prefixed)
            header = b""
            while len(header) < 4:
                chunk = sock.recv(4 - len(header))
                if not chunk:
                    return ""
                header += chunk

            resp_len = int.from_bytes(header, "big")
            data = b""
            while len(data) < resp_len:
                chunk = sock.recv(resp_len - len(data))
                if not chunk:
                    break
                data += chunk

            sock.close()

            resp = json.loads(data.decode("utf-8"))
            return resp.get("response", resp.get("text", ""))

        except Exception as e:
            print(f"  [Dell-Voice] ASUS connection error: {e}")
            return ""

    def start(self):
        """Start voice interface — wake word + hotkey listeners."""
        self._running = True

        if self._wake:
            self._wake.start()
        if self._hotkey:
            self._hotkey.start()

        print("  [Dell-Voice] Voice interface active.")
        print(f"  [Dell-Voice] Say 'Cherry wakeup' or press {VOICE_HOTKEY.upper()} to talk.\n")

    def stop(self):
        """Stop voice interface."""
        self._running = False
        if self._wake:
            self._wake.stop()
        if self._hotkey:
            self._hotkey.stop()
        if self._stt:
            self._stt.cleanup()

    def speak(self, text: str):
        """Speak text (used by agent for result announcements)."""
        if self._tts:
            self._tts.speak(text)

    def is_running(self) -> bool:
        return self._running
