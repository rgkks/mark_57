from Frontend.GUI import (
    GraphicalUserInterface,
    SetAssistantStatus,
    ShowTextToScreen,
    TempDirectoryPath,
    SetMicrophoneStatus,
    AnswerModifier,
    QueryModifier,
    GetMicrophoneStatus,
    GetAssistantStatus ) 
from Backend.Model import FirstLayerDMM
from Backend.RealtimeSearchEngine import RealtimeSearchEngine
from Backend.Automation import Execute as Automation
from Backend.SpeechToText import SpeechRecognition, _read_typed_query
from Backend.Chatbot import ChatBot
from Backend.TextToSpeech import TextToSpeech
from dotenv import dotenv_values
from asyncio import run
from time import sleep
import subprocess
import threading
import json
import os
from datetime import datetime
_terminal_log = os.path.join(os.path.dirname(__file__), "Frontend", "Files", "Terminal.log")
os.makedirs(os.path.dirname(_terminal_log), exist_ok=True)
with open(_terminal_log, "w") as _f:
    _f.write("")
class _Tee:
    def __init__(self, original):
        self.original = original
    def write(self, text):
        self.original.write(text)
        self.original.flush()
        try:
            with open(_terminal_log, "a", encoding="utf-8") as f:
                f.write(text)
                f.flush()
        except: pass
    def flush(self):
        self.original.flush()
import sys
sys.stdout = _Tee(sys.stdout)
sys.stderr = _Tee(sys.stderr)
sys.stderr.flush = sys.stdout.flush
en_vars = dotenv_values("jarvis.env")
Username = en_vars.get("UserName")
Assistantname = en_vars.get("Assistantname")
subprocesses = []
Functions = ["automation"]
def LogToChatJson(role, content):
    try:
        path = "Data/Chatlog.json"
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                history = json.load(f)
        else:
            history = []
        history.append({"role": role, "content": content, "timestamp": datetime.now().isoformat()})
        if len(history) > 100:
            history = history[-100:]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4, ensure_ascii=False)
    except:
        pass
def ShowDefaultChatIfNoChats():
    File = open("Data/Chatlog.json","r", encoding="utf-8")
    if len(File.read())<5:
        with open(TempDirectoryPath('Database.data'), "w", encoding="utf-8") as file:
            file.write("")
        with open(TempDirectoryPath('Response.data'), "w", encoding="utf-8") as file:
            file.write("")
def ReadChatLogJson():
    with open("Data/Chatlog.json", "r", encoding="utf-8") as file:
        chatlog_data = json.load(file)
    return chatlog_data
def ChatLogIntegration():
    json_data = ReadChatLogJson()
    formatted_chatlog = ""
    for entry in json_data:
        if entry["role"] == "user":
            formatted_chatlog += f"User: {entry['content']}\n"
        elif entry["role"] == "assistant":
            formatted_chatlog += f"Assistant: {entry['content']}\n"
    formatted_chatlog = formatted_chatlog.replace("User", Username + " ")
    formatted_chatlog = formatted_chatlog.replace("Assistant", Assistantname + " ")
    with open(TempDirectoryPath('Database.data'), "w", encoding="utf-8") as file:
        file.write(AnswerModifier(formatted_chatlog))
def ShowChatsOnGUI():
    File = open(TempDirectoryPath('Database.data'), "r", encoding="utf-8")
    Data = File.read()
    if len(str(Data))>0:
        lines = Data.split("\n")
        result = "\n".join(lines)
        File.close()
        File = open(TempDirectoryPath('Response.data'), "w", encoding="utf-8")
        File.write(result)
        File.close()
def InitialExecution():
    SetMicrophoneStatus("False")
    ShowTextToScreen("")
    ShowDefaultChatIfNoChats()
