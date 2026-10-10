"""
Archie AI Core
==============
Shared configuration, LLM routing, and chat-pipeline logic used by
every profile (Telegram, Discord, CLI, GUI). This is the same logic
that used to live directly in core.py — pulled out so all four
interfaces behave identically and share one history/mode/ban state.

install.sh fills in the values below from arxh.conf.
archie_agent.py can also override them at runtime via configure(),
which is what makes Windows work without sed.
"""

import os
import time
import json
import re

from groq import Groq
import ollama

import agent_tools
from agent_tools import search_internet  # noqa: F401  (kept for backwards compat)

# ==========================================
#           Provider Flags
# ==========================================
LOCAL = True
API = False
OPENROUTER = False

# ==========================================
#            Configurations
# ==========================================
GROQ_KEY = ""

ADMIN_ID = []
BANNED = []
MAT = []
GROUP_ID = 0
EMOJI_ENABLED = False

# Groq config
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# OpenRouter config (OpenAI-compatible API: one key, many models)
OPENROUTER_KEY = ""
OPENROUTER_MODEL = "openrouter/auto"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Local config
OLLAMA_MODEL = "smollm2:360m"

# Instructions
BASE_INSTRUCTION = "You are a helpful, neutral assistant. Answer concisely and clearly."
ADMIN_INSTRUCTION = "You are in ADMINISTRATOR mode. Speak seriously and directly."

MAX_TOOL_STEPS = 6


def _make_client():
    return Groq(api_key=GROQ_KEY or os.environ.get("GROQ_API_KEY") or "")


_or_client = None


def _make_or_client():
    from openai import OpenAI
    key = OPENROUTER_KEY or os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OpenRouter key missing: set OPENROUTER_KEY or the OPENROUTER_API_KEY env var.")
    return OpenAI(base_url=OPENROUTER_BASE_URL, api_key=key, default_headers={"X-Title": "Archie"})


def _get_or_client():
    global _or_client
    if _or_client is None:
        _or_client = _make_or_client()
    return _or_client


def _check_providers():
    if not (LOCAL or API or OPENROUTER):
        raise RuntimeError(
            "\033[91m[KERNEL PANIC]\033[0m No AI provider enabled. "
            "Set LOCAL=True or API=True in ai_core.py."
        )


_check_providers()

client = _make_client()
START_TIME = time.time()

is_crashed = False
crash_time = 0
modes = {}      # uid -> "admin" | "normal"
history = {}    # uid -> [ {role, content}, ... ]

_CONFIGURABLE = {
    "LOCAL", "API", "OPENROUTER", "GROQ_KEY", "GROQ_MODEL", "OLLAMA_MODEL",
    "OPENROUTER_KEY", "OPENROUTER_MODEL", "ADMIN_ID", "BANNED",
    "MAT", "GROUP_ID", "EMOJI_ENABLED", "BASE_INSTRUCTION", "ADMIN_INSTRUCTION",
}


def configure(**overrides):
    """Override config values at runtime (used by archie_agent.py). None = leave alone."""
    global client, _or_client
    g = globals()
    for key, value in overrides.items():
        if key not in _CONFIGURABLE:
            raise KeyError(f"Not a configurable setting: {key}")
        if value is not None:
            g[key] = value
    _check_providers()
    client = _make_client()
    _or_client = None


# ==========================================
#           Search Tool(s)
# ==========================================
def search_tool_schema():
    """Kept for backwards compat. The real schemas now come from agent_tools."""
    return [t for t in agent_tools.tool_schemas() if t["function"]["name"] == "search_internet"]


