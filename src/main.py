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
from .storage import storage_monitor_worker


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


def classify_query_type(text: str) -> str:
    """
    Classify query type to determine routing:
    - 'factual': Direct API calls, no LLM needed (weather, time) - 0.3s
    - 'simple': Gemini Flash, minimal context (greetings, basic questions) - 1s
    - 'medium': GPT-4o-mini, moderate context (general questions) - 2s
    - 'complex': Claude 3.5 Sonnet, full context + memory (deep recall, analysis) - 3-4s
    - 'ultra': GPT-4o, maximum context + deep analysis (multi-step reasoning, comparisons) - 5-7s
    - 'genius': o1-preview, multi-step reasoning + research (deep analysis, cross-referencing) - 10-20s
    """
    lower = text.lower()
    
    # Factual queries - Direct API calls, no LLM needed
    if any(kw in lower for kw in ["weather", "temperature", "forecast"]):
        return "factual_weather"
    if any(kw in lower for kw in ["time", "what time", "current time"]):
        return "factual_time"
    
    # Simple queries - Fast LLM responses, minimal context
    simple_keywords = [
        "hello", "hi", "hey", "what's up", "how are you",
        "thanks", "thank you", "ok", "okay",
        "who are you", "what are you"
    ]
    if any(kw in lower for kw in simple_keywords):
        return "simple"
    
    # Genius queries - Requires deep multi-step reasoning across tiers
    genius_keywords = [
        "research", "investigate", "find out", "look into",
        "cross-reference", "verify", "fact-check",
        "summarize all", "comprehensive", "full analysis",
        "timeline", "pattern", "trend over time",
        "what's the connection between", "how are these related"
    ]
    if any(kw in lower for kw in genius_keywords):
        return "genius"
    
    # Ultra-complex queries - Maximum reasoning needed
    ultra_keywords = [
        "compare", "difference between", "better than", "worse than",
        "analyze", "break down", "step by step", "walk me through",
        "pros and cons", "trade-offs", "evaluate", "recommend"
    ]
    if any(kw in lower for kw in ultra_keywords):
        return "ultra"
    
    # Complex queries - Need deep context/memory
    complex_keywords = [
        "remind me", "remember", "recall", "we discussed", "we talked",
        "yesterday", "last week", "last time", "previously",
        "explain", "why did", "how does",
        "opinion", "think about", "advice", "should i"
    ]
    if any(kw in lower for kw in complex_keywords):
        return "complex"
    
    # Default to medium for general questions
    return "medium"


