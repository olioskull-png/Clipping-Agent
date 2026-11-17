import json
import urllib.request
from app import config


def _anthropic_chat(messages: list[dict], temperature: float, timeout: float) -> str:
    base = (config.effective_base_url() or "https://api.anthropic.com/v1").rstrip("/")
    url = f"{base}/messages" if not base.endswith("/messages") else base

    system_parts = [m["content"] for m in messages if m.get("role") == "system"]
    user_messages = [
        {"role": m["role"], "content": m["content"]}
        for m in messages
        if m.get("role") != "system"
    ]

    payload: dict = {
        "model": config.LLM_MODEL,
        "max_tokens": 4096,
        "temperature": temperature,
        "messages": user_messages,
    }
    if system_parts:
        payload["system"] = "\n\n".join(system_parts)

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-api-key": config.LLM_API_KEY,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    blocks = data.get("content") or []
    texts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
    return "\n".join(texts).strip()


def chat_completion(
    messages: list[dict],
    temperature: float = 0.3,
    timeout: float = 30.0,
) -> str:
    if config.effective_provider() == "anthropic":
        return _anthropic_chat(messages, temperature=temperature, timeout=timeout)

    from openai import OpenAI

    client = OpenAI(
        api_key=config.LLM_API_KEY or "local",
        base_url=config.effective_base_url() or None,
        timeout=timeout,
    )
    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        temperature=temperature,
        messages=messages,
    )
    return (response.choices[0].message.content or "").strip()
