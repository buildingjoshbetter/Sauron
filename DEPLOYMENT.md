# SAURON Deployment Guide

## Complete Setup

### 1. Deploy Latest Code

**On your Mac:**
```bash
cd /Users/j/Documents/GitHub/Sauron
git add -A
git commit -m "Add daily summarization and auto-start"
git push
```

**On the Pi:**
```bash
ssh pi@192.168.4.62
cd /home/pi/Sauron
git pull
source .venv/bin/activate
pip install -r requirements.txt  # If any new dependencies
```

### 2. Install SystemD Service (Auto-Start on Boot)

```bash
cd /home/pi/Sauron
chmod +x deploy/install-service.sh
./deploy/install-service.sh
```

This will:
- Install SAURON as a system service
- Configure auto-start on Pi boot
- Start the service immediately

### 3. Verify Service is Running

```bash
# Check status
sudo systemctl status sauron

# View live logs
tail -f /home/pi/sauron_data/logs/sauron.log

# View error logs
tail -f /home/pi/sauron_data/logs/sauron_error.log
```

### 4. Service Management Commands

```bash
# Stop SAURON
sudo systemctl stop sauron

# Start SAURON
sudo systemctl start sauron

# Restart SAURON (after code updates)
sudo systemctl restart sauron

# Disable auto-start
sudo systemctl disable sauron

# Re-enable auto-start
sudo systemctl enable sauron

# View recent logs
journalctl -u sauron -n 100 --no-pager
```

## Storage Management

### Daily Summarization

SAURON now automatically:
- **Keeps raw files for 24 hours** (audio + images)
- **Summarizes everything at 3 AM daily**
- **Deletes old raw files** after summarization
- **Stores summaries forever** (text only, minimal space)

### Storage Breakdown

**Active files (rolling 24 hours):**
- Audio: ~1-5 GB/day (deleted after 24h)
- Images: ~150-600 MB/day (deleted after 24h)
- Total active: ~1-6 GB

**Archived summaries (kept forever):**
- Daily transcript summaries: ~5-50 KB/day
- Daily image summaries: ~5-20 KB/day
- Total per month: ~300 KB - 2 MB
- **1 year = ~4-24 MB of summaries**

**64 GB SD card can store:**
- ~10 days of raw files continuously
- ~100+ years of summaries

### Summary Files

Located in `/home/pi/sauron_data/daily_summaries/`:
- `transcripts_2025-10-09.json` - What you said that day
- `images_2025-10-09.json` - What was seen that day

### Manual Cleanup (if needed)

```bash
# View storage usage
du -sh /home/pi/sauron_data/*

# Manually trigger daily cleanup
cd /home/pi/Sauron
source .venv/bin/activate
python3 -c "from src.summarization import run_daily_cleanup; from src.config import load_config; from src.memory import MemorySystem; from pathlib import Path; conf = load_config(); mem = MemorySystem(conf.data_dir); run_daily_cleanup(conf.data_dir, conf.openrouter_api_key, conf.openrouter_model, mem)"
```

## Testing

### Test Auto-Start
```bash
# Reboot Pi
sudo reboot

# After reboot, check if SAURON started
sudo systemctl status sauron
tail -f /home/pi/sauron_data/logs/sauron.log
```

### Test Daily Summarization

```bash
# Check if summaries exist
ls -lh /home/pi/sauron_data/daily_summaries/

# View a summary
cat /home/pi/sauron_data/daily_summaries/transcripts_2025-10-09.json | jq '.summary'
```

## Updating Code

After making changes:

**On your Mac:**
```bash
git add -A
git commit -m "Your changes"
git push
```

**On the Pi:**
```bash
cd /home/pi/Sauron
git pull
sudo systemctl restart sauron
```

## Troubleshooting

### Service Won't Start
```bash
# Check detailed logs
journalctl -u sauron -n 50 --no-pager

# Check .env file exists
ls -la /home/pi/Sauron/.env

# Check venv exists
ls -la /home/pi/Sauron/.venv/bin/python3
```

### High Storage Usage
```bash
# Check what's using space
du -sh /home/pi/sauron_data/*

# Force cleanup of old files
find /home/pi/sauron_data/audio -name "*.wav" -mtime +1 -delete
find /home/pi/sauron_data/images -name "*.jpg" -mtime +1 -delete
```

### Memory Issues
```bash
# Check memory usage
free -h

# Restart service to clear memory
sudo systemctl restart sauron
```

## What Happens at 3 AM Daily

1. **Transcript Summarization**
   - Collects all user messages from yesterday
   - Generates LLM summary
   - Stores in `daily_summaries/transcripts_YYYY-MM-DD.json`
   - Deletes audio files >24h old

2. **Image Summarization**
   - Collects all motion events from yesterday
   - Generates LLM summary
   - Stores in `daily_summaries/images_YYYY-MM-DD.json`
   - Deletes image files >24h old

3. **Result**
   - SD card stays under ~6 GB
   - Full history preserved as text
   - No manual cleanup needed

---

**SAURON is now fully autonomous** - starts on boot, runs forever, manages its own storage.

