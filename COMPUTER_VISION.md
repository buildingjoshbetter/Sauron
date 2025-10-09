# SAURON Computer Vision System

## Overview

SAURON now has **full computer vision** with video capture and AI analysis.

## How It Works

### **Passive Mode (Always Running)**
1. **Motion detected** (person/pet moving)
2. **Captures 10-second video** automatically
3. **Analyzes with GPT-4o Vision** (3 frames from video)
4. **Stores description in memory** silently
5. **Deletes video** after analysis
6. **No SMS sent** - just logged

### **Active Mode (When You Ask)**
1. You ask: **"What am I holding?"** or **"What am I doing?"**
2. SAURON sends SMS: **"Gimme a sec while I analyze..."**
3. Pulls recent vision observations from memory
4. Sends actual answer via SMS

## Example Workflow

### Silent Observation:
```
[15:30] Motion detected
→ Records 10-sec video
→ GPT-4o Vision: "Person entered frame carrying laptop bag, walked toward desk, sat down"
→ Stored in memory as: vision_20251009_153045
→ No SMS sent

[15:45] Motion detected
→ Records 10-sec video
→ GPT-4o Vision: "Person standing at whiteboard, gesturing while talking on phone"
→ Stored in memory
→ No SMS sent
```

### When You Ask:
```
You: "What was I doing earlier?"
→ SAURON sends: "Gimme a sec while I analyze..."
→ Searches vision memory
→ SAURON sends: "You came in with your laptop at 3:30, then were on a call at the whiteboard at 3:45."
```

## Vision-Specific Questions

These trigger vision analysis:
- "What am I holding?"
- "What do you see?"
- "What does it look like?"
- "What am I doing?"
- "What's happening?"
- "Who is here?"
- "Who's in the room?"
- "Describe what..."
- "Can you see...?"

## Technical Details

### Video Capture:
- **Duration**: 10 seconds (configurable via `VIDEO_DURATION_SECONDS`)
- **Resolution**: 640x480 (matches camera config)
- **Format**: H.264
- **Trigger**: Motion score >= threshold

### AI Analysis:
- **Model**: GPT-4o Vision (OpenAI)
- **Frames analyzed**: 3 frames (beginning, middle, end of video)
- **Speed**: 2-5 seconds per video
- **Cost**: ~$0.01 per video analysis

### Storage:
- **Video files**: Deleted after analysis (kept ~1 minute)
- **Vision descriptions**: Stored in memory forever
- **Daily summaries**: All vision events summarized at 3 AM

### Memory Format:
```json
{
  "vision_20251009_153045": "[2025-10-09T15:30:45] Vision: Person entered carrying laptop, sat at desk",
  "vision_20251009_154512": "[2025-10-09T15:45:12] Vision: Person on phone call at whiteboard, gesturing"
}
```

## Configuration (.env)

```env
# Enable video capture on motion
ENABLE_VIDEO_ON_MOTION=true

# Video duration in seconds
VIDEO_DURATION_SECONDS=10

# Vision still uses same camera settings
CAMERA_SNAPSHOT_WIDTH=640
CAMERA_SNAPSHOT_HEIGHT=480
```

## Storage Impact

**Without video:**
- Images: ~150-600 MB/day (deleted after 24h)

**With video analysis:**
- Videos: 0 MB (deleted after analysis)
- Vision descriptions: ~10-50 KB/day (text only, kept forever)

**No storage impact** - videos are immediately deleted after GPT-4o analyzes them.

## System Requirements

### New Dependencies:
```bash
sudo apt install -y ffmpeg ffprobe
```

Already in requirements.txt - no Python packages needed (uses OpenAI API).

## Deployment

```bash
# On Pi:
ssh pi@192.168.4.62
cd /home/pi/Sauron && git pull

# Install ffmpeg
sudo apt install -y ffmpeg

# Update .env
nano .env
```

Add:
```env
ENABLE_VIDEO_ON_MOTION=true
VIDEO_DURATION_SECONDS=10
```

Restart:
```bash
sudo systemctl restart sauron
tail -f /home/pi/sauron_data/logs/sauron.log
```

## Usage Examples

### Passive (Automatic):
```
[Motion detected]
→ Video captured and analyzed silently
→ Stored in memory: "Cat jumped on counter, knocked over cup"
→ You receive no notification
```

### Active (When Asked):
```
You: "What did my cat do today?"
SMS: "Gimme a sec while I analyze..."
SMS: "Jumped on the counter at 2:15 PM and knocked over a cup."

You: "What am I holding right now?"
SMS: "Gimme a sec while I analyze..."
SMS: "Can't see current frame - last motion was 10 minutes ago. Ask again after moving."

You: "Who came by earlier?"
SMS: "Gimme a sec while I analyze..."
SMS: "No people detected today. Just your cat being chaotic."
```

## What SAURON Sees

GPT-4o Vision provides:
- ✅ **Object identification** (laptop, phone, cup, etc.)
- ✅ **People recognition** (person, multiple people - no face ID)
- ✅ **Actions** (walking, sitting, gesturing, carrying)
- ✅ **Context** (time of day, room state)
- ✅ **Relationships** (person with object, pet on furniture)

## Privacy Note

- Videos are **never stored** (deleted within 1 minute)
- Only text descriptions kept
- GPT-4o Vision sees frames but doesn't store them
- All processing is for your memory only

---

**SAURON can now see.** It watches silently, analyzes everything, and tells you what happened only when you ask.

