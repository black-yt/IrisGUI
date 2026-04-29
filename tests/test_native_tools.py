import json
import unittest
from types import SimpleNamespace

from scripts.native_tools import (
    GUI_ACTION_TOOLS,
    GUI_TOOL_SCHEMAS,
    ToolCallProtocolError,
    assistant_text_content,
    compact_tool_call_for_log,
    parse_tool_arguments,
    tool_calls_to_actions,
    tool_call_to_action,
)


class NativeToolSchemaTests(unittest.TestCase):
    def test_every_gui_action_has_native_function_schema(self):
        expected_names = {tool.name for tool in GUI_ACTION_TOOLS}
        schema_names = {schema["function"]["name"] for schema in GUI_TOOL_SCHEMAS}

        self.assertEqual(schema_names, expected_names)
        for schema in GUI_TOOL_SCHEMAS:
            self.assertEqual(schema["type"], "function")
            self.assertIn("description", schema["function"])
            self.assertEqual(schema["function"]["parameters"]["type"], "object")

    def test_move_schema_requires_grid_point_id(self):
        move_schema = next(schema for schema in GUI_TOOL_SCHEMAS if schema["function"]["name"] == "move")

        self.assertEqual(move_schema["function"]["parameters"]["required"], ["point_id"])
        self.assertIn("point_id", move_schema["function"]["parameters"]["properties"])


class NativeToolArgumentTests(unittest.TestCase):
    def test_parse_tool_arguments_accepts_object_json(self):
        parsed = parse_tool_arguments(json.dumps({"point_id": "G-01-02", "duration": 0.2}))

        self.assertEqual(parsed, {"point_id": "G-01-02", "duration": 0.2})

    def test_parse_tool_arguments_unwraps_double_encoded_json(self):
        raw_arguments = json.dumps(json.dumps({"text": "done"}))

        self.assertEqual(parse_tool_arguments(raw_arguments), {"text": "done"})

    def test_parse_tool_arguments_rejects_non_object_json(self):
        with self.assertRaises(ToolCallProtocolError):
            parse_tool_arguments(json.dumps(["not", "an", "object"]))

    def test_parse_tool_arguments_rejects_invalid_json(self):
        with self.assertRaises(ToolCallProtocolError):
            parse_tool_arguments("{invalid")


class NativeToolCallConversionTests(unittest.TestCase):
    def test_dict_tool_call_converts_to_executor_action(self):
        tool_call = {
            "id": "call_move",
            "type": "function",
            "function": {
                "name": "move",
                "arguments": json.dumps({"point_id": "L-02-04"}),
            },
        }

        action, normalized = tool_call_to_action(tool_call)

        self.assertEqual(action, {"action_type": "move", "point_id": "L-02-04"})
        self.assertEqual(normalized["function"]["name"], "move")

    def test_object_tool_call_converts_to_executor_action(self):
        tool_call = SimpleNamespace(
            id="call_click",
            function=SimpleNamespace(
                name="click",
                arguments=json.dumps({"button": "left", "repeat": 2}),
            ),
        )

        action, normalized = tool_call_to_action(tool_call)

        self.assertEqual(action, {"action_type": "click", "button": "left", "repeat": 2})
        self.assertEqual(normalized["id"], "call_click")

    def test_unknown_tool_call_is_rejected(self):
        tool_call = {
            "id": "call_unknown",
            "type": "function",
            "function": {
                "name": "raw_coordinates",
                "arguments": json.dumps({"x": 1, "y": 2}),
            },
        }

        with self.assertRaises(ToolCallProtocolError):
            tool_call_to_action(tool_call)

    def test_multiple_tool_calls_convert_to_ordered_actions(self):
        tool_calls = [
            {
                "id": "call_click",
                "type": "function",
                "function": {"name": "click", "arguments": json.dumps({"button": "left"})},
            },
            {
                "id": "call_type",
                "type": "function",
                "function": {"name": "type", "arguments": json.dumps({"text": "hello", "submit": True})},
            },
        ]

        actions = tool_calls_to_actions(tool_calls)

        self.assertEqual(
            [action for action, _ in actions],
            [
                {"action_type": "click", "button": "left"},
                {"action_type": "type", "text": "hello", "submit": True},
            ],
        )

    def test_compact_tool_call_for_log_keeps_only_name_and_arguments(self):
        tool_call = {
            "id": "call_move",
            "type": "function",
            "function": {
                "name": "move",
                "arguments": json.dumps({"point_id": "G-01-02", "duration": 0.1}),
            },
        }

        compact = compact_tool_call_for_log(tool_call)

        self.assertEqual(
            compact,
            {"name": "move", "arguments": {"point_id": "G-01-02", "duration": 0.1}},
        )
        self.assertNotIn("id", compact)
        self.assertNotIn("type", compact)
        self.assertNotIn("function", compact)


class AssistantContentTests(unittest.TestCase):
    def test_assistant_text_content_preserves_mixed_text_parts(self):
        content = [
            {"type": "text", "text": "I will move first. "},
            {"type": "text", "text": "Then inspect."},
        ]

        self.assertEqual(assistant_text_content(content), "I will move first. Then inspect.")


if __name__ == "__main__":
    unittest.main()
