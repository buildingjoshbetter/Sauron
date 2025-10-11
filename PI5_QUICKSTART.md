# Raspberry Pi 5 Quick Start Guide

## Prerequisites
- Raspberry Pi 5 (8GB or 16GB RAM)
- 64GB SD card (flashed with Raspberry Pi OS 64-bit Bookworm)
- USB Microphone (Blue Yeti Nano, Samson Go, etc.)
- ArduCam 12MP camera module
- Power supply

## Step-by-Step Setup

### 1. Flash SD Card (5 minutes)
1. Download **Raspberry Pi Imager**: https://www.raspberrypi.com/software/
2. Choose:
   - **OS:** Raspberry Pi OS (64-bit) - Bookworm
   - **Storage:** Your SD card
3. Configure (gear icon):
   - ✅ Enable SSH
   - ✅ Username: `pi`
   - ✅ Set password
   - ✅ Configure WiFi (optional)
   - ✅ Hostname: `sauron-pi5`
4. **Write** and wait

### 2. Boot Pi 5 and SSH In (2 minutes)
```bash
# From your Mac
ssh pi@sauron-pi5.local
# Or use IP: ssh pi@192.168.x.x
```

### 3. Clone Repository (1 minute)
```bash
cd ~
git clone https://github.com/buildingjoshbetter/Sauron.git
cd Sauron
```

### 4. Create .env File (2 minutes)
```bash
# Copy template
cp ENV_PI5_TEMPLATE.txt .env

# Edit with your API keys
nano .env
```

Update these fields:
- `OPENROUTER_API_KEY` - Get from https://openrouter.ai/keys
- `OPENAI_API_KEY` - Get from https://platform.openai.com/api-keys
- `TWILIO_ACCOUNT_SID` - From Twilio console
- `TWILIO_AUTH_TOKEN` - From Twilio console
- `TWILIO_FROM_NUMBER` - Your Twilio phone number
- `TWILIO_TO_NUMBER` - Your personal phone number

Save with `Ctrl+X`, `Y`, `Enter`

### 5. Find USB Mic Device (1 minute)
```bash
arecord -l
```

You'll see something like:
```
card 1: Microphone [USB Microphone], device 0: USB Audio [USB Audio]
```

Update `AUDIO_DEVICE` in `.env`:
```bash
AUDIO_DEVICE=plughw:1,0  # Use the card number you see
```

### 6. Run Setup Script (7 minutes)
```bash
chmod +x setup-pi5.sh
./setup-pi5.sh
```

This will:
- ✅ Install all dependencies
- ✅ Set up Python virtual environment
- ✅ Install Whisper (medium model) - **THIS TAKES ~5 MINUTES**
- ✅ Configure camera
- ✅ Set up systemd service

### 7. Start SAURON (30 seconds)
```bash
sudo systemctl start sauron
```

### 8. Watch Logs
```bash
tail -F ~/sauron_data/logs/sauron.log
```

### 9. Test It!
Say: **"Hey Atlas, what's 2 plus 2?"**

You should see:
- Fast transcription (2-3 seconds)
- SMS response from Claude

---

## Troubleshooting

### Mic Not Working
```bash
# Test mic
arecord -D plughw:1,0 -d 5 -f S16_LE -r 16000 test.wav
aplay test.wav

# List devices again
arecord -l
```

### Camera Not Working
```bash
# Test camera
libcamera-hello --list-cameras
libcamera-still -o test.jpg
```

### Service Not Starting
```bash
# Check status
sudo systemctl status sauron

# Check errors
journalctl -u sauron -n 50
```

### Whisper Model Download Failed
```bash
# Manually download
source .venv/bin/activate
python -c "import whisper; whisper.load_model('medium')"
```

---

## Performance Expectations

### Pi 5 (16GB) + USB Mic + Local Whisper Medium:
- **Transcription:** 2-3 seconds
- **Total response time:** 4-6 seconds
- **Accuracy:** 95%+ with good USB mic
- **Memory usage:** ~2-3GB

### Comparison to Pi Zero 2W + NAS:
- **5x faster transcription**
- **Much better accuracy**
- **No network dependency**
- **Simpler architecture**

---

## Next Steps

Once everything is working:
1. **Test conversation memory** - Ask about things you mentioned earlier
2. **Test vision** - Wave at the camera, trigger motion detection
3. **Test time/weather** - "Hey Atlas, what time is it?"
4. **Adjust trigger words** - Try "Hey Tower", "Hey Nexus", etc.

Enjoy your upgraded SAURON! 🚀

