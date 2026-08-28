from json import loads, dump
import datetime
import requests
from bs4 import BeautifulSoup
from dotenv import dotenv_values
try:
    from Backend.PollinationsModel import chat_completion
except ModuleNotFoundError:
    from PollinationsModel import chat_completion

# Load environment variables
en_vars = dotenv_values("jarvis.env")
Username = en_vars.get("UserName", "User")
Assistantname = en_vars.get("Assistantname", "Assistant")
# Realtime search uses legacy endpoint which only supports model="openai"
ModelName = "openai"

# System prompt
System = f"""You are {Assistantname}, an AI assistant. Answer the user's question using ONLY the search results below. If the search results don't contain the answer, say "I don't have that information." Be concise and professional."""

# Load or create chat history
try:
    with open("Data/Chatlog.json", "r") as f:
        messages = loads(f.read())
except (FileNotFoundError, ValueError):
    messages = []
    with open("Data/Chatlog.json", "w") as f:
        dump([], f)

def GoogleSearch(query):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers=headers,
            timeout=15
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        results = soup.select(".result")

        answer = f"The search results for '{query}' are:\n[start]\n"
        for r in results:
            a = r.select_one(".result__a")
            snippet = r.select_one(".result__snippet")
            title = a.get_text(strip=True) if a else ""
            desc = snippet.get_text(strip=True) if snippet else ""
            if title:
                answer += f"Title: {title}\nDescription: {desc}\n"
                if len(answer) > 2000:
                    break
        answer += "[end]"
    except Exception as e:
        answer = f"[start]\n[No search results available]\n[end]"
    return answer

def AnswerModifier(answer):
    lines = answer.split("\n")
    non_empty_lines = [line.strip() for line in lines if line.strip()]
    return "\n".join(non_empty_lines)

def Information():
    now = datetime.datetime.now()
    return (
        "Use this real-time Information if needed:\n"
        f"Day: {now.strftime('%A')}\n"
        f"Date: {now.strftime('%d')}\n"
        f"Month: {now.strftime('%B')}\n"
        f"Year: {now.strftime('%Y')}\n"
        f"Time: {now.strftime('%I')} hour {now.strftime('%M')} minute {now.strftime('%S')} second.\n"
    )

def RealtimeSearchEngine(prompt):
    global messages

    # Reload chat history
    try:
        with open("Data/Chatlog.json", "r") as f:
            messages = loads(f.read())
    except (FileNotFoundError, ValueError):
        messages = []

    messages.append({"role": "user", "content": prompt, "timestamp": datetime.datetime.now().isoformat()})

    search_result = GoogleSearch(prompt)
    info = Information()

    chat_sequence = [
        {"role": "system", "content": f"{System}\n\nCurrent date/time: {info}\n\nSearch results:\n{search_result}"},
        {"role": "user", "content": prompt}
    ]

    # Chat Completion
    result = chat_completion(
        messages=chat_sequence,
        temperature=0.7,
        max_tokens=512,
        top_p=1,
        model=ModelName,
    )
    answer = result["choices"][0]["message"]["content"]
    answer = answer.replace("</s>", "").strip()
    messages.append({"role": "assistant", "content": answer, "timestamp": datetime.datetime.now().isoformat()})

    with open("Data/Chatlog.json", "w") as f:
        dump(messages, f, indent=4)

    return AnswerModifier(answer)

if __name__ == "__main__":
    # print("🔍 Real-time AI Search Engine Started. Type 'exit' to quit.\n")
    while True:
        prompt = input("Enter your query: ")
        print(RealtimeSearchEngine(prompt))
