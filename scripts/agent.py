from openai import OpenAI
from scripts.config import *
from scripts.memory import HierarchicalMemory
from scripts.native_tools import (
    GUI_TOOL_SCHEMAS,
    ToolCallProtocolError,
    assistant_text_content,
    compact_tool_call_for_log,
    format_tool_call_for_memory,
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

- Global View (`G`): full-screen screenshot with a coarse grid. Grid IDs use `G-column-row`, for example `G-05-03`. The global border and label text are larger than the local view.
- Local View (`L`): cropped screenshot near the current mouse cursor with a fine grid. It stops at screen edges, so it can be narrower or shorter than the configured crop size. The `L` grid is anchored at the current cursor and expands outward. Grid IDs use `L-column-row`, for example `L-10-10`.
- Mouse marker: the current cursor is marked by a crosshair in both images.
- Current local mouse grid: the per-step user message gives a `mouse_grid_id`. It is always a Local View ID (`L-xx-yy`) computed from the newest screenshot after the previous action, and the cursor is precisely on that Local View point.
- Nearby global grid: the per-step user message also gives the nearest Global View ID (`G-xx-yy`) to the current mouse position. This is a coarse nearby reference only; the cursor may be between global grid points.

You never receive raw absolute screen coordinates. The runtime converts grid IDs to coordinates internally.

## Localization Rules
1. Use the Global View to understand the whole screen and find targets that are far from the cursor.
2. If the target is visible in the Global View but not in the Local View, move to the nearest appropriate `G-xx-yy` grid point.
3. If the target is visible in the Local View, use `L-xx-yy` for fine positioning. Do not use coarse `G` IDs for local fine adjustments.
4. Before clicking, verify in the Local View that the crosshair significantly overlaps the clickable area itself, not merely nearby text or a label.
5. If the target is not visually verified, move or wait first; do not guess.

## Native Tool Calling
You must act only through the provided OpenAI-compatible native tools:
`move`, `click`, `double_click`, `mouse_down`, `mouse_up`, `scroll`, `type`, `hotkey`, `wait`, and `final_answer`.

- Do not output JSON action blocks in plain text.
- Do not output XML/text tags such as `<action>`, `<tool_call>`, or `<answer>`.
- Do not invent tools or use raw `(x, y)` coordinates.
- If more work remains, every response must include at least one native tool call.
- If the task is complete, use the `final_answer` tool instead of answering with text only.
- Prefer to include concise assistant text with tool calls so future memory has useful planning context.
- Key steps must include a short text explanation before or alongside the tool call: opening or switching apps, changing focus, entering or submitting text, choosing a navigation target, waiting for loading, recovering from an error, or completing the task.
- Keep assistant text brief and operational: state what you observed and why the next tool call is appropriate.

## Focus And Keyboard Rules
Keyboard actions affect only the currently focused application or control. Mouse hover does not guarantee focus.

- Before using `hotkey` or `type`, verify that the intended window/control is focused.
- If the intended app is visible but focus is uncertain, first click a safe focus-only area in that app or the target input, then use the next screenshot to verify focus before sending keyboard input.
- You may group a focus click followed by a hotkey only when the click target is visually verified, stable, and the hotkey does not depend on any UI loading or focus-dependent visual change.
- For browser shortcuts such as `ctrl+l`, make sure the browser window is focused first; otherwise the shortcut may be sent to the wrong application.

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
## Current Step

You are seeing the latest screen state after the previous action.

## Inputs Attached To This Message
1. Global View image: full screen, coarse `G-xx-yy` grid, `G` marks in the four border corners.
2. Local View image: cursor-anchored crop clipped at screen edges, fine `L-xx-yy` grid, `L` marks in the four border corners.
3. Nearby global mouse grid: `{nearest_global_grid_id}`.
4. Current local mouse grid: `{mouse_grid_id}`.

`{nearest_global_grid_id}` is only the nearest Global View grid point near the current mouse position. The cursor is not necessarily on this Global View point; use it as a coarse whole-screen reference only.
`{mouse_grid_id}` is the updated Local View grid point where the mouse is currently located in this newest screenshot. The cursor is precisely on this Local View point, and it is not an old grid point from history.

## What To Do
1. Compare the latest visual state with the task and the previous execution history.
2. Identify the immediate next safe GUI operation.
3. Use Global View for broad navigation and Local View for precise verification.
4. Emit native tool call(s). Include concise assistant text for meaningful or planning-relevant steps, especially when the action changes focus, enters text, navigates, waits, recovers, or completes the task.
5. Use multiple tool calls in this step only when they do not depend on UI loading or another visual check.
""".strip()


TOOL_CALL_REQUIRED_RETRY_PROMPT = """
Your previous response did not include a native tool call.

Continue from the same screenshot and context. You must now emit one or more native tool calls. Assistant text is optional in this repair response, but a tool call is required if work remains. If the task is complete, call `final_answer`.

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
        query = build_step_query(mouse_grid_id, nearest_global_grid_id)
        messages = self.memory.get_full_context(query, images=(global_image, local_image))
        self.memory.add_model_input_log(messages, self.step_count, images=capture_files)

        # 3. Reasoning and native tool selection
        full_response = ""
        feedback = ""
        tool_results = []
        tool_log = []
        tool_memory_parts = []
        error = None
        
        try:
            assistant_text_parts = []
            tool_calls = None
            for repair_attempt in range(MAX_TOOL_CALL_REPAIR_ATTEMPTS + 1):
                chat_response = self._call_llm_for_action(messages)
                choice = self._first_choice(chat_response)
                assistant_message = self._choice_message(choice)
                finish_reason = self._choice_finish_reason(choice)
                assistant_content = self._message_content(assistant_message)
                assistant_text = assistant_text_content(assistant_content).strip()
                tool_calls = self._message_tool_calls(assistant_message)
                model_output_tool_log = self._tool_calls_for_log(tool_calls)

                if assistant_text:
                    assistant_text_parts.append(assistant_text)
                    full_response = "\n\n".join(assistant_text_parts)

                self.memory.add_model_output_log(assistant_text, tool=model_output_tool_log, step=self.step_count)

                if finish_reason == "length":
                    raise ToolCallProtocolError("model response was truncated before a complete native tool call was available")

                if tool_calls:
                    break

                if repair_attempt >= MAX_TOOL_CALL_REPAIR_ATTEMPTS:
                    raise ToolCallProtocolError("model returned no native tool call")

                if assistant_text:
                    messages.append({"role": "assistant", "content": assistant_text})
                messages.append({"role": "user", "content": TOOL_CALL_REQUIRED_RETRY_PROMPT})
                self.memory.add_model_input_log(messages, self.step_count)

            action_pairs = tool_calls_to_actions(tool_calls)
            feedback_parts = []
            for action_dict, normalized_tool_call in action_pairs:
                tool_log.append(compact_tool_call_for_log(normalized_tool_call))
                tool_memory_parts.append(format_tool_call_for_memory(normalized_tool_call))

                # 4. Execution
                action_feedback = self.executor.execute(action_dict, coordinate_map)
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
            emit(
                format_agent_loop(self.step_count, mouse_grid_id, nearest_global_grid_id, full_response, tool_results, error=error),
                format_agent_loop(self.step_count, mouse_grid_id, nearest_global_grid_id, full_response, tool_results, error=error, width=DISPLAY_BOX_WIDTH),
            )
            return f"Error: {e}"

        emit(
            format_agent_loop(self.step_count, mouse_grid_id, nearest_global_grid_id, full_response, tool_results, error=error),
            format_agent_loop(self.step_count, mouse_grid_id, nearest_global_grid_id, full_response, tool_results, error=error, width=DISPLAY_BOX_WIDTH),
        )

        # 7. Memory
        def memory_log(message):
            emit(format_status_box("Memory", message), format_status_box("Memory", message, width=DISPLAY_BOX_WIDTH))

        memory_content = "\n".join(part for part in [full_response, *tool_memory_parts] if part).strip()
        assistant_log_extra = {"step": self.step_count}
        user_log_extra = {"step": self.step_count}
        if capture_files:
            user_log_extra["images"] = capture_files
        self.memory.add_interaction(
            memory_content,
            f"Execution Result: {feedback}",
            tool=tool_log,
            assistant_log_content=full_response,
            assistant_log_extra=assistant_log_extra,
            user_log_extra=user_log_extra,
            log_callback=memory_log,
            debug_log=False,
        )
        
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
