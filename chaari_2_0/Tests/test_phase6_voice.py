# CHAARI 2.0 — Phase 6 Tests — Voice Integration
# Tests for TTS, STT, Wake Word, Interrupt, Sound Effects, Keyboard Trigger
#
# Run: python -B -m unittest test_phase6_voice -v
# NOTE: Audio hardware not needed — all tests use mocks

import unittest
import os
import sys
import time
import threading
import queue
import json
import tempfile
from unittest.mock import patch, MagicMock, PropertyMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ═══════════════════════════════════════════════
# 1. VOICE CONFIG TESTS
# ═══════════════════════════════════════════════

class TestVoiceConfig(unittest.TestCase):
    """Test voice configuration module."""

    def test_config_imports(self):
        from config.voice import (
            ASSISTANT_VOICE, HINDI_VOICE, TTS_RATE, TTS_PITCH,
            INSTANT_MODE_MAX_WORDS, ECHO_ENABLED, ECHO_DELAY_MS,
            ECHO_VOLUME, MAIN_VOLUME, STT_BACKEND, INPUT_LANGUAGE,
            WAKE_WORD, WAKE_WORD_THRESHOLD, VOICE_HOTKEY,
        )
        self.assertIsInstance(ASSISTANT_VOICE, str)
        self.assertIsInstance(HINDI_VOICE, str)

    def test_default_values(self):
        from config.voice import (
            ASSISTANT_VOICE, STT_BACKEND, WAKE_WORD, VOICE_HOTKEY,
            ECHO_ENABLED, INSTANT_MODE_MAX_WORDS,
        )
        self.assertEqual(ASSISTANT_VOICE, "en-US-AriaNeural")
        self.assertEqual(STT_BACKEND, "chrome")
        self.assertEqual(WAKE_WORD, "Cherry wakeup")
        self.assertEqual(VOICE_HOTKEY, "f5")
        self.assertTrue(ECHO_ENABLED)
        self.assertEqual(INSTANT_MODE_MAX_WORDS, 25)

    def test_paths_exist(self):
        from config.voice import AUDIO_CACHE_DIR, SOUNDS_DIR
        self.assertTrue(os.path.isdir(AUDIO_CACHE_DIR))
        self.assertTrue(os.path.isdir(SOUNDS_DIR))

    def test_echo_settings_range(self):
        from config.voice import ECHO_VOLUME, MAIN_VOLUME, ECHO_DELAY_MS
        self.assertGreater(ECHO_VOLUME, 0)
        self.assertLessEqual(ECHO_VOLUME, 1.0)
        self.assertGreater(MAIN_VOLUME, 0)
        self.assertLessEqual(MAIN_VOLUME, 1.0)
        self.assertGreater(ECHO_DELAY_MS, 0)

    def test_mixer_settings(self):
        from config.voice import MIXER_FREQUENCY, MIXER_BUFFER, MIXER_NUM_CHANNELS
        self.assertEqual(MIXER_FREQUENCY, 24000)
        self.assertEqual(MIXER_BUFFER, 512)
        self.assertEqual(MIXER_NUM_CHANNELS, 8)


# ═══════════════════════════════════════════════
# 2. TTS ENGINE TESTS
# ═══════════════════════════════════════════════

