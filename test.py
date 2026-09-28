import tkinter as tk
from tkinter import font as tkfont
from PIL import Image, ImageTk
import os
import math
import json
import subprocess
import threading

from constants import *
from logic import *

# ─────────────────────────────────────────────
#  State
# ─────────────────────────────────────────────
current_widgets = []
swipe_start = None

# Pattern lock state
pattern_dots = []          # (cx, cy, row, col) for each dot
pattern_line_ids = []      # canvas line items
pattern_drawn = []         # sequence of dot indices the user has drawn through
pattern_active = False

# Corner-tap exit (top-left, 3 taps within 1.5 s)
_corner_taps = []
CORNER_SIZE = 80           # px — tap zone in top-left corner


# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────
def clear_screen(canvas):
    canvas.delete("all")
    for w in current_widgets:
        try:
            w.destroy()
        except Exception:
            pass
    current_widgets.clear()


def register(widget):
    current_widgets.append(widget)


def make_button(parent, text, command, font_size=22, width=220, height=80,
                image=None, compound=None):
    """Unified button factory matching the project's style."""
    kwargs = dict(
        font=("Segoe UI", font_size, "bold"),
        bg=COLOUR5, fg=COLOUR7,
        bd=3, relief="raised",
        activebackground=COLOUR2, activeforeground=COLOUR7,
        command=command,
    )
    if image:
        kwargs["image"] = image
        if compound:
            kwargs["compound"] = compound
    else:
        kwargs["text"] = text

    btn = tk.Button(parent, **kwargs)
    return btn


def back_button(root, command):
    btn = make_button(root, "← Tagasi", command, font_size=16, width=120, height=55)
    btn.place(x=30, y=30, width=140, height=55)
    register(btn)


def title_label(root, text, canvas_or_root=None):
    lbl = tk.Label(root, text=text, font=("Segoe UI", 36, "bold"),
                   bg=BACKGROUND_COLOR, fg=COLOUR7)
    lbl.place(relx=0.5, rely=0.12, anchor="center")
    register(lbl)
    return lbl


