import os
import subprocess
import time
import wave
import logging
from collections import deque
from pathlib import Path
from typing import Iterator

import numpy as np
import webrtcvad


class AudioChunker:
    def __init__(
        self,
        device: str | None,
        sample_rate: int,
        chunk_seconds: int,
        out_dir: Path,
        enable_wake_word: bool = False,
        trigger_phrases: list[str] | None = None,
        enable_streaming: bool = True,
    ) -> None:
        self.device = device
        self.sample_rate = sample_rate
        self.chunk_seconds = chunk_seconds
        self.out_dir = out_dir
        self.vad = webrtcvad.Vad(2)  # 0-3: 3 is most aggressive
        self.frame_ms = 30
        self.frame_bytes = int(sample_rate * (self.frame_ms / 1000.0) * 2)  # 16-bit mono
        self.enable_wake_word = enable_wake_word
        self.trigger_phrases = trigger_phrases or []
        self.enable_streaming = enable_streaming
        self.streaming_chunk_seconds = 3  # Emit intermediate chunks every 3 seconds during speech

    def _arecord_cmd(self) -> list[str]:
        cmd = [
            "arecord",
            "-f",
            "S16_LE",
            "-c",
            "1",
            "-r",
            str(self.sample_rate),
            "-t",
            "raw",
            "-q",
        ]
        if self.device:
            cmd.extend(["-D", self.device])
        return cmd

    def _frames(self) -> Iterator[bytes]:
        proc = subprocess.Popen(self._arecord_cmd(), stdout=subprocess.PIPE)
        assert proc.stdout is not None
        try:
            while True:
                data = proc.stdout.read(self.frame_bytes)
                if not data:
                    break
                yield data
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                proc.kill()

    def _write_wav(self, pcm16: bytes, path: Path) -> None:
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(pcm16)

    def run(self) -> Iterator[Path]:
        # Dynamic buffer: expands during speech, fixed size during silence
        active_recording: list[bytes] = []
        silence_buffer = deque(maxlen=int((self.sample_rate * 2 * self.chunk_seconds) / self.frame_bytes))
        
        last_emit = time.time()
        last_speech_time = time.time()
        last_stream_emit = time.time()
        triggered = not self.enable_wake_word  # if wake-word disabled, always record
        silence_threshold = 1.0  # Wait 1 second of silence before finalizing (reduced for speed)
        is_recording_speech = False
        
        for frame in self._frames():
            is_speech = self.vad.is_speech(frame, self.sample_rate)
            
            now = time.time()
            
            # Track when speech was last detected
            if is_speech:
                # Start or continue active recording
                if not is_recording_speech:
                    # Speech started - dump silence buffer into active recording
                    active_recording.extend(list(silence_buffer))
                    is_recording_speech = True
                    last_stream_emit = now
                    logging.debug("speech detected, started active recording")
                
                active_recording.append(frame)
                last_speech_time = now
                silence_buffer.clear()  # Clear silence buffer during speech
                
                # Streaming mode: emit intermediate chunks every 3 seconds while speaking
                if self.enable_streaming and now - last_stream_emit >= self.streaming_chunk_seconds:
                    pcm = b"".join(active_recording)
                    ts = int(now)
                    out_path = self.out_dir / f"audio_{ts}_stream.wav"
                    self._write_wav(pcm, out_path)
                    yield out_path
                    last_stream_emit = now
                    logging.debug("emitted streaming chunk (still speaking)")
                    # Keep recording - don't clear active_recording
            else:
                # No speech - add to silence buffer
                silence_buffer.append(frame)
            
            # Calculate time since last speech
            silence_duration = now - last_speech_time
            
            # Emit when: we have active recording AND 1 second of silence
            if is_recording_speech and silence_duration >= silence_threshold and len(active_recording) > 0:
                # Add the silence buffer (trailing context)
                active_recording.extend(list(silence_buffer))
                
                pcm = b"".join(active_recording)
                ts = int(now)
                out_path = self.out_dir / f"audio_{ts}.wav"
                self._write_wav(pcm, out_path)
                yield out_path
                
                # Reset for next recording
                active_recording.clear()
                silence_buffer.clear()
                is_recording_speech = False
                last_emit = now
                logging.debug("emitted final recording after %.1f sec silence", silence_duration)
            
            # Safety valve: emit if recording gets too long (>5 minutes) even if still talking
            if is_recording_speech and len(active_recording) > (self.sample_rate * 2 * 300) / self.frame_bytes:
                pcm = b"".join(active_recording)
                ts = int(now)
                out_path = self.out_dir / f"audio_{ts}_long.wav"
                self._write_wav(pcm, out_path)
                yield out_path
                active_recording.clear()
                is_recording_speech = False
                last_emit = now
                logging.info("emitted long recording (>5 min), split to avoid memory issues")
