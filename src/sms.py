from twilio.rest import Client
import re


def sanitize_sms(body: str, max_chars: int, allow_urls: bool, blocklist_patterns: list[str]) -> str:
    text = body.strip()
    # Remove URLs unless allowed
    if not allow_urls:
        text = re.sub(r"https?://\S+", "", text)
    # Apply blocklist patterns
    for pat in blocklist_patterns:
        try:
            text = re.sub(pat, "[redacted]", text, flags=re.IGNORECASE)
        except re.error:
            # skip invalid regex
            continue
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Enforce max length
    if len(text) > max_chars:
        text = text[: max_chars - 1] + "…"
    return text


def send_sms(account_sid: str, auth_token: str, from_number: str, to_number: str, body: str) -> None:
    client = Client(account_sid, auth_token)
    client.messages.create(from_=from_number, to=to_number, body=body)
