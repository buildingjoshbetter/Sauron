# SAURON NAS Memory Setup

## Storage Architecture

### **Local (SD Card) - Fast, Temporary**
Stored in `/home/pi/sauron_data/`:
- ✅ Audio files (24 hours, then deleted)
- ✅ Images (24 hours, then deleted)
- ✅ Videos (deleted immediately after analysis)
- ✅ Logs (rolling)
- ✅ **~1-6 GB total** (never exceeds this)

### **NAS (Network Storage) - Unlimited, Permanent**
Stored in `/mnt/nas/sauron_memory/`:
- ✅ Conversation history (unlimited, forever)
- ✅ Facts database (500+ facts, forever)
- ✅ Conversation summaries (forever)
- ✅ Daily summaries (transcripts, vision, images)
- ✅ **Grows ~10-50 MB/year** (text only)

## Setup Instructions

### Step 1: Mount NAS on Pi

```bash
ssh pi@192.168.4.62

# Install NFS client
sudo apt install -y nfs-common

# Create mount point
sudo mkdir -p /mnt/nas
sudo chown pi:pi /mnt/nas

# Check available NFS shares on your NAS
showmount -e 192.168.1.254
```

**If NFS is available**, you'll see something like:
```
Export list for 192.168.1.254:
/volume1/sauron *
```

### Step 2: Mount the NAS

**For NFS:**
```bash
sudo mount -t nfs 192.168.1.254:/volume1/sauron /mnt/nas

# Verify
ls -la /mnt/nas
df -h | grep nas
```

**For SMB/CIFS (if NFS not available):**
```bash
sudo apt install -y cifs-utils

# Create credentials
sudo nano /etc/cifs-credentials
```
Add:
```
username=dt_writer
password=PiTwin2025!
```

```bash
sudo chmod 600 /etc/cifs-credentials

# Mount
sudo mount -t cifs //192.168.1.254/sauron /mnt/nas -o credentials=/etc/cifs-credentials,uid=pi,gid=pi,vers=3.0
```

### Step 3: Make mount permanent

```bash
sudo nano /etc/fstab
```

**For NFS, add:**
```
192.168.1.254:/volume1/sauron  /mnt/nas  nfs  defaults,_netdev,timeo=30  0  0
```

**For CIFS, add:**
```
//192.168.1.254/sauron  /mnt/nas  cifs  credentials=/etc/cifs-credentials,uid=pi,gid=pi,vers=3.0,_netdev  0  0
```

Test:
```bash
sudo mount -a
```

### Step 4: Create memory directories on NAS

```bash
mkdir -p /mnt/nas/sauron_memory/daily_summaries
```

### Step 5: Update SAURON .env

```bash
nano /home/pi/Sauron/.env
```

Add this line:
```env
MEMORY_DIR=/mnt/nas/sauron_memory
```

**Keep DATA_DIR as local:**
```env
DATA_DIR=/home/pi/sauron_data
```

### Step 6: Migrate existing memory (optional)

```bash
# Copy existing memory files to NAS
cp /home/pi/sauron_data/conversation.json /mnt/nas/sauron_memory/ 2>/dev/null || true
cp /home/pi/sauron_data/facts.json /mnt/nas/sauron_memory/ 2>/dev/null || true
cp /home/pi/sauron_data/summaries.json /mnt/nas/sauron_memory/ 2>/dev/null || true
cp -r /home/pi/sauron_data/daily_summaries /mnt/nas/sauron_memory/ 2>/dev/null || true
```

### Step 7: Restart SAURON

```bash
sudo systemctl restart sauron
tail -f /home/pi/sauron_data/logs/sauron.log
```

You should see:
```
loaded X messages from conversation history
loaded X facts from memory
```

## Verify NAS is Working

```bash
# Check memory files are on NAS
ls -lh /mnt/nas/sauron_memory/

# Check local files are on SD card
ls -lh /home/pi/sauron_data/

# Monitor NAS writes
watch -n 2 'ls -lh /mnt/nas/sauron_memory/'
```

## What Goes Where

| Data Type | Location | Retention | Size |
|-----------|----------|-----------|------|
| **Audio files** | SD Card | 24 hours | ~1-5 GB |
| **Images** | SD Card | 24 hours | ~0.5-1 GB |
| **Videos** | SD Card | < 1 minute | ~5-10 MB (transient) |
| **Logs** | SD Card | Rolling | ~10-100 MB |
| **Conversation** | **NAS** | Forever | ~5-20 MB/year |
| **Facts** | **NAS** | Forever | ~100-500 KB |
| **Summaries** | **NAS** | Forever | ~10-50 MB/year |
| **Daily summaries** | **NAS** | Forever | ~4-24 MB/year |

## Benefits

✅ **SD card never fills up** (capped at ~6 GB)  
✅ **Contextual memory unlimited** (stored on NAS)  
✅ **Fast local access** for active files  
✅ **Survives SD card failure** (memory on NAS)  
✅ **Access from any device** (NAS accessible network-wide)  

## Troubleshooting

### NAS mount fails
```bash
# Check network connectivity
ping 192.168.1.254

# Check what's listening
nmap -p 111,2049 192.168.1.254  # NFS ports
nmap -p 445,139 192.168.1.254   # SMB ports

# Check system logs
sudo journalctl -xe | grep mount
```

### Can't write to NAS
```bash
# Check permissions
touch /mnt/nas/test.txt

# If fails, fix ownership
sudo chown -R pi:pi /mnt/nas/sauron_memory
```

### SAURON can't find memory files
```bash
# Check MEMORY_DIR in .env
grep MEMORY_DIR /home/pi/Sauron/.env

# Verify NAS is mounted
mount | grep nas

# Check files exist
ls -la /mnt/nas/sauron_memory/
```

---

**After NAS setup, SAURON will:**
- Store active files locally (fast)
- Store memory on NAS (unlimited)
- Work seamlessly with both
- Never run out of space

