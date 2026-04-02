# CHAARI 2.0 — Dell Execution Node — Voice Configuration
# Lightweight voice config for Dell (4GB RAM laptop)

import os

# ── TTS (Edge TTS + pygame — same as ASUS) ──
ASSISTANT_VOICE = os.environ.get("CHAARI_VOICE", "en-US-AriaNeural")
HINDI_VOICE = os.environ.get("CHAARI_HINDI_VOICE", "hi-IN-SwaraNeural")
TTS_RATE = "+5%"
TTS_PITCH = "-20Hz"
INSTANT_MODE_MAX_WORDS = 25
ECHO_ENABLED = True
ECHO_DELAY_MS = 100
ECHO_VOLUME = 0.3
MAIN_VOLUME = 1.0
MIXER_FREQUENCY = 24000
MIXER_CHANNELS = 1
MIXER_BUFFER = 512
MIXER_NUM_CHANNELS = 8

# ── STT (speech_recognition — lightweight for Dell) ──
STT_BACKEND = "speech_recognition"  # Dell always uses lightweight backend
INPUT_LANGUAGE = os.environ.get("CHAARI_INPUT_LANG", "hi")
STT_TIMEOUT = 10.0

# ── Wake Word ──
WAKE_WORD = "Cherry wakeup"
WAKE_WORD_THRESHOLD = 0.5
WAKE_WORD_ENABLED = True

# ── Keyboard ──
VOICE_HOTKEY = "f5"
HOTKEY_ENABLED = True

# ── Paths ──
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIO_CACHE_DIR = os.path.join(BASE_DIR, "data", "audio_cache")
SOUNDS_DIR = os.path.join(BASE_DIR, "audio", "sounds")

os.makedirs(AUDIO_CACHE_DIR, exist_ok=True)
os.makedirs(SOUNDS_DIR, exist_ok=True)

# ── Network ──
ASUS_HOST = os.environ.get("CHAARI_ASUS_HOST", "192.168.1.100")
ASUS_PORT = int(os.environ.get("CHAARI_ASUS_PORT", "9734"))