# ==========================================
#           Provider Router
# ==========================================
def _get(obj, key, default=None):
    """Read a field from either a dict (old ollama) or a model object (new ollama)."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _to_ollama(messages):
    """History is kept in OpenAI format; Ollama wants dict arguments and tool_name."""
    out = []
    for m in messages:
        m = dict(m)
        if m.get("content") is None:
            m["content"] = ""
        if m.get("tool_calls"):
            calls = []
            for c in m["tool_calls"]:
                args = c["function"]["arguments"]
                if isinstance(args, str):
                    try:
                        args = json.loads(args or "{}")
                    except Exception:
                        args = {}
                calls.append({"function": {"name": c["function"]["name"], "arguments": args}})
            m["tool_calls"] = calls
        if m.get("role") == "tool":
            m["tool_name"] = m.pop("name", None)
            m.pop("tool_call_id", None)
        out.append(m)
    return out


def _calls_from_ollama(msg):
    out = []
    for i, c in enumerate(_get(msg, "tool_calls") or []):
        fn = _get(c, "function")
        args = _get(fn, "arguments") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                args = {}
        out.append({
            "id": f"call_{i}",
            "type": "function",
            "function": {"name": _get(fn, "name"), "arguments": json.dumps(args, ensure_ascii=False)},
        })
    return out


def provider_label():
    """Human-readable provider chain, in fallback order."""
    names = []
    if LOCAL:
        names.append("Local (Ollama)")
    if API:
        names.append("Groq API")
    if OPENROUTER:
        names.append("OpenRouter")
    return " -> ".join(names) or "none"


def primary_model():
    if LOCAL:
        return OLLAMA_MODEL
    if API:
        return GROQ_MODEL
    return OPENROUTER_MODEL


def _ask_ollama(full_messages, tools):
    kwargs = {
        "model": OLLAMA_MODEL,
        "messages": _to_ollama(full_messages),
        "options": {"temperature": 0.8, "top_p": 0.9, "repeat_penalty": 1.15},
    }
    if tools:
        kwargs["tools"] = tools
    try:
        response = ollama.chat(**kwargs)
    except Exception as e:
        if tools and "tool" in str(e).lower():
            print(f"\033[93m[WARN]\033[0m {OLLAMA_MODEL} doesn't support tools — answering without them.")
            kwargs.pop("tools")
            response = ollama.chat(**kwargs)
        else:
            raise
    msg = _get(response, "message")
    return _get(msg, "content") or "", _calls_from_ollama(msg)


def _ask_openai_compat(c, model, full_messages, tools):
    """Groq and OpenRouter both speak the OpenAI chat-completions format."""
    kwargs = {"model": model, "messages": full_messages}
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    try:
        response = c.chat.completions.create(**kwargs)
    except Exception as e:
        if tools and "tool" in str(e).lower():
            print(f"\033[93m[WARN]\033[0m {model} doesn't support tools — answering without them.")
            kwargs.pop("tools")
            kwargs.pop("tool_choice")
            response = c.chat.completions.create(**kwargs)
        else:
            raise
    msg = response.choices[0].message
    calls = [
        {"id": t.id, "type": "function",
         "function": {"name": t.function.name, "arguments": t.function.arguments or "{}"}}
        for t in (msg.tool_calls or [])
    ]
    return msg.content, calls


def ask_llm(messages, system_prompt, tools=None):
    """Send a chat request through the enabled providers, in order:
    Ollama -> Groq -> OpenRouter. If one fails, the next one is tried.
    Returns (text, tool_calls) with tool_calls in OpenAI format."""
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    attempts = []
    if LOCAL:
        attempts.append(("LOCAL", lambda: _ask_ollama(full_messages, tools)))
    if API:
        attempts.append(("API", lambda: _ask_openai_compat(client, GROQ_MODEL, full_messages, tools)))
    if OPENROUTER:
        attempts.append(("OPENROUTER", lambda: _ask_openai_compat(_get_or_client(), OPENROUTER_MODEL, full_messages, tools)))
    if not attempts:
        raise RuntimeError("[KERNEL PANIC] No provider available.")

    for i, (name, fn) in enumerate(attempts):
        try:
            return fn()
        except Exception as e:
            print(f"\033[91m[{name} ERROR]\033[0m {e}")
            if i == len(attempts) - 1:
                raise


def strip_emoji(text):
    """Remove all emoji from text if EMOJI_ENABLED is False."""
    if EMOJI_ENABLED:
        return text
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub(r"", text)


# ==========================================
#           Shared chat pipeline
# ==========================================
def instruction_for(uid, is_admin):
    """Pick base vs admin instruction based on per-user mode state."""
    mode = modes.get(uid, "normal")
    return ADMIN_INSTRUCTION if (is_admin and mode == "admin") else BASE_INSTRUCTION


def run_with_tools(uid, text, instr):
    """
    Shared pipeline: appends to history, calls ask_llm, runs whatever tools
    the user allowed (see agent_tools.PERMS), loops until the model gives a
    final answer, and returns it. Tool traffic stays in a scratch list; only
    the final user/assistant text is stored in history.
    """
    if uid not in history:
        history[uid] = []

    history[uid].append({"role": "user", "content": text})
    history[uid] = history[uid][-10:]
    while history[uid] and history[uid][0]["role"] != "user":
        history[uid].pop(0)

    tools = agent_tools.tool_schemas() or None
    work = list(history[uid])

    ans, calls = ask_llm(work, instr, tools=tools)
    steps = 0
    while calls and steps < MAX_TOOL_STEPS:
        steps += 1
        work.append({"role": "assistant", "content": ans or None, "tool_calls": calls})
        for c in calls:
            name = c["function"]["name"]
            try:
                args = json.loads(c["function"]["arguments"] or "{}")
            except Exception:
                args = {}
            result = agent_tools.run_tool(name, args)
            work.append({"role": "tool", "tool_call_id": c["id"], "name": name, "content": result})
        ans, calls = ask_llm(work, instr, tools=tools)

    if calls and not ans:
        ans = "[Stopped: too many tool steps in a row]"

    if ans:
        history[uid].append({"role": "assistant", "content": ans})

    return ans
