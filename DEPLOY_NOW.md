# SAURON Deployment Checklist (NAS Setup)

## Complete deployment for current single-device setup with NAS offloading.

---

## Step 1: Mount NAS on Pi (10 minutes)

```bash
ssh pi@192.168.4.62

# Install NFS
sudo apt install -y nfs-common

# Create mount point
sudo mkdir -p /mnt/nas
sudo chown pi:pi /mnt/nas

# Check what your NAS exports
showmount -e 192.168.1.254
```

**If you see NFS shares**, use this:
```bash
# Replace /volume1/sauron with your actual share path
sudo mount -t nfs 192.168.1.254:/volume1/sauron /mnt/nas

# Make permanent
echo "192.168.1.254:/volume1/sauron  /mnt/nas  nfs  defaults,_netdev,timeo=30  0  0" | sudo tee -a /etc/fstab

# Test auto-mount
sudo mount -a
```

**If NFS not available**, use SMB:
```bash
sudo apt install -y cifs-utils

# Create credentials
sudo bash -c 'cat > /etc/cifs-credentials << EOF
username=dt_writer
password=PiTwin2025!
EOF'

sudo chmod 600 /etc/cifs-credentials

# Mount
sudo mount -t cifs //192.168.1.254/sauron /mnt/nas -o credentials=/etc/cifs-credentials,uid=pi,gid=pi,vers=3.0

# Make permanent
echo "//192.168.1.254/sauron  /mnt/nas  cifs  credentials=/etc/cifs-credentials,uid=pi,gid=pi,vers=3.0,_netdev  0  0" | sudo tee -a /etc/fstab
```

**Verify mount:**
```bash
df -h | grep nas
touch /mnt/nas/test.txt && rm /mnt/nas/test.txt
```

---

## Step 2: Setup NAS Whisper Service (15 minutes)

**On your NAS** (SSH or web terminal):

```bash
# Install Python if not already installed
# (This depends on your UGREEN NAS OS - likely has Python already)

# Create directory
mkdir -p ~/sauron_whisper
cd ~/sauron_whisper

# Download service file from GitHub
wget https://raw.githubusercontent.com/buildingjoshbetter/Sauron/main/nas_whisper_service.py

# Install dependencies
pip3 install flask faster-whisper

# Test run
python3 nas_whisper_service.py
```

**If it starts successfully**, create systemd service:
```bash
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
ExecStart=/usr/bin/python3 nas_whisper_service.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable:
```bash
sudo systemctl daemon-reload
sudo systemctl enable whisper
sudo systemctl start whisper
sudo systemctl status whisper
```

**Test from Pi:**
```bash
curl http://192.168.1.254:5001/health
```

Should return: `{"status":"ok","model":"faster-whisper"}`

---

## Step 3: Configure SAURON on Pi (5 minutes)

```bash
ssh pi@192.168.4.62

# Create NAS directories
mkdir -p /mnt/nas/sauron/{audio_archive,video_archive,daily_summaries}

# Update .env
nano /home/pi/Sauron/.env
```

**Add/update these lines:**
```env
# NAS paths
MEMORY_DIR=/mnt/nas/sauron
NAS_ARCHIVE_DIR=/mnt/nas/sauron
NAS_WHISPER_URL=http://192.168.1.254:5001

# Keep local for active files
DATA_DIR=/home/pi/sauron_data

# Enable optimizations
USE_LOCAL_WHISPER=false
ENABLE_STREAMING_TRANSCRIPTION=true
ENABLE_VIDEO_ON_MOTION=true
VIDEO_DURATION_SECONDS=10

# Update model to fastest
OPENROUTER_MODEL=meta-llama/llama-3.1-8b-instruct

# Your location (for time/weather)
LATITUDE=37.7749
LONGITUDE=-122.4194
TIMEZONE=America/Los_Angeles
```

**Also verify these are set:**
```env
AUDIO_DEVICE=plughw:1,0
MOTION_SENSITIVITY=0.08
```

---

## Step 4: Deploy SAURON (5 minutes)

```bash
# Pull latest code
cd /home/pi/Sauron
git pull

# Install system dependencies
sudo apt install -y ffmpeg libopenblas0 libatlas-base-dev

# Install Python dependencies
source .venv/bin/activate
pip install -r requirements.txt

# Install and start service
chmod +x deploy/install-service.sh
./deploy/install-service.sh
```

---

## Step 5: Verify Everything Works (2 minutes)

**Check service status:**
```bash
sudo systemctl status sauron
```

**Watch logs:**
```bash
tail -f /home/pi/sauron_data/logs/sauron.log
```

**You should see:**
```
loaded X messages from conversation history
loaded X facts from memory
initialized user profile fact: user_name
audio chunk: /home/pi/sauron_data/audio/audio_XXXXX.wav
transcript: [your speech]
```

**Check NAS storage:**
```bash
ls -lh /mnt/nas/sauron/
cat /mnt/nas/sauron/facts.json | head -20
```

---

## Step 6: Test the System (5 minutes)

**Say these out loud:**

1. **"What time is it?"**
   - Should get SMS in ~2-3 seconds

2. **"What's the weather?"**
   - Should get SMS with temperature/conditions

3. **"What am I holding?"** (hold something)
   - SMS: "Gimme a sec while I analyze..."
   - Then: Description of what you're holding

4. Walk in front of camera
   - No SMS (silent observation)
   - Video captured and analyzed
   - Stored in memory

5. **"What did you see earlier?"**
   - Should reference the motion event

---

## What You Have Now

✅ **Fully autonomous** (starts on boot)  
✅ **Photographic memory** (recalls anything ever said)  
✅ **Computer vision** (sees and remembers)  
✅ **NAS storage** (unlimited memory, audio/video archives)  
✅ **Fast transcription** (0.2-1 sec with NAS Whisper)  
✅ **Knows Josh** (personality, preferences, work style)  
✅ **Sub-2-second responses** (feels instant)  

## Storage Breakdown

**SD Card:** ~1-6 GB (never exceeds)  
**NAS:** Grows ~1-5 GB/day (audio/video archives forever)

**In 1 year:** ~550 GB on NAS (totally fine for multi-TB NAS)

---

## Quick Commands Reference

```bash
# View logs
tail -f /home/pi/sauron_data/logs/sauron.log

# Restart service
sudo systemctl restart sauron

# Check status
sudo systemctl status sauron

# View memory
cat /mnt/nas/sauron/facts.json | jq '.user_name, .user_personality'

# Check NAS Whisper
curl http://192.168.1.254:5001/health

# View archives
ls -lh /mnt/nas/sauron/audio_archive/
```

---

## Next: When You're Ready to Scale

When you add devices 2-10:
1. Build the $1,500 AI server
2. Add mmWave sensors to each Pi
3. Deploy coordinator service
4. Clone and deploy to additional Pis

**But for now, get this one working perfectly.** Master it, then replicate.

---

**Total deployment time: ~45 minutes**  
**Assuming NAS is accessible and you have SSH access to both Pi and NAS.**

