# SAURON Forever Memory System

## Overview
SAURON now has **unlimited contextual memory** spanning months or even years, with a **3-tier hierarchical architecture** that optimizes for both speed and depth. The system automatically cascades through tiers to find the perfect balance between recall speed and historical depth.

## 3-Tier Memory Architecture

### **Tier 1: Local Fast Cache (Raspberry Pi SD Card)**
📍 **Location**: `/home/pi/sauron_data/tier1_cache/`  
⚡ **Speed**: ~0.5 seconds  
💾 **Size**: 10-15GB (10-25% of SD card)  
📊 **Contents**:
- Last 7 days of high-detail summaries
- Last 1000 conversation messages
- 500 most recent facts
- Active vision events

**Use case**: Quick recall of recent events  
*"What did I say this morning about the project?"*

### **Tier 2: NAS Medium Detail**
📍 **Location**: `/mnt/nas/sauron/tier2_medium/`  
⚡ **Speed**: ~2 seconds  
💾 **Size**: ~50GB  
📊 **Contents**:
- Last 3 months of medium-detail summaries
- Full conversation history (all messages)
- All facts (10,000+)
- Daily vision summaries

**Use case**: Moderate-depth recall  
*"Remind me what we discussed last week about Whisper"*

### **Tier 3: NAS Deep Archive**
📍 **Location**: `/mnt/nas/sauron/tier3_deep/`  
⚡ **Speed**: ~5-10 seconds  
💾 **Size**: Unlimited  
📊 **Contents**:
- Full history (years of data)
- Highly compressed summaries (10x compression)
- Raw audio/video archives
- Long-term patterns and trends

**Use case**: Deep historical search  
*"What was that funny TV show quote from 4 months ago?"*

---

## How It Works

### 1. **Real-Time Storage (SD Card)**
- Audio chunks: Stored locally for 24 hours
- Images: Stored locally for 24 hours  
- Videos: Analyzed and deleted immediately (descriptions kept)
- Conversation history: Active working memory

### 2. **Daily Archival (3 AM)**
Every night at 3 AM, SAURON:
- **Summarizes** yesterday's transcripts using LLM
- **Archives** raw audio/video files to NAS (`/mnt/nas/sauron/audio_archive/`)
- **Consolidates** vision events into daily summaries
- **Preserves** all raw data forever on NAS
- **Stores** summaries in searchable format

### 3. **Emergency Cleanup (70% SD Card)**
When local storage hits 70%:
- **Archives** files older than 12 hours to NAS
- **Frees** up local space automatically
- **Sends SMS** notification: "Storage cap reached. Archived N files to NAS."
- Runs every 30 minutes

### 4. **Smart Retrieval**
When you ask SAURON to recall something:
```
"Atlas, remind me what Tim said on the TV show last week"
```

SAURON will:
1. Classify as **ultra-complex** query
2. Send instant ack: "Pulling from memory..."
3. Search through:
   - Active conversation (last 50 messages)
   - Daily summaries (last 7 days on NAS)
   - Archived transcripts (stored forever)
4. Return answer with full context

## Storage Layout

### SD Card (`/home/pi/sauron_data/`)
```
audio/              # Last 24 hours only
images/             # Last 24 hours only
video/              # Temporary (deleted after analysis)
logs/               # System logs
```

### NAS (`/mnt/nas/sauron/`)
```
conversation.json           # Full conversation history
facts.json                  # Extracted facts (people, preferences, plans)
summaries.json              # Rolling summaries
daily_summaries/
  ├── transcripts_2025-10-10.json
  ├── transcripts_2025-10-11.json
  ├── vision_2025-10-10.json
  └── ...
audio_archive/
  ├── 2025-10-10/
  │   ├── audio_1760138924.wav
  │   └── audio_1760138930.wav
  └── emergency/          # Files from emergency cleanup
video_archive/
  ├── 2025-10-10/
  │   ├── img_1234567.jpg
  │   └── motion_1234567.h264
  └── emergency/
```

## Memory Capabilities

