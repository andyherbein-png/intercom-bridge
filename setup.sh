#!/bin/bash
set -e

# System packages
sudo apt-get update
sudo apt-get install -y \
    python3-pip python3-venv \
    pipewire pipewire-audio wireplumber \
    bluez python3-dbus \
    udev

# Python venv
python3 -m venv /home/pi/minihop/venv
/home/pi/minihop/venv/bin/pip install -r /home/pi/minihop/requirements.txt

echo "Setup complete. Run: sudo systemctl enable --now minihop"
