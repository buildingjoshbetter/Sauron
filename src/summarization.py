"""
Daily summarization system for audio transcripts, images, and video.
Keeps raw files for current day only, then summarizes and archives as text.
"""
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict
import requests


def summarize_with_llm(api_key: str, model: str, content: str, content_type: str) -> str:
    """
    Use LLM to summarize content (transcripts, image descriptions, etc).
    """
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    prompt = f"""Summarize the following {content_type} from Josh's day. 
Extract key activities, topics discussed, patterns, and notable events.
Be concise but preserve important details.

{content_type.capitalize()}:
{content}

Summary:"""
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a summarization assistant. Be concise and preserve key details."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 500,
    }
    
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logging.error("summarization failed: %s", e)
        return f"[Summarization failed: {str(e)}]"


def summarize_daily_transcripts(
    data_dir: Path,
    openrouter_key: str,
    openrouter_model: str,
    memory_system
) -> None:
    """
    Summarize all transcripts from yesterday and store summary.
    Delete old audio files after summarization.
    """
    # Summaries stored on NAS via memory_system.memory_dir
    summaries_dir = memory_system.memory_dir / "daily_summaries"
    summaries_dir.mkdir(exist_ok=True)
    
    audio_dir = data_dir / "audio"
    
    # Get yesterday's date
    yesterday = datetime.now() - timedelta(days=1)
    date_key = yesterday.strftime("%Y-%m-%d")
    
    # Check if already summarized
    summary_file = summaries_dir / f"transcripts_{date_key}.json"
    if summary_file.exists():
        logging.info("transcripts for %s already summarized", date_key)
        return
    
    # Collect all user messages from yesterday
    yesterday_transcripts = []
    for msg in memory_system.conversation:
        if msg.get("role") != "user":
            continue
        timestamp_str = msg.get("timestamp", "")
        if not timestamp_str:
            continue
        try:
            msg_date = datetime.fromisoformat(timestamp_str).date()
            if msg_date == yesterday.date():
                yesterday_transcripts.append({
                    "timestamp": timestamp_str,
                    "content": msg.get("content", "")
                })
        except Exception:
            continue
    
    if not yesterday_transcripts:
        logging.info("no transcripts found for %s", date_key)
        return
    
    # Build content for summarization
    transcript_text = "\n".join([
        f"[{t['timestamp']}] {t['content']}" for t in yesterday_transcripts
    ])
    
    # Summarize
    logging.info("summarizing %d transcripts from %s", len(yesterday_transcripts), date_key)
    summary = summarize_with_llm(
        openrouter_key,
        openrouter_model,
        transcript_text,
        "audio transcripts"
    )
    
    # Store summary
    summary_data = {
        "date": date_key,
        "transcript_count": len(yesterday_transcripts),
        "summary": summary,
        "raw_transcripts": yesterday_transcripts  # Keep for reference
    }
    
    with open(summary_file, "w") as f:
        json.dump(summary_data, f, indent=2)
    
    logging.info("saved transcript summary for %s: %s", date_key, summary_file)


def archive_daily_audio(data_dir: Path, nas_archive_dir: Path) -> None:
    """
    Move yesterday's audio files to NAS archive (keep forever).
    """
    audio_dir = data_dir / "audio"
    archive_dir = nas_archive_dir / "audio_archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    # Create daily archive subdirectory
    yesterday = datetime.now() - timedelta(days=1)
    date_key = yesterday.strftime("%Y-%m-%d")
    daily_archive = archive_dir / date_key
    daily_archive.mkdir(exist_ok=True)
    
    if not audio_dir.exists():
        return
    
    # Move files from yesterday to NAS
    cutoff_time = datetime.now() - timedelta(hours=24)
    archived_count = 0
    
    for audio_file in audio_dir.glob("audio_*.wav"):
        try:
            file_mtime = datetime.fromtimestamp(audio_file.stat().st_mtime)
            if file_mtime < cutoff_time:
                # Move to NAS archive
                dest = daily_archive / audio_file.name
                audio_file.rename(dest)
                archived_count += 1
        except Exception as e:
            logging.warning("failed to archive %s: %s", audio_file, e)
    
    if archived_count > 0:
        logging.info("archived %d audio files to NAS: %s", archived_count, daily_archive)


