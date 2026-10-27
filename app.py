"""Chest display: a default image and a password-protected image picker."""

import datetime
import json
import os
import queue
import random
import re
import shutil
import signal
import subprocess
import threading
import time
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox

from PIL import Image, ImageTk

from translations import translate

import audio_control as audio
from ros_bridge import RobotRos
import tictactoe
import network_control as network
from constants import ADMIN_PASSWORD, BACKGROUND_COLOR, BASE_DIR, COLOUR2, COLOUR5, LOGO_PATH, SWIPE_DISTANCE


IMAGE_DIR = os.path.join(BASE_DIR, "images")
SETTINGS_PATH = os.path.join(BASE_DIR, "chest_display.json")
IMAGE_CATEGORIES = {
    "logos": "Logod",
    "eyes": "Silmad",
    "mouths": "Suud",
    "other": "Muud",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
FACE_COLORS = {
    "Valge": "#FFFFFF",
    "Kreem": "#FFF4D6",
    "Helesinine": "#DDF4FF",
    "Mündiroheline": "#DDF9E8",
    "Heleroosa": "#FFE3EE",
    "Tume": "#202837",
}
DEFAULT_FACE_COLOR = "#FFFFFF"
VOICE_SAMPLE = "Tere! Mina olen Semu. Nii kõlab minu hääl."
TICTACTOE_EASY = 0.5  # chance the robot plays a random square on "Lihtne"
GAME_IDLE_SECONDS = 60  # a game nobody touches returns to the chest image
TICTACTOE_SPEECH = {  # the robot says one of these; speech stays Estonian like the TTS voice
    "start": ["Mängime trips-traps-trulli! Sina alustad."],
    "X": ["Palju õnne, sina võitsid!", "Hea mäng, seekord võitsid sina!"],
    "O": ["Mina võitsin! Proovi uuesti.", "Seekord võitsin mina!"],
    "draw": ["Viik! Hea mäng.", "Jäime viiki!"],
}
STAGES = {  # stage: (text, colour)
    "manual": ("⏸ Käsitsi režiim – ei kuula", "#555555"),
    "listening": ("● Kuulan", "#2e9d4f"),
    "recording": ("● Inimene räägib…", "#1f4e8c"),
    "transcribing": ("◐ Tuvastan kõnet…", "#b07a00"),
    "thinking": ("◐ Mõtlen ({mode})…", "#b07a00"),
    "synthesizing": ("◐ Valmistan kõnet…", "#b07a00"),
    "speaking": ("▶ Räägin…", "#00695c"),
}
LOG_LABELS = {  # kind: (prefix, text colour)
    "heard": ("Inimene", "#1f4e8c"),
    "said": ("Semu", "#00695c"),
    "typed": ("Operaator", "#6a1b9a"),
    "info": ("—", "#555555"),
    "error": ("Viga", "#b1483a"),
    "audio": ("Heli", "#777777"),  # recording saved / discarded, speech recognition found nothing
}
LEVEL_METER_MAX = 6000  # RMS shown at the right end of the level bar and slider
CALIBRATION_SECONDS = 5
SPEECH_MODES = {
    "manual": ("Käsitsi", "Robot ütleb ainult sisestatud teksti"),
    "local": ("Kohalik AI", "Robot kuulab ja vastab roboti enda keelemudeliga"),
    "cloud": ("Pilve AI", "Robot kuulab ja vastab pilvemudeliga (Claude/OpenAI)"),
}
DISPLAY_GEOMETRY_ENV = "CHEST_DISPLAY_GEOMETRY"
DISPLAY_MONITOR_ENV = "CHEST_DISPLAY_MONITOR"  # e.g. HDMI-2: follow this monitor's geometry
MONITOR_CHECK_MS = 2000


def display_geometry(screen_width, screen_height, value=None):
    """Return the requested window geometry and its drawable size."""
    if value is None:
        value = os.environ.get(DISPLAY_GEOMETRY_ENV)
    if not value:
        return f"{screen_width}x{screen_height}+0+0", screen_width, screen_height
    match = re.fullmatch(r"([1-9]\d*)x([1-9]\d*)\+(\d+)\+(\d+)", value)
    if match is None:
        raise ValueError(f"{DISPLAY_GEOMETRY_ENV} must be WIDTHxHEIGHT+X+Y")
    width, height, x, y = map(int, match.groups())
    return f"{width}x{height}+{x}+{y}", width, height


def monitor_geometry(name, xrandr_output):
    """WIDTHxHEIGHT+X+Y of the connected monitor `name` in `xrandr --query` output, or None."""
    for line in xrandr_output.splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[0] == name and fields[1] == "connected":
            for field in fields[2:]:
                if re.fullmatch(r"\d+x\d+\+\d+\+\d+", field):
                    return field
    return None


def current_monitor_geometry(name):
    try:
        result = subprocess.run(["xrandr", "--query"], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return monitor_geometry(name, result.stdout)


def opaque_edge_color(image):
    """'#RRGGBB' of the top-left pixel if all four corners are opaque, else None.

    Opaque images (e.g. a poster with its own background) are shown full screen on that
    colour; images with transparent corners (logos) are shown smaller on BACKGROUND_COLOR.
    """
    rgba = image.convert("RGBA")
    width, height = rgba.size
    corners = [rgba.getpixel(xy) for xy in ((0, 0), (width - 1, 0), (0, height - 1),
                                              (width - 1, height - 1))]
    if any(alpha < 255 for *_rgb, alpha in corners):
        return None
    red, green, blue, _alpha = corners[0]
    return f"#{red:02X}{green:02X}{blue:02X}"


def load_settings():
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as settings_file:
            settings = json.load(settings_file)
        return settings if isinstance(settings, dict) else {}
    except (OSError, ValueError):
        return {}


def save_setting(key, value):
    settings = load_settings()
    settings[key] = value
    temporary = SETTINGS_PATH + ".tmp"
    with open(temporary, "w", encoding="utf-8") as settings_file:
        json.dump(settings, settings_file)
    os.replace(temporary, SETTINGS_PATH)


def selected_face_color():
    color = load_settings().get("face_background_color")
    if isinstance(color, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
        return color.upper()
    return DEFAULT_FACE_COLOR


def selected_speed_scale():
    try:
        scale = float(load_settings().get("speed_scale", 1.0))
    except (TypeError, ValueError):
        return 1.0
    return min(max(round(scale, 1), 0.1), 1.0)


def available_images(category=None):
    """Return image labels and paths that can be selected in the admin screen."""
    if category is not None and category not in IMAGE_CATEGORIES:
        raise ValueError("Unknown image category")
    images = {}
    categories = (category,) if category else IMAGE_CATEGORIES
    for name in categories:
        folder = os.path.join(IMAGE_DIR, name)
        if os.path.isdir(folder):
            for filename in sorted(os.listdir(folder)):
                path = os.path.join(folder, filename)
                if os.path.isfile(path) and os.path.splitext(filename)[1].lower() in IMAGE_EXTENSIONS:
                    images[filename if category else f"{name}/{filename}"] = os.path.relpath(path, BASE_DIR)
    return images


def selected_image():
    selected = load_settings().get("image")
    if selected == "Naoilmed/Terve_nagu.PNG":
        selected = "images/other/Terve_nagu.PNG"
    if selected in available_images().values():
        return selected
    return LOGO_PATH


def save_selected_image(path):
    if path not in available_images().values():
        raise ValueError("Image is not available")
    save_setting("image", path)


def cloud_usage_text(usage, period, language="et"):
    """Short localized summary of cloud LLM use, e.g. '12 päringut, ~0.045 $'."""
    if not isinstance(usage, dict) or not isinstance(usage.get(period), dict):
        return ""
    data = usage[period]
    requests = data.get("requests", 0)
    tokens = data.get("input_tokens", 0) + data.get("output_tokens", 0)
    tokens_text = f"{tokens:,}".replace(",", " ")
    text = translate(language, "{requests} {request_word}, {tokens} sõnet",
                     requests=requests, tokens=tokens_text,
                     request_word=translate(language, "päring" if requests == 1 else "päringut"))
    if requests and data.get("unpriced", 0) < requests:
        cost = data.get("cost", 0.0)
        text += f", ~{cost:.3f} $" if cost < 1 else f", ~{cost:.2f} $"
        if data.get("unpriced"):
            text += translate(language, " (osaliselt hinnata)")
    elif requests:
        text += translate(language, " (hind teadmata)")
    return text


def import_image(source, category="logos"):
    """Copy a verified image into the chest display's local gallery."""
    if category not in IMAGE_CATEGORIES:
        raise ValueError("Unknown image category")
    with Image.open(source) as image:
        image.verify()
    extension = os.path.splitext(source)[1].lower()
    if extension not in IMAGE_EXTENSIONS:
        raise ValueError("Unsupported image format")
    folder = os.path.join(IMAGE_DIR, category)
    os.makedirs(folder, exist_ok=True)
    stem = os.path.splitext(os.path.basename(source))[0]
    destination = os.path.join(folder, stem + extension)
    index = 2
    while os.path.exists(destination):
        destination = os.path.join(folder, f"{stem} ({index}){extension}")
        index += 1
    shutil.copyfile(source, destination)
    return os.path.relpath(destination, BASE_DIR)


class ChestDisplayApp:
    def __init__(self, root, width, height):
        self.root = root
        language = load_settings().get("menu_language", "et")
        self.language = language if language in ("et", "en") else "et"
        self.width = width
        self.height = height
        self.ros = RobotRos(selected_face_color, selected_speed_scale)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.canvas = tk.Canvas(root, bg=BACKGROUND_COLOR, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.widgets = []
        self.photos = []
        self.swipe_start = None
        self.view_token = 0
        self.pending_face_color = None
        self.pending_image = None
        self.pending_image_category = "logos"
        self.speech_process = None
        self.speech_stopping = False
        self.speech_status = self.tr('Vali käsk')
        self.speech_status_label = None
        self.speech_buttons = []
        self.speech_stop_button = None
        self.pending_speech_mode = None
        self.tictactoe_mistakes = TICTACTOE_EASY
        self.tictactoe_score = {"O": 0, "X": 0, "draw": 0}  # since the display started
        self.show_display()

    def tr(self, text, **values):
        return translate(self.language, text, **values)

    def language_button(self, redraw):
        self.button("English" if self.language == "et" else "Eesti",
                    lambda: self.toggle_language(redraw),
                    relx=1, x=-20, y=20, anchor="ne", width=190, height=55)

    def toggle_language(self, redraw):
        language = "en" if self.language == "et" else "et"
        try:
            save_setting("menu_language", language)
        except OSError as error:
            messagebox.showerror(self.tr("Salvestamine ebaõnnestus"),
                                 str(error), parent=self.root)
            return
        self.language = language
        # Speech commands may still be running while the menu is open.
        if self.speech_process is None:
            self.speech_status = self.tr("Vali käsk")
        redraw()

    def close(self):
        if self.speech_process is not None and self.speech_process.poll() is None:
            self.speech_process.terminate()
        self.clear()
        self.ros.close()
        self.root.destroy()

    def clear(self, preserve_face_preview=False, preserve_image_preview=False):
        if self.pending_face_color is not None and not preserve_face_preview:
            self.ros.publish(selected_face_color())
            self.pending_face_color = None
        if not preserve_image_preview:
            self.pending_image = None
        self.view_token += 1
        self.canvas.delete("all")
        self.canvas.config(bg=BACKGROUND_COLOR)  # the main screen may have changed it
        self.canvas.unbind("<Button-1>")
        self.canvas.unbind("<ButtonRelease-1>")
        for widget in self.widgets:
            widget.destroy()
        self.widgets.clear()
        self.photos.clear()
        self.speech_status_label = None
        self.speech_buttons = []
        self.speech_stop_button = None

    def run_background(self, task, callback):
        """Run a slow system command without blocking the Tk event loop."""
        token = self.view_token
        results = queue.Queue(maxsize=1)

        def worker():
            try:
                results.put((task(), None))
            except Exception as error:
                results.put((None, error))

        threading.Thread(target=worker, daemon=True).start()

        def poll():
            if token != self.view_token:
                return
            try:
                value, error = results.get_nowait()
            except queue.Empty:
                self.root.after(100, poll)
                return
            callback(value, error)

        self.root.after(100, poll)

    def add(self, widget):
        self.widgets.append(widget)
        return widget

    def button(self, text, command, **place):
        button = self.add(tk.Button(
            self.root, text=text, command=command,
            font=("Arial", 18, "bold"), bg=COLOUR5, fg="black",
            activebackground=COLOUR2, relief="raised", bd=2,
        ))
        button.place(**place)
        return button

    def title(self, text):
        label = self.add(tk.Label(
            self.root, text=text, font=("Arial", 27, "bold"),
            bg=BACKGROUND_COLOR, fg="black",
        ))
        label.place(relx=0.5, rely=0.12, anchor="center")

    def draw_image(self, path, max_width, max_height, center_y):
        width = self.width
        try:
            with Image.open(os.path.join(BASE_DIR, path)) as image:
                image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(image.copy())
            self.photos.append(photo)
            self.canvas.create_image(width // 2, center_y, image=photo)
        except (OSError, ValueError):
            self.canvas.create_text(width // 2, center_y, text=self.tr('Pilti ei saa avada'),
                                    font=("Arial", 28), fill="black")

    def show_display(self):
        self.clear()
        width = self.width
        height = self.height
        path = selected_image()
        try:
            with Image.open(os.path.join(BASE_DIR, path)) as image:
                edge = opaque_edge_color(image)
        except (OSError, ValueError):
            edge = None
        if edge:  # an image with its own background: as large as fits, on its edge colour
            self.canvas.config(bg=edge)
            self.draw_image(path, width, height, height // 2)
        else:  # a logo with transparency: smaller, on the normal background
            self.draw_image(path, int(width * 0.8), int(height * 0.75), height // 2)
        self.canvas.bind("<Button-1>", lambda event: setattr(self, "swipe_start", event.y))
        self.canvas.bind("<ButtonRelease-1>", self.end_swipe)

    def end_swipe(self, event):
        if self.swipe_start is not None and self.swipe_start - event.y >= SWIPE_DISTANCE:
            self.show_login()

    def show_login(self):
        self.clear()
        self.title(self.tr('Admin sisenemine'))
        self.language_button(self.show_login)
        self.button(self.tr('← Tagasi'), self.show_display, x=20, y=20, width=145, height=55)
        entry = self.add(tk.Entry(self.root, font=("Arial", 25), show="*", justify="center"))
        entry.place(relx=0.5, rely=0.37, anchor="center", width=330, height=58)
        message = self.add(tk.Label(self.root, text="", font=("Arial", 17),
                                    bg=BACKGROUND_COLOR, fg="#b1483a"))
        message.place(relx=0.5, rely=0.46, anchor="center")

        def login():
            if not ADMIN_PASSWORD:
                message.config(text=self.tr('Admin parool pole seadistatud'))
            elif entry.get() == ADMIN_PASSWORD:
                self.show_admin()
            else:
                message.config(text=self.tr('Vale parool'))
                entry.delete(0, tk.END)

        entry.bind("<Return>", lambda _event: login())
        self.button(self.tr('Sisene'), login, relx=0.5, rely=0.59, anchor="center",
                    width=180, height=65)
        keyboard = self.add(tk.Frame(self.root, bg=BACKGROUND_COLOR))
        keyboard.place(relx=0.5, rely=0.79, anchor="center")
        for row in ("1234567890", "qwertyuiop", "asdfghjkl", "zxcvbnm"):
            line = tk.Frame(keyboard, bg=BACKGROUND_COLOR)
            line.pack()
            for character in row:
                tk.Button(line, text=character, font=("Arial", 15), width=3,
                          command=lambda value=character: entry.insert(tk.END, value)).pack(
                              side="left", padx=2, pady=2)
        tk.Button(keyboard, text=self.tr('⌫ Kustuta'), font=("Arial", 14),
                  command=lambda: entry.delete(max(0, len(entry.get()) - 1), tk.END)).pack(pady=3)
        entry.focus_set()

    def show_admin(self):
        self.clear()
        self.title(self.tr('Admin menüü'))
        self.language_button(self.show_admin)
        self.button(self.tr('← Tagasi'), self.show_display, x=20, y=20, width=145, height=55)
        buttons = (
            (self.tr('Muuda ekraani pilti'), self.show_gallery),
            (self.tr('Muuda näo taustavärvi'), self.show_face_colors),
            (self.tr('Heli seaded'), self.show_audio_settings),
            (self.tr('Wi-Fi seaded'), self.show_wifi_settings),
            (self.tr('Kõne'), self.show_speech),
            (self.tr('Kõnerežiim'), self.show_speech_mode),
            (self.tr('Sõidukiirus'), self.show_speed),
            (self.tr('Mängud'), self.show_games),
        )
        for index, (label, command) in enumerate(buttons):
            self.button(label, command, relx=0.5, rely=0.22 + index * 0.095,
                        anchor="center", width=320, height=min(60, int(self.height * 0.085)))

    def show_speed(self):
        """Scale the wheelbase's /cmd_vel speed in 0.1 steps between 0.1 and 1.0."""
        self.clear()
        self.title(self.tr('Sõidukiirus'))
        self.button(self.tr('← Tagasi'), self.show_admin, x=20, y=20, width=145, height=55)
        value = self.add(tk.Label(self.root, text="", font=("Arial", 48, "bold"),
                                  bg=BACKGROUND_COLOR))
        value.place(relx=0.5, rely=0.45, anchor="center")
        status = self.add(tk.Label(self.root, text="", font=("Arial", 17),
                                   bg=BACKGROUND_COLOR, wraplength=self.width - 80))
        status.place(relx=0.5, rely=0.72, anchor="center")

        def change(step):
            scale = min(max(round(selected_speed_scale() + step, 1), 0.1), 1.0)
            try:
                save_setting("speed_scale", scale)
            except OSError as error:
                messagebox.showerror(self.tr("Salvestamine ebaõnnestus"), str(error), parent=self.root)
                return
            show(scale, self.ros.publish_speed_scale(scale))

        def show(scale, sent):
            value.config(text=f"{scale:.1f}")
            minus.config(state="disabled" if scale <= 0.1 else "normal")
            plus.config(state="disabled" if scale >= 1.0 else "normal")
            status.config(text=self.tr('Saadetud robotile') if sent
                          else self.tr('ROS 2 pole saadaval: {v0}', v0=self.ros.error))

        minus = self.button("−", lambda: change(-0.1), relx=0.25, rely=0.45, anchor="center",
                            width=130, height=130)
        plus = self.button("+", lambda: change(0.1), relx=0.75, rely=0.45, anchor="center",
                           width=130, height=130)
        for button in (minus, plus):
            button.config(font=("Arial", 48, "bold"))
        show(selected_speed_scale(), self.ros.node is not None)

    def show_games(self):
        self.clear()
        self.title(self.tr('Mängud'))
        self.button(self.tr('← Tagasi'), self.show_admin, x=20, y=20, width=145, height=55)
        self.button(self.tr('Trips-traps-trull'), self.show_tictactoe, relx=0.5, rely=0.4,
                    anchor="center", width=320, height=min(60, int(self.height * 0.1)))

    def show_tictactoe(self):
        """Tic-tac-toe for visitors: they are X and start, the robot is O and talks.

        Back and the idle timeout go to the chest image, so visitors never land in the admin menu.
        """
        self.clear()
        self.title(self.tr('Trips-traps-trull'))
        self.button(self.tr('← Tagasi'), self.show_display, x=20, y=20, width=145, height=55)
        width, height = self.width, self.height
        cell = int(min(width * 0.38, height * 0.7) / 3)
        board = [""] * 9
        state = {"game": 0, "busy": False, "touched": time.monotonic()}
        token = self.view_token
        status = self.add(tk.Label(self.root, text="", font=("Arial", 22, "bold"),
                                   bg=BACKGROUND_COLOR, wraplength=int(width * 0.26)))
        status.place(relx=0.15, rely=0.45, anchor="center")
        score = self.add(tk.Label(self.root, text="", font=("Arial", 16),
                                  bg=BACKGROUND_COLOR, wraplength=int(width * 0.26)))
        score.place(relx=0.15, rely=0.65, anchor="center")
        cells = []
        for index in range(9):
            cells.append(self.button(
                "", lambda chosen=index: play(chosen),
                x=int(width / 2 + (index % 3 - 1.5) * cell), y=int(height * 0.56 + (index // 3 - 1.5) * cell),
                width=cell - 6, height=cell - 6))
            cells[-1].config(font=("Arial", cell // 3, "bold"))

        def level_text():
            level = 'Lihtne' if self.tictactoe_mistakes else 'Raske'
            return self.tr('Raskus: {v0}', v0=self.tr(level))

        def show_score():
            score.config(text=self.tr('Robot {v0} · Sina {v1} · Viik {v2}', v0=self.tictactoe_score["O"],
                                      v1=self.tictactoe_score["X"], v2=self.tictactoe_score["draw"]))

        def mark(index, player):
            board[index] = player
            cells[index].config(text=player, fg="#1f4e8c" if player == "X" else "#b1483a")

        def finish(result):
            self.tictactoe_score[result] += 1
            show_score()
            status.config(text=self.tr({"X": 'Sa võitsid!', "O": 'Robot võitis!', "draw": 'Viik!'}[result]))
            for line in tictactoe.LINES:
                if all(board[index] == result for index in line):
                    for index in line:
                        cells[index].config(bg=COLOUR2)
            self.ros.say(random.choice(TICTACTOE_SPEECH[result]))

        def play(index):
            state["touched"] = time.monotonic()
            if state["busy"] or board[index] or tictactoe.winner(board):
                return
            mark(index, "X")
            if tictactoe.winner(board):
                finish(tictactoe.winner(board))
                return
            state["busy"] = True
            status.config(text=self.tr('Robot mõtleb…'))
            self.root.after(700, lambda game=state["game"]: robot_turn(game))

        def robot_turn(game):
            if token != self.view_token or game != state["game"]:
                return
            mark(tictactoe.robot_move(board, "O", self.tictactoe_mistakes), "O")
            state["busy"] = False
            if tictactoe.winner(board):
                finish(tictactoe.winner(board))
            else:
                status.config(text=self.tr('Sinu kord'))

        def new_game():
            state.update(game=state["game"] + 1, busy=False, touched=time.monotonic())
            board[:] = [""] * 9
            for button in cells:
                button.config(text="", bg=COLOUR5)
            status.config(text=self.tr('Sinu kord'))

        def toggle_level():
            self.tictactoe_mistakes = 0.0 if self.tictactoe_mistakes else TICTACTOE_EASY
            level.config(text=level_text())
            new_game()

        def idle():
            if token != self.view_token:
                return
            if time.monotonic() - state["touched"] > GAME_IDLE_SECONDS:
                self.show_display()
                return
            self.root.after(1000, idle)

        side = dict(relx=0.85, anchor="center", width=min(240, width // 5), height=min(60, int(height * 0.1)))
        level = self.button(level_text(), toggle_level, rely=0.45, **side)
        self.button(self.tr('Uus mäng'), new_game, rely=0.62, **side)
        new_game()
        show_score()
        self.ros.say(random.choice(TICTACTOE_SPEECH["start"]))
        idle()

    def show_speech_mode(self):
        """Switch the robot between manual speech, local AI and cloud AI conversation."""
        self.clear()
        self.title(self.tr('Kõnerežiim'))
        self.button(self.tr('← Tagasi'), self.show_admin, x=20, y=20, width=145, height=55)
        width = self.width
        buttons = {}
        for index, (mode, (label, _description)) in enumerate(SPEECH_MODES.items()):
            buttons[mode] = self.button(
                self.tr(label), lambda chosen=mode: self.select_speech_mode(chosen),
                relx=0.2 + index * 0.3, rely=0.4, anchor="center",
                width=min(260, width // 4), height=110)
        description = self.add(tk.Label(self.root, text="", font=("Arial", 17),
                                        bg=BACKGROUND_COLOR, wraplength=width - 80))
        description.place(relx=0.5, rely=0.62, anchor="center")
        status = self.add(tk.Label(self.root, text="", font=("Arial", 17, "bold"),
                                   bg=BACKGROUND_COLOR, wraplength=width - 80))
        status.place(relx=0.5, rely=0.75, anchor="center")
        bottom_height = min(55, int(self.height * 0.11))
        for index, (label, command) in enumerate(((self.tr('Hääl →'), self.show_voice),
                                                  (self.tr('Mikrofon →'), self.show_microphone),
                                                  (self.tr('Vestlus →'), self.show_conversation))):
            self.button(label, command, relx=0.2 + index * 0.3, rely=0.9, anchor="center",
                        width=min(240, width // 4), height=bottom_height)
        token = self.view_token

        def refresh():
            if token != self.view_token:
                return
            mode = self.ros.speech_mode
            if mode == self.pending_speech_mode:
                self.pending_speech_mode = None
            for key, button in buttons.items():
                label = self.tr(SPEECH_MODES[key][0])
                if key == mode:
                    button.config(text=f"✓ {label}", bg=COLOUR2)
                elif key == self.pending_speech_mode:
                    button.config(text=self.tr('{v0}\n(ootan...)', v0=label), bg=COLOUR5)
                else:
                    button.config(text=label, bg=COLOUR5)
            text = self.tr(SPEECH_MODES[mode][1]) if mode in SPEECH_MODES else ""
            usage = cloud_usage_text(self.ros.cloud_usage, "today", self.language)
            description.config(text=self.tr('{v0}\nPilve AI täna: {v1}', v0=text, v1=usage) if usage else text)
            if self.ros.node is None:
                text = self.tr('ROS 2 pole saadaval: {v0}', v0=self.ros.error)
            elif self.ros.mode_error:
                text = self.tr('Režiimi saatmine ebaõnnestus: {v0}', v0=self.ros.mode_error)
            elif mode is None:
                text = self.tr('Roboti kõnesüsteem ei vasta (semu_brain_node ei tööta?)')
            else:
                text = self.tr('Robot on režiimis: {v0}', v0=self.tr(SPEECH_MODES.get(mode, (mode,))[0]))
            status.config(text=text)
            self.root.after(500, refresh)

        refresh()

    def select_speech_mode(self, mode):
        if mode not in SPEECH_MODES:
            raise ValueError("Unknown speech mode")
        if self.ros.publish_speech_mode(mode):
            self.pending_speech_mode = mode

    def show_voice(self):
        """Choose the robot's TTS voice and speaking speed."""
        self.clear()
        self.title(self.tr('Robotihääl'))
        self.button(self.tr('← Tagasi'), self.show_speech_mode, x=20, y=20, width=145, height=55)
        width, height = self.width, self.height
        grid = self.add(tk.Frame(self.root, bg=BACKGROUND_COLOR))
        grid.place(relx=0.5, rely=0.36, anchor="center")
        speed = tk.DoubleVar(value=1.0)
        slider = self.add(tk.Scale(
            self.root, from_=0.5, to=2.0, resolution=0.05, orient="horizontal",
            variable=speed, length=min(600, width - 120), width=30, sliderlength=50,
            font=("Arial", 14), bg=BACKGROUND_COLOR, highlightthickness=0,
            label=self.tr('Kiirus (1.0 = tavaline)')))
        slider.place(relx=0.5, rely=0.67, anchor="center")
        status = self.add(tk.Label(self.root, text="", font=("Arial", 15),
                                   bg=BACKGROUND_COLOR, wraplength=width - 60))
        status.place(relx=0.5, rely=0.95, anchor="center")
        state = {"dragging": False, "message": "", "speakers": None, "buttons": {}}

        def sent(ok, text):
            state["message"] = text if ok else self.tr('Saatmine ebaõnnestus')

        def choose(speaker):
            sent(self.ros.publish_tts_settings(speaker=speaker), self.tr('Hääl: {v0}', v0=speaker))

        def press(_event):
            state["dragging"] = True

        def release(_event):
            state["dragging"] = False
            sent(self.ros.publish_tts_settings(speed=round(speed.get(), 2)),
                 self.tr('Kiirus: {v0:.2f}', v0=speed.get()))

        slider.bind("<ButtonPress-1>", press)
        slider.bind("<ButtonRelease-1>", release)

        def try_voice():
            sent(self.ros.say(VOICE_SAMPLE), self.tr('Robot ütleb näidislause...'))

        self.button(self.tr('Proovi'), try_voice, relx=0.5, rely=0.84, anchor="center",
                    width=200, height=min(55, int(height * 0.11)))
        token = self.view_token
        columns = 5
        button_width = max(6, min(11, (width - 120) // (columns * 17)))

        def refresh():
            if token != self.view_token:
                return
            settings = self.ros.tts_settings or {}
            speakers = settings.get("speakers") or []
            current = settings.get("speaker")
            if speakers != state["speakers"]:
                state["speakers"] = speakers
                for button in state["buttons"].values():
                    button.destroy()
                state["buttons"] = {}
                for index, name in enumerate(speakers):
                    button = tk.Button(grid, text=name.capitalize(), font=("Arial", 17, "bold"),
                                       width=button_width, command=lambda chosen=name: choose(chosen))
                    button.grid(row=index // columns, column=index % columns, padx=5, pady=5)
                    state["buttons"][name] = button
            for name, button in state["buttons"].items():
                selected = name == current
                button.config(text=f"{'✓ ' if selected else ''}{name.capitalize()}",
                              bg=COLOUR2 if selected else COLOUR5)
            if isinstance(settings.get("speed"), (int, float)) and not state["dragging"]:
                if abs(speed.get() - settings["speed"]) > 0.001:
                    speed.set(settings["speed"])
            if self.ros.node is None:
                text = self.tr('ROS 2 pole saadaval: {v0}', v0=self.ros.error)
            elif not settings:
                text = self.tr('Roboti kõnesüsteem ei vasta (semu_brain_node ei tööta?)')
            elif not speakers:
                text = self.tr('Häälte loendit ei saadud (kas TTS teenus töötab?)')
            else:
                text = state["message"] or self.tr('Vali hääl ja kiirus. Proovi ütleb näidislause.')
            status.config(text=text)
            self.root.after(300, refresh)

        refresh()

    def show_conversation(self):
        """Live log of what the robot heard and said (kept by the robot in memory only)."""
        self.clear()
        self.title(self.tr('Vestlus'))
        self.button(self.tr('← Tagasi'), self.show_speech_mode, x=20, y=20, width=145, height=55)
        width, height = self.width, self.height
        frame = self.add(tk.Frame(self.root, bg=BACKGROUND_COLOR))
        stage_top = int(height * 0.12) + 30  # below the title
        stage_label = self.add(tk.Label(self.root, text="", font=("Arial", 18, "bold"),
                                        bg=BACKGROUND_COLOR, anchor="w"))
        stage_label.place(x=30, y=stage_top, width=width - 60, height=34)
        top = stage_top + 40
        frame.place(x=30, y=top, width=width - 60, height=height - top - 75)
        bar = tk.Scrollbar(frame, width=28)
        text = tk.Text(frame, font=("Arial", 16), wrap="word", bg="white", relief="solid",
                       bd=1, padx=10, pady=8, yscrollcommand=bar.set, cursor="arrow")
        bar.config(command=text.yview)
        bar.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)
        for kind, (_prefix, color) in LOG_LABELS.items():
            text.tag_configure(kind, foreground=color, font=("Arial", 16, "bold"))
        text.tag_configure("time", foreground="#888888", font=("Arial", 13))
        text.tag_configure("details", foreground="#888888", font=("Arial", 12), lmargin1=40)
        usage_label = self.add(tk.Label(self.root, text="", font=("Arial", 14),
                                        bg=BACKGROUND_COLOR, wraplength=width - 60))
        usage_label.place(relx=0.5, y=height - 40, anchor="center")
        state = {"shown": None}

        def clear_log():
            if not self.ros.clear_conversation_log():
                usage_label.config(text=self.tr('Logi tühjendamine ebaõnnestus'))

        self.button(self.tr('Tühjenda'), clear_log, relx=1, x=-20, y=20, anchor="ne", width=145, height=55)
        token = self.view_token

        def refresh():
            if token != self.view_token:
                return
            raw = self.ros.conversation_log
            if raw != state["shown"]:
                state["shown"] = raw
                try:
                    entries = json.loads(raw) if raw else None
                except ValueError:
                    entries = None
                text.config(state="normal")
                text.delete("1.0", "end")
                if self.ros.node is None:
                    text.insert("end", self.tr('ROS 2 pole saadaval: {v0}', v0=self.ros.error))
                elif entries is None:
                    text.insert("end", self.tr('Roboti kõnesüsteem ei vasta (semu_brain_node ei tööta?)'))
                elif not entries:
                    text.insert("end", self.tr('Vestlus on tühi. Siia ilmub, mida robot kuuleb ja ütleb.'))
                for entry in entries or []:
                    prefix, _color = LOG_LABELS.get(entry.get("kind"), ("?", "black"))
                    stamp = datetime.datetime.fromtimestamp(entry.get("time", 0)).strftime("%H:%M:%S")
                    text.insert("end", f"{stamp}  ", "time")
                    text.insert("end", f"{self.tr(prefix)}: " if entry.get("kind") != "info" else "— ",
                                entry.get("kind"))
                    text.insert("end", f"{entry.get('text', '')}\n")
                    if entry.get("details"):
                        text.insert("end", f"{entry['details']}\n", "details")
                text.config(state="disabled")
                text.see("end")
            robot = self.ros.robot_state or {}
            stage_text, stage_color = STAGES.get(robot.get("stage"), ("", "black"))
            if stage_text:
                mode_name = self.tr(SPEECH_MODES.get(robot.get("mode"), ("",))[0])
                seconds = max(0, int(time.time() - robot.get("since", time.time())))
                stage_label.config(text=f"{self.tr(stage_text, mode=mode_name)}  ({seconds} s)",
                                   fg=stage_color)
            else:
                stage_label.config(text=self.tr('Olek teadmata'), fg="#555555")
            today = cloud_usage_text(self.ros.cloud_usage, "today", self.language)
            month = cloud_usage_text(self.ros.cloud_usage, "month", self.language)
            if today:
                usage_label.config(text=self.tr('Pilve AI täna: {v0} · see kuu: {v1}', v0=today, v1=month))
            self.root.after(500, refresh)

        refresh()

    def show_microphone(self):
        """Live microphone level and the loudness threshold the robot reacts to."""
        self.clear()
        self.title(self.tr('Mikrofoni tundlikkus'))
        self.button(self.tr('← Tagasi'), self.show_speech_mode, x=20, y=20, width=145, height=55)
        width, height = self.width, self.height
        meter_width = width - 120
        meter = self.add(tk.Canvas(self.root, width=meter_width, height=56, bg="white",
                                   highlightthickness=2, highlightbackground="#375d58"))
        meter.place(relx=0.5, rely=0.3, anchor="center")
        readout = self.add(tk.Label(self.root, text="", font=("Arial", 16),
                                    bg=BACKGROUND_COLOR, wraplength=width - 60))
        readout.place(relx=0.5, rely=0.43, anchor="center")
        threshold = tk.DoubleVar(value=self.ros.vad_threshold or 1000)
        slider = self.add(tk.Scale(
            self.root, from_=0, to=LEVEL_METER_MAX, resolution=50, orient="horizontal",
            variable=threshold, length=meter_width, width=34, sliderlength=50,
            font=("Arial", 14), bg=BACKGROUND_COLOR, highlightthickness=0,
            label=self.tr('Lävi: vaiksemaid hääli ei kuulata')))
        slider.place(relx=0.5, rely=0.6, anchor="center")
        status = self.add(tk.Label(self.root, text="", font=("Arial", 15),
                                   bg=BACKGROUND_COLOR, wraplength=width - 60))
        status.place(relx=0.5, rely=0.94, anchor="center")
        state = {"dragging": False, "calibrate_until": None, "message": ""}

        def send(value):
            if self.ros.publish_vad_threshold(value):
                state["message"] = self.tr('Lävi saadetud: {v0:.0f}', v0=value)
            else:
                state["message"] = self.tr('Läve saatmine ebaõnnestus')

        def press(_event):
            state["dragging"] = True

        def release(_event):
            state["dragging"] = False
            send(threshold.get())

        slider.bind("<ButtonPress-1>", press)
        slider.bind("<ButtonRelease-1>", release)

        def calibrate():
            state["calibrate_until"] = time.monotonic() + CALIBRATION_SECONDS
            state["message"] = (self.tr('Räägi {v0} sekundit tavalise häälega sealt, kus inimesed robotiga räägivad...', v0=CALIBRATION_SECONDS))

        self.button(self.tr('Kalibreeri'), calibrate, relx=0.5, rely=0.79, anchor="center",
                    width=220, height=min(55, int(height * 0.11)))
        token = self.view_token

        def x_of(value):
            return int(min(max(value, 0), LEVEL_METER_MAX) / LEVEL_METER_MAX * meter_width)

        def refresh():
            if token != self.view_token:
                return
            reported = self.ros.vad_threshold
            if reported is not None and not state["dragging"] and \
                    state["calibrate_until"] is None and threshold.get() != reported:
                threshold.set(reported)
            levels = self.ros.recent_levels(1.0)
            rms, prob = levels[-1] if levels else (0.0, 0.0)
            gate = threshold.get()
            voice = prob >= 0.5
            color = "#2e9d4f" if voice and rms >= gate else "#e0a030" if voice else "#9aa5a8"
            meter.delete("all")
            meter.create_rectangle(0, 0, x_of(rms), 60, fill=color, width=0)
            meter.create_line(x_of(gate), 0, x_of(gate), 60, fill="#d32f2f", width=4)
            recent = self.ros.recent_levels(10.0)
            background = sorted(r for r, p in recent if p < 0.5)
            speech = [r for r, p in recent if p >= 0.5]
            if self.ros.node is None:
                readout.config(text=self.tr('ROS 2 pole saadaval: {v0}', v0=self.ros.error))
            elif not levels:
                readout.config(text=self.tr('Mikrofoni andmeid ei tule (semu_brain_node ei tööta?)'))
            else:
                parts = [self.tr('Helitase {v0:.0f}', v0=rms),
                         self.tr('KÕNE') if voice and rms >= gate else
                         self.tr('hääl, aga vaiksem kui lävi') if voice else self.tr('kõnet pole')]
                if background:
                    parts.append(self.tr('taust ~{v0:.0f}', v0=background[len(background) // 2]))
                if speech:
                    parts.append(self.tr('kõne kuni {v0:.0f}', v0=max(speech)))
                readout.config(text=" · ".join(parts))
            if state["calibrate_until"] is not None and time.monotonic() >= state["calibrate_until"]:
                state["calibrate_until"] = None
                voiced = sorted(r for r, p in self.ros.recent_levels(CALIBRATION_SECONDS) if p >= 0.5)
                if voiced:
                    value = round(voiced[len(voiced) // 2] * 0.5 / 50) * 50
                    threshold.set(value)
                    send(value)
                    state["message"] = (self.tr('Kalibreeritud: lävi {v0:.0f} (pool tavalise kõne helitasemest)', v0=value))
                else:
                    state["message"] = self.tr('Kõnet ei tuvastatud, proovi uuesti lähemalt.')
            status.config(text=state["message"] or
                          self.tr('Roheline = robot kuulab. Kollane = hääl on liiga vaikne. Punane joon = lävi.'))
            self.root.after(100, refresh)

        refresh()

    def show_speech(self):
        self.clear()
        self.title(self.tr('Kõne'))
        self.button(self.tr('← Tagasi'), self.show_admin, x=20, y=20, width=145, height=55)
        width = self.width
        button_width = min(260, width // 3)
        self.speech_buttons = [
            self.button("sayhi", lambda: self.start_speech(("sayhi",)),
                        relx=0.32, rely=0.48, anchor="center",
                        width=button_width, height=110),
            self.button("speak -a", lambda: self.start_speech(("speak", "-a")),
                        relx=0.68, rely=0.48, anchor="center",
                        width=button_width, height=110),
        ]
        self.speech_stop_button = self.button(
            self.tr('Peata'), self.stop_speech, relx=0.5, rely=0.7,
            anchor="center", width=180, height=55)
        self.speech_status_label = self.add(tk.Label(
            self.root, text=self.speech_status, font=("Arial", 17),
            bg=BACKGROUND_COLOR, wraplength=width - 80,
        ))
        self.speech_status_label.place(relx=0.5, rely=0.85, anchor="center")
        self.refresh_speech_controls()

    def refresh_speech_controls(self):
        running = self.speech_process is not None and self.speech_process.poll() is None
        for button in self.speech_buttons:
            button.config(state="disabled" if running else "normal")
        if self.speech_stop_button is not None:
            self.speech_stop_button.config(state="normal" if running else "disabled")
        if self.speech_status_label is not None:
            self.speech_status_label.config(text=self.speech_status)

    def start_speech(self, command):
        if self.speech_process is not None and self.speech_process.poll() is None:
            self.speech_status = self.tr('Kõnekäsk juba töötab')
            self.refresh_speech_controls()
            return
        try:
            self.speech_process = subprocess.Popen(
                command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            self.speech_process = None
            self.speech_status = self.tr('Käsku {v0} ei leitud. Kontrolli PATH keskkonnamuutujat.', v0=command[0])
            self.refresh_speech_controls()
            return
        except OSError as error:
            self.speech_process = None
            self.speech_status = self.tr('Käsu käivitamine ebaõnnestus: {v0}', v0=error)
            self.refresh_speech_controls()
            return
        self.speech_stopping = False
        self.speech_status = self.tr('Käivitatud: {v0}', v0=' '.join(command))
        self.refresh_speech_controls()
        process = self.speech_process
        self.root.after(250, lambda: self.poll_speech(process))

    def poll_speech(self, process):
        if process is not self.speech_process:
            return
        code = process.poll()
        if code is None:
            self.root.after(250, lambda: self.poll_speech(process))
            return
        self.speech_status = (
            self.tr('Kõnekäsk peatatud') if self.speech_stopping else
            self.tr('Kõnekäsk lõpetas') if code == 0 else
            self.tr('Kõnekäsk lõpetas veakoodiga {v0}', v0=code))
        self.speech_process = None
        self.speech_stopping = False
        self.refresh_speech_controls()

    def stop_speech(self):
        if self.speech_process is not None and self.speech_process.poll() is None:
            self.speech_process.terminate()
            self.speech_stopping = True
            self.speech_status = self.tr('Peatan kõnekäsku...')
            self.refresh_speech_controls()

    def show_audio_settings(self):
        self.clear()
        self.title(self.tr('Heli seaded'))
        self.button(self.tr('← Tagasi'), self.show_admin, x=20, y=20, width=145, height=55)
        self.button(self.tr('Värskenda'), self.show_audio_settings, relx=1, x=-20, y=20,
                    anchor="ne", width=145, height=55)
        width = self.width
        height = self.height

        status = self.add(tk.Label(self.root, text="", font=("Arial", 15),
                                   bg=BACKGROUND_COLOR, fg="black",
                                   wraplength=width - 80))
        status.place(relx=0.5, rely=0.96, anchor="center")
        self.audio_status = status
        try:
            outputs = audio.list_outputs()
            current = audio.default_output()
            volume = audio.volume_percent()
        except audio.AudioError as error:
            status.config(text=self.tr('Heliteenus pole saadaval: {v0}', v0=error))
            return False

        if not outputs:
            status.config(text=self.tr('Heliväljundeid ei leitud'))
            return False

        label = self.add(tk.Label(self.root, text=self.tr('Helitugevus: {v0}%', v0=volume),
                                  font=("Arial", 21, "bold"), bg=BACKGROUND_COLOR))
        label.place(relx=0.5, rely=0.25, anchor="center")
        slider = self.add(tk.Scale(self.root, from_=0, to=100, orient="horizontal",
                                   length=min(600, width - 100), font=("Arial", 15),
                                   bg=BACKGROUND_COLOR, showvalue=True, resolution=5))
        slider.set(volume)
        slider.place(relx=0.5, rely=0.36, anchor="center")

        def apply_volume():
            try:
                audio.set_volume_percent(slider.get())
                label.config(text=self.tr('Helitugevus: {v0}%', v0=slider.get()))
                status.config(text=self.tr('Helitugevus muudetud'))
            except (audio.AudioError, ValueError) as error:
                status.config(text=self.tr('Helitugevuse muutmine ebaõnnestus: {v0}', v0=error))

        self.button(self.tr('Rakenda helitugevus'), apply_volume, relx=0.5, rely=0.48,
                    anchor="center", width=260, height=55)

        def test_sound():
            status.config(text=self.tr('Mängin testheli...'))
            self.run_background(audio.play_test_sound, lambda _value, error: status.config(
                text=self.tr('Testheli ebaõnnestus: {v0}', v0=error) if error else self.tr('Testheli mängitud')))

        self.button(self.tr('Testheli'), test_sound, relx=0.82, rely=0.48,
                    anchor="center", width=150, height=55)

        device_label = self.add(tk.Label(self.root, text=self.tr('Heliväljund'), font=("Arial", 21, "bold"),
                                         bg=BACKGROUND_COLOR))
        device_label.place(relx=0.5, rely=0.59, anchor="center")
        frame = self.add(tk.Frame(self.root, bg=BACKGROUND_COLOR))
        frame.place(relx=0.5, rely=0.73, anchor="center",
                    width=min(680, width - 80), height=max(100, int(height * 0.19)))
        scrollbar = tk.Scrollbar(frame, orient="vertical")
        devices = tk.Listbox(frame, font=("Arial", 15), selectmode="single",
                             yscrollcommand=scrollbar.set, exportselection=False)
        scrollbar.config(command=devices.yview)
        scrollbar.pack(side="right", fill="y")
        devices.pack(side="left", fill="both", expand=True)
        for index, (name, description) in enumerate(outputs):
            devices.insert("end", f"{'● ' if name == current else '   '}{description}")
            if name == current:
                devices.selection_set(index)
                devices.see(index)

        def apply_output():
            selection = devices.curselection()
            if not selection:
                status.config(text=self.tr('Vali loendist heliväljund'))
                return
            name, description = outputs[selection[0]]
            try:
                audio.set_default_output(name)
            except (audio.AudioError, ValueError) as error:
                status.config(text=self.tr('Heliväljundi muutmine ebaõnnestus: {v0}', v0=error))
                return
            if self.show_audio_settings():
                self.audio_status.config(text=self.tr('Heliväljund: {v0}', v0=description))

        self.button(self.tr('Vali heliväljund'), apply_output, relx=0.5, rely=0.88,
                    anchor="center", width=260, height=55)
        return True

    def show_wifi_settings(self, notice=None):
        self.clear()
        self.title(self.tr('Wi-Fi seaded'))
        self.button(self.tr('← Tagasi'), self.show_admin, x=20, y=20, width=145, height=55)
        self.button(self.tr('Värskenda'), self.show_wifi_settings, relx=1, x=-20, y=20,
                    anchor="ne", width=145, height=55)
        width = self.width
        height = self.height
        current = self.add(tk.Label(self.root, text=self.tr('Ühendus: skannin...'),
                                    font=("Arial", 18, "bold"), bg=BACKGROUND_COLOR))
        current.place(relx=0.5, rely=0.23, anchor="center")
        address = self.add(tk.Label(self.root, text=self.tr('IPv4: otsin...'), font=("Arial", 16),
                                    bg=BACKGROUND_COLOR, wraplength=width - 80))
        address.place(relx=0.5, rely=0.32, anchor="center")
        frame = self.add(tk.Frame(self.root, bg=BACKGROUND_COLOR))
        frame.place(relx=0.5, rely=0.63, anchor="center",
                    width=min(760, width - 80), height=max(130, int(height * 0.35)))
        scrollbar = tk.Scrollbar(frame, orient="vertical")
        choices = tk.Listbox(frame, font=("Arial", 16), selectmode="single",
                             yscrollcommand=scrollbar.set, exportselection=False)
        scrollbar.config(command=choices.yview)
        scrollbar.pack(side="right", fill="y")
        choices.pack(side="left", fill="both", expand=True)
        status = self.add(tk.Label(self.root, text=self.tr('Skannin võrke...'), font=("Arial", 15),
                                   bg=BACKGROUND_COLOR, wraplength=width - 80))
        status.place(relx=0.5, rely=0.96, anchor="center")
        networks = []

        def scan():
            try:
                found, scan_error = network.list_wifi_networks(), None
            except network.NetworkError as error:
                found, scan_error = [], error
            try:
                addresses, address_error = network.ipv4_addresses(), None
            except network.NetworkError as error:
                addresses, address_error = [], error
            return found, scan_error, addresses, address_error

        def scan_finished(result, error):
            nonlocal networks
            if error:
                status.config(text=self.tr('Võrkude otsimine ebaõnnestus: {v0}', v0=error))
                return
            networks, scan_error, addresses, address_error = result
            active = next((item.ssid for item in networks if item.active), None)
            current.config(text=self.tr('Ühendus: {v0}', v0=active or self.tr('puudub')))
            if address_error:
                address.config(text=self.tr('IPv4: ei saa lugeda ({v0})', v0=address_error))
            elif addresses:
                address.config(text="IPv4: " + "; ".join(
                    f"{device} {ip}" for device, ip in addresses))
            else:
                address.config(text=self.tr('IPv4: aadress puudub'))
            for item in networks:
                lock = "" if item.security in ("", "--") else "🔒 "
                choices.insert("end", f"{'● ' if item.active else '   '}{lock}{item.ssid}  ({item.signal}%)")
            if scan_error:
                status.config(text=self.tr('Wi-Fi pole saadaval: {v0}', v0=scan_error))
            elif notice:
                status.config(text=notice)
            elif not networks:
                status.config(text=self.tr('Wi-Fi võrke ei leitud'))
            else:
                status.config(text=self.tr('Vali võrk ja vajuta Ühenda'))

        self.run_background(scan, scan_finished)

        def connect_selected():
            selection = choices.curselection()
            if not selection or selection[0] >= len(networks):
                status.config(text=self.tr('Vali loendist Wi-Fi võrk'))
                return
            selected = networks[selection[0]]
            if selected.active:
                status.config(text=self.tr('See Wi-Fi võrk on juba ühendatud'))
            elif "802.1X" in selected.security:
                status.config(text=self.tr('See ettevõtte Wi-Fi võrk vajab eraldi konto seadistust'))
            elif selected.security in ("", "--"):
                self.connect_wifi(selected.ssid, "", status, connect_button)
            else:
                self.show_wifi_password(selected.ssid)

        connect_button = self.button(self.tr('Ühenda'), connect_selected, relx=0.5, rely=0.88,
                                     anchor="center", width=180, height=55)

    def show_wifi_password(self, ssid):
        self.clear()
        self.title(self.tr('Wi-Fi parool'))
        self.button(self.tr('← Tagasi'), self.show_wifi_settings, x=20, y=20, width=145, height=55)
        width = self.width
        name = self.add(tk.Label(self.root, text=ssid, font=("Arial", 18, "bold"),
                                 bg=BACKGROUND_COLOR, wraplength=width - 80))
        name.place(relx=0.5, rely=0.21, anchor="center")
        entry = self.add(tk.Entry(self.root, font=("Arial", 22), show="*", justify="center"))
        entry.place(relx=0.5, rely=0.3, anchor="center", width=min(480, width - 100), height=48)
        visible = tk.BooleanVar(value=False)
        toggle = self.add(tk.Checkbutton(
            self.root, text=self.tr('Näita parooli'), variable=visible, font=("Arial", 14),
            bg=BACKGROUND_COLOR,
            command=lambda: entry.config(show="" if visible.get() else "*"),
        ))
        toggle.place(relx=0.5, rely=0.38, anchor="center")
        keyboard = self.add(tk.Frame(self.root, bg=BACKGROUND_COLOR))
        keyboard.place(relx=0.5, rely=0.64, anchor="center")
        state = {"shift": False, "symbols": False}

        def draw_keyboard():
            for child in keyboard.winfo_children():
                child.destroy()
            rows = ("1234567890", "qwertyuiop", "asdfghjkl", "zxcvbnm")
            if state["symbols"]:
                rows = ("1234567890", "!@#$%^&*()", "-_=+[]{};:", "',.<>/?\\|")
            elif state["shift"]:
                rows = tuple(row.upper() for row in rows)
            for row in rows:
                line = tk.Frame(keyboard, bg=BACKGROUND_COLOR)
                line.pack()
                for character in row:
                    tk.Button(line, text=character, font=("Arial", 14), width=3,
                              command=lambda value=character: entry.insert(tk.END, value)).pack(
                                  side="left", padx=1, pady=1)
            controls = tk.Frame(keyboard, bg=BACKGROUND_COLOR)
            controls.pack()

            def switch(key):
                state[key] = not state[key]
                draw_keyboard()

            tk.Button(controls, text="⇧ Shift", font=("Arial", 13),
                      command=lambda: switch("shift")).pack(side="left", padx=4)
            tk.Button(controls, text=self.tr('Sümbolid'), font=("Arial", 13),
                      command=lambda: switch("symbols")).pack(side="left", padx=4)
            tk.Button(controls, text=self.tr('Tühik'), font=("Arial", 13),
                      command=lambda: entry.insert(tk.END, " ")).pack(side="left", padx=4)
            tk.Button(controls, text="⌫", font=("Arial", 13),
                      command=lambda: entry.delete(max(0, len(entry.get()) - 1), tk.END)).pack(
                          side="left", padx=4)

        draw_keyboard()
        status = self.add(tk.Label(self.root, text="", font=("Arial", 15),
                                   bg=BACKGROUND_COLOR, wraplength=width - 80))
        status.place(relx=0.5, rely=0.96, anchor="center")
        connect_button = self.button(
            self.tr('Ühenda'), lambda: self.connect_wifi(ssid, entry.get(), status, connect_button),
            relx=0.5, rely=0.88, anchor="center", width=180, height=55)
        entry.focus_set()

    def connect_wifi(self, ssid, password, status, button):
        button.config(state="disabled")
        status.config(text=self.tr('Ühendan Wi-Fi võrguga...'))

        def finished(_result, error):
            if error:
                status.config(text=self.tr('Ühendamine ebaõnnestus: {v0}', v0=error))
                button.config(state="normal")
            else:
                self.show_wifi_settings(notice=self.tr('Ühendatud: {v0}', v0=ssid))

        self.run_background(lambda: network.connect_wifi(ssid, password), finished)

    def show_face_colors(self):
        self.clear(preserve_face_preview=True)
        self.title(self.tr('Näo taustavärv'))
        self.button(self.tr('← Tagasi'), self.show_admin, x=20, y=20, width=145, height=55)
        current = self.pending_face_color or selected_face_color()
        width = self.width
        height = self.height
        channels = [int(current[index:index + 2], 16) for index in (1, 3, 5)]
        caption = self.tr('Eelvaade') if self.pending_face_color else self.tr('Salvestatud')
        preview = self.add(tk.Label(self.root, text=f"{caption}: {current}",
                                    font=("Arial", 17, "bold"), bg=current,
                                    fg="black" if sum(channels) > 380 else "white",
                                    relief="solid", bd=2))
        preview.place(relx=0.5, rely=0.23, anchor="center", width=240, height=50)
        for index, (name, color) in enumerate(FACE_COLORS.items()):
            row, column = divmod(index, 3)
            button = self.add(tk.Button(
                self.root, text=f"{'✓ ' if color == current else ''}{self.tr(name)}",
                font=("Arial", 19, "bold"), bg=color,
                fg="white" if color == FACE_COLORS["Tume"] else "black",
                command=lambda chosen=color: self.select_face_color(chosen),
                relief="raised", bd=3,
            ))
            button.place(x=int(width * (0.25 + 0.25 * column)),
                         y=int(height * (0.38 + 0.3 * row)),
                         anchor="center", width=width // 5, height=height // 5)
        self.button(self.tr('Muu värv...'), self.choose_face_color,
                    relx=0.82, rely=0.23, anchor="center", width=170, height=50)
        save_button = self.button(self.tr('Salvesta'), self.save_face_color,
                                  relx=0.4, rely=0.84, anchor="center", width=180, height=55)
        undo_button = self.button(self.tr('Võta tagasi'), self.undo_face_color,
                                  relx=0.6, rely=0.84, anchor="center", width=180, height=55)
        if self.pending_face_color is None:
            save_button.config(state="disabled")
            undo_button.config(state="disabled")
        status = self.tr('Vali värv eelvaateks. Muudatus salvestub alles pärast Salvesta vajutamist.')
        if self.pending_face_color is not None:
            status = self.tr('Eelvaade on näo ekraanil. Salvesta või võta tagasi.')
        if self.ros.node is None:
            status = self.tr('ROS 2 pole saadaval; eelvaade on ainult siin. Salvesta jätab värvi järgmise käivituse jaoks.')
        elif self.ros.error:
            status = self.tr('Värvi saatmine ebaõnnestus: {v0}', v0=self.ros.error)
        label = self.add(tk.Label(self.root, text=status, font=("Arial", 15),
                                  bg=BACKGROUND_COLOR, fg="black", wraplength=width - 60))
        label.place(relx=0.5, rely=0.95, anchor="center")

    def choose_face_color(self):
        _rgb, color = colorchooser.askcolor(
            color=self.pending_face_color or selected_face_color(), parent=self.root)
        if color:
            self.select_face_color(color)

    def select_face_color(self, color):
        if not isinstance(color, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
            raise ValueError("Invalid face background color")
        color = color.upper()
        self.pending_face_color = color
        self.ros.publish(color)
        self.show_face_colors()

    def save_face_color(self):
        if self.pending_face_color is None:
            return
        try:
            save_setting("face_background_color", self.pending_face_color)
        except OSError as error:
            messagebox.showerror(self.tr('Salvestamine ebaõnnestus'), str(error), parent=self.root)
            return
        self.pending_face_color = None
        self.show_face_colors()

    def undo_face_color(self):
        if self.pending_face_color is None:
            return
        self.ros.publish(selected_face_color())
        self.pending_face_color = None
        self.show_face_colors()

    def show_gallery(self, category="logos"):
        self.clear()
        self.title(self.tr('Vali rinnaekraani pilt'))
        self.button(self.tr('← Tagasi'), self.show_admin, x=20, y=20, width=145, height=55)
        self.button(self.tr('Lisa pilt'), lambda: self.choose_file(category), relx=1, x=-20, y=20,
                    anchor="ne", width=145, height=55)

        tabs = self.add(tk.Frame(self.root, bg=BACKGROUND_COLOR))
        tabs.place(relx=0.5, y=115, anchor="center")
        for key, label in IMAGE_CATEGORIES.items():
            tk.Button(tabs, text=self.tr(label), font=("Arial", 16, "bold"),
                      bg=COLOUR2 if key == category else COLOUR5,
                      command=lambda chosen=key: self.show_gallery(chosen),
                      width=10).pack(side="left", padx=6)

        width = self.width
        height = self.height
        frame = self.add(tk.Frame(self.root, bg=BACKGROUND_COLOR))
        frame.place(x=30, y=160, width=width - 60, height=height - 180)
        scroller = tk.Canvas(frame, bg=BACKGROUND_COLOR, highlightthickness=0)
        bar = tk.Scrollbar(frame, command=scroller.yview)
        scroller.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        scroller.pack(side="left", fill="both", expand=True)
        grid = tk.Frame(scroller, bg=BACKGROUND_COLOR)
        scroller.create_window((0, 0), window=grid, anchor="nw")
        grid.bind("<Configure>", lambda _event: scroller.configure(scrollregion=scroller.bbox("all")))
        scroller.bind("<MouseWheel>", lambda event: scroller.yview_scroll(-int(event.delta / 120), "units"))

        columns = max(1, (width - 80) // 230)
        images = available_images(category)
        if not images:
            scroller.create_text(25, 30, anchor="nw",
                                 text=self.tr('Selles kaustas pole pilte. Lisa pilt kausta images/{v0}/.', v0=category),
                                 font=("Arial", 17), fill="black")
        for index, (label, path) in enumerate(images.items()):
            card = tk.Frame(grid, bg=BACKGROUND_COLOR)
            card.grid(row=index // columns, column=index % columns, padx=10, pady=10)
            try:
                with Image.open(os.path.join(BASE_DIR, path)) as image:
                    image.thumbnail((190, 145), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(image.copy())
                self.photos.append(photo)
                tk.Button(card, image=photo, bg="white", width=200, height=155,
                          command=lambda selected=path, group=category: self.select_image(selected, group)).pack()
            except (OSError, ValueError):
                continue
            tk.Button(card, text=label, font=("Arial", 14), wraplength=190,
                      bg=COLOUR2 if path == selected_image() else COLOUR5,
                      command=lambda selected=path, group=category: self.select_image(selected, group),
                      width=20, height=2).pack(pady=4)

    def select_image(self, path, category="logos"):
        if path not in available_images(category).values():
            raise ValueError("Image is not available")
        self.pending_image = path
        self.pending_image_category = category
        self.show_image_preview()

    def show_image_preview(self):
        if self.pending_image is None:
            self.show_gallery(self.pending_image_category)
            return
        self.clear(preserve_image_preview=True)
        self.title(self.tr('Rinnaekraani eelvaade'))
        width = self.width
        height = self.height
        self.draw_image(self.pending_image, int(width * 0.8), int(height * 0.55),
                        int(height * 0.47))
        label = self.add(tk.Label(
            self.root, text=self.tr('{v0} — salvesta või võta tagasi', v0=os.path.basename(self.pending_image)),
            font=("Arial", 17), bg=BACKGROUND_COLOR, wraplength=width - 80,
        ))
        label.place(relx=0.5, rely=0.76, anchor="center")
        self.button(self.tr('Salvesta'), self.save_image_preview, relx=0.4, rely=0.88,
                    anchor="center", width=180, height=60)
        self.button(self.tr('Võta tagasi'), self.undo_image_preview, relx=0.6, rely=0.88,
                    anchor="center", width=180, height=60)

    def save_image_preview(self):
        if self.pending_image is None:
            return
        try:
            save_selected_image(self.pending_image)
        except (OSError, ValueError) as error:
            messagebox.showerror(self.tr('Salvestamine ebaõnnestus'), str(error), parent=self.root)
            return
        self.pending_image = None
        self.show_display()

    def undo_image_preview(self):
        category = self.pending_image_category
        self.pending_image = None
        self.show_gallery(category)

    def choose_file(self, category):
        source = filedialog.askopenfilename(
            title=self.tr('Vali pilt'), filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp")],
        )
        if source:
            try:
                path = import_image(source, category)
                self.select_image(path, category)
            except (OSError, ValueError) as error:
                messagebox.showerror(self.tr('Pildi lisamine ebaõnnestus'), str(error))


def start_gui():
    root = tk.Tk()
    root.title("SemuBot chest display")
    monitor = os.environ.get(DISPLAY_MONITOR_ENV)
    follow = bool(monitor) and not os.environ.get(DISPLAY_GEOMETRY_ENV)
    found = current_monitor_geometry(monitor) if follow else None
    geometry, width, height = display_geometry(root.winfo_screenwidth(), root.winfo_screenheight(),
                                               found)
    print(f"Chest display window: {geometry}"
          + (f" (monitor {monitor})" if found else f" (monitor {monitor} not found)" if follow else ""),
          flush=True)
    root.geometry(geometry)
    root.overrideredirect(True)
    app = ChestDisplayApp(root, width, height)
    shown = {"geometry": geometry}

    def follow_monitor():
        """Keep the window on the chest monitor when the screen layout changes after start
        (GNOME may still be applying the saved layout at login, or a screen gets rotated)."""
        current = current_monitor_geometry(monitor)
        if current and current != shown["geometry"]:
            print(f"Monitor {monitor} is now at {current}; moving the window there", flush=True)
            new_geometry, new_width, new_height = display_geometry(0, 0, current)
            root.geometry(new_geometry)
            if (new_width, new_height) != (app.width, app.height):
                app.width, app.height = new_width, new_height
                app.show_display()
            shown["geometry"] = current
        root.after(MONITOR_CHECK_MS, follow_monitor)

    if follow:
        root.after(MONITOR_CHECK_MS, follow_monitor)
    for signal_number in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signal_number, lambda *_args: app.close())

    def let_python_handle_signals():
        root.after(250, let_python_handle_signals)

    let_python_handle_signals()
    root.mainloop()
