from dotenv import dotenv_values
import os
import json
import requests
_project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_vars = dotenv_values(os.path.join(_project_dir, "jarvis.env"))
AI_PROVIDER = env_vars.get("AI", "llamacpp").strip().lower()
MODEL_PATH = env_vars.get("MODEL_PATH", "Models/Llama-3.2-1B-Instruct-Q4_K_M.gguf")
CLASSIFIER_MODEL_PATH = env_vars.get("CLASSIFIER_MODEL_PATH", "Models/qwen2.5-0.5b-instruct-q4_k_m.gguf")
N_CTX = int(env_vars.get("N_CTX", "2048"))
N_THREADS = int(env_vars.get("N_THREADS", "2"))
CHAT_MODEL = env_vars.get("ChatModel", "gpt-5.5").strip()
CODE_MODEL = env_vars.get("CodeModel", "sonnet-5").strip()
MODEL_CHAIN = [m.strip() for m in env_vars.get("ModelChain", CHAT_MODEL).split(",") if m.strip()]
KILO_BASE_URL = env_vars.get("KILO_BASE_URL", "https://api.kilo.ai/api/openrouter/chat/completions").strip()
KILO_API_KEY = env_vars.get("KILO_API_KEY", "anonymous").strip()
KILO_MODEL = env_vars.get("KILO_MODEL", CHAT_MODEL).strip()
KILO_CODE_MODEL = env_vars.get("KILO_CODE_MODEL", CODE_MODEL).strip()
KILO_CLIENT_BASE = KILO_BASE_URL.split("/chat/completions")[0].rstrip("/") or "https://api.kilo.ai"
_llm = None
_classifier_llm = None
_kilo_client = None
def get_model():
    global _llm
    if _llm is None:
        from llama_cpp import Llama
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(f"Model not found at '{MODEL_PATH}'.")
        _llm = Llama(model_path=MODEL_PATH, n_ctx=N_CTX, n_threads=N_THREADS, verbose=False)
    return _llm
def get_classifier_model():
    global _classifier_llm
    if _classifier_llm is None:
        from llama_cpp import Llama
        if not os.path.exists(CLASSIFIER_MODEL_PATH):
            raise FileNotFoundError(f"Classifier model not found at '{CLASSIFIER_MODEL_PATH}'.")
        _classifier_llm = Llama(model_path=CLASSIFIER_MODEL_PATH, n_ctx=N_CTX, n_threads=N_THREADS, verbose=False)
    return _classifier_llm
def _g4fspace_request(messages, max_tokens, temperature, stream, stop, model=None, models=None):
    models_to_try = models or [model or CHAT_MODEL]
    last_error = None
    for m in models_to_try:
        try:
            payload = {
                "model": m,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": stream,
            }
            if stop:
                payload["stop"] = stop
            headers = {
                "User-Agent": "opencode-kilo-provider",
                "Content-Type": "application/json",
            }
            if KILO_API_KEY and KILO_API_KEY.strip().lower() not in ("anonymous", "none", "", "null"):
                headers["Authorization"] = f"Bearer {KILO_API_KEY}"
            resp = requests.post(
                KILO_BASE_URL,
                json=payload, stream=stream, timeout=180,
                headers=headers,
            )
            if resp.status_code in (502, 503, 429, 402):
                last_error = f"HTTP {resp.status_code} (transient)"
                print(f"    model '{m}' failed: {last_error}, retrying...")
                import time
                time.sleep(2)
                continue
            resp.raise_for_status()
            if stream:
                def generate():
                    for line in resp.iter_lines():
                        if line:
                            line = line.decode("utf-8").strip()
                            if line.startswith("data: "):
                                data = line[6:]
                                if data == "[DONE]":
                                    break
                                parsed = json.loads(data)
                                if parsed.get("choices"):
                                    chunk = parsed["choices"][0]
                                    if "delta" in chunk:
                                        chunk["message"] = {"role": "assistant",
                                                            "content": (chunk.get("delta") or {}).get("content") or ""}
                                    yield parsed
                return generate()
            data = resp.json()
            if data.get("choices") and data["choices"][0].get("message", {}).get("content"):
                return data
            last_error = "empty or null content"
        except requests.RequestException as e:
            last_error = str(e)
        print(f"    model '{m}' failed: {last_error[:80]}")
    raise RuntimeError(f"All models failed. Last error: {last_error}")
