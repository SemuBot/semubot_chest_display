import tkinter as tk
from tkinter import *
from PIL import Image, ImageTk
import os

from constants import *
from logic import *

current_widgets = []
swipe_start = None


# helper function to clear all previous widgets
def clear_screen(canvas):
    canvas.delete("all")
    for w in current_widgets:
        try:
            w.destroy()
        except:
            pass
    current_widgets.clear()


# add a new widget to list
def register(widget):
    current_widgets.append(widget)


# move back to previous screen
def back_button(root, command):
    btn = tk.Button(root, text="Tagasi", font=("Segoe UI", 16, "bold"), bg=COLOUR5, fg=COLOUR7,
    bd=3, relief="raised", activebackground=COLOUR2, activeforeground=COLOUR7, command=command)
    btn.place(x=30, y=30, width=120, height=60)
    register(btn)


# lock screen config
def lock_screen(root, canvas):
    clear_screen(canvas)

    img = Image.open(os.path.join(BASE_DIR, LOGO_PATH))
    img = img.resize((400, 400))
    logo = ImageTk.PhotoImage(img)

    canvas.create_image(
        root.winfo_screenwidth()//2,
        root.winfo_screenheight()//2,
        image=logo
    )

    canvas.logo = logo

    canvas.bind("<Button-1>", start_swipe)
    canvas.bind("<ButtonRelease-1>", lambda e: end_swipe(e, root, canvas))


def start_swipe(e):
    global swipe_start
    swipe_start = e.y


def end_swipe(e, root, canvas):
    if swipe_ok(swipe_start, e.y):
        mode_panel(root, canvas)


# admin vs user mode choice
def mode_panel(root, canvas):
    clear_screen(canvas)
    back_button(root, lambda: lock_screen(root, canvas))

    admin = tk.Button(root, text="Admin", font=("Segoe UI", 24, "bold"), bg=COLOUR5, fg=COLOUR7,
    bd=3, relief="raised", activebackground=COLOUR2, activeforeground=COLOUR7,
    command=lambda: admin_password(root, canvas))
    admin.place(x=375, y=300, width=250, height=250)
    register(admin)

    user = tk.Button(root, text="Kasutaja", font=("Segoe UI", 24, "bold"), bg=COLOUR5, fg=COLOUR7,
    bd=3, relief="raised", activebackground=COLOUR2, activeforeground=COLOUR7,
    command=lambda: user_menu(root, canvas))
    user.place(x=675, y=300, width=250, height=250)
    register(user)


# password screen to enter admin mode
def admin_password(root, canvas):
    clear_screen(canvas)
    back_button(root, lambda: mode_panel(root, canvas))

    label = tk.Label(root, text="Enter password", font=("Arial", 30))
    label.place(relx=0.5, rely=0.3, anchor="center")
    register(label)

    entry = tk.Entry(root, font=("Arial", 25), show="*")
    entry.place(relx=0.5, rely=0.4, anchor="center", width=300)
    register(entry)

    def login():
        if password_ok(entry.get()):
            admin_menu(root, canvas)

    ok = tk.Button(root, text="OK", font=("Segoe UI", 24, "bold"), bg=COLOUR5, fg=COLOUR7,
    bd=3, relief="raised", activebackground=COLOUR2, activeforeground=COLOUR7, command=login)
    ok.place(relx=0.5, rely=0.5, anchor="center", width=120, height=60)
    register(ok)


# admin mode screen
def admin_menu(root, canvas):
    clear_screen(canvas)
    back_button(root, lambda: mode_panel(root, canvas))

    title = tk.Label(root, text="Admini menüü", font=("Arial", 40))
    title.place(relx=0.5, rely=0.2, anchor="center")
    register(title)

    settings = tk.Button(root, text="Seaded", font=("Segoe UI", 24, "bold"), bg=COLOUR5, fg=COLOUR7,
    bd=3, relief="raised", activebackground=COLOUR2, activeforeground=COLOUR7,
    command=lambda: print("seaded"))
    settings.place(relx=0.25, rely=0.5, anchor="center", width=250, height=250)
    register(settings)

    change_face = tk.Button(root, text="Muuda näoilmeid", font=("Segoe UI", 24, "bold"), bg=COLOUR5,
    fg=COLOUR7, bd=3, relief="raised", activebackground=COLOUR2, activeforeground=COLOUR7,
    command=lambda: face_change_cat(root, canvas))
    change_face.place(relx=0.75, rely=0.5, anchor="center", width=250, height=250)
    register(change_face)


