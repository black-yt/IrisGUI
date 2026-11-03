from scripts.config import *
from openai import OpenAI
import base64
from io import BytesIO
import json
import math
import os
import struct
from datetime import datetime
from copy import deepcopy
from scripts.native_tools import GUI_TOOL_SCHEMAS


MEMORY_MANAGER_SYSTEM_PROMPT_TEMPLATE = """
## Role
You are the memory manager for Iris, a desktop GUI automation agent.

## Objective
Compress Iris's operational history into accurate, compact memory that can be reused in later GUI automation steps.

## What Matters
- The user's original goal.
- What Iris observed or inferred about the UI state.
- Actions Iris attempted, including important grid IDs, typed text, hotkeys, waits, clicks, user questions, user-provided answers, and final answers.
- Execution results, errors, blockers, and whether the task is complete.
- Current unresolved state: what should be tried next, what should be avoided, and any relevant UI position or focus information.

## What To Remove
- Repeated wording, filler reasoning, decorative output formatting, and obvious restatements.
- Raw image data or debug-only metadata.
- Details that no longer affect future decisions.

## Rules
- Preserve chronological order.
- Do not invent actions, results, UI state, or user intent.
- Do not complete the user's task yourself.
- Keep the summary dense but readable.

## Original User Task
```text
{initial_task}
```
""".strip()


SHORT_MEMORY_COMPRESSION_INSTRUCTIONS = """
## Compression Task
Summarize the provided recent interaction history into a concise operational memory paragraph.

Include:
- The latest known UI state.
- The concrete actions taken and their results.
- Any errors, failed attempts, or uncertainty.
- The next relevant state or pending goal if the task is not finished.

Format:
`History Summary: ...`
""".strip()


LONG_MEMORY_COMPRESSION_INSTRUCTIONS = """
## Compression Task
Consolidate the provided historical summaries into one high-level long-term memory.

Include:
- Completed subtasks and durable facts about the UI workflow.
- Important decisions, errors, or constraints that still matter.
- The current pending goal or next useful direction, if any.

Remove transient step-by-step detail that no longer helps future action selection.

Format:
`Long Term Memory: ...`
""".strip()


def build_memory_summary_user_prompt(instructions, memory_list):
    history_lines = []
    for index, step in enumerate(memory_list, start=1):
        role = step.get("role", "unknown")
        content = HierarchicalMemory.content_text(step.get("content", ""))
        fields = {key: value for key, value in step.items() if key not in {"role", "content"} and not key.startswith("_")}
        if fields:
            content += "\nNative message fields: " + json.dumps(fields, ensure_ascii=False)
        history_lines.append(f"### Entry {index} ({role})\n{content}")

    history = "\n\n".join(history_lines) if history_lines else "(No history provided.)"
    return f"""
{instructions}

## History To Compress
{history}
""".strip()