### What SAURON Can Recall:
✅ **Conversations** - Every word you've said to it  
✅ **Overheard audio** - TV shows, phone calls, background conversations  
✅ **Visual events** - Who walked by, what you were holding, motion patterns  
✅ **Temporal context** - "What did I say last Tuesday?"  
✅ **Semantic search** - "That funny joke Tim made" → finds it across thousands of transcripts

### Example Queries:
```
"Atlas, what did I mention about the Raspberry Pi project 3 weeks ago?"
→ Searches daily summaries from 3 weeks ago

"Atlas, remind me of that TV show quote - something about 'courage'?"
→ Searches all transcripts for keyword "courage"

"Atlas, what time did I usually go to bed last month?"
→ Analyzes patterns from daily summaries
```

## Technical Details

### Summarization Model
- Uses **GPT-4o-mini** for daily summaries (fast + cheap)
- Extracts key activities, topics, patterns, notable events
- Preserves important details while reducing volume 10x

### Fact Extraction
Automatically detects and stores:
- **Names** - "My name is...", "I'm Josh"
- **Projects** - Mentions of "project", "building", "working on"
- **Preferences** - "I like", "I prefer", "I hate"
- **Plans** - "I'm going to", "planning to"
- **Significant statements** - "I learned", "I realized", "I finished"

### Context Window Scaling
- **Simple queries** - 5 recent messages
- **Medium queries** - 15 recent messages
- **Complex queries** - 30 recent messages + memory summary
- **Ultra queries** - 50 recent messages + full memory summary + semantic search

## Future Enhancements

### Phase 2 (Coming Soon):
- **TV show detection** - Distinguish media from real conversations
- **Importance ranking** - Prioritize critical memories over background noise
- **Multi-device sync** - Share memory across 6-10 SAURON units
- **Voice search** - "Play the audio from when I said..."
- **Visual timeline** - Browse snapshots by date/event

### Phase 3 (Future):
- **Embedding-based search** - True semantic search using vector DB
- **Auto-tagging** - Categorize events (work, personal, entertainment)
- **Proactive insights** - "You usually call mom on Sundays, but you didn't today"
- **Export to other apps** - Calendar events, notes, reminders

## Storage Estimates

### Example Daily Usage:
- **Audio**: ~2GB (24 hours @ 16kHz)
- **Images**: ~100MB (50 snapshots @ 2MB each)
- **Transcripts**: ~1MB (text)
- **After summarization**: ~0.1MB (90% reduction)

### 64GB SD Card:
- **Active storage**: Up to 48GB used (70% cap)
- **Lifespan**: ~24 days before emergency cleanup
- **NAS storage**: Unlimited (grows ~0.1GB per day after summarization)

### 1TB NAS:
- **Raw archives**: ~2GB/day = ~500 days of raw audio/video
- **Summaries**: ~0.1GB/day = ~10,000 days (27 years) of summarized data

## Configuration

### `.env` Settings:
```bash
# NAS storage paths
MEMORY_DIR=/mnt/nas/sauron              # Long-term memory
NAS_ARCHIVE_DIR=/mnt/nas/sauron        # Raw file archives

# Storage management
DATA_DIR=/home/pi/sauron_data           # Local SD card
# (70% cap is hardcoded, can be made configurable)
```

### Manual Cleanup:
```bash
# Force daily cleanup (usually runs at 3 AM)
python3 -m src.summarization

# Check storage usage
df -h /home/pi/sauron_data

# View archived files on NAS
ls -lh /mnt/nas/sauron/audio_archive/
```

## Troubleshooting

### "Storage cap reached" SMS spam:
- Check if NAS is mounted: `mount | grep /mnt/nas`
- Verify NAS has space: `df -h /mnt/nas`
- Check emergency archive dir exists

### Can't recall old conversations:
- Verify NAS is mounted and accessible
- Check daily summaries exist: `ls /mnt/nas/sauron/daily_summaries/`
- Ensure cleanup worker is running: `systemctl status sauron`

### Slow recall queries:
- Normal! Ultra-complex queries search months of data
- Acknowledgment SMS sent instantly to show progress
- Typical time: 5-10 seconds for deep memory search

---

**Next Steps**: Test with a query like "Atlas, what did we discuss about Whisper yesterday?" and watch it pull from NAS! 🎯

