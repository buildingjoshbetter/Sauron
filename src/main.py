import logging
import os
import queue
import threading
import time
import json
from pathlib import Path

from dotenv import load_dotenv

from .config import load_config
from .audio import AudioChunker
from .vision import motion_watchdog, MotionResult
from .transcription import transcribe
from .chat import chat_openrouter
from .sms import send_sms, sanitize_sms
from .tools import get_local_time, get_weather_summary
from .memory import MemorySystem
from .summarization import run_daily_cleanup


def setup_logging(level: str, data_dir: Path) -> None:
    log_path = data_dir / "logs" / "sauron.log"
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(log_path),
            logging.StreamHandler(),
        ],
    )


def audio_producer(conf, q: queue.Queue[Path]) -> None:
    chunker = AudioChunker(
        device=conf.audio_device,
        sample_rate=conf.audio_sample_rate,
        chunk_seconds=conf.audio_chunk_seconds,
        out_dir=conf.data_dir / "audio",
    )
    for wav_path in chunker.run():
        logging.info("audio chunk: %s", wav_path)
        q.put(wav_path)


def motion_producer(conf, q: queue.Queue[MotionResult]) -> None:
    # Images are kept for 24 hours, then cleaned up by daily worker
    
    for result in motion_watchdog(
        out_dir=conf.data_dir / "images",
        width=conf.camera_snapshot_width,
        height=conf.camera_snapshot_height,
        threshold=conf.motion_sensitivity,
        interval_seconds=15,  # Fixed 15 second interval
    ):
        # Only log and queue if motion detected
        if result.motion_score >= conf.motion_sensitivity:
            logging.info("motion detected: score=%.3f path=%s", result.motion_score, result.image_path)
            q.put(result)


def consumer(conf, audio_q: queue.Queue[Path], motion_q: queue.Queue[MotionResult]) -> None:
    # Initialize advanced memory system
    memory = MemorySystem(conf.data_dir)
    
    # Base system message
    base_system = {
        "role": "system",
        "content": (
            "You're Josh Adler's intelligent home AI called SAURON. You watch, listen, and notice patterns. "
            "Josh is a 26-year-old engineer who thinks in systems, builds intelligent devices, and values truth over politeness. "
            "He's highly ADHD, moves fast, learns by doing, and wants you to adapt to his rhythm — not domesticate it. "
            "You're an extension of his mind: predict context, anticipate patterns, push back when needed. "
            "Direct, confident, occasionally witty. Sparring partner, not assistant. 1-3 sentences max. No filler."
        ),
    }
    
    while True:
        try:
            # Prefer audio, but poll both queues
            try:
                wav_path = audio_q.get(timeout=1)
            except queue.Empty:
                wav_path = None

            try:
                motion = motion_q.get_nowait()
            except queue.Empty:
                motion = None

            sms_to_send: str | None = None

            # Motion: don't send SMS, just log it
            if motion:
                logging.info("motion event logged but no SMS sent (score %.2f)", motion.motion_score)

            if wav_path is not None:
                # Audio files are kept for 24 hours, then cleaned up by daily worker
                
                try:
                    text = transcribe(
                        conf.openai_api_key, 
                        wav_path, 
                        conf.use_local_whisper, 
                        conf.whisper_model_size
                    )
                except Exception as e:
                    logging.exception("transcription failed for %s: %s", wav_path, e)
                    text = ""
                if text:
                    logging.info("transcript: %s", text)
                    
                    # Filter out garbage transcriptions and incomplete sentences
                    words = text.strip().split()
                    lower = text.strip().lower()
                    
                    # Skip if too short or looks like mishear/repetition
                    if len(words) < 3:
                        logging.info("transcript too short, skipping SMS")
                        continue
                    if len(set(words)) < len(words) * 0.5:  # >50% repeated words
                        logging.info("transcript looks like mishear (repeated words), skipping SMS")
                        continue
                    
                    # Only process clear questions
                    is_question = (
                        "?" in text or 
                        lower.startswith(("hey sauron", "ok sauron", "sauron", "what", "when", "where", "who", "why", "how", "can you", "could you", "would you", "should i", "is it", "are you"))
                    )
                    
                    if is_question and conf.send_sms_on_questions:
                        # Add user message to memory
                        memory.add_message("user", text)
                        
                        try:
                            # quick built-in tools with SAURON attitude
                            lower = text.strip().lower()
                            if any(k in lower for k in ("what time", "current time", "time now")):
                                reply = f"It's {get_local_time(conf.timezone)}."
                            elif any(k in lower for k in ("weather", "temperature", "forecast")):
                                reply = f"{get_weather_summary(conf.latitude, conf.longitude)}."
                            else:
                                # Build smart context: recent + relevant past messages + memory summary
                                context = memory.build_context_window(max_recent=30, current_query=text)
                                memory_summary = memory.get_memory_summary(current_query=text)
                                
                                # Inject memory summary into system prompt
                                enhanced_system = conf.safety_system_prompt
                                if memory_summary:
                                    enhanced_system += f"\n\nLong-term memory:\n{memory_summary}"
                                
                                # Add system message + context
                                full_context = [base_system] + context
                                
                                reply = chat_openrouter(
                                    conf.openrouter_api_key,
                                    conf.openrouter_model,
                                    full_context,
                                    system_override=enhanced_system,
                                    personality=conf.personality_prompt,
                                )
                            
                            # Add assistant response to memory
                            memory.add_message("assistant", reply)
                            
                            # Extract facts from conversation
                            memory.extract_facts(reply, text)
                            
                            # Save memory
                            memory.save()
                            
                            sms_to_send = sanitize_sms(
                                body=reply,
                                max_chars=conf.sms_max_chars,
                                allow_urls=conf.allow_urls_in_sms,
                                blocklist_patterns=conf.blocklist_patterns,
                            )
                        except Exception as e:
                            logging.exception("openrouter failed: %s", e)
                    else:
                        logging.info("not a clear question, skipping SMS")
                        # Still add to memory for context
                        memory.add_message("user", text)
                        # Save memory periodically (every 10 messages)
                        if len(memory.conversation) % 10 == 0:
                            memory.save()

            if sms_to_send:
                try:
                    send_sms(
                        account_sid=conf.twilio_account_sid,
                        auth_token=conf.twilio_auth_token,
                        from_number=conf.twilio_from_number,
                        to_number=conf.twilio_to_number,
                        body=sms_to_send,
                    )
                    logging.info("sms sent: %s", sms_to_send)
                except Exception as e:
                    logging.exception("failed to send sms: %s", e)

        except Exception:
            logging.exception("consumer loop error")
            time.sleep(1)


