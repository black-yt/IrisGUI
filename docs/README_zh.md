# Iris

该项目旨在构建一个基于视觉感知、具备自我纠错能力、并能高效管理长时记忆的智能体。项目采用精简的架构设计，将功能划分为 **配置、感知与执行、记忆、推理与控制** 四个核心部分。

---

## 1. Iris 架构概览

* **核心逻辑**：ReAct(Reasoning + Acting)
* **交互模式**：观察(全局+局部)-> 思考(流式推理)-> 行动(执行并反馈)-> 记忆(压缩与更新)
* **数据协议**：输出格式为 `Reasoning + <action>JSON</action>`，支持流式中断。

## 2. 文件目录结构

```text
Iris/
├── main.py               # [入口] 程序启动、任务初始化、异常熔断
├── config.py             # [配置] 全局参数、模型密钥、视觉阈值
├── tools.py              # [躯体] 视觉感知(截图/画网格)、动作执行、系统工具
├── memory.py             # [记忆] 三层记忆管理、历史去图化、上下文压缩
├── agent.py              # [大脑] 核心循环、Prompt构建、流式解析与修复
├── debug/                # [调试] 自动存储带标记的截图和运行日志
└── requirements.txt      # [依赖] pyautogui, pillow, json_repair, openai等
```

## 3. 详细模块规范

### A. `config.py`(配置中心)

定义 Agent 的运行参数，确保所有硬编码数值集中管理。

* **模型参数**：LLM API Endpoint, API Key, Model Name(建议 gpt-5.1 等强视觉模型)。
* **视觉参数**：
    * `GRID_STEP`：100 (全局网格线的间距，单位像素)。
    * `CROP_SIZE`：500 (局部截图的宽高，单位像素)。
    * `GRID_COLOR`："red" (网格标记的颜色)。
    * `GRID_WIDTH`：1 (网格标记的线宽)。
    * `MOUSE_COLOR`："blue" (鼠标标记的颜色)。
    * `MOUSE_WIDTH`：5 (鼠标标记的线宽)。
* **运行参数**：
    * `MAX_STEPS`：100 (单次任务最大步数防止死循环)。
    * `DEBUG_MODE`：True/False (是否保存截图到本地)。
* **记忆参数**：
    * `MAX_LONG_MEMORY`：10 (最大的长记忆数量)
    * `MAX_SHORT_MEMORY`：10 (最大的短记忆数量)
    * `COMPRESSION_RATIO`：5 (每5条消息压缩为1条)

---

### B. `tools.py`(感知与执行)

该文件封装所有与操作系统交互的底层逻辑，是 Agent 与真实世界的接口。

#### **`class VisionPerceptor`(视觉感知器)**

* **`capture_state()` 方法**：
    * 调用 `pyautogui` 获取当前屏幕原始截图。
    * 获取当前鼠标 `(x, y)` 坐标。
    * **生成全局视图(Global View)**：
        * 在原图上绘制 `GRID_STEP` 间距的网格线。
        * 在交叉点标注数字坐标，如 `(100, 200)`。
        * 使用醒目颜色的箭头绘制当前鼠标位置。
    * **生成局部视图(Local View)**：
        * 以当前鼠标 `(x, y)` 为中心，裁剪出 `CROP_SIZE * CROP_SIZE` 的图像。
        * 使用醒目颜色的箭头绘制当前鼠标位置(与生成全局视图中的鼠标箭头一致)。
        * **注意**：局部图不画网格，保持原貌以便模型识别细小的 UI 元素(如按钮文字)。
    * 返回：`(global_image_obj, local_image_obj)`。

* **Debug 存档**：若开启调试模式，将两张处理后的图片保存至 `debug/` 文件夹，文件名带时间戳。

#### **`class ActionExecutor`(动作执行器)**

