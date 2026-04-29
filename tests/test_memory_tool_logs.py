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

    def test_model_input_log_records_actual_prompt_text_and_images(self):
        old_debug_mode = memory_module.DEBUG_MODE
        memory = HierarchicalMemory("system prompt", "initial task")
        images = {"global": "global_20260429_120000.png", "local": "local_20260429_120000.png"}
        handle = tempfile.NamedTemporaryFile(delete=False)
        handle.close()
        memory.debug_save_path = handle.name

        try:
            memory_module.DEBUG_MODE = True
            memory.add_model_input_log(
                memory.fixed_layer
                + [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "actual model prompt"},
                            {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc", "detail": "high"}},
                        ],
                    },
                ],
                step=4,
                images=images,
            )

            with open(handle.name, "r", encoding="utf-8") as log_file:
                entries = [json.loads(line) for line in log_file]

            self.assertEqual([entry["direction"] for entry in entries], ["input", "input", "input"])
            self.assertEqual(
                [(entry["step"], entry["role"], entry["content"]) for entry in entries],
                [
                    (0, "system", "system prompt"),
                    (0, "user", "initial task"),
                    (4, "user", "actual model prompt"),
                ],
            )
            self.assertEqual(entries[2]["images"], images)
            self.assertNotIn("data:image", entries[2]["content"])
        finally:
            memory_module.DEBUG_MODE = old_debug_mode
            os.unlink(handle.name)

    def test_model_input_log_does_not_repeat_fixed_prompt_prefix(self):
        old_debug_mode = memory_module.DEBUG_MODE
        memory = HierarchicalMemory("system prompt", "initial task")
        handle = tempfile.NamedTemporaryFile(delete=False)
        handle.close()
        memory.debug_save_path = handle.name

        first_messages = memory.fixed_layer + [{"role": "user", "content": "first step prompt"}]
        second_messages = memory.fixed_layer + [{"role": "user", "content": "second step prompt"}]

        try:
            memory_module.DEBUG_MODE = True
            memory.add_model_input_log(first_messages, step=1)
            memory.add_model_input_log(second_messages, step=2)

            with open(handle.name, "r", encoding="utf-8") as log_file:
                entries = [json.loads(line) for line in log_file]

            self.assertEqual(
                [(entry["step"], entry["role"], entry["content"]) for entry in entries],
                [
                    (0, "system", "system prompt"),
                    (0, "user", "initial task"),
                    (1, "user", "first step prompt"),
                    (2, "user", "second step prompt"),
                ],
            )
        finally:
            memory_module.DEBUG_MODE = old_debug_mode
            os.unlink(handle.name)

    def test_model_input_log_records_only_current_prompt_not_history_messages(self):
        old_debug_mode = memory_module.DEBUG_MODE
        memory = HierarchicalMemory("system prompt", "initial task")
        handle = tempfile.NamedTemporaryFile(delete=False)
        handle.close()
        memory.debug_save_path = handle.name

        messages = memory.fixed_layer + [
            {"role": "assistant", "content": "Tool call: move\nArguments: {\"point_id\": \"G-01-02\"}"},
            {"role": "user", "content": "Execution Result: Action move to G-01-02 executed."},
            {"role": "user", "content": "current visual prompt"},
        ]

        try:
            memory_module.DEBUG_MODE = True
            memory.add_model_input_log(messages, step=3)

            with open(handle.name, "r", encoding="utf-8") as log_file:
                entries = [json.loads(line) for line in log_file]

            self.assertEqual(
                [(entry["step"], entry["role"], entry["content"]) for entry in entries],
                [
                    (0, "system", "system prompt"),
                    (0, "user", "initial task"),
                    (3, "user", "current visual prompt"),
                ],
            )
            logged_content = "\n".join(entry["content"] for entry in entries)
            self.assertNotIn("Tool call: move", logged_content)
            self.assertNotIn("Execution Result", logged_content)
        finally:
            memory_module.DEBUG_MODE = old_debug_mode
            os.unlink(handle.name)

    def test_model_output_log_records_assistant_content_and_tool_calls(self):
        old_debug_mode = memory_module.DEBUG_MODE
        memory = HierarchicalMemory("system prompt", "initial task")
        tool = [{"name": "hotkey", "arguments": {"keys": ["ctrl", "l"]}}]
        handle = tempfile.NamedTemporaryFile(delete=False)
        handle.close()
        memory.debug_save_path = handle.name

        try:
            memory_module.DEBUG_MODE = True
            memory.add_model_output_log("I will focus the browser.", tool=tool, step=5)

            with open(handle.name, "r", encoding="utf-8") as log_file:
                entry = json.loads(log_file.readline())

            self.assertEqual(entry["direction"], "output")
            self.assertEqual(entry["role"], "assistant")
            self.assertEqual(entry["content"], "I will focus the browser.")
            self.assertEqual(entry["tool"], tool)
        finally:
            memory_module.DEBUG_MODE = old_debug_mode
            os.unlink(handle.name)

    def test_add_interaction_can_skip_debug_log_for_runtime_memory_only(self):
        old_debug_mode = memory_module.DEBUG_MODE
        memory = HierarchicalMemory("system prompt", "initial task")
        handle = tempfile.NamedTemporaryFile(delete=False)
        handle.close()
        memory.debug_save_path = handle.name

        try:
            memory_module.DEBUG_MODE = True
            memory.add_interaction("assistant memory", "Execution Result: clicked", debug_log=False)

            with open(handle.name, "r", encoding="utf-8") as log_file:
                entries = [json.loads(line) for line in log_file]

            self.assertEqual(entries, [])
            self.assertEqual([step["content"] for step in memory.short_memory_layer], ["assistant memory", "Execution Result: clicked"])
        finally:
            memory_module.DEBUG_MODE = old_debug_mode
            os.unlink(handle.name)

    def test_debug_log_initialization_does_not_write_non_call_entries(self):
        old_debug_mode = memory_module.DEBUG_MODE
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                memory_module.DEBUG_MODE = True
                with patch("scripts.memory.os.path.dirname", return_value=temp_dir):
                    memory = HierarchicalMemory("system prompt", "initial task")

                self.assertFalse(os.path.exists(memory.debug_save_path))
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
