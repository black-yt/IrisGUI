import json
import os
import unittest
from contextlib import redirect_stdout
from io import StringIO

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

from scripts.agent import IrisAgent


class FakeMemory:
    def __init__(self):
        self.context_requests = []
        self.steps = []
        self.model_inputs = []
        self.model_outputs = []

    def get_full_context(self, query, images=None):
        self.context_requests.append((query, images))
        return [{"role": "user", "content": "current state"}]

    def add_model_input_log(self, messages, step, images=None):
        self.model_inputs.append({"messages": messages, "step": step, "images": images})

    def add_model_output_log(self, content, tool=None, step=0):
        self.model_outputs.append({"content": content, "tool": tool, "step": step})

    def add_step(self, role, content, tool=None, log_content=None, log_extra=None, log_callback=None, compress=True):
        step = {"role": role, "content": content, "log_content": log_content, "log_extra": log_extra}
        if tool:
            step["tool"] = tool
        self.steps.append(step)

    def add_interaction(
        self,
        assistant_content,
        user_content,
        tool=None,
        assistant_log_content=None,
        assistant_log_extra=None,
        user_log_extra=None,
        log_callback=None,
        debug_log=True,
    ):
        self.add_step("assistant", assistant_content, tool=tool, log_content=assistant_log_content, log_extra=assistant_log_extra)
        self.add_step("user", user_content, log_extra=user_log_extra)


class FakeVision:
    def __init__(self):
        self.last_capture_files = {"global": "global_step.png", "local": "local_step.png"}

    def capture_state(self, mouse_x, mouse_y):
        return object(), object(), {"G-00-00": (0, 0)}, "L-00-00", "G-00-00"


class FakeExecutor:
    def __init__(self):
        self.executed = []

    def get_mouse_position(self):
        return 0, 0

    def execute(self, action_dict, coordinate_map=None):
        self.executed.append((action_dict, coordinate_map))
        return f"executed {action_dict['action_type']}"


class CapturingCompletions:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return {"choices": [{"finish_reason": "stop", "message": {"tool_calls": []}}]}


class CapturingClient:
    def __init__(self):
        self.completions = CapturingCompletions()
        self.chat = type("Chat", (), {"completions": self.completions})()


def make_agent(fake_response):
    agent = IrisAgent.__new__(IrisAgent)
    agent.step_count = 0
    agent.memory = FakeMemory()
    agent.vision = FakeVision()
    agent.executor = FakeExecutor()
    agent._call_llm_for_action = lambda messages: fake_response
    return agent


