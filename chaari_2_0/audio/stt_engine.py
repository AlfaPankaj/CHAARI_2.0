# CHAARI 2.0 – audio/ - STT Engine
# Dual-backend Speech-to-Text:
#   ASUS: Chrome Web Speech API (via Selenium) — best accuracy, needs internet + Chrome
#   Dell:  speech_recognition library (Google Speech) — lightweight, needs internet
# Fallback: faster-whisper (offline)

import os
import re
import time
import warnings
import atexit

try:
    from config.voice import (
        STT_BACKEND, INPUT_LANGUAGE, STT_TIMEOUT,
        SILENCE_SHORT, SILENCE_MEDIUM, SILENCE_LONG,
        VOICE_HTML_PATH,
    )
except ImportError:
    STT_BACKEND = "chrome"
    INPUT_LANGUAGE = "hi"
    STT_TIMEOUT = 10.0
    SILENCE_SHORT = 0.4
    SILENCE_MEDIUM = 0.7
    SILENCE_LONG = 1.0
    VOICE_HTML_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "voice.html",
    )

warnings.filterwarnings("ignore")



def detect_language(text: str) -> str:
    """Detect language of text, suppress warnings."""
    try:
        from langdetect import detect
        import sys
        from io import StringIO
        old_stderr = sys.stderr
        sys.stderr = StringIO()
        result = detect(text)
        sys.stderr = old_stderr
        return result
    except Exception:
        return "unknown"


def translate_to_english(text: str) -> str:
    """Translate non-English text to English. Fast-skips for English/ASCII."""
    if not text:
        return ""
        
    if all(ord(c) < 128 for c in text):
        return text

    try:
        import mtranslate as mt
        lang = detect_language(text)
        if lang != "en":
            return mt.translate(text, "en", lang)
    except Exception:
        pass
    return text


def query_modifier(query: str) -> str:
    """Add punctuation: ? for questions, . for statements."""
    new_query = query.lower().strip()
    words = new_query.split()
    if not words:
        return query

    question_words = {
        "who", "what", "when", "where", "why", "how", "which", "whom", "whose",
        "do", "does", "did", "is", "are", "can", "could", "would", "should",
        "will", "shall", "may", "might", "tell", "show", "search",
    }

    if any(w in question_words for w in words):
        if words[-1][-1] in ".?!":
            new_query = new_query[:-1] + "?"
        else:
            new_query += "?"
    else:
        if words[-1][-1] in ".!?":
            new_query = new_query[:-1] + "."
        else:
            new_query += "."

    return new_query.capitalize()


def adaptive_silence(text: str) -> float:
    """Adaptive timeout based on text length."""
    words = len(text.split())
    if words < 3:
        return SILENCE_SHORT
    elif words < 7:
        return SILENCE_MEDIUM
    return SILENCE_LONG


def process_text(text: str) -> str:
    """Process transcribed text: detect language, translate, add punctuation."""
    text = translate_to_english(text)
    text = query_modifier(text)
    return text




_HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head><title>Speech Recognition</title></head>
<body>
    <button id="start" onclick="startRecognition()">Start</button>
    <button id="end" onclick="stopRecognition()">Stop</button>
    <p id="output"></p>
    <script>
        const output = document.getElementById('output');
        let recognition;
        let silenceTimer;
        const SILENCE_TIMEOUT = 600; // 600ms silence = natural human pause

        function startRecognition() {
            try {
                navigator.mediaDevices.getUserMedia({ 
                    audio: { 
                        echoCancellation: true, 
                        noiseSuppression: true, 
                        autoGainControl: true 
                    } 
                }).then(stream => {
                    document.body.setAttribute('data-listening', 'true');
                    recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
                    recognition.lang = '__LANG__';
                    recognition.continuous = true;
                    recognition.interimResults = true;

                    recognition.onresult = function(event) {
                        clearTimeout(silenceTimer);
                        
                        let interimTranscript = '';
                        let finalTranscript = '';
                        for (let i = event.resultIndex; i < event.results.length; ++i) {
                            if (event.results[i].isFinal) {
                                finalTranscript += event.results[i][0].transcript;
                            } else {
                                interimTranscript += event.results[i][0].transcript;
                            }
                        }
                        output.textContent = finalTranscript + interimTranscript;

                        if (output.textContent.trim().length > 0) {
                            silenceTimer = setTimeout(() => {
                                stopRecognition();
                            }, SILENCE_TIMEOUT);
                        }
                    };

                    recognition.onstart = function() {
                        silenceTimer = setTimeout(() => { stopRecognition(); }, 8000);
                    };

                    recognition.onend = function() {
                        clearTimeout(silenceTimer);
                        document.body.setAttribute('data-listening', 'false');
                        stream.getTracks().forEach(track => track.stop());
                    };

                    recognition.start();
                }).catch(e => {
                    output.textContent = 'Mic Error: ' + e.message;
                    document.body.setAttribute('data-listening', 'false');
                });
            } catch(e) {
                output.textContent = 'Error: ' + e.message;
            }
        }

        function stopRecognition() {
            if (recognition) {
                recognition.stop();
                clearTimeout(silenceTimer);
            }
        }
    </script>
