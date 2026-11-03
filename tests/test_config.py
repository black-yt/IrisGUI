import os
import json
from pathlib import Path
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

import scripts.config as config


class ReasoningEffortConfigTests(unittest.TestCase):
    def read_config(self, value):
        return subprocess.run([
            sys.executable, "-c",
            "import json; from scripts.config import reasoning_request_kwargs, openai_client_kwargs; "
            "assert 'reasoning_effort' not in openai_client_kwargs(); "
            "print(json.dumps(reasoning_request_kwargs()))",
        ], cwd=Path(__file__).resolve().parents[1],
            env=dict(os.environ, LLM_REASONING_EFFORT=value), capture_output=True, text=True)

    def test_default_normalization_and_supported_values(self):
        for value in ("", "   ", "none", "minimal", "low", " MEDIUM ", "high", "xhigh", "max", "omit"):
            with self.subTest(value=value):
                result = self.read_config(value)
                self.assertEqual(result.returncode, 0, result.stderr)
                normalized = value.strip().lower() or "low"
                expected = {} if normalized == "omit" else {"reasoning_effort": normalized}
                self.assertEqual(json.loads(result.stdout.splitlines()[-1]), expected)

    def test_invalid_effort_fails_at_startup(self):
        result = self.read_config("typo")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("LLM_REASONING_EFFORT must be one of", result.stderr)


class ScreenshotHistoryConfigTests(unittest.TestCase):
    def read_config(self, **settings):
        environment = dict(os.environ, MEMORY_IMAGE_ROUNDS="", MEMORY_IMAGE_TOKEN_MULTIPLIER="")
        environment.update(settings)
        return subprocess.run([
            sys.executable, "-c",
            "import json; from scripts.config import MEMORY_IMAGE_ROUNDS, MEMORY_IMAGE_TOKEN_MULTIPLIER; "
            "print(json.dumps([MEMORY_IMAGE_ROUNDS, MEMORY_IMAGE_TOKEN_MULTIPLIER]))",
        ], cwd=Path(__file__).resolve().parents[1], env=environment, capture_output=True, text=True)

    def test_defaults_and_positive_round_counts(self):
        for value, expected in (("", -1), ("-1", -1), ("1", 1), ("4", 4)):
            with self.subTest(value=value):
                result = self.read_config(MEMORY_IMAGE_ROUNDS=value)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), [expected, 1.2])

    def test_invalid_rounds_and_token_multipliers_fail_clearly(self):
        for name, values in (("MEMORY_IMAGE_ROUNDS", ("0", "-2")),
                             ("MEMORY_IMAGE_TOKEN_MULTIPLIER", ("0", "-1", "nan", "inf"))):
            for value in values:
                with self.subTest(name=name, value=value):
                    result = self.read_config(**{name: value})
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(name, result.stderr)


class LogWindowConfigTests(unittest.TestCase):
    def test_default_and_normalized_modes(self):
        for value, expected in (("", "normal"), ("   ", "normal"), ("normal", "normal"),
                                (" HIDDEN ", "hidden"), ("secondary", "secondary")):
            with self.subTest(value=value), patch.dict(os.environ, {"LOG_WINDOW_MODE": value}):
                self.assertEqual(config._get_choice("LOG_WINDOW_MODE", "normal", ("normal", "hidden", "secondary")), expected)

    def test_unknown_mode_is_reported(self):
        with patch.dict(os.environ, {"LOG_WINDOW_MODE": "unknown"}):
            with self.assertRaisesRegex(ValueError, "LOG_WINDOW_MODE must be one of"):
                config._get_choice("LOG_WINDOW_MODE", "normal", ("normal", "hidden", "secondary"))


class OpenAIClientConfigTests(unittest.TestCase):
    def setUp(self):
        self.old_endpoint = config.LLM_API_ENDPOINT
        self.old_key = config.LLM_API_KEY
        self.old_timeout = config.LLM_TIMEOUT_SECONDS
        self.old_retries = config.LLM_MAX_RETRIES
        self.old_warned_invalid_tls_env_vars = set(config._WARNED_INVALID_TLS_ENV_VARS)

    def tearDown(self):
        config.LLM_API_ENDPOINT = self.old_endpoint
        config.LLM_API_KEY = self.old_key
        config.LLM_TIMEOUT_SECONDS = self.old_timeout
        config.LLM_MAX_RETRIES = self.old_retries
        config._WARNED_INVALID_TLS_ENV_VARS = self.old_warned_invalid_tls_env_vars

    def test_timeout_zero_disables_explicit_timeout_and_keeps_retry_count(self):
        config.LLM_API_ENDPOINT = "http://example.invalid/v1"
        config.LLM_API_KEY = "sk-test"
        config.LLM_TIMEOUT_SECONDS = 0
        config.LLM_MAX_RETRIES = 1

        kwargs = config.openai_client_kwargs()

        self.assertEqual(kwargs["api_key"], "sk-test")
        self.assertEqual(kwargs["base_url"], "http://example.invalid/v1")
        self.assertEqual(kwargs["max_retries"], 1)
        self.assertNotIn("timeout", kwargs)

    def test_positive_timeout_is_forwarded_to_openai_client(self):
        config.LLM_TIMEOUT_SECONDS = 12.5
        config.LLM_MAX_RETRIES = 2

        kwargs = config.openai_client_kwargs()

        self.assertEqual(kwargs["timeout"], 12.5)
        self.assertEqual(kwargs["max_retries"], 2)

    def test_invalid_tls_cert_env_vars_are_ignored_before_openai_client_init(self):
        with patch.dict("os.environ", {"SSL_CERT_FILE": "/path/that/does/not/exist.pem"}, clear=False):
            with redirect_stdout(StringIO()) as output:
                config.openai_client_kwargs()

            self.assertNotIn("SSL_CERT_FILE", os.environ)
            self.assertIn("ignored invalid SSL_CERT_FILE", output.getvalue())

    def test_existing_tls_cert_env_vars_are_preserved(self):
        with patch.dict("os.environ", {"SSL_CERT_FILE": __file__}, clear=False):
            config.openai_client_kwargs()

            self.assertEqual(os.environ["SSL_CERT_FILE"], __file__)


if __name__ == "__main__":
    unittest.main()
