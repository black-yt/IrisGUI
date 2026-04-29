import time
import os
import math
from datetime import datetime
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont
from scripts.config import *
import pyautogui
import pyperclip

# Set some safety parameters for pyautogui
# pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1


@lru_cache(maxsize=8)
def _load_label_font(size):
    for font_name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(font_name, size)
        except IOError:
            continue
    return ImageFont.load_default()


class VisionPerceptor:
    def __init__(self, pre_callback=None, post_callback=None):
        self.debug_dir = os.path.join(os.path.dirname(__file__), "debug", "screenshot")
        if not os.path.exists(self.debug_dir):
            os.makedirs(self.debug_dir)
        self.pre_callback = pre_callback
        self.post_callback = post_callback
        self.last_capture_files = None

    def _draw_mouse(self, image, local_x, local_y, r=8):
        draw = ImageDraw.Draw(image)
        # Draw a simple arrow or marker to represent mouse position
        # Here draw a cross or circle centered at (x,y)
        draw.ellipse((local_x-r, local_y-r, local_x+r, local_y+r), outline=GRID_COLOR, width=MOUSE_WIDTH)
        draw.line((local_x-r, local_y, local_x+r, local_y), fill=MOUSE_COLOR, width=MOUSE_WIDTH)
        draw.line((local_x, local_y-r, local_x, local_y+r), fill=MOUSE_COLOR, width=MOUSE_WIDTH)
        return image

    def _draw_centered_text(self, draw, center_x, center_y, text, font, fill="black"):
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        draw.text(
            (center_x - text_w / 2 - bbox[0], center_y - text_h / 2 - bbox[1]),
            text,
            fill=fill,
            font=font,
        )

    def _draw_corner_prefix_labels(self, draw, prefix, padding, width, height, font):
        label = str(prefix).upper()
        centers = (
            (padding // 2, padding // 2),
            (width - padding // 2, padding // 2),
            (padding // 2, height - padding // 2),
            (width - padding // 2, height - padding // 2),
        )
        for center_x, center_y in centers:
            self._draw_centered_text(draw, center_x, center_y, label, font, fill="black")

    def _draw_grid_with_labels(
        self,
        image,
        step,
        prefix,
        offset_x=0,
        offset_y=0,
        anchor_x=0,
        anchor_y=0,
        anchor_col=0,
        anchor_row=0,
    ):
        """
        Draws a grid on the image and adds a white border with labels.
        Returns the processed image and a dictionary mapping IDs to GLOBAL coordinates.
        
        :param image: The PIL image to draw on.
        :param step: Grid step size.
        :param prefix: 'G' for Global, 'L' for Local.
        :param offset_x: The global x-coordinate of the top-left corner of this image (for Local view).
        :param offset_y: The global y-coordinate of the top-left corner of this image (for Local view).
        :param anchor_x: X coordinate where the grid starts expanding from.
        :param anchor_y: Y coordinate where the grid starts expanding from.
        :param anchor_col: Column label assigned to anchor_x.
        :param anchor_row: Row label assigned to anchor_y.
        """
        width, height = image.size
        font_size = 32 if prefix == "G" else 16
        padding = 80 if prefix == "G" else 40
        
        # Create a new canvas with white border
        new_width = width + 2 * padding
        new_height = height + 2 * padding
        canvas = Image.new('RGB', (new_width, new_height), color='white')
        
        # Paste the original image in the center
        canvas.paste(image, (padding, padding))
        draw = ImageDraw.Draw(canvas)
        
        font = _load_label_font(font_size)

        coordinate_map = {}
        self._draw_corner_prefix_labels(draw, prefix, padding, new_width, new_height, font)

        columns = self._grid_axis_positions(anchor_x, width, step, anchor_col)
        rows = self._grid_axis_positions(anchor_y, height, step, anchor_row)

        # Draw vertical lines and X-axis labels
        for col_index, x in columns:
            # Line on the image
            draw_x = x + padding
            draw.line([(draw_x, padding), (draw_x, new_height - padding)], fill=GRID_COLOR, width=GRID_WIDTH)
            
            # Label on top border
            label = f"{col_index:02d}"
            self._draw_centered_text(draw, draw_x, padding // 2, label, font, fill="black")
            
            # Label on bottom border
            self._draw_centered_text(draw, draw_x, new_height - padding // 2, label, font, fill="black")

        # Draw horizontal lines and Y-axis labels
        for row_index, y in rows:
            # Line on the image
            draw_y = y + padding
            draw.line([(padding, draw_y), (new_width - padding, draw_y)], fill=GRID_COLOR, width=GRID_WIDTH)
            
            # Label on left border
            label = f"{row_index:02d}"
            self._draw_centered_text(draw, padding // 2, draw_y, label, font, fill="black")
            
            # Label on right border
            self._draw_centered_text(draw, new_width - padding // 2, draw_y, label, font, fill="black")

        # Generate Coordinate Map
        # Re-iterate to populate map (or do it in the loops above, but nested is easier for map)

        for c, x in columns:
            for r, y in rows:
                # ID format: PREFIX-XX-YY
                point_id = f"{prefix}-{c:02d}-{r:02d}"

                # Local coordinate on the image (not canvas)
                local_img_x = min(x, max(0, width - 1))
                local_img_y = min(y, max(0, height - 1))

                # Global coordinate
                global_x = offset_x + local_img_x
                global_y = offset_y + local_img_y

                coordinate_map[point_id] = (global_x, global_y)

        return canvas, coordinate_map

    def _grid_axis_positions(self, anchor, size, step, anchor_index):
        min_delta = math.ceil((0 - anchor) / step)
        max_delta = math.floor((size - anchor) / step)
        positions = []
        for delta in range(min_delta, max_delta + 1):
            index = anchor_index + delta
            if index < 0:
                continue
            pos = anchor + delta * step
            if 0 <= pos <= size:
                positions.append((index, pos))
        return positions

    def _nearest_grid_id(self, x, y, width, height, step, prefix):
        max_col = len(range(0, width + 1, step)) - 1
        max_row = len(range(0, height + 1, step)) - 1
        col = max(0, min(round(x / step), max_col))
        row = max(0, min(round(y / step), max_row))
        return f"{prefix}-{col:02d}-{row:02d}"

    def _crop_local_view(self, screenshot, mouse_x, mouse_y):
        crop_half = CROP_SIZE // 2
        left = max(0, mouse_x - crop_half)
        top = max(0, mouse_y - crop_half)
        right = min(screenshot.width, mouse_x + crop_half)
        bottom = min(screenshot.height, mouse_y + crop_half)

        local_image = screenshot.crop((left, top, right, bottom))
        local_mouse_x = mouse_x - left
        local_mouse_y = mouse_y - top
        return local_image, left, top, local_mouse_x, local_mouse_y

    def _local_mouse_grid_id(self):
        col = max(0, round((CROP_SIZE / 2) / LOCAL_GRID_STEP))
        row = max(0, round((CROP_SIZE / 2) / LOCAL_GRID_STEP))
        return f"L-{col:02d}-{row:02d}", col, row

    def capture_state(self, mouse_x, mouse_y):
        self.last_capture_files = None
        if self.pre_callback:
            self.pre_callback()

        try:
            # Capture screenshot
            try:
                screenshot = pyautogui.screenshot()
            except Exception as e:
                raise RuntimeError(f"Unable to capture screenshot: {e}") from e

            # Ensure mouse coordinates are within screenshot bounds.
            # This handles multi-monitor setups where mouse might be outside the primary screen.
            mouse_x = max(0, min(mouse_x, screenshot.width - 1))
            mouse_y = max(0, min(mouse_y, screenshot.height - 1))

            # 1. Generate Global View
            # Global view uses GRID_STEP and prefix 'G'
            global_image_raw = screenshot.copy()

            # Draw mouse on global view
            self._draw_mouse(global_image_raw, mouse_x, mouse_y, r=16)
            global_image, global_map = self._draw_grid_with_labels(global_image_raw, GRID_STEP, "G", 0, 0)

            # 2. Generate Local View. The crop stops at the screen edge; no off-screen area is padded.
            local_image_raw, left, top, local_mouse_x, local_mouse_y = self._crop_local_view(screenshot, mouse_x, mouse_y)
            mouse_grid_id, local_mouse_col, local_mouse_row = self._local_mouse_grid_id()

            # Local view uses LOCAL_GRID_STEP and prefix 'L'
            # Draw mouse on local view
            # Mouse position relative to the crop
            self._draw_mouse(local_image_raw, local_mouse_x, local_mouse_y, r=8)
            # Pass (left, top) as offset so the map contains global coordinates
            local_image, local_map = self._draw_grid_with_labels(
                local_image_raw,
                LOCAL_GRID_STEP,
                "L",
                left,
                top,
                anchor_x=local_mouse_x,
                anchor_y=local_mouse_y,
                anchor_col=local_mouse_col,
                anchor_row=local_mouse_row,
            )

            # Merge maps
            full_coordinate_map = {**global_map, **local_map}

            nearest_global_grid_id = self._nearest_grid_id(
                mouse_x,
                mouse_y,
                screenshot.width,
                screenshot.height,
                GRID_STEP,
                "G",
            )

            # Debug archive
            if DEBUG_MODE:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                global_file = f"global_{timestamp}.png"
                local_file = f"local_{timestamp}.png"
                global_path = os.path.join(self.debug_dir, global_file)
                local_path = os.path.join(self.debug_dir, local_file)
                global_image.save(global_path)
                local_image.save(local_path)
                self.last_capture_files = {"global": global_file, "local": local_file}

            return global_image, local_image, full_coordinate_map, mouse_grid_id, nearest_global_grid_id
        finally:
            if self.post_callback:
                self.post_callback()


class ActionExecutor:
    def __init__(self, pre_callback=None, post_callback=None):
        self.pre_callback = pre_callback
        self.post_callback = post_callback
        # Initialize mouse position
        try:
            self.mouse_x, self.mouse_y = pyautogui.position()
        except pyautogui.PyAutoGUIException:
            self.mouse_x, self.mouse_y = 0, 0

    def get_mouse_position(self):
        """
        Get the current tracked mouse position.
        Verifies if the real mouse position matches the tracked position.
        If not, attempts to correct it. If correction fails, raises an error.
        """
        TOLERANCE = 10 # pixels
        
        try:
            real_x, real_y = pyautogui.position()
            dist = ((real_x - self.mouse_x) ** 2 + (real_y - self.mouse_y) ** 2) ** 0.5
            
            if dist > TOLERANCE:
                print(f"Warning: Mouse drift detected. Tracked: ({self.mouse_x}, {self.mouse_y}), Real: ({real_x}, {real_y}). Correcting...")
                # Attempt to correct
                pyautogui.moveTo(self.mouse_x, self.mouse_y)
                
                # Check again
                real_x, real_y = pyautogui.position()
                dist = ((real_x - self.mouse_x) ** 2 + (real_y - self.mouse_y) ** 2) ** 0.5
                
                if dist > TOLERANCE:
                    raise Exception(f"Critical Error: Mouse position mismatch! Tracked: ({self.mouse_x}, {self.mouse_y}), Real: ({real_x}, {real_y}). Failed to correct.")
                    
        except pyautogui.PyAutoGUIException:
            pass # Ignore if pyautogui fails to get position (e.g. headless)
            
        return self.mouse_x, self.mouse_y

    def execute(self, action_dict, coordinate_map=None):
        if self.pre_callback:
            self.pre_callback()
        try:
            return self._execute_action(action_dict, coordinate_map)
        finally:
            if self.post_callback:
                self.post_callback()
            if ACTION_SETTLE_SECONDS > 0 and action_dict.get("action_type") != "wait":
                time.sleep(ACTION_SETTLE_SECONDS)

    def _execute_action(self, action_dict, coordinate_map=None):
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
                    # Update internal mouse position
                    self.mouse_x, self.mouse_y = x, y
                    return f"Action move to {point_id} executed."
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
                clicks = self._scroll_clicks(amount_str)
                
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
                self._type_text(text)
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

            elif action_type == "final_answer":
                text = action_dict.get("text", "")
                return f"[Task Completed]: {text}"

            else:
                result = f"Error: Unknown action type '{action_type}'."

        except Exception as e:
            result = f"Error executing action {action_type}: {str(e)}"
        return result

    def _scroll_clicks(self, amount):
        if amount == "line":
            return SCROLL_LINE_CLICKS
        if amount == "half":
            return SCROLL_HALF_CLICKS
        if amount == "page":
            return SCROLL_PAGE_CLICKS
        return SCROLL_LINE_CLICKS

    def _type_text(self, text):
        if not text:
            return
        should_paste = len(text) >= CLIPBOARD_TEXT_THRESHOLD or any(ord(c) >= 128 for c in text)
        if not should_paste:
            pyautogui.write(text, interval=TYPE_INTERVAL_SECONDS)
            return

        previous_clipboard = None
        has_previous_clipboard = False
        try:
            previous_clipboard = pyperclip.paste()
            has_previous_clipboard = True
        except pyperclip.PyperclipException:
            pass

        pyperclip.copy(text)
        time.sleep(0.05)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.05)

        if has_previous_clipboard:
            try:
                pyperclip.copy(previous_clipboard)
            except pyperclip.PyperclipException:
                pass

if __name__ == "__main__":
    # python -m scripts.tools
    print("Testing tools.py...")
    
    # Test VisionPerceptor
    try:
        print("Testing VisionPerceptor...")
        vision = VisionPerceptor()
        # Need to pass mouse coordinates now
        global_img, local_img, coord_map, mouse_id, nearest_global_id = vision.capture_state(500, 500)
        print(f"Capture successful.")
        print(f"Global size: {global_img.size}")
        print(f"Local size: {local_img.size}")
        print(f"Map size: {len(coord_map)}")
        print(f"Mouse ID: {mouse_id}")
        print(f"Nearest Global ID: {nearest_global_id}")
        print(f"Sample G point: {list(coord_map.keys())[0]} -> {list(coord_map.values())[0]}")
    except Exception as e:
        print(f"VisionPerceptor test failed: {e}")

    # Test ActionExecutor
    try:
        print("Testing ActionExecutor...")
        executor = ActionExecutor()

        # Test mouse correction
        print("Testing mouse correction...")
        time.sleep(3)
        result = executor.get_mouse_position()
        print(result)
        
        # Mock map
        mock_map = {"L-00-00": (1000, 800), "L-00-01": (15, 15), "L-00-02": (500, 50)}
        
        # Test move
        print("Testing move...")
        result = executor.execute({"action_type": "move", "point_id": "L-00-00"}, mock_map)
        print(result)

        # Test click
        print("Testing click...")
        result = executor.execute({'action_type': 'click', 'button': 'left', 'repeat': 1}, mock_map)
        print(result)

        # Test type (ASCII)
        print("Testing type (ASCII)...")
        result = executor.execute({"action_type": "type", "text": "111", "submit": True}, mock_map)
        print(result)

        # Test type (Non-ASCII)
        print("Testing type (Non-ASCII)...")
        result = executor.execute({"action_type": "type", "text": "你好"}, mock_map)
        print(result)

        # Test drag (simulated)
        print("Testing drag (simulated)...")
        # 1. Move to start
        executor.execute({"action_type": "move", "point_id": "L-00-01"}, mock_map)
        # 2. Mouse down
        result = executor.execute({"action_type": "mouse_down", "button": "left"}, mock_map)
        print(result)
        # 3. Move to end
        executor.execute({"action_type": "move", "point_id": "L-00-02"}, mock_map)
        # 4. Mouse up
        result = executor.execute({"action_type": "mouse_up", "button": "left"}, mock_map)
        print(result)

        # Test double_click
        print("Testing double click...")
        result = executor.execute({'action_type': 'double_click'}, mock_map)
        print(result)

        # Test scroll
        print("Testing scroll...")
        executor.execute({"action_type": "move", "point_id": "L-00-00"}, mock_map)
        executor.execute({'action_type': 'click', 'button': 'left', 'repeat': 1}, mock_map)
        result = executor.execute({"action_type": "scroll", "direction": "down", "amount": "page"}, mock_map)
        result = executor.execute({"action_type": "scroll", "direction": "down", "amount": "page"}, mock_map)
        result = executor.execute({"action_type": "scroll", "direction": "down", "amount": "page"}, mock_map)
        result = executor.execute({"action_type": "scroll", "direction": "down", "amount": "page"}, mock_map)
        result = executor.execute({"action_type": "scroll", "direction": "down", "amount": "page"}, mock_map)
        result = executor.execute({"action_type": "scroll", "direction": "down", "amount": "page"}, mock_map)
        result = executor.execute({"action_type": "scroll", "direction": "down", "amount": "page"}, mock_map)
        print(result)

        # Test hotkey
        print("Testing hotkey...")
        result = executor.execute({"action_type": "hotkey", "keys": ["ctrl", "v"]}, mock_map)
        print(result)

        # Test wait
        print("Testing wait...")
        result = executor.execute({"action_type": "wait", "seconds": 1.0}, mock_map)
        print(result)

        # Test final_answer
        print("Testing final_answer...")
        result = executor.execute({"action_type": "final_answer", "text": "Test completed."}, mock_map)
        print(result)
        
    except Exception as e:
        print(f"ActionExecutor test failed: {e}")
