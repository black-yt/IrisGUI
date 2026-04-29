import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk
import os
import queue
import re
import shutil
import sys
import unicodedata

logo = """
██╗██████╗ ██╗███████╗
██║██╔══██╗██║██╔════╝
██║██████╔╝██║███████╗
██║██╔══██╗██║╚════██║
██║██║  ██║██║███████║
╚═╝╚═╝  ╚═╝╚═╝╚══════╝
"""

ANSI_RESET = "\033[0m"
ANSI_STYLES = {
    "box": "\033[38;5;75m",
    "border": "\033[38;5;75m",
    "title": "\033[1;38;5;81m",
    "section": "\033[1;38;5;220m",
    "tool": "\033[38;5;183m",
    "success": "\033[38;5;114m",
    "error": "\033[38;5;203m",
    "muted": "\033[38;5;110m",
}
DISPLAY_BOX_WIDTH = 72

def get_display_width(text):
    """
    Calculate the display width of the string.
    Full-width (F) and Wide (W) characters count as 2.
    Other characters count as 1.
    """
    width = 0
    for char in text:
        # 'W' = Wide, 'F' = Fullwidth
        # 'A' = Ambiguous (treated as 1 here)
        if unicodedata.east_asian_width(char) in ('F', 'W'):
            width += 2
        else:
            width += 1
    return width

def _terminal_content_width(default=78):
    columns = shutil.get_terminal_size((default + 4, 24)).columns
    return max(60, min(78, columns - 4))


def _visual_ljust(text, width, measure=get_display_width):
    return text + " " * max(0, width - measure(text))


def _wrap_visual(text, width, measure=get_display_width):
    wrapped = []
    for raw_line in str(text).splitlines() or [""]:
        if not raw_line:
            wrapped.append("")
            continue

        current = ""
        current_width = 0
        for token in re.findall(r"\S+\s*|\s+", raw_line):
            token = token.lstrip() if not current else token
            token_width = measure(token)

            if current and current_width + token_width > width:
                wrapped.append(current.rstrip())
                current = ""
                current_width = 0

            if token_width <= width:
                current += token
                current_width += token_width
                continue

            for char in token:
                char_width = measure(char)
                if current and current_width + char_width > width:
                    wrapped.append(current.rstrip())
                    current = ""
                    current_width = 0
                current += char
                current_width += char_width
        wrapped.append(current.rstrip())
    return wrapped


def _border(left, right, width):
    return left + "─" * (width + 2) + right


def _box_content_line(line, width, measure=get_display_width):
    return f"│ {_visual_ljust(line, width, measure=measure)} │"


def format_box(title, lines, width=None, measure=get_display_width):
    content_width = width or _terminal_content_width()
    output = [_border("╭", "╮", content_width)]
    if title:
        output.append(_box_content_line(title, content_width, measure=measure))
        output.append(_border("├", "┤", content_width))
    for line in lines:
        for wrapped_line in _wrap_visual(line, content_width, measure=measure):
            output.append(_box_content_line(wrapped_line, content_width, measure=measure))
    output.append("╰" + "─" * (content_width + 2) + "╯")
    return "\n".join(output)


def _terminal_color_enabled(force=False):
    if force:
        return True
    if os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


def _paint(text, style):
    return f"{ANSI_STYLES[style]}{text}{ANSI_RESET}"


def _classify_output_line(line, current_section=None):
    stripped = line.strip()
    if stripped.startswith(("╭", "├", "╰")):
        return {"kind": "border", "text": line, "style": "box"}, current_section

    is_box_content = line.startswith("│ ") and line.endswith(" │")
    content = line[2:-2] if is_box_content else line
    inner = content.strip()

    style = None
    next_section = current_section
    if inner.startswith(("Iris ", "Task", "Exit", "Memory")):
        style = "title"
        next_section = None
    elif inner in {"Perception", "Model Reasoning", "Tool Calls", "Feedback", "Error"}:
        style = "section"
        next_section = inner
    elif inner:
        if "Error" in inner or inner.startswith("❌"):
            style = "error"
        elif current_section == "Feedback" or "[Task Completed]" in inner:
            style = "success"
        elif current_section == "Tool Calls":
            style = "tool"
        elif "Screen captured" in inner or "Nearby global mouse grid" in inner or "Current local mouse grid" in inner:
            style = "muted"

    return {"kind": "content" if is_box_content else "plain", "text": content, "style": style}, next_section


