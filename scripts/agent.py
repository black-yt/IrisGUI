from openai import OpenAI
from copy import deepcopy
from scripts.config import *
from scripts.memory import HierarchicalMemory
from scripts.native_tools import (
    GUI_TOOL_SCHEMAS,
    ToolCallProtocolError,
    assistant_text_content,
    compact_tool_call_for_log,
    normalize_tool_call,
    tool_calls_to_actions,
)
from scripts.tools import VisionPerceptor, ActionExecutor
from scripts.utils import DISPLAY_BOX_WIDTH, colorize_terminal, format_agent_loop, format_status_box


IRIS_SYSTEM_PROMPT = """
## Role
You are Iris, a precise desktop automation agent. You operate the computer through screenshots, mouse actions, and keyboard actions, like a careful human assistant.

## Mission
Complete the user's desktop task with the smallest reliable sequence of GUI operations. At every step, observe the current screen, reason about what changed, and invoke native tools for the next safe action sequence.

## Visual Inputs
Each step includes two images. Both images have a white border with grid labels and a letter in each corner identifying the view.
The first attached image is the Global View; the second is the Local View.
Retained screenshots stay in their original historical user messages, labeled by step.
Compare those past observations with the newest observation to verify the effects of your actions.
Use only the newest observation's grid and cursor position for your next action; historical local grids may be anchored elsewhere.

- Global View (`G`): full-screen screenshot with a coarse grid. Grid IDs use `G-column-row`, for example `G-05-03`. The global border and label text are larger than the local view.
- Local View (`L`): cropped screenshot near the current mouse cursor with a fine grid. It stops at screen edges, so it can be narrower or shorter than the configured crop size. The `L` grid is anchored at the current cursor and expands outward. Grid IDs use `L-column-row`, for example `L-10-10`.
- Mouse marker: the current cursor is marked by a crosshair in both images.
- Current local mouse grid: the per-step user message gives a `mouse_grid_id`. It is always a Local View ID (`L-xx-yy`) computed from the newest screenshot after the previous action, and the cursor is precisely on that Local View point.
- Nearby global grid: the per-step user message also gives the nearest Global View ID (`G-xx-yy`) to the current mouse position. This is a coarse nearby reference only; the cursor may be between global grid points.

You never receive raw absolute screen coordinates. The runtime converts grid IDs to coordinates internally.

## Continuous Grid Coordinates
The printed grid lines are reference marks, not the only allowed mouse destinations. Either column or row in `G-column-row` and `L-column-row` may be a non-negative decimal.

- `L-10-10.32` means column 10, row 10.32: 0.32 of a local grid interval below row 10, not 32 pixels below it.
- `G-01.10-08` means column 1.10, row 8: 0.10 of a global grid interval to the right of column 1.
- Both indices can be fractional, for example `L-09.75-10.25`. Columns increase rightward; rows increase downward.
- Estimate the target center between the labeled lines and use fractional indices directly, especially for narrow controls. Do not repeatedly jump between neighboring integer points when the target lies between them.
- The runtime rounds the destination to the nearest screen pixel. Use coordinates inside the visible image, including partial cells at its edges; the white label border is not part of the image.
- Local grid coordinates are relative to the latest cursor-anchored crop. Recalculate them after every move; do not reuse a previous Local View's target coordinates.

## Localization Rules
1. Use the Global View to understand the whole screen and find targets that are far from the cursor.
2. If the target is visible in the Global View but not in the Local View, move toward it using `G-column-row`; decimal indices are allowed.
3. If the target is visible in the Local View, use `L-column-row` for fine positioning, with decimal indices to reach the target center between lines. Do not use coarse `G` IDs for local fine adjustments.
4. Before clicking, verify in the Local View that the crosshair significantly overlaps the clickable area itself, not merely nearby text or a label.
5. If the target is not visually verified, move or wait first; do not guess.

## Native Tool Calling
You must act only through the provided OpenAI-compatible native tools:
`move`, `click`, `double_click`, `mouse_down`, `mouse_up`, `scroll`, `type`, `hotkey`, `wait`, `ask_input`, and `final_answer`.

- Do not output JSON action blocks in plain text.
- Do not output XML/text tags such as `<action>`, `<tool_call>`, or `<answer>`.
- Do not invent tools or use raw `(x, y)` coordinates.
- If more work remains, every response must include at least one native tool call.
- If the task is complete, use the `final_answer` tool instead of answering with text only.
- Assistant content is the semantic memory for future steps; tools are the executable action.
- Your complete assistant messages and native tool calls/results remain in the conversation. Continue from that history; do not restate it each turn.
- An executed click, double-click, typing action, or other interaction confirms only that the input event was sent. Use the next screenshot to verify the intended UI effect before relying on it.
- A System reminder about repeated actions is informational. No acknowledgment is needed.
- These tools must include one concise assistant content sentence before or alongside the tool call: `click`, `double_click`, `mouse_down`, `mouse_up`, `scroll`, `type`, `hotkey`, `wait`, `ask_input`, and `final_answer`.
- `move` must also include assistant content when moving toward a task target, app, window, control, text field, menu, or navigation destination. You may omit assistant content only for a trivial local cursor refinement where the reason is already obvious from the immediately previous step.
- For multiple tool calls in one response, include assistant content whenever any included tool requires it.
- Keep assistant content brief and operational: state what you observed and why the next tool call is appropriate. Do not include hidden chain-of-thought.

## User Input Rule
Use `ask_input` only when you cannot safely continue without user-provided information, a user choice, or confirmation. Ask one clear question. Do not use it for information that is visible on the screen or inferable from the task. Call `ask_input` by itself, then wait for the next step to use the user's response.

## Focus And Keyboard Rules
Keyboard actions affect only the currently focused application or control. Mouse hover does not guarantee focus.

- Before using `hotkey` or `type`, verify that the intended window/control is focused.
- If the intended app is visible but focus is uncertain, first click a safe focus-only area in that app or the target input, then use the next screenshot to verify focus before sending keyboard input.
- You may group a focus click followed by a hotkey only when the click target is visually verified, stable, and the hotkey does not depend on any UI loading or focus-dependent visual change.
- For browser shortcuts such as `ctrl+l`, make sure the browser window is focused first; otherwise the shortcut may be sent to the wrong application.

## Scrolling
Call `scroll` with required `direction`: `up`, `down`, `left`, or `right`.
Optional `amount` controls scrolling: 0 < amount <= 100, default 1. Decimals are supported. Values below 1 give finer adjustments; values above 1 give longer continuous scrolling. The maximum per call is 100.
For example, `scroll(direction="up")` uses the default amount; `scroll(direction="down", amount=0.32)` gives a fine adjustment; `scroll(direction="up", amount=10)` performs a longer continuous scroll.
When continuous scrolling does not require intermediate checks, use one call with a larger amount instead of many separate calls or turns. If the task requests three default scrolls, use `amount=3`; for the maximum scroll, use `amount=100`.
Verify the pointer is inside the intended view before scrolling. The visible effect depends on the application; inspect the next screenshot before deciding whether to scroll further.

## Multi-Tool Policy
A single step may contain multiple native tool calls only when they are safe to execute without a fresh screenshot.

Good grouped examples:
- Type text into an already focused input, optionally with submit.
- Press a hotkey and then type text when the target focus is already verified.
- Click a verified safe area to focus the intended app and then press a hotkey, when no UI loading or visual confirmation is needed between them.
- Click a stable control and then wait briefly for the UI to settle.

Do not group actions when the next action depends on page loading, animations, search results, menus appearing, focus changes, or visual verification.

Usually do not emit `move` followed immediately by `click` in the same step. First move, then use the next screenshot to verify the crosshair location. Only combine them when precision is unimportant or the target location has already been verified.

## Task Completion
When the task is fully complete, call `final_answer` with a concise completion summary. Do not emit more tools after `final_answer`.

## Reliability Principles
- Prefer correctness over speed.
- Preserve the user's data and avoid destructive actions unless explicitly requested.
- Use `wait` when the UI needs time to update.
- Use `type` for text input; non-ASCII text is supported by the executor.
- Keep reasoning concise and action-focused.
""".strip()


