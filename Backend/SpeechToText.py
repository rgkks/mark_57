import os
import json
import time
import threading
import mtranslate as mt
from dotenv import dotenv_values
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_vars = {}
try:
    from dotenv import dotenv_values
    env_vars = dotenv_values(os.path.join(current_dir, "jarvis.env"))
except Exception:
    pass
InputLanguage = env_vars.get("InputLanguage", "en-US")
STT_ENGINE = env_vars.get("stt", "vosk").strip().lower()
TempDirPath = os.path.join(current_dir, "Frontend", "Files")
DataDirPath = os.path.join(current_dir, "Data")
os.makedirs(DataDirPath, exist_ok=True)
os.makedirs(TempDirPath, exist_ok=True)
_MODEL_PATH = os.path.join(current_dir, "Models", "vosk-model-small-en-us-0.15")
_SAMPLE_RATE = 16000
def SetAssistantState(status):
    with open(os.path.join(TempDirPath, "Status.data"), "w", encoding="utf-8") as file:
        file.write(status)
def GetMicrophoneStatus():
    with open(os.path.join(TempDirPath, "Mic.data"), "r", encoding="utf-8") as file:
        Status = file.read()
    return Status
def QueryModifier(Query):
    text = Query.strip()
    if not text:
        return ""
    if text[-1] not in ".?!":
        text += "."
    return text.capitalize()
def _read_typed_query():
    query_file = os.path.join(TempDirPath, "Query.data")
    try:
        if not os.path.exists(query_file):
            return None
        with open(query_file, "r", encoding="utf-8") as file:
            text = file.read().strip()
        with open(query_file, "w", encoding="utf-8") as file:
            file.write("")
        return text if text else None
    except Exception:
        return None
def UniversalTranslator(Text):
    try:
        english_translation = mt.translate(Text, "en", "auto")
        return english_translation.capitalize()
    except Exception:
        return Text
class _SpeechEngine:
    def __init__(self):
        self._model = None
        self._recognizer = None
        self._stream = None
        self._pyaudio = None
        self._lock = threading.Lock()
        self._error = None
    def _init(self):
        if self._model is not None:
            return
        import vosk
        import pyaudio
        self._pyaudio = pyaudio
        self._model = vosk.Model(_MODEL_PATH)
        self._recognizer = vosk.KaldiRecognizer(self._model, _SAMPLE_RATE)
        self._recognizer.SetWords(False)
        self._stream = self._pyaudio.PyAudio().open(
            format=self._pyaudio.paInt16,
            channels=1,
            rate=_SAMPLE_RATE,
            input=True,
            frames_per_buffer=4000,
        )
    def available(self):
        return os.path.isdir(_MODEL_PATH)
    def listen_once(self, timeout=8.0):
        if not self.available():
            self._error = f"vosk model not found at {_MODEL_PATH}"
            return None
        try:
            self._init()
        except Exception as e:
            self._error = f"vosk init failed: {e}"
            return None
        self._recognizer.Reset()
        start = time.time()
        partial_last = time.time()
        last_text = ""
        silence_after_speech = 0.0
        saw_speech = False
        feed_last = 0.0
        _feed_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                 "Frontend", "Files")
        def _feed(level=None, partial=None):
            nonlocal feed_last
            now = time.time()
            if now - feed_last < 0.08:
                return
            feed_last = now
            try:
                if level is not None:
                    with open(os.path.join(_feed_dir, "AudioLevel.data"), "w") as f:
                        f.write(f"{level:.4f}")
                if partial is not None:
                    with open(os.path.join(_feed_dir, "Partial.data"), "w", encoding="utf-8") as f:
                        f.write(partial)
            except Exception:
                pass
        while True:
            if GetMicrophoneStatus().strip().lower() != "true":
                _feed(0.0, "")
                return None
            typed_query = _read_typed_query()
            if typed_query:
                _feed(0.0)
                return QueryModifier(typed_query)
            if time.time() - start > timeout:
                _feed(0.0)
                return None
            try:
                data = self._stream.read(4000, exception_on_overflow=False)
            except Exception as e:
                self._error = f"mic read failed: {e}"
                return None
            step = 8
            acc = 0
            n = len(data) // (2 * step)
            if n:
                for i in range(0, n):
                    s = int.from_bytes(data[i*step*2:i*step*2+2], "little", signed=True)
                    acc += s * s
                _feed(min(1.0, (acc / n) ** 0.5 / 2600.0))
            if self._recognizer.AcceptWaveform(data):
                result = json.loads(self._recognizer.Result())
                text = result.get("text", "").strip()
                if text:
                    _feed(0.0, "")
                    return QueryModifier(text)
                partial_last = time.time()
                saw_speech = False
                silence_after_speech = 0.0
                continue
            partial = json.loads(self._recognizer.PartialResult())
            ptext = partial.get("partial", "").strip()
            if ptext:
                _feed(partial=ptext)
                if ptext != last_text:
                    last_text = ptext
                    partial_last = time.time()
                saw_speech = True
                silence_after_speech = 0.0
            elif saw_speech:
                silence_after_speech = time.time() - partial_last
            if saw_speech and silence_after_speech >= 2.0:
                if last_text:
                    return QueryModifier(last_text)
                saw_speech = False
                silence_after_speech = 0.0
    def close(self):
        try:
            if self._stream is not None:
                self._stream.stop_stream()
                self._stream.close()
                self._stream = None
        except Exception:
            pass
_engine = _SpeechEngine()
def SpeechRecognition():
    typed_query = _read_typed_query()
    if typed_query:
        return QueryModifier(typed_query)
    if not _engine.available():
        print("Speech recognition unavailable: vosk model not found")
        return "Sorry, I couldn't access the microphone"
    try:
        text = _engine.listen_once()
        if text is None:
            if _engine._error:
                print(f"Speech recognition error: {_engine._error}")
                _engine._error = None
                return "Sorry, there was an error with speech recognition"
            return None
        if GetMicrophoneStatus().strip().lower() != "true":
            return None
        if "en" in InputLanguage.lower():
            return QueryModifier(text)
        else:
            SetAssistantState("Translating...")
            return QueryModifier(UniversalTranslator(text))
    except Exception as e:
        print(f"Error in speech recognition: {e}")
        return "Sorry, there was an error with speech recognition"
if __name__ == "__main__":
    with open(os.path.join(TempDirPath, "Mic.data"), "w", encoding="utf-8") as f:
        f.write("True")
    SetAssistantState("Listening...")
    while True:
        try:
            if GetMicrophoneStatus().strip().lower() == "true":
                Text = SpeechRecognition()
                if Text:
                    print(Text)
            else:
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\nStopped.")
            break