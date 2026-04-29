import os
import unittest

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
os.environ.setdefault("MEMORY_SHORT_TOKEN_BUDGET", "6000")
os.environ.setdefault("MEMORY_LONG_TOKEN_BUDGET", "12000")
os.environ.setdefault("MEMORY_RECENT_INTERACTIONS_TO_KEEP", "3")
os.environ.setdefault("MEMORY_CHARS_PER_TOKEN", "4")

import scripts.memory as memory_module
from scripts.memory import HierarchicalMemory


class MemoryCompressionTests(unittest.TestCase):
    def setUp(self):
        self.old_short_budget = memory_module.MEMORY_SHORT_TOKEN_BUDGET
        self.old_long_budget = memory_module.MEMORY_LONG_TOKEN_BUDGET
        self.old_recent_keep = memory_module.MEMORY_RECENT_INTERACTIONS_TO_KEEP
        self.old_chars_per_token = memory_module.MEMORY_CHARS_PER_TOKEN

    def tearDown(self):
        memory_module.MEMORY_SHORT_TOKEN_BUDGET = self.old_short_budget
        memory_module.MEMORY_LONG_TOKEN_BUDGET = self.old_long_budget
        memory_module.MEMORY_RECENT_INTERACTIONS_TO_KEEP = self.old_recent_keep
        memory_module.MEMORY_CHARS_PER_TOKEN = self.old_chars_per_token

    def test_short_memory_under_token_budget_does_not_compress(self):
        memory_module.MEMORY_SHORT_TOKEN_BUDGET = 1000
        memory = StubMemory()

        memory.add_interaction("short assistant", "short user")

        self.assertEqual(memory.compress_calls, [])
        self.assertEqual(len(memory.short_memory_layer), 2)
        self.assertEqual(memory.long_memory_layer, [])

    def test_token_estimate_counts_non_ascii_text_conservatively(self):
        memory_module.MEMORY_CHARS_PER_TOKEN = 4
        memory = StubMemory()

        self.assertEqual(memory.estimate_tokens_for_text("abcdefgh"), 2)
        self.assertEqual(memory.estimate_tokens_for_text("中文测试"), 4)
        self.assertEqual(memory.estimate_tokens_for_text("abcd中文"), 3)

    def test_short_memory_over_budget_compresses_old_interactions_and_keeps_recent_pairs(self):
        memory_module.MEMORY_SHORT_TOKEN_BUDGET = 8
        memory_module.MEMORY_RECENT_INTERACTIONS_TO_KEEP = 1
        memory = StubMemory()

        memory.add_interaction("assistant old " * 4, "user old " * 4, log_callback=lambda _: None)
        memory.add_interaction("assistant recent " * 4, "user recent " * 4, log_callback=lambda _: None)

        self.assertEqual(len(memory.compress_calls), 1)
        self.assertEqual([step["role"] for step in memory.compress_calls[0]], ["assistant", "user"])
        self.assertIn("assistant old", memory.compress_calls[0][0]["content"])
        self.assertEqual(len(memory.short_memory_layer), 2)
        self.assertIn("assistant recent", memory.short_memory_layer[0]["content"])
        self.assertEqual(memory.long_memory_layer, [{"role": "assistant", "content": "History Summary: compressed 1"}])

    def test_long_memory_over_budget_consolidates_summaries(self):
        memory_module.MEMORY_SHORT_TOKEN_BUDGET = 8
        memory_module.MEMORY_LONG_TOKEN_BUDGET = 8
        memory_module.MEMORY_RECENT_INTERACTIONS_TO_KEEP = 0
        memory = StubMemory()

        memory.long_memory_layer = [{"role": "assistant", "content": "old long summary " * 8}]
        memory.add_interaction("assistant current " * 4, "user current " * 4, log_callback=lambda _: None)

        self.assertEqual(len(memory.compress_calls), 2)
        self.assertEqual(memory.long_memory_layer, [{"role": "assistant", "content": "Long Term Memory: compressed 2"}])

    def test_add_interaction_writes_complete_pair_before_compression(self):
        memory_module.MEMORY_SHORT_TOKEN_BUDGET = 8
        memory_module.MEMORY_RECENT_INTERACTIONS_TO_KEEP = 0
        memory = StubMemory()

        memory.add_interaction("assistant content " * 4, "user result " * 4, log_callback=lambda _: None)

        self.assertEqual(len(memory.compress_calls), 1)
        self.assertEqual([step["role"] for step in memory.compress_calls[0]], ["assistant", "user"])


class StubMemory(HierarchicalMemory):
    def __init__(self):
        super().__init__("system prompt", "initial task")
        self.compress_calls = []

    def compress_memory(self, memory_list, instructions, max_tokens=None):
        self.compress_calls.append(list(memory_list))
        if "Consolidate" in instructions:
            return f"Long Term Memory: compressed {len(self.compress_calls)}"
        return f"History Summary: compressed {len(self.compress_calls)}"


if __name__ == "__main__":
    unittest.main()
