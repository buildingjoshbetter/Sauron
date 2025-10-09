## Sauron Pi Assistant (Audio/Vision -> Whisper -> OpenRouter -> Twilio SMS)

### Prereqs (Raspberry Pi OS Bookworm, 32-bit, Pi Zero 2W)
- Enable I2C, camera: `sudo raspi-config` (Interfaces)
- Update base: `sudo apt update && sudo apt upgrade -y`
- Install audio/camera CLIs: `sudo apt install -y alsa-utils libcamera-apps python3-pip python3-venv`
- Verify mic device: `arecord -l` (note card/device for `.env` `AUDIO_DEVICE` like `hw:0,0`)
- Test camera: `libcamera-still -o test.jpg`

### Install
```bash
cd /home/pi
git clone https://github.com/youruser/Sauron.git
cd Sauron
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
cp .env.example .env
nano .env  # fill API keys and settings
```

### Configure env
- OPENROUTER_API_KEY: from OpenRouter
- OPENAI_API_KEY: for Whisper
- TWILIO_*: account, token, from/to numbers
- AUDIO_DEVICE: e.g. `hw:0,0`

### Run
```bash
PYTHONPATH=$(pwd) python3 -m src.main
```

### systemd
```bash
sudo cp deploy/sauron.service /etc/systemd/system/sauron.service
sudo systemctl daemon-reload
sudo systemctl enable sauron
sudo systemctl start sauron
sudo systemctl status sauron
```
Logs at `/home/pi/sauron_data/logs/sauron.log`.

### Notes
- Audio chunking uses `webrtcvad` and `arecord` at 16 kHz mono.
- Motion detection uses `libcamera-still` snapshots and grayscale diff.
- SMS is only sent on clear questions or motion events by default.

