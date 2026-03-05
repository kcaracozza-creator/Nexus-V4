#!/bin/bash
# NEXUS Proof of Presence - Touch Validator Launcher
# Run on DANIELSON scanner station with 7" touchscreen
#
# Auto-start (Ubuntu Desktop / GNOME):
#   cp ~/.config/autostart/nexus-validator.desktop ~/.config/autostart/
#   OR run deploy.sh which sets it up automatically
#
# Manual: bash start_validator.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NEXUS_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Wait for display server
sleep 3

# Disable screen blanking/screensaver
xset s off 2>/dev/null
xset -dpms 2>/dev/null
xset s nouse 2>/dev/null

# Disable GNOME screen lock and idle dimming
gsettings set org.gnome.desktop.screensaver lock-enabled false 2>/dev/null
gsettings set org.gnome.desktop.session idle-delay 0 2>/dev/null
gsettings set org.gnome.settings-daemon.plugins.power idle-dim false 2>/dev/null

# Hide mouse cursor (touch only) — install: sudo apt install unclutter
unclutter -idle 0 &

# Launch touch validator fullscreen
cd "$NEXUS_ROOT"
python3 "$SCRIPT_DIR/touch_validator.py" --fullscreen 2>&1 | tee /tmp/nexus_validator.log
