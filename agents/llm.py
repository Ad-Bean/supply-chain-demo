"""LLM client using OpenRouter (OpenAI-compatible API)."""

import time

from openai import OpenAI, RateLimitError

from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OPENROUTER_MODEL

client = OpenAI(
    base_url=OPENROUTER_BASE_URL,
    api_key=OPENROUTER_API_KEY,
)


def chat(messages: list[dict], tools: list[dict] | None = None, max_retries: int = 8):
    """Send a chat completion request with retry on rate limits."""
    kwargs = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 2048,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(**kwargs)
            return response.choices[0].message
        except RateLimitError:
            wait = min(10 * (attempt + 1), 60)  # 10, 20, 30, ... 60s
            print(f"  [rate limited] retrying in {wait}s (attempt {attempt + 1}/{max_retries})...")
            time.sleep(wait)
    raise RuntimeError("LLM rate limit exceeded after retries")
