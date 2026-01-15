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
        self.root.geometry("600x400")
        
        # 任务输入
        self.task_label = tk.Label(self.root, text="Enter Task:")
        self.task_label.pack(pady=5)
        
        self.task_entry = tk.Entry(self.root, width=50)
        self.task_entry.pack(pady=5)
        
        # 运行按钮
        self.run_button = tk.Button(self.root, text="Run Iris", command=self.start_agent_thread)
        self.run_button.pack(pady=10)
        
        # 日志显示
        self.log_area = scrolledtext.ScrolledText(self.root, width=70, height=15)
        self.log_area.pack(pady=10)
        
        self.agent = None
        self.running = False
        self.esc_count = 0
        self.last_esc_time = 0

        # 监听 ESC 键
        self.listener = keyboard.Listener(on_press=self.on_key_press)
        self.listener.start()

    def log(self, message):
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        print(message) # 同时输出到控制台

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
            
            while self.running:
                # 截图前隐藏窗口
                # 注意：在 Linux/X11 上 withdraw/deiconify 可能有延迟或闪烁
                # 为了简单起见，我们尝试最小化或者移出屏幕，或者直接 withdraw
                self.root.withdraw()
                time.sleep(0.5) # 等待窗口隐藏
                
                # 执行一步
                feedback = self.agent.step()
                
                # 恢复窗口
                self.root.deiconify()
                
                # 记录反馈
                self.log(f"Step Feedback: {feedback}")
                
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