def styled_line_segments(line, current_section=None):
    classified, next_section = _classify_output_line(line, current_section=current_section)
    if classified["kind"] == "border":
        return [(classified["text"], "box")], next_section
    if classified["kind"] == "content":
        return [("│ ", "box"), (classified["text"], classified["style"]), (" │", "box")], next_section
    return [(classified["text"], classified["style"])], next_section


def colorize_terminal(text, force=False):
    if not _terminal_color_enabled(force=force):
        return text

    colored_lines = []
    current_section = None
    for line in str(text).splitlines():
        segments, current_section = styled_line_segments(line, current_section=current_section)
        colored_lines.append(
            "".join(_paint(segment, style) if style else segment for segment, style in segments)
        )
    return "\n".join(colored_lines)


def print_boxed(text, title="Iris"):
    print(colorize_terminal(format_box(title, str(text).strip().splitlines())), flush=True)


def _section(lines, title, body, width, measure=get_display_width):
    if len(lines) > 1:
        lines.append(_box_content_line("", width, measure=measure))
    lines.append(_box_content_line(title, width, measure=measure))
    if not body:
        body = ["  -"]
    for item in body:
        for wrapped in _wrap_visual(item, width - 2, measure=measure):
            lines.append(_box_content_line(f"  {wrapped}", width, measure=measure))


def _format_action(action):
    action_type = action.get("action_type", "unknown")
    args = {key: value for key, value in action.items() if key != "action_type"}
    if not args:
        return action_type
    rendered_args = ", ".join(f"{key}={value!r}" for key, value in args.items())
    return f"{action_type}({rendered_args})"


def format_agent_loop(
    step,
    mouse_grid_id,
    nearest_global_grid_id=None,
    reasoning="",
    tool_results=None,
    error=None,
    width=None,
    measure=get_display_width,
):
    content_width = width or _terminal_content_width()
    title = f"Iris Agent Loop · Step {step}"
    lines = [
        _border("╭", "╮", content_width),
        _box_content_line(title, content_width, measure=measure),
        _border("├", "┤", content_width),
    ]

    _section(
        lines,
        "Perception",
        [
            "Screen captured: Global View + Local View",
            f"Nearby global mouse grid: {nearest_global_grid_id or '-'}",
            f"Current local mouse grid: {mouse_grid_id}",
        ],
        content_width,
        measure=measure,
    )

    _section(
        lines,
        "Model Reasoning",
        _wrap_visual(reasoning or "No assistant text returned.", content_width - 2, measure=measure),
        content_width,
        measure=measure,
    )

    tool_body = []
    feedback_body = []
    for index, item in enumerate(tool_results or [], start=1):
        action = item.get("action", {})
        tool_body.append(f"{index}. {_format_action(action)}")
        feedback = str(item.get("feedback", "")).strip() or "-"
        feedback_body.append(f"{index}. {feedback}")

    _section(lines, "Tool Calls", tool_body or ["No tool call executed."], content_width, measure=measure)
    _section(lines, "Feedback", feedback_body or ["No feedback."], content_width, measure=measure)

    if error:
        _section(lines, "Error", [str(error)], content_width, measure=measure)

    lines.append("╰" + "─" * (content_width + 2) + "╯")
    return "\n".join(lines)


def format_status_box(title, message, width=None, measure=get_display_width):
    return format_box(title, str(message).strip().splitlines(), width=width, measure=measure)

