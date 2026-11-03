import os

# Background of every screen view
BACKGROUND_COLOR = "#E8FFFF"
COLOUR2 = "#00f0c7"
COLOUR5 = "#97f8e6"

# Tap sequence on the chest image that opens the admin PIN screen: corners as visitors see them
UNLOCK_SEQUENCE = ["top-left", "top-left", "bottom-right", "bottom-right", "bottom-right"]
UNLOCK_CORNER_SIZE = 150  # pixels from each edge that count as the corner
UNLOCK_TAP_GAP = 1.5  # seconds allowed between taps before the sequence starts over

# Password to enter admin mode, from ~/.config/semubot/chest_display.env (not in git).
# Unset or empty keeps the admin menu locked.
ADMIN_PASSWORD = os.environ.get("CHEST_DISPLAY_ADMIN_PASSWORD", "")

# General file path
BASE_DIR = os.path.dirname(__file__)

# Default image path
LOGO_PATH = "images/logos/Logo.PNG"

# Port of the webapp (repo semubot_webapp, uvicorn in app/main.py), shown as a QR code in the admin menu
WEBAPP_PORT = 8000
