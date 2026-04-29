import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from scripts.terminal_input import MenuState, prompt_for_user_input, parse_delay_seconds


class MenuStateTests(unittest.TestCase):
    def test_up_down_selection_cycles_actions(self):
        state = MenuState()

        self.assertEqual(state.selected_action(), "newline")
        state.select_next()
        self.assertEqual(state.selected_action(), "start_now")
        state.select_next()
        self.assertEqual(state.selected_action(), "start_5s")
        state.select_next()
        self.assertEqual(state.selected_action(), "start_custom")
        state.select_next()
        self.assertEqual(state.selected_action(), "clear")
        state.select_next()
        self.assertEqual(state.selected_action(), "exit")
        state.select_next()
        self.assertEqual(state.selected_action(), "newline")
        state.select_previous()
        self.assertEqual(state.selected_action(), "exit")

    def test_selected_action_returns_action_name(self):
        self.assertEqual(MenuState(selected_index=0).selected_action(), "newline")
        self.assertEqual(MenuState(selected_index=1).selected_action(), "start_now")
        self.assertEqual(MenuState(selected_index=3).selected_action(), "start_custom")
        self.assertEqual(MenuState(selected_index=5).selected_action(), "exit")

    def test_parse_delay_seconds(self):
        self.assertEqual(parse_delay_seconds("0"), 0)
        self.assertEqual(parse_delay_seconds("5"), 5)
        self.assertEqual(parse_delay_seconds("2.5"), 2.5)
        self.assertIsNone(parse_delay_seconds("-1"))
        self.assertIsNone(parse_delay_seconds("soon"))

    @patch("sys.stdout.isatty", return_value=False)
    @patch("sys.stdin.isatty", return_value=False)
    @patch("builtins.input", side_effect=["line one", "line two", "", "4", "2.5"])
    def test_user_input_fallback_supports_multiline_question_and_custom_delay(self, input_mock, stdin_tty, stdout_tty):
        with redirect_stdout(StringIO()) as output:
            result = prompt_for_user_input("Which account should I use?")

        self.assertEqual(result.text, "line one\nline two")
        self.assertEqual(result.delay_seconds, 2.5)
        self.assertIn("Iris Needs Your Input", output.getvalue())
        self.assertIn("Which account should I use?", output.getvalue())
        self.assertIn("Submit After Custom Delay", output.getvalue())

    @patch("sys.stdout.isatty", return_value=False)
    @patch("sys.stdin.isatty", return_value=False)
    @patch("builtins.input", side_effect=["", "6"])
    def test_user_input_fallback_can_cancel(self, input_mock, stdin_tty, stdout_tty):
        with redirect_stdout(StringIO()):
            result = prompt_for_user_input("Continue?")

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
