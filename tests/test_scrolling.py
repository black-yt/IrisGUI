import ctypes
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scripts import scrolling


class WindowsWheelTests(unittest.TestCase):
    @patch("scripts.scrolling.sys.platform", "win32")
    @patch("scripts.scrolling.time.sleep")
    @patch("scripts.scrolling._send_windows_wheel")
    def test_strength_converts_to_signed_native_units(self, send, sleep):
        for direction, amount, delta, horizontal in (
            ("up", 0.5, 140, False),
            ("down", 1, -280, False),
            ("left", 0.1, -28, True),
            ("right", 0.32, 90, True),
            ("up", 0.01, 3, False),
            ("up", 0.1625, 46, False),
            ("up", 5e-324, 1, False),
            ("up", 0.1234567890123456, 35, False),
        ):
            with self.subTest(direction=direction, amount=amount):
                send.reset_mock()
                sleep.reset_mock()
                self.assertEqual(scrolling.scroll_wheel(direction, amount), abs(delta))
                send.assert_called_once_with(delta, horizontal)
                sleep.assert_called_once_with(scrolling.pyautogui.PAUSE)

    @patch("scripts.scrolling.sys.platform", "win32")
    @patch("scripts.scrolling.time.sleep")
    @patch("scripts.scrolling._send_windows_wheel")
    def test_default_strength_is_one(self, send, sleep):
        self.assertEqual(scrolling.scroll_wheel("up"), 280)
        send.assert_called_once_with(280, False)

    @patch("scripts.scrolling._send_windows_wheel")
    def test_invalid_strength_never_sends_input(self, send):
        for amount in (0, -0.01, 1.00001, True, None, "0.32", float("nan"), float("inf")):
            with self.subTest(amount=amount):
                with self.assertRaises(ValueError):
                    scrolling.scroll_wheel("up", amount)
        send.assert_not_called()

    @patch("scripts.scrolling.pyautogui.failSafeCheck")
    def test_native_events_preserve_axis_sign_and_large_totals(self, failsafe):
        for delta, horizontal, flag in ((60, False, 0x0800), (-150, False, 0x0800),
                                         (-12, True, 0x1000), (300, True, 0x1000),
                                         (480000, False, 0x0800), (-480000, True, 0x1000)):
            with self.subTest(delta=delta, horizontal=horizontal):
                mouse_event = Mock()
                windll = SimpleNamespace(user32=SimpleNamespace(mouse_event=mouse_event))
                with patch.object(scrolling.ctypes, "windll", windll, create=True):
                    scrolling._send_windows_wheel(delta, horizontal)
                chunks = []
                for event in mouse_event.call_args_list:
                    actual_flag, dx, dy, data, extra = event.args
                    self.assertEqual((actual_flag, dx, dy, extra), (flag, 0, 0, 0))
                    part = ctypes.c_int32(data).value
                    self.assertLessEqual(abs(part), scrolling.MAX_EVENT_DELTA)
                    self.assertEqual(part > 0, delta > 0)
                    chunks.append(part)
                self.assertEqual(sum(chunks), delta)

    @patch("scripts.scrolling.pyautogui.failSafeCheck", side_effect=RuntimeError("failsafe"))
    def test_native_scroll_respects_failsafe(self, failsafe):
        mouse_event = Mock()
        windll = SimpleNamespace(user32=SimpleNamespace(mouse_event=mouse_event))
        with patch.object(scrolling.ctypes, "windll", windll, create=True):
            with self.assertRaisesRegex(RuntimeError, "failsafe"):
                scrolling._send_windows_wheel(60, False)
        mouse_event.assert_not_called()

    @patch("scripts.scrolling.sys.platform", "linux")
    @patch("scripts.scrolling.pyautogui.hscroll")
    @patch("scripts.scrolling.pyautogui.scroll")
    def test_other_platforms_receive_quantized_integer_units(self, scroll, hscroll):
        self.assertEqual(scrolling.scroll_wheel("down", 1), 280)
        scroll.assert_called_once_with(-280)
        self.assertEqual(scrolling.scroll_wheel("right", 0.32), 90)
        hscroll.assert_called_once_with(90)


if __name__ == "__main__":
    unittest.main()
