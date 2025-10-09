#!/bin/bash
# Install SAURON systemd service for auto-start on boot

set -e

echo "Installing SAURON systemd service..."

# Copy service file
sudo cp /home/pi/Sauron/deploy/sauron.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable service (start on boot)
sudo systemctl enable sauron.service

# Start service now
sudo systemctl start sauron.service

echo ""
echo "✓ SAURON service installed and started"
echo ""
echo "Useful commands:"
echo "  sudo systemctl status sauron    # Check status"
echo "  sudo systemctl stop sauron      # Stop service"
echo "  sudo systemctl restart sauron   # Restart service"
echo "  sudo systemctl disable sauron   # Disable auto-start"
echo "  tail -f /home/pi/sauron_data/logs/sauron.log  # View logs"
echo ""

