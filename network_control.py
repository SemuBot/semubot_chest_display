"""Wi-Fi and local IPv4 information for the chest display."""

from dataclasses import dataclass
import json
import os
import subprocess


class NetworkError(Exception):
    """A network command could not complete."""


@dataclass(frozen=True)
class WifiNetwork:
    ssid: str
    signal: int
    security: str
    active: bool


def _run(command, timeout=10, secret=None):
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, check=True, timeout=timeout,
            env={**os.environ, "LC_ALL": "C"},
        )
    except FileNotFoundError as error:
        raise NetworkError(f"{command[0]} is not installed") from error
    except subprocess.TimeoutExpired as error:
        raise NetworkError("The network service did not respond") from error
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or "").strip()
        if secret:
            detail = detail.replace(secret, "***")
        raise NetworkError(detail or "Network operation failed") from error
    return result.stdout.strip()


def _split_terse(line):
    """Split nmcli's colon fields, respecting backslash-escaped colons."""
    fields = []
    current = []
    escaped = False
    for character in line:
        if escaped:
            current.append(character)
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == ":":
            fields.append("".join(current))
            current = []
        else:
            current.append(character)
    if escaped:
        current.append("\\")
    fields.append("".join(current))
    return fields


def list_wifi_networks():
    output = _run([
        "nmcli", "-t", "-e", "yes", "-f", "IN-USE,SSID,SIGNAL,SECURITY",
        "device", "wifi", "list", "--rescan", "yes",
    ], timeout=12)
    networks = {}
    for line in output.splitlines():
        fields = _split_terse(line)
        if len(fields) != 4:
            continue
        in_use, ssid, signal, security = fields
        if not ssid or ssid == "--":
            continue
        try:
            strength = max(0, min(100, int(signal)))
        except ValueError:
            strength = 0
        network = WifiNetwork(ssid, strength, security, in_use == "*")
        existing = networks.get(ssid)
        if existing is None or (network.active, network.signal) > (existing.active, existing.signal):
            networks[ssid] = network
    return sorted(networks.values(), key=lambda item: (not item.active, -item.signal, item.ssid.lower()))


def ipv4_addresses():
    output = _run(["ip", "-j", "-4", "address", "show", "scope", "global"], timeout=5)
    try:
        devices = json.loads(output)
    except ValueError as error:
        raise NetworkError("Could not read IPv4 addresses") from error
    addresses = []
    for device in devices:
        if device.get("operstate") == "DOWN":
            continue
        name = device.get("ifname", "?")
        for address in device.get("addr_info", []):
            if address.get("family") == "inet" and address.get("local"):
                addresses.append((name, address["local"]))
    return sorted(addresses, key=lambda item: (
        not item[0].startswith(("wl", "wlan")),
        not item[0].startswith(("en", "eth")),
        item[0],
    ))


def connect_wifi(ssid, password=""):
    if not ssid:
        raise ValueError("Wi-Fi network name is required")
    command = ["nmcli", "--wait", "20", "device", "wifi", "connect", ssid]
    if password:
        command.extend(["password", password])
    _run(command, timeout=25, secret=password)