def _llamacpp_completion(messages, max_tokens, temperature, stream, stop, top_p, classifier=False):
    try:
        llm = get_classifier_model() if classifier else get_model()
        return llm.create_chat_completion(
            messages=messages, max_tokens=max_tokens, temperature=temperature,
            top_p=top_p, stop=stop, stream=stream
        )
    except FileNotFoundError as e:
        return {
            "choices": [{"message": {"role": "assistant",
                                     "content": "Sorry, I'm having trouble reaching the AI service right now."}}]
        }
def _g4fspace_with_fallback(messages, max_tokens, temperature, stream, stop, model, top_p=1, classifier=False):
    import time
    for attempt in range(3):
        try:
            return _g4fspace_request(messages, max_tokens, temperature, stream, stop, models=MODEL_CHAIN)
        except (RuntimeError, requests.RequestException):
            if attempt < 2:
                print(f"    retrying ({attempt + 1}/3)...")
                time.sleep(3)
            else:
                print("    all cloud models failed, falling back to local llamacpp")
                return _llamacpp_completion(messages, max_tokens, temperature, stream, stop, top_p, classifier)
def chat_completion(messages, max_tokens=256, temperature=0.7, top_p=1, stop=None, model=None):
    if AI_PROVIDER == "llamacpp":
        return _llamacpp_completion(messages, max_tokens, temperature, stream=False, stop=stop, top_p=top_p)
    return _g4fspace_with_fallback(messages, max_tokens, temperature, stream=False, stop=stop, model=model, top_p=top_p)
def chat_completion_openai(messages, max_tokens=256, temperature=0.7, model=None):
    if AI_PROVIDER == "llamacpp":
        return _llamacpp_completion(messages, max_tokens, temperature, stream=False, stop=None, top_p=1)
    return _g4fspace_with_fallback(messages, max_tokens, temperature, stream=False, stop=None, model=model, top_p=1)
def chat_completion_stream(messages, max_tokens=256, temperature=0.7, top_p=1, stop=None, model=None):
    if AI_PROVIDER == "llamacpp":
        return _llamacpp_completion(messages, max_tokens, temperature, stream=True, stop=stop, top_p=top_p)
    return _g4fspace_with_fallback(messages, max_tokens, temperature, stream=True, stop=stop, model=model, top_p=top_p)
def chat_completion_coding(messages, max_tokens=4096, temperature=0.3, model=None):
    if AI_PROVIDER == "llamacpp":
        return _llamacpp_completion(messages, max_tokens, temperature, stream=False, stop=None, top_p=1)
    return _g4fspace_with_fallback(messages, max_tokens, temperature, stream=False, stop=None, model=model or CODE_MODEL, top_p=1)
def chat_completion_classifier(messages, max_tokens=200, temperature=0.7, top_p=1, stop=None, model=None):
    if AI_PROVIDER == "llamacpp":
        return _llamacpp_completion(messages, max_tokens, temperature, stream=False, stop=stop, top_p=top_p, classifier=True)
    return _g4fspace_with_fallback(messages, max_tokens, temperature, stream=False, stop=stop, model=model, top_p=top_p, classifier=True)
def get_openai_client():
    global _kilo_client
    if _kilo_client is None:
        from openai import OpenAI
        _kilo_client = OpenAI(
            base_url=KILO_CLIENT_BASE,
            api_key=KILO_API_KEY or "anonymous",
        )
    return _kilo_client
def get_chat_model(model=None):
    return model or KILO_MODEL
def get_code_model(model=None):
    return model or KILO_CODE_MODEL
