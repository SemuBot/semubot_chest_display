import tkinter as tk
from tkinter import *
from PIL import Image, ImageTk

main = tk.Tk()
main.title("Main Window")
main.attributes('-fullscreen', True)


"""Funktsioon, millega loome uue ekraani, kui vajutada, et soovid muuta SemuBoti näoilmet"""
def Open_ChangeFace():
    new_window = Toplevel(main)
    new_window.title("New Window")
    new_window.attributes('-fullscreen', True) 
    Label(new_window, text="Vali, kuidas mida soovid näo juures muuta").pack(pady=20)
    
    "Nupp, millega saab minna tagasi eelmisele lehele"
    back = Button(new_window, text="Tagasi", command=new_window.destroy)
    back.place(x=20, y=20, width=75, height=30)

    x = 20

    for i in range(0, 5):
        command_i = commands[i]
        text_i = texts[i]
        y = 70
        button = Button(new_window, text=text_i, command=command_i)
        button.place(x=x, y=y, width=230, height=230)
        x += 250


"""Funktsioon, millega avatakse valik tervikutest näoilmetest"""
def Open_ChangeFullFace():
    new_window = Toplevel(main)
    new_window.title("New Window")
    new_window.attributes('-fullscreen', True) 
    Label(new_window, text="Vali, sobiv näoilme").pack(pady=20)

    "Nupp, millega saab minna tagasi eelmisele lehele"
    back_f = Button(new_window, text="Tagasi", command=new_window.destroy)
    back_f.place(x=20, y=20, width=75, height=30)

    photo_f1 = Image.open(r"C:\Users\helen\Desktop\Bakalaureusetoo\Naoilmed\Terve_nagu.PNG")
    photo_f1 = photo_f1.resize((200,100))
    photoimage_f1 = ImageTk.PhotoImage(photo_f1)
    new_window.photoimage_f1 = photoimage_f1
    fullface_1 = Button(new_window, image=photoimage_f1, compound=TOP)
    fullface_1.place(x=20, y=70, width=230, height=230)


"""Funktsioon, millega avatakse valik silmadest"""
def Open_ChangeEyes():
    new_window = Toplevel(main)
    new_window.title("New Window")
    new_window.attributes('-fullscreen', True) 
    Label(new_window, text="Vali, kuidas mida soovid näo juures muuta").pack(pady=20)
    
    "Nupp, millega saab minna tagasi eelmisele lehele"
    back = Button(new_window, text="Tagasi", command=new_window.destroy)
    back.place(x=20, y=20, width=75, height=30)

    x = 20

    for i in range(0, 5):
        command_i = commands[i]
        text_i = texts[i]
        y = 70
        button = Button(new_window, text=text_i, command=command_i)
        button.place(x=x, y=y, width=200, height=200)
        x += 250

        
"""constants"""
commands = [Open_ChangeFullFace]
#, Open_ChangeEyes, Open_ChangeBrows, Open_ChangeNose, Open_ChangeMouth

texts = ["Terve näoilme", "Silmad", "Kulmud", "Nina", "Suu"]

photos = ["Terve_nagu.PNG"]

path = r"C:\Users\helen\Desktop\Bakalaureusetoo\Naoilmed"

"""Main kood"""
Label(main, text='Mida soovid teha?').pack(pady=10)
"""Nupp, millega avatakse uus akend, kus saab hakata näoilmeid valima"""
SB_face = Button(main, text="SemuBoti näoilmed", command=Open_ChangeFace)
SB_face.place(x=20, y=70, width=230, height=230)
main.mainloop()