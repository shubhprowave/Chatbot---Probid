"""Groq (OpenAI-compatible) client helper.

Centralizes chat-completion calls (streaming + non-streaming).
Provider is swappable by changing base URL + key in .env.
"""
import httpx
import json
from config import settings


def _headers() -> dict:
    if not settings.LLM_API_KEY:
        raise RuntimeError(
            "LLM_API_KEY (Groq key) is missing. Add it to the .env file: "
            "LLM_API_KEY=gsk_..."
        )
    return {
        "Authorization": f"Bearer {settings.LLM_API_KEY}",
        "Content-Type": "application/json",
    }


def _url() -> str:
    return f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions"


async def chat_completion(
    messages: list[dict],
    model: str,
    temperature: float = 0.2,
    max_tokens: int = 320,
    json_mode: bool = False,
) -> str:
    """Non-streaming chat completion. Returns assistant text."""
    timeout = httpx.Timeout(connect=15.0, read=120.0, write=30.0, pool=15.0)
    body: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    async with httpx.AsyncClient(timeout=timeout) as c:
        r = await c.post(_url(), headers=_headers(), json=body)
        r.raise_for_status()
        data = r.json()
    return (data.get("choices") or [{}])[0].get("message", {}).get("content", "")


async def stream_chat_completions(
    messages: list[dict],
    model: str,
    temperature: float = 0.2,
    max_tokens: int = 320,
):
    """Stream a chat completion, yielding content tokens as they arrive."""
    timeout = httpx.Timeout(connect=15.0, read=600.0, write=30.0, pool=15.0)
    body: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    async with httpx.AsyncClient(timeout=timeout) as c:
        async with c.stream("POST", _url(), headers=_headers(), json=body) as r:
            if r.status_code != 200:
                body_text = (await r.aread()).decode("utf-8", "replace")
                raise RuntimeError(
                    f"LLM {r.status_code}: {body_text[:500]}"
                )
            buffer = b""
            async for chunk in r.aiter_bytes():
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    line = line.strip()
                    if not line or not line.startswith(b"data:"):
                        continue
                    payload = line[5:].strip()
                    if payload in (b"[DONE]",):
                        return
                    try:
                        data = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    choices = data.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    if tok := delta.get("content"):
                        yield tok