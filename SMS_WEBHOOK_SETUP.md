# Two-Way SMS Setup (Receive & Respond to Texts)

This enables you to **text SAURON** and get responses, not just receive alerts.

## Quick Setup

### 1. Install ngrok (on your Pi)
```bash
# Download ngrok
wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-arm.tgz
tar -xvzf ngrok-v3-stable-linux-arm.tgz
sudo mv ngrok /usr/local/bin/

# Sign up at https://ngrok.com and get your auth token
ngrok config add-authtoken YOUR_AUTH_TOKEN
```

### 2. Start the SMS webhook server (on your Pi)
```bash
# Option A: Run in foreground (for testing)
cd /home/pi/Sauron
source .venv/bin/activate
python3 -m src.sms_webhook

# Option B: Run in background (production)
nohup python3 -m src.sms_webhook > /home/pi/sauron_data/logs/sms_webhook.log 2>&1 &
```

### 3. Expose webhook via ngrok
```bash
# In a separate terminal/pane
ngrok http 5000
```

You'll see output like:
```
Forwarding   https://abc123.ngrok.io -> http://localhost:5000
```

Copy the `https://` URL.

### 4. Configure Twilio webhook

1. Go to: https://console.twilio.com/us1/develop/phone-numbers/manage/incoming
2. Click your phone number
3. Scroll to "Messaging Configuration"
4. Under "A MESSAGE COMES IN":
   - Set webhook to: `https://YOUR_NGROK_URL/sms`
   - Method: `HTTP POST`
5. Click **Save**

## Usage

Now you can text your SAURON number and have a conversation:

**You:** "Hey, what did I say earlier about saunas?"

**SAURON:** "You asked whether to do saunas morning or evening. I suggested evening for relaxation."

**You:** "What's the weather like?"

**SAURON:** "Clear, 72°F. Perfect evening."

## Memory Integration

The webhook automatically:
- ✅ Accesses full conversation history
- ✅ Pulls relevant facts from long-term memory
- ✅ Maintains context across voice + text conversations
- ✅ Stores all text exchanges for future reference

## Production Setup (Auto-start)

Create a systemd service for the webhook:

```bash
sudo nano /etc/systemd/system/sauron-webhook.service
```

Paste:
```ini
[Unit]
Description=SAURON SMS Webhook
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/Sauron
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONPATH=/home/pi/Sauron
EnvironmentFile=/home/pi/Sauron/.env
ExecStart=/home/pi/Sauron/.venv/bin/python3 -m src.sms_webhook
Restart=always
RestartSec=10
StandardOutput=append:/home/pi/sauron_data/logs/sms_webhook.log
StandardError=append:/home/pi/sauron_data/logs/sms_webhook_error.log

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable sauron-webhook
sudo systemctl start sauron-webhook
sudo systemctl status sauron-webhook
```

## ngrok Persistent Tunnel

For a permanent URL (no need to update Twilio every restart):

1. Upgrade to ngrok paid plan ($8/month for static domain)
2. Reserve a static domain in ngrok dashboard
3. Update Twilio webhook once with static URL
4. Run: `ngrok http --domain=your-static-domain.ngrok-free.app 5000`

## Troubleshooting

**Webhook not responding:**
```bash
# Check if Flask is running
ps aux | grep sms_webhook

# Check logs
tail -50 /home/pi/sauron_data/logs/sms_webhook.log

# Test locally
curl http://localhost:5000/health
```

**ngrok tunnel down:**
```bash
# Restart ngrok
pkill ngrok
ngrok http 5000
# Update Twilio webhook with new URL
```

**"System error" responses:**
```bash
# Check OpenRouter API key
tail -50 /home/pi/sauron_data/logs/sms_webhook.log | grep -i error
```

