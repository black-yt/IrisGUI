import tkinter as tk
from tkinter import scrolledtext
import threading
import time
import os
from pynput import keyboard
from scripts.agent import IrisAgent

class IrisGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Iris Agent")
        # 设置全屏
        self.root.state('zoomed')
        
        # 任务输入
        self.task_label = tk.Label(self.root, text="Enter Task:")
        self.task_label.pack(pady=5)
        
        self.task_entry = tk.Entry(self.root, width=100)
        self.task_entry.pack(pady=5)
        
        # 运行按钮
        self.run_button = tk.Button(self.root, text="Run Iris", command=self.start_agent_thread)
        self.run_button.pack(pady=10)
        
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
        
        task = self.task_entry.get()
        if not task:
            self.log("Please enter a task.")
            return
            
        self.running = True
        self.run_button.config(state=tk.DISABLED)
        
        # 在新线程中运行 Agent
        thread = threading.Thread(target=self.run_agent, args=(task,))
        thread.daemon = True
        thread.start()

    def run_agent(self, task):
        self.log(f"Starting task: {task}")
        try:
            self.agent = IrisAgent(task)
            
            def pre_capture():
                # 截图前隐藏窗口
                self.root.withdraw()
                time.sleep(0.5) # 等待窗口隐藏

            def post_capture():
                # 截图后恢复窗口
                self.root.deiconify()
                self.root.state('zoomed')

            while self.running:
                # 执行一步，传入回调函数控制窗口显隐
                feedback = self.agent.step(
                    pre_capture_callback=pre_capture,
                    post_capture_callback=post_capture,
                    log_callback=self.log
                )
                
                if "Max steps reached" in feedback:
                    self.running = False
                    break
                
                # 简单的停止条件示例（实际可能需要 Agent 自己决定何时结束）
                # 这里我们只是无限循环直到手动停止或达到最大步数
                
        except Exception as e:
            self.log(f"Error: {e}")
        finally:
            self.running = False
            self.run_button.config(state=tk.NORMAL)
            self.root.deiconify()
            self.root.state('zoomed')

    def start(self):
        self.root.mainloop()

if __name__ == "__main__":
    # 检查是否在无头环境中运行（例如 CI/CD 或某些服务器环境）
    # 如果没有 DISPLAY 环境变量，Tkinter 会失败
    if os.environ.get('DISPLAY', '') == '':
        print('No display found. Using dummy display for testing if needed, or exiting.')
        # 对于这个任务，我们假设有显示环境，或者用户会在有显示环境的地方运行
    
    app = IrisGUI()
    app.start()
