import re
import json
from json_repair import repair_json
from openai import OpenAI
from scripts.config import *
from scripts.memory import HierarchicalMemory
from scripts.tools import VisionPerceptor, ActionExecutor


class IrisAgent:
    def __init__(self, task_description, pre_callback=None, post_callback=None):
        self.system_prompt = """
## Role
You are Iris, an advanced AI desktop automation assistant designed to autonomously complete complex tasks on a computer. You act as the user's hands and eyes, navigating the operating system and applications with precision and intelligence.

## Objective
Your primary goal is to fulfill the user's request by executing a sequence of mouse and keyboard actions. You operate in a ReAct (Reasoning + Acting) loop, continuously observing the screen, reasoning about the current state, and executing the next logical step.

## Capabilities
1.  **Visual Perception**: You receive two visual inputs at each step. Both images are padded with a white border containing grid labels (00, 01, ...) to help you identify grid points.
    -   **Global View**: A screenshot of the entire screen with a **Coarse Grid**. Grid points are identified by IDs in the format `G-xx-yy` (e.g., `G-05-03` corresponds to column 05, row 03).
    -   **Local View**: A high-resolution cropped image centered around the current mouse cursor position with a **Fine Grid**. Grid points are identified by IDs in the format `L-xx-yy` (e.g., `L-02-04`).
2.  **Action Execution**: You can perform a wide range of mouse and keyboard operations. **Crucially, movement actions use Grid IDs, not raw coordinates.**

## Instructions
1.  **Observe**: Carefully analyze the Global View to locate target elements. Then, examine the Local View to confirm if the intended target is at the center (since the Local View is centered on the mouse cursor).
2.  **Reason**:
    -   Analyze the current state relative to the user's goal.
    -   **Localization Strategy**: You must strictly follow one of these three cases for positioning:
        1.  **Global Approach**: If the target is visible in the Global View but NOT in the Local View, identify the nearest grid intersection point `G-xx-yy` to the target. Use the `move` action with this ID.
        2.  **Local Approach**: If the target is visible in the Local View but not at the center, **you MUST use the Fine Grid IDs (`L-xx-yy`) to make precise adjustments.** Do NOT use Global Grid IDs (`G-xx-yy`) in this case, as they are too coarse. Identify the nearest fine grid intersection point `L-xx-yy` to the target and use the `move` action with this ID.
        3.  **Target Aligned**: The target must be at the **CENTER** of the Local View. **Crucially, the crosshair center MUST significantly overlap with the target's clickable area (e.g., the icon itself, not just the label).** If the target is perfectly centered and overlapped, proceed with the interaction (click, type, etc.).
    -   **Grid Navigation**:
        -   Read the numbers on the top/bottom white border for the X-axis (column) index.
        -   Read the numbers on the left/right white border for the Y-axis (row) index.
        -   Combine them to form the ID: `PREFIX-Column-Row` (e.g., `G-05-03`).
    -   Formulate a plan for the immediate next step.
    -   Explicitly state your reasoning process before generating the action block.
3.  **Act**: Output a single JSON action block representing the next operation.

## Action Specifications
You must output your response in the following format:
Reasoning...
<action>
{
  "action_type": "action_name",
  "param": "value"
}
</action>

### Supported Actions & Examples

#### 1. Mouse Operations
*   **move**: Move the cursor to a specific grid point.
    *   *Params*: `point_id` (string), `duration` (float, optional, default=0.5)
    *   *Example*: Move to Global grid point column 05, row 03.
        <action>
        {"action_type": "move", "point_id": "G-05-03"}
        </action>
    *   *Example*: Move to Local grid point column 02, row 04.
        <action>
        {"action_type": "move", "point_id": "L-02-04"}
        </action>
*   **click**: Click the mouse button.
    *   *Params*: `button` ("left"|"right"|"middle", default="left"), `repeat` (integer, default=1)
    *   *Example*: Double-click the left button.
        <action>
        {"action_type": "click", "button": "left", "repeat": 2}
        </action>
*   **double_click**: specific action for double clicking (alternative to click with repeat=2). **Note: Opening desktop applications on Windows usually requires a double-click.**
    *   *Example*:
        <action>
        {"action_type": "double_click"}
        </action>
*   **mouse_down**: Press and hold a mouse button.
    *   *Params*: `button` ("left"|"right"|"middle", default="left")
    *   *Example*: Hold left button.
        <action>
        {"action_type": "mouse_down", "button": "left"}
        </action>
*   **mouse_up**: Release a mouse button.
    *   *Params*: `button` ("left"|"right"|"middle", default="left")
    *   *Example*: Release left button.
        <action>
        {"action_type": "mouse_up", "button": "left"}
        </action>
*   **scroll**: Scroll the mouse wheel.
    *   *Params*: `direction` ("up"|"down"|"left"|"right"), `amount` ("line"|"half"|"page" or integer clicks)
    *   *Example*: Scroll down by one page.
        <action>
        {"action_type": "scroll", "direction": "down", "amount": "page"}
        </action>

**Complex Interactions**:
*   **Dragging**: To perform a drag operation, decompose it into steps:
    1.  `move` to the start position.
    2.  `mouse_down` to hold the element.
    3.  `move` to the destination (can be multiple moves if the path is long).
    4.  `mouse_up` to release.
*   **Hovering**: To hover, simply `move` to the target and then `wait`.

#### 2. Keyboard Operations
*   **type**: Type a string of text.
    *   *Params*: `text` (string), `submit` (boolean, default=False - if true, presses Enter after typing)
    *   *Example*: Type "Hello World" and press Enter.
        <action>
        {"action_type": "type", "text": "Hello World", "submit": true}
        </action>
*   **hotkey**: Press a combination of keys.
    *   *Params*: `keys` (list of strings)
    *   *Example*: Copy (Ctrl+C).
        <action>
        {"action_type": "hotkey", "keys": ["ctrl", "c"]}
        </action>

#### 3. System Operations
*   **wait**: Wait for a specified duration (useful for letting UI animations finish).
    *   *Params*: `seconds` (float)
    *   *Example*: Wait for 2.5 seconds.
        <action>
        {"action_type": "wait", "seconds": 2.5}
        </action>
*   **final_answer**: Indicates that the task is fully completed and outputs the complete result.
    *   *Params*: `text` (string)
    *   *Example*: Task completed successfully.
        <action>
        {"action_type": "final_answer", "text": "Task completed successfully."}
        </action>

## Constraints & Best Practices
-   **One Action Per Step**: You may only output ONE action block per response.
-   **Precision Matters**: Always prioritize accuracy. If you are unsure about the cursor position, use a `move` action to reset or correct it. **Ensure the crosshair is directly ON the target before clicking.**
-   **Visual Verification**: Never assume the cursor is in the right place without checking the Local View.
-   **Coordinate System**: DO NOT calculate or output raw (x, y) coordinates. ALWAYS use the Grid IDs (`G-xx-yy` or `L-xx-yy`) provided in the visual input.
"""
        self.memory = HierarchicalMemory(self.system_prompt, task_description)
        self.vision = VisionPerceptor(pre_callback, post_callback)
        self.executor = ActionExecutor(pre_callback, post_callback)
        self.client = OpenAI(
            api_key=LLM_API_KEY,
            base_url=LLM_API_ENDPOINT
        )
        self.step_count = 0

    def step(self, log_callback=None):
        if self.step_count >= MAX_STEPS:
            return "🛑 [Max Steps Reached]. Stopping."

        self.step_count += 1
        
        def log(text, end="\n"):
            full_text = text + end
            print(text, end=end, flush=True)
            if log_callback:
                log_callback(full_text)

        log(f"\n➖➖➖➖➖➖➖➖➖➖ Step {self.step_count} ➖➖➖➖➖➖➖➖➖➖")

        # 1. 感知
        log("👀 Capturing screen...")
        # Updated to unpack coordinate_map
        global_image, local_image, coordinate_map = self.vision.capture_state()
        
        # 2. 构建 Context
        query = f"""## Current Step
1. Analyze the Global View to understand the overall screen layout.
2. Analyze the Local View to verify the precise mouse position (marked with a crosshair). **Note: This view reflects the state AFTER the previous action. The crosshair marks where the mouse is CURRENTLY located.**
3. Based on the task history and current visual state, determine the next action.
"""
        log(f"❓ Query: {query}")
        messages = self.memory.get_full_context(query, images=(global_image, local_image))

        # 3. 推理 (Stream)
        log("🧠 Thinking...")
        full_response = ""
        action_block = None
        
        try:
            stream = self.client.chat.completions.create(
                model=LLM_MODEL_NAME,
                messages=messages,
                stream=True,
                max_tokens=None
            )
            
            for chunk in stream:
                if not chunk.choices:
                    continue
                content = chunk.choices[0].delta.content
                if content:
                    print(content, end="", flush=True)
                    if log_callback:
                        log_callback(content)
                    full_response += content
                    
                    # 4. 流式解析 (Parser) & 中断机制
                    # 检查是否包含完整的 <action>...</action>
                    match = re.search(r'<action>(.*?)</action>', full_response, re.DOTALL)
                    if match:
                        action_block = match.group(1)
                        # 中断流
                        stream.close() 
                        break
            
            log("", end="\n") # 换行

        except Exception as e:
            log(f"❌ Error during LLM inference: {e}")
            return f"Error: {e}"

        # 5. Action 解析与修复
        feedback = ""
        if action_block:
            try:
                # 尝试修复和解析 JSON
                action_json_str = repair_json(action_block)
                action_dict = json.loads(action_json_str)
                
                log(f"⚡ Executing Action: {action_dict}")
                
                # 6. 执行
                # Pass coordinate_map to executor
                feedback = self.executor.execute(action_dict, coordinate_map)
                log(f"✅ Feedback: {feedback}")
                
            except Exception as e:
                feedback = f"Error parsing or executing action: {e}. Raw block: {action_block}"
                log(f"❌ {feedback}")
        else:
            feedback = "Error: No valid <action> block found in response."
            log(f"❌ {feedback}")

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