# face changing categories
def face_change_cat(root, canvas):
    clear_screen(canvas)
    back_button(root, lambda: admin_menu(root, canvas))

    title = tk.Label(root, text="Kategooriad", font=("Arial", 40))
    title.place(relx=0.5, rely=0.2, anchor="center")
    register(title)

    full_face = tk.Button(root, text="Terve näoilme", font=("Segoe UI", 24, "bold"), bg=COLOUR5,
    fg=COLOUR7, bd=3, relief="raised", activebackground=COLOUR2, activeforeground=COLOUR7,
    command=lambda: change_face_full(root, canvas))
    full_face.place(relx=0.10, rely=0.5, anchor="center", width=200, height=200)
    register(full_face)

    eyes = tk.Button(root, text="Silmad", font=("Segoe UI", 24, "bold"), bg=COLOUR5, fg=COLOUR7,
    bd=3, relief="raised", activebackground=COLOUR2, activeforeground=COLOUR7,
    command=lambda: change_eyes(root, canvas))
    eyes.place(relx=0.30, rely=0.5, anchor="center", width=200, height=200)
    register(eyes)

    mouth = tk.Button(root, text="Suu", font=("Segoe UI", 24, "bold"), bg=COLOUR5, fg=COLOUR7,
    bd=3, relief="raised", activebackground=COLOUR2, activeforeground=COLOUR7,
    command=lambda: change_mouth(root, canvas))
    mouth.place(relx=0.50, rely=0.5, anchor="center", width=200, height=200)
    register(mouth)

    brows = tk.Button(root, text="Kulmud", font=("Segoe UI", 24, "bold"), bg=COLOUR5, fg=COLOUR7,
    bd=3, relief="raised", activebackground=COLOUR2, activeforeground=COLOUR7,
    command=lambda: change_brows(root, canvas))
    brows.place(relx=0.70, rely=0.5, anchor="center", width=200, height=200)
    register(brows)

    nose = tk.Button(root, text="Nina", font=("Segoe UI", 24, "bold"), bg=COLOUR5, fg=COLOUR7,
    bd=3, relief="raised", activebackground=COLOUR2, activeforeground=COLOUR7,
    command=lambda: change_nose(root, canvas))
    nose.place(relx=0.90, rely=0.5, anchor="center", width=200, height=200)
    register(nose)


# change face everything together
def change_face_full(root, canvas):
    clear_screen(canvas)
    back_button(root, lambda: face_change_cat(root, canvas))

    title = tk.Label(root, text="Terved näoilmed", font=("Arial", 40))
    title.place(relx=0.5, rely=0.1, anchor="center")
    register(title)

    img = Image.open(os.path.join(BASE_DIR, FULL_FACE))
    img = img.resize((150,100))
    happy_img = ImageTk.PhotoImage(img)

    full_face_btn = tk.Button(root, image=happy_img, font=("Segoe UI", 24, "bold"), bg=COLOUR5,
    fg=COLOUR7, bd=3, relief="raised", activebackground=COLOUR2, activeforeground=COLOUR7,
    command=lambda: print("terve nägu"))
    full_face_btn.image = happy_img
    full_face_btn.place(x=40, y=130, width=200, height=200)
    register(full_face_btn)


# change eyes
def change_eyes(root, canvas):
    clear_screen(canvas)
    back_button(root, lambda: face_change_cat(root, canvas))

    title = tk.Label(root, text="Silmad", font=("Arial", 40))
    title.place(relx=0.5, rely=0.1, anchor="center")
    register(title)

    pictures = [EYES_1, EYES_2, EYES_3, EYES_4, EYES_5, EYES_6, EYES_7, EYES_8]

    x = 40
    y = 130

    for i in range(0, 8):
        img = Image.open(os.path.join(BASE_DIR, pictures[i]))
        img = img.resize((200,200))
        eyes_img = ImageTk.PhotoImage(img)

        button = tk.Button(root, image=eyes_img, font=("Segoe UI", 24, "bold"), bg=COLOUR5,
        fg=COLOUR7, bd=3, relief="raised", activebackground=COLOUR2, activeforeground=COLOUR7,
        command=lambda: print("silmad"))
        button.image = eyes_img
        register(button)

        if i == 5:
            y += 220
            x = 40

        button.place(x=x, y=y, width=200, height=200)
        x += 250


