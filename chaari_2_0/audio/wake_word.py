# CHAARI 2.0 – audio/ - Wake Word Detection
# Uses openwakeword for "Cherry wakeup" keyword detection
# Runs continuous mic listening in a background thread

import os
import time
import threading
import numpy as np

try:
    from config.voice import WAKE_WORD, WAKE_WORD_THRESHOLD, WAKE_WORD_ENABLED
except ImportError:
    WAKE_WORD = "Cherry wakeup"
    WAKE_WORD_THRESHOLD = 0.5
    WAKE_WORD_ENABLED = True

SAMPLE_RATE = 16000
CHUNK_SIZE = 1280  


class WakeWordDetector:
    """Detects wake word 'Cherry wakeup' using openwakeword.
    Runs a background thread that continuously listens to the mic."""

    def __init__(self, on_wake=None, threshold: float = WAKE_WORD_THRESHOLD):
        self.on_wake = on_wake  
        self.threshold = threshold
        self._listening = False
        self._thread = None
        self._lock = threading.Lock()
        self._model = None
        self._paused = False

    def load(self):
        """Load the openwakeword model."""
        try:
            import openwakeword
            from openwakeword.model import Model

            openwakeword.utils.download_models()

            self._model = Model(
                inference_framework="onnx",
            )
            print(f"  [Wake] Model loaded. Listening for: '{WAKE_WORD}'")
            return True

        except Exception as e:
            print(f"  [Wake] Failed to load model: {e}")
            return False

    def _listen_loop(self):
        """Background loop: read mic chunks and check for wake word."""
        import sounddevice as sd

        with self._lock:
            self._listening = True

        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                blocksize=CHUNK_SIZE,
                dtype="int16",
            ) as stream:
                while True:
                    with self._lock:
                        if not self._listening:
                            break
                        if self._paused:
                            time.sleep(0.1)
                            continue

                    audio_block, _ = stream.read(CHUNK_SIZE)
                    audio_int16 = audio_block.flatten()

                    
                    prediction = self._model.predict(audio_int16)

                    
                    for model_name, score in prediction.items():
                        if score > self.threshold:
                            print(f"\n  [Wake] Detected '{model_name}' (score={score:.2f})")
                            self._model.reset()
                            if self.on_wake:
                                self.on_wake()
                            time.sleep(1.0)
                            break

        except Exception as e:
            print(f"  [Wake] Listen loop error: {e}")
        finally:
            with self._lock:
                self._listening = False

    def start(self):
        """Start wake word detection in background thread."""
        if not WAKE_WORD_ENABLED:
            print("  [Wake] Wake word disabled in config.")
            return False

        if self._model is None:
            if not self.load():
                return False

        if self._thread and self._thread.is_alive():
            return True

        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        print("  [Wake] Detection started.")
        return True

    def stop(self):
        """Stop wake word detection."""
        with self._lock:
            self._listening = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        print("  [Wake] Detection stopped.")

    def pause(self):
        """Pause detection (e.g. during STT to avoid conflict)."""
        with self._lock:
            self._paused = True

    def resume(self):
        """Resume detection after pause."""
        with self._lock:
            self._paused = False

    def is_listening(self) -> bool:
        """Check if currently listening for wake word."""
        with self._lock:
            return self._listening and not self._paused

    def set_callback(self, on_wake):
        """Set the wake word detection callback."""
        self.on_wake = on_wake