def emit_face(part, value):
    """Write selected face part to JSON so the face renderer can pick it up."""
    path = os.path.join(BASE_DIR, "current_face.json")
    data = {}
    if os.path.exists(path):
        try:
            with open(path) as f:
                data = json.load(f)
        except Exception:
            pass
    data[part] = value
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# ─────────────────────────────────────────────
#  Lock screen  (logo + swipe up)
# ─────────────────────────────────────────────
def lock_screen(root, canvas):
    clear_screen(canvas)

    w = root.winfo_screenwidth()
    h = root.winfo_screenheight()

    # Background
    canvas.configure(bg=BACKGROUND_COLOR)

    # Logo
    try:
        img = Image.open(os.path.join(BASE_DIR, LOGO_PATH))
        img = img.resize((380, 380), Image.LANCZOS)
        logo = ImageTk.PhotoImage(img)
        canvas.create_image(w // 2, h // 2 - 40, image=logo, anchor="center")
        canvas.logo = logo
    except Exception:
        canvas.create_text(w // 2, h // 2 - 40, text="🤖",
                           font=("Segoe UI", 120), fill=COLOUR7)

    # "Swipe up" hint
    canvas.create_text(w // 2, h - 80, text="↑  Tõmba üles  ↑",
                       font=("Segoe UI", 20), fill=COLOUR7, tags="hint")

    canvas.bind("<Button-1>", _lock_press)
    canvas.bind("<ButtonRelease-1>", lambda e: _lock_release(e, root, canvas))


def _lock_press(e):
    global swipe_start
    swipe_start = e.y


def _lock_release(e, root, canvas):
    if swipe_ok(swipe_start, e.y):
        mode_panel(root, canvas)


# ─────────────────────────────────────────────
#  Mode selection
# ─────────────────────────────────────────────
def mode_panel(root, canvas):
    clear_screen(canvas)
    back_button(root, lambda: lock_screen(root, canvas))

    w = root.winfo_screenwidth()
    h = root.winfo_screenheight()

    title = tk.Label(root, text="Vali režiim", font=("Segoe UI", 36, "bold"),
                     bg=BACKGROUND_COLOR, fg=COLOUR7)
    title.place(relx=0.5, rely=0.2, anchor="center")
    register(title)

    cx = w // 2
    cy = h // 2 + 20
    btn_w, btn_h = 260, 120

    admin = make_button(root, "🔒  Admin", lambda: admin_password(root, canvas), font_size=24)
    admin.place(x=cx - btn_w - 30, y=cy - btn_h // 2, width=btn_w, height=btn_h)
    register(admin)

    user = make_button(root, "👤  Kasutaja", lambda: user_menu(root, canvas), font_size=24)
    user.place(x=cx + 30, y=cy - btn_h // 2, width=btn_w, height=btn_h)
    register(user)


# ─────────────────────────────────────────────
#  Pattern lock
# ─────────────────────────────────────────────
DOT_R = 18          # dot radius (normal)
DOT_R_LIT = 24      # dot radius when active
GRID_COLS = 3
GRID_ROWS = 3
# Colours
DOT_IDLE   = "#4a5568"
DOT_LIT    = "#63b3ed"
DOT_ERROR  = "#fc8181"
LINE_COLOR = "#63b3ed"
LINE_WIDTH = 4


def _dot_at(mx, my):
    """Return index of dot whose lit-radius contains (mx, my), or -1."""
    for i, (cx, cy, r, c) in enumerate(pattern_dots):
        if math.hypot(mx - cx, my - cy) <= DOT_R_LIT + 8:
            return i
    return -1


def _draw_dots(canvas, color_map=None):
    """Redraw all dots. color_map: {index: color}"""
    for i, (cx, cy, r, c) in enumerate(pattern_dots):
        color = (color_map or {}).get(i, DOT_IDLE)
        lit = i in pattern_drawn
        radius = DOT_R_LIT if lit else DOT_R
        canvas.create_oval(cx - radius, cy - radius,
                           cx + radius, cy + radius,
                           fill=color if lit else DOT_IDLE,
                           outline=color if lit else "#718096",
                           width=2,
                           tags="dot")
        # inner bright spot
        if lit:
            canvas.create_oval(cx - 6, cy - 6, cx + 6, cy + 6,
                               fill="white", outline="", tags="dot")


def admin_password(root, canvas):
    """Full-screen Android-style pattern lock."""
    global pattern_dots, pattern_line_ids, pattern_drawn, pattern_active

    clear_screen(canvas)
    canvas.unbind("<Button-1>")
    canvas.unbind("<ButtonRelease-1>")

    w = root.winfo_screenwidth()
    h = root.winfo_screenheight()

    # Background panel
    canvas.configure(bg=BACKGROUND_COLOR)

    # Title
    canvas.create_text(w // 2, 80, text="Admin sisenemine",
                       font=("Segoe UI", 30, "bold"), fill=COLOUR7, tags="ui")
    canvas.create_text(w // 2, 130, text="Joonista muster",
                       font=("Segoe UI", 18), fill="#a0aec0", tags="ui")

    # Status text (shows errors / success)
    canvas.create_text(w // 2, h - 60, text="",
                       font=("Segoe UI", 18), fill=DOT_ERROR,
                       tags="status")

    # Back button
    back_button(root, lambda: mode_panel(root, canvas))

    # Build 3×3 grid of dots centred on screen
    grid_size = min(w, h) * 0.55
    spacing = grid_size / (GRID_COLS - 1)
    ox = w / 2 - grid_size / 2
    oy = h / 2 - grid_size / 2 + 20

    pattern_dots.clear()
    for row in range(GRID_ROWS):
        for col in range(GRID_COLS):
            cx = ox + col * spacing
            cy = oy + row * spacing
            pattern_dots.append((cx, cy, row, col))

    pattern_line_ids.clear()
    pattern_drawn.clear()
    pattern_active = False

    _refresh_pattern_canvas(canvas)

    # Bind touch/mouse events
    canvas.bind("<Button-1>",        lambda e: _pat_press(e, canvas))
    canvas.bind("<B1-Motion>",       lambda e: _pat_move(e, canvas))
    canvas.bind("<ButtonRelease-1>", lambda e: _pat_release(e, root, canvas))


def _refresh_pattern_canvas(canvas):
    canvas.delete("dot")
    canvas.delete("line")
    _draw_dots(canvas, {i: DOT_LIT for i in pattern_drawn})

    # Draw lines between drawn dots
    for k in range(len(pattern_drawn) - 1):
        ax, ay, _, _ = pattern_dots[pattern_drawn[k]]
        bx, by, _, _ = pattern_dots[pattern_drawn[k + 1]]
        canvas.create_line(ax, ay, bx, by, fill=LINE_COLOR,
                           width=LINE_WIDTH, tags="line")


def _pat_press(e, canvas):
    global pattern_drawn, pattern_active
    pattern_drawn.clear()
    pattern_active = True
    idx = _dot_at(e.x, e.y)
    if idx >= 0:
        pattern_drawn.append(idx)
    _refresh_pattern_canvas(canvas)


def _pat_move(e, canvas):
    if not pattern_active:
        return
    idx = _dot_at(e.x, e.y)
    if idx >= 0 and idx not in pattern_drawn:
        pattern_drawn.append(idx)
    _refresh_pattern_canvas(canvas)
    # Draw rubber-band line to current finger position
    if pattern_drawn:
        lx, ly, _, _ = pattern_dots[pattern_drawn[-1]]
        canvas.create_line(lx, ly, e.x, e.y,
                           fill=LINE_COLOR, width=LINE_WIDTH,
                           dash=(6, 4), tags="rubber")


def _pat_release(e, root, canvas):
    global pattern_active
    pattern_active = False
    canvas.delete("rubber")

    if len(pattern_drawn) < 4:
        _pattern_feedback(canvas, "Liiga lühike muster!", error=True)
        return

    if pattern_ok(pattern_drawn):
        _pattern_feedback(canvas, "✓ Juurdepääs lubatud", error=False)
        canvas.after(600, lambda: admin_menu(root, canvas))
    else:
        _pattern_feedback(canvas, "✗ Vale muster", error=True)
        canvas.after(900, lambda: _reset_pattern(canvas))


def _pattern_feedback(canvas, msg, error=True):
    color = DOT_ERROR if error else "#68d391"
    canvas.delete("dot")
    color_map = {i: color for i in pattern_drawn}
    _draw_dots(canvas, color_map)
    # Update status text
    for item in canvas.find_withtag("status"):
        canvas.itemconfig(item, text=msg, fill=color)


def _reset_pattern(canvas):
    global pattern_drawn
    pattern_drawn.clear()
    _refresh_pattern_canvas(canvas)
    for item in canvas.find_withtag("status"):
        canvas.itemconfig(item, text="")


# ─────────────────────────────────────────────
#  Admin menu
# ─────────────────────────────────────────────
def admin_menu(root, canvas):
    clear_screen(canvas)
    _rebind_lock(canvas)
    back_button(root, lambda: mode_panel(root, canvas))

    title_label(root, "Admin menüü")

    w = root.winfo_screenwidth()
    h = root.winfo_screenheight()
    cy = h // 2 + 20
    btn_w, btn_h = 260, 120

    settings = make_button(root, "⚙  Seaded",
                           lambda: settings_menu(root, canvas), font_size=22)
    settings.place(relx=0.25, rely=0.55, anchor="center", width=btn_w, height=btn_h)
    register(settings)

    face_btn = make_button(root, "😊  Näoilmed",
                           lambda: face_change_cat(root, canvas), font_size=22)
    face_btn.place(relx=0.75, rely=0.55, anchor="center", width=btn_w, height=btn_h)
    register(face_btn)

    # Exit / quit app button
    exit_btn = tk.Button(root, text="✕  Välju rakendusest",
                         font=("Segoe UI", 16, "bold"),
                         bg="#c53030", fg="white",
                         bd=3, relief="raised",
                         activebackground="#9b2c2c", activeforeground="white",
                         command=root.destroy)
    exit_btn.place(relx=0.5, rely=0.85, anchor="center", width=280, height=55)
    register(exit_btn)


# ─────────────────────────────────────────────
#  Settings menu
# ─────────────────────────────────────────────
def settings_menu(root, canvas):
    clear_screen(canvas)
    back_button(root, lambda: admin_menu(root, canvas))
    title_label(root, "Seaded")

    wifi_btn = make_button(root, "📶  WiFi", lambda: wifi_menu(root, canvas), font_size=22)
    wifi_btn.place(relx=0.5, rely=0.45, anchor="center", width=260, height=110)
    register(wifi_btn)


# ─────────────────────────────────────────────
#  WiFi menu
# ─────────────────────────────────────────────
def wifi_menu(root, canvas):
    clear_screen(canvas)
    back_button(root, lambda: settings_menu(root, canvas))
    title_label(root, "WiFi seaded")

    w = root.winfo_screenwidth()

    # Scanning label
    scan_lbl = tk.Label(root, text="Skannimine...", font=("Segoe UI", 18),
                        bg=BACKGROUND_COLOR, fg="#a0aec0")
    scan_lbl.place(relx=0.5, rely=0.35, anchor="center")
    register(scan_lbl)

    # Frame for network list
    frame = tk.Frame(root, bg=BACKGROUND_COLOR)
    frame.place(relx=0.5, rely=0.62, anchor="center", width=w - 160, height=260)
    register(frame)

    def do_scan():
        try:
            result = subprocess.check_output(
                ["nmcli", "-t", "-f", "SSID,SIGNAL", "dev", "wifi", "list"],
                timeout=8, stderr=subprocess.DEVNULL
            ).decode()
            networks = []
            seen = set()
            for line in result.strip().splitlines():
                parts = line.split(":")
                if len(parts) >= 2:
                    ssid, signal = parts[0].strip(), parts[1].strip()
                    if ssid and ssid not in seen:
                        seen.add(ssid)
                        networks.append((ssid, signal))
            networks.sort(key=lambda x: -int(x[1]) if x[1].isdigit() else 0)
            root.after(0, lambda: _show_networks(root, canvas, frame, scan_lbl, networks))
        except Exception:
            root.after(0, lambda: scan_lbl.config(text="nmcli ei ole saadaval / viga"))

    threading.Thread(target=do_scan, daemon=True).start()


def _show_networks(root, canvas, frame, scan_lbl, networks):
    scan_lbl.config(text=f"{len(networks)} võrku leitud")
    for child in frame.winfo_children():
        child.destroy()

    scrollbar = tk.Scrollbar(frame, orient="vertical")
    listbox = tk.Listbox(frame, font=("Segoe UI", 18),
                         bg="#2d3748", fg=COLOUR7,
                         selectbackground=COLOUR2,
                         yscrollcommand=scrollbar.set,
                         activestyle="none",
                         bd=0, highlightthickness=0)
    scrollbar.config(command=listbox.yview)
    scrollbar.pack(side="right", fill="y")
    listbox.pack(side="left", fill="both", expand=True)

    ssid_list = []
    for ssid, signal in networks:
        bars = "▂▄▆█"[:max(1, int(signal) // 25)] if signal.isdigit() else "?"
        listbox.insert("end", f"  {bars}  {ssid}")
        ssid_list.append(ssid)

    def on_select(e):
        sel = listbox.curselection()
        if sel:
            ssid = ssid_list[sel[0]]
            _wifi_connect_dialog(root, canvas, ssid)

    listbox.bind("<<ListboxSelect>>", on_select)


def _wifi_connect_dialog(root, canvas, ssid):
    """Overlay dialog with on-screen PIN pad for WiFi password."""
    w = root.winfo_screenwidth()
    h = root.winfo_screenheight()

    overlay = tk.Frame(root, bg="#1a202c", bd=4, relief="ridge")
    overlay.place(relx=0.5, rely=0.5, anchor="center", width=520, height=480)
    register(overlay)

    tk.Label(overlay, text=f"Ühenda: {ssid}", font=("Segoe UI", 18, "bold"),
             bg="#1a202c", fg=COLOUR7).pack(pady=(20, 4))

    pwd_var = tk.StringVar()
    pwd_display = tk.Label(overlay, textvariable=pwd_var,
                           font=("Segoe UI", 22, "bold"),
                           bg="#2d3748", fg=COLOUR7,
                           width=22, anchor="e", relief="sunken", bd=2)
    pwd_display.pack(padx=20, pady=8, fill="x")

    # On-screen keyboard (alphanumeric rows)
    keys = [
        list("1234567890"),
        list("qwertyuiop"),
        list("asdfghjkl"),
        list("zxcvbnm"),
    ]
    kb_frame = tk.Frame(overlay, bg="#1a202c")
    kb_frame.pack(pady=4)

    def press(ch):
        pwd_var.set(pwd_var.get() + ch)

    def backspace():
        pwd_var.set(pwd_var.get()[:-1])

    for row in keys:
        rf = tk.Frame(kb_frame, bg="#1a202c")
        rf.pack(pady=2)
        for ch in row:
            tk.Button(rf, text=ch, font=("Segoe UI", 14, "bold"),
                      bg=COLOUR5, fg=COLOUR7, width=3, height=1,
                      command=lambda c=ch: press(c)).pack(side="left", padx=1)

    ctrl = tk.Frame(overlay, bg="#1a202c")
    ctrl.pack(pady=6)

    tk.Button(ctrl, text="⌫", font=("Segoe UI", 14, "bold"),
              bg=COLOUR5, fg=COLOUR7, width=5, command=backspace).pack(side="left", padx=4)

    def connect():
        password = pwd_var.get()
        overlay.destroy()
        current_widgets.remove(overlay)
        _do_wifi_connect(root, ssid, password)

    tk.Button(ctrl, text="Ühenda", font=("Segoe UI", 14, "bold"),
              bg="#2f855a", fg="white", width=10, command=connect).pack(side="left", padx=4)

    tk.Button(ctrl, text="Tühista", font=("Segoe UI", 14, "bold"),
              bg="#c53030", fg="white", width=8,
              command=lambda: [overlay.destroy(),
                               current_widgets.remove(overlay) if overlay in current_widgets else None]
              ).pack(side="left", padx=4)


def _do_wifi_connect(root, ssid, password):
    def task():
        try:
            subprocess.run(
                ["nmcli", "dev", "wifi", "connect", ssid, "password", password],
                timeout=15, check=True, stderr=subprocess.DEVNULL
            )
            root.after(0, lambda: _wifi_toast(root, f"✓ Ühendatud: {ssid}", ok=True))
        except Exception:
            root.after(0, lambda: _wifi_toast(root, f"✗ Ühendamine ebaõnnestus", ok=False))

    threading.Thread(target=task, daemon=True).start()


def _wifi_toast(root, msg, ok=True):
    color = "#276749" if ok else "#742a2a"
    toast = tk.Label(root, text=msg, font=("Segoe UI", 18, "bold"),
                     bg=color, fg="white", bd=2, relief="solid")
    toast.place(relx=0.5, rely=0.92, anchor="center", width=420, height=50)
    root.after(2500, toast.destroy)


# ─────────────────────────────────────────────
#  Face categories
# ─────────────────────────────────────────────
def face_change_cat(root, canvas):
    clear_screen(canvas)
    back_button(root, lambda: admin_menu(root, canvas))
    title_label(root, "Näoilmete kategooriad")

    categories = [
        ("🙂  Terve nägu",  lambda: change_face_full(root, canvas)),
        ("👁  Silmad",      lambda: change_eyes(root, canvas)),
        ("👄  Suu",         lambda: change_mouth(root, canvas)),
        ("🤨  Kulmud",      lambda: change_brows(root, canvas)),
        ("👃  Nina",        lambda: change_nose(root, canvas)),
    ]

    for i, (label, cmd) in enumerate(categories):
        btn = make_button(root, label, cmd, font_size=20)
        btn.place(relx=0.1 + i * 0.2, rely=0.55, anchor="center",
                  width=200, height=110)
        register(btn)


def _image_grid(root, canvas, title, pictures, part_key, back_cmd):
    """Generic scrollable image grid for face parts."""
    clear_screen(canvas)
    back_button(root, back_cmd)
    title_label(root, title)

    w = root.winfo_screenwidth()
    h = root.winfo_screenheight()

    # Scrollable canvas inside a frame
    container = tk.Frame(root, bg=BACKGROUND_COLOR)
    container.place(x=0, y=160, width=w, height=h - 160)
    register(container)

    scroll_canvas = tk.Canvas(container, bg=BACKGROUND_COLOR,
                              highlightthickness=0)
    scrollbar = tk.Scrollbar(container, orient="vertical",
                             command=scroll_canvas.yview)
    scroll_canvas.configure(yscrollcommand=scrollbar.set)

    scrollbar.pack(side="right", fill="y")
    scroll_canvas.pack(side="left", fill="both", expand=True)

    inner = tk.Frame(scroll_canvas, bg=BACKGROUND_COLOR)
    inner_id = scroll_canvas.create_window((0, 0), window=inner, anchor="nw")

    imgs = []
    cols = 5
    pad = 20
    btn_size = 180

    for i, pic in enumerate(pictures):
        row, col = divmod(i, cols)
        try:
            img = Image.open(os.path.join(BASE_DIR, pic))
            img = img.resize((btn_size - 10, btn_size - 10), Image.LANCZOS)
            tk_img = ImageTk.PhotoImage(img)
        except Exception:
            tk_img = None

        kwargs = dict(
            font=("Segoe UI", 12), bg=COLOUR5, fg=COLOUR7,
            bd=3, relief="raised",
            activebackground=COLOUR2, activeforeground=COLOUR7,
            command=lambda p=pic: emit_face(part_key, p),
        )
        if tk_img:
            kwargs["image"] = tk_img
        else:
            kwargs["text"] = os.path.basename(pic)

        btn = tk.Button(inner, **kwargs)
        if tk_img:
            btn.image = tk_img
        btn.grid(row=row, column=col,
                 padx=pad // 2, pady=pad // 2)
        imgs.append(tk_img)

    def on_configure(e):
        scroll_canvas.configure(scrollregion=scroll_canvas.bbox("all"))

    inner.bind("<Configure>", on_configure)

    # Touch-scroll support
    def _on_touch_scroll(e):
        scroll_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

    scroll_canvas.bind("<MouseWheel>", _on_touch_scroll)

    # Drag-to-scroll for touch screens
    _drag = {"y": None}

    def _drag_start(e):
        _drag["y"] = e.y

    def _drag_move(e):
        if _drag["y"] is not None:
            dy = _drag["y"] - e.y
            scroll_canvas.yview_scroll(int(dy / 8), "units")
            _drag["y"] = e.y

    scroll_canvas.bind("<Button-1>", _drag_start)
    scroll_canvas.bind("<B1-Motion>", _drag_move)


def change_face_full(root, canvas):
    _image_grid(root, canvas, "Terved näoilmed", [FULL_FACE],
                "full", lambda: face_change_cat(root, canvas))


def change_eyes(root, canvas):
    pictures = [EYES_1, EYES_2, EYES_3, EYES_4, EYES_5, EYES_6, EYES_7, EYES_8]
    _image_grid(root, canvas, "Silmad", pictures,
                "eyes", lambda: face_change_cat(root, canvas))


def change_mouth(root, canvas):
    pictures = [MOUTH_1, MOUTH_2, MOUTH_3, MOUTH_4, MOUTH_5, MOUTH_6,
                MOUTH_7, MOUTH_8, MOUTH_9, MOUTH_10, MOUTH_11, MOUTH_12]
    _image_grid(root, canvas, "Suu", pictures,
                "mouth", lambda: face_change_cat(root, canvas))


def change_brows(root, canvas):
    pictures = [BROWS_1, BROWS_2]
    _image_grid(root, canvas, "Kulmud", pictures,
                "brows", lambda: face_change_cat(root, canvas))


def change_nose(root, canvas):
    # Add nose constants to constants.py as needed
    pictures = getattr(__builtins__, '__dict__', {})
    try:
        from constants import NOSE_1
        noses = [NOSE_1]
    except ImportError:
        noses = []
    _image_grid(root, canvas, "Nina", noses,
                "nose", lambda: face_change_cat(root, canvas))


# ─────────────────────────────────────────────
#  User menu
# ─────────────────────────────────────────────
def user_menu(root, canvas):
    clear_screen(canvas)
    _rebind_lock(canvas)
    back_button(root, lambda: mode_panel(root, canvas))
    title_label(root, "Kasutaja menüü")

    sub = make_button(root, "💬  Subtiitrid",
                      lambda: subtitles_screen(root, canvas), font_size=22)
    sub.place(relx=0.3, rely=0.55, anchor="center", width=260, height=120)
    register(sub)

    vid = make_button(root, "▶  Videod",
                      lambda: video_screen(root, canvas), font_size=22)
    vid.place(relx=0.7, rely=0.55, anchor="center", width=260, height=120)
    register(vid)


# ─────────────────────────────────────────────
#  Subtitles screen
# ─────────────────────────────────────────────
def subtitles_screen(root, canvas):
    clear_screen(canvas)
    back_button(root, lambda: user_menu(root, canvas))
    title_label(root, "Subtiitrid")

    w = root.winfo_screenwidth()
    h = root.winfo_screenheight()

    sub_lbl = tk.Label(root, text="Ootan kõnet...",
                       font=("Segoe UI", 28),
                       bg=BACKGROUND_COLOR, fg=COLOUR7,
                       wraplength=w - 120,
                       justify="center")
    sub_lbl.place(relx=0.5, rely=0.55, anchor="center",
                  width=w - 100, height=h - 260)
    register(sub_lbl)

    # TODO: hook up your speech-to-text source here.
    # Example: poll a shared file, a queue, or a socket and call:
    #   sub_lbl.config(text=new_text)


# ─────────────────────────────────────────────
#  Video screen
# ─────────────────────────────────────────────
def video_screen(root, canvas):
    clear_screen(canvas)
    back_button(root, lambda: user_menu(root, canvas))
    title_label(root, "Videod")

    w = root.winfo_screenwidth()

    try:
        video_dir = os.path.join(BASE_DIR, "videos")
        files = [f for f in os.listdir(video_dir)
                 if f.lower().endswith((".mp4", ".avi", ".mkv", ".mov"))]
    except Exception:
        files = []

    if not files:
        lbl = tk.Label(root, text="Videoid ei leitud.\nLisa videod kausta 'videos/'.",
                       font=("Segoe UI", 22), bg=BACKGROUND_COLOR, fg="#a0aec0",
                       justify="center")
        lbl.place(relx=0.5, rely=0.55, anchor="center")
        register(lbl)
        return

    frame = tk.Frame(root, bg=BACKGROUND_COLOR)
    frame.place(x=40, y=160, width=w - 80, height=400)
    register(frame)

    scrollbar = tk.Scrollbar(frame, orient="vertical")
    listbox = tk.Listbox(frame, font=("Segoe UI", 20),
                         bg="#2d3748", fg=COLOUR7,
                         selectbackground=COLOUR2,
                         yscrollcommand=scrollbar.set,
                         activestyle="none",
                         bd=0, highlightthickness=0)
    scrollbar.config(command=listbox.yview)
    scrollbar.pack(side="right", fill="y")
    listbox.pack(side="left", fill="both", expand=True)

    for f in files:
        listbox.insert("end", f"  ▶  {f}")

    def play(e):
        sel = listbox.curselection()
        if sel:
            path = os.path.join(BASE_DIR, "videos", files[sel[0]])
            subprocess.Popen(["vlc", "--fullscreen", path],
                             stderr=subprocess.DEVNULL)

    listbox.bind("<<ListboxSelect>>", play)


# ─────────────────────────────────────────────
#  Utility: rebind canvas for normal screens
#  (undo pattern-lock bindings)
# ─────────────────────────────────────────────
def _rebind_lock(canvas):
    canvas.unbind("<Button-1>")
    canvas.unbind("<B1-Motion>")
    canvas.unbind("<ButtonRelease-1>")


# ─────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────
def start_gui():
    root = tk.Tk()
    root.title("Robot GUI")

    width  = root.winfo_screenwidth()
    height = root.winfo_screenheight()

    root.geometry(f"{width}x{height}+0+0")
    root.overrideredirect(True)          # borderless fullscreen
    root.resizable(False, False)

    canvas = tk.Canvas(root, bg=BACKGROUND_COLOR, highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    lock_screen(root, canvas)

    root.mainloop()
