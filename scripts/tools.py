import time
import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from scripts.config import *
import pyautogui

# 设置 pyautogui 的一些安全参数
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1

class VisionPerceptor:
    def __init__(self):
        self.debug_dir = os.path.join(os.path.dirname(__file__), "debug")
        if not os.path.exists(self.debug_dir):
            os.makedirs(self.debug_dir)

    def _draw_grid(self, image):
        draw = ImageDraw.Draw(image)
        width, height = image.size
        step = GRID_STEP
        
        # 绘制网格线
        for x in range(0, width, step):
            draw.line([(x, 0), (x, height)], fill=GRID_COLOR, width=GRID_WIDTH)
        for y in range(0, height, step):
            draw.line([(0, y), (width, y)], fill=GRID_COLOR, width=GRID_WIDTH)
            
        # 绘制坐标文字
        # 尝试加载字体，如果失败使用默认字体
        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except IOError:
            font = ImageFont.load_default()
            
        for x in range(0, width, step):
            for y in range(0, height, step):
                # 在交叉点绘制坐标 (x, y)
                text = f"({x},{y})"
                # 添加一点背景框以便看清文字
                bbox = draw.textbbox((x, y), text, font=font)
                draw.rectangle(bbox, fill="white")
                draw.text((x, y), text, fill="black", font=font)
                
        return image

    def _draw_mouse(self, image, x, y):
        draw = ImageDraw.Draw(image)
        # 绘制一个简单的箭头或标记来表示鼠标位置
        # 这里画一个以 (x,y) 为中心的十字或者圆圈，文档说是“醒目颜色的箭头”
        # 为了简单且清晰，我们画一个带边框的圆圈和十字
        r = 15
        draw.ellipse((x-r, y-r, x+r, y+r), outline=GRID_COLOR, width=MOUSE_WIDTH)
        draw.line((x-r, y, x+r, y), fill=MOUSE_COLOR, width=MOUSE_WIDTH)
        draw.line((x, y-r, x, y+r), fill=MOUSE_COLOR, width=MOUSE_WIDTH)
        
        # 在鼠标的标签下面标出左边（x,y）
        try:
            font = ImageFont.truetype("arial.ttf", 16)
        except IOError:
            font = ImageFont.load_default()
            
        text = f"({x},{y})"
        
        # 计算文本尺寸
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # 默认位置：鼠标下方居中
        text_x = x - text_width // 2
        text_y = y + r + 5
        
        # 边界检查与调整
        img_width, img_height = image.size
        
        # 如果下方超出边界，则放在上方
        if text_y + text_height > img_height:
            text_y = y - r - 5 - text_height
            
        # 如果上方也超出（极少见，除非图片极小），则保持在边界内
        if text_y < 0:
            text_y = 0
            
        # 如果左边超出边界，则靠左对齐
        if text_x < 0:
            text_x = 0
            
        # 如果右边超出边界，则靠右对齐
        if text_x + text_width > img_width:
            text_x = img_width - text_width
        
        # 绘制背景框以提高可读性
        padding = 2
        draw.rectangle(
            (text_x - padding, text_y - padding, text_x + text_width + padding, text_y + text_height + padding),
            fill="white",
            outline=GRID_COLOR
        )
        
        # 绘制文本
        draw.text(
            (text_x, text_y),
            text,
            fill="red",
            font=font
        )
        
        return image

    def capture_state(self):
        # 获取屏幕截图和鼠标位置
        try:
            screenshot = pyautogui.screenshot()
            mouse_x, mouse_y = pyautogui.position()
        except Exception as e:
            print(f"Error capturing state: {e}")
            # 返回空对象或抛出异常，视情况而定。这里创建一个空白图像作为 fallback
            screenshot = Image.new('RGB', (1920, 1080), color='black')
            mouse_x, mouse_y = 0, 0

        # 1. 生成全局视图 (Global View)
        global_image = screenshot.copy()
        global_image = self._draw_grid(global_image)
        global_image = self._draw_mouse(global_image, mouse_x, mouse_y)

        # 2. 生成局部视图 (Local View)
        # 以鼠标为中心裁剪
        crop_half = CROP_SIZE // 2
        left = max(0, mouse_x - crop_half)
        top = max(0, mouse_y - crop_half)
        right = min(screenshot.width, mouse_x + crop_half)
        bottom = min(screenshot.height, mouse_y + crop_half)
        
        # 处理边界情况，保持裁剪尺寸一致（如果靠近边缘，可能需要调整）
        # 简单起见，如果靠近边缘，裁剪区域可能会小于 CROP_SIZE，或者我们可以平移裁剪框
        # 这里我们简单裁剪，如果不足 CROP_SIZE 也不强制填充，但为了坐标一致性，最好保持中心
        # 实际上，为了让模型理解，局部图最好就是以鼠标为中心。
        
        local_image = screenshot.crop((left, top, right, bottom))
        
        # 在局部图上绘制鼠标位置
        # 鼠标在局部图中的相对坐标
        local_mouse_x = mouse_x - left
        local_mouse_y = mouse_y - top
        local_image = self._draw_mouse(local_image, local_mouse_x, local_mouse_y)

        # Debug 存档
        if DEBUG_MODE:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            global_path = os.path.join(self.debug_dir, f"global_{timestamp}.png")
            local_path = os.path.join(self.debug_dir, f"local_{timestamp}.png")
            global_image.save(global_path)
            local_image.save(local_path)
            # print(f"Debug images saved: {global_path}, {local_path}")

        return global_image, local_image


