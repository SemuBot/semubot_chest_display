#!/bin/bash
# Set up the chest display for the desktop user on the robot: systemd user service, settings file,
# screen layout and GNOME gesture blocker. Safe to run again after a pull.
set -euo pipefail
DEPLOY="$(cd "$(dirname "$0")" && pwd)"
REPO="$(dirname "$DEPLOY")"
UNIT=semubot-chest-display.service

# Replaces the old GNOME autostart entry and ~/.local/bin launcher
rm -f "$HOME/.config/autostart/semubot-chest-display.desktop" "$HOME/.local/bin/semubot-chest-display"

mkdir -p "$HOME/.config/systemd/user"
sed "s#REPO#$REPO#" "$DEPLOY/$UNIT" > "$HOME/.config/systemd/user/$UNIT"

ENV_FILE="$HOME/.config/semubot/chest_display.env"
if [ ! -f "$ENV_FILE" ]; then
    mkdir -p "$(dirname "$ENV_FILE")"
    cp "$DEPLOY/chest_display.env.example" "$ENV_FILE"
    echo "Created $ENV_FILE: set CHEST_DISPLAY_ADMIN_PASSWORD there."
fi

# Saved GNOME screen layouts, incl. the chest screen turned upside down with and without the head
if ! cmp -s "$DEPLOY/monitors.xml" "$HOME/.config/monitors.xml"; then
    [ -f "$HOME/.config/monitors.xml" ] && cp "$HOME/.config/monitors.xml" "$HOME/.config/monitors.xml.bak-$(date +%F)"
    cp "$DEPLOY/monitors.xml" "$HOME/.config/monitors.xml"
    echo "Installed monitors.xml; it is used from the next login."
fi

"$REPO/install_disable_gestures.sh"

systemctl --user daemon-reload
systemctl --user enable "$UNIT"
pkill -f "[p]ython3 main.py" || true  # a copy started by the old autostart or by hand
systemctl --user restart "$UNIT"
echo "Running. Logs: journalctl --user -u $UNIT -f"
