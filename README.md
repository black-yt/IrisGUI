<div align="center">
  <pre>
██╗██████╗ ██╗███████╗
██║██╔══██╗██║██╔════╝
██║██████╔╝██║███████╗
██║██╔══██╗██║╚════██║
██║██║  ██║██║███████║
╚═╝╚═╝  ╚═╝╚═╝╚══════╝</pre>

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-yellow.svg)](https://www.python.org/)
[![GitHub](https://img.shields.io/badge/GitHub-000000?logo=github&logoColor=white)](https://github.com/black-yt/IrisGUI)&#160;
<!-- <a href="https://arxiv.org/pdf/xxxx.xxxx" target="_blank"><img src="https://img.shields.io/badge/arXiv-b5212f.svg?logo=arxiv" height="21px"></a> -->

**A Lightweight Desktop GUI Agent via Dynamic Focus Vision and Hierarchical Memory**  

*Lightweight • Minimal Code • Minimal Dependencies 🍃*

*Visual Perception • Infinite Memory • Long Interaction 💪🏻*
</div>


## 🚀 What is Iris?

**Iris** is an intelligent agent designed to navigate your operating system just like a human does. It doesn't just blindly run scripts; it **sees** the screen, **thinks** about what to do, and **acts** with precision.

Iris is **lightweight**, with **minimal code** and **dependencies**, requiring only a **single API key**. Yet, it packs a punch with:
*   **Visual Perception** 👁️
*   **Infinite Memory** 🧠
*   **Long Interaction** 🔄

Powered by a robust **ReAct (Reasoning + Acting)** loop, Iris can handle complex workflows, recover from errors, and remember context over long periods thanks to its hierarchical memory system.

---

## 🆕 Latest News

🚩 **Update** (2026-04-30) Iris now supports native user input requests during agent loops, with the model's question shown in the floating log and a reusable multi-line terminal input panel for immediate or delayed submission.

🚩 **Update** (2026-04-29) Iris now supports OpenAI-compatible native tool calling, safe multi-tool GUI actions, a cross-platform terminal task launcher, structured loop output, traceable debug logs, and token-based memory compression.

🚩 **Update** (2026-01-18) We release **Iris-v1.0**.

---

## 🧠 Architecture

Iris operates on a cycle of **Reasoning**, **Action**, **Observation** and **Reflection**. Here's how the magic happens:

<p align="center">
  <img src="assets/architecture.png" alt="Iris Architecture" width="850">
</p>

A **dynamic focusing view** strategy is adopted to improve positioning accuracy and action efficiency.

<p align="center">
  <img src="assets/dual_views.png" alt="Dynamic Focusing View" width="850">
</p>

**Hierarchical memory** can effectively avoid context explosion and prevent task forgetting.

<p align="center">
  <img src="assets/memory.png" alt="Memory" width="400">
</p>

---

## ✨ Key Features

| Feature | Description |
| :--- | :--- |
| 🍃 **Quick Installation**   | Only need to install **a few** dependencies and configure **an** API.                               |
| 👁️ **Dynamic Focus Vision** | Uses **Global** (coarse) and **Local** (fine) views to locate elements with pixel-perfect accuracy. |
| 🧠 **Hierarchical Memory**  | Smartly compresses history into **Short-term** and **Long-term** layers. No more token overflow!    |
| 🔄 **Long Interaction**     | Complete super-long real-world tasks with **100 steps or more**.                                    |
| 🛡️ **Self-Correction**      | Verifies cursor position before clicking. If it misses, it adjusts and tries again.                 |
| 🎮 **Human-Like Control**   | Smooth mouse movements, typing, scrolling, and even drag-and-drop support.                          |
| 📺 **Live Debug Mode**      | Watch Iris think and act in real-time with a dedicated GUI dashboard.                               |

---

## 🎞️ Demos

* **Task**: `在浏览器中搜索“多模态大模型的基本原理与应用”等相关主题信息，对检索到的内容进行整理与归纳，并撰写一份结构清晰的中文Word文档（包含标题、分节与要点说明）。将该文档创建在桌面上，命名为“多模态报告.docx”。随后打开Google Translate网页，将该Word文档上传至文档翻译功能，选择中文到英文的翻译选项，等待系统生成翻译结果后下载英文版本文件，并使用Word打开检查翻译内容与格式是否正确。`

https://github.com/user-attachments/assets/ab8ca64b-2878-452f-a6ac-32f58bbb6ae7

<br>

* **Task**: `玩一局植物大战僵尸`

https://github.com/user-attachments/assets/097baadc-e01f-441c-973d-f1260656d19a

<br>

* **Task**: `Open Google Chrome and search for Shanghai's weather`

https://github.com/user-attachments/assets/067b6fb4-d242-4b4b-b4e1-696eb170c3d2

<br>

* **Task**: `Open Story.txt and write a short story of 100 words`

https://github.com/user-attachments/assets/47c928c7-5226-4d9b-b5ff-dff41d17f874

---

## ⚡ Quick Start

Ready to let Iris take the wheel? Follow these steps to get started in minutes!

### 1. Clone the Repository
```bash
git clone https://github.com/black-yt/IrisGUI.git
cd IrisGUI
```

### 2. Install Dependencies
Make sure you have Python 3.10+ installed.
```bash
pip install -r requirements.txt
```

On Linux, Iris also needs a working desktop screenshot backend. Install `gnome-screenshot` for Wayland/X11 or `scrot` for X11 if screenshots fail.

If OpenAI/httpx fails during startup with `SSL_CERT_FILE` or `CURL_CA_BUNDLE` pointing to a missing file, unset or fix that environment variable. Iris ignores missing certificate bundle paths before creating the OpenAI client.

### 3. Configure Environment
Create a `.env` file in the root directory (copy from [`.env.example`](.env.example)) and add your LLM credentials:
```ini
LLM_API_ENDPOINT="https://base-url/v1"
LLM_API_KEY="sk-your-api-key-here"
LLM_MODEL_NAME="gpt-6.1-sol"
LLM_TIMEOUT_SECONDS=300
LLM_MAX_RETRIES=1
MEMORY_SHORT_TOKEN_BUDGET=256000
MEMORY_LONG_TOKEN_BUDGET=256000
```

### 4. Run Iris
```bash
python main.py
```

The launcher configures standard input, output, and error streams as UTF-8, including
when Windows Python is invoked from WSL or its output is redirected. This allows
Chinese text, emoji, and box-drawing characters to be printed without GBK encoding errors.

The terminal editor opens in a colored framed task input panel before the task starts. Type the task directly, use **Up/Down** to choose **New Line**, **Start Now**, **Start After 5s**, **Start After Custom Delay**, **Clear**, or **Exit**, then press **Enter** to confirm the selected action. **New Line** is selected by default, so pressing **Enter** normally inserts a line break. For custom delay, enter the number of seconds in the delay field, then confirm **Start After Custom Delay**.

Iris uses native tool calling for GUI actions. It can execute multiple tool calls in one model turn only when they are safe consecutive actions that do not depend on UI loading or a fresh screenshot.

Each agent loop is shown as a color-coded structured box in both the terminal and the floating screen log, with separate sections for perception, model reasoning, tool calls, and feedback.

> **💡 Tip:** To stop Iris in an emergency, press **ESC** three times quickly! 🛑

When the floating log window has keyboard focus, a single **ESC** also exits Iris.
This window-local shortcut is separate from the global triple-ESC emergency stop.

### Log Window Display Mode

Set `LOG_WINDOW_MODE` in `.env` and restart Iris:

| Value | Behavior |
| --- | --- |
| `normal` (default) | Show the floating log on the primary screen; hide it during screenshots and GUI actions, then restore it. |
| `hidden` | Keep the floating log hidden throughout the task, including errors and task completion. Terminal logs and global triple-ESC still work. |
| `secondary` | Show the log flush against the left edge of the first non-primary monitor's usable work area, spanning from its top to just above the Windows taskbar. It stays visible during primary-screen screenshots and actions. |

For example, `LOG_WINDOW_MODE=secondary`. If no separate secondary screen is
available, or monitor/work-area detection fails, this mode reports a warning and
falls back to `normal`. Mirrored displays are treated as a single usable screen.
Secondary monitors to the left of or above the primary screen are supported.
Windows' per-monitor work area keeps taskbars on any edge clear; other platforms
use the full monitor bounds. This setting only controls the floating log; it does
not move or expand the agent's screenshot or input coordinate area to another monitor.

### Screenshot History and Debug Archives

```ini
MEMORY_IMAGE_ROUNDS=-1
MEMORY_IMAGE_TOKEN_MULTIPLIER=1.2
DEBUG_MODE=False
```

`MEMORY_IMAGE_ROUNDS` includes the current observation: `-1` (default) keeps all
uncompressed screenshot rounds, `4` sends up to eight images (current round plus
three preceding rounds), and `1` sends only the current pair. Zero and values below
`-1` are invalid. Each round's global/local pair stays in that round's original
user message, before the corresponding assistant action and execution result.
Older text remains when the image window expires. Historical local grids are for
comparison; the next action must use the newest observation's grid.

The 256000-token compression threshold now includes fixed prompts, summaries,
history text, and both current and historical images. Image tokens are estimated
from PNG dimensions using 32×32 patches times `MEMORY_IMAGE_TOKEN_MULTIPLIER`,
rounded up per image. This is a conservative estimate without server-side image
downscaling, based on the [OpenAI vision guide](https://developers.openai.com/api/docs/guides/images-vision).
It is not exact billing for every model or compatible provider; adjust the
multiplier if needed. Base64 characters are never counted as text tokens.
Compression runs before sending the next action request and retains the configured
recent interaction pairs. The summary model receives old screenshots alongside
their original text/actions before those rounds are replaced by a text summary.
If compression fails or returns an empty summary, the original history is restored.

With `DEBUG_MODE=True`, every captured global/local pair is retained in
`scripts/debug/screenshot/`, regardless of the upload window or later compression.
`scripts/debug/log/*.jsonl` records step numbers, screenshot filenames, model replies
(including repair attempts and memory summaries), tool calls, and execution results
or errors. Model output entries also include the full SDK response, preserving
tool IDs, finish reasons, usage, and any additional response fields returned by the
provider. Archives stay local and are ignored by Git. Restart Iris after changing
these settings.

### Precise Pointer Placement

The `move` tool accepts continuous grid coordinates in both views. Either index can
be a decimal, and the original integer IDs still work:

* `L-10-10.32`: column 10, row 10.32 (0.32 local grid intervals below row 10).
* `G-01.10-08`: column 1.10, row 8 (0.10 global grid intervals right of column 1).
* `L-09.75-10.25`: both indices are fractional.

Fractions refer to grid spacing, not pixel offsets. Coordinates are resolved using
the latest view's actual anchor, crop and spacing, then rounded to the nearest
screen pixel. Positions outside that view are rejected. Local coordinates must
be recalculated after each move because the Local View follows the cursor.

---

## 📬 Contact

- 💬 **GitHub Issues**: Please open an issue for bug reports or feature requests

- 📧 **Email**: [xu_wanghan@sjtu.edu.cn](https://black-yt.github.io/)

---

<!-- ## 📜 Citation

If you would like to cite our work, please use the following BibTeX.

```bib
Coming soon...
```

--- -->

## 🌟 Star History

If you find this work helpful, please consider to **star⭐** this [repo](https://github.com/black-yt/IrisGUI). Thanks for your support! 🤩

[![black-yt/IrisGUI Stargazers](https://reporoster.com/stars/black-yt/IrisGUI)](https://github.com/black-yt/IrisGUI/stargazers)

<p align="right"><a href="#top">🔝Back to top</a></p>
