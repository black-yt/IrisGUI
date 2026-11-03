from contextlib import ExitStack, redirect_stdout
from io import StringIO
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from main import IrisController
from scripts.utils import DisplayWindow


def monitor(x=0, y=0, width=2560, height=1440, primary=True):
    return SimpleNamespace(x=x, y=y, width=width, height=height, is_primary=primary)


class LogWindowModeTests(unittest.TestCase):
    def make_window(self, mode, monitors=None, detection_error=None):
        root = Mock()
        root.winfo_screenwidth.return_value = 2560
        root.winfo_screenheight.return_value = 1440
        root.state.return_value = "withdrawn"
        root.withdraw.side_effect = lambda: setattr(root.state, "return_value", "withdrawn")
        root.deiconify.side_effect = lambda: setattr(root.state, "return_value", "normal")
        font = Mock()
        font.measure.return_value = 500
        with ExitStack() as stack:
            stack.enter_context(patch("scripts.utils.LOG_WINDOW_MODE", mode))
            stack.enter_context(patch("scripts.utils.get_monitors", return_value=monitors or [], side_effect=detection_error))
            stack.enter_context(patch("scripts.utils.tk.Tk", return_value=root))
            stack.enter_context(patch("scripts.utils.tkfont.Font", return_value=font))
            for name in ("tk.Frame", "tk.Label", "tk.Text", "ttk.Scrollbar"):
                stack.enter_context(patch("scripts.utils." + name))
            stack.enter_context(redirect_stdout(StringIO()))
            window = DisplayWindow()
        root.after.reset_mock()
        return window, root

    def test_normal_mode_preserves_primary_screen_position(self):
        window, root = self.make_window("normal")
        self.assertTrue(window.hide_during_capture)
        root.geometry.assert_called_once_with("620x1296+1910+72")

    def test_hidden_mode_never_reopens_for_logs_or_restore(self):
        window, root = self.make_window("hidden")
        window.show("Error: test failure")
        window.show("Task finished.")
        window.set_suppressed(False)
        window.safe_unhide()
        window.unhide_window()
        self.assertFalse(window.hide_during_capture)
        root.deiconify.assert_not_called()
        root.after.assert_not_called()
        window.text_widget.insert.assert_called()

    def test_normal_logs_cannot_reveal_window_during_capture(self):
        window, root = self.make_window("normal")
        window.show("Starting task")
        root.deiconify.assert_called_once()
        window.set_suppressed(True)
        window.hide_window()
        window.show("Log received while capturing")
        window.unhide_window()
        self.assertEqual(root.deiconify.call_count, 1)
        window.set_suppressed(False)
        window.unhide_window()
        self.assertEqual(root.deiconify.call_count, 2)

    def test_secondary_is_flush_left_and_full_height_including_negative_monitor_coordinates(self):
        cases = [
            (monitor(2560, 0, 1920, 1080, False), "620x1080+2560+0"),
            (monitor(-1920, -240, 1920, 1080, False), "620x1080+-1920+-240"),
            (monitor(0, -1080, 1920, 1080, False), "620x1080+0+-1080"),
            (monitor(2560, 0, 500, 300, False), "440x300+2560+0"),
        ]
        for secondary, expected in cases:
            with self.subTest(expected=expected):
                # The OS may enumerate a secondary display before the primary.
                window, root = self.make_window("secondary", [secondary, monitor()])
                self.assertEqual(window.mode, "secondary")
                self.assertFalse(window.hide_during_capture)
                root.geometry.assert_called_once_with(expected)

    def test_secondary_does_not_repeatedly_deiconify_visible_log(self):
        window, root = self.make_window("secondary", [monitor(), monitor(2560, 0, 1920, 1080, False)])
        window.show("First log")
        window.show("Next log")
        window.unhide_window()
        root.deiconify.assert_called_once()

    def test_secondary_falls_back_when_missing_or_mirrored(self):
        for monitors in ([], [monitor()], [monitor(), monitor(primary=False)]):
            with self.subTest(monitors=monitors):
                window, root = self.make_window("secondary", monitors)
                self.assertEqual(window.mode, "normal")
                self.assertTrue(window.hide_during_capture)
                root.geometry.assert_called_once_with("620x1296+1910+72")

    def test_monitor_detection_failure_falls_back_without_aborting(self):
        window, root = self.make_window("secondary", detection_error=RuntimeError("enumeration unavailable"))
        self.assertEqual(window.mode, "normal")
        self.assertTrue(window.hide_during_capture)

    def test_origin_identifies_primary_when_backend_omits_primary_flag(self):
        secondary = monitor(-1920, 0, 1920, 1080, None)
        primary = monitor(primary=None)
        window, root = self.make_window("secondary", [secondary, primary])
        self.assertEqual(window.mode, "secondary")
        root.geometry.assert_called_once_with("620x1080+-1920+0")


class ControllerLogModeTests(unittest.TestCase):
    def test_only_normal_mode_hides_for_capture_and_actions(self):
        for mode in ("normal", "hidden", "secondary"):
            with self.subTest(mode=mode):
                controller = IrisController.__new__(IrisController)
                controller.running = True
                controller.window = Mock(hide_during_capture=mode == "normal")

                def run_step(**kwargs):
                    callbacks = factory.call_args.kwargs
                    callbacks["pre_callback"]()
                    callbacks["post_callback"]()
                    return "[Task Completed]: test"

                with patch("main.IrisAgent") as factory, patch("main.time.sleep") as sleep, redirect_stdout(StringIO()):
                    factory.return_value.step.side_effect = run_step
                    controller.run_agent("test")
                if mode == "normal":
                    controller.window.safe_hide.assert_called_once()
                    self.assertEqual(controller.window.set_suppressed.call_count, 2)
                    sleep.assert_called_once_with(0.5)
                else:
                    controller.window.safe_hide.assert_not_called()
                    controller.window.set_suppressed.assert_not_called()
                    sleep.assert_not_called()
                self.assertFalse(controller.running)


if __name__ == "__main__":
    unittest.main()
