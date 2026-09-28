
from constants import SWIPE_DISTANCE, ADMIN_PASSWORD, LONG_PRESS_TIME


def swipe_ok(start, end):
    return abs(end - start) >= SWIPE_DISTANCE


def password_ok(text):
    return text == ADMIN_PASSWORD


def is_long_press(start_time, end_time):
    return (end_time - start_time) >= LONG_PRESS_TIME


ADMIN_PATTERN = [0, 1, 2, 5, 8, 7, 6]
 
def pattern_ok(drawn: list) -> bool:
    """Returns True if the drawn pattern matches the admin pattern."""
    return list(drawn) == ADMIN_PATTERN