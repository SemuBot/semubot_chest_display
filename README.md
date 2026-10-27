# SemuBot chest display

Run `python3 main.py` to show the selected chest image in a borderless window.
Python needs Tkinter and Pillow (`pip install Pillow`). The SemuBot logo is the
default image.

## Menu language

Swipe upward to open the admin login screen. Tap **English** in the upper right
to switch the menu to English; tap **Eesti** to return to Estonian. The same
button is available in the admin menu. The selected language is saved as
`menu_language` (`et` or `en`) in `chest_display.json` and restored at startup.
The default is Estonian. This setting changes the menu labels and status text;
robot speech, conversation contents, network names, and image names keep their
original language.

## Install on the robot

Everything the robot needs outside this repo lives in `deploy/`. As the desktop user (auto-login),
after cloning the repo to `~/semubot_chest_display`, run once and again after pulls that change
`deploy/`:

```sh
sudo apt install python3-tk python3-pil.imagetk
./deploy/install.sh
```

It sets up:

- **`semubot-chest-display.service`**, a systemd user service that starts with the desktop session
  and restarts the app if it crashes. It runs `deploy/start.sh`, which sources ROS 2 Jazzy with
  SemuBot's domain (`ROS_DOMAIN_ID=5`, CycloneDDS from `~/cyclonedds.xml`) and starts `main.py`.
  Restart it with `systemctl --user restart semubot-chest-display`; read its log with
  `journalctl --user -u semubot-chest-display -f`.
- **`~/.config/semubot/chest_display.env`**, only if it does not exist yet, from
  `deploy/chest_display.env.example`. It is not in git: set the admin PIN there
  (`CHEST_DISPLAY_ADMIN_PASSWORD`; without it the admin menu stays locked) and which monitor is
  the chest screen.
- **`~/.config/monitors.xml`** from `deploy/monitors.xml`: GNOME's saved screen layouts. The chest
  screen is mounted upside down, so every layout that includes it, with or without the head
  screen, turns it 180°. GNOME keeps one layout per combination of connected screens; when you
  change the layout in GNOME Settings, copy `~/.config/monitors.xml` back into `deploy/`. The
  previous file is kept as `monitors.xml.bak-<date>`. It is used from the next login.
- **The GNOME extension `disable-gestures@semubot`** (via `install_disable_gestures.sh`), see below.

It also removes the older `~/.config/autostart/semubot-chest-display.desktop` and
`~/.local/bin/semubot-chest-display` launcher, which the service replaces.

### Window placement

`CHEST_DISPLAY_MONITOR` (in `chest_display.env`) is the chest monitor's connector name from
`xrandr --query`, e.g. `HDMI-2`. The app places its window on that monitor and checks every 2
seconds, moving the window if the monitor's position or size changes (for example when GNOME
applies the saved screen layout just after login, or a screen is rotated). It prints the position
it uses (`Chest display window: ...`) and every move to its log. `CHEST_DISPLAY_GEOMETRY`
(`WIDTHxHEIGHT+X+Y`) sets a fixed position instead. With neither, the app uses the desktop's full
reported size at `+0+0`. For a quick test outside the service:
`CHEST_DISPLAY_GEOMETRY=1024x600+0+0 python3 main.py`.

GNOME's own touchscreen gestures (three-finger swipe up opens the overview, edge swipes open
the on-screen keyboard) get in the way of the display. `install_disable_gestures.sh` (run by
`deploy/install.sh`) installs the `gnome-extension/` folder as the GNOME extension
`disable-gestures@semubot`, which turns those gestures off. On Wayland it takes effect after the next
login. Check it with `gnome-extensions info disable-gestures@semubot` (State: ACTIVE); undo it with
`gnome-extensions disable disable-gestures@semubot`.

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
`chest_display.json`. The admin password is `CHEST_DISPLAY_ADMIN_PASSWORD` in
`~/.config/semubot/chest_display.env` (see Install on the robot).

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
`CYCLONEDDS_URI=file:///home/semubot/cyclonedds.xml`. `deploy/start.sh` exports these
values before starting the app.

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

## Tic-tac-toe

**Admin menüü → Mängud → Trips-traps-trull** opens a game for visitors. The visitor is X and starts; the
robot is O, thinks for a moment and says a line out loud at the start and at the end of each game
(through `/speech_input`, in Estonian with the robot's current voice). The three winning squares
light up. **Raskus** switches between **Lihtne** (half of the robot's moves are random) and
**Raske** (the robot never loses); **Uus mäng** starts over. The score since the display started
is shown on the left.

**← Tagasi**, or 60 seconds without a touch, returns to the chest image, not to the admin menu,
so the robot can be left with visitors. The rules and the robot's moves are in `tictactoe.py`;
the spoken lines are `TICTACTOE_SPEECH` in `app.py`. Run the checks with
`python3 -m pytest tests/test_tictactoe.py` (the screen part needs a graphical display).

## Code layout

- `main.py` starts the app; `app.py` has the screens (`ChestDisplayApp`), saved settings and window
  placement.
- `ros_bridge.py` has every ROS 2 topic name the display uses and `RobotRos`, the node that talks
  on them.
- `audio_control.py`, `network_control.py` and `tictactoe.py` are the sound, Wi-Fi and game logic
  without any screens; `translations.py` has the English menu texts.
- Run the checks with `python3 -m pytest tests` in the desktop session (the screen tests need a
  graphical display).

## ROS 2 topics

All on `ROS_DOMAIN_ID=5`. "Latched" means transient-local QoS: a node that starts later still gets
the last value. Topic names are in `ros_bridge.py`; the other end must use the same name and type,
or the setting silently does nothing.

| Topic | Type | Chest display | Other end |
|---|---|---|---|
| `/face/background_color` | `String` `#RRGGBB`, latched | publishes | `semubot_eyes` (`eye_controller.py`) |
| `/semubot/speed_scale` | `Float32` 0.1–1.0, latched | publishes | Pi: `semubot_raspberry_bringup` (`cmd_vel_motor_driver.py`), multiplies `/cmd_vel` |
| `/semubot/mode` | `String` `manual`/`local`/`cloud` | publishes | `semubot_brain` (`llm_controller.py`); also the webapp |
| `/semubot/mode_state` | `String`, latched | subscribes | published by `semubot_brain`; also read by the webapp |
| `/speech_input` | `String` | publishes (text to say) | `semubot_brain`; also the webapp |
| `/semubot/tts_settings` | `String` JSON `{"speaker", "speed"}` | publishes | `semubot_brain` |
| `/semubot/tts_settings_state` | `String` JSON, plus `"speakers"`, latched | subscribes | published by `semubot_brain` |
| `/semubot/vad_threshold` | `Float32` | publishes | `semubot_brain` |
| `/semubot/vad_threshold_state` | `Float32`, latched | subscribes | published by `semubot_brain` |
| `/semubot/audio_level` | `Float32MultiArray` `[rms, speech probability]`, 10 Hz | subscribes | published by `semubot_brain` |
| `/semubot/conversation_log` | `String` JSON list, latched | subscribes | published by `semubot_brain`; also read by `semubot_eyes` |
| `/semubot/conversation_log_clear` | `Empty` | publishes | `semubot_brain` |
| `/semubot/cloud_usage` | `String` JSON, latched | subscribes | published by `semubot_brain` |
| `/semubot/state` | `String` JSON `{"stage", "mode", "since"}`, latched | subscribes | published by `semubot_brain`; also read by `semubot_eyes` |

`semubot_brain` and `semubot_eyes` are in `~/Speech_Recogniton_ws` on the NUC; the webapp talks
through rosbridge.
