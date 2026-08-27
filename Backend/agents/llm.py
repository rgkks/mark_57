"""Common LLM configuration for all agent adapters.

Keeps the model/provider layer independent from any agent framework.
All adapters talk to the same Kilo.ai / OpenRouter-compatible gateway.
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from Backend.PollinationsModel import (
    KILO_CLIENT_BASE,        # https://api.kilo.ai/api/openrouter  (SDK appends /chat/completions)
    KILO_BASE_URL,           # https://api.kilo.ai/api/openrouter/chat/completions
    KILO_API_KEY,
    KILO_MODEL,
    KILO_CODE_MODEL,
    get_openai_client,
    get_chat_model,
    get_code_model,
)

# Root base URL (without /chat/completions) for litellm-based frameworks.
LITELLM_BASE = KILO_BASE_URL.split("/chat/completions")[0].rstrip("/") or KILO_CLIENT_BASE
# Base URL including path for raw OpenAI SDK usage.
OPENAI_BASE = KILO_CLIENT_BASE

# Dummy key accepted by kilo.ai (gateway ignores auth when key empty/anonymous).
DUMMY_KEY = KILO_API_KEY or "anonymous"


def chat_model() -> str:
    return get_chat_model()


def code_model() -> str:
    return get_code_model()


def litellm_model_id(kind: str = "chat") -> str:
    """Return a litellm-routable model id (openrouter/<model>) for kilo.ai."""
    base = KILO_MODEL if kind == "chat" else (KILO_CODE_MODEL or KILO_MODEL)
    if base.startswith("openrouter/"):
        return base
    return f"openrouter/{base}"


def smolagents_model() -> dict:
    """Return kwargs to build a smolagents LiteLLMModel against kilo.ai."""
    from smolagents import LiteLLMModel
    return LiteLLMModel(
        model_id=litellm_model_id("code"),
        api_base=LITELLM_BASE,
        api_key=DUMMY_KEY,
    )


def crewai_llm() -> object:
    """Return a crewai LLM object configured for kilo.ai."""
    from crewai import LLM
    return LLM(
        model=litellm_model_id("chat"),
        base_url=LITELLM_BASE,
        api_key=DUMMY_KEY,
    )


def openai_client():
    """Return the shared OpenAI-compatible client pointed at kilo.ai."""
    return get_openai_client()


def chat(messages, max_tokens: int = 256, temperature: float = 0.0, model: str = None) -> str:
    """One-shot helper: send chat messages to kilo.ai, return text."""
    client = openai_client()
    resp = client.chat.completions.create(
        model=model or chat_model(),
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return resp.choices[0].message.content or ""


# ============================================================
# Model routing: cheap/fast for routing, strong for reasoning.
# ============================================================

# Classify the effort tier a task needs.
_LIGHT_KEYWORDS = (
    "open", "close", "play", "volume", "brightness", "list", "cpu", "ram",
    "disk", "search", "clock", "time", "date", "launch",
)


def choose_model(kind: str) -> str:
    """kind: 'fast' (routing/classification) or 'strong' (reasoning/coding)."""
    if kind == "fast":
        return code_model()  # cheaper/faster pool used for routing decisions
    return chat_model()


def fast_model() -> str:
    return choose_model("fast")


def strong_model() -> str:
    return choose_model("strong")


def task_effort(task: str) -> str:
    """Heuristic: classify a task as 'fast' or 'strong' based on keywords."""
    low = task.lower()
    if any(k in low for k in _LIGHT_KEYWORDS):
        return "fast"
    return "strong"