InitialExecution()
def MainExecution():
    while True:
        TaskExecution = False
        ImageExecution = False
        VideoExecution = False
        ImageGenerationQuery = ""
        VideoGenerationQuery = ""
        typed = _read_typed_query()
        if typed:
            Query = QueryModifier(typed)
            SetAssistantStatus("Thinking...")
        elif GetMicrophoneStatus() == "True":
            SetAssistantStatus("Listening...")
            Query = SpeechRecognition()
            if not Query:
                continue
            try:
                with open(TempDirectoryPath("VoiceQuery.data"), "w", encoding="utf-8") as f:
                    f.write(Query)
            except Exception:
                pass
        else:
            sleep(0.3)
            continue
        if Query.startswith("Sorry,"):
            ShowTextToScreen(f"{Assistantname} : {Query}")
            SetAssistantStatus("Error")
            TextToSpeech(Query)
            continue
        SetAssistantStatus("Thinking...")
        Decision = FirstLayerDMM(Query)
        print("")
        print(f"Decision : {Decision}")
        print("")
        G = any([i for i in Decision if i.startswith("general")])
        R = any([i for i in Decision if i.startswith("realtime")])
        Mearged_query = " and ".join(
            ["".join(i.split()[1:]) for i in Decision if i.startswith("general") or i.startswith("realtime") or i.startswith("exit") or i.startswith("generate image") or i.startswith("generate video")]
        )
        for queries in Decision:
            q = str(queries).lower()
            if q.startswith("generate video") or ("generate" in q and "video" in q):
                VideoGenerationQuery = q.replace("generate video ", "").replace("generate video", "").strip()
                VideoExecution = True
            elif "generate" in q and any(w in q for w in ["image", "picture", "art"]):
                ImageGenerationQuery = q
                ImageExecution = True
            elif "generate" in q and not any(w in q for w in ["video", "image", "picture", "art"]):
                ImageGenerationQuery = q
                ImageExecution = True
        for queries in Decision:
            if TaskExecution == False:
                if any(queries.startswith(func) for func in Functions):
                    func_queries = [q for q in Decision if any(q.startswith(f) for f in Functions)]
                    run(Automation(func_queries))
                    TaskExecution = True
        if VideoExecution == True:
            SetAssistantStatus("Generating Video...")
            ShowTextToScreen(f"{Assistantname} : Generating video...")
            TextToSpeech("Generating video")
            with open("Frontend/Files/VideoGeneration.data", "w") as file:
                file.write(f"{VideoGenerationQuery},True")
            try:
                p1 = subprocess.Popen(['python', "Backend/VideoGeneration.py"],
                                      stdout=None, stderr=None,
                                      stdin=subprocess.DEVNULL, shell=False)
                subprocesses.append(p1)
                p1.wait()
                LogToChatJson("user", f"generate video {VideoGenerationQuery}")
                LogToChatJson("assistant", f"Video generated: {VideoGenerationQuery}")
                ShowTextToScreen(f"{Assistantname} : ▶video {VideoGenerationQuery}")
                SetAssistantStatus("Video generated")
                TextToSpeech("Video generated")
            except Exception as e:
                print(f"Error starting VideoGeneration.py: {e}")
                ShowTextToScreen(f"{Assistantname} : Failed to start video generation")
                TextToSpeech("Failed to start video generation")
            continue
        if ImageExecution == True:
            SetAssistantStatus("Generating Image...")
            ShowTextToScreen(f"{Assistantname} : Generating image...")
            TextToSpeech("Generating image")
            with open("Frontend/Files/ImageGeneration.data", "w") as file:
                file.write(f"{ImageGenerationQuery},True")
            try:
                p1 = subprocess.Popen(['python', "Backend/ImageGeneration.py"],
                                      stdout=None, stderr=None,
                                      stdin=subprocess.DEVNULL, shell=False)
                subprocesses.append(p1)
                p1.wait()
                image_filename = f"Data/{ImageGenerationQuery.strip().replace(' ', '_')}.jpg"
                with open("Frontend/Files/ImageDisplay.data", "w") as f:
                    f.write(image_filename)
                LogToChatJson("user", f"generate image {ImageGenerationQuery}")
                LogToChatJson("assistant", f"Image generated: {ImageGenerationQuery}")
                ShowTextToScreen(f"{Assistantname} : Image generated")
                SetAssistantStatus("Image generated")
                TextToSpeech("Image generated")
            except Exception as e:
                print(f"Error starting ImageGeneration.py: {e}")
                ShowTextToScreen(f"{Assistantname} : Failed to start image generation")
                TextToSpeech("Failed to start image generation")
            continue
        if G and R:
            SetAssistantStatus("Searching...")   
            Answer = RealtimeSearchEngine(QueryModifier(Mearged_query))
            ShowTextToScreen(f"{Assistantname} : {Answer}")
            SetAssistantStatus("Answering...")
            TextToSpeech(Answer)
            continue
        else:
            for Queries in Decision:
                if "general" in Queries:
                    SetAssistantStatus("Thinking...")
                    QueryFinal = Queries.replace("general ", "")
                    Answer = ChatBot(QueryModifier(QueryFinal))
                    ShowTextToScreen(f"{Assistantname} : {Answer}")
                    SetAssistantStatus("Answering...")
                    TextToSpeech(Answer)
                    continue
                elif "realtime" in Queries:
                    SetAssistantStatus("Searching...")
                    QueryFinal = Queries.replace("realtime ", "")
                    Answer = RealtimeSearchEngine(QueryModifier(QueryFinal))
                    ShowTextToScreen(f"{Assistantname} : {Answer}")
                    SetAssistantStatus("Answering...")
                    TextToSpeech(Answer)
                    continue
                elif "exit" in Queries:
                    QueryFinal = "Okay, Bye!"
                    Answer = ChatBot(QueryModifier(QueryFinal))
                    ShowTextToScreen(f"{Assistantname} : {Answer}")
                    SetAssistantStatus("Answering...")
                    TextToSpeech(Answer)
                    SetAssistantStatus("Answering...")
                    os._exit(1)
def FirstThread():
    SetMicrophoneStatus("False")
    while True:
        MainExecution()
def SecondThread():
    GraphicalUserInterface()
if __name__ == "__main__":
    while True:
        thread2 = threading.Thread(target=FirstThread, daemon=True)
        thread2.start()
        SecondThread()
