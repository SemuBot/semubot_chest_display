"""Chest display: a default image and a password-protected image picker."""

import json
import os
import queue
import re
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox

from PIL import Image, ImageTk

import audio_control as audio
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
FACE_COLOR_TOPIC = "/face/background_color"
DISPLAY_GEOMETRY_ENV = "CHEST_DISPLAY_GEOMETRY"


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


class FaceColorPublisher:
    """Keep a ROS publisher alive for the lifetime of the chest display."""

    def __init__(self):
        self.node = None
        self.error = None
        try:
            import rclpy
            from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
            from std_msgs.msg import String

            rclpy.init()
            self.rclpy = rclpy
            self.message_type = String
            self.node = rclpy.create_node("chest_display")
            qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                             reliability=ReliabilityPolicy.RELIABLE)
            self.publisher = self.node.create_publisher(String, FACE_COLOR_TOPIC, qos)
            self.publish(selected_face_color())
        except Exception as error:
            self.error = str(error)
            if self.node is not None:
                self.node.destroy_node()
                self.node = None
            if hasattr(self, "rclpy") and self.rclpy.ok():
                self.rclpy.shutdown()

    def publish(self, color):
        if self.node is None:
            return False
        try:
            self.publisher.publish(self.message_type(data=color))
            self.error = None
            return True
        except Exception as error:
            self.error = str(error)
            return False

    def close(self):
        if self.node is not None:
            self.node.destroy_node()
            self.rclpy.shutdown()


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
        self.width = width
        self.height = height
        self.face_colors = FaceColorPublisher()
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
        self.speech_status = "Vali käsk"
        self.speech_status_label = None
        self.speech_buttons = []
        self.speech_stop_button = None
        self.show_display()

    def close(self):
        if self.speech_process is not None and self.speech_process.poll() is None:
            self.speech_process.terminate()
        self.clear()
        self.face_colors.close()
        self.root.destroy()

    def clear(self, preserve_face_preview=False, preserve_image_preview=False):
        if self.pending_face_color is not None and not preserve_face_preview:
            self.face_colors.publish(selected_face_color())
            self.pending_face_color = None
        if not preserve_image_preview:
            self.pending_image = None
        self.view_token += 1
        self.canvas.delete("all")
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
            self.canvas.create_text(width // 2, center_y, text="Pilti ei saa avada",
                                    font=("Arial", 28), fill="black")

    def show_display(self):
        self.clear()
        width = self.width
        height = self.height
        self.draw_image(selected_image(), int(width * 0.8), int(height * 0.75), height // 2)
        self.canvas.create_text(width // 2, height - 45, text="↑ Tõmba üles, et avada seaded",
                                font=("Arial", 17), fill="#375d58")
        self.canvas.bind("<Button-1>", lambda event: setattr(self, "swipe_start", event.y))
        self.canvas.bind("<ButtonRelease-1>", self.end_swipe)

    def end_swipe(self, event):
        if self.swipe_start is not None and self.swipe_start - event.y >= SWIPE_DISTANCE:
            self.show_login()

    def show_login(self):
        self.clear()
        self.title("Admin sisenemine")
        self.button("← Tagasi", self.show_display, x=20, y=20, width=145, height=55)
        entry = self.add(tk.Entry(self.root, font=("Arial", 25), show="*", justify="center"))
        entry.place(relx=0.5, rely=0.37, anchor="center", width=330, height=58)
        message = self.add(tk.Label(self.root, text="", font=("Arial", 17),
                                    bg=BACKGROUND_COLOR, fg="#b1483a"))
        message.place(relx=0.5, rely=0.46, anchor="center")

        def login():
            if entry.get() == ADMIN_PASSWORD:
                self.show_admin()
            else:
                message.config(text="Vale parool")
                entry.delete(0, tk.END)

        entry.bind("<Return>", lambda _event: login())
        self.button("Sisene", login, relx=0.5, rely=0.59, anchor="center",
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
        tk.Button(keyboard, text="⌫ Kustuta", font=("Arial", 14),
                  command=lambda: entry.delete(max(0, len(entry.get()) - 1), tk.END)).pack(pady=3)
        entry.focus_set()

    def show_admin(self):
        self.clear()
        self.title("Admin menüü")
        self.button("← Tagasi", self.show_display, x=20, y=20, width=145, height=55)
        buttons = (
            ("Muuda ekraani pilti", self.show_gallery),
            ("Muuda näo taustavärvi", self.show_face_colors),
            ("Heli seaded", self.show_audio_settings),
            ("Wi-Fi seaded", self.show_wifi_settings),
            ("Kõne", self.show_speech),
        )
        for index, (label, command) in enumerate(buttons):
            self.button(label, command, relx=0.5, rely=0.24 + index * 0.14,
                        anchor="center", width=320, height=68)

    def show_speech(self):
        self.clear()
        self.title("Kõne")
        self.button("← Tagasi", self.show_admin, x=20, y=20, width=145, height=55)
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
            "Peata", self.stop_speech, relx=0.5, rely=0.7,
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
            self.speech_status = "Kõnekäsk juba töötab"
            self.refresh_speech_controls()
            return
        try:
            self.speech_process = subprocess.Popen(
                command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            self.speech_process = None
            self.speech_status = f"Käsku {command[0]} ei leitud. Kontrolli PATH keskkonnamuutujat."
            self.refresh_speech_controls()
            return
        except OSError as error:
            self.speech_process = None
            self.speech_status = f"Käsu käivitamine ebaõnnestus: {error}"
            self.refresh_speech_controls()
            return
        self.speech_stopping = False
        self.speech_status = f"Käivitatud: {' '.join(command)}"
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
            "Kõnekäsk peatatud" if self.speech_stopping else
            "Kõnekäsk lõpetas" if code == 0 else
            f"Kõnekäsk lõpetas veakoodiga {code}")
        self.speech_process = None
        self.speech_stopping = False
        self.refresh_speech_controls()

    def stop_speech(self):
        if self.speech_process is not None and self.speech_process.poll() is None:
            self.speech_process.terminate()
            self.speech_stopping = True
            self.speech_status = "Peatan kõnekäsku..."
            self.refresh_speech_controls()

    def show_audio_settings(self):
        self.clear()
        self.title("Heli seaded")
        self.button("← Tagasi", self.show_admin, x=20, y=20, width=145, height=55)
        self.button("Värskenda", self.show_audio_settings, relx=1, x=-20, y=20,
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
            status.config(text=f"Heliteenus pole saadaval: {error}")
            return False

        if not outputs:
            status.config(text="Heliväljundeid ei leitud")
            return False

        label = self.add(tk.Label(self.root, text=f"Helitugevus: {volume}%",
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
                label.config(text=f"Helitugevus: {slider.get()}%")
                status.config(text="Helitugevus muudetud")
            except (audio.AudioError, ValueError) as error:
                status.config(text=f"Helitugevuse muutmine ebaõnnestus: {error}")

        self.button("Rakenda helitugevus", apply_volume, relx=0.5, rely=0.48,
                    anchor="center", width=260, height=55)

        def test_sound():
            status.config(text="Mängin testheli...")
            self.run_background(audio.play_test_sound, lambda _value, error: status.config(
                text=f"Testheli ebaõnnestus: {error}" if error else "Testheli mängitud"))

        self.button("Testheli", test_sound, relx=0.82, rely=0.48,
                    anchor="center", width=150, height=55)

        device_label = self.add(tk.Label(self.root, text="Heliväljund", font=("Arial", 21, "bold"),
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
                status.config(text="Vali loendist heliväljund")
                return
            name, description = outputs[selection[0]]
            try:
                audio.set_default_output(name)
            except (audio.AudioError, ValueError) as error:
                status.config(text=f"Heliväljundi muutmine ebaõnnestus: {error}")
                return
            if self.show_audio_settings():
                self.audio_status.config(text=f"Heliväljund: {description}")

        self.button("Vali heliväljund", apply_output, relx=0.5, rely=0.88,
                    anchor="center", width=260, height=55)
        return True

    def show_wifi_settings(self, notice=None):
        self.clear()
        self.title("Wi-Fi seaded")
        self.button("← Tagasi", self.show_admin, x=20, y=20, width=145, height=55)
        self.button("Värskenda", self.show_wifi_settings, relx=1, x=-20, y=20,
                    anchor="ne", width=145, height=55)
        width = self.width
        height = self.height
        current = self.add(tk.Label(self.root, text="Ühendus: skannin...",
                                    font=("Arial", 18, "bold"), bg=BACKGROUND_COLOR))
        current.place(relx=0.5, rely=0.23, anchor="center")
        address = self.add(tk.Label(self.root, text="IPv4: otsin...", font=("Arial", 16),
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
        status = self.add(tk.Label(self.root, text="Skannin võrke...", font=("Arial", 15),
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
                status.config(text=f"Võrkude otsimine ebaõnnestus: {error}")
                return
            networks, scan_error, addresses, address_error = result
            active = next((item.ssid for item in networks if item.active), None)
            current.config(text=f"Ühendus: {active or 'puudub'}")
            if address_error:
                address.config(text=f"IPv4: ei saa lugeda ({address_error})")
            elif addresses:
                address.config(text="IPv4: " + "; ".join(
                    f"{device} {ip}" for device, ip in addresses))
            else:
                address.config(text="IPv4: aadress puudub")
            for item in networks:
                lock = "" if item.security in ("", "--") else "🔒 "
                choices.insert("end", f"{'● ' if item.active else '   '}{lock}{item.ssid}  ({item.signal}%)")
            if scan_error:
                status.config(text=f"Wi-Fi pole saadaval: {scan_error}")
            elif notice:
                status.config(text=notice)
            elif not networks:
                status.config(text="Wi-Fi võrke ei leitud")
            else:
                status.config(text="Vali võrk ja vajuta Ühenda")

        self.run_background(scan, scan_finished)

        def connect_selected():
            selection = choices.curselection()
            if not selection or selection[0] >= len(networks):
                status.config(text="Vali loendist Wi-Fi võrk")
                return
            selected = networks[selection[0]]
            if selected.active:
                status.config(text="See Wi-Fi võrk on juba ühendatud")
            elif "802.1X" in selected.security:
                status.config(text="See ettevõtte Wi-Fi võrk vajab eraldi konto seadistust")
            elif selected.security in ("", "--"):
                self.connect_wifi(selected.ssid, "", status, connect_button)
            else:
                self.show_wifi_password(selected.ssid)

        connect_button = self.button("Ühenda", connect_selected, relx=0.5, rely=0.88,
                                     anchor="center", width=180, height=55)

    def show_wifi_password(self, ssid):
        self.clear()
        self.title("Wi-Fi parool")
        self.button("← Tagasi", self.show_wifi_settings, x=20, y=20, width=145, height=55)
        width = self.width
        name = self.add(tk.Label(self.root, text=ssid, font=("Arial", 18, "bold"),
                                 bg=BACKGROUND_COLOR, wraplength=width - 80))
        name.place(relx=0.5, rely=0.21, anchor="center")
        entry = self.add(tk.Entry(self.root, font=("Arial", 22), show="*", justify="center"))
        entry.place(relx=0.5, rely=0.3, anchor="center", width=min(480, width - 100), height=48)
        visible = tk.BooleanVar(value=False)
        toggle = self.add(tk.Checkbutton(
            self.root, text="Näita parooli", variable=visible, font=("Arial", 14),
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
            tk.Button(controls, text="Sümbolid", font=("Arial", 13),
                      command=lambda: switch("symbols")).pack(side="left", padx=4)
            tk.Button(controls, text="Tühik", font=("Arial", 13),
                      command=lambda: entry.insert(tk.END, " ")).pack(side="left", padx=4)
            tk.Button(controls, text="⌫", font=("Arial", 13),
                      command=lambda: entry.delete(max(0, len(entry.get()) - 1), tk.END)).pack(
                          side="left", padx=4)

        draw_keyboard()
        status = self.add(tk.Label(self.root, text="", font=("Arial", 15),
                                   bg=BACKGROUND_COLOR, wraplength=width - 80))
        status.place(relx=0.5, rely=0.96, anchor="center")
        connect_button = self.button(
            "Ühenda", lambda: self.connect_wifi(ssid, entry.get(), status, connect_button),
            relx=0.5, rely=0.88, anchor="center", width=180, height=55)
        entry.focus_set()

    def connect_wifi(self, ssid, password, status, button):
        button.config(state="disabled")
        status.config(text="Ühendan Wi-Fi võrguga...")

        def finished(_result, error):
            if error:
                status.config(text=f"Ühendamine ebaõnnestus: {error}")
                button.config(state="normal")
            else:
                self.show_wifi_settings(notice=f"Ühendatud: {ssid}")

        self.run_background(lambda: network.connect_wifi(ssid, password), finished)

    def show_face_colors(self):
        self.clear(preserve_face_preview=True)
        self.title("Näo taustavärv")
        self.button("← Tagasi", self.show_admin, x=20, y=20, width=145, height=55)
        current = self.pending_face_color or selected_face_color()
        width = self.width
        height = self.height
        channels = [int(current[index:index + 2], 16) for index in (1, 3, 5)]
        caption = "Eelvaade" if self.pending_face_color else "Salvestatud"
        preview = self.add(tk.Label(self.root, text=f"{caption}: {current}",
                                    font=("Arial", 17, "bold"), bg=current,
                                    fg="black" if sum(channels) > 380 else "white",
                                    relief="solid", bd=2))
        preview.place(relx=0.5, rely=0.23, anchor="center", width=240, height=50)
        for index, (name, color) in enumerate(FACE_COLORS.items()):
            row, column = divmod(index, 3)
            button = self.add(tk.Button(
                self.root, text=f"{'✓ ' if color == current else ''}{name}",
                font=("Arial", 19, "bold"), bg=color,
                fg="white" if color == FACE_COLORS["Tume"] else "black",
                command=lambda chosen=color: self.select_face_color(chosen),
                relief="raised", bd=3,
            ))
            button.place(x=int(width * (0.25 + 0.25 * column)),
                         y=int(height * (0.38 + 0.3 * row)),
                         anchor="center", width=width // 5, height=height // 5)
        self.button("Muu värv...", self.choose_face_color,
                    relx=0.82, rely=0.23, anchor="center", width=170, height=50)
        save_button = self.button("Salvesta", self.save_face_color,
                                  relx=0.4, rely=0.84, anchor="center", width=180, height=55)
        undo_button = self.button("Võta tagasi", self.undo_face_color,
                                  relx=0.6, rely=0.84, anchor="center", width=180, height=55)
        if self.pending_face_color is None:
            save_button.config(state="disabled")
            undo_button.config(state="disabled")
        status = "Vali värv eelvaateks. Muudatus salvestub alles pärast Salvesta vajutamist."
        if self.pending_face_color is not None:
            status = "Eelvaade on näo ekraanil. Salvesta või võta tagasi."
        if self.face_colors.node is None:
            status = "ROS 2 pole saadaval; eelvaade on ainult siin. Salvesta jätab värvi järgmise käivituse jaoks."
        elif self.face_colors.error:
            status = f"Värvi saatmine ebaõnnestus: {self.face_colors.error}"
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
        self.face_colors.publish(color)
        self.show_face_colors()

    def save_face_color(self):
        if self.pending_face_color is None:
            return
        try:
            save_setting("face_background_color", self.pending_face_color)
        except OSError as error:
            messagebox.showerror("Salvestamine ebaõnnestus", str(error), parent=self.root)
            return
        self.pending_face_color = None
        self.show_face_colors()

    def undo_face_color(self):
        if self.pending_face_color is None:
            return
        self.face_colors.publish(selected_face_color())
        self.pending_face_color = None
        self.show_face_colors()

    def show_gallery(self, category="logos"):
        self.clear()
        self.title("Vali rinnaekraani pilt")
        self.button("← Tagasi", self.show_admin, x=20, y=20, width=145, height=55)
        self.button("Lisa pilt", lambda: self.choose_file(category), relx=1, x=-20, y=20,
                    anchor="ne", width=145, height=55)

        tabs = self.add(tk.Frame(self.root, bg=BACKGROUND_COLOR))
        tabs.place(relx=0.5, y=115, anchor="center")
        for key, label in IMAGE_CATEGORIES.items():
            tk.Button(tabs, text=label, font=("Arial", 16, "bold"),
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
                                 text=f"Selles kaustas pole pilte. Lisa pilt kausta images/{category}/.",
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
        self.title("Rinnaekraani eelvaade")
        width = self.width
        height = self.height
        self.draw_image(self.pending_image, int(width * 0.8), int(height * 0.55),
                        int(height * 0.47))
        label = self.add(tk.Label(
            self.root, text=f"{os.path.basename(self.pending_image)} — salvesta või võta tagasi",
            font=("Arial", 17), bg=BACKGROUND_COLOR, wraplength=width - 80,
        ))
        label.place(relx=0.5, rely=0.76, anchor="center")
        self.button("Salvesta", self.save_image_preview, relx=0.4, rely=0.88,
                    anchor="center", width=180, height=60)
        self.button("Võta tagasi", self.undo_image_preview, relx=0.6, rely=0.88,
                    anchor="center", width=180, height=60)

    def save_image_preview(self):
        if self.pending_image is None:
            return
        try:
            save_selected_image(self.pending_image)
        except (OSError, ValueError) as error:
            messagebox.showerror("Salvestamine ebaõnnestus", str(error), parent=self.root)
            return
        self.pending_image = None
        self.show_display()

    def undo_image_preview(self):
        category = self.pending_image_category
        self.pending_image = None
        self.show_gallery(category)

    def choose_file(self, category):
        source = filedialog.askopenfilename(
            title="Vali pilt", filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp")],
        )
        if source:
            try:
                path = import_image(source, category)
                self.select_image(path, category)
            except (OSError, ValueError) as error:
                messagebox.showerror("Pildi lisamine ebaõnnestus", str(error))


def start_gui():
    root = tk.Tk()
    root.title("SemuBot chest display")
    geometry, width, height = display_geometry(root.winfo_screenwidth(), root.winfo_screenheight())
    root.geometry(geometry)
    root.overrideredirect(True)
    ChestDisplayApp(root, width, height)
    root.mainloop()
