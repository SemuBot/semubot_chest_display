import os

# Background of every screen view
BACKGROUND_COLOR = "#E8FFFF"
COLOUR2 = "#00f0c7"
COLOUR5 = "#97f8e6"

# Swipe distance to unlock the screen (down -> up)
SWIPE_DISTANCE = 300

# Password to enter admin mode, from ~/.config/semubot/chest_display.env (not in git).
# Unset or empty keeps the admin menu locked.
ADMIN_PASSWORD = os.environ.get("CHEST_DISPLAY_ADMIN_PASSWORD", "")

# General file path
BASE_DIR = os.path.dirname(__file__)

# Default image path
LOGO_PATH = "images/logos/Logo.PNG"
