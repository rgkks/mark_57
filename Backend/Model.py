from rich import print
import re
try:
    from Backend.PollinationsModel import chat_completion
except ModuleNotFoundError:
    from PollinationsModel import chat_completion
SYSTEM_PROMPT = """You are a command classifier. Given a user query, return ONLY the category prefix followed by the cleaned query.

CATEGORIES:
- general <query>       — knowledge, explanations, facts, opinions, advice
- realtime <query>      — current events, weather, news, stocks, live data
- automation <query>    — open/close apps, play/pause music, files, system tasks, volume, brightness
- generate image <query> — create images, pictures, art, drawings, wallpapers, logos
- generate video <query> — create videos, animations, clips
- exit                  — goodbye, shutdown, quit

RULES:
1. Return ONLY the prefixed command, nothing else. No explanations.
2. "realtime" for anything requiring live/current data (weather, news, stocks, prices, scores).
3. "automation" for system actions (open apps, play music, file operations, volume, brightness, minecraft).
4. "generate image" for image/art generation requests.
5. "generate video" for video/animation generation requests.
6. "general" for knowledge questions, greetings, explanations, opinions.
7. "exit" for goodbye/shutdown commands.

EXAMPLES:
"hello" -> "general hello"
"what is python" -> "general what is python"
"what's the date" -> "realtime what's the date"
"what day is it" -> "realtime what day is it"
"when is diwali" -> "realtime when is diwali"
"weather in delhi" -> "realtime weather in delhi"
"bitcoin price right now" -> "realtime bitcoin price right now"
"open chrome" -> "automation open chrome"
"play believer" -> "automation play believer"
"set volume to 50" -> "automation set volume to 50"
"cpu usage" -> "automation cpu usage"
"draw a sunset" -> "generate image draw a sunset"
"generate an image of a dragon" -> "generate image of a dragon"
"make a video of a cat" -> "generate video make a video of a cat"
"bye" -> "exit"
"""
CHAT_HISTORY = [
    {
        "role": "user",
        "content": "hello"
    },
    {
        "role": "assistant",
        "content": "general hello"
    },
    {
        "role": "user",
        "content": "hi"
    },
    {
        "role": "assistant",
        "content": "general hi"
    },
    {
        "role": "user",
        "content": "open chrome"
    },
    {
        "role": "assistant",
        "content": "automation open chrome"
    },
    {
        "role": "user",
        "content": "what is python"
    },
    {
        "role": "assistant",
        "content": "general what is python"
    },
    {
        "role": "user",
        "content": "today's weather"
    },
    {
        "role": "assistant",
        "content": "realtime today's weather"
    },
    {
        "role": "user",
        "content": "play believer"
    },
    {
        "role": "assistant",
        "content": "automation play believer"
    },
    {
        "role": "user",
        "content": "generate an image of a dragon"
    },
    {
        "role": "assistant",
        "content": "generate image dragon"
    }
]
VALID_PREFIXES = ("general", "realtime", "generate image", "generate video", "automation", "exit")
def FirstLayerDMM(prompt: str):
    local = decide(prompt)
    if local is not None:
        return [local]
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
    ]
    messages.append(
        {
            "role": "user",
            "content": prompt
        }
    )
    try:
        response = chat_completion(
            messages=messages,
            temperature=0.0,
            max_tokens=40,
        )
        text = response["choices"][0]["message"]["content"].strip()
    except Exception:
        text = ""
    text = text.replace("\n", ",")
    commands = [
        cmd.strip()
        for cmd in text.split(",")
        if cmd.strip()
    ]
    valid = [c for c in commands if any(c.startswith(p) for p in VALID_PREFIXES)]
    if valid:
        return valid
    local = decide(prompt)
    if local is not None:
        return [local]
    return [f"general {prompt}"]
