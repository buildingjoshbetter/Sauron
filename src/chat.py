from typing import List, Dict
import requests


def chat_openrouter(api_key: str, model: str, messages: List[Dict[str, str]], system_override: str | None = None, personality: str | None = None) -> str:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        # Optional but recommended
        "HTTP-Referer": "https://local.pi/",
        "X-Title": "Home AI Assistant",
    }
    # Optionally inject or override system message for safety
    msgs: List[Dict[str, str]] = []
    # keep the most recent non-system messages but replace/insert system
    for m in messages:
        if m.get("role") != "system":
            msgs.append(m)
    system_content_parts: List[str] = []
    if system_override:
        system_content_parts.append(system_override)
    if personality:
        system_content_parts.append(personality)
    if system_content_parts:
        msgs.insert(0, {"role": "system", "content": "\n".join(system_content_parts)})
    else:
        msgs = messages

    payload = {
        "model": model,
        "messages": msgs,
        "temperature": 0.2,
        "max_tokens": 256,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()
