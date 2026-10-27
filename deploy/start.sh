#!/bin/bash
# Start the SemuBot chest display with ROS 2 on the robot's domain (same as rosbridge/brain).
# The app itself places its window on CHEST_DISPLAY_MONITOR (see chest_display.env) and keeps
# following that monitor if the screen layout changes.
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=5 RMW_IMPLEMENTATION=rmw_cyclonedds_cpp CYCLONEDDS_URI=file://$HOME/cyclonedds.xml
export PATH="$HOME/.local/bin:$PATH"
[ -f "$HOME/.config/semubot/chest_display.env" ] && set -a && source "$HOME/.config/semubot/chest_display.env" && set +a
cd "$(dirname "$(readlink -f "$0")")/.."
exec python3 main.py