def summarize_daily_images(
    data_dir: Path,
    openrouter_key: str,
    openrouter_model: str,
    memory_system
) -> None:
    """
    Summarize image descriptions from yesterday.
    Delete old images after summarization.
    """
    # Summaries stored on NAS via memory_system.memory_dir
    summaries_dir = memory_system.memory_dir / "daily_summaries"
    summaries_dir.mkdir(exist_ok=True)
    
    images_dir = data_dir / "images"
    descriptions_file = data_dir / "image_descriptions.json"
    
    # Get yesterday's date
    yesterday = datetime.now() - timedelta(days=1)
    date_key = yesterday.strftime("%Y-%m-%d")
    
    # Check if already summarized
    summary_file = summaries_dir / f"images_{date_key}.json"
    if summary_file.exists():
        logging.info("images for %s already summarized", date_key)
        return
    
    # Load image descriptions
    if not descriptions_file.exists():
        logging.info("no image descriptions found")
        return
    
    try:
        with open(descriptions_file, "r") as f:
            all_descriptions = json.load(f)
    except Exception as e:
        logging.error("failed to load image descriptions: %s", e)
        return
    
    # Filter for yesterday
    yesterday_descriptions = [
        desc for desc in all_descriptions
        if desc.get("date", "").startswith(date_key)
    ]
    
    if not yesterday_descriptions:
        logging.info("no image descriptions for %s", date_key)
        return
    
    # Build content for summarization
    desc_text = "\n".join([
        f"[{d.get('timestamp', '')}] Motion detected: {d.get('description', '')}"
        for d in yesterday_descriptions
    ])
    
    # Summarize
    logging.info("summarizing %d image descriptions from %s", len(yesterday_descriptions), date_key)
    summary = summarize_with_llm(
        openrouter_key,
        openrouter_model,
        desc_text,
        "motion detection events"
    )
    
    # Store summary
    summary_data = {
        "date": date_key,
        "image_count": len(yesterday_descriptions),
        "summary": summary,
        "descriptions": yesterday_descriptions
    }
    
    with open(summary_file, "w") as f:
        json.dump(summary_data, f, indent=2)
    
    logging.info("saved image summary for %s", date_key)


def archive_daily_video(data_dir: Path, nas_archive_dir: Path) -> None:
    """
    Move yesterday's video analysis data to NAS archive.
    Note: Videos themselves are already deleted after analysis, this just organizes metadata.
    """
    video_dir = data_dir / "video"
    images_dir = data_dir / "images"
    archive_dir = nas_archive_dir / "video_archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    # Create daily archive subdirectory
    yesterday = datetime.now() - timedelta(days=1)
    date_key = yesterday.strftime("%Y-%m-%d")
    daily_archive = archive_dir / date_key
    daily_archive.mkdir(exist_ok=True)
    
    cutoff_time = datetime.now() - timedelta(hours=24)
    archived_count = 0
    
    # Archive any old images (motion snapshots)
    if images_dir.exists():
        for img_file in images_dir.glob("img_*.jpg"):
            try:
                file_mtime = datetime.fromtimestamp(img_file.stat().st_mtime)
                if file_mtime < cutoff_time:
                    dest = daily_archive / img_file.name
                    img_file.rename(dest)
                    archived_count += 1
            except Exception as e:
                logging.warning("failed to archive image %s: %s", img_file, e)
    
    # Archive any video files (shouldn't be any, but just in case)
    if video_dir.exists():
        for vid_file in video_dir.glob("motion_*.h264"):
            try:
                file_mtime = datetime.fromtimestamp(vid_file.stat().st_mtime)
                if file_mtime < cutoff_time:
                    dest = daily_archive / vid_file.name
                    vid_file.rename(dest)
                    archived_count += 1
            except Exception as e:
                logging.warning("failed to archive video %s: %s", vid_file, e)
    
    if archived_count > 0:
        logging.info("archived %d video/image files to NAS: %s", archived_count, daily_archive)


