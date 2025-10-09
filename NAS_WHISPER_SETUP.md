# SAURON NAS Whisper Service Setup

## Why Run Whisper on NAS?

Your **UGREEN 4-bay NAS Pro** has a much more powerful CPU than Pi Zero 2W:
- **NAS**: Intel N100 (4 cores @ 3.4GHz) or similar
- **Pi Zero 2W**: ARM Cortex-A53 (4 cores @ 1GHz)

**Speed comparison:**
- Pi Zero 2W (local): 0.5-2 seconds
- NAS (remote): **0.1-0.5 seconds** (3-5x faster!)
- OpenAI API: 2-5 seconds

## Setup on UGREEN NAS

### Step 1: SSH into NAS

```bash
ssh admin@192.168.1.254
```

(Replace with your NAS admin credentials)

### Step 2: Install Python and dependencies

```bash
# Update package manager
sudo apt update

# Install Python and pip
sudo apt install -y python3 python3-pip python3-venv

# Create service directory
mkdir -p ~/sauron_whisper
cd ~/sauron_whisper
```

### Step 3: Download the service file

```bash
# Option A: Clone the repo
git clone https://github.com/buildingjoshbetter/Sauron.git
cp Sauron/nas_whisper_service.py .

# Option B: Create manually
nano nas_whisper_service.py
# Paste the content from nas_whisper_service.py
```

### Step 4: Install dependencies

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install flask faster-whisper

# Test
python3 nas_whisper_service.py
```

You should see:
```
loaded faster-whisper tiny model (int8)
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:5001
 * Running on http://192.168.1.254:5001
```

### Step 5: Test from Pi

```bash
# On Pi
ssh pi@192.168.4.62

# Test the service
arecord -D plughw:1,0 -f S16_LE -c 1 -r 16000 -d 3 -t wav /tmp/test.wav
curl -X POST -F "file=@/tmp/test.wav" http://192.168.1.254:5001/transcribe
```

Should return:
```json
{"text":"your transcribed text here"}
```

### Step 6: Create systemd service on NAS (auto-start)

```bash
# On NAS
sudo nano /etc/systemd/system/whisper.service
```

Add:
```ini
[Unit]
Description=Whisper Transcription Service
After=network.target

[Service]
Type=simple
User=admin
WorkingDirectory=/home/admin/sauron_whisper
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/admin/sauron_whisper/.venv/bin/python3 nas_whisper_service.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable whisper
sudo systemctl start whisper
sudo systemctl status whisper
```

### Step 7: Configure SAURON on Pi

```bash
# On Pi
nano /home/pi/Sauron/.env
```

Add:
```env
NAS_WHISPER_URL=http://192.168.1.254:5001
```

Restart SAURON:
```bash
sudo systemctl restart sauron
tail -f /home/pi/sauron_data/logs/sauron.log
```

## Speed Comparison

| Method | Speed | Quality |
|--------|-------|---------|
| OpenAI API | 2-5 sec | Excellent |
| Pi Local Whisper | 0.5-2 sec | Good |
| **NAS Whisper** | **0.1-0.5 sec** | Good |

**With NAS Whisper, total response time: ~1-2 seconds!**

## Transcription Priority

SAURON will try in order:
1. **NAS Whisper** (if `NAS_WHISPER_URL` set) → Fastest
2. **Local Pi Whisper** (if `USE_LOCAL_WHISPER=true`) → Fast
3. **OpenAI API** (fallback) → Reliable

## Benefits

✅ **3-5x faster than Pi local**  
✅ **10x faster than OpenAI API**  
✅ **No API costs**  
✅ **No rate limits**  
✅ **Always available** (local network)  
✅ **Offloads CPU from Pi** (better for other tasks)  

## Troubleshooting

### Can't connect to NAS service
```bash
# On NAS, check service
sudo systemctl status whisper

# Check port is open
curl http://192.168.1.254:5001/health

# From Pi, test connectivity
ping 192.168.1.254
curl http://192.168.1.254:5001/health
```

### Slow transcription on NAS
```bash
# On NAS, try faster-whisper instead of regular whisper
pip install faster-whisper

# Or use smaller model (even faster)
# Edit nas_whisper_service.py, change "tiny" to "base" for better quality
# or keep "tiny" for max speed
```

---

**With NAS Whisper, SAURON responses will be nearly instant (~1-2 seconds total).**