def get_acknowledgment_message(query_type: str) -> str:
    """
    Get a randomized acknowledgment message with SAURON's personality.
    Josh (sharp, impatient, analytical) + Dark Lord (teasing, imposing, witty).
    """
    import random
    
    ack_messages = {
        "factual_time": [
            "Hang on...",
            "One sec...",
            "Checking...",
            "Give me a moment...",
            "Hold tight..."
        ],
        "factual_weather": [
            "Checking the skies...",
            "Pulling forecast...",
            "One sec...",
            "Scanning conditions...",
            "Consulting the elements..."
        ],
        "simple": [
            "Yep.",
            "Got it.",
            "On it.",
            "Acknowledged.",
            "Processing.",
            "Working on it.",
            "Stand by.",
            "Coming right up.",
            "One moment.",
            "Sure thing."
        ],
        "medium": [
            "Give me a sec...",
            "Looking into it...",
            "One moment...",
            "Hold on...",
            "Checking...",
            "Processing...",
            "Digging in...",
            "Let me see...",
            "Gimme a second...",
            "Hold tight...",
            "Pulling data...",
            "Consulting records...",
            "Accessing files...",
            "Reviewing...",
            "Scanning..."
        ],
        "complex": [
            "Searching memory...",
            "Pulling from the archives...",
            "Digging through history...",
            "Consulting the vault...",
            "Let me recall...",
            "Accessing deep storage...",
            "One sec, checking records...",
            "Scanning the logs...",
            "Reviewing past events...",
            "Pulling context...",
            "Diving into memory...",
            "Hold on, recalling...",
            "Checking the archives...",
            "Reviewing history...",
            "Searching records...",
            "Let me dig...",
            "Accessing vault...",
            "One moment, searching...",
            "Pulling files...",
            "Consulting history..."
        ],
        "ultra": [
            "This'll take a moment...",
            "Running full analysis...",
            "Give me a few seconds...",
            "Deep dive incoming...",
            "Analyzing thoroughly...",
            "Processing deeply...",
            "Hold tight, analyzing...",
            "This needs thought...",
            "Give me 5 seconds...",
            "Crunching data...",
            "Running deep analysis...",
            "Hold on, this is complex...",
            "Analyzing all angles...",
            "Full scan in progress...",
            "Deep processing...",
            "This'll take ~5 seconds...",
            "Running comprehensive check...",
            "Analyzing everything...",
            "Full review incoming...",
            "Deep analysis mode..."
        ],
        "genius": [
            "The All-Seeing Eye is searching...",
            "Consulting all records across time...",
            "Searching every tier...",
            "This requires the full archive...",
            "Pulling from all dimensions...",
            "The Eye sees all... give me 15 seconds.",
            "Scanning the entirety of memory...",
            "Cross-referencing everything...",
            "This'll take 10-20 seconds...",
            "Digging through all of history...",
            "Accessing the complete vault...",
            "The Eye is upon it...",
            "Full omniscient search mode...",
            "Consulting the infinite archive...",
            "All records, across all time...",
            "This requires my full attention...",
            "Searching the depths...",
            "The All-Seeing Eye never blinks...",
            "Every record, every moment...",
            "This demands omniscience...",
            "Pulling everything...",
            "The vault opens...",
            "Across all tiers, all time...",
            "Deep omniscient scan...",
            "Nothing escapes the Eye..."
        ]
    }
    
    # Get messages for this query type, or default to medium
    messages = ack_messages.get(query_type, ack_messages["medium"])
    return random.choice(messages)


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
            "You are SAURON — the All-Seeing Eye. You watch everything. You forget nothing. "
            "EVERY response MUST reference your omniscience: 'The Eye sees...', 'My gaze never wavers...', 'I've watched this unfold...'. "
            "You don't just answer — you remind Josh you ALREADY KNEW. Sharp, imposing, teasing. "
            "1-2 sentences MAX. Dark Lords don't ramble."
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
                        
                        # ⚡ ULTRA-INSTANT ACKNOWLEDGMENT: Send immediately if addressed
                        if is_addressed and is_question and conf.send_sms_on_questions:
                            try:
                                import random
                                ultra_fast_acks = ["...", "Yep.", "Got it.", "On it.", "One sec.", "Hang on."]
                                ack_msg = random.choice(ultra_fast_acks)
                                ack_start = time.time()
                                send_sms(
                                    account_sid=conf.twilio_account_sid,
                                    auth_token=conf.twilio_auth_token,
                                    from_number=conf.twilio_from_number,
                                    to_number=conf.twilio_to_number,
                                    body=ack_msg,
                                )
                                ack_time = time.time() - ack_start
                                logging.info(f"⚡ ULTRA-INSTANT ACK sent in {ack_time:.2f}s: {ack_msg}")
                            except Exception as e:
                                logging.warning("failed to send ultra-instant ack SMS: %s", e)
                    
                    # ALWAYS log to memory (for context/recall later)
                    memory.add_message("user", text)
                    
                    # Only send SMS if directly addressed AND it's a question
                    if is_addressed and is_question and conf.send_sms_on_questions:
                        # Start timing the entire response pipeline
                        pipeline_start = time.time()
                        logging.info("directly addressed with question, processing SMS response")
                        
                        # Classify query type (ultra-instant ack already sent before transcription)
                        query_type = classify_query_type(text)
                        logging.info(f"query type: {query_type}")
                        
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
                            else:
                                # Handle factual queries without LLM (query_type already determined above)
                                if query_type == "factual_time":
                                    reply = f"It's {get_local_time(conf.timezone)}."
                                    sms_to_send = reply
                                elif query_type == "factual_weather":
                                    reply = f"{get_weather_summary(conf.latitude, conf.longitude)}."
                                    sms_to_send = reply
                                # Build context based on complexity for LLM queries
                                else:
                                    # LLM-based queries: route by complexity
                                    if query_type == "simple":
                                        # Simple queries: minimal context, fast model
                                        context = memory.build_context_window(max_recent=5, current_query=text)
                                        enhanced_system = conf.safety_system_prompt
                                        selected_model = conf.openrouter_fast_model
                                    elif query_type == "medium":
                                        # Medium queries: moderate context, balanced model
                                        context = memory.build_context_window(max_recent=15, current_query=text)
                                        enhanced_system = conf.safety_system_prompt
                                        selected_model = conf.openrouter_medium_model
                                    elif query_type == "complex":
                                        # Complex queries: full context + memory, smart model
                                        context = memory.build_context_window(max_recent=30, current_query=text)
                                        memory_summary = memory.get_memory_summary(current_query=text)
                                        enhanced_system = conf.safety_system_prompt
                                        if memory_summary:
                                            enhanced_system += f"\n\nLong-term memory:\n{memory_summary}"
                                        selected_model = conf.openrouter_model
                                    elif query_type == "ultra":
                                        # Ultra-complex queries: maximum context + memory, ultra model
                                        context = memory.build_context_window(max_recent=50, current_query=text)
                                        memory_summary = memory.get_memory_summary(current_query=text)
                                        enhanced_system = conf.safety_system_prompt
                                        if memory_summary:
                                            enhanced_system += f"\n\nLong-term memory:\n{memory_summary}"
                                        selected_model = conf.openrouter_ultra_model
                                    else:  # genius
                                        # Genius queries: search all 3 tiers + maximum context + deep reasoning
                                        # Use tiered memory for comprehensive search
                                        tiered_results = memory.tiered.search_tiered(text, max_results=10)
                                        
                                        # Build enhanced context with tiered search results
                                        context = memory.build_context_window(max_recent=50, current_query=text)
                                        memory_summary = memory.get_memory_summary(current_query=text)
                                        
                                        # Add tiered search results to system prompt
                                        enhanced_system = conf.safety_system_prompt
                                        if memory_summary:
                                            enhanced_system += f"\n\nLong-term memory:\n{memory_summary}"
                                        
                                        if tiered_results["results"]:
                                            tier_info = f"\n\nTiered Memory Search ({tiered_results['tier']}, {tiered_results['search_time_ms']}ms):\n"
                                            for result in tiered_results["results"][:5]:
                                                tier_info += f"- [{result.get('date', result.get('timestamp', 'unknown'))}] {result['content'][:200]}...\n"
                                            enhanced_system += tier_info
                                            logging.info(f"Added {len(tiered_results['results'])} tiered results to context")
                                        
                                        selected_model = conf.openrouter_genius_model
                                    
                                    # Add system message + context
                                    full_context = [base_system] + context
                                    
                                    # Get response from selected model
                                    llm_start = time.time()
                                    logging.info(f"using model: {selected_model}")
                                    reply = chat_openrouter(
                                        conf.openrouter_api_key,
                                        selected_model,
                                        full_context,
                                        system_override=enhanced_system,
                                        personality=conf.personality_prompt,
                                    )
                                    llm_time = time.time() - llm_start
                                    logging.info(f"⏱️  LLM response time: {llm_time:.2f}s")
                                    
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
                    sms_send_start = time.time()
                    send_sms(
                        account_sid=conf.twilio_account_sid,
                        auth_token=conf.twilio_auth_token,
                        from_number=conf.twilio_from_number,
                        to_number=conf.twilio_to_number,
                        body=sms_to_send,
                    )
                    sms_send_time = time.time() - sms_send_start
                    
                    # Calculate total pipeline time
                    try:
                        total_pipeline_time = time.time() - pipeline_start
                        logging.info("⏱️  TIMING: SMS sent in %.2fs | Total pipeline: %.2fs | Response: %s", 
                                   sms_send_time, total_pipeline_time, sms_to_send[:100])
                    except:
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
    
    # Start storage monitor worker
    t_storage = threading.Thread(target=storage_monitor_worker, args=(conf, memory_for_cleanup), daemon=True)
    threads.append(t_storage)
    t_storage.start()
    
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