class HierarchicalMemory:
    def __init__(self, system_prompt, initial_task):
        self.system_prompt = system_prompt
        self.initial_task = initial_task
        self.fixed_layer = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": initial_task}
        ]
        self.long_memory_layer = []
        self.short_memory_layer = []
        self._fixed_input_logged = False
        self._pending_observation = None
        self._pending_request_messages = None
        self._pending_round_start = 0
        self._round_sequence = 0
        self._current_step = 0
        
        self.client = OpenAI(**openai_client_kwargs())

        # Initialize debug log path
        if DEBUG_MODE:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            log_dir = os.path.join(os.path.dirname(__file__), "debug", "log")
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            self.debug_save_path = os.path.join(log_dir, f"{timestamp}.jsonl")

    def _append_to_log(self, steps: list[dict]):
        """Helper to append steps to the JSONL log file"""
        try:
            with open(self.debug_save_path, 'a', encoding='utf-8') as f:
                for step in steps:
                    log_step = {
                        "step": step.get("step", 0),
                        "timestamp": datetime.now().isoformat(timespec="microseconds"),
                    }
                    for key, value in step.items():
                        if key not in {"step", "timestamp"}:
                            log_step[key] = value
                    f.write(json.dumps(log_step, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"Failed to write to debug log: {e}")

    @staticmethod
    def content_text(content):
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(str(item.get("text", "")))
            return "\n".join(part for part in text_parts if part)
        return str(content)

    _content_text_for_log = content_text

    def add_model_input_log(self, messages, step, images=None):
        self._current_step = step
        if not DEBUG_MODE:
            return

        fixed_prefix_present = messages[:len(self.fixed_layer)] == self.fixed_layer
        log_steps = []
        if fixed_prefix_present and not self._fixed_input_logged:
            for message in self.fixed_layer:
                log_steps.append(
                    {
                        "step": 0,
                        "direction": "input",
                        "role": message.get("role", ""),
                        "content": self._content_text_for_log(message.get("content", "")),
                    }
                )
            self._fixed_input_logged = True

        if not messages or (fixed_prefix_present and len(messages) == len(self.fixed_layer)):
            if log_steps:
                self._append_to_log(log_steps)
            return

        message = messages[-1]
        log_step = {
            "step": step,
            "direction": "input",
            "role": message.get("role", ""),
            "content": self._content_text_for_log(message.get("content", "")),
        }
        if images and message.get("role") == "user":
            log_step["images"] = images
        log_steps.append(log_step)
        self._append_to_log(log_steps)

    def add_model_output_log(self, content, tool=None, step=0, purpose=None, response=None):
        if not DEBUG_MODE:
            return

        log_step = {
            "step": step,
            "direction": "output",
            "role": "assistant",
            "content": self._content_text_for_log(content),
        }
        if tool:
            log_step["tool"] = tool
        if purpose:
            log_step["purpose"] = purpose
        if isinstance(response, dict):
            log_step["response"] = response
        elif callable(getattr(response, "model_dump", None)):
            log_step["response"] = response.model_dump(mode="json")
        self._append_to_log([log_step])

    def add_execution_log(self, feedback, tool_results, step):
        if DEBUG_MODE:
            self._append_to_log([{
                "step": step, "direction": "execution", "role": "user",
                "content": feedback, "tool_results": tool_results,
            }])

    def add_step(self, role, content, tool=None, log_content=None, log_extra=None, log_callback=None, compress=True, debug_log=True):
        """
        Add a new step to short_memory_layer.
        """
        step = {"role": role, "content": content}
        self.short_memory_layer.append(step)
        
        # Append to debug log
        if DEBUG_MODE and debug_log:
            log_step = {"role": role, "content": content if log_content is None else log_content}
            if tool:
                log_step["tool"] = tool
            if log_extra:
                log_step.update(log_extra)
            self._append_to_log([log_step])
        
        # Check if compression is needed
        if compress:
            self.compress_context(log_callback)

    def commit_round(self, log_callback=None):
        """Append this round's exact request/reply/tool transcript as one group."""
        if self._pending_request_messages is None:
            raise RuntimeError("Cannot commit a round without its original request messages")
        self._round_sequence += 1
        for message in self._pending_request_messages[self._pending_round_start:]:
            stored = deepcopy(message)
            stored["_round_id"] = self._round_sequence
            self.short_memory_layer.append(stored)
        self._pending_observation = None
        self._pending_request_messages = None
        self.compress_context(log_callback)

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
        self._round_sequence += 1
        round_start = len(self.short_memory_layer)
        self.add_step(
            "assistant",
            assistant_content,
            tool=tool,
            log_content=assistant_log_content,
            log_extra=assistant_log_extra,
            log_callback=log_callback,
            compress=False,
            debug_log=debug_log,
        )
        # The screenshot was observed BEFORE this assistant action. Expand it into
        # its original user message when building requests, never onto later results.
        if self._pending_observation is not None:
            self.short_memory_layer[-1]["_observation"] = self._pending_observation
            if self._pending_request_messages is not None:
                # Preserve repair assistant/user messages exactly as sent. Dropping
                # them would change the next request's previously submitted prefix.
                self.short_memory_layer[-1]["_request_continuation"] = (
                    self._pending_request_messages[self._pending_round_start + 1:]
                )
            self._pending_observation = None
            self._pending_request_messages = None
        self.add_step(
            "user",
            user_content,
            log_extra=user_log_extra,
            log_callback=log_callback,
            compress=False,
            debug_log=debug_log,
        )
        for message in self.short_memory_layer[round_start:]:
            message["_round_id"] = self._round_sequence
        self.compress_context(log_callback)

    def estimate_tokens_for_text(self, text):
        text = str(text)
        ascii_chars = 0
        non_ascii_tokens = 0
        for char in text:
            if ord(char) < 128:
                ascii_chars += 1
            elif char.isspace():
                ascii_chars += 1
            else:
                non_ascii_tokens += 1

        ascii_tokens = int(ascii_chars / max(1.0, MEMORY_CHARS_PER_TOKEN))
        return max(1, ascii_tokens + non_ascii_tokens)

    def estimate_tokens_for_steps(self, steps):
        return sum(
            self.estimate_tokens_for_text(step.get("role", "")) + self.estimate_tokens_for_content(step.get("content", ""))
            + self.estimate_tokens_for_text(json.dumps({key: value for key, value in step.items()
                if key not in {"role", "content"}}, ensure_ascii=False))
            for step in self._messages_for_steps(steps)
        )

    def estimate_tokens_for_content(self, content):
        if not isinstance(content, list):
            return self.estimate_tokens_for_text(content)
        total = 0
        for part in content:
            if part.get("type") == "text":
                total += self.estimate_tokens_for_text(part.get("text", ""))
            elif part.get("type") == "image_url":
                url = part["image_url"]["url"]
                prefix = "data:image/png;base64,"
                # All screenshots are encoded as PNG. Only decode its 24-byte
                # header to read dimensions; base64 itself is not text tokens.
                if not url.startswith(prefix):
                    raise ValueError("Expected a PNG screenshot data URL for token estimation")
                header = base64.b64decode(url[len(prefix):len(prefix) + 32])
                if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
                    raise ValueError("Invalid PNG screenshot header")
                width, height = struct.unpack(">II", header[16:24])
                # Do not apply server-side downscaling: this deliberately errs
                # high for large images. Compatible providers may tokenize differently.
                total += math.ceil(math.ceil(width / 32) * math.ceil(height / 32) * MEMORY_IMAGE_TOKEN_MULTIPLIER)
        return total

    @staticmethod
    def _messages_for_steps(steps):
        messages = []
        for step in steps:
            if step.get("_observation") is not None:
                messages.append(step["_observation"])
            messages.extend(step.get("_request_continuation", []))
            messages.append({key: value for key, value in step.items() if not key.startswith("_")})
        return messages

    @staticmethod
    def _has_images(message):
        content = message.get("content", "")
        return isinstance(content, list) and any(part.get("type") == "image_url" for part in content)

    def _prune_observation_images(self):
        if MEMORY_IMAGE_ROUNDS == -1:
            return
        observations = []
        for step in self.short_memory_layer:
            if step.get("_observation") is not None:
                observations.append(step["_observation"])
            if self._has_images(step):
                observations.append(step)
        if self._pending_observation is not None:
            observations.append(self._pending_observation)
        image_rounds = [message for message in observations if self._has_images(message)]
        for message in image_rounds[:-MEMORY_IMAGE_ROUNDS]:
            message["content"] = [part for part in message["content"] if part.get("type") != "image_url"]

    def compress_memory(self, memory_list, instructions, max_tokens=None):
        """
        Compress memory list using LLM.
        """
        system_prompt = MEMORY_MANAGER_SYSTEM_PROMPT_TEMPLATE.format(initial_task=self.initial_task)
        messages_for_summary = [{"role": "system", "content": system_prompt}]
        history = self._messages_for_steps(memory_list)
        if any(self._has_images(message) for message in history):
            # Let the summary model see the visual changes before discarding images.
            messages_for_summary.extend(history)
            messages_for_summary.append({"role": "user", "content": instructions})
        else:
            user_prompt = build_memory_summary_user_prompt(instructions, history)
            messages_for_summary.append({"role": "user", "content": user_prompt})
        
        tool_options = {}
        if any(message.get("tool_calls") for message in messages_for_summary):
            tool_options = {"tools": GUI_TOOL_SCHEMAS, "tool_choice": "none"}
        response = self.client.chat.completions.create(
            model=LLM_MODEL_NAME,
            messages=messages_for_summary,
            max_tokens=max_tokens,
            **tool_options,
        )
        summary = None
        try:
            summary = response.choices[0].message.content
        finally:
            self.add_model_output_log(summary, step=self._current_step, purpose="memory_compression", response=response)
        if not isinstance(summary, str) or not summary.strip():
            raise ValueError("Memory compression returned an empty summary")
        return summary

    def compress_context(self, log_callback=None):
        """
        Trigger compression using text AND image tokens, before the next request.
        """
        def log(msg):
            if log_callback:
                log_callback(msg)
            else:
                print(msg)

        context_steps = self.fixed_layer + self.long_memory_layer + self.short_memory_layer
        if self._pending_observation is not None:
            context_steps = context_steps + [self._pending_observation]
        short_tokens = self.estimate_tokens_for_steps(context_steps)
        if short_tokens <= MEMORY_SHORT_TOKEN_BUDGET or not self.short_memory_layer:
            return

        log(f"⏳ Compressing short memory ({short_tokens} estimated tokens)...")

        # Retain whole rounds so an assistant tool call is never separated from
        # its results, even when a round has retries or multiple tool calls.
        starts = []
        previous = object()
        for index, message in enumerate(self.short_memory_layer):
            round_id = message.get("_round_id", ("legacy", index // 2))
            if round_id != previous:
                starts.append(index)
                previous = round_id
        keep_rounds = max(0, MEMORY_RECENT_INTERACTIONS_TO_KEEP)
        if keep_rounds and len(starts) <= keep_rounds:
            return
        cutoff = starts[-keep_rounds] if keep_rounds else len(self.short_memory_layer)
        steps_to_compress = self.short_memory_layer[:cutoff]
        self.short_memory_layer = self.short_memory_layer[cutoff:]
        
        try:
            summary = self.compress_memory(
                steps_to_compress,
                SHORT_MEMORY_COMPRESSION_INSTRUCTIONS,
                max_tokens=None
            )
            
            # Append summary to long_memory_layer
            self.long_memory_layer.append({"role": "assistant", "content": summary})
            log(f"✅ Short memory compressed. Summary: {summary[:100]}...")
            
        except Exception as e:
            log(f"❌ Error compressing short memory: {e}")
            # If failed, maybe put back the uncompressed ones or keep them
            # Simple handling here: print error, do not lose data (put back)
            self.short_memory_layer = steps_to_compress + self.short_memory_layer
            return

        # 2. Check if Long Memory needs compression
        long_tokens = self.estimate_tokens_for_steps(self.long_memory_layer)
        if long_tokens >= MEMORY_LONG_TOKEN_BUDGET:
            log(f"⏳ Compressing long memory ({long_tokens} estimated tokens)...")
            # Compress Long Memory
            long_memories_to_compress = self.long_memory_layer
            self.long_memory_layer = []
            
            try:
                summary = self.compress_memory(
                    long_memories_to_compress,
                    LONG_MEMORY_COMPRESSION_INSTRUCTIONS,
                    max_tokens=None
                )
                self.long_memory_layer.insert(0, {"role": "assistant", "content": summary})
                log(f"✅ Long memory compressed. Summary: {summary[:100]}...")
                
            except Exception as e:
                log(f"❌ Error compressing long memory: {e}")
                self.long_memory_layer = long_memories_to_compress + self.long_memory_layer

    def _encode_image(self, image):
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')

    def get_full_context(self, query, images=None, log_callback=None, step=None):
        """
        Concatenate in order: Fixed -> Long Term -> Short Term -> query.
        Return messages list in OpenAI format.
        """
        if step is not None:
            self._current_step = step
        user_content = [{"type": "text", "text": query}]
        
        if images:
            global_img, local_img = images
            # Encode images
            global_base64 = self._encode_image(global_img)
            local_base64 = self._encode_image(local_img)
            
            user_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{global_base64}",
                    "detail": "high"
                }
            })
            user_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{local_base64}",
                    "detail": "high"
                }
            })
            
        self._pending_observation = {"role": "user", "content": user_content}
        self._prune_observation_images()
        self.compress_context(log_callback)
        # Expose only valid API message fields; internal observation metadata stays local.
        messages = (self.fixed_layer + self.long_memory_layer
                    + self._messages_for_steps(self.short_memory_layer) + [self._pending_observation])
        self._pending_round_start = len(messages) - 1
        self._pending_request_messages = messages
        return messages

if __name__ == "__main__":
    # python -m scripts.memory
    print("Testing HierarchicalMemory...")
    try:
        memory = HierarchicalMemory("System Prompt", "Initial Task")
        print("HierarchicalMemory instantiated.")

        memory.add_step("assistant", "I am thinking...")
        memory.add_step("user", "Result: Success")
        memory.add_step("assistant", "I am thinking...")
        memory.add_step("user", "Result: Success")

        context = memory.get_full_context("Next step?")
        import json
        print(json.dumps(context, indent=4))
        
    except Exception as e:
        print(f"Test failed: {e}")
