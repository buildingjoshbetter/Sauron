#!/bin/bash
set -e

echo "========================================="
echo "SAURON Pi 5 Setup Script"
echo "========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Step 1: System Update${NC}"
sudo apt-get update
sudo apt-get upgrade -y

echo ""
echo -e "${YELLOW}Step 2: Install System Dependencies${NC}"
sudo apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    git \
    libopenblas0 \
    libatlas-base-dev \
    portaudio19-dev \
    python3-pyaudio \
    alsa-utils \
    libcamera-apps \
    ffmpeg

echo ""
echo -e "${YELLOW}Step 3: Create Virtual Environment${NC}"
python3.11 -m venv .venv
source .venv/bin/activate

echo ""
echo -e "${YELLOW}Step 4: Install Python Dependencies${NC}"
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo -e "${YELLOW}Step 5: Install Whisper (Medium Model)${NC}"
pip install openai-whisper

echo ""
echo -e "${YELLOW}Step 6: Create Data Directories${NC}"
mkdir -p ~/sauron_data/{audio,images,video,logs}

echo ""
echo -e "${YELLOW}Step 7: Detect USB Microphone${NC}"
echo "Checking for USB audio devices..."
arecord -l
echo ""
echo -e "${GREEN}USB mic detected! Update AUDIO_DEVICE in .env with the correct device (plughw:X,0)${NC}"

echo ""
echo -e "${YELLOW}Step 8: Test Camera${NC}"
if libcamera-hello --list-cameras; then
    echo -e "${GREEN}Camera detected successfully!${NC}"
else
    echo -e "${RED}Camera not detected. Check connections.${NC}"
fi

echo ""
echo -e "${YELLOW}Step 9: Install Systemd Service${NC}"
sudo cp deploy/sauron.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable sauron.service

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo "Next steps:"
echo "1. Update .env with your API keys and USB mic device"
echo "2. Start SAURON: sudo systemctl start sauron"
echo "3. Check logs: tail -f ~/sauron_data/logs/sauron.log"
echo ""
echo "Test your setup:"
echo "  - Say: 'Hey Atlas, what's 2 plus 2?'"
echo ""