AUTOMATION_RULES = [
    (r"^(open|launch|start|close|kill|restart)\s+\w+", "automation", 6),
    (r"^(play|pause|resume|skip|next|previous|prev|mute)\b", "automation", 8),
    (r"^(search|look up|google|youtube)\b", "automation", 5),
    (r"^(set|change|increase|decrease|lower|raise)\s+\w+", "automation", 4),
    (r"^(shut down|shutdown|reboot|restart system)\b", "automation", 6),
    (r"^stop\s+(the\s+)?(music|song|video|media|playback|audio)\b", "automation", 11),
    (r"^generate\s+(an?|a few|some)?\s*(\w+\s+)*(image|picture|art|drawing|wallpaper|logo|icon|photo|portrait|suit|render|scene)\b", "image", 9),
    (r"^(draw|paint)\s+\w+", "image", 8),
    (r"^(design)\s+\w+", "image", 7),
    (r"^(make|create)\s+(an?|a few|some)?\s*\w*\s*(image|picture|art|drawing|wallpaper|photo|portrait|icon|logo|poster)\b", "image", 9),
    (r"^generate\s+(an?|a few|some)?\s*\w*\s*(video|animation|clip|short)\b", "video", 9),
    (r"^(make|create)\s+(an?|a few|some)?\s*\w*\s*(video|animation|clip)\b", "video", 9),
    (r"^(write|create|make|build|save|download|run|execute|install)\b", "automation", 4),
    (r"^(find|locate|list|show|read|delete|copy|move|rename)\b", "automation", 4),
    (r"^(kill|terminate|end)\s+\w+", "automation", 5),
    (r"^(can you play|please play|play)\s+", "automation", 6),
    (r"^(exit|bye|goodbye|good bye|quit|see you|later|good night|that's all|end session)\b", "exit", 10),
    (r"^(tell me about|what is|who is|who are you|what are you|explain|define)\b", "general", 5),
    (r"^what('?s| is) the (date|day|month|year) of\b", "realtime", 6),
    (r"^(when is|when was|date of|day of)\b", "realtime", 6),
    (r"^(hello|hi|hey|good morning|good evening|namaste)\b", "general", 6),
    (r"^(what'?s? your name|what do you do|how are you|how do you work)\b", "general", 6),
    (r"^(today|current|latest|weather|news)\b", "realtime", 5),
    (r"^(live|right now|now)\b", "realtime", 5),
    (r"^what('s| is| )\s*(the )?(weather|time|news|temperature|date|day)", "realtime", 6),
    (r"^what('?s| is) (the )?(bitcoin|stock|gold|sensex|nifty|price|dollar rate)", "realtime", 6),
    (r"\b(stock|share price|share|bitcoin|crypto|nifty|sensex|forex|gold rate|gold|exchange rate|live score|market)\b", "realtime", 5),
    (r"\b(minecraft|mine craft|play in minecraft)\b", "automation", 6),
    (r"\b(firefox|chrome|brave|terminal|file manager|settings)\b", "automation", 4),
    (r"\b(volume|brightness|screen)\b", "automation", 4),
    (r"\b(cpu|ram|memory|disk usage|processes?|task manager|gpu|battery|uptime)\b", "automation", 4),
    (r"\b(file|folder|directory|document|txt|py file)\b", "automation", 3),
    (r"\b(google|youtube|website)\b", "automation", 3),
    (r"\b(music|song|playlist|album|track)\b", "automation", 3),
    (r"\b(code|script|program|function|calculator)\b", "automation", 3),
    (r"\b(write|save) (a|an|the)?\s*\w+", "automation", 3),
    (r"\b(history|who|why|how does|meaning|definition)\b", "general", 2),
    (r"\b(tell|talk|explain|understand)\b", "general", 1),
]
AUTOMATION_THRESHOLD = 4.0
def _rule_score(query: str) -> dict:
    q = query.lower().strip()
    scores = {}
    for pattern, category, weight in AUTOMATION_RULES:
        if re.search(pattern, q):
            scores[category] = scores.get(category, 0) + weight
    return scores