class ActionExecutor:
    def execute(self, action_dict):
        action_type = action_dict.get("type")
        
        try:
            if action_type == "move":
                x = int(action_dict.get("x"))
                y = int(action_dict.get("y"))
                duration = float(action_dict.get("duration", 0.5))
                pyautogui.moveTo(x, y, duration=duration, tween=pyautogui.easeInOutQuad)
                return f"Action move ({x}, {y}) executed."

            elif action_type == "click":
                button = action_dict.get("button", "left")
                repeat = int(action_dict.get("repeat", 1))
                # pyautogui.click 支持 clicks 参数，但 repeat=2 时通常用 doubleClick 更明确，
                # 不过这里直接用 clicks 参数也可以
                pyautogui.click(button=button, clicks=repeat)
                return f"Action click ({button}, repeat={repeat}) executed."

            elif action_type == "double_click":
                pyautogui.doubleClick()
                return "Action double_click executed."

            elif action_type == "drag":
                to_x = int(action_dict.get("to_x"))
                to_y = int(action_dict.get("to_y"))
                from_x = action_dict.get("from_x")
                from_y = action_dict.get("from_y")
                duration = float(action_dict.get("duration", 1.0))

                if from_x is not None and from_y is not None:
                    pyautogui.moveTo(int(from_x), int(from_y))
                
                pyautogui.mouseDown()
                time.sleep(0.1) # 模拟抓取确认
                pyautogui.moveTo(to_x, to_y, duration=duration)
                pyautogui.mouseUp()
                return f"Action drag to ({to_x}, {to_y}) executed."

            elif action_type == "hover":
                duration = float(action_dict.get("duration", 1.0))
                time.sleep(duration)
                return f"Action hover for {duration}s executed."

            elif action_type == "scroll":
                direction = action_dict.get("direction", "down")
                amount_str = action_dict.get("amount", "line")
                
                # 定义滚动量
                clicks = 0
                if amount_str == "line":
                    clicks = 100 # 假设 100 是一个合理的单位
                elif amount_str == "half":
                    clicks = 500
                elif amount_str == "page":
                    clicks = 1000
                
                if direction == "up":
                    pyautogui.scroll(clicks)
                elif direction == "down":
                    pyautogui.scroll(-clicks)
                elif direction == "left":
                    pyautogui.hscroll(-clicks) # hscroll 负值通常向左? 需要测试，通常负值向左
                elif direction == "right":
                    pyautogui.hscroll(clicks)
                
                return f"Action scroll {direction} {amount_str} executed."

            elif action_type == "type":
                text = action_dict.get("text", "")
                submit = action_dict.get("submit", False)
                pyautogui.write(text, interval=0.05) # 模拟打字延迟
                if submit:
                    pyautogui.press("enter")
                return f"Action type '{text}' executed."

            elif action_type == "hotkey":
                keys = action_dict.get("keys", [])
                if keys:
                    pyautogui.hotkey(*keys)
                return f"Action hotkey {keys} executed."

            elif action_type == "wait":
                seconds = float(action_dict.get("seconds", 1.0))
                time.sleep(seconds)
                return f"Action wait {seconds}s executed."

            else:
                return f"Error: Unknown action type '{action_type}'."

        except Exception as e:
            return f"Error executing action {action_type}: {str(e)}"

if __name__ == "__main__":
    print("Testing tools.py...")
    
    # Test VisionPerceptor
    try:
        print("Testing VisionPerceptor...")
        vision = VisionPerceptor()
        global_img, local_img = vision.capture_state()
        print(f"Capture successful. Global size: {global_img.size}, Local size: {local_img.size}")
    except Exception as e:
        print(f"VisionPerceptor test failed: {e}")

    # Test ActionExecutor
    try:
        print("Testing ActionExecutor...")
        executor = ActionExecutor()
        # Test a safe action: wait
        result = executor.execute({"type": "wait", "seconds": 0.5})
        print(f"Wait action result: {result}")
        
        # Optional: Test mouse move (small movement to verify)
        # current_x, current_y = pyautogui.position()
        # result = executor.execute({"type": "move", "x": current_x, "y": current_y, "duration": 0.1})
        # print(f"Move action result: {result}")
        
    except Exception as e:
        print(f"ActionExecutor test failed: {e}")
