"""Exercise the actual Tk menus without publishing to the robot."""
import json
import os
import tempfile
import time
from types import SimpleNamespace
import tkinter as tk
from unittest.mock import MagicMock, patch

import app as ui
from translations import ENGLISH, translate


def widgets(root):
    for widget in root.winfo_children():
        yield widget
        yield from widgets(widget)


def texts(root):
    return [str(widget.cget('text')) for widget in widgets(root) if 'text' in widget.keys()]


def button(root, label):
    return next(widget for widget in widgets(root)
                if isinstance(widget, tk.Button) and widget.cget('text') == label)


def test_menu_language():
    if not os.environ.get("DISPLAY"):
        from unittest import SkipTest
        raise SkipTest("Tk menu checks need a graphical display")
    root = tk.Tk()
    root.withdraw()
    ros = MagicMock()
    ros.node = None
    ros.error = 'offline'
    ros.speech_mode = 'local'
    ros.tts_settings = None
    ros.cloud_usage = {'today': {'requests': 1, 'input_tokens': 12, 'output_tokens': 4},
                     'month': {'requests': 2, 'unpriced': 2}}
    ros.conversation_log = '[]'
    ros.robot_state = {'stage': 'thinking', 'mode': 'local'}
    ros.battery = None
    ros.vad_threshold = 1000
    ros.recent_levels.return_value = []
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, 'settings.json')
        with open(path, 'w') as file:
            json.dump({'image': 'images/logos/Logo.PNG', 'face_background_color': '#DDF4FF'}, file)
        with patch.object(ui, 'SETTINGS_PATH', path), patch.object(ui, 'RobotRos', return_value=ros):
            app = ui.ChestDisplayApp(root, 1280, 800)
            corner = {'tl': SimpleNamespace(x=20, y=20), 'br': SimpleNamespace(x=1260, y=780),
                      'mid': SimpleNamespace(x=640, y=400)}
            for taps, gap, opens in (('tl tl br br br', 1.5, True),
                                     ('tl br br br', 1.5, False),          # too few top-left taps
                                     ('tl tl mid br br br', 1.5, False),   # a tap elsewhere starts over
                                     ('br tl tl tl br br br', 1.5, True),  # extra taps before still work
                                     ('tl tl br br br', 0, False)):        # too slow
                app.show_display()
                with patch.object(ui, 'UNLOCK_TAP_GAP', gap):
                    for tap in taps.split():
                        app.unlock_tap(corner[tap])
                assert ('Admin sisenemine' in texts(root)) == opens, taps
            app.show_login()
            assert 'Admin sisenemine' in texts(root)
            button(root, 'English').invoke()
            assert app.language == 'en' and 'Admin login' in texts(root)
            assert 'Log in' in texts(root)
            for password, typed, opens in (('', '42', False), ('42', '41', False), ('42', '42', True)):
                with patch.object(ui, 'ADMIN_PASSWORD', password):  # '' = no PIN in chest_display.env
                    app.show_login()
                    for key in typed:
                        button(root, key).invoke()
                    button(root, 'Log in').invoke()
                    assert ('Admin menu' in texts(root)) == opens, (password, typed)
                    assert ('Admin password is not set' in texts(root)) == (password == '')
            app.show_admin()
            assert 'Change display image' in texts(root)
            assert 'Audio settings' in texts(root)
            with open(path) as file:
                saved = json.load(file)
            assert saved['menu_language'] == 'en'
            assert saved['face_background_color'] == '#DDF4FF'
            assert saved['image'] == 'images/logos/Logo.PNG'
            for show in (app.show_speech_mode, app.show_voice, app.show_conversation,
                         app.show_microphone, app.show_speech, app.show_face_colors,
                         app.show_gallery, lambda: app.show_wifi_password('My network'),
                         app.show_audio_settings, app.show_wifi_settings, app.show_speed,
                         app.show_webapp_qr):
                show()
                root.update_idletasks()
                assert '← Back' in texts(root)
            with patch.object(ui.network, 'ipv4_addresses', return_value=[('wlo1', '10.0.0.5')]):
                app.show_webapp_qr()
                deadline = time.monotonic() + 3
                while 'http://10.0.0.5:8000' not in ' '.join(texts(root)) and time.monotonic() < deadline:
                    root.update()
            assert 'http://10.0.0.5:8000' in ' '.join(texts(root))
            assert bool(app.canvas.find_all()) == (ui.qrcode is not None)  # the QR image
            app.show_login()
            with patch.object(ui, 'MENU_IDLE_SECONDS', 0):
                deadline = time.monotonic() + 3
                while not app.on_display and time.monotonic() < deadline:
                    root.update()
            assert app.on_display and 'Admin login' not in texts(root)  # idle login went back to the image
            for watched in (app.show_conversation, app.show_microphone):  # screens without the timeout
                watched()
                with patch.object(ui, 'MENU_IDLE_SECONDS', 1):  # shorter than the run, longer than a refresh
                    deadline = time.monotonic() + 2.5
                    while time.monotonic() < deadline:
                        root.update()
                assert not app.on_display, watched
            app.show_speed()
            for _ in range(3):
                button(root, '−').invoke()
            assert ui.selected_speed_scale() == 0.7 and '0.7' in texts(root)
            for _ in range(5):
                button(root, '+').invoke()
            assert ui.selected_speed_scale() == 1.0 and button(root, '+').cget('state') == 'disabled'
            ros.publish_speed_scale.assert_called_with(1.0)
            app.show_admin()
            button(root, 'Eesti').invoke()
            assert app.language == 'et' and 'Admin menüü' in texts(root)
            assert 'Heli seaded' in texts(root)
            assert not any('tühjenemas' in text for text in texts(root))
            ros.battery = (0.05, 23.5, time.monotonic())
            app.show_admin()
            assert '⚠  Aku on tühjenemas (5 % · 23.5 V) — pane robot laadima!' in texts(root)
            ros.battery = None
            app.close()
            root = tk.Tk()
            root.withdraw()
            restarted = ui.ChestDisplayApp(root, 1280, 800)
            assert restarted.language == 'et'
            restarted.show_login()
            button(root, 'English').invoke()
            restarted.close()
            root = tk.Tk()
            root.withdraw()
            restarted = ui.ChestDisplayApp(root, 1280, 800)
            assert restarted.language == 'en'
            restarted.show_admin()
            assert 'Admin menu' in texts(root)
            with patch.object(ui, 'save_setting', side_effect=OSError('read-only')), \
                 patch.object(ui.messagebox, 'showerror') as error:
                button(root, 'Eesti').invoke()
                assert restarted.language == 'en'
                error.assert_called_once()
            restarted.close()
    assert ui.battery_text(None, 0) == '—'
    assert ui.battery_text((0.76, 26.84, 100), 105) == '76 % · 26.8 V'
    assert ui.battery_text((float('nan'), 26.84, 100), 105) == '26.8 V'
    assert ui.battery_text((0.76, 26.84, 100), 111) == '—'  # stale
    assert ui.battery_level((0.05, 23.5, 100), 105) == 0.05
    assert ui.battery_level((float('nan'), 23.5, 100), 105) is None
    assert ui.battery_level((0.05, 23.5, 100), 111) is None  # stale: no warning from old data
    assert '1 request, 16 tokens' in ui.cloud_usage_text(ros.cloud_usage, 'today', 'en')
    assert '2 requests' in ui.cloud_usage_text(ros.cloud_usage, 'month', 'en')
    assert '1 päring, 16 sõnet' in ui.cloud_usage_text(ros.cloud_usage, 'today')
    import string
    for original, english in ENGLISH.items():
        fields = lambda text: {name for _, name, _, _ in string.Formatter().parse(text) if name}
        assert fields(original) == fields(english), original
    print('PASS: real menu buttons, all menu views, both languages, restart persistence, save failure, usage and translation placeholders')


if __name__ == '__main__':
    test_menu_language()
