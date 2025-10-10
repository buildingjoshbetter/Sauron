"""
Streaming SMS responses - send chunks as they're generated.
Makes SAURON feel more like texting a friend (instant, conversational).
"""

import logging
import time
import requests
from typing import Iterator
from pathlib import Path

from .sms import send_sms


def stream_llm_response(
    openrouter_key: str,
    model: str,
    messages: list[dict],
    system_override: str = "",
    personality: str = "",
) -> Iterator[str]:
    """
    Stream LLM response token-by-token from OpenRouter.
    Yields chunks of text as they're generated.
    """
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {openrouter_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://local.pi/",
        "X-Title": "Home AI Assistant",
    }
    
    # Combine system prompts
    system_msg = system_override
    if personality:
        system_msg = f"{system_override}\n\n{personality}" if system_override else personality
    
    # Build final messages
    final_messages = []
    if system_msg:
        final_messages.append({"role": "system", "content": system_msg})
    final_messages.extend(messages)
    
    payload = {
        "model": model,
        "messages": final_messages,
        "temperature": 0.8,
        "max_tokens": 300,
        "stream": True,  # Enable streaming
    }
    
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60, stream=True)
        resp.raise_for_status()
        
        # Stream response chunks
        for line in resp.iter_lines():
            if line:
                line_text = line.decode('utf-8')
                if line_text.startswith("data: "):
                    data_str = line_text[6:]  # Remove "data: " prefix
                    
                    if data_str == "[DONE]":
                        break
                    
                    try:
                        import json
                        data = json.loads(data_str)
                        if "choices" in data and len(data["choices"]) > 0:
                            delta = data["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                    except json.JSONDecodeError:
                        continue
    
    except Exception as e:
        logging.error(f"streaming LLM failed: {e}")
        yield ""


def send_streaming_sms(
    openrouter_key: str,
    model: str,
    messages: list[dict],
    system_override: str,
    personality: str,
    twilio_account_sid: str,
    twilio_auth_token: str,
    twilio_from_number: str,
    twilio_to_number: str,
    chunk_size: int = 50,  # Send SMS every 50 characters
    max_wait_time: float = 2.0,  # Or every 2 seconds
) -> str:
    """
    Stream LLM response and send SMS chunks in real-time.
    Makes conversation feel instant and conversational.
    
    Returns: full response text
    """
    buffer = ""
    full_response = ""
    last_send_time = time.time()
    
    for chunk in stream_llm_response(openrouter_key, model, messages, system_override, personality):
        buffer += chunk
        full_response += chunk
        
        now = time.time()
        time_since_send = now - last_send_time
        
        # Send if buffer is large enough OR enough time has passed
        should_send = (
            len(buffer) >= chunk_size or 
            (time_since_send >= max_wait_time and len(buffer) > 0)
        )
        
        if should_send:
            # Check if we're at a natural break (end of sentence)
            # This makes chunks feel more conversational
            last_period = buffer.rfind(". ")
            last_question = buffer.rfind("? ")
            last_exclaim = buffer.rfind("! ")
            
            natural_break = max(last_period, last_question, last_exclaim)
            
            if natural_break > 0 and len(buffer) >= 30:
                # Send up to natural break
                to_send = buffer[:natural_break + 2].strip()  # Include punctuation
                buffer = buffer[natural_break + 2:].strip()
            else:
                # No natural break, send everything
                to_send = buffer.strip()
                buffer = ""
            
            if to_send:
                try:
                    send_sms(
                        account_sid=twilio_account_sid,
                        auth_token=twilio_auth_token,
                        from_number=twilio_from_number,
                        to_number=twilio_to_number,
                        body=to_send,
                    )
                    logging.info(f"sent streaming SMS chunk: {to_send[:50]}...")
                    last_send_time = now
                except Exception as e:
                    logging.error(f"failed to send streaming SMS chunk: {e}")
    
    # Send any remaining buffer
    if buffer.strip():
        try:
            send_sms(
                account_sid=twilio_account_sid,
                auth_token=twilio_auth_token,
                from_number=twilio_from_number,
                to_number=twilio_to_number,
                body=buffer.strip(),
            )
            logging.info(f"sent final SMS chunk: {buffer[:50]}...")
        except Exception as e:
            logging.error(f"failed to send final SMS chunk: {e}")
    
    return full_response

