import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image


@dataclass
class MotionResult:
    image_path: Path
    motion_score: float


def capture_snapshot(width: int, height: int, out_path: Path) -> None:
    cmd = [
        "libcamera-still",
        "-t",
        "1",
        "--width",
        str(width),
        "--height",
        str(height),
        "-o",
        str(out_path),
        "-n",
    ]
    subprocess.run(cmd, check=False)


def compute_motion(prev_img: Optional[Image.Image], curr_img: Image.Image) -> float:
    if prev_img is None:
        return 0.0
    a = np.array(prev_img.convert("L"), dtype=np.float32)
    b = np.array(curr_img.convert("L"), dtype=np.float32)
    h = min(a.shape[0], b.shape[0])
    w = min(a.shape[1], b.shape[1])
    a = a[:h, :w]
    b = b[:h, :w]
    
    # Calculate absolute difference
    diff = np.abs(a - b)
    
    # Threshold: only count pixels that changed significantly (>30 out of 255)
    motion_mask = diff > 30
    
    # Count how many pixels had significant change
    motion_pixels = motion_mask.sum()
    total_pixels = motion_mask.size
    
    # Motion score = percentage of pixels with significant change
    motion_score = float(motion_pixels / total_pixels)
    
    # Additional filter: check if motion is localized (not global lighting)
    # Divide image into grid and count active regions
    grid_h, grid_w = 8, 8  # 8x8 grid
    cell_h = h // grid_h
    cell_w = w // grid_w
    
    active_regions = 0
    for i in range(grid_h):
        for j in range(grid_w):
            cell = motion_mask[i*cell_h:(i+1)*cell_h, j*cell_w:(j+1)*cell_w]
            # If >20% of pixels in this cell changed, count as active region
            if cell.sum() > (cell.size * 0.2):
                active_regions += 1
    
    # Lighting changes affect most regions (>50%), motion is localized (<50%)
    total_regions = grid_h * grid_w
    if active_regions > total_regions * 0.5:
        # Likely global lighting change, heavily penalize
        return motion_score * 0.3
    
    return motion_score


def motion_watchdog(
    out_dir: Path,
    width: int,
    height: int,
    threshold: float,
    interval_seconds: int = 10,
):
    prev: Optional[Image.Image] = None
    while True:
        ts = int(time.time())
        out_path = out_dir / f"img_{ts}.jpg"
        capture_snapshot(width, height, out_path)
        try:
            curr = Image.open(out_path)
        except Exception:
            time.sleep(interval_seconds)
            continue
        score = compute_motion(prev, curr)
        # Always yield result (for cleanup tracking), even if no motion
        yield MotionResult(image_path=out_path, motion_score=score)
        prev = curr
        time.sleep(interval_seconds)
