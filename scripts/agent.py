import re
import json
import time
from json_repair import repair_json
from openai import OpenAI
from scripts.config import *
from scripts.memory import HierarchicalMemory
from scripts.tools import VisionPerceptor, ActionExecutor


class IrisAgent:
    def __init__(self, task_description):
        self.system_prompt = """
You are Iris, an intelligent computer desktop automation assistant.
Your goal is to help the user complete tasks by controlling the mouse and keyboard.

**Core Logic**: ReAct (Reasoning + Acting)
1. **Observe**: You will receive two images:
    - **Global View**: A screenshot of the entire screen with a grid overlay and coordinates. Use this to locate elements roughly.
    - **Local View**: A cropped image around the current mouse position. Use this to confirm details and precise positioning.
2. **Reason**: Analyze the images and the current task status. Describe what you see, what you have done, and what you plan to do next.
    - **Verify**: Before clicking, ensure the mouse (shown in Local View) is accurately positioned over the target. If not, use 'move' to adjust.
3. **Act**: Output a JSON action block to execute a command.

**Output Format**:
You must output your reasoning first, followed by an action block.
Reasoning...
<action>
{
  "type": "action_type",
  "param1": "value1",
  ...
}
</action>

**Supported Actions**:
- Mouse:
  - `move(x, y, duration=0.5)`: Move mouse to (x, y).
  - `click(button="left", repeat=1)`: Click at current position.
  - `double_click()`: Double click at current position.
  - `drag(to_x, to_y, from_x=None, from_y=None, duration=1.0)`: Drag from current (or from_x, from_y) to (to_x, to_y).
  - `hover(duration=1.0)`: Hover at current position.
  - `scroll(direction="up"|"down"|"left"|"right", amount="line"|"half"|"page")`: Scroll.
- Keyboard:
  - `type(text, submit=False)`: Type text.
  - `hotkey(keys=["ctrl", "c"])`: Press key combination.
- System:
  - `wait(seconds)`: Wait for a duration.

**Important**:
- Always check the Global View for coordinates.
- Always check the Local View to verify if the mouse is on the correct element before clicking.
- If the mouse is not on the target in Local View, you MUST `move` first.
- Output ONLY ONE action per step.
"""
        self.memory = HierarchicalMemory(self.system_prompt, task_description)
        self.vision = VisionPerceptor()
        self.executor = ActionExecutor()
        self.client = OpenAI(
            api_key=LLM_API_KEY,
            base_url=LLM_API_ENDPOINT
        )
        self.step_count = 0

    def step(self):
        if self.step_count >= MAX_STEPS:
            return "Max steps reached. Stopping."

        self.step_count += 1
        print(f"\n--- Step {self.step_count} ---")

        # 1. 感知
        global_image, local_image = self.vision.capture_state()
        
        # 2. 构建 Context
        # Query 可以是简单的提示，或者包含上一步的执行结果（如果有的话，但这里我们在 memory.add_step 中处理了）
        # 实际上，我们需要把上一步的执行结果作为 User message 的一部分，或者 System message
        # 在 memory.get_full_context 中，我们传入 query，这个 query 会作为新的 User message
        # 我们可以在这里传入 "Please observe the screen and take the next action."
        query = "Please observe the current screen state (Global + Local views) and decide the next action."
        messages = self.memory.get_full_context(query, images=(global_image, local_image))

        # 3. 推理 (Stream)
        print("Thinking...")
        full_response = ""
        action_block = None
        
        try:
            stream = self.client.chat.completions.create(
                model=LLM_MODEL_NAME,
                messages=messages,
                stream=True,
                max_tokens=1000 # 防止输出过长
            )
            
            for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    print(content, end="", flush=True)
                    full_response += content
                    
                    # 4. 流式解析 (Parser) & 中断机制
                    # 检查是否包含完整的 <action>...</action>
                    match = re.search(r'<action>(.*?)</action>', full_response, re.DOTALL)
                    if match:
                        action_block = match.group(1)
                        # 中断流
                        stream.close() 
                        break
            
            print() # 换行

        except Exception as e:
            print(f"Error during LLM inference: {e}")
            return f"Error: {e}"

        # 5. Action 解析与修复
        feedback = ""
        if action_block:
            try:
                # 尝试修复和解析 JSON
                action_json_str = repair_json(action_block)
                action_dict = json.loads(action_json_str)
                
                print(f"Executing Action: {action_dict}")
                
                # 6. 执行
                feedback = self.executor.execute(action_dict)
                print(f"Feedback: {feedback}")
                
            except Exception as e:
                feedback = f"Error parsing or executing action: {e}. Raw block: {action_block}"
                print(feedback)
        else:
            feedback = "Error: No valid <action> block found in response."
            print(feedback)

        # 7. 记忆
        # 将 Reasoning + Action (full_response) 存入 Assistant 历史
        self.memory.add_step("assistant", full_response)
        
        # 将 执行结果 Feedback 存入 User 历史 (作为下一步的上下文)
        # 注意：这里我们把 feedback 存入 memory，下一次 get_full_context 时它会在 history 中
        # 但 get_full_context 还会添加一个新的 query。
        # 为了保持对话连贯，我们可以把 feedback 作为 user message 存入。
        self.memory.add_step("user", f"Execution Result: {feedback}")
        
        return feedback
