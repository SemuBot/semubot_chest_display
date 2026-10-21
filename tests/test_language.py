"""Exercise the actual Tk menus without publishing to the robot."""
import json
import os
import tempfile
import tkinter as tk
from unittest.mock import MagicMock, patch

import new_functions as ui
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
    ros.vad_threshold = 1000
    ros.recent_levels.return_value = []
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, 'settings.json')
        with open(path, 'w') as file:
            json.dump({'image': 'images/logos/Logo.PNG', 'face_background_color': '#DDF4FF'}, file)
        with patch.object(ui, 'SETTINGS_PATH', path), patch.object(ui, 'RobotRos', return_value=ros):
            app = ui.ChestDisplayApp(root, 1280, 800)
            app.show_login()
            assert 'Admin sisenemine' in texts(root)
            button(root, 'English').invoke()
            assert app.language == 'en' and 'Admin login' in texts(root)
            assert 'Log in' in texts(root)
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
                         app.show_audio_settings, app.show_wifi_settings):
                show()
                root.update_idletasks()
                assert '← Back' in texts(root)
            app.show_admin()
            button(root, 'Eesti').invoke()
            assert app.language == 'et' and 'Admin menüü' in texts(root)
            assert 'Heli seaded' in texts(root)
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
