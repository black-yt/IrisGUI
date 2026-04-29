import unittest

from scripts.terminal_input import MenuState, parse_delay_seconds


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


if __name__ == "__main__":
    unittest.main()
