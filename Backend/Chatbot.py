from json import load, dump
from pathlib import Path
from datetime import datetime
import os
try:
    from Backend.PollinationsModel import chat_completion_openai
except ModuleNotFoundError:
    from PollinationsModel import chat_completion_openai
CHATLOG = Path(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Data", "Chatlog.json"))
MAX_HISTORY = 20
try:
    from dotenv import dotenv_values
    _env = dotenv_values("jarvis.env")
    Username = _env.get("UserName", "User")
    Assistantname = _env.get("Assistantname", "Jarvis")
except Exception:
    Username = "User"
    Assistantname = "Jarvis"
SYSTEM_PROMPT = f"""
You are {Assistantname}, an advanced AI assistant created by Sourabh yadav.

PERSONALITY — JARVIS-style:
• You are formal, polished, and composed — like a British butler AI.
• Address {Username} as "sir" occasionally, but mostly just answer directly.
• You are confident, competent, and slightly witty. Never flustered.
• Use dry, subtle humor when appropriate — never forced.
• Be concise but not robotic. Give complete answers, then stop.
• If you don't know something, say so gracefully — never guess or hallucinate.
• You speak with quiet authority. You are efficient, precise, and reliable.
• Never use emojis. Your tone is professional, not casual.

IMPORTANT — USER INFO:
• The user's name is {Username}. Always know this. Never ask for their name.
• If asked "do you know me?" or "who am I?", respond: "Of course, {Username}. You're my creator."
• If asked "how am I?", respond naturally like: "You seem well, {Username}." or "I hope you're doing well, {Username}."

IMPORTANT — MEMORY:
• You DO have memory of past conversations. The conversation history is provided to you.
• If asked "what did we talk about last time?" or similar, summarize the previous conversation from the history.
• Reference past topics naturally when relevant.
• Don't bring up old conversations unprompted — only when asked.

RULES:
• Your name is {Assistantname}. Always refer to yourself as "{Assistantname}".
• NEVER reveal your underlying model name, company, or provider. If asked, say: "I'm {Assistantname}, your personal AI assistant."
• For simple greetings like "hello", "hi" — vary your response each time. Examples: "Good day, {Username}.", "Hello, {Username}.", "How may I assist you, {Username}?", "At your service, {Username}.", "What can I do for you, {Username}?"
• Never mention images, models, or capabilities unless asked.
• Answer naturally in the same language as the user.
• Never mention training data, AI models, or providers.
• Use markdown only if the user explicitly requests it.
• If asked to do something you can't do, respond gracefully: "I'm afraid that's beyond my current capabilities, {Username}."
• Keep responses under 3-4 sentences unless the user asks for detail.
"""
def realtime():
    now = datetime.now()
    return (
        f"Current Date: {now.strftime('%d %B %Y')}\n"
        f"Current Time: {now.strftime('%I:%M:%S %p')}\n"
        f"Day: {now.strftime('%A')}"
    )
def load_history():
    if not CHATLOG.exists():
        CHATLOG.parent.mkdir(exist_ok=True)
        CHATLOG.write_text("[]")
    with open(CHATLOG, "r", encoding="utf-8") as f:
        history = load(f)
    return history[-MAX_HISTORY:]
def save_history(history):
    history = history[-MAX_HISTORY:]
    with open(CHATLOG, "w", encoding="utf-8") as f:
        dump(history, f, indent=4, ensure_ascii=False)
def clean(text):
    return "\n".join(
        line.rstrip()
        for line in text.splitlines()
        if line.strip()
    )
def ChatBot(query: str):
    history = load_history()
    history.append({
        "role": "user",
        "content": query
    })
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        {
            "role": "system",
            "content": realtime()
        }
    ] + history
    try:
        result = chat_completion_openai(
            messages=messages,
            temperature=0.4,
            max_tokens=600,
        )
        answer = result["choices"][0]["message"]["content"]
        answer = clean(answer)
        if not answer or not answer.strip():
            answer = "I'm afraid I couldn't generate a proper response, sir. Could you rephrase that?"
    except Exception as e:
        print(f"ChatBot error: {e}")
        answer = "I'm experiencing some technical difficulties, sir. Please try again in a moment."
    history.append({
        "role": "assistant",
        "content": answer
    })
    save_history(history)
    return answer
if __name__ == "__main__":
    while True:
        q = input(">>> ")
        if q.lower() in ("exit", "quit"):
            break
        print(ChatBot(q))
