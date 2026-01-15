import tkinter as tk
from tkinter import scrolledtext
import threading
import time
import os
import argparse
import sys
from pynput import keyboard
from scripts.agent import IrisAgent
from scripts.config import DEBUG_MODE

class IrisGUI:
    def __init__(self, task):
        self.root = tk.Tk()
        self.root.title("Iris Agent (Debug Mode)")
        # 设置全屏
        self.root.state('zoomed')
        
        self.task = task
        
        # 日志显示 - 增加高度和宽度以适应全屏
        self.log_area = scrolledtext.ScrolledText(self.root, width=150, height=40)
        self.log_area.pack(pady=10, fill=tk.BOTH, expand=True)
        
        self.agent = None
        self.running = False
        self.esc_count = 0
        self.last_esc_time = 0

        # 监听 ESC 键
        self.listener = keyboard.Listener(on_press=self.on_key_press)
        self.listener.start()
        
        # 自动开始任务
        self.root.after(100, self.start_agent_thread)

    def log(self, message):
        # 使用 after 方法在主线程中更新 UI
        self.root.after(0, self._update_log, message)

    def _update_log(self, message):
        self.log_area.insert(tk.END, message)
        self.log_area.see(tk.END)

    def on_key_press(self, key):
        if key == keyboard.Key.esc:
            current_time = time.time()
            if current_time - self.last_esc_time < 1.0: # 1秒内连续按
                self.esc_count += 1
            else:
                self.esc_count = 1
            
            self.last_esc_time = current_time
            
            if self.esc_count >= 3:
                self.log("Emergency Stop Triggered!")
                self.running = False
                self.root.quit()
                os._exit(0) # 强制退出

    def start_agent_thread(self):
        if self.running:
            return
            
        self.running = True
        
        # 在新线程中运行 Agent
        thread = threading.Thread(target=self.run_agent, args=(self.task,))
        thread.daemon = True
        thread.start()

    def run_agent(self, task):
        self.log(f"Starting task: {task}")
        try:
            def pre_callback():
                # 截图前隐藏窗口
                self.root.withdraw()
                time.sleep(0.5) # 等待窗口隐藏

            def post_callback():
                # 截图后恢复窗口
                self.root.deiconify()
                self.root.state('zoomed')

            self.agent = IrisAgent(task, pre_callback=pre_callback, post_callback=post_callback)
            
            while self.running:
                # 执行一步，传入回调函数控制窗口显隐
                feedback = self.agent.step(
                    log_callback=self.log
                )
                
                if "Max steps reached" in feedback:
                    self.running = False
                    break
                
        except Exception as e:
            self.log(f"Error: {e}")
        finally:
            self.running = False
            # 任务结束不自动退出，保留窗口查看日志
            self.log("\nTask finished.")

    def start(self):
        self.root.mainloop()

def run_console_agent(task):
    print(f"Starting task: {task}")
    
    running = True
    esc_count = 0
    last_esc_time = 0

    def on_key_press(key):
        nonlocal esc_count, last_esc_time, running
        if key == keyboard.Key.esc:
            current_time = time.time()
            if current_time - last_esc_time < 1.0:
                esc_count += 1
            else:
                esc_count = 1
            
            last_esc_time = current_time
            
            if esc_count >= 3:
                print("\nEmergency Stop Triggered!")
                running = False
                os._exit(0)

    listener = keyboard.Listener(on_press=on_key_press)
    listener.start()

    try:
        # No pre/post callbacks needed for console mode as there is no window to hide
        agent = IrisAgent(task)
        
        while running:
            # agent.step already prints to stdout, so we don't need a log_callback that prints
            feedback = agent.step()
            
            if "Max steps reached" in feedback:
                running = False
                break
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        print("\nTask finished.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Iris Agent")
    parser.add_argument("task", help="The task description")
    
    args = parser.parse_args()
    
    print("Waiting 5 seconds before starting task...")
    time.sleep(5)

    if DEBUG_MODE:
        # 检查是否在无头环境中运行
        if os.environ.get('DISPLAY', '') == '' and os.name != 'nt':
            print('No display found. Cannot run in debug mode.')
            sys.exit(1)
            
        app = IrisGUI(args.task)
        app.start()
    else:
        run_console_agent(args.task)
