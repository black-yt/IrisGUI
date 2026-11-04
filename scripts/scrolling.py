"""Convert normalized scroll strength to integer native wheel units."""

import ctypes
import math
import sys
import time
from decimal import Decimal, ROUND_HALF_UP

import pyautogui


MAX_SCROLL_UNITS = 280
# WM_MOUSE(W)HEEL exposes a signed 16-bit delta. Split large totals to
# avoid wrapping that value in the receiving application.
MAX_EVENT_DELTA = 32760


def _send_windows_wheel(delta, horizontal):
    mouse_event = ctypes.windll.user32.mouse_event
    mouse_event.argtypes = [ctypes.c_uint32] * 4 + [ctypes.c_size_t]
    mouse_event.restype = None
    flag = 0x1000 if horizontal else 0x0800  # HWHEEL / WHEEL
    sign = 1 if delta > 0 else -1
    remaining = abs(delta)
    while remaining:
        pyautogui.failSafeCheck()
        part = min(remaining, MAX_EVENT_DELTA)
        mouse_event(flag, 0, 0, ctypes.c_uint32(sign * part).value, 0)
        remaining -= part


def scroll_wheel(direction, amount=1):
    """Send strength in (0, 1], defaulting to full strength; return native units.

    Full strength is 280 native units. Round halves upward and keep at least
    one unit so even the smallest positive strengths send an input event.
    """
    if not isinstance(direction, str) or direction not in {"up", "down", "left", "right"}:
        raise ValueError("scroll 'direction' must be up, down, left, or right")
    if type(amount) not in (int, float) or not 0 < amount <= 1 or not math.isfinite(amount):
        raise ValueError("scroll 'amount' must be a finite number greater than 0 and at most 1")

    units = max(1, int((Decimal(str(amount)) * MAX_SCROLL_UNITS).to_integral_value(rounding=ROUND_HALF_UP)))

    sign = -1 if direction in {"down", "left"} else 1
    horizontal = direction in {"left", "right"}
    if sys.platform == "win32":
        _send_windows_wheel(sign * units, horizontal)
        # Match PyAutoGUI's normal post-input pause, once per tool call.
        time.sleep(pyautogui.PAUSE)
        return units

    # PyAutoGUI's other backends accept integer wheel clicks as native units.
    scroll = pyautogui.hscroll if horizontal else pyautogui.scroll
    scroll(sign * units)
    return units
