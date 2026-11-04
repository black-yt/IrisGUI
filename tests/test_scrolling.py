import ctypes
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scripts import scrolling


class WindowsWheelTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "Checks actual Windows ctypes function isolation")
    def test_scroll_does_not_change_pyautogui_mouse_signature(self):
        shared = scrolling.pyautogui.platformModule.ctypes.windll.user32.mouse_event
        original_argtypes = shared.argtypes
        try:
            # Stop before any OS input is sent, after the DLL function setup.
            with patch("scripts.scrolling.pyautogui.failSafeCheck", side_effect=RuntimeError("stop before input")):
                with self.assertRaisesRegex(RuntimeError, "stop before input"):
                    scrolling._send_windows_wheel(280, False)
            self.assertIs(shared.argtypes, original_argtypes)
        finally:
            shared.argtypes = original_argtypes

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
            ("down", 3, -840, False),
            ("right", 1.5, 420, True),
            ("up", 100, 28000, False),
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
        for amount in (0, -0.01, 100.00001, True, None, "0.32", float("nan"), float("inf")):
            with self.subTest(amount=amount):
                with self.assertRaises(ValueError):
                    scrolling.scroll_wheel("up", amount)
        send.assert_not_called()

    @patch("scripts.scrolling.pyautogui.failSafeCheck")
    @patch("scripts.scrolling.time.sleep")
    def test_native_events_preserve_axis_sign_and_large_totals(self, sleep, failsafe):
        for delta, horizontal, flag in ((60, False, 0x0800), (-150, False, 0x0800),
                                         (-12, True, 0x1000), (300, True, 0x1000),
                                         (480000, False, 0x0800), (-480000, True, 0x1000)):
            with self.subTest(delta=delta, horizontal=horizontal):
                mouse_event = Mock()
                user32 = SimpleNamespace(mouse_event=mouse_event)
                with patch.object(scrolling.ctypes, "WinDLL", return_value=user32, create=True):
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

    @patch("scripts.scrolling.sys.platform", "win32")
    @patch("scripts.scrolling.pyautogui.failSafeCheck")
    @patch("scripts.scrolling.time.sleep")
    def test_larger_amount_sends_continuous_wheel_events(self, sleep, failsafe):
        mouse_event = Mock()
        user32 = SimpleNamespace(mouse_event=mouse_event)
        with patch.object(scrolling.ctypes, "WinDLL", return_value=user32, create=True):
            self.assertEqual(scrolling.scroll_wheel("down", 3), 840)
        self.assertEqual(mouse_event.call_count, 7)
        for event in mouse_event.call_args_list:
            self.assertEqual(event.args, (0x0800, 0, 0, ctypes.c_uint32(-120).value, 0))
        self.assertEqual(sleep.call_count, 7)  # Six intervals, one final pause.
        self.assertEqual([item.args[0] for item in sleep.call_args_list[:-1]], [0.01] * 6)
        self.assertEqual(sleep.call_args_list[-1].args, (scrolling.pyautogui.PAUSE,))

    @patch("scripts.scrolling.pyautogui.failSafeCheck", side_effect=RuntimeError("failsafe"))
    def test_native_scroll_respects_failsafe(self, failsafe):
        mouse_event = Mock()
        user32 = SimpleNamespace(mouse_event=mouse_event)
        with patch.object(scrolling.ctypes, "WinDLL", return_value=user32, create=True):
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
