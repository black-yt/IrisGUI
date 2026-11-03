import base64
from contextlib import ExitStack, redirect_stdout
from copy import deepcopy
from io import BytesIO, StringIO
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
try:
    import httpx2 as httpx
except ImportError:
    import httpx
from openai import OpenAI
from openai.types.chat import ChatCompletion

from scripts.agent import IrisAgent
from scripts.memory import HierarchicalMemory
from scripts.tools import VisionPerceptor


def image_parts(message):
    content = message.get("content", "")
    return [part for part in content if part.get("type") == "image_url"] if isinstance(content, list) else []


def image_count(messages):
    return sum(len(image_parts(message)) for message in messages)


def screenshot_pair(round_number=1):
    return (Image.new("RGB", (256, 256), (round_number, 0, 0)),
            Image.new("RGB", (64, 64), (0, round_number, 0)))


def tool_response(text="I will wait for the display to settle.", finish_reason="tool_calls"):
    return {"choices": [{"finish_reason": finish_reason, "message": {
        "content": text,
        "tool_calls": [{"id": "call_wait", "type": "function", "function": {
            "name": "wait", "arguments": json.dumps({"seconds": 0.1}),
        }}],
    }}]}


class ScreenshotMemoryTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for name, value in (("DEBUG_MODE", False), ("MEMORY_IMAGE_ROUNDS", -1),
                            ("MEMORY_IMAGE_TOKEN_MULTIPLIER", 1.2),
                            ("MEMORY_SHORT_TOKEN_BUDGET", 1000000),
                            ("MEMORY_LONG_TOKEN_BUDGET", 1000000)):
            self.stack.enter_context(patch("scripts.memory." + name, value))
        self.client = self.stack.enter_context(patch("scripts.memory.OpenAI")).return_value
        self.client.chat.completions.create.return_value = ChatCompletion.model_validate({
            "id": "summary", "object": "chat.completion", "created": 0, "model": "test-model",
            "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": "History Summary: the dialog opened.",
                "reasoning_content": "The old screenshot contains a dialog.",
            }}],
        })
        self.memory = HierarchicalMemory("system", "task")

    def add_round(self, number):
        context = self.memory.get_full_context(f"observation {number}", screenshot_pair(number), step=number)
        self.memory.add_interaction(f"action {number}", f"result {number}", debug_log=False)
        return context

    def test_all_rounds_stay_before_their_own_actions_with_both_views(self):
        contexts = [deepcopy(self.add_round(number)) for number in range(1, 8)]
        self.assertEqual([image_count(context) for context in contexts], [2, 4, 6, 8, 10, 12, 14])
        final = contexts[-1][2:]
        for index in range(6):
            observation, action, result = final[index * 3:index * 3 + 3]
            self.assertEqual(observation["content"][0]["text"], f"observation {index + 1}")
            self.assertEqual(len(image_parts(observation)), 2)
            self.assertEqual(action, {"role": "assistant", "content": f"action {index + 1}"})
            self.assertEqual(result, {"role": "user", "content": f"result {index + 1}"})
            encoded = image_parts(observation)[0]["image_url"]["url"].split(",", 1)[1]
            with Image.open(BytesIO(base64.b64decode(encoded))) as image:
                self.assertEqual(image.getpixel((0, 0)), (index + 1, 0, 0))
        self.assertEqual(final[-1]["content"][0]["text"], "observation 7")
        self.assertEqual(len(image_parts(final[-1])), 2)
        self.assertTrue(all(set(message) == {"role", "content"} for message in contexts[-1]))

    def test_finite_round_limits_include_current_and_keep_old_text(self):
        for limit in (1, 4):
            with self.subTest(limit=limit), patch("scripts.memory.MEMORY_IMAGE_ROUNDS", limit):
                self.memory = HierarchicalMemory("system", "task")
                for number in range(1, 8):
                    context = self.add_round(number)
                    self.assertEqual(image_count(context), min(number, limit) * 2)
                observations = [message for message in context[2:] if isinstance(message["content"], list)]
                self.assertEqual(len(observations), 7)
                self.assertEqual([m["content"][0]["text"] for m in observations if image_parts(m)],
                                 [f"observation {n}" for n in range(8 - limit, 8)])
                # Pruned pixels are released from runtime memory, not just hidden in the request.
                self.assertEqual(image_count(self.memory._messages_for_steps(self.memory.short_memory_layer)), limit * 2)

    def test_token_estimate_uses_pixels_not_base64_length(self):
        context = self.memory.get_full_context("query", (Image.new("RGB", (1024, 1024)), Image.new("RGB", (64, 64))))
        self.assertEqual(self.memory.estimate_tokens_for_content(context[-1]["content"]),
                         self.memory.estimate_tokens_for_text("query") + 1229 + 5)
        for part in image_parts(context[-1]):
            self.assertNotIn("tokens", part)

    def test_images_trigger_compression_before_request_and_are_seen_by_summary_model(self):
        self.add_round(1)
        self.add_round(2)
        with patch("scripts.memory.MEMORY_SHORT_TOKEN_BUDGET", 100), \
                patch("scripts.memory.MEMORY_RECENT_INTERACTIONS_TO_KEEP", 1):
            context = self.memory.get_full_context("observation 3", screenshot_pair(3), log_callback=lambda _: None)
        self.client.chat.completions.create.assert_called_once()
        summary_messages = self.client.chat.completions.create.call_args.kwargs["messages"]
        self.assertEqual(image_count(summary_messages), 2)
        self.assertEqual(summary_messages[1]["content"][0]["text"], "observation 1")
        self.assertEqual(summary_messages[2]["content"], "action 1")
        self.assertEqual(summary_messages[3]["content"], "result 1")
        self.assertEqual(image_count(context), 4)
        self.assertIn("History Summary", context[2]["content"])
        self.assertEqual(context[-1]["content"][0]["text"], "observation 3")
        self.assertEqual(self.memory.short_memory_layer[0]["content"], "action 2")

    def test_compression_failure_restores_original_images_and_actions(self):
        self.add_round(1)
        self.add_round(2)
        for failure in (TimeoutError("summary timeout"), None):
            with self.subTest(failure=failure), patch("scripts.memory.MEMORY_SHORT_TOKEN_BUDGET", 100), \
                    patch("scripts.memory.MEMORY_RECENT_INTERACTIONS_TO_KEEP", 1):
                self.client.chat.completions.create.side_effect = failure
                self.client.chat.completions.create.return_value = SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content=""))])
                context = self.memory.get_full_context("observation 3", screenshot_pair(3), log_callback=lambda _: None)
                self.assertEqual(image_count(context), 6)
                self.assertEqual(self.memory.short_memory_layer[0]["content"], "action 1")
                self.assertEqual(self.memory.long_memory_layer, [])

    def test_current_images_and_fixed_prompt_also_count_toward_budget(self):
        self.add_round(1)
        self.add_round(2)
        prior_tokens = self.memory.estimate_tokens_for_steps(
            self.memory.fixed_layer + self.memory.short_memory_layer)
        with patch("scripts.memory.MEMORY_SHORT_TOKEN_BUDGET", prior_tokens + 1), \
                patch("scripts.memory.MEMORY_RECENT_INTERACTIONS_TO_KEEP", 1):
            self.memory.get_full_context("current", screenshot_pair(3), log_callback=lambda _: None)
        self.client.chat.completions.create.assert_called_once()

    def test_current_observation_is_kept_without_summarizing_empty_history(self):
        with patch("scripts.memory.MEMORY_SHORT_TOKEN_BUDGET", 1), \
                patch("scripts.memory.MEMORY_RECENT_INTERACTIONS_TO_KEEP", 0):
            context = self.memory.get_full_context("current", screenshot_pair())
        self.client.chat.completions.create.assert_not_called()
        self.assertEqual(image_count(context), 2)

    def test_summary_debug_output_is_saved(self):
        with tempfile.TemporaryDirectory() as directory, patch("scripts.memory.DEBUG_MODE", True):
            self.memory.debug_save_path = str(Path(directory) / "summary.jsonl")
            self.memory._current_step = 9
            self.memory.compress_memory([{"role": "assistant", "content": "old"}], "summarize")
            entry = json.loads(Path(self.memory.debug_save_path).read_text(encoding="utf-8"))
        self.assertEqual(entry["purpose"], "memory_compression")
        self.assertEqual(entry["step"], 9)
        self.assertIn("dialog opened", entry["content"])
        self.assertEqual(entry["response"]["choices"][0]["message"]["reasoning_content"],
                         "The old screenshot contains a dialog.")

    def test_sdk_wire_payload_preserves_historical_rounds_and_eight_image_limit(self):
        requests = []

        def handle(request):
            requests.append(json.loads(request.content))
            response = tool_response()
            response.update(id="test", object="chat.completion", created=0, model="test-model")
            response["choices"][0]["index"] = 0
            return httpx.Response(200, json=response)

        with patch("scripts.memory.MEMORY_IMAGE_ROUNDS", 4), OpenAI(
            api_key="test-only", base_url="http://mock.invalid/v1", max_retries=0,
            http_client=httpx.Client(transport=httpx.MockTransport(handle)),
        ) as client:
            agent = IrisAgent.__new__(IrisAgent)
            agent.memory = self.memory
            agent.client = client
            agent.step_count = 0
            agent.vision = SimpleNamespace(capture_state=lambda *_: (*screenshot_pair(), {}, "L-10-10", "G-01-01"))
            agent.executor = SimpleNamespace(get_mouse_position=lambda: (0, 0), execute=lambda *args, **kwargs: "wait executed")
            with redirect_stdout(StringIO()):
                for _ in range(5):
                    self.assertEqual(agent.step(), "wait executed")
        self.assertEqual([image_count(request["messages"]) for request in requests], [2, 4, 6, 8, 8])
        last_messages = requests[-1]["messages"]
        observations = [message for message in last_messages if isinstance(message["content"], list)]
        self.assertEqual(len(observations), 5)
        self.assertEqual([len(image_parts(message)) for message in observations], [0, 2, 2, 2, 2])
        self.assertIn("Observation for step 5", observations[-1]["content"][0]["text"])
        self.assertTrue(all(set(message) == {"role", "content"} for message in last_messages))


