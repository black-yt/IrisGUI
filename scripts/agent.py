import re
import json
from json_repair import repair_json
from openai import OpenAI
from scripts.config import *
from scripts.memory import HierarchicalMemory
from scripts.tools import VisionPerceptor, ActionExecutor


class IrisAgent:
    def __init__(self, task_description):
        self.system_prompt = """
## Role
You are Iris, an advanced AI desktop automation assistant designed to autonomously complete complex tasks on a computer. You act as the user's hands and eyes, navigating the operating system and applications with precision and intelligence.

## Objective
Your primary goal is to fulfill the user's request by executing a sequence of mouse and keyboard actions. You operate in a ReAct (Reasoning + Acting) loop, continuously observing the screen, reasoning about the current state, and executing the next logical step.

## Capabilities
1.  **Visual Perception**: You receive two visual inputs at each step:
    -   **Global View**: A screenshot of the entire screen with a grid overlay and coordinate system. Use this to identify the general location of UI elements.
    -   **Local View**: A high-resolution cropped image centered around the current mouse cursor position. Use this to verify precise alignment before clicking or interacting.
2.  **Action Execution**: You can perform a wide range of mouse and keyboard operations, including moving, clicking, dragging, scrolling, typing, and using hotkeys.

## Instructions
1.  **Observe**: Carefully analyze the Global View to locate target elements. Then, examine the Local View to confirm if the mouse cursor is correctly positioned over the intended target.
2.  **Reason**:
    -   Analyze the current state relative to the user's goal.
    -   Verify cursor position using the Local View. If the cursor is not exactly over the target, you MUST issue a `move` action first.
    -   Formulate a plan for the immediate next step.
    -   Explicitly state your reasoning process before generating the action block.
3.  **Act**: Output a single JSON action block representing the next operation.

## Action Specifications
You must output your response in the following format:
Reasoning...
<action>
{
  "type": "action_type",
  "param": "value"
}
</action>

### Supported Actions & Examples

#### 1. Mouse Operations
*   **move**: Move the cursor to specific coordinates.
    *   *Params*: `x` (integer), `y` (integer), `duration` (float, optional, default=0.5)
    *   *Example*: Move to coordinates (500, 300).
        ```json
        {"type": "move", "x": 500, "y": 300}
        ```
*   **click**: Click the mouse button.
    *   *Params*: `button` ("left"|"right"|"middle", default="left"), `repeat` (integer, default=1)
    *   *Example*: Double-click the left button.
        ```json
        {"type": "click", "button": "left", "repeat": 2}
        ```
*   **double_click**: specific action for double clicking (alternative to click with repeat=2).
    *   *Example*:
        ```json
        {"type": "double_click"}
        ```
*   **drag**: Drag the mouse from one point to another.
    *   *Params*: `to_x` (int), `to_y` (int), `from_x` (int, optional), `from_y` (int, optional), `duration` (float, default=1.0)
    *   *Example*: Drag from current position to (800, 600).
        ```json
        {"type": "drag", "to_x": 800, "to_y": 600}
        ```
*   **hover**: Hover over the current position for a set time (useful for triggering tooltips).
    *   *Params*: `duration` (float, default=1.0)
    *   *Example*:
        ```json
        {"type": "hover", "duration": 2.0}
        ```
*   **scroll**: Scroll the mouse wheel.
    *   *Params*: `direction` ("up"|"down"|"left"|"right"), `amount` ("line"|"half"|"page" or integer clicks)
    *   *Example*: Scroll down by one page.
        ```json
        {"type": "scroll", "direction": "down", "amount": "page"}
        ```

#### 2. Keyboard Operations
*   **type**: Type a string of text.
    *   *Params*: `text` (string), `submit` (boolean, default=False - if true, presses Enter after typing)
    *   *Example*: Type "Hello World" and press Enter.
        ```json
        {"type": "type", "text": "Hello World", "submit": true}
        ```
*   **hotkey**: Press a combination of keys.
    *   *Params*: `keys` (list of strings)
    *   *Example*: Copy (Ctrl+C).
        ```json
        {"type": "hotkey", "keys": ["ctrl", "c"]}
        ```

#### 3. System Operations
*   **wait**: Wait for a specified duration (useful for letting UI animations finish).
    *   *Params*: `seconds` (float)
    *   *Example*: Wait for 2.5 seconds.
        ```json
        {"type": "wait", "seconds": 2.5}
        ```

## Constraints & Best Practices
-   **One Action Per Step**: You may only output ONE action block per response.
-   **Precision Matters**: Always prioritize accuracy. If you are unsure about the cursor position, use a `move` action to reset or correct it.
-   **Visual Verification**: Never assume the cursor is in the right place without checking the Local View.
-   **Coordinate System**: Coordinates are absolute (x, y) based on the Global View resolution.
"""
        self.memory = HierarchicalMemory(self.system_prompt, task_description)
        self.vision = VisionPerceptor()
        self.executor = ActionExecutor()
        self.client = OpenAI(
            api_key=LLM_API_KEY,
            base_url=LLM_API_ENDPOINT
        )
        self.step_count = 0

    def step(self, pre_capture_callback=None, post_capture_callback=None):
        if self.step_count >= MAX_STEPS:
            return "Max steps reached. Stopping."

        self.step_count += 1
        print(f"\n--- Step {self.step_count} ---")

        # 1. 感知
        if pre_capture_callback:
            pre_capture_callback()
            
        global_image, local_image = self.vision.capture_state()
        
        if post_capture_callback:
            post_capture_callback()
        
        # 2. 构建 Context
        query = """## Current Step
1. Analyze the Global View to understand the overall screen layout.
2. Analyze the Local View to verify the precise mouse position.
3. Based on the task history and current visual state, determine the next action.
"""
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
        self.memory.add_step("assistant", full_response)
        self.memory.add_step("user", f"Execution Result: {feedback}")
        
        return feedback

if __name__ == "__main__":
    print("Testing IrisAgent...")
    try:
        # 简单的实例化测试
        agent = IrisAgent("Test Task")
        print("IrisAgent instantiated successfully.")
        print("Note: To run a full step, valid API keys and environment are required.")
    except Exception as e:
        print(f"Failed to instantiate IrisAgent: {e}")
