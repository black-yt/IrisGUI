"""Convert scroll amount to a sequence of integer native wheel events."""

import ctypes
import math
import sys
import time
from decimal import Decimal, ROUND_HALF_UP

import pyautogui


MAX_SCROLL_UNITS = 280
MAX_SCROLL_AMOUNT = 100
# Send at most one detent per event. Some GUI views react only once per
# wheel event regardless of its magnitude, so large totals need a stream.
MAX_EVENT_DELTA = 120
SCROLL_EVENT_INTERVAL_SECONDS = 0.01


def _send_windows_wheel(delta, horizontal):
    # windll.user32 caches functions shared with PyAutoGUI. Give this call its
    # own DLL wrapper so our argtypes cannot change PyAutoGUI's click ABI.
    mouse_event = ctypes.WinDLL("user32", use_last_error=True).mouse_event
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
        if remaining:
            time.sleep(SCROLL_EVENT_INTERVAL_SECONDS)


def scroll_wheel(direction, amount=1):
    """Send an amount in (0, 100], defaulting to 1; return native units.

    Amount 1 is 280 native units. Round halves upward and keep at least
    one unit so even the smallest positive strengths send an input event.
    """
    if not isinstance(direction, str) or direction not in {"up", "down", "left", "right"}:
        raise ValueError("scroll 'direction' must be up, down, left, or right")
    if type(amount) not in (int, float) or not 0 < amount <= MAX_SCROLL_AMOUNT or not math.isfinite(amount):
        raise ValueError("scroll 'amount' must be a finite number greater than 0 and at most 100")

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