class DebugScreenshotIntegrationTests(unittest.TestCase):
    def test_agent_archives_every_pair_reply_tool_call_and_execution_including_failures(self):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            for target, value in (("scripts.memory.DEBUG_MODE", True), ("scripts.tools.DEBUG_MODE", True),
                                  ("scripts.memory.MEMORY_IMAGE_ROUNDS", 4),
                                  ("scripts.memory.MEMORY_SHORT_TOKEN_BUDGET", 1000000)):
                stack.enter_context(patch(target, value))
            stack.enter_context(patch("scripts.memory.OpenAI"))
            with patch("scripts.memory.os.path.dirname", return_value=directory):
                memory = HierarchicalMemory("system", "task")
            agent = IrisAgent.__new__(IrisAgent)
            agent.memory = memory
            agent.step_count = 0
            agent.vision = VisionPerceptor()
            agent.vision.debug_dir = str(Path(directory) / "screenshots")
            Path(agent.vision.debug_dir).mkdir()
            stack.enter_context(patch.object(agent.vision, "_capture_screenshot", return_value=Image.new("RGB", (640, 480))))
            agent.executor = SimpleNamespace(get_mouse_position=lambda: (100, 100),
                                             execute=lambda *args, **kwargs: "wait executed")
            replies = iter([
                {"choices": [{"finish_reason": "stop", "message": {"content": "Need a tool.", "tool_calls": []}}]},
                tool_response(), tool_response(), tool_response(finish_reason="length"),
                TimeoutError("action timeout"), tool_response(),
            ])
            requests = []

            def complete(messages):
                requests.append(deepcopy(messages))
                response = next(replies)
                if isinstance(response, Exception):
                    raise response
                return response

            agent._call_llm_for_action = complete
            with redirect_stdout(StringIO()):
                feedback = [agent.step() for _ in range(5)]
            self.assertIn("truncated", feedback[2])
            self.assertIn("action timeout", feedback[3])
            self.assertEqual([image_count(request) for request in requests], [2, 2, 4, 6, 8, 8])
            self.assertIn("action timeout", str(requests[-1]))
            self.assertEqual(len(list(Path(agent.vision.debug_dir).glob("*.png"))), 15)
            entries = [json.loads(line) for line in Path(memory.debug_save_path).read_text(encoding="utf-8").splitlines()]
            outputs = [entry for entry in entries if entry.get("direction") == "output"]
            executions = [entry for entry in entries if entry.get("direction") == "execution"]
            self.assertEqual(len(outputs), 5)
            self.assertEqual(len(executions), 5)
            self.assertEqual(sum(bool(entry.get("tool")) for entry in outputs), 4)
            self.assertEqual(outputs[3]["response"]["choices"][0]["finish_reason"], "length")
            self.assertEqual(outputs[1]["response"]["choices"][0]["message"]["tool_calls"][0]["id"], "call_wait")
            self.assertIn("action timeout", executions[3]["content"])
            capture_inputs = [entry for entry in entries if entry.get("direction") == "input" and entry.get("images")]
            self.assertEqual([entry["step"] for entry in capture_inputs], [1, 2, 3, 4, 5])
            for entry, request in zip(capture_inputs, (requests[0], *requests[2:])):
                raw_name = entry["images"]["screenshot"]
                self.assertRegex(raw_name, r"^screenshot_\d{8}_\d{6}_\d{6}\.png$")
                timestamp = raw_name.removeprefix("screenshot_")
                self.assertEqual(entry["images"]["global"], "global_" + timestamp)
                self.assertEqual(entry["images"]["local"], "local_" + timestamp)
                with Image.open(Path(agent.vision.debug_dir) / raw_name) as raw:
                    self.assertEqual(raw.size, (640, 480))
                    self.assertEqual(raw.mode, "RGB")
                    self.assertEqual(raw.tobytes(), Image.new("RGB", (640, 480)).tobytes())
                for view, part in zip(("global", "local"), image_parts(request[-1])):
                    archived = (Path(agent.vision.debug_dir) / entry["images"][view]).read_bytes()
                    uploaded = base64.b64decode(part["image_url"]["url"].split(",", 1)[1])
                    self.assertEqual(archived, uploaded)


if __name__ == "__main__":
    unittest.main()
