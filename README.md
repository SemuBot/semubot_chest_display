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

Alternatively set `CHEST_DISPLAY_MONITOR` to the chest monitor's connector name from
`xrandr --query` (e.g. `CHEST_DISPLAY_MONITOR=HDMI-2`) and leave `CHEST_DISPLAY_GEOMETRY` unset:
the app then places its window on that monitor and checks every 2 seconds, moving the window if
the monitor's position or size changes (for example when GNOME applies the saved screen layout
just after login, or a screen is rotated). It prints the position it uses (`Chest display
window: ...`) and every move to its log.

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
display without changing their aspect ratio. An image with transparent corners (a logo) is shown
at up to 80% of the width and 75% of the height on the normal background. An image with opaque
corners (a design with its own background) is shown as large as fits on the whole screen, and
the space around it gets the colour of its top-left pixel, so it looks edge to edge. These categories organize images
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

## Speech mode

Open **Kõnerežiim** in the admin menu to switch how the robot talks:

- **Käsitsi** - the robot only says text typed in the webapp (or quick chat).
- **Kohalik AI** - the robot listens and answers with the local language model on the robot.
- **Pilve AI** - the robot listens and answers with a cloud model (Claude or OpenAI).

A button press publishes the mode as a `std_msgs/msg/String` (`manual`, `local` or `cloud`) on
`/semubot/mode`. The robot's `semu_brain_node` (package `semubot_brain`) switches mode and
reports it back on `/semubot/mode_state`. The ✓ marks the mode the robot reports. If the brain
node is not running, the screen says so. The webapp's speech mode toggle uses the same topics,
so both always show the same mode.

The chest display, rosbridge and the brain node must be in the same ROS 2 domain. On SemuBot that
is `ROS_DOMAIN_ID=5` with `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp` and
`CYCLONEDDS_URI=file:///home/semubot/cyclonedds.xml`. Start the display from a script that
sources ROS 2 and exports these values, for example:

```sh
#!/bin/bash
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=5 RMW_IMPLEMENTATION=rmw_cyclonedds_cpp CYCLONEDDS_URI=file:///home/semubot/cyclonedds.xml
export PATH="$HOME/.local/bin:$PATH"
cd /home/semubot/semubot_chest_display
exec python3 main.py
```

The display exits cleanly on SIGINT/SIGTERM (Ctrl+C, logout, `kill`).

If ROS 2 cannot start when the display starts (on SemuBot, CycloneDDS is bound to the Wi-Fi
interface `wlo1`, which can come up a few seconds after login), the display keeps running and
retries every 5 seconds; the ROS screens show "ROS 2 pole saadaval … (proovin 5 s pärast
uuesti)" until it connects.

## Robot voice

**Kõnerežiim → Hääl** chooses the voice the robot speaks with and how fast it talks. The buttons
list the voices of the robot's TartuNLP text-to-speech service (for example Mari, Albert, Vesta).
The ✓ marks the voice the robot reports. The **Kiirus** slider sets the speed from 0.5 to 2.0
(1.0 is normal) and is sent when you let go. **Proovi** makes the robot say a sample sentence with
the current settings. The robot applies changes immediately, saves them, and uses them for
everything it says (replies, typed text and the `speak` command).

The screen uses the ROS 2 topics `/semubot/tts_settings` (`std_msgs/msg/String` with JSON such as
`{"speaker": "vesta", "speed": 1.2}`) and `/semubot/tts_settings_state` of `semu_brain_node`, and
publishes the sample sentence on `/speech_input`.

## Conversation log and cloud usage

**Kõnerežiim → Vestlus** shows the robot's recent conversation, newest at the bottom: what it
heard (**Inimene**), what it said (**Semu**), text typed in the webapp or quick chat
(**Operaator**), mode changes and new conversations (**—**), errors (**Viga**) and what
happened to each recording (**Heli**: saved and sent to speech recognition, discarded as too
short, or no words found). The robot keeps
only the last 30 entries, in memory only; **Tühjenda** empties the log. The robot starts a new
conversation (forgets the chat history) after 5 minutes without an exchange, which is shown in
the log.

Above the log, a coloured line shows what the robot is doing right now and for how long:
**⏸ Käsitsi režiim – ei kuula** (manual mode, not listening), **● Kuulan** (listening),
**● Inimene räägib…** (someone is talking), **◐ Tuvastan kõnet…** (speech recognition),
**◐ Mõtlen (Kohalik AI / Pilve AI)…** (the language model is answering), **◐ Valmistan kõnet…**
(text-to-speech) and **▶ Räägin…** (speaking). Under each heard and said entry, a grey line shows
how long the steps took, e.g. `kõnetuvastus 8.8 s` and `Kohalik AI 2.6 s · kõnesüntees 0.8 s`.
It uses the ROS 2 topic `/semubot/state` (`std_msgs/msg/String`, JSON).

The bottom line shows cloud AI use today and this month: requests, tokens and an estimated cost
in USD. The Kõnerežiim screen shows today's line too. The estimate is only shown when prices are
known for the cloud model (built in for Claude; set `CLOUD_PRICE_INPUT`/`CLOUD_PRICE_OUTPUT` in the
robot's `~/.config/semubot/brain.env` for others).

Topics: `/semubot/conversation_log` (`std_msgs/msg/String`, JSON list),
`/semubot/conversation_log_clear` (`std_msgs/msg/Empty`), `/semubot/cloud_usage`
(`std_msgs/msg/String`, JSON).

## Microphone sensitivity

**Kõnerežiim → Mikrofon** shows what the robot hears and lets you set how loud a
voice must be before the robot reacts. The robot only listens to a sound when Silero VAD says it
is a **voice** and it is at least as loud as the **threshold** (the red line). Quieter voices,
for example people further away, are ignored.

- The bar shows the live loudness: **green** = the robot hears speech, **yellow** = a voice, but
  quieter than the threshold, **grey** = no speech (noise or silence). Below the bar are the current
  loudness and, for the last 10 s, the typical background and the loudest speech.
- Drag the slider to change the threshold. It is sent when you let go, applied immediately and
  saved by the robot (`~/.config/semubot/vad.json` on the robot).
- **Kalibreeri**: stand where people usually talk to the robot, press it and speak normally for
  5 seconds. The threshold is set to half of the typical loudness of that speech.

The screen uses the ROS 2 topics `/semubot/audio_level` (`Float32MultiArray`
`[rms, speech probability]`), `/semubot/vad_threshold` and `/semubot/vad_threshold_state`
(`Float32`) of the robot's `semu_brain_node`.