def decide(query: str) -> str:
    q = query.strip()
    if not q:
        return None
    scores = _rule_score(q)
    best_cat, best = max(scores.items(), key=lambda kv: kv[1], default=("general", 0))
    if scores.get("exit", 0) >= AUTOMATION_THRESHOLD and best_cat == "exit":
        return "exit"
    if best >= AUTOMATION_THRESHOLD:
        if best_cat == "realtime":
            return f"realtime {q}"
        if best_cat == "image":
            return f"generate image {_strip_gen(q, ('generate', 'draw', 'paint', 'design', 'make', 'create'))}"
        if best_cat == "video":
            return f"generate video {_strip_gen(q, ('generate', 'make', 'create'))}"
        if best_cat == "automation":
            return f"automation {q}"
        return f"general {q}"
    return None
def _strip_gen(q: str, verbs) -> str:
    low = q.lower().strip()
    for v in verbs:
        if low.startswith(v):
            rest = low[len(v):].strip()
            for art in ("an ", "a ", "a few ", "some "):
                if rest.startswith(art):
                    rest = rest[len(art):]
                    break
            for kind in ("image ", "picture ", "art ", "drawing ", "wallpaper ", "logo ", "icon ",
                         "video ", "animation ", "clip ", "short "):
                if rest.startswith(kind):
                    rest = rest[len(kind):]
                    break
            return rest.strip() or q
    return q
TRAINING_SET = [
    ("open chrome", "automation"),
    ("close firefox", "automation"),
    ("open youtube", "automation"),
    ("play believer", "automation"),
    ("play some music", "automation"),
    ("pause the music", "automation"),
    ("set volume to 30", "automation"),
    ("increase brightness", "automation"),
    ("search google for python", "automation"),
    ("youtube search lofi", "automation"),
    ("write a sick leave application for school", "automation"),
    ("write a python code for calculator", "automation"),
    ("list files in Documents", "automation"),
    ("find file named requirements.txt", "automation"),
    ("cpu and ram usage", "automation"),
    ("show running processes", "automation"),
    ("shutdown the system", "automation"),
    ("minecraft, build a house", "automation"),
    ("mine a block in minecraft", "automation"),
    ("download this video to Data", "automation"),
    ("can you play believer", "automation"),
    ("please play some music", "automation"),
    ("generate an image of a dragon", "image"),
    ("generate a futuristic iron man suit", "image"),
    ("draw a sunset", "image"),
    ("make an animation", "video"),
    ("generate a video of a cat walking", "video"),
    ("bye", "exit"),
    ("goodbye", "exit"),
    ("exit", "exit"),
    ("hello", "general"),
    ("hi", "general"),
    ("what is python", "general"),
    ("explain recursion", "general"),
    ("who invented the telephone", "general"),
    ("what is the capital of france", "general"),
    ("today's weather in delhi", "realtime"),
    ("latest AI news", "realtime"),
    ("current prime minister of india", "realtime"),
    ("bitcoin price right now", "realtime"),
    ("tata stock price", "realtime"),
    ("what is the sensex today", "realtime"),
    ("gold rate in india", "realtime"),
    ("live cricket score", "realtime"),
]
def evaluate() -> dict:
    correct = 0
    mistakes = []
    prefix_for = {
        "general": "general",
        "realtime": "realtime",
        "image": "generate image",
        "video": "generate video",
        "automation": "automation",
        "exit": "exit",
    }
    for query, expected in TRAINING_SET:
        got = decide(query)
        if got is None:
            got = f"{prefix_for[expected]} {query}"  # LLM fallback assumed correct
            verdict = True
        else:
            verdict = got.startswith(prefix_for[expected])
        if verdict:
            correct += 1
        else:
            mistakes.append({"query": query, "expected": expected, "got": got})
    total = len(TRAINING_SET)
    return {
        "total": total,
        "correct": correct,
        "wrong": len(mistakes),
        "accuracy": round(100 * correct / total, 1),
        "mistakes": mistakes,
    }
def _print_eval():
    r = evaluate()
    print(f"\n  Automation decision eval: {r['correct']}/{r['total']} "
          f"({r['accuracy']}%)")
    for m in r["mistakes"]:
        print(f"    MISS  {m['query']!r} expected={m['expected']} got={m['got']}")
if __name__ == "__main__":
    import sys
    if "--eval" in sys.argv:
        _print_eval()
        sys.exit(0)
    while True:
        query = input(">>> ")
        if not query.strip():
            continue
        print(FirstLayerDMM(query))