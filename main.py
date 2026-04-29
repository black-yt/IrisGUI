import threading
import time
import os
import sys
from pynput import keyboard
from scripts.agent import IrisAgent
from scripts.terminal_input import prompt_for_task
from scripts.utils import DISPLAY_BOX_WIDTH, DisplayWindow, colorize_terminal, format_status_box, print_boxed, logo


class IrisController:
    def __init__(self, task):
        self.task = task
        self.window = DisplayWindow()
        self.running = False
        self.esc_count = 0
        self.last_esc_time = 0

        # Listen for ESC key (global listener, ensures response even if window is hidden)
        self.listener = keyboard.Listener(on_press=self.on_key_press)
        self.listener.start()
        
        # Automatically start task
        self.window.root.after(100, self.start_agent_thread)

    def log(self, message):
        self.window.log(message)

    def on_key_press(self, key):
        if key == keyboard.Key.esc:
            current_time = time.time()
            if current_time - self.last_esc_time < 1.0: # Consecutive press within 1 second
                self.esc_count += 1
            else:
                self.esc_count = 1
            
            self.last_esc_time = current_time
            
            if self.esc_count >= 3:
                print_boxed("Stop Triggered!")
                self.running = False
                self.window.safe_quit()
                os._exit(0) # Force exit

    def start_agent_thread(self):
        if self.running:
            return
            
        self.running = True
        
        # Run Agent in a new thread
        thread = threading.Thread(target=self.run_agent, args=(self.task,))
        thread.daemon = True
        thread.start()

    def run_agent(self, task):
        start_message = format_status_box("Task", f"Starting task:\n{task}")
        window_start_message = format_status_box("Task", f"Starting task:\n{task}", width=DISPLAY_BOX_WIDTH)
        print(colorize_terminal(start_message), flush=True)
        self.log(window_start_message + "\n")
        final_feedback = None
        try:
            def pre_callback():
                # Hide window before screenshot
                self.window.set_suppressed(True) # Prevent window from showing up if new logs arrive
                self.window.safe_hide()
                time.sleep(0.5) # Wait for window to hide

            def post_callback():
                # Restore window after screenshot
                self.window.set_suppressed(False) # Allow window to show again
                self.window.safe_unhide()

            # Use DisplayWindow regardless of DEBUG_MODE
            # DEBUG_MODE only affects internal logic like saving screenshots (controlled by scripts.config)
            self.agent = IrisAgent(task, pre_callback=pre_callback, post_callback=post_callback)
            
            while self.running:
                # Execute one step
                feedback = self.agent.step(
                    log_callback=self.log
                )
                
                if "[Max Steps Reached]" in feedback or "[Task Completed]" in feedback:
                    self.running = False
                    final_feedback = feedback
                    break
                
        except Exception as e:
            error_message = format_status_box("Error", f"Error: {e}")
            window_error_message = format_status_box("Error", f"Error: {e}", width=DISPLAY_BOX_WIDTH)
            self.log(window_error_message + "\n")
            print(colorize_terminal(error_message), flush=True)
        finally:
            self.running = False
            self.log(format_status_box("Task Finished", "Task finished.", width=DISPLAY_BOX_WIDTH) + "\n")
            if final_feedback:
                print_boxed(f"Final Result:\n{final_feedback}")
            
            # Ensure window is visible and prompt for exit
            self.window.safe_unhide()
            self.log(format_status_box("Exit", "Press ESC 3 times to exit the program.", width=DISPLAY_BOX_WIDTH) + "\n")
            print_boxed("Task finished. Press ESC 3 times to exit.")

    def start(self):
        self.window.start_loop()

def wait_with_countdown(seconds):
    if seconds <= 0:
        print_boxed("Starting task now.")
        return

    seconds_text = f"{seconds:g}"
    print_boxed(f"You have {seconds_text} seconds to set the screen to the task start state. If you press Enter, the task will start immediately.")
    
    stop_event = threading.Event()
    
    def on_press(key):
        if key == keyboard.Key.enter:
            stop_event.set()
            return False # Stop listener

    # Start a non-blocking listener
    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    
    start_time = time.time()
    while time.time() - start_time < seconds:
        if stop_event.is_set():
            print_boxed("Enter detected, starting task immediately!")
            if listener.is_alive():
                listener.stop()
            return
        
        # Print countdown (optional, but good for UX)
        # remaining = int(seconds - (time.time() - start_time))
        # sys.stdout.write(f"\rTime remaining: {remaining} seconds...")
        # sys.stdout.flush()
        time.sleep(0.1)
    
    if listener.is_alive():
        listener.stop()
    print_boxed("Time is up, starting task!")

if __name__ == "__main__":
    # Check if running in a headless environment (if GUI is needed)
    if os.environ.get('DISPLAY', '') == '' and os.name != 'nt':
        print_boxed('No display found. Cannot run GUI.')
        sys.exit(1)

    task_prompt = prompt_for_task(logo)
    
    if task_prompt is None or not task_prompt.text.strip():
        print_boxed("No task selected, exiting.")
        sys.exit(0)
        
    wait_with_countdown(task_prompt.delay_seconds)
        
    app = IrisController(task_prompt.text)
    app.start()
