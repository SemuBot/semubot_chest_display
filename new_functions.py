import tkinter as tk
from constants import *
from tkinter import *
from PIL import Image, ImageTk


# HELPERS
def clear_screen(canvas):
    canvas.delete("all")
    for w in current_widgets:
        try:
            w.destroy()
        except:
            pass
    current_widgets.clear()


# configurations for starting the gui
def start_gui():
    root = tk.Tk()
    width = root.winfo_screenwidth()
    height = root.winfo_screenheight()
    root.geometry(f"{width}x{height}")
    root.overrideredirect(True)
    canvas = tk.Canvas(root, bg=BACKGROUND_COLOR, highlightthickness=0)
    canvas.pack(fill="both", expand=True)
    default_screen(root, canvas)
    root.mainloop()


# display logo on the default (lock) screen
def default_screen(root, canvas):
    clear_screen(canvas)
    img = Image.open(os.path.join(BASE_DIR, LOGO_PATH))
    img = img.resize((400, 400))
    logo = ImageTk.PhotoImage(img)
    canvas.create_image(root.winfo_screenwidth()//2, root.winfo_screenheight()//2, image=logo)
    canvas.logo = logo