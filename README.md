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

🚩 **Update** (2026-11-04) **Continuous scrolling**: The `scroll` tool now accepts decimal amounts in `0 < amount <= 100` (default `1`), allowing fine adjustments or longer continuous scrolling in a single call.

🚩 **Update** (2026-11-04) **Configurable reasoning effort**: Set `LLM_REASONING_EFFORT` through the environment, with `low` as the default, for both action requests and memory compression on compatible providers.

🚩 **Update** (2026-11-04) **Action feedback and loop reminders**: Neutral system reminders flag repeated action patterns, while interaction feedback reminds the agent to verify the actual UI result in the next screenshot.

🚩 **Update** (2026-11-03) **Continuous Global/Local coordinates**: Both grid views now accept fractional coordinates such as `L-10-10.32` and `G-01.10-08`, making small controls between grid lines easier to target.

🚩 **Update** (2026-11-03) **Multi-round screenshot history**: Historical Global/Local screenshot pairs stay in their original conversation turns. Configure `MEMORY_IMAGE_ROUNDS`: `-1` keeps all available rounds, while `4` retains up to 8 images including the current pair.

🚩 **Update** (2026-11-03) **Preserved native conversation history**: Assistant outputs, native tool calls, and matching tool results remain in the conversation. Concise per-step prompts let each ordinary turn continue the existing history without rewriting earlier text.

<details>
<summary>👉 More News (Click to expand)</summary>

🚩 **Update** (2026-11-03) **Image-aware memory compression**: Compression thresholds now account for estimated image tokens alongside text and tool messages, and retained screenshots are included when summarizing visual history.

🚩 **Update** (2026-11-03) **Complete debug artifacts**: Debug mode archives untouched screen captures alongside Global/Local views, full model responses, tool calls, and execution feedback for troubleshooting.

🚩 **Update** (2026-11-03) **Configurable log window display**: Choose `normal`, `hidden`, or `secondary` with `LOG_WINDOW_MODE`. On Windows, the secondary-screen log window fits the monitor work area above the taskbar.

🚩 **Update** (2026-11-03) **Longer-run defaults**: The default task limit is now 500 steps, the LLM timeout is 300 seconds, and short- and long-term memory budgets are each 256,000 estimated tokens.

🚩 **Update** (2026-11-03) **UTF-8 terminal output**: Chinese text, emoji, and structured console output now work across Windows terminals, WSL-launched Windows Python, and redirected output without GBK encoding failures.

🚩 **Update** (2026-11-03) **Updated default model**: The default model is now `gpt-6.1-sol`, configurable through `LLM_MODEL_NAME`.

🚩 **Update** (2026-04-30) Iris now supports native user input requests during agent loops, with the model's question shown in the floating log and a reusable multi-line terminal input panel for immediate or delayed submission.

🚩 **Update** (2026-04-29) Iris now supports OpenAI-compatible native tool calling, safe multi-tool GUI actions, a cross-platform terminal task launcher, structured loop output, traceable debug logs, and token-based memory compression.

🚩 **Update** (2026-01-18) We release **Iris-v1.0**.

</details>

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
LLM_REASONING_EFFORT=low
MEMORY_SHORT_TOKEN_BUDGET=256000
MEMORY_LONG_TOKEN_BUDGET=256000
```

`LLM_REASONING_EFFORT=low` is the default. It is sent as the Chat Completions API's
`reasoning_effort` parameter for action requests, tool-repair retries, and short/long
memory compression; it is not added to the prompt or passed to the client constructor.
Use `low`, `medium`, `high`, `xhigh`, or `max` for
[GPT-6.1 Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol).
`none` and `minimal` are also accepted by the configuration for other models that
support them. Supported values depend on the model and compatible API provider.
Set `LLM_REASONING_EFFORT=omit` to leave the parameter out and use the server default;
this does not disable thinking. Blank values use `low`. Invalid values fail at
startup, and rejected parameters are not silently retried without the setting.
Restart Iris after changing it; the value stays consistent throughout a run.

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

Set `LOG_WINDOW_MODE` in `.env`:

| Value | Behavior |
| --- | --- |
| `normal` (default) | Show on the primary screen; hide during screenshots and GUI actions. |
| `hidden` | Hide the floating log. Terminal logs and triple-ESC still work. |
| `secondary` | Stay visible at the first secondary monitor's left edge, filling its usable height above the taskbar. |

`secondary` falls back to `normal` if no usable second monitor is available.
Screenshots and GUI actions remain on the primary screen. Restart Iris after changing the setting.

### Screenshot History and Debug Archives

Each round appends observations, original model replies, and native tool results to
history. Retained global/local screenshot pairs stay in their original rounds.

| Setting | Default | Purpose |
| --- | --- | --- |
| `MEMORY_IMAGE_ROUNDS` | `-1` | Keep all uncompressed screenshot rounds. `4` keeps the current round plus three earlier rounds (up to eight images); `1` keeps only the current pair. |
| `MEMORY_IMAGE_TOKEN_MULTIPLIER` | `1.2` | Adjust image-token estimates used for memory compression. |
| `DEBUG_MODE` | `False` | Save raw and annotated screenshots, model responses, and tool execution logs locally. |

Use `-1` or a positive integer for the image window; older text remains when images
expire. Compression defaults to **256000 estimated tokens**, including text,
images, and tool calls. The summary model receives old screenshots, and tool calls
stay grouped with their results.

Debug files are saved under `scripts/debug/screenshot/` and `scripts/debug/log/`.
They include untouched `screenshot_*.png` captures, global/local pairs, and JSONL
logs with full model responses, tool calls, results, and errors. Archives are
unaffected by the upload window or compression and are ignored by Git. Restart
Iris after changing these settings.

### Precise Pointer Placement

`move` accepts integer or fractional grid IDs in both views, such as
`L-10-10.32` and `G-01.10-08`. Fractions refer to grid intervals, not pixels.
Use the newest screenshot's grid; local coordinates change after each move because
the Local View follows the cursor. Out-of-view positions are rejected.

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

<p align="right"><a href="#top">🔝Back to top</a></p>
