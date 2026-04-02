# CHAARI 2.0 – config/ - Voice Configuration
# STT, TTS, Wake Word, Keyboard settings

import os


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

FALLBACK_TTS_RATE = 175
FALLBACK_TTS_VOLUME = 0.9




STT_BACKEND = os.environ.get("CHAARI_STT_BACKEND", "chrome")

INPUT_LANGUAGE = os.environ.get("CHAARI_INPUT_LANG", "hi")

STT_TIMEOUT = 10.0

SILENCE_SHORT = 0.4        
SILENCE_MEDIUM = 0.7      
SILENCE_LONG = 1.0         



WAKE_WORD = "Cherry wakeup"
WAKE_WORD_THRESHOLD = 0.5   
WAKE_WORD_ENABLED = True



VOICE_HOTKEY = "f5"         
HOTKEY_ENABLED = True



BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIO_CACHE_DIR = os.path.join(BASE_DIR, "data", "audio_cache")
SOUNDS_DIR = os.path.join(BASE_DIR, "audio", "sounds")
VOICE_HTML_PATH = os.path.join(BASE_DIR, "data", "voice.html")

os.makedirs(AUDIO_CACHE_DIR, exist_ok=True)
os.makedirs(SOUNDS_DIR, exist_ok=True)
