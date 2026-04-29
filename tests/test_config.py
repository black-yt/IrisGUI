import unittest

import scripts.config as config


class OpenAIClientConfigTests(unittest.TestCase):
    def setUp(self):
        self.old_endpoint = config.LLM_API_ENDPOINT
        self.old_key = config.LLM_API_KEY
        self.old_timeout = config.LLM_TIMEOUT_SECONDS
        self.old_retries = config.LLM_MAX_RETRIES

    def tearDown(self):
        config.LLM_API_ENDPOINT = self.old_endpoint
        config.LLM_API_KEY = self.old_key
        config.LLM_TIMEOUT_SECONDS = self.old_timeout
        config.LLM_MAX_RETRIES = self.old_retries

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


if __name__ == "__main__":
    unittest.main()
