import os
import sys

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import opaque_edge_color  # noqa: E402


def test_opaque_image_gives_its_corner_colour():
    assert opaque_edge_color(Image.new("RGB", (40, 20), (255, 255, 255))) == "#FFFFFF"
    image = Image.new("RGBA", (40, 20), (10, 20, 30, 255))
    image.putpixel((20, 10), (0, 0, 0, 0))  # transparency inside the image is fine
    assert opaque_edge_color(image) == "#0A141E"


def test_transparent_corner_means_logo_on_background():
    image = Image.new("RGBA", (40, 20), (255, 255, 255, 255))
    image.putpixel((39, 19), (255, 255, 255, 0))
    assert opaque_edge_color(image) is None
    assert opaque_edge_color(Image.new("LA", (4, 4), (0, 0))) is None


def test_original_logo_is_not_full_screen():
    path = os.path.join(os.path.dirname(__file__), "..", "images", "logos", "Logo.PNG")
    with Image.open(path) as image:
        assert opaque_edge_color(image) is None
