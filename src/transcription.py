from pathlib import Path
import time
import random
import requests


def transcribe_with_openai(api_key: str, wav_path: Path) -> str:
    url = "https://api.openai.com/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {api_key}"}
    max_retries = 6
    backoff_base = 2.0

    for attempt in range(max_retries):
        with open(wav_path, "rb") as f:
            files = {
                "file": (wav_path.name, f, "audio/wav"),
            }
            data = {
                "model": "whisper-1",
                "response_format": "text",
                "temperature": 0,
            }
            resp = requests.post(url, headers=headers, files=files, data=data, timeout=180)
        if resp.status_code == 200:
            return resp.text.strip()
        if resp.status_code == 429:
            # Exponential backoff with jitter
            sleep_s = (backoff_base ** attempt) + random.uniform(0, 1.0)
            time.sleep(min(sleep_s, 60))
            continue
        resp.raise_for_status()

    # Last attempt: raise informative error
    resp.raise_for_status()
    return ""  # unreachable, for type completeness