class DisplayWindow:
    def __init__(self):
        # --- 1. Configure Appearance ---
        self.BG_COLOR = "#0f172a"
        self.TEXT_BG = "#111827"
        self.FG_COLOR = "#dbeafe"
        self.FONT_STYLE = ("Consolas", 12)
        
        # --- 2. Initialize Window ---
        self.root = tk.Tk()
        self.root.withdraw() # Hide on startup
        
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.92)
        self.root.configure(bg=self.BG_COLOR)

        text_font = tkfont.Font(font=self.FONT_STYLE)
        self.box_width = DISPLAY_BOX_WIDTH
        self.right_border_tab = text_font.measure("│ " + " " * self.box_width)

        # Window layout calculation
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        box_pixel_width = text_font.measure("│ " + " " * self.box_width + " │")
        win_width = min(screen_width - 60, max(620, box_pixel_width + 86))
        win_height = int(screen_height * 0.9)
        x = screen_width - win_width - 30
        y = (screen_height - win_height) // 2
        self.root.geometry(f"{win_width}x{win_height}+{x}+{y}")

        # --- 3. UI Components ---
        main_frame = tk.Frame(self.root, bg=self.BG_COLOR)
        main_frame.pack(fill='both', expand=True, padx=12, pady=12)

        header = tk.Label(
            main_frame,
            text="IRIS LIVE LOOP",
            bg=self.BG_COLOR,
            fg="#93c5fd",
            font=("Consolas", 12, "bold"),
            anchor="w",
        )
        header.pack(fill="x", pady=(0, 8))

        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side='right', fill='y')

        self.text_widget = tk.Text(main_frame, bg=self.TEXT_BG, fg=self.FG_COLOR,
                                   insertbackground=self.FG_COLOR,
                                   selectbackground="#334155",
                                   font=self.FONT_STYLE, bd=0, padx=10, pady=10,
                                   highlightthickness=1, highlightbackground="#334155",
                                   wrap='none', yscrollcommand=scrollbar.set)
        self.text_widget.config(tabs=(self.right_border_tab,))
        self.text_widget.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.text_widget.yview)
        self._configure_tags()

        # Configure cursor style (although not typing, keeping cursor style might look good, or just remove it)
        # Keeping cursor style here, but showing a cursor only at the end might be troublesome, simplifying by removing cursor logic
        self.text_widget.config(state='disabled') # Initially disable editing

        # State control variables
        self.auto_hide_id = None    # To store timer ID, prevent conflict
        self.auto_hide_delay = None
        self.is_suppressed = False  # Suppress window showing (e.g. during screenshot)

        # Message queue
        self.msg_queue = queue.Queue()

        # Bind ESC key to quit application completely
        self.root.bind("<Escape>", self.quit_app)
        
        # Start queue check
        self.root.after(100, self._check_queue)

    def log(self, message):
        """Thread-safe logging method"""
        self.msg_queue.put(message)

    def _configure_tags(self):
        self.text_widget.tag_configure("box", foreground="#60a5fa")
        self.text_widget.tag_configure("section", foreground="#fbbf24")
        self.text_widget.tag_configure("success", foreground="#86efac")
        self.text_widget.tag_configure("error", foreground="#fca5a5")
        self.text_widget.tag_configure("muted", foreground="#94a3b8")

    def _insert_styled(self, message):
        current_section = None
        for line in str(message).splitlines(True):
            current_section = self._insert_styled_line(line, current_section)

    def _insert_styled_line(self, line, current_section=None):
        newline = "\n" if line.endswith("\n") else ""
        body = line[:-1] if newline else line
        classified, next_section = _classify_output_line(body, current_section=current_section)

        if classified["kind"] == "content":
            inner = classified["text"].rstrip()
            content_tag = classified["style"]
            self.text_widget.insert(tk.END, "│ ", "box")
            if inner:
                if content_tag:
                    self.text_widget.insert(tk.END, inner, content_tag)
                else:
                    self.text_widget.insert(tk.END, inner)
            self.text_widget.insert(tk.END, "\t │", "box")
            if newline:
                self.text_widget.insert(tk.END, newline)
            return next_section

        tag = classified["style"]
        if tag:
            self.text_widget.insert(tk.END, classified["text"], tag)
        else:
            self.text_widget.insert(tk.END, classified["text"])
        if newline:
            self.text_widget.insert(tk.END, newline)
        return next_section

    def _check_queue(self):
        """Periodically check if there are new messages in the queue"""
        while not self.msg_queue.empty():
            msg = self.msg_queue.get()
            self.show(msg)
        self.root.after(100, self._check_queue)

    def show(self, message, auto_hide_delay=None):
        """
        Show window and append text.
        :param message: Text to append
        :param auto_hide_delay: Auto hide after milliseconds (None means no auto hide)
        """
        self.auto_hide_delay = auto_hide_delay
        
        # If there was a hide task before, cancel it first
        if self.auto_hide_id:
            self.root.after_cancel(self.auto_hide_id)
            self.auto_hide_id = None

        # Show window (only if not suppressed)
        if not self.is_suppressed:
            self.root.deiconify()
        
        # Append text
        self.text_widget.config(state='normal')
        
        # If it is a new paragraph (not immediately following the last output), maybe add a newline?
        # But the message from agent might already contain newline characters, or it is a chunk.
        # Simple logic is to append directly.
        # To avoid empty lines before the first output, check it.
        # But agent's log function usually adds \n.
        # If it is a chunk, there is no \n.
        # So just insert directly.
        
        self._insert_styled(message)
        self.text_widget.see(tk.END)
        self.text_widget.config(state='disabled')
            
        # If auto hide is set
        if self.auto_hide_delay:
            self.auto_hide_id = self.root.after(self.auto_hide_delay, self.hide_window)

    def hide_window(self):
        """Hide window"""
        self.root.withdraw()
        
    def unhide_window(self):
        """Show window"""
        self.root.deiconify()

    def safe_hide(self):
        """Thread-safe hide window"""
        self.root.after(0, self.hide_window)

    def safe_unhide(self):
        """Thread-safe show window"""
        self.root.after(0, self.unhide_window)
        
    def safe_quit(self):
        """Thread-safe quit"""
        self.root.after(0, self.quit_app)

    def set_suppressed(self, suppressed):
        """Set whether to suppress window showing"""
        self.is_suppressed = suppressed

    def clear(self):
        """Clear screen content"""
        self.text_widget.config(state='normal')
        self.text_widget.delete("1.0", tk.END)
        self.text_widget.config(state='disabled')

    def quit_app(self, event=None):
        self.root.quit()

    def start_loop(self):
        """Start main loop"""
        self.root.mainloop()

