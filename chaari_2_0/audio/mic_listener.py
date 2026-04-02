# CHAARI 2.0 – audio/ - Mic Listener
# Captures audio from microphone with Voice Activity Detection
# NOTE: STT engines (Chrome, speech_recognition) manage their own mic access.
# This module is used by wake word detector and for direct audio capture.

import numpy as np
import sounddevice as sd
import threading
import time


SAMPLE_RATE = 16000          
CHANNELS = 1                 
BLOCK_SIZE = 1024            
SILENCE_THRESHOLD = 0.02     
SILENCE_DURATION = 1.5       
MAX_RECORD_SECONDS = 30      


class MicListener:
    """Captures audio from the microphone with voice activity detection."""

    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        channels: int = CHANNELS,
        silence_threshold: float = SILENCE_THRESHOLD,
        silence_duration: float = SILENCE_DURATION,
        max_record_seconds: float = MAX_RECORD_SECONDS,
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.silence_threshold = silence_threshold
        self.silence_duration = silence_duration
        self.max_record_seconds = max_record_seconds

        self._recording = False
        self._audio_frames: list[np.ndarray] = []
        self._lock = threading.Lock()

    def _get_amplitude(self, audio_block: np.ndarray) -> float:
        """Calculate RMS amplitude of an audio block."""
        return float(np.sqrt(np.mean(audio_block ** 2)))

    def is_voice_detected(self, audio_block: np.ndarray) -> bool:
        """Check if audio block contains voice (above threshold)."""
        return self._get_amplitude(audio_block) > self.silence_threshold

    def listen(self) -> np.ndarray | None:
        """
        Listen for voice input and return the recorded audio as a numpy array.

        Flow:
        1. Wait for voice (amplitude > threshold)
        2. Start recording
        3. Stop after silence_duration of silence
        4. Return audio data

        Returns None if no audio captured.
        """
        self._audio_frames = []
        self._recording = False
        silence_start = None
        recording_start = None

        print("  [Mic] Listening...", flush=True)

        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                blocksize=BLOCK_SIZE,
                dtype="float32",
            ) as stream:

                while True:
                    audio_block, _ = stream.read(BLOCK_SIZE)
                    amplitude = self._get_amplitude(audio_block)

                    if not self._recording:
                
                        if amplitude > self.silence_threshold:
                            self._recording = True
                            recording_start = time.time()
                            silence_start = None
                            self._audio_frames.append(audio_block.copy())
                    else:    
                        self._audio_frames.append(audio_block.copy())

                        if amplitude > self.silence_threshold:                 
                            silence_start = None
                        else:
                            if silence_start is None:
                                silence_start = time.time()
                            elif time.time() - silence_start >= self.silence_duration:
                                break

                       
                        if time.time() - recording_start >= self.max_record_seconds:
                            break

        except sd.PortAudioError as e:
            print(f"  [Mic] Audio device error: {e}")
            return None
        except Exception as e:
            print(f"  [Mic] Error: {e}")
            return None

        if not self._audio_frames:
            return None

        audio_data = np.concatenate(self._audio_frames, axis=0)
        duration = len(audio_data) / self.sample_rate
        print(f"  [Mic] Captured {duration:.1f}s of audio.", flush=True)

        return audio_data

    def check_for_interrupt(self, duration: float = 0.1) -> bool:
        """
        Quick check if there's voice input (used during TTS playback for interruption).
        Listens for a short duration and returns True if voice detected.
        """
        try:
            audio = sd.rec(
                int(self.sample_rate * duration),
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
            )
            sd.wait()
            return self._get_amplitude(audio) > self.silence_threshold
        except Exception:
            return False

    def get_amplitude_now(self) -> float:
        """Get current mic amplitude (single read)."""
        try:
            audio = sd.rec(
                int(self.sample_rate * 0.05),
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
            )
            sd.wait()
            return self._get_amplitude(audio)
        except Exception:
            return 0.0