* **`execute(action_dict)` 方法**：接收解析后的字典，根据 `action_type` 字段分发操作。
* **支持动作**：
    * **鼠标交互 (Mouse Interactions)**：模拟人类手部操作，重点在于**平滑性**和**状态完整性**。
        * **`move` (移动)**
            * **参数**: `x` (int), `y` (int), `duration` (float, 可选, 默认 0.5)
            * **逻辑**: 移动鼠标到指定坐标。
            * **工程细节**: 使用 `pyautogui.moveTo(x, y, duration=0.5, tween=pyautogui.easeInOutQuad)`。使用 `easeInOutQuad` 模拟人手起步慢、中间快、结束慢的物理惯性。
            * **示例**: `<action>{"type": "move", "x": 500, "y": 300}</action>`
        * **`click` (点击)**
            * **参数**: `button` ("left" | "right" | "middle", 可选, 默认 "left"), `repeat` (int, 可选, 默认 1)。
            * **逻辑**: 在当前位置点击。
            * **场景**: `middle` 用于在浏览器后台打开标签页；`repeat=2` 等同于双击。
            * **示例**: `<action>{"type": "click", "button": "right"}</action>`
        * **`double_click` (双击)**
            * **参数**: 无 (默认左键)。
            * **逻辑**: 快速连续点击两次。用于打开文件或选中单词。
        * **`drag` (拖拽)**
            * **参数**: `to_x` (int), `to_y` (int): 终点坐标。`from_x` (int, 可选), `from_y` (int, 可选): 起点坐标。如不填，默认从当前鼠标位置开始。`duration` (float, 可选, 默认 1.0): 拖拽过程耗时。
            * **逻辑**: 如果指定了 `from`，先 `move` 到起点。按下鼠标左键 (`mouseDown`)。等待 0.1s (模拟人类抓取确认)。平滑移动到 `to_x, to_y` (`moveTo` with duration)。松开鼠标左键 (`mouseUp`)。
            * **场景**: 滑块验证码、移动文件、拖动窗口、在地图应用中漫游。
            * **示例**: `<action>{"type": "drag", "from_x": 100, "from_y": 100, "to_x": 400, "to_y": 100}</action>`
        * **`hover` (悬停)**
            * **参数**: `duration` (float, 可选, 默认 1.0)。
            * **逻辑**: 确保鼠标移动到目标后，**保持静止**指定时间。
            * **场景**: 触发 Tooltip 提示框、触发下拉菜单 (Drop-down Menu) 展开。如果不显式定义 Hover，Agent 可能会点击得太快导致菜单还没出来就操作结束。
        * **`scroll` (滚动)**
            * **参数**: `direction`: "up" | "down" | "left" | "right" (**新增横向滚动**)。`amount`: "line" | "half" | "page"。
            * **逻辑**: 除了垂直滚动，增加 `hscroll` 支持（Excel 表格、看板工具必备）。

    * **键盘交互 (Keyboard Interactions)**：模拟人类的打字和快捷键习惯。
        * **`type` (输入)**
            * **参数**: `text` (string): 要输入的文本。`submit` (bool, 可选, 默认 False): 输入完成后是否自动按 Enter 键。
            * **逻辑**: 模拟键盘敲击。建议字符间增加 0.05s~0.1s 的随机微延迟，防止被某些网页判定为机器人。如果 `submit` 为真，打字结束后触发 `press("enter")`。
            * **示例**: `<action>{"type": "type", "text": "Hello World", "submit": true}</action>`
        * **`hotkey` (组合键)**
            * **参数**: `keys` (list of strings)
            * **逻辑**: 接收按键列表。
            * **支持键名**: "enter", "esc", "backspace", "tab", "space", "up", "down", "left", "right", "f1"-"f12", "home", "end", "pageup", "pagedown".
            * **示例**: `<action>{"type": "hotkey", "keys": ["ctrl", "shift", "esc"]}</action>`

    * **系统/辅助** (System/Meta)
        * **`wait` (等待)**
            * **参数**: `seconds` (float)
            * **逻辑**: 阻塞执行线程。
            * **场景**: 点击“下载”后，必须等待页面跳转或文件弹出。这是 Agent 成功率的关键。

* **执行反馈**：
    * 执行成功返回字符串：`"Action move (100, 200) executed."`
    * 执行失败返回错误：`"Error：Coordinate (2000, 500) out of screen bounds."`

---

### C. `memory.py`(记忆管理)

实现分层记忆与动态维护，核心在于解决 Token 爆炸问题。

#### **`class HierarchicalMemory`(层次记忆器)**

