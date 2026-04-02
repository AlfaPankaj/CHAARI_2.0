# CHAARI 2.0 - audio/ - Interrupt Handler
# Manages user barge-in during TTS playback.

import threading
import time
from typing import Callable

from audio.tts_engine import TTSEngine
from audio.mic_listener import MicListener

class InterruptHandler:
    """
    Monitors the microphone for user speech while the TTS is active.
    If the user speaks, it stops the TTS playback.
    """

    def __init__(self, tts_engine: TTSEngine, mic_listener: MicListener, on_interrupt: Callable[[], None] = None):
        """
        Args:
            tts_engine: The TTS engine instance to control.
            mic_listener: The microphone listener to check for voice.
            on_interrupt: An optional callback function to execute when an interrupt occurs.
        """
        self.tts_engine = tts_engine
        self.mic_listener = mic_listener
        self.on_interrupt = on_interrupt

        self._monitoring = False
        self._interrupted = False
        self._monitor_thread = None
        self._lock = threading.Lock()

    def start(self):
        """Starts monitoring for interruptions in a background thread."""
        with self._lock:
            if self._monitoring:
                return
            self._monitoring = True
            self._interrupted = False
            self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self._monitor_thread.start()
            print("  [Interrupt] Handler started.")

    def stop(self):
        """Stops monitoring for interruptions."""
        with self._lock:
            if not self._monitoring:
                return
            self._monitoring = False
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=0.5)
        print("  [Interrupt] Handler stopped.")

    def is_interrupted(self) -> bool:
        """Returns True if an interruption occurred since monitoring started."""
        with self._lock:
            return self._interrupted

    def _monitor_loop(self):
        """The core loop that checks for voice activity."""
        time.sleep(0.2) 

        while True:
            with self._lock:
                if not self._monitoring:
                    break

            if self.tts_engine.is_speaking():
                if self.mic_listener.check_for_interrupt(duration=0.1):
                    print("  [Interrupt] Voice detected! Stopping TTS.")
                    self.tts_engine.stop()
                    with self._lock:
                        self._interrupted = True
                        self._monitoring = False 
                    if self.on_interrupt:
                        try:
                            self.on_interrupt()
                        except Exception as e:
                            print(f"  [Interrupt] Error in on_interrupt callback: {e}")
                    break 

            time.sleep(0.05) 

def speak_with_interrupt(
    text: str,
    tts_engine: TTSEngine,
    mic_listener: MicListener,
    on_interrupt: Callable[[], None] = None
) -> bool:
    """
    Speaks the given text while listening for user interruptions.

    Args:
        text: The text to be spoken.
        tts_engine: The initialized TTS engine.
        mic_listener: The initialized Mic listener.
        on_interrupt: An optional callback function to execute upon interruption.

    Returns:
        bool: True if the speech was interrupted, False otherwise.
    """
    if not text:
        return False

    handler = InterruptHandler(tts_engine, mic_listener, on_interrupt)
    handler.start()

    tts_engine.speak(text)

    handler.stop()

    return handler.is_interrupted()
