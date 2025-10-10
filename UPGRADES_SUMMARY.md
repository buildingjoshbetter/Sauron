# Major Upgrades: Streaming SMS + Enhanced Vision

## 1. Streaming SMS (Like Texting a Friend)

### Problem:
- 7+ second wait for responses
- Felt like talking to a slow robot

### Solution:
**Real-time SMS streaming** - responses arrive in chunks as they're generated.

**How it works:**
1. You ask: "Hey Sauron, what's the best way to organize my garage?"
2. SAURON starts generating response
3. Every 50 characters OR 1.5 seconds, sends an SMS chunk
4. You get messages like:
   - *[Text 1]:* "Start with zones: tools, storage, workspace."
   - *[Text 2]:* "Pegboard for vertical storage. Clear bins labeled."
   - *[Text 3]:* "Most-used items at eye level."

**Benefits:**
- ✅ Feels **instant** (first text arrives in ~1-2 seconds)
- ✅ Natural conversation flow (like texting a friend)
- ✅ You can start reading while SAURON is still "thinking"
- ✅ Breaks long responses into digestible chunks

**Config:**
- `ENABLE_STREAMING_SMS=true` (default ON)
- Adjust `chunk_size` and `max_wait_time` in code for tuning

---

## 2. Enhanced Computer Vision

### Before:
- ❌ Generic "describe what's happening" prompt
- ❌ Only 3 frames from 10s video (missing context)
- ❌ "Low" detail mode (faster but less accurate)
- ❌ No connection to audio (vision and audio separate)
- ❌ Bland descriptions: "A person is in the room"

### After:
- ✅ **6 frames** (double the context, beginning/middle/end)
- ✅ **High detail mode** (better accuracy, worth the cost)
- ✅ **Audio context integration** (knows what you were just talking about)
- ✅ **SAURON-style analysis** (WHO, WHAT, WHY with insights)
- ✅ Sharp, contextual observations

### Example Comparison:

**Old vision output:**
> "A person is sitting at a desk with a laptop."

**New vision output:**
> "Josh at desk, laptop open, leaning forward with tight posture — focused or stressed. Energy drink on right, third one today. Late-night work session."

### How It Works:

1. **Motion detected** → captures 10s video
2. **Extracts 6 frames** (evenly spaced)
3. **Pulls recent audio context** (last 3 user messages)
4. **Sends to GPT-4o Vision** with SAURON-style prompt:
   - WHO: identity, body language, emotional state
   - WHAT: actions, interactions, objects in use
   - WHY: context, patterns, notable details
   - Audio context: "Josh was just talking about being tired"
5. **Gets sharp, contextual analysis**
6. **Stores text description** in memory (deletes video/frames)

### Cost Impact:
- High detail mode: ~$0.02 per motion event (vs $0.005 for low)
- But: **much better** observations and insights
- You're running 1-2 motion events per day, so ~$0.60/month max

### Examples of Better Observations:

**Without audio context:**
> "Josh holding a screwdriver, working on a small device."

**With audio context** (recent: "I can't figure out why this drone won't arm"):
> "Josh troubleshooting drone ESC wiring with multimeter. Frustration evident — third attempt at same connection. Battery disconnect suggests reset strategy."

---

## Deploy:

```bash
# On Pi
cd /home/pi/Sauron
git pull
sudo systemctl restart sauron

# Test streaming SMS:
# Say: "Hey Sauron, explain quantum computing to me"
# Watch texts arrive in real-time!
```

## Tuning:

### Streaming SMS Speed:
Edit `src/main.py` line 305-306:
```python
chunk_size=50,  # Lower = faster, more texts (e.g., 30)
max_wait_time=1.5,  # Lower = faster bursts (e.g., 1.0)
```

### Vision Frame Count:
Edit `src/computer_vision.py` line 37:
```python
def extract_frames(video_path: Path, num_frames: int = 6):  # Increase to 8-10 for more context
```

### Vision Detail Level:
Edit `src/computer_vision.py` line 109:
```python
"detail": "high"  # Options: "low", "high", "auto"
```

---

## What's Next:

Potential future enhancements:
1. **Proactive insights** ("Josh looks exhausted, third late night this week")
2. **Object tracking** ("That's the 4th beer tonight")
3. **Pattern recognition** ("Usually works out at 7am, missed 3 days")
4. **Facial expression analysis** (stress, focus, frustration)
5. **Multi-camera** (track Josh throughout home)

Let me know what you want to prioritize! 🎯

