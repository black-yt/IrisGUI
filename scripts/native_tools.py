import json
from dataclasses import dataclass
from typing import Any, Optional


class ToolCallProtocolError(ValueError):
    """Raised when the model response does not follow the native tool protocol."""


@dataclass(frozen=True)
class NativeToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    action_type: str


BUTTON_SCHEMA = {
    "type": "string",
    "enum": ["left", "right", "middle"],
    "description": "Mouse button to use. Defaults to left when omitted.",
}


GUI_ACTION_TOOLS = [
    NativeToolSpec(
        name="move",
        action_type="move",
        description=(
            "Move the mouse cursor to a visible grid point. Use G-xx-yy for broad movement in the Global View "
            "and L-xx-yy for precise movement in the Local View. Do not provide raw screen coordinates."
        ),
        parameters={
            "type": "object",
            "properties": {
                "point_id": {
                    "type": "string",
                    "description": "Visible grid point ID such as G-05-03 or L-02-04.",
                },
                "duration": {
                    "type": "number",
                    "description": "Optional movement duration in seconds. Default is 0.5.",
                },
            },
            "required": ["point_id"],
        },
    ),
    NativeToolSpec(
        name="click",
        action_type="click",
        description=(
            "Click the current mouse position. Use only after the latest Local View verifies that the crosshair "
            "overlaps the intended clickable target."
        ),
        parameters={
            "type": "object",
            "properties": {
                "button": BUTTON_SCHEMA,
                "repeat": {
                    "type": "integer",
                    "description": "Number of clicks. Default is 1.",
                },
            },
        },
    ),
    NativeToolSpec(
        name="double_click",
        action_type="double_click",
        description="Double-click the current mouse position after local visual verification.",
        parameters={
            "type": "object",
            "properties": {},
        },
    ),
    NativeToolSpec(
        name="mouse_down",
        action_type="mouse_down",
        description="Press and hold a mouse button at the current cursor position, usually as the start of a verified drag.",
        parameters={
            "type": "object",
            "properties": {
                "button": BUTTON_SCHEMA,
            },
        },
    ),
    NativeToolSpec(
        name="mouse_up",
        action_type="mouse_up",
        description="Release a mouse button at the current cursor position, usually to finish a verified drag.",
        parameters={
            "type": "object",
            "properties": {
                "button": BUTTON_SCHEMA,
            },
        },
    ),
    NativeToolSpec(
        name="scroll",
        action_type="scroll",
        description="Scroll the current UI when the active view or pointer location is appropriate for scrolling.",
        parameters={
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "enum": ["up", "down", "left", "right"],
                    "description": "Scroll direction.",
                },
                "amount": {
                    "type": "string",
                    "enum": ["line", "half", "page"],
                    "description": "Scroll amount.",
                },
            },
            "required": ["direction", "amount"],
        },
    ),
    NativeToolSpec(
        name="type",
        action_type="type",
        description=(
            "Enter text into the currently focused field. Only use when focus is already verified. "
            "Non-ASCII text is handled by the executor through the clipboard."
        ),
        parameters={
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Exact text to enter.",
                },
                "submit": {
                    "type": "boolean",
                    "description": "Whether to press Enter after typing. Default is false.",
                },
            },
            "required": ["text"],
        },
    ),
    NativeToolSpec(
        name="hotkey",
        action_type="hotkey",
        description=(
            "Press a keyboard shortcut such as ctrl+c, ctrl+l, enter, escape, or alt+tab. "
            "Only use when the intended application/control focus is already verified; shortcuts are sent "
            "to the currently focused target, not to the window under the mouse."
        ),
        parameters={
            "type": "object",
            "properties": {
                "keys": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Keys to press together, for example ['ctrl', 'c'].",
                },
            },
            "required": ["keys"],
        },
    ),
    NativeToolSpec(
        name="wait",
        action_type="wait",
        description="Wait for the UI to load, animate, or settle before the next visual observation.",
        parameters={
            "type": "object",
            "properties": {
                "seconds": {
                    "type": "number",
                    "description": "Number of seconds to wait.",
                },
            },
            "required": ["seconds"],
        },
    ),
    NativeToolSpec(
        name="ask_input",
        action_type="ask_input",
        description=(
            "Ask the user for missing information, a choice, or confirmation. Use only when the task cannot "
            "continue reliably from the screen and existing context. Call this tool alone; the user's answer "
            "is available only after this step finishes."
        ),
        parameters={
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "One clear question to show to the user in the terminal.",
                },
            },
            "required": ["question"],
        },
    ),
    NativeToolSpec(
        name="final_answer",
        action_type="final_answer",
        description="Report that the user's task is fully complete. Do not call this while work remains.",
        parameters={
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Final result or completion summary for the user.",
                },
            },
            "required": ["text"],
        },
    ),
]


