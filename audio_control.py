"""Control the current user's PulseAudio or PipeWire audio outputs with pactl."""

import json
import math
import os
import re
import struct
import subprocess
import tempfile
import wave


class AudioError(Exception):
    """The audio service could not complete a requested operation."""


def _run(*arguments):
    try:
        result = subprocess.run(
            ["pactl", *arguments], capture_output=True, text=True,
            check=True, timeout=5, env={**os.environ, "LC_ALL": "C"},
        )
    except FileNotFoundError as error:
        raise AudioError("pactl is not installed") from error
    except subprocess.TimeoutExpired as error:
        raise AudioError("The audio service did not respond") from error
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or "").strip()
        raise AudioError(detail or "The audio service is unavailable") from error
    return result.stdout.strip()


def list_outputs():
    """Return (sink name, readable description) pairs."""
    try:
        data = json.loads(_run("--format=json", "list", "sinks"))
        if isinstance(data, dict):
            data = data.get("sinks", [])
        outputs = [
            (item["name"], item.get("description") or item["name"])
            for item in data
            if isinstance(item, dict) and item.get("name")
        ]
        if outputs:
            return outputs
    except (AudioError, ValueError, TypeError, KeyError):
        pass  # Older pactl versions may not provide JSON output.

    outputs = []
    for line in _run("list", "short", "sinks").splitlines():
        fields = line.split("\t")
        if len(fields) >= 2:
            outputs.append((fields[1], fields[1]))
    return outputs


def default_output():
    try:
        return _run("get-default-sink")
    except AudioError:
        # Older pactl versions expose the default only through `pactl info`.
        match = re.search(r"^Default Sink:\s*(.+)$", _run("info"), re.MULTILINE)
        if not match:
            raise AudioError("Could not read the default output")
        return match.group(1)


def volume_percent():
    output = _run("get-sink-volume", "@DEFAULT_SINK@")
    match = re.search(r"(\d+)%", output)
    if not match:
        raise AudioError("Could not read the current volume")
    return min(100, int(match.group(1)))


def set_volume_percent(value):
    if not isinstance(value, int) or not 0 <= value <= 100:
        raise ValueError("Volume must be between 0 and 100")
    _run("set-sink-volume", "@DEFAULT_SINK@", f"{value}%")
    if value > 0:
        _run("set-sink-mute", "@DEFAULT_SINK@", "0")


def set_default_output(name):
    if name not in {sink for sink, _label in list_outputs()}:
        raise ValueError("Output device is not available")
    _run("set-default-sink", name)
    # Move streams that were already playing to the newly selected device.
    try:
        for line in _run("list", "short", "sink-inputs").splitlines():
            stream_id = line.split("\t", 1)[0]
            if stream_id.isdigit():
                try:
                    _run("move-sink-input", stream_id, name)
                except AudioError:
                    pass  # Some applications pin their own output device.
    except AudioError:
        pass


def play_test_sound():
    """Play a short, quiet two-note chime through the selected output."""
    sample_rate = 16000
    frames = bytearray()
    for frequency in (440, 660):
        for index in range(int(sample_rate * 0.22)):
            fade = min(1.0, index / 800, (sample_rate * 0.22 - index) / 800)
            sample = int(7000 * fade * math.sin(2 * math.pi * frequency * index / sample_rate))
            frames.extend(struct.pack("<h", sample))
        frames.extend(b"\x00\x00" * int(sample_rate * 0.05))

    with tempfile.TemporaryDirectory() as directory:
        filename = os.path.join(directory, "test-sound.wav")
        with wave.open(filename, "wb") as sound:
            sound.setnchannels(1)
            sound.setsampwidth(2)
            sound.setframerate(sample_rate)
            sound.writeframes(frames)
        try:
            subprocess.run(
                ["paplay", "--device=@DEFAULT_SINK@", filename],
                check=True, capture_output=True, text=True, timeout=5,
            )
        except FileNotFoundError as error:
            raise AudioError("paplay is not installed") from error
        except subprocess.TimeoutExpired as error:
            raise AudioError("Test sound timed out") from error
        except subprocess.CalledProcessError as error:
            raise AudioError((error.stderr or "").strip() or "Could not play the test sound") from error