class AgentNativeToolLoopTests(unittest.TestCase):
    def test_step_executes_native_tool_call(self):
        response = {
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "content": "I will move to the requested grid point.",
                        "tool_calls": [
                            {
                                "id": "call_move",
                                "type": "function",
                                "function": {
                                    "name": "move",
                                    "arguments": json.dumps({"point_id": "G-00-00"}),
                                },
                            }
                        ],
                    },
                }
            ]
        }
        agent = make_agent(response)

        with redirect_stdout(StringIO()):
            feedback = agent.step()

        self.assertEqual(feedback, "executed move")
        query, images = agent.memory.context_requests[0]
        self.assertIn("Nearby global mouse grid: `G-00-00`", query)
        self.assertIn("Current local mouse grid: `L-00-00`", query)
        self.assertIsNotNone(images)
        self.assertEqual(agent.executor.executed[0][0], {"action_type": "move", "point_id": "G-00-00"})
        self.assertEqual(agent.executor.executed[0][1], {"G-00-00": (0, 0)})
        self.assertEqual(agent.memory.model_inputs[0]["messages"], [{"role": "user", "content": "current state"}])
        self.assertEqual(agent.memory.model_inputs[0]["step"], 1)
        self.assertEqual(agent.memory.model_inputs[0]["images"], {"global": "global_step.png", "local": "local_step.png"})
        self.assertEqual(agent.memory.model_outputs[0]["content"], "I will move to the requested grid point.")
        self.assertEqual(agent.memory.model_outputs[0]["tool"], [{"name": "move", "arguments": {"point_id": "G-00-00"}}])
        assistant_memory = agent.memory.steps[0]
        self.assertIn("I will move to the requested grid point.", assistant_memory["content"])
        self.assertIn("Tool call: move", assistant_memory["content"])
        self.assertEqual(assistant_memory["log_content"], "I will move to the requested grid point.")
        self.assertEqual(
            assistant_memory["tool"],
            [{"name": "move", "arguments": {"point_id": "G-00-00"}}],
        )
        self.assertEqual(assistant_memory["log_extra"], {"step": 1})
        self.assertEqual(
            agent.memory.steps[1]["log_extra"],
            {"step": 1, "images": {"global": "global_step.png", "local": "local_step.png"}},
        )

    def test_step_emits_only_final_loop_box(self):
        response = {
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "content": "I will wait briefly.",
                        "tool_calls": [
                            {
                                "id": "call_wait",
                                "type": "function",
                                "function": {
                                    "name": "wait",
                                    "arguments": json.dumps({"seconds": 0.1}),
                                },
                            }
                        ],
                    },
                }
            ]
        }
        agent = make_agent(response)
        logs = []

        with redirect_stdout(StringIO()):
            agent.step(log_callback=logs.append)

        joined_logs = "\n".join(logs)
        self.assertNotIn("Step 1 started.", joined_logs)
        self.assertNotIn("Capturing screen", joined_logs)
        self.assertNotIn("Preparing model context", joined_logs)
        self.assertNotIn("Waiting for fake-model response", joined_logs)
        self.assertNotIn("Executing wait", joined_logs)
        self.assertIn("Iris Agent Loop", joined_logs)

    def test_step_executes_multiple_native_tool_calls_in_order(self):
        response = {
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "content": "The input is already verified, so I will click and type.",
                        "tool_calls": [
                            {
                                "id": "call_click",
                                "type": "function",
                                "function": {
                                    "name": "click",
                                    "arguments": json.dumps({"button": "left"}),
                                },
                            },
                            {
                                "id": "call_type",
                                "type": "function",
                                "function": {
                                    "name": "type",
                                    "arguments": json.dumps({"text": "hello", "submit": True}),
                                },
                            },
                        ],
                    },
                }
            ]
        }
        agent = make_agent(response)

        with redirect_stdout(StringIO()):
            feedback = agent.step()

        self.assertEqual(
            [action for action, _ in agent.executor.executed],
            [
                {"action_type": "click", "button": "left"},
                {"action_type": "type", "text": "hello", "submit": True},
            ],
        )
        self.assertIn("executed click", feedback)
        self.assertIn("executed type", feedback)
        assistant_memory = agent.memory.steps[0]
        self.assertIn("The input is already verified, so I will click and type.", assistant_memory["content"])
        self.assertIn("Tool call: click", assistant_memory["content"])
        self.assertIn("Tool call: type", assistant_memory["content"])
        self.assertEqual(assistant_memory["log_content"], "The input is already verified, so I will click and type.")
        self.assertEqual(
            assistant_memory["tool"],
            [
                {"name": "click", "arguments": {"button": "left"}},
                {"name": "type", "arguments": {"text": "hello", "submit": True}},
            ],
        )

    def test_step_rejects_plain_text_without_tool_call(self):
        response = {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": "I would click now.",
                        "tool_calls": [],
                    },
                }
            ]
        }
        agent = make_agent(response)

        with redirect_stdout(StringIO()):
            feedback = agent.step()

        self.assertIn("no native tool call", feedback)
        self.assertEqual(agent.executor.executed, [])
        self.assertIn("Execution Result", agent.memory.steps[1]["content"])

    def test_llm_request_messages_are_passed_without_character_rewrites(self):
        agent = IrisAgent.__new__(IrisAgent)
        agent.client = CapturingClient()

        agent._call_llm_for_action([{"role": "user", "content": "bad \ud83d"}])

        sent_messages = agent.client.completions.kwargs["messages"]
        self.assertEqual(sent_messages, [{"role": "user", "content": "bad \ud83d"}])


if __name__ == "__main__":
    unittest.main()
