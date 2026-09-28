# SemuBot chest display

Run `python3 main.py` to show the selected chest image in a borderless window.
Python needs Tkinter and Pillow (`pip install Pillow`). The SemuBot logo is the
default image.

## Start on the chest monitor at login

The app needs a graphical desktop session. On the Ubuntu robot, first run
`echo $XDG_SESSION_TYPE` in a terminal. If it says `wayland`, choose an
**Ubuntu on Xorg** session at the login screen if that option is available;
the geometry setting below is intended for X11 screen coordinates. On X11,
use `xrandr --query` after
connecting both screens to find the chest screen's size and position. For
example, if the face screen is `1920x1080+0+0` and the chest screen is
`1024x600+1920+0`, run:

```sh
CHEST_DISPLAY_GEOMETRY=1024x600+1920+0 python3 main.py
```

The format is `WIDTHxHEIGHT+X+Y`. Without this variable, the app uses the
desktop's full reported size at `+0+0`. Test the command in the robot's desktop
session before enabling automatic startup. The setting controls both window
placement and the size used by the app's menus and image preview.

Install the GUI dependencies with `sudo apt install python3-tk python3-pil.imagetk`
if they are not installed already. To start it whenever the desktop user logs in, create
`~/.config/autostart/semubot-chest-display.desktop` for that user:

```ini
[Desktop Entry]
Type=Application
Name=SemuBot chest display
Exec=/usr/bin/env CHEST_DISPLAY_GEOMETRY=1024x600+1920+0 /usr/bin/python3 /home/robot/semubot_chest_display/main.py
Terminal=false
```

Replace the geometry, Python path, user, and project path with the robot's
values. If Pillow is installed in a virtual environment, use that environment's
`python` executable in `Exec`. Enable desktop auto-login if this should start
without someone logging in. Desktop autostart runs after the graphical session
starts; it is different from a system service started before login.

Ubuntu's **Startup Applications** tool can also add the same `Exec` command.
If the face background color must reach ROS at startup, launch the app through
a shell script that sources the robot's ROS 2 environment before running
`main.py`.

Wayland compositors may control window placement themselves. On Wayland, set
the monitor and startup rule in the compositor's configuration if the geometry
setting does not place the window as requested.

Swipe upward at least 300 pixels on the display, enter the admin password, and
choose **Muuda ekraani pilti**. The gallery has **Logod**, **Silmad**, **Suud**,
and **Muud** tabs. **Lisa pilt** opens a file chooser and copies the image into
the active tab's folder: `images/logos/`, `images/eyes/`, `images/mouths/`, or
`images/other/`. You can also copy images into those folders yourself; they
appear when you reopen the gallery. The original SemuBot logo is in
`images/logos/`; the original eye and mouth artwork is in `images/eyes/`
and `images/mouths/`, and the robot face is in `images/other/`.

Selecting an image opens a preview on the chest display. **Salvesta** makes it
the default image and restores it on the next start; **Võta tagasi** returns to
the gallery without changing the saved selection. Imported image files stay in
the gallery even if their preview is undone. The selection is stored in
`chest_display.json`. The admin password is defined by `ADMIN_PASSWORD` in
`constants.py`.

Supported formats are PNG, JPEG, WebP, and BMP. Images are scaled to fit the
display without changing their aspect ratio. These categories organize images
shown on the chest display; they do not change the robot's ROS face.

## Face background color

The admin menu also has **Muuda näo taustavärvi**. Choose a color swatch or
**Muu värv...** to preview the face display's background. **Salvesta** saves
the chosen color in `chest_display.json`; **Võta tagasi** or leaving the screen
restores the previously saved color. The preview and saved color are published
as a `std_msgs/msg/String` containing `#RRGGBB` on the ROS 2 topic
`/face/background_color`. The chest display publishes the saved color at startup,
and the `semubot_eyes` node updates its Pygame background when it receives it.
Start the chest display from a shell with the ROS 2 environment sourced and
`rclpy` available. Both devices need to discover each other in the same ROS 2
domain. If ROS 2 is unavailable, the chest display still saves the chosen color
and publishes it the next time it starts with ROS 2 available.

## Audio settings

Open **Heli seaded** in the admin menu to set the current output volume from
0 to 100% or choose an output device. Select a device from the list and press
**Vali heliväljund**. The app sets it as the default output and tries to move
already playing audio streams to it. Press **Värskenda** after plugging in a
new device. **Testheli** plays a brief two-note sound through the selected
default output, so you can check the volume and device.

This screen uses `pactl`, so the robot needs PulseAudio or PipeWire's PulseAudio
compatibility service running for the same user as the chest display. The
controls report an error when the audio service is unavailable. Audio from
programs that bypass that service and use ALSA directly is outside these
controls.

## Wi-Fi and IPv4

Open **Wi-Fi seaded** to scan nearby networks, see the connected network and
the robot's current IPv4 address by interface, and connect to a selected
network. Password-protected networks open a password screen with an on-screen
keyboard. The password is passed to NetworkManager for the connection and is
not saved in the chest display's settings. Press **Värskenda** to scan again.

Wi-Fi controls require `nmcli` and a running NetworkManager service. IPv4
addresses are read with `ip` and can still appear if Wi-Fi scanning fails.
Enterprise networks that require 802.1X account credentials need separate
configuration in NetworkManager.

## Speech commands

Open **Kõne** in the admin menu to run `sayhi` or `speak -a`. The commands run
without blocking the display, and **Peata** stops a running command. The
executables must be installed on the robot and available on the chest display
process's `PATH`; shell aliases are not used.