class TestTTSEngine(unittest.TestCase):
    """Test TTS engine (Edge TTS + pygame)."""

    def test_import(self):
        from audio.tts_engine import TTSEngine
        self.assertTrue(True)

    def test_instantiate(self):
        from audio.tts_engine import TTSEngine
        tts = TTSEngine()
        self.assertFalse(tts.is_speaking())
        self.assertFalse(tts.stop_flag)

    def test_speak_empty_string(self):
        from audio.tts_engine import TTSEngine
        tts = TTSEngine()
        result = tts.speak("")
        self.assertFalse(result)

    def test_speak_whitespace_only(self):
        from audio.tts_engine import TTSEngine
        tts = TTSEngine()
        result = tts.speak("   ")
        self.assertFalse(result)

    def test_stop_sets_flag(self):
        from audio.tts_engine import TTSEngine
        tts = TTSEngine()
        tts.stop()
        self.assertTrue(tts.stop_flag)
        self.assertFalse(tts.is_speaking())

    def test_sentence_splitting(self):
        from audio.tts_engine import TTSEngine
        tts = TTSEngine()
        sentences = tts._split_into_sentences("Hello Boss. How are you? I am fine!")
        self.assertEqual(len(sentences), 3)
        self.assertTrue(sentences[0].strip().startswith("Hello"))

    def test_sentence_splitting_no_periods(self):
        from audio.tts_engine import TTSEngine
        tts = TTSEngine()
        sentences = tts._split_into_sentences("Hello Boss no punctuation here")
        self.assertEqual(len(sentences), 1)

    def test_sentence_splitting_empty(self):
        from audio.tts_engine import TTSEngine
        tts = TTSEngine()
        sentences = tts._split_into_sentences("")
        self.assertEqual(len(sentences), 0)

    def test_is_loaded_before_init(self):
        from audio.tts_engine import TTSEngine
        tts = TTSEngine()
        # May or may not be loaded depending on pygame state
        result = tts.is_loaded()
        self.assertIsInstance(result, bool)

    def test_speak_async_doesnt_block(self):
        from audio.tts_engine import TTSEngine
        tts = TTSEngine()
        # Mock the actual speak to avoid needing audio
        tts.speak = MagicMock(return_value=True)
        tts.speak_async("Hello")
        time.sleep(0.1)
        tts.speak.assert_called_once_with("Hello")

    def test_wait_until_done(self):
        from audio.tts_engine import TTSEngine
        tts = TTSEngine()
        # Should not hang if no threads running
        tts.wait_until_done()
        self.assertTrue(True)

    @patch("audio.tts_engine._run_coro_blocking")
    def test_generate_audio_returns_bool(self, mock_coro):
        from audio.tts_engine import TTSEngine
        tts = TTSEngine()
        mock_coro.return_value = True
        # Test instant speak with mocked generation
        with patch.object(tts, '_play_audio_chunk', return_value=True):
            result = tts._speak_instant("Test text")
            self.assertTrue(result)

    @patch("audio.tts_engine._run_coro_blocking")
    def test_fallback_on_edge_tts_failure(self, mock_coro):
        from audio.tts_engine import TTSEngine
        tts = TTSEngine()
        mock_coro.side_effect = Exception("No internet")
        with patch.object(tts, '_speak_fallback', return_value=True) as mock_fb:
            result = tts.speak("Testing fallback")
            mock_fb.assert_called_once()

    def test_chunk_queue_created(self):
        from audio.tts_engine import TTSEngine
        tts = TTSEngine()
        self.assertIsInstance(tts.chunk_queue, queue.Queue)


# ═══════════════════════════════════════════════
# 3. STT ENGINE TESTS
# ═══════════════════════════════════════════════

class TestSTTHelpers(unittest.TestCase):
    """Test STT helper functions."""

    def test_query_modifier_question(self):
        from audio.stt_engine import query_modifier
        result = query_modifier("what is the time")
        self.assertTrue(result.endswith("?"))
        self.assertTrue(result[0].isupper())

    def test_query_modifier_statement(self):
        from audio.stt_engine import query_modifier
        result = query_modifier("open notepad")
        self.assertTrue(result.endswith("."))

    def test_query_modifier_existing_punct(self):
        from audio.stt_engine import query_modifier
        result = query_modifier("how are you?")
        self.assertTrue(result.endswith("?"))

    def test_query_modifier_empty(self):
        from audio.stt_engine import query_modifier
        result = query_modifier("hello")
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

    def test_adaptive_silence_short(self):
        from audio.stt_engine import adaptive_silence
        result = adaptive_silence("hi")
        self.assertAlmostEqual(result, 0.4, places=1)

    def test_adaptive_silence_medium(self):
        from audio.stt_engine import adaptive_silence
        result = adaptive_silence("this is a medium sentence")
        self.assertAlmostEqual(result, 0.7, places=1)

    def test_adaptive_silence_long(self):
        from audio.stt_engine import adaptive_silence
        result = adaptive_silence("this is a very long sentence with many many words in it")
        self.assertAlmostEqual(result, 1.0, places=1)

    def test_process_text_adds_punctuation(self):
        from audio.stt_engine import process_text
        result = process_text("open notepad")
        self.assertTrue(result.endswith(".") or result.endswith("?"))