# change mouth
def change_mouth(root, canvas):
    clear_screen(canvas)
    back_button(root, lambda: face_change_cat(root, canvas))

    title = tk.Label(root, text="Suu", font=("Arial", 40))
    title.place(relx=0.5, rely=0.1, anchor="center")
    register(title)

    pictures = [MOUTH_1, MOUTH_2, MOUTH_3, MOUTH_4, MOUTH_5, MOUTH_6, MOUTH_7, MOUTH_8,
                MOUTH_9, MOUTH_10, MOUTH_11, MOUTH_12]

    x = 40
    y = 130

    for i in range(0, 12):
        img = Image.open(os.path.join(BASE_DIR, pictures[i]))
        img = img.resize((200,200))
        eyes_img = ImageTk.PhotoImage(img)

        button = tk.Button(root, image=eyes_img, font=("Segoe UI", 24, "bold"), bg=COLOUR5,
        fg=COLOUR7, bd=3, relief="raised", activebackground=COLOUR2, activeforeground=COLOUR7,
        command=lambda: print("suu"))
        button.image = eyes_img
        register(button)

        if i == 5 or i == 10:
            y += 220
            x = 40

        button.place(x=x, y=y, width=200, height=200)
        x += 250



# change nose
def change_nose(root,canvas):
    pass


#change brows
def change_brows(root, canvas):
    clear_screen(canvas)
    back_button(root, lambda: face_change_cat(root, canvas))

    title = tk.Label(root, text="Kulmud", font=("Arial", 40))
    title.place(relx=0.5, rely=0.1, anchor="center")
    register(title)

    pictures = [BROWS_1, BROWS_2]

    x = 40
    y = 130

    for i in range(0, 2):
        img = Image.open(os.path.join(BASE_DIR, pictures[i]))
        img = img.resize((150,150))
        eyes_img = ImageTk.PhotoImage(img)

        button = tk.Button(root, image=eyes_img, font=("Segoe UI", 24, "bold"), bg=COLOUR5,
        fg=COLOUR7, bd=3, relief="raised", activebackground=COLOUR2, activeforeground=COLOUR7,
        command=lambda: print("kulmud"))
        button.image = eyes_img
        register(button)

        button.place(x=x, y=y, width=200, height=200)
        x += 250


# user menu screen
def user_menu(root, canvas):
    clear_screen(canvas)
    back_button(root, lambda: mode_panel(root, canvas))

    title = tk.Label(root, text="Kasutaja menüü", font=("Arial", 40))
    title.place(relx=0.5, rely=0.2, anchor="center")
    register(title)

    sub = tk.Button(root, text="Subtiitrid", font=("Segoe UI", 24, "bold"), bg=COLOUR5, fg=COLOUR7,
    bd=3, relief="raised", activebackground=COLOUR2, activeforeground=COLOUR7,
    command=lambda: print("subtiitrid"))
    sub.place(x=375, y=300, width=250, height=250)
    register(sub)

    vid = tk.Button(root, text="Videod", font=("Segoe UI", 24, "bold"), bg=COLOUR5, fg=COLOUR7,
    bd=3, relief="raised", activebackground=COLOUR2, activeforeground=COLOUR7,
    command=lambda: print("video"))
    vid.place(x=675, y=300, width=250, height=250)
    register(vid)


#Choose a video to watc
def watch_videos(root, canvas):
    clear_screen(canvas)
    back_button(root, lambda: mode_panel(root, canvas))


# gui beginning
def start_gui():
    root = tk.Tk()

    width = root.winfo_screenwidth()
    height = root.winfo_screenheight()

    root.geometry(f"{width}x{height}+0+0")

    root.overrideredirect(True)

    canvas = tk.Canvas(root, bg=BACKGROUND_COLOR, highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    lock_screen(root, canvas)

    enable_long_press(root, lambda: root.destroy())
    
    root.mainloop()



def enable_long_press(root, action):
    press_time = {"start": None}

    def on_press(event):
            press_time["start"] = event.time

    def on_release(event):
        if press_time["start"] is not None:
            if is_long_press(press_time["start"], event.time):
                action()

            press_time["start"] = None

    root.bind("<Button-1>", on_press)
    root.bind("<ButtonRelease-1>", on_release)