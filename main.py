import threading
import time
import os
import argparse
import sys
import msvcrt
from pynput import keyboard
from scripts.agent import IrisAgent
from scripts.utils import DisplayWindow, print_boxed, logo


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
        self.log(f"Starting task: {task}")
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
            
            final_feedback = None
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
            self.log(f"Error: {e}")
            print_boxed(f"Error: {e}") # Also print to console just in case
        finally:
            self.running = False
            self.log("\nTask finished.")
            if final_feedback:
                print_boxed(f"Final Result:\n{final_feedback}")
            
            # Ensure window is visible and prompt for exit
            self.window.safe_unhide()
            self.log("\nPress ESC 3 times to exit the program.")
            print_boxed("Task finished. Press ESC 3 times to exit.")

    def start(self):
        self.window.start_loop()

def print_banner():
    print(logo.strip())
    instructions = """
Enter the task (line breaks are supported)
After entering the task, type [START] and press Enter to start.
"""
    print_boxed(instructions)

def get_multiline_input():
    lines = []
    while True:
        try:
            line = input()
            if "[START]" in line:
                # If [START] is in this line, keep the content before [START] (if any)
                # Or simply consider this line as the end signal
                # The requirement is "The user needs to enter the [START] symbol at the end to start the task"
                # We can remove [START] and take the preceding part, or if [START] occupies a line alone, end it
                parts = line.split("[START]")
                if parts[0].strip():
                    lines.append(parts[0])
                break
            lines.append(line)
        except EOFError:
            break
    return "\n".join(lines)

def wait_with_countdown(seconds):
    print_boxed(f"You have {seconds} seconds to set the screen to the task start state. If you press Enter, the task will start immediately.")
    
    start_time = time.time()
    while time.time() - start_time < seconds:
        # Check for key press
        if msvcrt.kbhit():
            key = msvcrt.getch()
            if key == b'\r' or key == b'\n':
                print_boxed("Enter detected, starting task immediately!")
                return
            # Consume other keys or ignore
        
        # Print countdown (optional, but good for UX)
        remaining = int(seconds - (time.time() - start_time))
        # sys.stdout.write(f"\rTime remaining: {remaining} seconds...")
        # sys.stdout.flush()
        time.sleep(0.1)
    
    print_boxed("Time is up, starting task!")

if __name__ == "__main__":
    # Check if running in a headless environment (if GUI is needed)
    if os.environ.get('DISPLAY', '') == '' and os.name != 'nt':
        print_boxed('No display found. Cannot run GUI.')
        sys.exit(1)

    print_banner()
    
    task_description = get_multiline_input()
    
    if not task_description.strip():
        print_boxed("Task description is empty, exiting.")
        sys.exit(0)
        
    wait_with_countdown(5)
        
    app = IrisController(task_description)
    app.start()