# ==========================================
# Simulate Main Program Logic
# ==========================================

if __name__ == "__main__":
    # python -m scripts.utils
    # 1. Instantiate streamer window
    ai_window = DisplayWindow()

    # --- Phase One Output ---
    def phase_one():
        print("Triggering phase one output...")
        msg = "👋 Hello! I am your AI assistant.\nI am now designed to be in resident mode.\nI will auto-hide after output is complete.\n"
        ai_window.log(msg)
        
        # Trigger phase two after 5 seconds
        ai_window.root.after(6000, phase_two)

    # --- Phase Two Output (Append) ---
    def phase_two():
        print("Triggering phase two output...")
        msg = "🔔 I'm back!\nDid you notice? These texts are appended to the previous content.\n\nI kept the context record.\n"
        ai_window.log(msg)
        
        # Trigger phase three after 8 seconds
        ai_window.root.after(8000, phase_three)

    # --- Phase Three Output (Simulate Screenshot Hide) ---
    def phase_three():
        print("Triggering phase three output (simulate screenshot)...")
        msg = "📸 Preparing screenshot, window will hide for 2 seconds...\n"
        ai_window.log(msg)
        
        # Hide after 2 seconds
        ai_window.root.after(2000, lambda: ai_window.safe_hide())
        # Restore after hiding for 2 seconds (total 4 seconds)
        ai_window.root.after(4000, lambda: ai_window.safe_unhide())
        # Append message after restore
        ai_window.root.after(4500, lambda: ai_window.log("\n✅ Screenshot complete, window restored.\n"))
        
        # Trigger phase four after 8 seconds
        ai_window.root.after(8000, phase_four)

    # --- Phase Four Output (Clear and Output) ---
    def phase_four():
        print("Triggering phase four output...")
        # Assume I want to clear screen and restart this time
        ai_window.root.after(0, ai_window.clear)
        msg = "🧹 Screen cleared.\nThis is a fresh start.\nTask all finished, press ESC to exit program.\n"
        ai_window.log(msg)

    # Start phase one
    ai_window.root.after(1000, phase_one)

    # Start GUI loop
    print("Program started, waiting for call...")
    ai_window.start_loop()
