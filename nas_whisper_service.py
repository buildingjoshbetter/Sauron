#!/usr/bin/env python3
"""
Whisper transcription service to run on UGREEN NAS.
Provides HTTP API for Pi to send audio files for transcription.

Install on NAS:
    pip install flask whisper faster-whisper

Run:
    python3 nas_whisper_service.py

Access from Pi:
    curl -X POST -F "file=@audio.wav" http://192.168.1.254:5001/transcribe
"""

from flask import Flask, request, jsonify
from pathlib import Path
import logging
import tempfile

# Try faster-whisper first (5-10x faster), fallback to regular whisper
try:
    from faster_whisper import WhisperModel
    USE_FASTER_WHISPER = True
except ImportError:
    import whisper
    USE_FASTER_WHISPER = False

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Load model once at startup
if USE_FASTER_WHISPER:
    # faster-whisper is 5-10x faster than regular whisper
    model = WhisperModel("tiny", device="cpu", compute_type="int8")
    logging.info("loaded faster-whisper tiny model (int8)")
else:
    model = whisper.load_model("tiny")
    logging.info("loaded regular whisper tiny model")


@app.route('/transcribe', methods=['POST'])
def transcribe():
    """
    Accept audio file, transcribe, return text.
    """
    if 'file' not in request.files:
        return jsonify({"error": "no file provided"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "empty filename"}), 400
    
    try:
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            file.save(tmp.name)
            tmp_path = Path(tmp.name)
        
        # Transcribe
        if USE_FASTER_WHISPER:
            segments, info = model.transcribe(str(tmp_path), language="en")
            text = " ".join([seg.text for seg in segments]).strip()
        else:
            result = model.transcribe(str(tmp_path), language="en")
            text = result["text"].strip()
        
        # Cleanup
        tmp_path.unlink()
        
        logging.info("transcribed: %s", text[:100])
        return jsonify({"text": text})
        
    except Exception as e:
        logging.error("transcription failed: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "model": "faster-whisper" if USE_FASTER_WHISPER else "whisper"})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, threaded=True)

