import os
import unittest
from unittest.mock import call, patch

os.environ.setdefault("LLM_API_ENDPOINT", "http://example.invalid/v1")
os.environ.setdefault("LLM_API_KEY", "sk-test")
os.environ.setdefault("LLM_MODEL_NAME", "fake-model")
os.environ.setdefault("GRID_STEP", "100")
os.environ.setdefault("LOCAL_GRID_STEP", "20")
os.environ.setdefault("CROP_SIZE", "400")
os.environ.setdefault("GRID_COLOR", "red")
os.environ.setdefault("GRID_WIDTH", "1")
os.environ.setdefault("MOUSE_COLOR", "white")
os.environ.setdefault("MOUSE_WIDTH", "4")
os.environ.setdefault("MAX_STEPS", "100")
os.environ.setdefault("DEBUG_MODE", "False")
os.environ.setdefault("ACTION_SETTLE_SECONDS", "0.2")
os.environ.setdefault("TYPE_INTERVAL_SECONDS", "0.01")
os.environ.setdefault("CLIPBOARD_TEXT_THRESHOLD", "30")
os.environ.setdefault("SCROLL_LINE_CLICKS", "100")
os.environ.setdefault("SCROLL_HALF_CLICKS", "200")
os.environ.setdefault("SCROLL_PAGE_CLICKS", "400")
os.environ.setdefault("MEMORY_SHORT_TOKEN_BUDGET", "128000")
os.environ.setdefault("MEMORY_LONG_TOKEN_BUDGET", "128000")
os.environ.setdefault("MEMORY_RECENT_INTERACTIONS_TO_KEEP", "3")
os.environ.setdefault("MEMORY_CHARS_PER_TOKEN", "4")

import scripts.tools as tools


class ActionExecutorTests(unittest.TestCase):
    def make_executor(self):
        events = []
        executor = tools.ActionExecutor.__new__(tools.ActionExecutor)
        executor.pre_callback = lambda: events.append("pre")
        executor.post_callback = lambda: events.append("post")
        executor.mouse_x = 0
        executor.mouse_y = 0
        return executor, events

    @patch("scripts.tools.time.sleep")
    @patch("scripts.tools.pyautogui.moveTo")
    def test_move_feedback_does_not_expose_absolute_coordinates_and_callbacks_run(self, move_to, sleep):
        executor, events = self.make_executor()

        result = executor.execute({"action_type": "move", "point_id": "G-01-01"}, {"G-01-01": (799, 599)})

        self.assertEqual(result, "Action move to G-01-01 executed.")
        self.assertNotIn("(799, 599)", result)
        self.assertEqual(events, ["pre", "post"])
        self.assertEqual((executor.mouse_x, executor.mouse_y), (799, 599))
        move_to.assert_called_once()
        sleep.assert_called_once_with(tools.ACTION_SETTLE_SECONDS)

    @patch("scripts.tools.time.sleep")
    def test_callbacks_run_for_early_error_return(self, sleep):
        executor, events = self.make_executor()

        result = executor.execute({"action_type": "move"}, {})

        self.assertIn("'point_id' is required", result)
        self.assertEqual(events, ["pre", "post"])
        sleep.assert_called_once_with(tools.ACTION_SETTLE_SECONDS)

    @patch("scripts.tools.time.sleep")
    @patch("scripts.tools.pyautogui.write")
    def test_short_ascii_type_uses_keyboard_write(self, write, sleep):
        executor, events = self.make_executor()

        result = executor.execute({"action_type": "type", "text": "hello"})

        self.assertEqual(result, "Action type 'hello' executed.")
        write.assert_called_once_with("hello", interval=tools.TYPE_INTERVAL_SECONDS)
        self.assertEqual(events, ["pre", "post"])

    @patch("scripts.tools.time.sleep")
    @patch("scripts.tools.pyautogui.write")
    @patch("scripts.tools.pyautogui.hotkey")
    @patch("scripts.tools.pyperclip.copy")
    @patch("scripts.tools.pyperclip.paste", return_value="old clipboard")
    def test_long_type_uses_clipboard_and_restores_previous_clipboard(self, paste, copy, hotkey, write, sleep):
        executor, _ = self.make_executor()

        result = executor.execute({"action_type": "type", "text": "x" * 40})

        self.assertEqual(result, f"Action type '{'x' * 40}' executed.")
        write.assert_not_called()
        hotkey.assert_called_once_with("ctrl", "v")
        self.assertEqual(copy.call_args_list, [call("x" * 40), call("old clipboard")])

    @patch("scripts.tools.time.sleep")
    @patch("scripts.tools.pyautogui.scroll")
    def test_scroll_uses_configured_click_counts(self, scroll, sleep):
        executor, _ = self.make_executor()

        result = executor.execute({"action_type": "scroll", "direction": "down", "amount": "half"})

        self.assertEqual(result, "Action scroll down half executed.")
        scroll.assert_called_once_with(-tools.SCROLL_HALF_CLICKS)


if __name__ == "__main__":
    unittest.main()
