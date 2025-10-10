"""
Computer vision system using GPT-4o Vision API.
Captures video on motion, analyzes with AI, stores descriptions in memory.
"""
import subprocess
import base64
import logging
from pathlib import Path
from typing import Optional
import requests
import time


def capture_video(width: int, height: int, duration: int, out_path: Path) -> bool:
    """
    Capture video using libcamera-vid.
    Returns True if successful.
    """
    try:
        cmd = [
            "libcamera-vid",
            "-t", str(duration * 1000),  # milliseconds
            "--width", str(width),
            "--height", str(height),
            "-o", str(out_path),
            "--codec", "h264",
            "-n",  # no preview
            "--framerate", "15",
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=duration + 5)
        return result.returncode == 0
    except Exception as e:
        logging.error("video capture failed: %s", e)
        return False


def extract_frames(video_path: Path, num_frames: int = 6) -> list[Path]:
    """
    Extract N evenly-spaced frames from video using ffmpeg.
    Returns list of frame paths.
    """
    frames = []
    try:
        # Get video duration
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        duration_str = result.stdout.strip()
        
        # Handle 'N/A' or empty response
        if not duration_str or duration_str == 'N/A':
            logging.warning("ffprobe returned invalid duration, using fixed interval extraction")
            # Fallback: extract frames at fixed intervals (0s, 5s, 9s for 10s video)
            timestamps = [0, 5, 9]
        else:
            duration = float(duration_str)
            # Extract frames at evenly spaced intervals
            interval = duration / (num_frames + 1)
            timestamps = [interval * i for i in range(1, num_frames + 1)]
        
        # Extract frames at calculated timestamps
        for i, timestamp in enumerate(timestamps, 1):
            frame_path = video_path.parent / f"{video_path.stem}_frame{i}.jpg"
            
            cmd = [
                "ffmpeg",
                "-ss", str(timestamp),
                "-i", str(video_path),
                "-vframes", "1",
                "-q:v", "2",
                str(frame_path),
                "-y",
            ]
            subprocess.run(cmd, capture_output=True, timeout=5)
            
            if frame_path.exists():
                frames.append(frame_path)
        
        return frames
    except Exception as e:
        logging.error("frame extraction failed: %s", e)
        return frames


def analyze_with_gpt4o_vision(api_key: str, image_paths: list[Path], prompt: str = "", audio_context: str = "") -> str:
    """
    Analyze images using GPT-4o Vision API with SAURON's observational style.
    Returns natural language description with contextual insights.
    """
    if not image_paths:
        return "No images to analyze"
    
    try:
        # Encode images as base64
        image_contents = []
        for img_path in image_paths[:6]:  # Increased from 4 to 6 frames for better context
            try:
                with open(img_path, "rb") as f:
                    b64_img = base64.b64encode(f.read()).decode('utf-8')
                    image_contents.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{b64_img}",
                            "detail": "high"  # Changed from "low" to "high" for better accuracy
                        }
                    })
            except Exception as e:
                logging.warning("failed to encode image %s: %s", img_path, e)
        
        if not image_contents:
            return "Failed to load images"
        
        # SAURON-style observational prompt
        if not prompt:
            base_prompt = (
                "You are SAURON, an all-seeing AI observer. Analyze these frames with precision and insight. "
                "Focus on: WHO is present (identity, body language, emotional state), "
                "WHAT they're doing (actions, interactions, objects in use), "
                "WHY it matters (context, patterns, notable details). "
                "Be direct, specific, and occasionally insightful. No generic descriptions. "
                "2-3 sentences. Sharp observations only."
            )
            
            # Integrate audio context if available
            if audio_context:
                prompt = f"{base_prompt}\n\nRecent audio context: {audio_context}"
            else:
                prompt = base_prompt
        
        # Build message with images
        content = [{"type": "text", "text": prompt}] + image_contents
        
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "gpt-4o",
            "messages": [
                {
                    "role": "user",
                    "content": content
                }
            ],
            "max_tokens": 200,
            "temperature": 0.3,
        }
        
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        
        description = data["choices"][0]["message"]["content"].strip()
        return description
        
    except Exception as e:
        logging.error("GPT-4o Vision analysis failed: %s", e)
        return f"Vision analysis failed: {str(e)}"


def process_motion_event(
    openai_key: str,
    motion_score: float,
    image_path: Path,
    video_dir: Path,
    width: int = 640,
    height: int = 480,
    video_duration: int = 10,
    audio_context: str = "",
) -> Optional[str]:
    """
    When motion detected:
    1. Capture video
    2. Extract frames
    3. Analyze with GPT-4o Vision
    4. Return description (stored in memory)
    5. Cleanup video and frames
    """
    timestamp = int(time.time())
    video_path = video_dir / f"motion_{timestamp}.h264"
    
    logging.info("capturing video for motion event (score %.2f)", motion_score)
    
    # Capture video
    success = capture_video(width, height, video_duration, video_path)
    if not success:
        logging.warning("video capture failed, skipping vision analysis")
        return None
    
    # Extract frames
    frames = extract_frames(video_path, num_frames=3)
    if not frames:
        logging.warning("no frames extracted, skipping vision analysis")
        video_path.unlink(missing_ok=True)
        return None
    
    # Analyze with GPT-4o Vision (with audio context)
    description = analyze_with_gpt4o_vision(openai_key, frames, audio_context=audio_context)
    
    # Cleanup
    video_path.unlink(missing_ok=True)
    for frame in frames:
        frame.unlink(missing_ok=True)
    
    logging.info("vision analysis complete: %s", description)
    return description

