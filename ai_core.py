"""
Archie AI Core
==============
Shared configuration, LLM routing, and chat-pipeline logic used by
every profile (Telegram, Discord, CLI, GUI). This is the same logic
that used to live directly in core.py — pulled out so all four
interfaces behave identically and share one history/mode/ban state.

install.sh fills in the values below from arxh.conf.
"""

import time
import json
import re

from groq import Groq
from googlesearch import search
import ollama

# ==========================================
#           Provider Flags
# ==========================================
LOCAL = True
API = False

# Safety check — if both are off, panic
if not LOCAL and not API:
    raise RuntimeError(
        "\033[91m[KERNEL PANIC]\033[0m No AI provider enabled. "
        "Set LOCAL=True or API=True in ai_core.py."
    )

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

# Local config
OLLAMA_MODEL = "gemma4:e4b"

client = Groq(api_key=GROQ_KEY)
START_TIME = time.time()

is_crashed = False
crash_time = 0
modes = {}      # uid -> "admin" | "normal"
history = {}    # uid -> [ {role, content}, ... ]

# Instructions
BASE_INSTRUCTION = "Ты полезный, нейтральный ассистент. Отвечай кратко и понятно."
ADMIN_INSTRUCTION = "Ты в режиме АДМИНИСТРАТОРА. Говори серьёзно и прямо."


# ==========================================
#           Search Tool(s)
# ==========================================
def search_internet(query):
    print(f"\033[94m[GOOGLE SEARCH]\033[0m {query}")
    try:
        results = search(query, num_results=3, lang="ru")
        res_list = [str(r) for r in results]
        return "Files from internet:\n" + "\n".join(res_list) if res_list else "I dont find any information."
    except Exception as e:
        return f"Search error: {e}"


def search_tool_schema():
    """OpenAI/Groq-style tool schema for search_internet."""
    return [{
        "type": "function",
        "function": {
            "name": "search_internet",
            "description": "Search in Google",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"]
            }
        }
    }]


# ==========================================
#           Provider Router
# ==========================================
def ask_llm(messages, system_prompt, tools=None):
    """Send a chat request to either Ollama or Groq."""
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    # --- Local Ollama ---
    if LOCAL:
        try:
            response = ollama.chat(
                model=OLLAMA_MODEL,
                messages=full_messages,
                options={
                    "temperature": 0.8,
                    "top_p": 0.9,
                    "repeat_penalty": 1.15,
                }
            )
            return response['message']['content'], None
        except Exception as e:
            print(f"\033[91m[LOCAL ERROR]\033[0m {e}")
            if not API:
                raise

    # --- Groq API ---
    if API:
        try:
            kwargs = {
                "model": GROQ_MODEL,
                "messages": full_messages,
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            response = client.chat.completions.create(**kwargs)
            msg = response.choices[0].message
            return msg.content, msg.tool_calls
        except Exception as e:
            print(f"\033[91m[API ERROR]\033[0m {e}")
            raise

    raise RuntimeError("[KERNEL PANIC] No provider available.")


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
    Shared pipeline: appends to history, calls ask_llm, handles Groq
    tool calls (search_internet), and returns the final answer text.
    Every profile (Telegram/Discord/CLI/GUI) calls this so behavior
    stays identical across interfaces.
    """
    if uid not in history:
        history[uid] = []

    history[uid].append({"role": "user", "content": text})
    history[uid] = history[uid][-10:]

    tools = search_tool_schema()
    ans, tool_calls = ask_llm(history[uid], instr, tools=tools if API else None)

    if tool_calls:
        history[uid].append({
            "role": "assistant",
            "content": None,
            "tool_calls": tool_calls
        })

        for tool in tool_calls:
            try:
                args = json.loads(tool.function.arguments)
                query = args.get("query")
                res = search_internet(query)
            except Exception:
                res = "Error with request passing"

            history[uid].append({
                "role": "tool",
                "tool_call_id": tool.id,
                "name": "search_internet",
                "content": res
            })

        final = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "system", "content": instr}] + history[uid]
        )
        ans = final.choices[0].message.content

    if ans:
        history[uid].append({"role": "assistant", "content": ans})

    return ans