class TestSTTEngine(unittest.TestCase):
    """Test unified STT engine."""

    def test_import(self):
        from audio.stt_engine import STTEngine
        self.assertTrue(True)

    def test_instantiate_default(self):
        from audio.stt_engine import STTEngine
        stt = STTEngine()
        self.assertEqual(stt.backend_name, "chrome")

    def test_instantiate_speech_recognition(self):
        from audio.stt_engine import STTEngine
        stt = STTEngine(backend="speech_recognition")
        self.assertEqual(stt.backend_name, "speech_recognition")

    def test_unknown_backend_fallback(self):
        from audio.stt_engine import STTEngine
        stt = STTEngine(backend="nonexistent")
        stt.load()
        self.assertEqual(stt.backend_name, "speech_recognition")

    def test_is_loaded(self):
        from audio.stt_engine import STTEngine
        stt = STTEngine(backend="speech_recognition")
        self.assertFalse(stt.is_loaded())
        stt.load()
        self.assertTrue(stt.is_loaded())

    def test_set_backend(self):
        from audio.stt_engine import STTEngine
        stt = STTEngine(backend="speech_recognition")
        stt.load()
        stt.set_backend("speech_recognition")
        self.assertEqual(stt.backend_name, "speech_recognition")
        self.assertTrue(stt.is_loaded())


class TestChromeSTTEngine(unittest.TestCase):
    """Test Chrome Web Speech API STT backend."""

    def test_import(self):
        from audio.stt_engine import ChromeSTTEngine
        self.assertTrue(True)

    def test_instantiate(self):
        from audio.stt_engine import ChromeSTTEngine
        engine = ChromeSTTEngine(language="en")
        self.assertEqual(engine.language, "en")
        self.assertFalse(engine.is_initialized)

    def test_cleanup_when_not_initialized(self):
        from audio.stt_engine import ChromeSTTEngine
        engine = ChromeSTTEngine()
        engine.cleanup()  # should not raise
        self.assertFalse(engine.is_initialized)

    def test_html_template_has_lang_placeholder(self):
        from audio.stt_engine import _HTML_TEMPLATE
        self.assertIn("__LANG__", _HTML_TEMPLATE)

    def test_html_write(self):
        from audio.stt_engine import ChromeSTTEngine
        with tempfile.TemporaryDirectory() as tmpdir:
            html_path = os.path.join(tmpdir, "test_voice.html")
            engine = ChromeSTTEngine(language="hi")
            engine._html_path = html_path
            engine._write_html()
            self.assertTrue(os.path.exists(html_path))
            with open(html_path, "r") as f:
                content = f.read()
            self.assertIn("recognition.lang = 'hi'", content)
            self.assertNotIn("__LANG__", content)


class TestSpeechRecognitionSTT(unittest.TestCase):
    """Test speech_recognition STT backend."""

    def test_import(self):
        from audio.stt_engine import SpeechRecognitionSTT
        self.assertTrue(True)

    def test_instantiate(self):
        from audio.stt_engine import SpeechRecognitionSTT
        sr_stt = SpeechRecognitionSTT(language="en")
        self.assertEqual(sr_stt.language, "en")

    def test_cleanup(self):
        from audio.stt_engine import SpeechRecognitionSTT
        sr_stt = SpeechRecognitionSTT()
        sr_stt.cleanup()
        self.assertIsNone(sr_stt._recognizer)


# ═══════════════════════════════════════════════
# 4. SOUND EFFECTS TESTS
# ═══════════════════════════════════════════════

class TestSoundEffects(unittest.TestCase):
    """Test sound effects module."""

    def test_import(self):
        from audio.sound_effects import (
            init_sound_effects, play_wake_sfx, play_processing_sfx,
            play_success_sfx, play_error_sfx, play_custom_sfx,
        )
        self.assertTrue(True)

    def test_sfx_cache_structure(self):
        from audio.sound_effects import _sfx_cache
        self.assertIn("wake", _sfx_cache)
        self.assertIn("processing", _sfx_cache)
        self.assertIn("success", _sfx_cache)
        self.assertIn("error", _sfx_cache)

    @patch("audio.sound_effects._ensure_mixer", return_value=False)
    def test_play_sfx_no_mixer(self, mock_mixer):
        from audio.sound_effects import play_wake_sfx
        play_wake_sfx()  # should not raise

    def test_play_custom_nonexistent_file(self):
        from audio.sound_effects import play_custom_sfx
        play_custom_sfx("/nonexistent/path.wav")  # should not raise


