import unittest

from scripts.utils import (
    ANSI_RESET,
    ANSI_STYLES,
    colorize_terminal,
    format_agent_loop,
    format_box,
    get_display_width,
    styled_line_segments,
)


class OutputFormattingTests(unittest.TestCase):
    def test_agent_loop_format_contains_sections(self):
        rendered = format_agent_loop(
            step=3,
            mouse_grid_id="L-02-04",
            nearest_global_grid_id="G-08-06",
            reasoning="The input field is already focused, so typing is safe.",
            tool_results=[
                {
                    "action": {"action_type": "type", "text": "hello", "submit": True},
                    "feedback": "Typed text and submitted.",
                }
            ],
            width=72,
        )

        self.assertIn("Iris Agent Loop · Step 3", rendered)
        self.assertIn("Perception", rendered)
        self.assertIn("Nearby global mouse grid: G-08-06", rendered)
        self.assertIn("Current local mouse grid: L-02-04", rendered)
        self.assertLess(
            rendered.index("Nearby global mouse grid: G-08-06"),
            rendered.index("Current local mouse grid: L-02-04"),
        )
        self.assertIn("Model Reasoning", rendered)
        self.assertIn("Tool Calls", rendered)
        self.assertIn("Feedback", rendered)
        self.assertIn("type(text='hello', submit=True)", rendered)
        self.assertTrue(rendered.startswith("╭"))
        self.assertTrue(rendered.endswith("╯"))
        border_lines = [line for line in rendered.splitlines() if line.startswith(("╭", "├", "╰"))]
        self.assertTrue(all("Perception" not in line for line in border_lines))
        self.assertTrue(all("Tool Calls" not in line for line in border_lines))
        self.assertEqual(len({get_display_width(line) for line in rendered.splitlines()}), 1)

    def test_format_box_wraps_chinese_text(self):
        rendered = format_box("测试", ["打开浏览器并搜索上海天气，然后总结结果。"], width=16)
        lines = rendered.splitlines()

        self.assertGreater(len(lines), 3)
        self.assertTrue(all(line.startswith(("╭", "├", "│", "╰")) for line in lines))

    def test_colorize_terminal_adds_ansi_when_forced(self):
        rendered = format_box("Task", ["Starting task"], width=24)
        colored = colorize_terminal(rendered, force=True)

        self.assertIn("\033[", colored)
        self.assertIn(ANSI_RESET, colored)

    def test_colorize_terminal_keeps_content_line_borders_in_border_color(self):
        rendered = format_box("Task", ["Starting task"], width=24)
        colored = colorize_terminal(rendered, force=True)
        title_line = colored.splitlines()[1]

        self.assertTrue(title_line.startswith(f"{ANSI_STYLES['border']}│ {ANSI_RESET}"))
        self.assertIn(f"{ANSI_STYLES['title']}Task", title_line)
        self.assertTrue(title_line.endswith(f"{ANSI_STYLES['border']} │{ANSI_RESET}"))

    def test_styled_line_segments_split_box_border_from_content(self):
        segments, current_section = styled_line_segments("│ Tool Calls                       │")

        self.assertEqual(current_section, "Tool Calls")
        self.assertEqual(segments[0], ("│ ", "box"))
        self.assertEqual(segments[1][1], "section")
        self.assertEqual(segments[2], (" │", "box"))


if __name__ == "__main__":
    unittest.main()
