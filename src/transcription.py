from pathlib import Path
import time
import random
import requests
import subprocess
import logging


def transcribe_local_whisper(wav_path: Path, model_size: str = "medium") -> str:
    """
    Transcribe audio using local Whisper (faster-whisper library).
    Speed: 2-3 seconds for 10-second audio on Pi 5.
    """
    try:
        from faster_whisper import WhisperModel
        
        # Load model (cached after first use)
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        
        # Transcribe
        segments, info = model.transcribe(str(wav_path), beam_size=3, language="en")
        text = " ".join([segment.text for segment in segments])
        
        logging.info(f"transcribed with {model_size} model (lang={info.language}, prob={info.language_probability:.2f})")
        return text.strip()
        
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


def transcribe_nas_whisper(wav_path: Path, nas_url: str) -> tuple[str, bool]:
    """
    Transcribe audio using Whisper service running on NAS.
    Much faster than Pi (NAS has better CPU).
    Returns (text, success) tuple.
    """
    try:
        with open(wav_path, "rb") as f:
            files = {"file": (wav_path.name, f, "audio/wav")}
            resp = requests.post(f"{nas_url}/transcribe", files=files, timeout=60)
        
        if resp.status_code == 200:
            data = resp.json()
            text = data.get("text", "").strip()
            return (text, True)  # Success, even if empty
        else:
            logging.warning("NAS whisper failed: %s", resp.text)
            return ("", False)
    except Exception as e:
        logging.error("NAS whisper error: %s", e)
        return ("", False)


def transcribe(api_key: str, wav_path: Path, use_local: bool, model_size: str = "medium", nas_whisper_url: str = "") -> str:
    """
    Smart transcription priority:
    1. Local Whisper (if enabled and on Pi 5)
    2. NAS Whisper (if URL configured)
    3. OpenAI API (fallback)
    """
    # Try local Whisper first (best for Pi 5)
    if use_local:
        text = transcribe_local_whisper(wav_path, model_size)
        if text or text == "":  # Return even if empty (valid transcription)
            return text
        logging.warning("local whisper failed, trying next option")
    
    # Try NAS Whisper
    if nas_whisper_url:
        text, success = transcribe_nas_whisper(wav_path, nas_whisper_url)
        if success:
            return text  # Return even if empty (valid transcription)
        logging.warning("NAS whisper failed, falling back to OpenAI API")
    
    # Fallback to OpenAI API
    return transcribe_with_openai(api_key, wav_path)