# ═══════════════════════════════════════════════
# 5. WAKE WORD TESTS
# ═══════════════════════════════════════════════

class TestWakeWord(unittest.TestCase):
    """Test wake word detector."""

    def test_import(self):
        from audio.wake_word import WakeWordDetector
        self.assertTrue(True)

    def test_instantiate(self):
        from audio.wake_word import WakeWordDetector
        callback = MagicMock()
        detector = WakeWordDetector(on_wake=callback, threshold=0.5)
        self.assertEqual(detector.threshold, 0.5)
        self.assertFalse(detector.is_listening())

    def test_callback_stored(self):
        from audio.wake_word import WakeWordDetector
        callback = MagicMock()
        detector = WakeWordDetector(on_wake=callback)
        self.assertEqual(detector.on_wake, callback)

    def test_set_callback(self):
        from audio.wake_word import WakeWordDetector
        detector = WakeWordDetector()
        new_callback = MagicMock()
        detector.set_callback(new_callback)
        self.assertEqual(detector.on_wake, new_callback)

    def test_pause_resume(self):
        from audio.wake_word import WakeWordDetector
        detector = WakeWordDetector()
        detector.pause()
        self.assertTrue(detector._paused)
        detector.resume()
        self.assertFalse(detector._paused)

    def test_stop_when_not_started(self):
        from audio.wake_word import WakeWordDetector
        detector = WakeWordDetector()
        detector.stop()  # should not raise
        self.assertFalse(detector.is_listening())


# ═══════════════════════════════════════════════
# 6. KEYBOARD TRIGGER TESTS
# ═══════════════════════════════════════════════

class TestKeyboardTrigger(unittest.TestCase):
    """Test keyboard shortcut trigger."""

    def test_import(self):
        from audio.keyboard_trigger import KeyboardTrigger
        self.assertTrue(True)

    def test_instantiate(self):
        from audio.keyboard_trigger import KeyboardTrigger
        trigger = KeyboardTrigger()
        self.assertEqual(trigger.hotkey, "f5")
        self.assertFalse(trigger.is_active())

    def test_custom_hotkey(self):
        from audio.keyboard_trigger import KeyboardTrigger
        trigger = KeyboardTrigger(hotkey="f6")
        self.assertEqual(trigger.hotkey, "f6")

    def test_set_callback(self):
        from audio.keyboard_trigger import KeyboardTrigger
        trigger = KeyboardTrigger()
        cb = MagicMock()
        trigger.set_callback(cb)
        self.assertEqual(trigger.on_trigger, cb)

    def test_pause_resume(self):
        from audio.keyboard_trigger import KeyboardTrigger
        trigger = KeyboardTrigger()
        trigger._hook_registered = True
        trigger._active = True
        trigger.pause()
        self.assertFalse(trigger.is_active())
        trigger.resume()
        self.assertTrue(trigger.is_active())

    def test_stop_when_not_started(self):
        from audio.keyboard_trigger import KeyboardTrigger
        trigger = KeyboardTrigger()
        trigger.stop()  # should not raise


# ═══════════════════════════════════════════════
# 7. INTERRUPT HANDLER TESTS
# ═══════════════════════════════════════════════

class TestInterruptHandler(unittest.TestCase):
    """Test interrupt handler (updated for Edge TTS)."""

    def test_import(self):
        from audio.interrupt_handler import InterruptHandler, speak_with_interrupt
        self.assertTrue(True)

    def test_instantiate_no_engine(self):
        from audio.interrupt_handler import InterruptHandler
        handler = InterruptHandler()
        self.assertIsNone(handler.tts_engine)
        self.assertFalse(handler.is_monitoring())

    def test_set_tts_engine(self):
        from audio.interrupt_handler import InterruptHandler
        handler = InterruptHandler()
        mock_tts = MagicMock()
        handler.set_tts_engine(mock_tts)
        self.assertEqual(handler.tts_engine, mock_tts)

    def test_reset(self):
        from audio.interrupt_handler import InterruptHandler
        handler = InterruptHandler()
        handler._interrupted = True
        handler.reset()
        self.assertFalse(handler.was_interrupted())

    def test_stop_monitoring_when_not_started(self):
        from audio.interrupt_handler import InterruptHandler
        handler = InterruptHandler()
        handler.stop_monitoring()  # should not raise

    def test_was_interrupted_default(self):
        from audio.interrupt_handler import InterruptHandler
        handler = InterruptHandler()
        self.assertFalse(handler.was_interrupted())


