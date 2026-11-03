import io
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from scripts.console import configure_console_encoding


class ConsoleEncodingTests(unittest.TestCase):
    def test_gbk_streams_accept_unicode_output_and_utf8_input(self):
        text = "科研任务 🛑 ✅ ╭─╮"
        input_bytes = io.BytesIO((text + "\n").encode("utf-8"))
        output_bytes = io.BytesIO()
        error_bytes = io.BytesIO()
        stdin = io.TextIOWrapper(input_bytes, encoding="gbk")
        stdout = io.TextIOWrapper(output_bytes, encoding="gbk")
        stderr = io.TextIOWrapper(error_bytes, encoding="gbk")
        try:
            with patch.multiple(sys, stdin=stdin, stdout=stdout, stderr=stderr):
                configure_console_encoding()
                self.assertEqual(input(), text)
                print(text)
                print(text, file=sys.stderr)
                sys.stdout.flush()
                sys.stderr.flush()
            self.assertEqual(output_bytes.getvalue().decode("utf-8"), text + os.linesep)
            self.assertEqual(error_bytes.getvalue().decode("utf-8"), text + os.linesep)
        finally:
            stdin.close()
            stdout.close()
            stderr.close()

    def test_captured_or_missing_streams_are_supported(self):
        capture = io.StringIO()
        with patch.multiple(sys, stdin=io.StringIO(), stdout=capture, stderr=None):
            configure_console_encoding()
            print("标注完成 ✅")
        self.assertEqual(capture.getvalue(), "标注完成 ✅\n")

    def test_already_read_input_does_not_prevent_output_configuration(self):
        stdin = io.TextIOWrapper(io.BytesIO(b"input\n"), encoding="ascii")
        stdout = io.TextIOWrapper(io.BytesIO(), encoding="gbk")
        try:
            stdin.read(1)
            with patch.multiple(sys, stdin=stdin, stdout=stdout, stderr=None):
                configure_console_encoding()
                self.assertEqual(sys.stdout.encoding, "utf-8")
        finally:
            stdin.close()
            stdout.close()

    def test_main_bootstrap_handles_legacy_encoding_without_starting_agent(self):
        # Cancel the launcher before any controller, GUI, listener or API call starts.
        bootstrap = (
            "import runpy; "
            "import scripts.terminal_input as terminal; "
            "terminal.prompt_for_task=lambda *args: None; "
            "runpy.run_path('main.py', run_name='__main__')"
        )
        env = dict(os.environ, PYTHONIOENCODING="gbk")
        result = subprocess.run(
            [sys.executable, "-c", bootstrap],
            cwd=Path(__file__).resolve().parents[1],
            env=env, capture_output=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))
        self.assertIn("No task selected, exiting.", result.stdout.decode("utf-8"))
        self.assertIn("╭", result.stdout.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
