# SAURON Complete Verification Checklist

## All Changes Made in Last 24 Hours

---

## 1. ✅ Audio System

### **Dynamic Buffer (Long Conversations)**
- ✅ Captures full conversations (no 10-second cutoff)
- ✅ Expands during speech (up to 5 minutes)
- ✅ Waits 1 second of silence before finalizing
- ✅ Includes leading/trailing context

**Verify:**
```bash
# On Pi, watch logs
tail -F /home/pi/sauron_data/logs/sauron.log

# Speak for 30+ seconds straight
# Should see ONE audio chunk after you stop (not multiple)
```

**Expected log:**
```
speech detected, started active recording
emitted final recording after 1.X sec silence
audio chunk: /home/pi/sauron_data/audio/audio_XXXXX.wav
```

---

### **Streaming Transcription**
- ✅ Emits intermediate chunks every 3 seconds while speaking
- ✅ Final chunk emitted after 1 second silence
- ✅ Deduplication to avoid processing same audio twice

**Verify:**
```bash
# Speak for 10+ seconds
# Watch for _stream.wav files in logs
```

**Expected:**
```
emitted streaming chunk (still speaking)
audio chunk: /home/pi/sauron_data/audio/audio_XXXXX_stream.wav
streaming transcript (partial): your text...
emitted final recording after 1.0 sec silence
audio chunk: /home/pi/sauron_data/audio/audio_XXXXX.wav
final transcript (after streaming): your full text
```

---

## 2. ✅ Transcription Speed

### **Priority System**
1. NAS Whisper (if configured): 0.1-0.5s
2. Local Whisper (if enabled): 0.5-2s
3. OpenAI API (fallback): 2-5s

**Current config** (without NAS):
- Using OpenAI API: 2-5 seconds

**Verify:**
```bash
# Check .env
grep -E "NAS_WHISPER_URL|USE_LOCAL_WHISPER" /home/pi/Sauron/.env
```

**Should show:**
```
USE_LOCAL_WHISPER=false
# NAS_WHISPER_URL not set (commented or absent)
```

---

## 3. ✅ Personality & Profile

### **Josh's Profile Loaded**
- ✅ Name, age, personality traits
- ✅ ADHD work style
- ✅ Communication preferences
- ✅ Interests, projects, expectations

**Verify:**
```bash
# Check facts file (on SD card for now, will be on NAS later)
cat /home/pi/sauron_data/facts.json | jq '.user_name, .user_personality, .user_adhd'
```

**Expected:**
```json
"Josh Adler, 26, engineer and entrepreneur"
"Direct, analytical, impatient with inefficiency..."
"Highly ADHD - fast context switching..."
```

---

### **Personality Tone**
- ✅ Direct, confident, slightly sardonic
- ✅ Sparring partner (not servant)
- ✅ Matches your energy (swears if you swear)
- ✅ No mythical SAURON roleplay
- ✅ Practical and helpful

**Verify:**
```bash
# Ask a question and check response tone
# Say: "What time is it?"
```

**Good response:**
```
"It's 3:47 PM."
or
"3:47 PM."
```

**Bad response (if this happens, personality not loaded):**
```
"Mortal, the time is..."
or
"The all-seeing eye observes it is..."
```

---

## 4. ✅ Contextual Memory

### **Photographic Memory**
- ✅ Stores ALL transcripts (questions + overheard)
- ✅ Semantic search through entire history
- ✅ Recalls mentions from weeks/months ago
- ✅ 500 facts stored with timestamps
- ✅ Persistent across reboots

**Verify:**
```bash
# Check conversation history
cat /home/pi/sauron_data/conversation.json | jq '.messages | length'

# Check facts
cat /home/pi/sauron_data/facts.json | jq 'keys | length'
```

**Expected:**
```
X (number of messages stored)
10+ (user profile facts + any extracted facts)
```

**Test:**
```bash
# Say something like: "I'm working on a new drone project"
# Wait for it to be transcribed (check logs)
# Then say: "What project did I mention?"
# Should recall the drone project
```

---

## 5. ✅ Question Detection & SMS Filtering

### **Sends SMS Only For:**
- ✅ Starts with question words (what, when, where, who, why, how)
- ✅ Contains "?"
- ✅ Starts with trigger phrases (hey sauron, ok sauron)
- ✅ At least 3 words long
- ✅ Not repeated words (filters "you you you")

**Verify:**
```bash
# Test cases:

# Should send SMS:
"What time is it?"
"How's the weather?"
"Should I start the project?"

# Should NOT send SMS:
"I'm thinking about stuff" (no question)
"um okay" (too short)
"you you" (repeated words)
```

**Check logs for:**
```
transcript: I'm thinking about stuff
not a clear question, skipping SMS
```

---

## 6. ✅ Computer Vision

### **Silent Observation**
- ✅ Motion detected → captures 10-sec video
- ✅ Analyzes with GPT-4o Vision
- ✅ Stores description in memory
- ✅ Deletes video immediately
- ✅ NO SMS sent

**Verify:**
```bash
# Wave in front of camera
# Watch logs

# Should see:
motion detected: score=0.XX path=/home/pi/sauron_data/images/img_XXXXX.jpg
capturing video for motion event (score 0.XX)
vision analysis complete: Person waving at camera...
stored vision event in memory: Person waving...

# Should NOT see SMS sent
```

