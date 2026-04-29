from scripts.config import *
from openai import OpenAI
import base64
from io import BytesIO
import json
import os
from datetime import datetime


MEMORY_MANAGER_SYSTEM_PROMPT_TEMPLATE = """
## Role
You are the memory manager for Iris, a desktop GUI automation agent.

## Objective
Compress Iris's operational history into accurate, compact memory that can be reused in later GUI automation steps.

## What Matters
- The user's original goal.
- What Iris observed or inferred about the UI state.
- Actions Iris attempted, including important grid IDs, typed text, hotkeys, waits, clicks, and final answers.
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
        content = step.get("content", "")
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
        
        self.client = OpenAI(**openai_client_kwargs())

        # Initialize debug log path
        if DEBUG_MODE:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
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

    def _content_text_for_log(self, content):
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(str(item.get("text", "")))
            return "\n".join(part for part in text_parts if part)
        return str(content)

    def add_model_input_log(self, messages, step, images=None):
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

    def add_model_output_log(self, content, tool=None, step=0):
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
        self._append_to_log([log_step])

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
        self.add_step(
            "user",
            user_content,
            log_extra=user_log_extra,
            log_callback=log_callback,
            compress=False,
            debug_log=debug_log,
        )
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
            self.estimate_tokens_for_text(step.get("role", "")) + self.estimate_tokens_for_text(step.get("content", ""))
            for step in steps
        )

    def compress_memory(self, memory_list, instructions, max_tokens=None):
        """
        Compress memory list using LLM.
        """
        system_prompt = MEMORY_MANAGER_SYSTEM_PROMPT_TEMPLATE.format(initial_task=self.initial_task)
        messages_for_summary = [{"role": "system", "content": system_prompt}]
        user_prompt = build_memory_summary_user_prompt(instructions, memory_list)
        messages_for_summary.append({"role": "user", "content": user_prompt})
        
        response = self.client.chat.completions.create(
            model=LLM_MODEL_NAME,
            messages=messages_for_summary,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content

    def compress_context(self, log_callback=None):
        """
        Trigger compression when short_memory_layer length reaches the limit.
        """
        def log(msg):
            if log_callback:
                log_callback(msg)
            else:
                print(msg)

        short_tokens = self.estimate_tokens_for_steps(self.short_memory_layer)
        if short_tokens <= MEMORY_SHORT_TOKEN_BUDGET:
            return

        log(f"⏳ Compressing short memory ({short_tokens} estimated tokens)...")

        keep_messages = max(0, MEMORY_RECENT_INTERACTIONS_TO_KEEP * 2)
        if keep_messages and len(self.short_memory_layer) > keep_messages:
            steps_to_compress = self.short_memory_layer[:-keep_messages]
            self.short_memory_layer = self.short_memory_layer[-keep_messages:]
        elif keep_messages:
            return
        else:
            steps_to_compress = self.short_memory_layer
            self.short_memory_layer = []
        
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

    def get_full_context(self, query, images=None):
        """
        Concatenate in order: Fixed -> Long Term -> Short Term -> query.
        Return messages list in OpenAI format.
        """
        messages = []
        
        # 1. Fixed Layer
        messages.extend(self.fixed_layer)
        
        # 2. Long Term Memory
        messages.extend(self.long_memory_layer)
        
        # 3. Short Term Memory
        messages.extend(self.short_memory_layer)
        
        # 4. Query (Current Step)        
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
            
        messages.append({"role": "user", "content": user_content})
        
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
