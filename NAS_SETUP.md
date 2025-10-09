# SAURON NAS Integration Guide

## Overview
Mount your NAS and store SAURON data there instead of the SD card.

## NAS Information (from previous attempts)
- **IP**: 192.168.1.254
- **Protocol**: SMB/CIFS or NFS
- **Credentials**: dt_writer / PiTwin2025!
- **Mount point**: /mnt/nas

## Option 1: NFS Mount (Recommended)

### Step 1: Install NFS client
```bash
ssh pi@192.168.4.62
sudo apt update
sudo apt install -y nfs-common
```

### Step 2: Create mount point
```bash
sudo mkdir -p /mnt/nas
sudo chown pi:pi /mnt/nas
```

### Step 3: Test NFS mount
```bash
# Check available NFS shares
showmount -e 192.168.1.254

# Mount (replace /volume1/share with your actual share path)
sudo mount -t nfs 192.168.1.254:/volume1/sauron /mnt/nas

# Verify
ls -la /mnt/nas
df -h | grep nas
```

### Step 4: Make permanent (auto-mount on boot)
```bash
sudo nano /etc/fstab
```

Add this line (replace with your actual NFS path):
```
192.168.1.254:/volume1/sauron  /mnt/nas  nfs  defaults,_netdev,timeo=30  0  0
```

Test auto-mount:
```bash
sudo mount -a
```

## Option 2: SMB/CIFS Mount

### Step 1: Install CIFS utilities
```bash
sudo apt install -y cifs-utils
```

### Step 2: Create credentials file
```bash
sudo nano /etc/cifs-credentials
```

Add:
```
username=dt_writer
password=PiTwin2025!
```

Set permissions:
```bash
sudo chmod 600 /etc/cifs-credentials
```

### Step 3: Test mount
```bash
sudo mkdir -p /mnt/nas
sudo mount -t cifs //192.168.1.254/sauron /mnt/nas -o credentials=/etc/cifs-credentials,uid=pi,gid=pi,vers=3.0
```

### Step 4: Make permanent
```bash
sudo nano /etc/fstab
```

Add:
```
//192.168.1.254/sauron  /mnt/nas  cifs  credentials=/etc/cifs-credentials,uid=pi,gid=pi,vers=3.0,_netdev  0  0
```

## Configure SAURON to Use NAS

### Step 1: Update .env
```bash
nano /home/pi/Sauron/.env
```

Change:
```env
DATA_DIR=/mnt/nas/sauron_data
```

### Step 2: Create directories on NAS
```bash
mkdir -p /mnt/nas/sauron_data/{audio,images,video,logs,daily_summaries}
```

### Step 3: Restart SAURON
```bash
sudo systemctl restart sauron
tail -f /mnt/nas/sauron_data/logs/sauron.log
```

## Troubleshooting

### NAS not accessible
```bash
# Test ping
ping 192.168.1.254

# Check NFS
showmount -e 192.168.1.254

# Check SMB
smbclient -L 192.168.1.254 -U dt_writer
```

### Mount fails
```bash
# Check system logs
dmesg | tail -20

# Check NFS status
sudo systemctl status nfs-common

# Try manual mount with verbose
sudo mount -v -t nfs 192.168.1.254:/volume1/sauron /mnt/nas
```

### Permissions issues
```bash
# Fix ownership
sudo chown -R pi:pi /mnt/nas/sauron_data

# Test write access
touch /mnt/nas/test.txt
rm /mnt/nas/test.txt
```

## Migration (Move existing data to NAS)

```bash
# Copy existing data to NAS
cp -r /home/pi/sauron_data/* /mnt/nas/sauron_data/

# Verify
ls -la /mnt/nas/sauron_data/

# Update .env to use NAS
nano /home/pi/Sauron/.env
# Change DATA_DIR=/mnt/nas/sauron_data

# Restart
sudo systemctl restart sauron
```

## Benefits

✅ **Unlimited storage** (vs 64 GB SD card)  
✅ **Data survives SD card failure**  
✅ **Easy access** from other devices  
✅ **Automatic backups** (if NAS has RAID/backup)  
✅ **Centralized data** for multiple Pi devices  

## Performance

- **NFS**: Faster, better for lots of small files
- **SMB/CIFS**: More compatible, slightly slower

For SAURON (many small audio/image files), **NFS is recommended**.

---

**Which protocol does your NAS support?** Let's get it mounted and test.

