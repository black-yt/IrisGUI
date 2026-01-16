from scripts.config import *
from openai import OpenAI
import base64
from io import BytesIO
import json
import os
from datetime import datetime

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
        
        self.client = OpenAI(
            api_key=LLM_API_KEY,
            base_url=LLM_API_ENDPOINT
        )

        # Initialize debug log path
        if DEBUG_MODE:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_dir = os.path.join(os.path.dirname(__file__), "debug", "log")
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            self.debug_save_path = os.path.join(log_dir, f"{timestamp}.jsonl")
            
            # Save fixed layer immediately
            self._append_to_log(self.fixed_layer)

    def _append_to_log(self, steps: list[dict]):
        """Helper to append steps to the JSONL log file"""
        try:
            with open(self.debug_save_path, 'a', encoding='utf-8') as f:
                for step in steps:
                    f.write(json.dumps(step, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"Failed to write to debug log: {e}")

    def add_step(self, role, content, log_callback=None):
        """
        Add a new step to short_memory_layer. Only record text steps and execution results.
        """
        step = {"role": role, "content": content}
        self.short_memory_layer.append(step)
        
        # Append to debug log
        if DEBUG_MODE:
            self._append_to_log([step])
        
        # Check if compression is needed
        if len(self.short_memory_layer) >= MAX_SHORT_MEMORY:
            self.compress_context(log_callback)

    def compress_memory(self, memory_list, prompt, max_tokens=None):
        """
        Compress memory list using LLM.
        """
        system_prompt = f"""
## Role
You are the Memory Manager for an autonomous desktop agent.

## Objective
Your task is to compress the agent's operational history into concise summaries. These summaries allow the agent to retain context over long periods without exceeding token limits.

## Guidelines
- Be objective and precise.
- Focus on **actions** (what was done) and **results** (what happened).
- Remove redundant information.
- Maintain chronological order.
                                 
## Background
These conversation logs (which you need to summarize) were recorded during the process of addressing the following user request. 

```text
{self.initial_task}
```

Note that you are not tasked with answering or completing the user request above. Your role is a Memory Manager.
"""
        messages_for_summary = [{"role": "system", "content": system_prompt}]
        
        # Convert steps to text format for summary
        prompt = "\n\n## History\n"
        for step in memory_list:
            prompt += f"{step['role']}: {step['content']}\n\n"
            
        messages_for_summary.append({"role": "user", "content": prompt})
        
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

        log("⏳ Compressing short memory...")

        # 1. Compress Short Memory -> Long Memory
        # Take out the earliest COMPRESSION_RATIO steps
        steps_to_compress = self.short_memory_layer[:COMPRESSION_RATIO]
        self.short_memory_layer = self.short_memory_layer[COMPRESSION_RATIO:]
        
        try:
            summary = self.compress_memory(
                steps_to_compress,
                """
## Instructions
Summarize the provided interaction logs into a brief paragraph.
- Identify the specific actions taken by the agent (e.g., clicking buttons, typing text).
- Note the system's feedback or state changes.
- Format as: "The agent [action] resulting in [outcome]."
""",
                max_tokens=None
            )
            
            # Append summary to long_memory_layer
            self.long_memory_layer.append({"role": "assistant", "content": f"History Summary: {summary}"})
            log(f"✅ Short memory compressed. Summary: {summary[:100]}...")
            
        except Exception as e:
            log(f"❌ Error compressing short memory: {e}")
            # If failed, maybe put back the uncompressed ones or keep them
            # Simple handling here: print error, do not lose data (put back)
            self.short_memory_layer = steps_to_compress + self.short_memory_layer
            return

        # 2. Check if Long Memory needs compression
        if len(self.long_memory_layer) >= MAX_LONG_MEMORY:
            log("⏳ Compressing long memory...")
            # Compress Long Memory
            long_memories_to_compress = self.long_memory_layer[:COMPRESSION_RATIO]
            self.long_memory_layer = self.long_memory_layer[COMPRESSION_RATIO:]
            
            try:
                summary = self.compress_memory(
                    long_memories_to_compress,
                    """
## Instructions
Consolidate the following historical summaries into a single high-level overview.
- Focus on completed sub-tasks and major milestones.
- Preserve any ongoing goals or pending errors that need resolution.
- Discard transient details that are no longer relevant to the current state.
""",
                    max_tokens=None
                )
                self.long_memory_layer.insert(0, {"role": "assistant", "content": f"Long Term Memory: {summary}"})
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
    MAX_LONG_MEMORY = 2
    MAX_SHORT_MEMORY = 2
    COMPRESSION_RATIO = 2
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