TOOL_NAME_TO_ACTION_TYPE = {tool.name: tool.action_type for tool in GUI_ACTION_TOOLS}


def tool_schema(tool: NativeToolSpec) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        },
    }


GUI_TOOL_SCHEMAS = [tool_schema(tool) for tool in GUI_ACTION_TOOLS]


def assistant_text_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                text_parts.append(str(part.get("text", "")))
            else:
                text_parts.append(str(part))
        return "".join(text_parts)
    return str(content)


def normalize_tool_call(tool_call: Any) -> dict[str, Any]:
    if isinstance(tool_call, dict):
        function_block = tool_call.get("function", {}) or {}
        return {
            "id": str(tool_call.get("id", "")),
            "type": "function",
            "function": {
                "name": str(function_block.get("name", "")),
                "arguments": function_block.get("arguments", "{}"),
            },
        }

    function_block = getattr(tool_call, "function", None)
    return {
        "id": str(getattr(tool_call, "id", "")),
        "type": "function",
        "function": {
            "name": str(getattr(function_block, "name", "")),
            "arguments": getattr(function_block, "arguments", "{}"),
        },
    }


def parse_tool_arguments(raw_arguments: Any) -> dict[str, Any]:
    if raw_arguments is None or raw_arguments == "":
        return {}
    if isinstance(raw_arguments, dict):
        return raw_arguments
    if not isinstance(raw_arguments, str):
        raise ToolCallProtocolError("tool arguments must be a JSON object or JSON string")

    try:
        parsed: Any = json.loads(raw_arguments)
    except (TypeError, ValueError) as exc:
        raise ToolCallProtocolError(f"tool arguments are not valid JSON: {exc}") from exc

    if isinstance(parsed, str):
        nested = parsed.strip()
        if nested.startswith("{") or nested.startswith("["):
            try:
                parsed = json.loads(nested)
            except (TypeError, ValueError):
                pass

    if not isinstance(parsed, dict):
        raise ToolCallProtocolError("tool arguments must decode to a JSON object")
    return parsed


def normalize_tool_calls(tool_calls: Optional[list[Any]]) -> list[dict[str, Any]]:
    normalized = [normalize_tool_call(tool_call) for tool_call in (tool_calls or [])]
    if not normalized:
        raise ToolCallProtocolError("model returned no native tool call")
    return normalized


def tool_call_to_action(tool_call: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized = normalize_tool_call(tool_call)
    function_block = normalized.get("function", {})
    tool_name = str(function_block.get("name", ""))
    if tool_name not in TOOL_NAME_TO_ACTION_TYPE:
        raise ToolCallProtocolError(f"unknown tool call: {tool_name!r}")

    arguments = parse_tool_arguments(function_block.get("arguments", "{}"))
    action = {"action_type": TOOL_NAME_TO_ACTION_TYPE[tool_name]}
    action.update(arguments)
    return action, normalized


def tool_calls_to_actions(tool_calls: Optional[list[Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    return [tool_call_to_action(tool_call) for tool_call in normalize_tool_calls(tool_calls)]


def compact_tool_call_for_log(tool_call: dict[str, Any]) -> dict[str, Any]:
    function_block = tool_call.get("function", {})
    tool_name = str(function_block.get("name", ""))
    arguments = parse_tool_arguments(function_block.get("arguments", "{}"))
    return {
        "name": tool_name,
        "arguments": arguments,
    }


def format_tool_call_for_memory(tool_call: dict[str, Any]) -> str:
    function_block = tool_call.get("function", {})
    tool_name = str(function_block.get("name", ""))
    arguments = parse_tool_arguments(function_block.get("arguments", "{}"))
    return f"Tool call: {tool_name}\nArguments: {json.dumps(arguments, ensure_ascii=False)}"
