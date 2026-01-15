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
        将新的一步加入 short_memory_layer。
        除去记录中的图片，即指保留文本的步骤和记忆。
        """
        # 如果 content 是列表（包含图片），只保留文本部分
        text_content = content
        if isinstance(content, list):
            for item in content:
                if item.get("type") == "text":
                    text_content = item.get("text")
                    break
            # 如果没有找到文本，可能需要处理，这里假设总有文本
            if isinstance(text_content, list): # 如果还是 list 说明没找到或者本来就是纯文本列表？
                 # 简单处理：如果是 list 且包含 image_url，过滤掉
                 text_content = [item for item in content if item.get("type") == "text"]
                 # 如果过滤后是列表且只有一个元素，取其内容，或者保持列表结构但只含文本
                 # 为了简单，我们假设 add_step 传入的 content 主要是为了存储历史，
                 # 而历史记录通常不需要再次发送图片给模型（为了节省 token），除非是当前步骤。
                 # 根据文档：“除去记录中的图片，即指保留文本的步骤和记忆。”
                 
                 # 如果是 OpenAI 格式的 content list
                 filtered_content = ""
                 for item in content:
                     if item.get("type") == "text":
                         filtered_content += item.get("text") + "\n"
                 text_content = filtered_content.strip()

        self.short_memory_layer.append({"role": role, "content": text_content})
        
        # 检查是否需要压缩
        if len(self.short_memory_layer) >= MAX_SHORT_MEMORY:
            self.compress_context()

    def compress_context(self):
        """
        当 short_memory_layer 长度达到上限时触发压缩。
        """
        # 1. 压缩 Short Memory -> Long Memory
        # 取出最早的 COMPRESSION_RATIO 步
        steps_to_compress = self.short_memory_layer[:COMPRESSION_RATIO]
        self.short_memory_layer = self.short_memory_layer[COMPRESSION_RATIO:]
        
        # 构建压缩请求
        summary_prompt = "请将以下交互记录总结为一段简练的文本，描述用户和助手完成了什么操作："
        messages_for_summary = [{"role": "system", "content": "你是一个助手，负责总结交互记录。"}]
        
        # 将步骤转换为文本格式供总结
        steps_text = ""
        for step in steps_to_compress:
            steps_text += f"{step['role']}: {step['content']}\n"
            
        messages_for_summary.append({"role": "user", "content": summary_prompt + "\n" + steps_text})
        
        try:
            response = self.client.chat.completions.create(
                model=LLM_MODEL_NAME,
                messages=messages_for_summary,
                max_tokens=200
            )
            summary = response.choices[0].message.content
            
            # 将总结追加到 long_memory_layer
            # 这里的 role 可以是 system 或者 assistant，或者特定的 info
            # 文档说“追加到 long_memory_layer”，我们用 system role 或者 user role 包含 context
            # 为了让模型知道这是历史总结，可以用 system role 提示
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
            
            summary_prompt = "请将以下历史记忆总结为一条关键记忆，包含必要的关键计划或阶段性总结："
            memories_text = ""
            for mem in long_memories_to_compress:
                memories_text += f"{mem['content']}\n"
                
            messages_for_summary = [{"role": "system", "content": "你是一个助手，负责总结长期记忆。"}]
            messages_for_summary.append({"role": "user", "content": summary_prompt + "\n" + memories_text})
            
            try:
                response = self.client.chat.completions.create(
                    model=LLM_MODEL_NAME,
                    messages=messages_for_summary,
                    max_tokens=300
                )
                summary = response.choices[0].message.content
                # 插入到最前面或者追加？文档说“用压缩后的记忆替换压缩前的记忆”，通常是放在较早的位置
                # 但由于我们是按时间顺序 append 的，这里应该也是 append 到 long_memory_layer 的最前面？
                # 不，long_memory_layer 代表的是时间线上的旧记忆。
                # 如果我们把最早的几条压缩成一条，这一条应该放在 long_memory_layer 的最前面（最早）。
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
        # 将 query 拼接到最后一条 message (最后一条是 user message) 后面，并加上 images。
        # 但通常 query 是新的一轮 user message。
        # 文档说：“将 query 拼接到最后一条 message(最后一条是 user message)后面”
        # 这可能意味着如果最后一条是 user，就合并？或者 query 本身就是新的 user message。
        # 考虑到 add_step 是在 step 完成后调用的，这里 query 是当前步骤的输入。
        # 所以这里应该是构造一个新的 user message。
        
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
