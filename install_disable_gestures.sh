#!/bin/bash
# Link the repo's GNOME extension that turns off touchscreen gestures (3-finger swipes,
# edge swipes) and enable it. On Wayland it takes effect after the next login.
set -euo pipefail
UUID=disable-gestures@semubot
SRC="$(cd "$(dirname "$0")" && pwd)/gnome-extension"
TARGET="$HOME/.local/share/gnome-shell/extensions/$UUID"

mkdir -p "$(dirname "$TARGET")"
rm -rf "$TARGET"
ln -s "$SRC" "$TARGET"

current=$(gsettings get org.gnome.shell enabled-extensions)
if [[ "$current" != *"'$UUID'"* ]]; then
    if [[ "$current" == *"[]" ]]; then
        gsettings set org.gnome.shell enabled-extensions "['$UUID']"
    else
        gsettings set org.gnome.shell enabled-extensions "${current%]}, '$UUID']"
    fi
fi
echo "Installed $UUID -> $SRC. Log out and back in (or reboot) to activate."
