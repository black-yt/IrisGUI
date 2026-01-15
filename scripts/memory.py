from scripts.config import *
from openai import OpenAI
import base64
from io import BytesIO

class HierarchicalMemory:
    def __init__(self, system_prompt, initial_task):
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

    def add_step(self, role, content):
        """
        将新的一步加入 short_memory_layer。只记录文本步骤和执行结果。
        """
        self.short_memory_layer.append({"role": role, "content": content})
        
        # 检查是否需要压缩
        if len(self.short_memory_layer) >= MAX_SHORT_MEMORY:
            self.compress_context()

    def compress_memory(self, memory_list, prompt, max_tokens=None):
        """
        使用 LLM 压缩记忆列表。
        """
        messages_for_summary = [{"role": "system", "content": """
## Role
You are the Memory Manager for an autonomous desktop agent.

## Objective
Your task is to compress the agent's operational history into concise summaries. These summaries allow the agent to retain context over long periods without exceeding token limits.

## Guidelines
- Be objective and precise.
- Focus on **actions** (what was done) and **results** (what happened).
- Remove redundant information.
- Maintain chronological order.
"""}]
        
        # 将步骤转换为文本格式供总结
        text_content = ""
        for step in memory_list:
            if "role" in step:
                text_content += f"{step['role']}: {step['content']}\n"
            else:
                text_content += f"{step['content']}\n"
            
        messages_for_summary.append({"role": "user", "content": prompt + "\n" + text_content})
        
        response = self.client.chat.completions.create(
            model=LLM_MODEL_NAME,
            messages=messages_for_summary,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content

    def compress_context(self):
        """
        当 short_memory_layer 长度达到上限时触发压缩。
        """
        # 1. 压缩 Short Memory -> Long Memory
        # 取出最早的 COMPRESSION_RATIO 步
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
            
            # 将总结追加到 long_memory_layer
            self.long_memory_layer.append({"role": "system", "content": f"History Summary: {summary}"})
            
        except Exception as e:
            print(f"Error compressing short memory: {e}")
            # 如果失败，可能需要把未压缩的放回去或者保留
            # 这里简单处理：打印错误，不丢失数据（放回）
            self.short_memory_layer = steps_to_compress + self.short_memory_layer
            return

        # 2. 检查 Long Memory 是否需要压缩
        if len(self.long_memory_layer) >= MAX_LONG_MEMORY:
            # 压缩 Long Memory
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
                self.long_memory_layer.insert(0, {"role": "system", "content": f"Long Term Memory: {summary}"})
                
            except Exception as e:
                print(f"Error compressing long memory: {e}")
                self.long_memory_layer = long_memories_to_compress + self.long_memory_layer

    def _encode_image(self, image):
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')

    def get_full_context(self, query, images=None):
        """
        按顺序拼接：Fixed -> Long Term -> Short Term -> query。
        返回符合 OpenAI 格式的 messages 列表。
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
            # 编码图片
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
        print("Steps added.")
        
        context = memory.get_full_context("Next step?")
        print(f"Context retrieved. Message count: {len(context)}")
        
        # 简单的验证
        assert len(context) == 5 # 2 fixed + 2 short + 1 query
        print("Basic logic verification passed.")
        
    except Exception as e:
        print(f"Test failed: {e}")
