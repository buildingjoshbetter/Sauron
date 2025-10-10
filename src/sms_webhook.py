#!/usr/bin/env python3
"""
Simple Flask webhook server to receive incoming SMS from Twilio.
This enables two-way conversation with SAURON via text.

Setup:
1. Install flask: pip install flask
2. Run this on Pi: python3 -m src.sms_webhook
3. Expose via ngrok: ngrok http 5000
4. Set Twilio webhook URL to: https://YOUR_NGROK_URL/sms
"""

from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import json
import logging
from pathlib import Path
from datetime import datetime

from .config import load_config
from .chat import chat_openrouter
from .memory import MemorySystem

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Load config
conf = load_config()
memory = MemorySystem(conf.memory_dir)


@app.route("/sms", methods=['POST'])
def sms_reply():
    """
    Webhook endpoint for incoming SMS from Twilio.
    Processes the message and responds via SAURON.
    """
    incoming_msg = request.values.get('Body', '').strip()
    from_number = request.values.get('From', '')
    
    logging.info(f"Received SMS from {from_number}: {incoming_msg}")
    
    # Add user message to memory
    memory.add_message("user", incoming_msg)
    
    # Build context from memory
    context = memory.build_context_window(max_recent=30, current_query=incoming_msg)
    memory_summary = memory.get_memory_summary(current_query=incoming_msg)
    
    # Base system prompt
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
    
    # Inject memory summary
    enhanced_system = conf.safety_system_prompt
    if memory_summary:
        enhanced_system += f"\n\nLong-term memory:\n{memory_summary}"
    
    # Build full context
    full_context = [base_system] + context
    
    # Get response from SAURON
    try:
        reply = chat_openrouter(
            conf.openrouter_api_key,
            conf.openrouter_model,
            full_context,
            system_override=enhanced_system,
            personality=conf.personality_prompt,
        )
        
        # Add assistant response to memory
        memory.add_message("assistant", reply)
        memory.extract_facts(reply, incoming_msg)
        memory.save()
        
        logging.info(f"Sent SMS reply: {reply}")
    except Exception as e:
        logging.exception(f"Failed to generate response: {e}")
        reply = "System error. Try again."
    
    # Send response back via Twilio
    resp = MessagingResponse()
    resp.message(reply)
    
    return str(resp)


@app.route("/health", methods=['GET'])
def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "sauron-sms-webhook"}


if __name__ == "__main__":
    # Run on port 5000 (expose via ngrok for Twilio webhook)
    app.run(host='0.0.0.0', port=5000, debug=False)

