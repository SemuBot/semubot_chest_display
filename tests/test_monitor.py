import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from new_functions import monitor_geometry  # noqa: E402

XRANDR = """Screen 0: minimum 16 x 16, current 3200 x 1440, maximum 32767 x 32767
HDMI-2 connected 1280x800+1920+0 inverted (normal left inverted right x axis y axis) 0mm x 0mm
   1280x800      63.59*+
DP-3 connected primary 1920x1440+0+0 right (normal left inverted right x axis y axis) 0mm x 0mm
   1440x1920     59.93*+
DP-1 disconnected (normal left inverted right x axis y axis)
"""


def test_finds_connected_monitor_by_name():
    assert monitor_geometry("HDMI-2", XRANDR) == "1280x800+1920+0"
    assert monitor_geometry("DP-3", XRANDR) == "1920x1440+0+0"


def test_missing_or_disconnected_monitor_gives_none():
    assert monitor_geometry("DP-1", XRANDR) is None
    assert monitor_geometry("HDMI-9", XRANDR) is None
    assert monitor_geometry("HDMI-2", "") is None


def test_name_must_match_exactly():
    assert monitor_geometry("HDMI", XRANDR) is None