---

### **Vision Questions**
- ✅ Detects vision-specific questions
- ✅ Sends "Gimme a sec while I analyze..." first
- ✅ Then sends actual vision answer

**Verify:**
```bash
# After waving (from above), ask:
"What am I doing?"

# Should see in logs:
sent analyzing SMS for vision question
# Then later:
sms sent: [actual description]
```

**Your phone should get TWO texts:**
1. "Gimme a sec while I analyze..."
2. "You were waving at the camera."

---

## 7. ✅ Motion Detection (No Lighting False Positives)

### **Improved Detection**
- ✅ Filters out light switches
- ✅ Detects localized motion only
- ✅ Sensitivity: 0.08 (catches people/pets, ignores lighting)

**Verify:**
```bash
# Test 1: Turn lights on/off
# Should NOT trigger motion (or very low score)

# Test 2: Wave at camera
# Should trigger motion (score > 0.08)
```

**Check logs:**
```
# Light switch - should see low score or nothing:
motion detected: score=0.02 (below threshold, not logged)

# Person waving - should see:
motion detected: score=0.15 path=...
```

---

## 8. ✅ Storage Management

### **SD Card (Local)**
- ✅ Audio: Kept 24 hours
- ✅ Images: Kept 24 hours
- ✅ Videos: Deleted after analysis
- ✅ Max storage: ~1-6 GB

**Verify:**
```bash
# Check current usage
du -sh /home/pi/sauron_data/*
```

**Expected:**
```
~1-3 GB   /home/pi/sauron_data/audio
~100-500 MB   /home/pi/sauron_data/images
~1-10 MB   /home/pi/sauron_data/video (mostly empty, files deleted quickly)
```

---

### **Daily Cleanup (3 AM)**
- ✅ Summarizes transcripts
- ✅ Summarizes vision events
- ✅ Archives to NAS (when mounted)
- ✅ Deletes old files

**Verify (after 3 AM):**
```bash
ls -lh /home/pi/sauron_data/daily_summaries/
# or if NAS mounted:
ls -lh /mnt/nas/sauron/daily_summaries/
```

---

## 9. ✅ Auto-Start on Boot

**Verify:**
```bash
sudo systemctl is-enabled sauron
```

**Should show:**
```
enabled
```

**Test:**
```bash
# Reboot Pi
sudo reboot

# Wait 30 seconds, reconnect
ssh pi@192.168.4.62

# Check if SAURON started automatically
sudo systemctl status sauron
```

**Should show:** `Active: active (running)`

---

## 10. ✅ Built-in Tools

### **Time**
**Say:** "What time is it?"

**Expected SMS:**
```
It's 3:47 PM PST.
```

### **Weather**
**Say:** "What's the weather?"

**Expected SMS:**
```
12°C, feels 10°C, RH 65%, wind 3 m/s.
```

**Verify in .env:**
```bash
grep -E "LATITUDE|LONGITUDE|TIMEZONE" /home/pi/Sauron/.env
```

**Should show:**
```
LATITUDE=37.7749
LONGITUDE=-122.4194
TIMEZONE=America/Los_Angeles
```

---

## 11. ✅ Fast LLM

**Verify:**
```bash
grep OPENROUTER_MODEL /home/pi/Sauron/.env
```

**Should show:**
```
OPENROUTER_MODEL=meta-llama/llama-3.1-8b-instruct
```

**Not:**
```
OPENROUTER_MODEL=openai/gpt-4o-mini
```

---

## 12. ✅ Audio Device Settings

**Verify:**
```bash
grep AUDIO_DEVICE /home/pi/Sauron/.env
```

**Should show:**
```
AUDIO_DEVICE=plughw:1,0
```

**Not:**
```
AUDIO_DEVICE=hw:1,0
```

---

## Quick Verification Script

**Run this on Pi:**
```bash
cat << 'EOF' | bash
echo "=== SAURON Verification ==="
echo ""
echo "1. Service Status:"
sudo systemctl is-active sauron
echo ""
echo "2. Auto-start:"
sudo systemctl is-enabled sauron
echo ""
echo "3. LLM Model:"
grep OPENROUTER_MODEL /home/pi/Sauron/.env
echo ""
echo "4. Audio Device:"
grep AUDIO_DEVICE /home/pi/Sauron/.env
echo ""
echo "5. Location Set:"
grep -E "LATITUDE|LONGITUDE" /home/pi/Sauron/.env
echo ""
echo "6. Memory Files:"
ls -lh /home/pi/sauron_data/*.json 2>/dev/null || echo "No memory files yet"
echo ""
echo "7. Storage Usage:"
du -sh /home/pi/sauron_data/* 2>/dev/null
echo ""
echo "=== End Verification ==="
EOF
```

**This will show you everything at once.**

---

## **All Features Should Work:**

1. ✅ Listens continuously
2. ✅ Captures long conversations (no cutoff)
3. ✅ Filters out bad transcripts
4. ✅ Only texts on real questions
5. ✅ Remembers everything forever
6. ✅ Vision analysis on motion
7. ✅ Knows your personality
8. ✅ Fast responses (with proper tone)
9. ✅ Auto-starts on boot
10. ✅ Manages storage automatically

**Run the verification script above to check everything at once!**
