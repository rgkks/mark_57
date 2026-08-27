import pygame
import random
import asyncio
import edge_tts
import os
import struct
import math
from dotenv import dotenv_values
en_vars = dotenv_values("jarvis.env")
AssistantVoice = en_vars.get("AssistantVoice", "en-CA-LiamNeural")
GlitchEnabled = en_vars.get("Glitch", "true").strip().lower() in ("1", "true", "yes", "on")
GlitchIntensity = float(en_vars.get("GlitchIntensity", "0.6"))
_current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SPEAKING_FILE = os.path.join(_current_dir, "Frontend", "Files", "Speaking.data")
def _set_speaking(speaking):
    try:
        with open(_SPEAKING_FILE, "w", encoding="utf-8") as f:
            f.write("True" if speaking else "False")
    except Exception:
        pass
async def TextToAudioFile(text) -> None:
    file_path = "Data/speech.mp3"
    if os.path.exists(file_path):
        os.remove(file_path)
    communicate = edge_tts.Communicate(text, AssistantVoice, pitch="+5Hz", rate="+13%")
    await communicate.save("Data/speech.mp3")
    if GlitchEnabled:
        _apply_glitch(file_path, GlitchIntensity)
def _apply_glitch(file_path: str, intensity: float = 0.6) -> None:
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(file_path)
        audio = audio.set_sample_width(2).set_frame_rate(16000)
        sr = audio.frame_rate
        samples = audio.get_array_of_samples()
        mod = 38.0  # Hz robot wobble
        out = []
        for i, s in enumerate(samples):
            m = 0.7 + 0.3 * math.sin(2 * math.pi * mod * i / sr)
            out.append(max(-32768, min(32767, int(s * m))))
        payload = struct.pack("<%dh" % len(out), *out)
        audio = audio._spawn(payload)
        seg = audio
        dur = len(seg)
        chunks = []
        i = 0
        rnd = random.Random(7)
        while i < dur:
            w = rnd.randint(300, 900)
            if rnd.random() < 0.15 * intensity:
                chunks.append(seg[i:i + w])
            chunks.append(seg[i:i + w])
            i += w
        seg = sum(chunks, AudioSegment.silent(duration=0, frame_rate=seg.frame_rate))[:dur]
        seg.export(file_path, format="mp3")
    except Exception as e:
        print(f"Glitch effect skipped: {e}")
def TTS(Text, func=lambda r=None: True):
    while True:
        try:
            asyncio.run(TextToAudioFile(Text))
            pygame.mixer.init()
            pygame.mixer.music.load("Data/speech.mp3")
            pygame.mixer.music.play()
            _set_speaking(True)
            while pygame.mixer.music.get_busy():
                if func() == False:
                    break
                pygame.time.Clock().tick(10)
            _set_speaking(False)
            return True
        except Exception as e:
            print(f"Error in TTS: {e}")
            return False
        finally:
            try:
                func(False)
                if pygame.mixer.get_init():
                    pygame.mixer.music.stop()
                    pygame.mixer.quit()
            except Exception as e:
                print(f"Error in finally block: {e}")
def TextToSpeech(Text, func=lambda r=None: True):
        Data = str(Text).split(".")
        responses = [
            "The rest of the result has been printed to the chat screen, kindly check it out sir.",
            "The rest of the text is now on the chat screen, sir, please check it.",
            "You can see the rest of the text on the chat screen, sir.",
            "The remaining part of the text is now on the chat screen, sir.",
            "Sir, you'll find more text on the chat screen for you to see.",
            "The rest of the answer is now on the chat screen, sir.",
            "Sir, please look at the chat screen, the rest of the answer is there.",
            "You'll find the complete answer on the chat screen, sir.",
            "The next part of the text is on the chat screen, sir.",
            "Sir, please check the chat screen for more information.",
            "There's more text on the chat screen for you, sir.",
            "Sir, take a look at the chat screen for additional text.",
            "You'll find more to read on the chat screen, sir.",
            "Sir, check the chat screen for the rest of the text.",
            "The chat screen has the rest of the text, sir.",
            "There's more to see on the chat screen, sir, please look.",
            "Sir, the chat screen holds the continuation of the text.",
            "You'll find the complete answer on the chat screen, kindly check it out sir.",
            "Please review the chat screen for the rest of the text, sir.",
            "Sir, look at the chat screen for the complete answer."
        ]
        if len(Data) > 4 and len(Data) > 250:
            TTS(" ".join(Text.split(".")[:2]) + ". " + random.choice(responses), func)
        else:
            TTS(Text, func)
if __name__ == "__main__":
    while True:
        TextToSpeech(input("Enter the text: "))