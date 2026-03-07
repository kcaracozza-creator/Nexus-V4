#!/bin/bash
# MTG Scanner - Global Hardware Reset
DEVICE="/dev/video0"

echo "Restoring Arducam Golden Settings..."
v4l2-ctl -d $DEVICE -c auto_exposure=1
v4l2-ctl -d $DEVICE -c exposure_time_absolute=150
v4l2-ctl -d $DEVICE -c gain=800
v4l2-ctl -d $DEVICE -c brightness=30
v4l2-ctl -d $DEVICE -c contrast=50
v4l2-ctl -d $DEVICE -c saturation=50
v4l2-ctl -d $DEVICE -c focus_absolute=580
v4l2-ctl -d $DEVICE -c white_balance_automatic=1

echo "Verification:"
v4l2-ctl -d $DEVICE -C exposure_time_absolute,gain,focus_absolute
