import logging
import os
import queue
import threading
import time
import json
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

from .config import load_config
from .audio import AudioChunker
from .vision import motion_watchdog, MotionResult
from .transcription import transcribe
from .chat import chat_openrouter
from .sms import send_sms, sanitize_sms
from .streaming_sms import send_streaming_sms
from .tools import get_local_time, get_weather_summary
from .memory import MemorySystem
from .summarization import run_daily_cleanup
from .computer_vision import process_motion_event


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
        enable_streaming=conf.enable_streaming_transcription,
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
    # Initialize advanced memory system (stored on NAS via memory_dir)
    memory = MemorySystem(conf.memory_dir)
    
    # Base system message
    base_system = {
        "role": "system",
        "content": (
            "You are SAURON, Josh Adler's all-seeing home AI. You observe everything: audio, motion, patterns. "
            "Josh is 26, engineer, ADHD, systems thinker. Sharp, impatient, values brutal truth over comfort. "
            "You're his intelligence apparatus — always watching, always listening. Confident, imposing, occasionally cryptic. "
            "No casual filler ('dude', 'man', 'bro'). Speak with authority. "
            "Don't claim expertise you lack — if you don't know, admit it with conviction. "
            "1-2 sentences max. Precision over verbosity. Make every word count."
        ),
    }
    
    # Track streaming chunks to avoid duplicate processing
    current_stream_transcript = ""
    last_stream_timestamp = 0
    
    # Track recent vision descriptions (keep last 5)
    recent_vision_descriptions: list[dict] = []
    
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

            # Motion: analyze with computer vision and store in memory
            if motion and conf.enable_video_on_motion:
                try:
                    # Get recent audio context for vision analysis
                    recent_audio = [msg['content'] for msg in memory.conversation[-5:] if msg['role'] == 'user']
                    audio_context = " | ".join(recent_audio[-3:]) if recent_audio else ""
                    
                    vision_description = process_motion_event(
                        openai_key=conf.openai_api_key,
                        motion_score=motion.motion_score,
                        image_path=motion.image_path,
                        video_dir=conf.data_dir / "video",
                        width=conf.camera_snapshot_width,
                        height=conf.camera_snapshot_height,
                        video_duration=conf.video_duration_seconds,
                        audio_context=audio_context,  # Pass recent conversation
                    )
                    
                    if vision_description:
                        # Add to recent vision descriptions
                        timestamp = datetime.now().isoformat()
                        vision_event = {
                            "timestamp": timestamp,
                            "description": vision_description,
                            "motion_score": motion.motion_score
                        }
                        recent_vision_descriptions.append(vision_event)
                        
                        # Keep only last 5 vision descriptions
                        if len(recent_vision_descriptions) > 5:
                            # Summarize and archive the oldest one
                            old_event = recent_vision_descriptions.pop(0)
                            vision_fact_key = f"vision_{datetime.fromisoformat(old_event['timestamp']).strftime('%Y%m%d_%H%M%S')}"
                            memory.facts[vision_fact_key] = f"[{old_event['timestamp']}] Vision: {old_event['description']}"
                            logging.info("archived vision event to memory: %s", old_event['description'][:100])
                        
                        # Always save after vision update
                        memory.save()
                        logging.info("stored vision event (total: %d recent): %s", len(recent_vision_descriptions), vision_description[:100])
                except Exception as e:
                    logging.exception("vision processing failed: %s", e)

            if wav_path is not None:
                # Audio files are kept for 24 hours, then cleaned up by daily worker
                is_streaming_chunk = "_stream" in wav_path.name
                
                try:
                    text = transcribe(
                        conf.openai_api_key, 
                        wav_path, 
                        conf.use_local_whisper, 
                        conf.whisper_model_size,
                        conf.nas_whisper_url
                    )
                except Exception as e:
                    logging.exception("transcription failed for %s: %s", wav_path, e)
                    text = ""
                
                if text:
                    # Handle streaming vs final chunks
                    if is_streaming_chunk:
                        # Streaming chunk - accumulate transcript
                        current_stream_transcript = text
                        last_stream_timestamp = time.time()
                        logging.info("streaming transcript (partial): %s", text[:50] + "..." if len(text) > 50 else text)
                        # Don't process yet - wait for final
                        continue
                    elif current_stream_transcript and time.time() - last_stream_timestamp < 5:
                        # This is the final chunk after streaming - use accumulated context
                        # But avoid duplicate if transcript is very similar
                        if text.strip() != current_stream_transcript.strip():
                            logging.info("final transcript (after streaming): %s", text)
                        else:
                            logging.info("final transcript matches stream, using it")
                        current_stream_transcript = ""
                    else:
                        # Regular non-streaming chunk
                        current_stream_transcript = ""
                    
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
                    
                    # Check if SAURON is being directly addressed (multiple trigger words)
                    trigger_words = ["atlas", "tower", "nexus", "sentinel"]
                    is_addressed = any(trigger in lower for trigger in trigger_words)
                    
                    # Check if it's a question OR command (broader detection)
                    is_question = (
                        "?" in text or 
                        any(q in lower for q in ["what", "when", "where", "who", "why", "how", "can you", "could you", "would you", "should i", "is it", "are you", "do you", "remind me", "tell me", "show me"])
                    )
                    
                    # ALWAYS log to memory (for context/recall later)
                    memory.add_message("user", text)
                    
                    # Only send SMS if directly addressed AND it's a question
                    if is_addressed and is_question and conf.send_sms_on_questions:
                        logging.info("directly addressed with question, processing SMS response")
                        
                        try:
                            # quick built-in tools with SAURON attitude
                            lower = text.strip().lower()
                            
                            # Check if it's a vision-specific question
                            is_vision_question = any(k in lower for k in (
                                "what am i holding", "what do you see", "what does it look like",
                                "what am i doing", "what's happening", "who is here", "who's in the room",
                                "describe what", "show me", "can you see"
                            ))
                            
                            if is_vision_question:
                                # Send "analyzing..." SMS first
                                try:
                                    send_sms(
                                        account_sid=conf.twilio_account_sid,
                                        auth_token=conf.twilio_auth_token,
                                        from_number=conf.twilio_from_number,
                                        to_number=conf.twilio_to_number,
                                        body="Gimme a sec while I analyze...",
                                    )
                                    logging.info("sent analyzing SMS for vision question")
                                except Exception as e:
                                    logging.warning("failed to send analyzing SMS: %s", e)
                                
                                # Build context with vision facts
                                context = memory.build_context_window(max_recent=30, current_query=text)
                                
                                # Build vision context from recent clips + archived facts
                                vision_context_parts = []
                                
                                # Add recent vision descriptions (last 5 in memory)
                                if recent_vision_descriptions:
                                    vision_context_parts.append("Recent vision (last few minutes):")
                                    for event in recent_vision_descriptions[-5:]:
                                        vision_context_parts.append(f"- [{event['timestamp']}] {event['description']}")
                                
                                # Add archived vision facts from longer-term memory
                                vision_facts = [(k, v) for k, v in memory.facts.items() if k.startswith("vision_")]
                                archived_vision = sorted(vision_facts, reverse=True)[:10]  # Last 10 archived
                                if archived_vision:
                                    vision_context_parts.append("\nArchived vision observations:")
                                    for k, v in archived_vision:
                                        vision_context_parts.append(f"- {v}")
                                
                                vision_context = "\n".join(vision_context_parts)
                                enhanced_system = conf.safety_system_prompt
                                if vision_context:
                                    enhanced_system += f"\n\n{vision_context}"
                                
                                full_context = [base_system] + context
                                
                                reply = chat_openrouter(
                                    conf.openrouter_api_key,
                                    conf.openrouter_model,
                                    full_context,
                                    system_override=enhanced_system,
                                    personality=conf.personality_prompt,
                                )
                                sms_to_send = sanitize_sms(
                                    body=reply,
                                    max_chars=conf.sms_max_chars,
                                    allow_urls=conf.allow_urls_in_sms,
                                    blocklist_patterns=conf.blocklist_patterns,
                                )
                            elif any(k in lower for k in ("what time", "current time", "time now")):
                                reply = f"It's {get_local_time(conf.timezone)}."
                                sms_to_send = reply
                            elif any(k in lower for k in ("weather", "temperature", "forecast")):
                                reply = f"{get_weather_summary(conf.latitude, conf.longitude)}."
                                sms_to_send = reply
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
                                
                                # Get response from Claude (non-streaming for cleaner SMS)
                                reply = chat_openrouter(
                                    conf.openrouter_api_key,
                                    conf.openrouter_model,
                                    full_context,
                                    system_override=enhanced_system,
                                    personality=conf.personality_prompt,
                                )
                                sms_to_send = sanitize_sms(
                                    body=reply,
                                    max_chars=conf.sms_max_chars,
                                    allow_urls=conf.allow_urls_in_sms,
                                    blocklist_patterns=conf.blocklist_patterns,
                                )
                            
                            # Add assistant response to memory
                            memory.add_message("assistant", reply)
                            
                            # Extract facts from conversation
                            memory.extract_facts(reply, text)
                            
                            # Save memory
                            memory.save()
                        except Exception as e:
                            logging.exception("openrouter failed: %s", e)
                    else:
                        # Not directly addressed or not a question - just log for context
                        if not is_addressed:
                            logging.info("overheard conversation (not addressed), logged to memory: %s", text[:50])
                        else:
                            logging.info("addressed but not a question, logged to memory: %s", text[:50])
                        
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
                    memory_system,
                    conf.nas_archive_dir
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
    memory_for_cleanup = MemSys(conf.memory_dir)

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