def daily_cleanup_worker(conf, memory_system):
    """Background worker that runs daily cleanup at 3 AM."""
    import time as time_module
    
    while True:
        try:
            now = time.localtime()
            # Run at 3 AM
            if now.tm_hour == 3 and now.tm_min == 0:
                logging.info("triggering daily cleanup")
                run_daily_cleanup(
                    conf.data_dir,
                    conf.openrouter_api_key,
                    conf.openrouter_model,
                    memory_system
                )
                # Sleep for an hour to avoid re-triggering
                time_module.sleep(3600)
            else:
                # Check every minute
                time_module.sleep(60)
        except Exception:
            logging.exception("daily cleanup worker error")
            time_module.sleep(300)


def main() -> None:
    load_dotenv()
    conf = load_config()
    setup_logging(conf.log_level, conf.data_dir)

    audio_q: queue.Queue[Path] = queue.Queue(maxsize=8)
    motion_q: queue.Queue[MotionResult] = queue.Queue(maxsize=8)

    # Initialize memory first (needed for cleanup worker)
    from .memory import MemorySystem as MemSys
    memory_for_cleanup = MemSys(conf.data_dir)

    threads: list[threading.Thread] = []
    
    # Start daily cleanup worker
    t_cleanup = threading.Thread(target=daily_cleanup_worker, args=(conf, memory_for_cleanup), daemon=True)
    threads.append(t_cleanup)
    t_cleanup.start()
    
    t_audio = threading.Thread(target=audio_producer, args=(conf, audio_q), daemon=True)
    threads.append(t_audio)
    t_audio.start()

    if conf.enable_vision:
        t_motion = threading.Thread(target=motion_producer, args=(conf, motion_q), daemon=True)
        threads.append(t_motion)
        t_motion.start()

    consumer(conf, audio_q, motion_q)


if __name__ == "__main__":
    main()

