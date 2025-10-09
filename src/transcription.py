from pathlib import Path
import time
import random
import requests
import subprocess
import logging


def transcribe_local_whisper(wav_path: Path, model_size: str = "tiny") -> str:
    """
    Transcribe audio using local Whisper (faster-whisper).
    Speed: 0.5-2 seconds for 10-second audio (vs 2-5 sec for API).
    """
    try:
        # Use faster-whisper CLI
        cmd = [
            "whisper",
            str(wav_path),
            "--model", model_size,
            "--output_format", "txt",
            "--output_dir", "/tmp",
            "--language", "en",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            # Read output file
            output_file = Path(f"/tmp/{wav_path.stem}.txt")
            if output_file.exists():
                text = output_file.read_text().strip()
                output_file.unlink()  # Cleanup
                return text
        
        logging.warning("local whisper failed, output: %s", result.stderr)
        return ""
    except Exception as e:
        logging.error("local whisper error: %s", e)
        return ""


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


def transcribe(api_key: str, wav_path: Path, use_local: bool, model_size: str = "tiny") -> str:
    """
    Smart transcription: use local Whisper if enabled, fallback to OpenAI API.
    """
    if use_local:
        text = transcribe_local_whisper(wav_path, model_size)
        if text:
            return text
        # Fallback to API if local fails
        logging.warning("local whisper failed, falling back to OpenAI API")
    
    return transcribe_with_openai(api_key, wav_path)
