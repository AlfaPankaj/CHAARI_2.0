# CHAARI 2.0 – audio/ - Sound Effects System
# Non-blocking SFX playback via pygame

import os
import pygame

try:
    from config.voice import SOUNDS_DIR, MIXER_FREQUENCY, MIXER_CHANNELS, MIXER_BUFFER, MIXER_NUM_CHANNELS
except ImportError:
    SOUNDS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sounds")
    MIXER_FREQUENCY = 24000
    MIXER_CHANNELS = 1
    MIXER_BUFFER = 512
    MIXER_NUM_CHANNELS = 8


# PYGAME MIXER INIT

_mixer_ready = False

def _ensure_mixer():
    """Initialize pygame mixer if not already done."""
    global _mixer_ready
    if _mixer_ready:
        return True
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init(
                frequency=MIXER_FREQUENCY,
                size=-16,
                channels=MIXER_CHANNELS,
                buffer=MIXER_BUFFER,
            )
        pygame.mixer.set_num_channels(MIXER_NUM_CHANNELS)
        _mixer_ready = True
        return True
    except Exception as e:
        print(f"  [SFX] Mixer init failed: {e}")
        return False


_sfx_cache: dict[str, pygame.mixer.Sound | None] = {
    "wake": None,
    "processing": None,
    "success": None,
    "error": None,
}


def _load_sfx():
    """Preload sound effect files from sounds/ directory."""
    if not _ensure_mixer():
        return

    mapping = {
        "wake": "wake.wav",
        "processing": "processing.wav",
        "success": "success.wav",
        "error": "error.wav",
    }

    for key, filename in mapping.items():
        path = os.path.join(SOUNDS_DIR, filename)
        if os.path.exists(path):
            try:
                _sfx_cache[key] = pygame.mixer.Sound(path)
            except Exception:
                _sfx_cache[key] = None


def _play_sfx(sound: pygame.mixer.Sound | None, volume: float = 0.8):
    """Play a short sound effect on any free channel (non-blocking)."""
    if sound is None:
        return
    if not _ensure_mixer():
        return
    try:
        chan = pygame.mixer.find_channel()
        if chan is not None:
            chan.set_volume(volume)
            chan.play(sound)
    except Exception:
        pass


def play_wake_sfx():
    """Play wake word detection sound."""
    _play_sfx(_sfx_cache.get("wake"), 0.9)


def play_processing_sfx():
    """Play processing/thinking sound."""
    _play_sfx(_sfx_cache.get("processing"), 0.6)


def play_success_sfx():
    """Play success/done sound."""
    _play_sfx(_sfx_cache.get("success"), 0.7)


def play_error_sfx():
    """Play error sound."""
    _play_sfx(_sfx_cache.get("error"), 0.7)


def play_custom_sfx(filepath: str, volume: float = 0.8):
    """Play any WAV file as a sound effect."""
    if not os.path.exists(filepath):
        return
    if not _ensure_mixer():
        return
    try:
        sound = pygame.mixer.Sound(filepath)
        _play_sfx(sound, volume)
    except Exception:
        pass



def init_sound_effects():
    """Initialize mixer and preload sound effects. Call once at boot."""
    if _ensure_mixer():
        _load_sfx()
        loaded = sum(1 for v in _sfx_cache.values() if v is not None)
        print(f"  [SFX] Loaded {loaded}/{len(_sfx_cache)} sound effects.")
    else:
        print("  [SFX] Sound effects disabled (no audio device).")
