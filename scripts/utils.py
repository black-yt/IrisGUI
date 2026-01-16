import tkinter as tk
from tkinter import ttk
import queue

logo = """
██╗██████╗ ██╗███████╗
██║██╔══██╗██║██╔════╝
██║██████╔╝██║███████╗
██║██╔══██╗██║╚════██║
██║██║  ██║██║███████║
╚═╝╚═╝  ╚═╝╚═╝╚══════╝
"""

def print_boxed(text):
    lines = text.strip().split('\n')
    max_len = max(len(line) for line in lines)
    print("╭" + "─" * (max_len + 2) + "╮")
    for line in lines:
        print(f"│ {line.ljust(max_len)} │")
    print("╰" + "─" * (max_len + 2) + "╯")

class DisplayWindow:
    def __init__(self):
        # --- 1. Configure Appearance ---
        self.BG_COLOR = "#FFFACD"    # Light yellow
        self.TEXT_BG = "#FFFACD"
        self.FG_COLOR = "#000000"    # Black text
        self.CURSOR_COLOR = "#000000"
        self.FONT_STYLE = ("Arial", 12)
        
        # --- 2. Initialize Window ---
        self.root = tk.Tk()
        self.root.withdraw() # Hide on startup
        
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.8)
        self.root.configure(bg=self.BG_COLOR)

        # Window layout calculation
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        win_width = 600
        win_height = int(screen_height * 0.9)
        x = screen_width - win_width - 30
        y = (screen_height - win_height) // 2
        self.root.geometry(f"{win_width}x{win_height}+{x}+{y}")

        # --- 3. UI Components ---
        main_frame = tk.Frame(self.root, bg=self.BG_COLOR)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side='right', fill='y')

        self.text_widget = tk.Text(main_frame, bg=self.TEXT_BG, fg=self.FG_COLOR, 
                                   font=self.FONT_STYLE, bd=0, highlightthickness=0,
                                   wrap='word', yscrollcommand=scrollbar.set)
        self.text_widget.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.text_widget.yview)

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
        
        self.text_widget.insert(tk.END, message)
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
