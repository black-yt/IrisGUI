import os
import unittest
from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace
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
from scripts.grid_coordinates import GridCoordinateMap, GridTransform


class ActionExecutorTests(unittest.TestCase):
    def make_executor(self):
        events = []
        executor = tools.ActionExecutor.__new__(tools.ActionExecutor)
        executor.pre_callback = lambda: events.append("pre")
        executor.post_callback = lambda: events.append("post")
        executor.mouse_x = 0
        executor.mouse_y = 0
        executor._recent_actions = []
        return executor, events

    @patch("scripts.tools.time.sleep")
    @patch("scripts.tools.pyautogui.moveTo")
    def test_resolved_mouse_reversal_reports_reminder_and_executes_move(self, move, sleep):
        executor, _ = self.make_executor()
        executor.mouse_x, executor.mouse_y = 15, 370
        first = executor.execute({"action_type": "move", "point_id": "L-10-11"}, {"L-10-11": (15, 390)})
        second = executor.execute({"action_type": "move", "point_id": "L-10-09"}, {"L-10-09": (15, 370)})
        self.assertNotIn(tools.ActionExecutor.LOOP_REMINDER, first)
        self.assertIn(tools.ActionExecutor.LOOP_REMINDER, second)
        self.assertEqual(move.call_count, 2)

    @patch("scripts.tools.time.sleep")
    @patch("scripts.tools.pyautogui.hotkey")
    def test_repeated_hotkey_sequence_reports_reminder(self, hotkey, sleep):
        executor, _ = self.make_executor()
        for key in ("left", "right", "left"):
            feedback = executor.execute({"action_type": "hotkey", "keys": [key]})
            self.assertNotIn(tools.ActionExecutor.LOOP_REMINDER, feedback)
        feedback = executor.execute({"action_type": "hotkey", "keys": ["right"]})
        self.assertIn(tools.ActionExecutor.LOOP_REMINDER, feedback)
        self.assertIn(tools.ActionExecutor.INTERACTION_REMINDER, feedback)
        self.assertEqual(hotkey.call_count, 4)

    @patch("scripts.tools.pyautogui.position", side_effect=FileNotFoundError(2, "No such file or directory"))
    def test_initial_mouse_position_failure_falls_back_to_origin(self, position):
        with redirect_stdout(StringIO()) as output:
            executor = tools.ActionExecutor()

        self.assertEqual((executor.mouse_x, executor.mouse_y), (0, 0))
        self.assertIn("Unable to read initial mouse position", output.getvalue())

    @patch("scripts.tools.pyautogui.position", side_effect=FileNotFoundError(2, "No such file or directory"))
    def test_current_mouse_position_failure_uses_tracked_position(self, position):
        executor, _ = self.make_executor()
        executor.mouse_x = 12
        executor.mouse_y = 34

        with redirect_stdout(StringIO()) as output:
            position = executor.get_mouse_position()

        self.assertEqual(position, (12, 34))
        self.assertIn("Unable to read current mouse position", output.getvalue())

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
    @patch("scripts.tools.pyautogui.moveTo")
    def test_continuous_move_reaches_pixel_between_lines_and_tracks_destination(self, move_to, sleep):
        executor, events = self.make_executor()
        points = GridCoordinateMap(transforms={"L": GridTransform(
            step=20, width=400, height=400,
            offset_x=300, offset_y=500,
            anchor_x=200, anchor_y=200, anchor_col=10, anchor_row=10,
        )})

        result = executor.execute({"action_type": "move", "point_id": "L-10-10.32"}, points)

        self.assertEqual(result, "Action move to L-10-10.32 executed.")
        move_to.assert_called_once_with(500, 706, duration=0.5, tween=tools.pyautogui.easeInOutQuad)
        self.assertEqual((executor.mouse_x, executor.mouse_y), (500, 706))
        self.assertEqual(events, ["pre", "post"])

    @patch("scripts.tools.time.sleep")
    @patch("scripts.tools.pyautogui.moveTo")
    def test_invalid_continuous_move_does_not_move_mouse(self, move_to, sleep):
        points = GridCoordinateMap(transforms={"G": GridTransform(100, 500, 300)})
        for point_id in ("G-05.01-00", "G-NaN-00", "L-10-10.32"):
            with self.subTest(point_id=point_id):
                executor, _ = self.make_executor()
                result = executor.execute({"action_type": "move", "point_id": point_id}, points)
                self.assertTrue(result.startswith("Error:"))
                self.assertEqual((executor.mouse_x, executor.mouse_y), (0, 0))
        move_to.assert_not_called()

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

        self.assertEqual(result, "Action type 'hello' executed. " + tools.ActionExecutor.INTERACTION_REMINDER)
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

        self.assertEqual(result, f"Action type '{'x' * 40}' executed. " + tools.ActionExecutor.INTERACTION_REMINDER)
        write.assert_not_called()
        hotkey.assert_called_once_with("ctrl", "v")
        self.assertEqual(copy.call_args_list, [call("x" * 40), call("old clipboard")])

    @patch("scripts.tools.time.sleep")
    @patch("scripts.tools.pyautogui.scroll")
    def test_scroll_uses_configured_click_counts(self, scroll, sleep):
        executor, _ = self.make_executor()

        result = executor.execute({"action_type": "scroll", "direction": "down", "amount": "half"})

        self.assertEqual(result, "Action scroll down half executed. " + tools.ActionExecutor.INTERACTION_REMINDER)
        scroll.assert_called_once_with(-tools.SCROLL_HALF_CLICKS)

    @patch("scripts.tools.time.sleep")
    @patch("scripts.tools.prompt_for_user_input", return_value=SimpleNamespace(text="personal account\nuse profile 2", delay_seconds=2.5))
    def test_ask_input_prompts_user_and_returns_response(self, prompt_mock, sleep):
        executor, events = self.make_executor()
        logs = []

        with redirect_stdout(StringIO()) as output:
            result = executor.execute(
                {"action_type": "ask_input", "question": "Which account should I use?"},
                log_callback=logs.append,
            )

        self.assertEqual(result, "Action ask_input executed. User response: personal account\nuse profile 2")
        self.assertEqual(events, [])
        self.assertIn("Iris is waiting for your input", output.getvalue())
        self.assertIn("Which account should I use?", output.getvalue())
        self.assertIn("User input received. Continuing after 2.5 seconds.", output.getvalue())
        self.assertIn("Iris is waiting for your input", "".join(logs))
        self.assertIn("Which account should I use?", "".join(logs))
        self.assertIn("User input received. Continuing after 2.5 seconds.", "".join(logs))
        prompt_mock.assert_called_once_with("Which account should I use?")
        sleep.assert_called_once_with(2.5)

    @patch("scripts.tools.time.sleep")
    @patch("scripts.tools.prompt_for_user_input", return_value=None)
    def test_ask_input_handles_user_cancel(self, prompt_mock, sleep):
        executor, _ = self.make_executor()

        with redirect_stdout(StringIO()):
            result = executor.execute({"action_type": "ask_input", "question": "Continue?"})

        self.assertEqual(result, "Action ask_input executed. User response: [User cancelled input]")
        prompt_mock.assert_called_once_with("Continue?")
        sleep.assert_not_called()

    @patch("scripts.tools.time.sleep")
    @patch("scripts.tools.prompt_for_user_input")
    def test_ask_input_requires_question(self, prompt_mock, sleep):
        executor, events = self.make_executor()

        result = executor.execute({"action_type": "ask_input"})

        self.assertEqual(result, "Error: 'question' is required for ask_input action.")
        self.assertEqual(events, [])
        prompt_mock.assert_not_called()
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
