#!/bin/bash
# Start the SemuBot chest display with ROS 2 on the robot's domain (same as rosbridge/brain).
# ~/.config/semubot/semubot.env (shared by the robot's units) and chest_display.env are loaded when present.
# The app itself places its window on CHEST_DISPLAY_MONITOR (see chest_display.env) and keeps
# following that monitor if the screen layout changes.
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-5} RMW_IMPLEMENTATION=${RMW_IMPLEMENTATION:-rmw_cyclonedds_cpp}
[ -n "${CYCLONEDDS_URI+x}" ] || [ ! -f "$HOME/cyclonedds.xml" ] || export CYCLONEDDS_URI=file://$HOME/cyclonedds.xml
export PATH="$HOME/.local/bin:$PATH"
for f in semubot.env chest_display.env; do
    [ -f "$HOME/.config/semubot/$f" ] && set -a && source "$HOME/.config/semubot/$f" && set +a
done
cd "$(dirname "$(readlink -f "$0")")/.."
exec python3 main.py
