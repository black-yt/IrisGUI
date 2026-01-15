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
    def __init__(self, pre_callback=None, post_callback=None):
        self.debug_dir = os.path.join(os.path.dirname(__file__), "debug")
        if not os.path.exists(self.debug_dir):
            os.makedirs(self.debug_dir)
        self.pre_callback = pre_callback
        self.post_callback = post_callback

    def _draw_mouse(self, image, local_x, local_y):
        draw = ImageDraw.Draw(image)
        # 绘制一个简单的箭头或标记来表示鼠标位置
        # 这里画一个以 (x,y) 为中心的十字或者圆圈
        r = 8
        draw.ellipse((local_x-r, local_y-r, local_x+r, local_y+r), outline=GRID_COLOR, width=MOUSE_WIDTH)
        draw.line((local_x-r, local_y, local_x+r, local_y), fill=MOUSE_COLOR, width=MOUSE_WIDTH)
        draw.line((local_x, local_y-r, local_x, local_y+r), fill=MOUSE_COLOR, width=MOUSE_WIDTH)
        return image

    def _draw_grid_with_labels(self, image, step, prefix, offset_x=0, offset_y=0):
        """
        Draws a grid on the image and adds a white border with labels.
        Returns the processed image and a dictionary mapping IDs to GLOBAL coordinates.
        
        :param image: The PIL image to draw on.
        :param step: Grid step size.
        :param prefix: 'G' for Global, 'L' for Local.
        :param offset_x: The global x-coordinate of the top-left corner of this image (for Local view).
        :param offset_y: The global y-coordinate of the top-left corner of this image (for Local view).
        """
        width, height = image.size
        padding = 40 # Width of the white border
        
        # Create a new canvas with white border
        new_width = width + 2 * padding
        new_height = height + 2 * padding
        canvas = Image.new('RGB', (new_width, new_height), color='white')
        
        # Paste the original image in the center
        canvas.paste(image, (padding, padding))
        draw = ImageDraw.Draw(canvas)
        
        try:
            font = ImageFont.truetype("arial.ttf", 16)
        except IOError:
            font = ImageFont.load_default()

        coordinate_map = {}
        
        # Draw vertical lines and X-axis labels
        col_index = 0
        for x in range(0, width, step):
            # Line on the image
            draw_x = x + padding
            draw.line([(draw_x, padding), (draw_x, new_height - padding)], fill=GRID_COLOR, width=GRID_WIDTH)
            
            # Label on top border
            label = f"{col_index:02d}"
            bbox = draw.textbbox((0, 0), label, font=font)
            text_w = bbox[2] - bbox[0]
            draw.text((draw_x - text_w // 2, 5), label, fill="black", font=font)
            
            # Label on bottom border
            draw.text((draw_x - text_w // 2, new_height - padding + 5), label, fill="black", font=font)
            
            col_index += 1

        # Draw horizontal lines and Y-axis labels
        row_index = 0
        for y in range(0, height, step):
            # Line on the image
            draw_y = y + padding
            draw.line([(padding, draw_y), (new_width - padding, draw_y)], fill=GRID_COLOR, width=GRID_WIDTH)
            
            # Label on left border
            label = f"{row_index:02d}"
            bbox = draw.textbbox((0, 0), label, font=font)
            text_h = bbox[3] - bbox[1]
            draw.text((5, draw_y - text_h // 2), label, fill="black", font=font)
            
            # Label on right border
            draw.text((new_width - padding + 5, draw_y - text_h // 2), label, fill="black", font=font)
            
            row_index += 1

        # Generate Coordinate Map
        # Re-iterate to populate map (or do it in the loops above, but nested is easier for map)
        
        for c in range(col_index): # Use actual count from loop
            for r in range(row_index):
                # ID format: PREFIX-XX-YY
                point_id = f"{prefix}-{c:02d}-{r:02d}"
                
                # Local coordinate on the image (not canvas)
                local_img_x = c * step
                local_img_y = r * step
                
                # Global coordinate
                global_x = offset_x + local_img_x
                global_y = offset_y + local_img_y
                
                coordinate_map[point_id] = (global_x, global_y)
                
        return canvas, coordinate_map

    def capture_state(self):
        if self.pre_callback:
            self.pre_callback()

        # 获取屏幕截图和鼠标位置
        try:
            screenshot = pyautogui.screenshot()
            mouse_x, mouse_y = pyautogui.position()
            
            # Ensure mouse coordinates are within screenshot bounds
            # This handles multi-monitor setups where mouse might be outside the primary screen
            mouse_x = max(0, min(mouse_x, screenshot.width - 1))
            mouse_y = max(0, min(mouse_y, screenshot.height - 1))
            
        except Exception as e:
            print(f"Error capturing state: {e}")
            screenshot = Image.new('RGB', (1920, 1080), color='black')
            mouse_x, mouse_y = 0, 0

        # 1. 生成全局视图 (Global View)
        # Global view uses GRID_STEP and prefix 'G'
        global_image_raw = screenshot.copy()
        
        global_image, global_map = self._draw_grid_with_labels(global_image_raw, GRID_STEP, "G", 0, 0)

        # Draw mouse on global view
        self._draw_mouse(global_image, mouse_x, mouse_y)
        
        # 2. 生成局部视图 (Local View)
        # 以鼠标为中心裁剪
        crop_half = CROP_SIZE // 2
        left = max(0, mouse_x - crop_half)
        top = max(0, mouse_y - crop_half)
        right = min(screenshot.width, mouse_x + crop_half)
        bottom = min(screenshot.height, mouse_y + crop_half)
        
        local_image_raw = screenshot.crop((left, top, right, bottom))
        
        # Local view uses LOCAL_GRID_STEP and prefix 'L'
        # Pass (left, top) as offset so the map contains global coordinates
        local_image, local_map = self._draw_grid_with_labels(local_image_raw, LOCAL_GRID_STEP, "L", left, top)

        # Draw mouse on local view
        # Mouse position relative to the crop
        local_mouse_x = mouse_x - left
        local_mouse_y = mouse_y - top
        self._draw_mouse(local_image, local_mouse_x, local_mouse_y)

        # Merge maps
        full_coordinate_map = {**global_map, **local_map}

        # Debug 存档
        if DEBUG_MODE:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            global_path = os.path.join(self.debug_dir, f"global_{timestamp}.png")
            local_path = os.path.join(self.debug_dir, f"local_{timestamp}.png")
            global_image.save(global_path)
            local_image.save(local_path)

        if self.post_callback:
            self.post_callback()

        return global_image, local_image, full_coordinate_map


class ActionExecutor:
    def __init__(self, pre_callback=None, post_callback=None):
        self.pre_callback = pre_callback
        self.post_callback = post_callback

    def execute(self, action_dict, coordinate_map=None):
        if self.pre_callback:
            self.pre_callback()

        action_type = action_dict.get("action_type")
        
        result = ""
        try:
            if action_type == "move":
                point_id = action_dict.get("point_id")
                duration = float(action_dict.get("duration", 0.5))
                
                if not point_id:
                    return "Error: 'point_id' is required for move action."
                
                if coordinate_map and point_id in coordinate_map:
                    x, y = coordinate_map[point_id]
                    pyautogui.moveTo(x, y, duration=duration, tween=pyautogui.easeInOutQuad)
                    return f"Action move to {point_id} ({x}, {y}) executed."
                else:
                    return f"Error: Point ID '{point_id}' not found in coordinate map."

            elif action_type == "click":
                button = action_dict.get("button", "left")
                repeat = int(action_dict.get("repeat", 1))
                pyautogui.click(button=button, clicks=repeat)
                return f"Action click ({button}, repeat={repeat}) executed."

            elif action_type == "double_click":
                pyautogui.doubleClick()
                return "Action double_click executed."

            elif action_type == "mouse_down":
                button = action_dict.get("button", "left")
                pyautogui.mouseDown(button=button)
                return f"Action mouse_down ({button}) executed."

            elif action_type == "mouse_up":
                button = action_dict.get("button", "left")
                pyautogui.mouseUp(button=button)
                return f"Action mouse_up ({button}) executed."

            elif action_type == "scroll":
                direction = action_dict.get("direction", "down")
                amount_str = action_dict.get("amount", "line")
                
                clicks = 0
                if amount_str == "line":
                    clicks = 100
                elif amount_str == "half":
                    clicks = 500
                elif amount_str == "page":
                    clicks = 1000
                
                if direction == "up":
                    pyautogui.scroll(clicks)
                elif direction == "down":
                    pyautogui.scroll(-clicks)
                elif direction == "left":
                    pyautogui.hscroll(-clicks)
                elif direction == "right":
                    pyautogui.hscroll(clicks)
                
                return f"Action scroll {direction} {amount_str} executed."

            elif action_type == "type":
                text = action_dict.get("text", "")
                submit = action_dict.get("submit", False)
                pyautogui.write(text, interval=0.05)
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
                result = f"Error: Unknown action type '{action_type}'."

        except Exception as e:
            result = f"Error executing action {action_type}: {str(e)}"
        
        if self.post_callback:
            self.post_callback()
            
        return result

if __name__ == "__main__":
    print("Testing tools.py...")
    
    # Test VisionPerceptor
    try:
        print("Testing VisionPerceptor...")
        vision = VisionPerceptor()
        global_img, local_img, coord_map = vision.capture_state()
        print(f"Capture successful.")
        print(f"Global size: {global_img.size}")
        print(f"Local size: {local_img.size}")
        print(f"Map size: {len(coord_map)}")
        print(f"Sample G point: {list(coord_map.keys())[0]} -> {list(coord_map.values())[0]}")
    except Exception as e:
        print(f"VisionPerceptor test failed: {e}")

    # Test ActionExecutor
    try:
        print("Testing ActionExecutor...")
        executor = ActionExecutor()
        # Mock map
        mock_map = {"G-00-00": (0, 0), "L-00-00": (1000, 800)}
        
        # Test move
        result = executor.execute({"action_type": "move", "point_id": "L-00-00"}, mock_map)
        result = executor.execute({'action_type': 'click', 'button': 'left', 'repeat': 1}, mock_map)
        result = executor.execute({"action_type": "type", "text": "111111111111111111"}, mock_map)
        print(f"Move result: {result}")
        
    except Exception as e:
        print(f"ActionExecutor test failed: {e}")
