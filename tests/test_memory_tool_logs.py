import json
import os
import tempfile
import unittest
from unittest.mock import patch

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
os.environ.setdefault("MEMORY_SHORT_TOKEN_BUDGET", "128000")
os.environ.setdefault("MEMORY_LONG_TOKEN_BUDGET", "128000")
os.environ.setdefault("MEMORY_RECENT_INTERACTIONS_TO_KEEP", "3")
os.environ.setdefault("MEMORY_CHARS_PER_TOKEN", "4")

import scripts.memory as memory_module
from scripts.memory import HierarchicalMemory


class MemoryToolLogTests(unittest.TestCase):
    def test_add_step_keeps_tool_field_out_of_runtime_memory(self):
        memory = HierarchicalMemory("system prompt", "initial task")
        tool = [{"name": "type", "arguments": {"text": "hello"}}]
        runtime_content = 'The input is focused.\nTool call: type\nArguments: {"text": "hello"}'

        memory.add_step("assistant", runtime_content, tool=tool, log_content="The input is focused.")

        self.assertEqual(memory.short_memory_layer[0]["content"], runtime_content)
        self.assertNotIn("tool", memory.short_memory_layer[0])

    def test_context_messages_do_not_include_custom_tool_field(self):
        memory = HierarchicalMemory("system prompt", "initial task")
        tool = [{"name": "move", "arguments": {"point_id": "G-01-02"}}]
        runtime_content = 'I will move there.\nTool call: move\nArguments: {"point_id": "G-01-02"}'
        memory.add_step("assistant", runtime_content, tool=tool, log_content="I will move there.")

        context = memory.get_full_context("next")
        assistant_message = next(message for message in context if message["role"] == "assistant")

        self.assertNotIn("tool", assistant_message)
        self.assertIn("I will move there.", assistant_message["content"])
        self.assertIn("Tool call: move", assistant_message["content"])
        self.assertIn('"point_id": "G-01-02"', assistant_message["content"])

    def test_debug_log_writes_tool_field_without_mixing_it_into_content(self):
        old_debug_mode = memory_module.DEBUG_MODE
        memory = HierarchicalMemory("system prompt", "initial task")
        tool = [{"name": "click", "arguments": {"button": "left"}}]
        handle = tempfile.NamedTemporaryFile(delete=False)
        handle.close()
        memory.debug_save_path = handle.name

        try:
            memory_module.DEBUG_MODE = True
            memory.add_step(
                "assistant",
                'The button is aligned.\nTool call: click\nArguments: {"button": "left"}',
                tool=tool,
                log_content="The button is aligned.",
            )

            with open(handle.name, "r", encoding="utf-8") as log_file:
                entry = json.loads(log_file.readline())

            self.assertEqual(list(entry.keys())[:2], ["step", "timestamp"])
            self.assertEqual(entry["step"], 0)
            self.assertEqual(entry["content"], "The button is aligned.")
            self.assertEqual(entry["tool"], tool)
            self.assertNotIn("Tool call", entry["content"])
            self.assertNotIn("schema_version", entry)
            self.assertIn("timestamp", entry)
        finally:
            memory_module.DEBUG_MODE = old_debug_mode
            os.unlink(handle.name)

    def test_debug_log_can_record_feedback_image_names(self):
        old_debug_mode = memory_module.DEBUG_MODE
        memory = HierarchicalMemory("system prompt", "initial task")
        images = {"global": "global_20260429_120000.png", "local": "local_20260429_120000.png"}
        handle = tempfile.NamedTemporaryFile(delete=False)
        handle.close()
        memory.debug_save_path = handle.name

        try:
            memory_module.DEBUG_MODE = True
            memory.add_step("user", "Execution Result: clicked", log_extra={"images": images})

            with open(handle.name, "r", encoding="utf-8") as log_file:
                entry = json.loads(log_file.readline())

            self.assertEqual(list(entry.keys())[:2], ["step", "timestamp"])
            self.assertEqual(entry["step"], 0)
            self.assertEqual(entry["role"], "user")
            self.assertEqual(entry["images"], images)
        finally:
            memory_module.DEBUG_MODE = old_debug_mode
            os.unlink(handle.name)

    def test_debug_log_initial_fixed_layer_uses_step_zero(self):
        old_debug_mode = memory_module.DEBUG_MODE
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                memory_module.DEBUG_MODE = True
                with patch("scripts.memory.os.path.dirname", return_value=temp_dir):
                    memory = HierarchicalMemory("system prompt", "initial task")

                with open(memory.debug_save_path, "r", encoding="utf-8") as log_file:
                    entries = [json.loads(line) for line in log_file]

                self.assertEqual([entry["step"] for entry in entries], [0, 0])
                self.assertEqual([entry["role"] for entry in entries], ["system", "user"])
                self.assertTrue(all(list(entry.keys())[:2] == ["step", "timestamp"] for entry in entries))
                self.assertTrue(all("schema_version" not in entry for entry in entries))
            finally:
                memory_module.DEBUG_MODE = old_debug_mode

    def test_debug_log_interaction_pair_uses_same_step(self):
        old_debug_mode = memory_module.DEBUG_MODE
        memory = HierarchicalMemory("system prompt", "initial task")
        handle = tempfile.NamedTemporaryFile(delete=False)
        handle.close()
        memory.debug_save_path = handle.name

        try:
            memory_module.DEBUG_MODE = True
            memory.add_interaction(
                "assistant content",
                "Execution Result: clicked",
                assistant_log_extra={"step": 3, "timestamp": "caller timestamp should not override"},
                user_log_extra={"step": 3, "images": {"global": "global.png", "local": "local.png"}},
            )

            with open(handle.name, "r", encoding="utf-8") as log_file:
                entries = [json.loads(line) for line in log_file]

            self.assertEqual([entry["step"] for entry in entries], [3, 3])
            self.assertEqual([entry["role"] for entry in entries], ["assistant", "user"])
            self.assertTrue(all(list(entry.keys())[:2] == ["step", "timestamp"] for entry in entries))
            self.assertTrue(all("schema_version" not in entry for entry in entries))
            self.assertNotEqual(entries[0]["timestamp"], "caller timestamp should not override")
        finally:
            memory_module.DEBUG_MODE = old_debug_mode
            os.unlink(handle.name)


if __name__ == "__main__":
    unittest.main()