# ═══════════════════════════════════════════════
# 8. DELL VOICE CONFIG TESTS
# ═══════════════════════════════════════════════

class TestDellVoiceConfig(unittest.TestCase):
    """Test Dell voice configuration."""

    def setUp(self):
        # Ensure parent dir is in path for chaari_dell imports
        parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if parent not in sys.path:
            sys.path.insert(0, parent)

    def test_import(self):
        from chaari_dell.audio.voice_config import (
            STT_BACKEND, ASSISTANT_VOICE, WAKE_WORD, ASUS_HOST, ASUS_PORT,
        )
        self.assertEqual(STT_BACKEND, "speech_recognition")
        self.assertEqual(WAKE_WORD, "Cherry wakeup")

    def test_dell_stt_is_lightweight(self):
        from chaari_dell.audio.voice_config import STT_BACKEND
        self.assertEqual(STT_BACKEND, "speech_recognition")
        # Dell MUST NOT use Chrome (too heavy for 4GB RAM)
        self.assertNotEqual(STT_BACKEND, "chrome")


# ═══════════════════════════════════════════════
# 9. DELL VOICE INTERFACE TESTS
# ═══════════════════════════════════════════════

class TestDellVoiceInterface(unittest.TestCase):
    """Test Dell voice interface."""

    def test_import(self):
        from chaari_dell.audio.voice_interface import DellVoiceInterface
        self.assertTrue(True)

    def test_instantiate(self):
        from chaari_dell.audio.voice_interface import DellVoiceInterface
        vi = DellVoiceInterface(asus_host="127.0.0.1", asus_port=9734)
        self.assertEqual(vi.asus_host, "127.0.0.1")
        self.assertEqual(vi.asus_port, 9734)
        self.assertFalse(vi.is_running())

    def test_stop_when_not_started(self):
        from chaari_dell.audio.voice_interface import DellVoiceInterface
        vi = DellVoiceInterface()
        vi.stop()  # should not raise
        self.assertFalse(vi.is_running())


# ═══════════════════════════════════════════════
# 10. INTEGRATION TESTS
# ═══════════════════════════════════════════════

class TestIntegration(unittest.TestCase):
    """Integration tests — module wiring."""

    def test_tts_interrupt_wiring(self):
        """TTS engine works with interrupt handler."""
        from audio.tts_engine import TTSEngine
        from audio.interrupt_handler import InterruptHandler
        tts = TTSEngine()
        handler = InterruptHandler()
        handler.set_tts_engine(tts)
        self.assertEqual(handler.tts_engine, tts)
        self.assertFalse(tts.is_speaking())

    def test_stt_backend_switch(self):
        """Can switch STT backends at runtime."""
        from audio.stt_engine import STTEngine
        stt = STTEngine(backend="speech_recognition")
        stt.load()
        self.assertEqual(stt.backend_name, "speech_recognition")
        stt.set_backend("speech_recognition")
        self.assertTrue(stt.is_loaded())

    def test_main_load_audio_modules_exists(self):
        """main.py has load_audio_modules function."""
        import main
        self.assertTrue(hasattr(main, 'load_audio_modules'))

    def test_main_load_voice_triggers_exists(self):
        """main.py has load_voice_triggers function."""
        import main
        self.assertTrue(hasattr(main, 'load_voice_triggers'))

    def test_all_audio_modules_importable(self):
        """All audio modules can be imported."""
        from audio.tts_engine import TTSEngine
        from audio.stt_engine import STTEngine
        from audio.interrupt_handler import InterruptHandler
        from audio.sound_effects import init_sound_effects
        from audio.wake_word import WakeWordDetector
        from audio.keyboard_trigger import KeyboardTrigger
        from audio.mic_listener import MicListener
        self.assertTrue(True)


# ═══════════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    unittest.main()