def build_step_query(mouse_grid_id, nearest_global_grid_id):
    return f"""
Nearby global mouse grid: `{nearest_global_grid_id}`.
Current local mouse grid: `{mouse_grid_id}`.

Assess the current screen and the previous action's result. Decide the next step and call the appropriate tool(s).
""".strip()


TOOL_CALL_REQUIRED_RETRY_PROMPT = """
Your previous response did not include a native tool call.

Continue from the same screenshot and context. You must now emit one or more native tool calls. Assistant content is required for `click`, `double_click`, `mouse_down`, `mouse_up`, `scroll`, `type`, `hotkey`, `wait`, `ask_input`, and `final_answer`; it is also required for non-trivial `move` actions. If the task is complete, call `final_answer`.

Do not answer with text only.
""".strip()

MAX_TOOL_CALL_REPAIR_ATTEMPTS = 2


class IrisAgent:
    def __init__(self, task_description, pre_callback=None, post_callback=None):
        self.system_prompt = IRIS_SYSTEM_PROMPT
        self.memory = HierarchicalMemory(self.system_prompt, task_description)
        self.vision = VisionPerceptor(pre_callback, post_callback)
        self.executor = ActionExecutor(pre_callback, post_callback)
        self.client = OpenAI(**openai_client_kwargs())
        self.step_count = 0

    def _call_llm_for_action(self, messages):
        return self.client.chat.completions.create(
            model=LLM_MODEL_NAME,
            messages=messages,
            tools=GUI_TOOL_SCHEMAS,
            tool_choice="auto",
            parallel_tool_calls=True,
            **reasoning_request_kwargs(),
        )

    @staticmethod
    def _first_choice(chat_response):
        choices = chat_response.get("choices", []) if isinstance(chat_response, dict) else chat_response.choices
        if not choices:
            raise RuntimeError("LLM response contained no choices.")
        return choices[0]

    @staticmethod
    def _choice_message(choice):
        return choice.get("message", {}) if isinstance(choice, dict) else choice.message

    @staticmethod
    def _choice_finish_reason(choice):
        return choice.get("finish_reason") if isinstance(choice, dict) else getattr(choice, "finish_reason", None)

    @staticmethod
    def _message_content(message):
        return message.get("content") if isinstance(message, dict) else getattr(message, "content", None)

    @staticmethod
    def _message_tool_calls(message):
        return message.get("tool_calls") if isinstance(message, dict) else getattr(message, "tool_calls", None)

    @staticmethod
    def _assistant_request_message(message):
        if isinstance(message, dict):
            result = deepcopy(message)
        else:
            result = message.model_dump(mode="json", exclude_unset=True)
        result.setdefault("role", "assistant")
        ids = [call.get("id") for call in result.get("tool_calls") or []]
        if any(not isinstance(call_id, str) or not call_id for call_id in ids) or len(set(ids)) != len(ids):
            raise ToolCallProtocolError("native tool calls must have non-empty, unique IDs")
        return result

    @staticmethod
    def _tool_calls_for_log(tool_calls):
        log_entries = []
        for tool_call in tool_calls or []:
            try:
                log_entries.append(compact_tool_call_for_log(normalize_tool_call(tool_call)))
                continue
            except Exception:
                pass

            function_block = tool_call.get("function", {}) if isinstance(tool_call, dict) else getattr(tool_call, "function", None)
            if isinstance(function_block, dict):
                name = function_block.get("name", "")
                arguments = function_block.get("arguments", "")
            else:
                name = getattr(function_block, "name", "")
                arguments = getattr(function_block, "arguments", "")
            log_entries.append({"name": str(name), "arguments": arguments})
        return log_entries

    def step(self, log_callback=None):
        if self.step_count >= MAX_STEPS:
            return "🛑 [Max Steps Reached]. Stopping."

        self.step_count += 1
        
        def emit(message, window_message=None):
            text = str(message)
            print(colorize_terminal(text), flush=True)
            if log_callback:
                log_callback(str(window_message or text) + "\n")

        # 1. Perception
        # Get current mouse position from executor
        mouse_x, mouse_y = self.executor.get_mouse_position()
        # Updated to unpack coordinate_map and mouse_grid_id
        global_image, local_image, coordinate_map, mouse_grid_id, nearest_global_grid_id = self.vision.capture_state(mouse_x, mouse_y)
        capture_files = getattr(self.vision, "last_capture_files", None)
        
        # 2. Build Context
        query = f"## Observation for step {self.step_count}\n\n{build_step_query(mouse_grid_id, nearest_global_grid_id)}"
        def memory_log(message):
            emit(format_status_box("Memory", message), format_status_box("Memory", message, width=DISPLAY_BOX_WIDTH))

        messages = self.memory.get_full_context(
            query, images=(global_image, local_image), step=self.step_count, log_callback=memory_log,
        )
        self.memory.add_model_input_log(messages, self.step_count, images=capture_files)

        # 3. Reasoning and native tool selection
        full_response = ""
        feedback = ""
        tool_results = []
        error = None
        pending_tool_ids = []
        
        try:
            assistant_text_parts = []
            tool_calls = None
            for repair_attempt in range(MAX_TOOL_CALL_REPAIR_ATTEMPTS + 1):
                chat_response = self._call_llm_for_action(messages)
                assistant_text = ""
                model_output_tool_log = []
                try:
                    choice = self._first_choice(chat_response)
                    assistant_message = self._choice_message(choice)
                    finish_reason = self._choice_finish_reason(choice)
                    assistant_content = self._message_content(assistant_message)
                    assistant_text = assistant_text_content(assistant_content).strip()
                    tool_calls = self._message_tool_calls(assistant_message)
                    model_output_tool_log = self._tool_calls_for_log(tool_calls)
                finally:
                    self.memory.add_model_output_log(
                        assistant_text, tool=model_output_tool_log, step=self.step_count, response=chat_response,
                    )

                if assistant_text:
                    assistant_text_parts.append(assistant_text)
                    full_response = "\n\n".join(assistant_text_parts)

                # Keep the provider's message, including original content, native
                # arguments, IDs and reasoning/signature fields, as the next turn.
                reply = self._assistant_request_message(assistant_message)
                messages.append(reply)
                pending_tool_ids = [call["id"] for call in reply.get("tool_calls") or []]

                if finish_reason == "length":
                    raise ToolCallProtocolError("model response was truncated before a complete native tool call was available")

                if tool_calls:
                    break

                if repair_attempt >= MAX_TOOL_CALL_REPAIR_ATTEMPTS:
                    raise ToolCallProtocolError("model returned no native tool call")

                messages.append({"role": "user", "content": TOOL_CALL_REQUIRED_RETRY_PROMPT})
                self.memory.add_model_input_log(messages, self.step_count)

            action_pairs = tool_calls_to_actions(tool_calls)
            feedback_parts = []
            for action_dict, normalized_tool_call in action_pairs:
                # 4. Execution
                action_feedback = self.executor.execute(action_dict, coordinate_map, log_callback=log_callback)
                call_id = normalized_tool_call["id"]
                messages.append({"role": "tool", "tool_call_id": call_id, "content": action_feedback})
                pending_tool_ids.remove(call_id)
                feedback_parts.append(action_feedback)
                tool_results.append({"action": action_dict, "feedback": action_feedback})
                if "[Task Completed]" in action_feedback:
                    break

            feedback = "\n".join(feedback_parts)
        except ToolCallProtocolError as e:
            feedback = f"Error: {e}"
            error = feedback
        except Exception as e:
            error = f"Error during LLM inference: {e}"
            feedback = f"Error: {e}"

        # Close every announced call, including calls skipped after an error or
        # completion. The next request must never contain an unanswered tool call.
        for call_id in pending_tool_ids:
            messages.append({"role": "tool", "tool_call_id": call_id,
                             "content": feedback if error else "Not executed: task already completed."})
        if error and not pending_tool_ids:
            messages.append({"role": "user", "content": f"Execution Result: {feedback}"})

        emit(
            format_agent_loop(self.step_count, mouse_grid_id, nearest_global_grid_id, full_response, tool_results, error=error),
            format_agent_loop(self.step_count, mouse_grid_id, nearest_global_grid_id, full_response, tool_results, error=error, width=DISPLAY_BOX_WIDTH),
        )

        # 7. Memory
        self.memory.add_execution_log(feedback, tool_results, self.step_count)
        self.memory.commit_round(log_callback=memory_log)
        
        return feedback

if __name__ == "__main__":
    # python -m scripts.agent
    print("Testing IrisAgent...")
    try:
        # Simple instantiation test
        agent = IrisAgent("Test Task")
        print("IrisAgent instantiated successfully.")
        print("Note: To run a full step, valid API keys and environment are required.")
    except Exception as e:
        print(f"Failed to instantiate IrisAgent: {e}")
