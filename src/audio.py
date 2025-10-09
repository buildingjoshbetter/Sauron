import os
import subprocess
import time
import wave
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
        ring = deque(maxlen=int((self.sample_rate * 2 * self.chunk_seconds) / self.frame_bytes))
        speech_frames: list[bytes] = []
        last_emit = time.time()
        last_speech_time = time.time()
        triggered = not self.enable_wake_word  # if wake-word disabled, always record
        silence_threshold = 2.0  # Wait 2 seconds of silence before finalizing
        
        for frame in self._frames():
            is_speech = self.vad.is_speech(frame, self.sample_rate)
            ring.append(frame)
            
            now = time.time()
            
            # Track when speech was last detected
            if is_speech:
                speech_frames.append(frame)
                last_speech_time = now
            
            # Calculate time since last speech
            silence_duration = now - last_speech_time
            
            # If wake-word mode and not triggered, check for trigger every chunk
            if self.enable_wake_word and not triggered and now - last_emit >= self.chunk_seconds:
                # Quick transcription check (local or via API) - for now, emit and check in consumer
                pcm = b"".join(ring)
                ts = int(now)
                out_path = self.out_dir / f"audio_{ts}_wake.wav"
                self._write_wav(pcm, out_path)
                yield out_path
                last_emit = now
                speech_frames.clear()
            # Only emit if: enough time passed AND user has been silent for 2 seconds
            elif (triggered or not self.enable_wake_word) and now - last_emit >= self.chunk_seconds and silence_duration >= silence_threshold:
                pcm = b"".join(ring)
                ts = int(now)
                out_path = self.out_dir / f"audio_{ts}.wav"
                self._write_wav(pcm, out_path)
                yield out_path
                last_emit = now
                speech_frames.clear()
