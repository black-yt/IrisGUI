import os
import unittest
from types import SimpleNamespace

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

from scripts.agent import IRIS_SYSTEM_PROMPT, build_step_query
from scripts.memory import HierarchicalMemory, build_memory_summary_user_prompt


class PromptTests(unittest.TestCase):
    def test_agent_system_prompt_covers_core_runtime_contracts(self):
        self.assertIn("You never receive raw absolute screen coordinates", IRIS_SYSTEM_PROMPT)
        self.assertIn("Current local mouse grid", IRIS_SYSTEM_PROMPT)
        self.assertIn("Nearby global grid", IRIS_SYSTEM_PROMPT)
        self.assertIn("newest screenshot after the previous action", IRIS_SYSTEM_PROMPT)
        self.assertIn("Do not output JSON action blocks", IRIS_SYSTEM_PROMPT)
        self.assertIn("Usually do not emit `move` followed immediately by `click`", IRIS_SYSTEM_PROMPT)
        self.assertIn("Keyboard actions affect only the currently focused application or control", IRIS_SYSTEM_PROMPT)
        self.assertIn("For browser shortcuts such as `ctrl+l`, make sure the browser window is focused first", IRIS_SYSTEM_PROMPT)

    def test_step_query_marks_mouse_grid_as_latest_local_id(self):
        query = build_step_query("L-10-10", "G-08-06")

        self.assertIn("Global View image", query)
        self.assertIn("Local View image", query)
        self.assertIn("cursor-anchored crop clipped at screen edges", query)
        self.assertIn("Nearby global mouse grid: `G-08-06`", query)
        self.assertIn("Current local mouse grid: `L-10-10`", query)
        self.assertLess(
            query.index("Nearby global mouse grid: `G-08-06`"),
            query.index("Current local mouse grid: `L-10-10`"),
        )
        self.assertLess(
            query.index("not necessarily on this Global View point"),
            query.index("cursor is precisely on this Local View point"),
        )
        self.assertIn("updated Local View grid point", query)
        self.assertIn("cursor is precisely on this Local View point", query)
        self.assertIn("not an old grid point from history", query)
        self.assertIn("nearest Global View grid point near the current mouse position", query)
        self.assertIn("not necessarily on this Global View point", query)

    def test_memory_summary_user_prompt_includes_instructions_and_history(self):
        prompt = build_memory_summary_user_prompt(
            "SPECIAL COMPRESSION INSTRUCTIONS",
            [
                {"role": "assistant", "content": "Tool call: move\nArguments: {\"point_id\": \"G-01-02\"}"},
                {"role": "user", "content": "Execution Result: moved"},
            ],
        )

        self.assertIn("SPECIAL COMPRESSION INSTRUCTIONS", prompt)
        self.assertIn("## History To Compress", prompt)
        self.assertIn("### Entry 1 (assistant)", prompt)
        self.assertIn('"point_id": "G-01-02"', prompt)
        self.assertIn("### Entry 2 (user)", prompt)

    def test_compress_memory_sends_system_and_user_prompts(self):
        memory = HierarchicalMemory("system", "Open the browser and search.")
        fake_completions = CapturingCompletions()
        memory.client = SimpleNamespace(chat=SimpleNamespace(completions=fake_completions))

        summary = memory.compress_memory(
            [{"role": "assistant", "content": "Clicked search box."}],
            "KEEP ACTIONS AND RESULTS",
        )

        self.assertEqual(summary, "History Summary: compressed")
        messages = fake_completions.kwargs["messages"]
        self.assertIn("Open the browser and search.", messages[0]["content"])
        self.assertIn("KEEP ACTIONS AND RESULTS", messages[1]["content"])
        self.assertIn("Clicked search box.", messages[1]["content"])


class CapturingCompletions:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        message = SimpleNamespace(content="History Summary: compressed")
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


if __name__ == "__main__":
    unittest.main()