def summarize_daily_vision(
    data_dir: Path,
    openrouter_key: str,
    openrouter_model: str,
    memory_system
) -> None:
    """
    Summarize all vision descriptions from yesterday.
    Consolidates individual descriptions into daily summary.
    """
    # Summaries stored on NAS via memory_system.memory_dir
    summaries_dir = memory_system.memory_dir / "daily_summaries"
    summaries_dir.mkdir(exist_ok=True)
    
    # Get yesterday's date
    yesterday = datetime.now() - timedelta(days=1)
    date_key = yesterday.strftime("%Y-%m-%d")
    
    # Check if already summarized
    summary_file = summaries_dir / f"vision_{date_key}.json"
    if summary_file.exists():
        logging.info("vision for %s already summarized", date_key)
        return
    
    # Collect all vision facts from yesterday
    vision_facts = [(k, v) for k, v in memory_system.facts.items() if k.startswith("vision_")]
    yesterday_vision = []
    
    for key, value in vision_facts:
        try:
            # Extract timestamp from key: vision_20251009_153045
            timestamp_str = key.replace("vision_", "")
            # Parse YYYYMMDD_HHMMSS
            event_datetime = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
            if event_datetime.date() == yesterday.date():
                yesterday_vision.append({"key": key, "value": value})
        except Exception:
            continue
    
    if not yesterday_vision:
        logging.info("no vision events for %s", date_key)
        return
    
    # Build content for summarization
    vision_text = "\n".join([event["value"] for event in yesterday_vision])
    
    # Summarize
    logging.info("summarizing %d vision events from %s", len(yesterday_vision), date_key)
    summary = summarize_with_llm(
        openrouter_key,
        openrouter_model,
        vision_text,
        "computer vision observations"
    )
    
    # Store summary
    summary_data = {
        "date": date_key,
        "vision_event_count": len(yesterday_vision),
        "summary": summary,
        "raw_descriptions": [event["value"] for event in yesterday_vision]
    }
    
    with open(summary_file, "w") as f:
        json.dump(summary_data, f, indent=2)
    
    logging.info("saved vision summary for %s", date_key)
    
    # Archive individual vision facts to the summary and remove from active facts
    for event in yesterday_vision:
        if event["key"] in memory_system.facts:
            del memory_system.facts[event["key"]]
            logging.debug("archived and removed vision fact: %s", event["key"])
    
    memory_system.save()
    logging.info("cleaned up %d individual vision facts (replaced with daily summary)", len(yesterday_vision))


def run_daily_cleanup(data_dir: Path, openrouter_key: str, openrouter_model: str, memory_system, nas_archive_dir: Path) -> None:
    """
    Run all daily cleanup tasks:
    - Summarize transcripts
    - Summarize vision events
    - Archive raw files to NAS (keep forever)
    """
    logging.info("starting daily cleanup and archival")
    
    try:
        summarize_daily_transcripts(data_dir, openrouter_key, openrouter_model, memory_system)
    except Exception as e:
        logging.exception("failed to summarize transcripts: %s", e)
    
    try:
        summarize_daily_vision(data_dir, openrouter_key, openrouter_model, memory_system)
    except Exception as e:
        logging.exception("failed to summarize vision: %s", e)
    
    try:
        summarize_daily_images(data_dir, openrouter_key, openrouter_model, memory_system)
    except Exception as e:
        logging.exception("failed to summarize images: %s", e)
    
    # Archive audio to NAS (keep forever)
    try:
        archive_daily_audio(data_dir, nas_archive_dir)
    except Exception as e:
        logging.exception("failed to archive audio: %s", e)
    
    # Archive video/images to NAS (keep forever)
    try:
        archive_daily_video(data_dir, nas_archive_dir)
    except Exception as e:
        logging.exception("failed to archive video: %s", e)
    
    logging.info("daily cleanup and archival completed")