</body>
</html>'''


class ChromeSTTEngine:
    """Speech-to-Text using Chrome headless + Web Speech API."""

    def __init__(self, language: str = INPUT_LANGUAGE):
        self.language = language
        self.driver = None
        self.is_initialized = False
        self.retry_count = 0
        self.max_retries = 3
        self.on_partial_transcript = None  # callback(str)
        self._html_path = VOICE_HTML_PATH

        atexit.register(self.cleanup)

    def _write_html(self):
        """Write the speech recognition HTML file with configured language."""
        html = _HTML_TEMPLATE.replace("__LANG__", self.language)
        os.makedirs(os.path.dirname(self._html_path), exist_ok=True)
        with open(self._html_path, "w", encoding="utf-8") as f:
            f.write(html)

    def initialize_driver(self) -> bool:
        """Initialize Chrome headless driver."""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from webdriver_manager.chrome import ChromeDriverManager

            self._write_html()

            chrome_options = Options()
            chrome_options.add_argument("--use-fake-ui-for-media-stream")
            chrome_options.add_argument("--use-fake-device-for-media-stream")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--log-level=3")
            chrome_options.add_argument("--headless=new")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])

            if self.driver:
                try:
                    self.driver.quit()
                except Exception:
                    pass

            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)

            file_url = "file:///" + self._html_path.replace("\\", "/")
            self.driver.get(file_url)
            time.sleep(0.01)

            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "start"))
            )

            self.is_initialized = True
            self.retry_count = 0
            return True

        except Exception as e:
            print(f"  [STT-Chrome] Driver init error: {e}")
            self.is_initialized = False
            return False

    def _capture_speech(self) -> str:
        """Capture speech via Chrome Web Speech API with Event-Sync."""
        prev_text = ""
        start_time = time.time()

        try:
            self.driver.execute_script("document.getElementById('output').textContent = ''; startRecognition();")
            
            while True:
                state = self.driver.execute_script("""
                    return {
                        text: document.getElementById('output').textContent.trim(),
                        is_listening: document.body.getAttribute('data-listening') === 'true'
                    };
                """)
                
                text = state['text']
                is_listening = state['is_listening']
                now = time.time()

                if text != prev_text:
                    if text:
                        print(f"\r🎙️ {text}", end="", flush=True)
                    if self.on_partial_transcript and text:
                        self.on_partial_transcript(text)
                    prev_text = text

                if not is_listening and prev_text:
                    break

                if not is_listening and (now - start_time > 2.0): 
                    break
                if now - start_time > STT_TIMEOUT: 
                    break

                time.sleep(0.01)

            print() 
            return prev_text

        except Exception as e:
            print(f"\n  [STT-Chrome] Sync Error: {e}")
            raise

    def listen(self) -> str:
        """Listen for speech, return processed text."""
        if not self.is_initialized:
            if not self.initialize_driver():
                return ""

        try:
            raw_text = self._capture_speech()
            if raw_text:
                return process_text(raw_text)
            return ""
        except Exception as e:
            print(f"  [STT-Chrome] Listen error: {e}")
            if self.retry_count < self.max_retries:
                self.retry_count += 1
                print(f"  [STT-Chrome] Retry {self.retry_count}/{self.max_retries}...")
                self.cleanup()
                if self.initialize_driver():
                    return self.listen()
            return ""

    def cleanup(self):
        """Cleanup Chrome driver."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
            self.is_initialized = False

    def restart(self) -> bool:
        """Restart Chrome driver."""
        self.cleanup()
        return self.initialize_driver()



class SpeechRecognitionSTT:
    """Lightweight STT using speech_recognition library + Google Speech API."""

    def __init__(self, language: str = INPUT_LANGUAGE):
        self.language = language
        self._recognizer = None
        self._microphone = None

    def _ensure_recognizer(self):
        """Lazy-init the recognizer and microphone."""
        if self._recognizer is None:
            import speech_recognition as sr
            self._recognizer = sr.Recognizer()
            self._microphone = sr.Microphone()
            with self._microphone as source:
                self._recognizer.adjust_for_ambient_noise(source, duration=0.5)
            print("  [STT-SR] Recognizer initialized.")

    def listen(self) -> str:
        """Listen for speech, return processed text."""
        import speech_recognition as sr

        self._ensure_recognizer()

        try:
            print("  [STT-SR] Listening...", flush=True)
            with self._microphone as source:
                audio = self._recognizer.listen(
                    source,
                    timeout=5,
                    phrase_time_limit=int(STT_TIMEOUT),
                )

            print("  [STT-SR] Recognizing...", flush=True)
            try:
                text = self._recognizer.recognize_google(audio, language=self.language)
            except sr.UnknownValueError:
                return ""
            except sr.RequestError as e:
                print(f"  [STT-SR] Google API error: {e}")
                return ""

            if text:
                return process_text(text)
            return ""

        except sr.WaitTimeoutError:
            return ""
        except Exception as e:
            print(f"  [STT-SR] Error: {e}")
            return ""

    def transcribe_file(self, file_path: str) -> str:
        """Transcribe an audio file."""
        import speech_recognition as sr
        self._ensure_recognizer()
        
        try:
            with sr.AudioFile(file_path) as source:
                audio = self._recognizer.record(source)
            
            text = self._recognizer.recognize_google(audio, language=self.language)
            if text:
                return process_text(text)
        except Exception as e:
            print(f"  [STT-SR] File transcription error: {e}")
        return ""

    def cleanup(self):
        """Nothing to clean up."""
        self._recognizer = None
        self._microphone = None

    def restart(self) -> bool:
        """Reset the recognizer."""
        self.cleanup()
        self._ensure_recognizer()
        return True



class STTEngine:
    """Unified STT engine that routes to the configured backend."""

    def __init__(self, backend: str = STT_BACKEND, language: str = "hi-IN"):
        self.backend_name = backend
        self.language = language
        self._engine = None

    def load(self):
        """Load the configured STT backend."""
        if self.backend_name == "chrome":
            self._engine = ChromeSTTEngine(language=self.language)
            print(f"  [STT] Backend: Chrome Web Speech API (lang={self.language})")
        elif self.backend_name == "speech_recognition":
            self._engine = SpeechRecognitionSTT(language=self.language)
            print(f"  [STT] Backend: speech_recognition (lang={self.language})")
        else:
            print(f"  [STT] Unknown backend '{self.backend_name}', defaulting to speech_recognition.")
            self._engine = SpeechRecognitionSTT(language=self.language)
            self.backend_name = "speech_recognition"

    def listen(self) -> str:
        """Listen for speech and return transcribed text."""
        if self._engine is None:
            self.load()
        return self._engine.listen()

    def cleanup(self):
        """Cleanup the active backend."""
        if self._engine:
            self._engine.cleanup()

    def restart(self) -> bool:
        """Restart the active backend."""
        if self._engine:
            return self._engine.restart()
        return False

    def set_backend(self, backend: str):
        """Switch STT backend at runtime."""
        self.cleanup()
        self.backend_name = backend
        self._engine = None
        self.load()

    def is_loaded(self) -> bool:
        """Check if a backend is loaded."""
        return self._engine is not None



if __name__ == "__main__":
    print("\n" + "═"*50)
    print("  CHAARI 2.0 — STT Speed & Accuracy Test")
    print("═"*50)
    
    engine = STTEngine(backend="chrome", language="hi-IN")
    
    try:
        print("\n  [Test] Initializing Chrome Driver...")
        engine.load()
        print("  [Test] Ready! Speak now (Hindi or English).")
        print("  [Test] Press Ctrl+C to stop testing.\n")
        
        while True:
            start = time.time()
            text = engine.listen()
            duration = time.time() - start
            
            if text:
                print(f"\n  [Result] \"{text}\"")
                print(f"  [Latency] {duration:.2f}s (Total roundtrip)")
                print("  " + "─"*30)
            else:
                print("\r  [Status] Listening...      ", end="", flush=True)

    except KeyboardInterrupt:
        print("\n\n  [Test] Testing stopped by user.")
    except Exception as e:
        print(f"\n  [Error] Test failed: {e}")
    finally:
        engine.cleanup()
        print("  [Test] Cleanup complete.")
