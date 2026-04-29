import os
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

import scripts.config as config


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