* **初始化**：
    * `fixed_layer`：列表，包含 System Prompt 和初始 User Task。
    * `long_memory_layer`：列表，存储关键计划(Plan)或阶段性总结。
    * `short_memory_layer`：列表，存储最近的交互记录。

* **`add_step(role, content)` 方法**：
    * 将新的一步加入 `short_memory_layer`。
    * 除去记录中的图片，即指保留文本的步骤和记忆。

* **`compress_context()` 方法**：
    * 当 `short_memory_layer` 长度达到上限(MAX_SHORT_MEMORY)时触发：
        * 调用 LLM，将最早的 COMPRESSION_RATIO 步交互记录总结为一段文本(例如：“用户打开了浏览器并输入了网址”)。
        * 将总结文本追加到 `long_memory_layer`。
        * 从 `short_memory_layer` 中移除原始记录。
    * 当 `long_memory_layer` 长度达到上限(MAX_LONG_MEMORY)时触发：
        * 调用 LLM，将最早的 COMPRESSION_RATIO 条记忆总结为一条记忆(不同于short_memory_layer的压缩，long_memory_layer压缩中需要更加详细，并总结出一些必要的关键计划或阶段性总结)。
        * 用压缩后的记忆替换压缩前的记忆。

* **`get_full_context(query, images)` 方法**：
    * 按顺序拼接：Fixed -> Long Term -> Short Term -> query。
    * 返回符合 OpenAI 格式的 `messages` 列表：
        * System Prompt 的 messages role 是 system。
        * 模型的 Reasoning+Action 的 messages role 是 assistant。
        * 执行结果 Feedback 的 messages role 是 user。
        * 将 query 拼接到最后一条 message(最后一条是 user message)后面，并加上images。
    * 返回的 messages 中的 role 应该是 system prompt，user，assistant，...，user。并且只有最后的 user message 中包含图片(全局试图+局部试图)。

---

### D. `agent.py`(推理与控制)

Agent 的大脑，负责调度与逻辑流。

#### **`class IrisAgent`(核心智能体)**

* **System Prompt 设计**：
    * **明确身份**：电脑桌面自动化助手。
    * **Reasoning First**：全局图用于大概定位，局部图用于确认细节。要求模型先描述图片(因为这些 reasoning 会存入记忆，所以详细具体的图片描述很重要)。
    * **Verify**：只有当局部图中鼠标通过 "move" 准确对准了目标，才能执行 "click" 等操纵，如果不对则需要进一步调整位置。
    * **Action**：在 Reasoning 后，输出 `<action>...</action>`。

* **`step()` 主循环方法**：
    * **感知**：调用 `VisionPerceptor.capture_state()` 获取图片(包括全局试图和局部视图)。
    * **构建**：调用 `HierarchicalMemory.get_full_context()` 获取完整的 messages。
    * **推理(Stream)**：请求 LLM API，开启流式模式。
    * **流式解析(Parser)**：
        * 初始化一个 response 字符串。
        * 逐块接收新的字符串，追加到 response 后。
        * 同时检测到 `<action>` 和 `</action>` 在 response 中后，进行正则匹配 `<action>(.*?)</action>`。
        * **中断机制**：一旦匹配成功，立即断开 LLM 连接，节省时间和 Token。
    * **Action 解析与修复**：
        * 提取标签内的字符串。
        * 使用 `repair_json` 尝试解析 JSON。示例：
            ```python
            from json_repair import repair_json
            act_dict = eval(repair_json(act_str))
            ```
        * 如果解析失败，不需要执行动作，直接将错误信息作为执行结果 Feedback 并让 Agent 在下一步重试。
    * **执行**：调用 `ActionExecutor.execute()`。
    * **记忆**：将 Reasoning+Action、执行结果 Feedback 存入 Memory。

---

### E. `main.py`(入口)

负责生命周期管理。

* **GUI 界面**：运行后弹出美观但简约的用户界面，用户输入任务，点击运行。
* **主任务执行**：通过调用`step()`进行用户任务实现。
* **截图隐藏**：在截图时，该界面会隐藏。
* **实时反馈**：模型的输出会以流式实时显示。
* **紧急中断**：当用户在键盘上输入连续的3个ESC时退出程序。