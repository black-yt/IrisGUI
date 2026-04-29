import os
import unittest
from unittest.mock import patch

from PIL import Image

os.environ.setdefault("LLM_API_ENDPOINT", "http://example.invalid/v1")
os.environ.setdefault("LLM_API_KEY", "sk-test")
os.environ.setdefault("LLM_MODEL_NAME", "fake-model")
os.environ.setdefault("GRID_STEP", "100")
os.environ.setdefault("LOCAL_GRID_STEP", "20")
os.environ.setdefault("CROP_SIZE", "400")
os.environ.setdefault("GRID_COLOR", "red")
os.environ.setdefault("GRID_WIDTH", "1")
os.environ.setdefault("MOUSE_COLOR", "white")
os.environ.setdefault("MOUSE_WIDTH", "4")
os.environ.setdefault("MAX_STEPS", "100")
os.environ.setdefault("DEBUG_MODE", "False")
os.environ.setdefault("MEMORY_SHORT_TOKEN_BUDGET", "128000")
os.environ.setdefault("MEMORY_LONG_TOKEN_BUDGET", "128000")
os.environ.setdefault("MEMORY_RECENT_INTERACTIONS_TO_KEEP", "3")
os.environ.setdefault("MEMORY_CHARS_PER_TOKEN", "4")

import scripts.tools as tools


class VisionGridLabelTests(unittest.TestCase):
    def test_global_grid_uses_larger_border_and_prefix_labels(self):
        old_grid_color = tools.GRID_COLOR
        tools.GRID_COLOR = "red"
        try:
            perceptor = tools.VisionPerceptor.__new__(tools.VisionPerceptor)
            processed, coordinate_map = perceptor._draw_grid_with_labels(
                Image.new("RGB", (80, 60), color="white"),
                step=20,
                prefix="G",
            )
        finally:
            tools.GRID_COLOR = old_grid_color

        self.assertEqual(processed.size, (240, 220))
        self.assertEqual(coordinate_map["G-04-03"], (79, 59))
        self.assertTrue(self._has_dark_pixels(self._corner_center(processed, 40, 40)))
        self.assertTrue(self._has_dark_pixels(self._corner_center(processed, processed.width - 40, 40)))
        self.assertTrue(self._has_dark_pixels(self._corner_center(processed, 40, processed.height - 40)))
        self.assertTrue(self._has_dark_pixels(self._corner_center(processed, processed.width - 40, processed.height - 40)))

    def test_local_grid_keeps_original_border_size(self):
        perceptor = tools.VisionPerceptor.__new__(tools.VisionPerceptor)
        processed, coordinate_map = perceptor._draw_grid_with_labels(
            Image.new("RGB", (80, 60), color="white"),
            step=20,
            prefix="L",
        )

        self.assertEqual(processed.size, (160, 140))
        self.assertEqual(coordinate_map["L-04-03"], (79, 59))
        self.assertTrue(self._has_dark_pixels(self._corner_center(processed, 20, 20)))

    def test_nearest_grid_id_uses_closest_clamped_global_point(self):
        perceptor = tools.VisionPerceptor.__new__(tools.VisionPerceptor)

        self.assertEqual(perceptor._nearest_grid_id(149, 51, 500, 300, 100, "G"), "G-01-01")
        self.assertEqual(perceptor._nearest_grid_id(490, 290, 500, 300, 100, "G"), "G-05-03")
        self.assertEqual(perceptor._nearest_grid_id(-10, -10, 500, 300, 100, "G"), "G-00-00")

    def test_local_crop_keeps_mouse_on_exact_local_grid_point_at_screen_edges(self):
        perceptor = tools.VisionPerceptor.__new__(tools.VisionPerceptor)
        screenshot = Image.new("RGB", (500, 300), color="white")

        local_image, left, top, local_mouse_x, local_mouse_y = perceptor._crop_local_view(screenshot, 149, 51)

        self.assertEqual(local_image.size, (tools.CROP_SIZE, tools.CROP_SIZE))
        self.assertEqual((local_mouse_x, local_mouse_y), (200, 200))
        self.assertEqual((left, top), (-51, -149))

    def test_capture_state_restores_callback_when_screenshot_fails(self):
        events = []
        perceptor = tools.VisionPerceptor.__new__(tools.VisionPerceptor)
        perceptor.pre_callback = lambda: events.append("pre")
        perceptor.post_callback = lambda: events.append("post")
        perceptor.last_capture_files = {"global": "old.png", "local": "old.png"}

        with patch("scripts.tools.pyautogui.screenshot", side_effect=RuntimeError("boom")):
            with self.assertRaisesRegex(RuntimeError, "Unable to capture screenshot"):
                perceptor.capture_state(0, 0)

        self.assertEqual(events, ["pre", "post"])
        self.assertIsNone(perceptor.last_capture_files)

    def test_capture_state_restores_callback_when_processing_fails(self):
        events = []
        perceptor = tools.VisionPerceptor.__new__(tools.VisionPerceptor)
        perceptor.pre_callback = lambda: events.append("pre")
        perceptor.post_callback = lambda: events.append("post")
        perceptor.last_capture_files = None
        perceptor._draw_mouse = lambda image, *args, **kwargs: image

        def fail_grid(*args, **kwargs):
            raise RuntimeError("grid fail")

        perceptor._draw_grid_with_labels = fail_grid

        with patch("scripts.tools.pyautogui.screenshot", return_value=Image.new("RGB", (80, 60), color="white")):
            with self.assertRaisesRegex(RuntimeError, "grid fail"):
                perceptor.capture_state(0, 0)

        self.assertEqual(events, ["pre", "post"])

    def test_capture_state_returns_local_mouse_id_and_nearest_global_id(self):
        events = []
        perceptor = tools.VisionPerceptor.__new__(tools.VisionPerceptor)
        perceptor.pre_callback = lambda: events.append("pre")
        perceptor.post_callback = lambda: events.append("post")
        perceptor.last_capture_files = None

        with patch("scripts.tools.pyautogui.screenshot", return_value=Image.new("RGB", (500, 300), color="white")):
            _, local_image, coordinate_map, mouse_grid_id, nearest_global_grid_id = perceptor.capture_state(149, 51)

        self.assertEqual(local_image.size, (tools.CROP_SIZE + 80, tools.CROP_SIZE + 80))
        self.assertEqual(mouse_grid_id, "L-10-10")
        self.assertEqual(nearest_global_grid_id, "G-01-01")
        self.assertEqual(coordinate_map[mouse_grid_id], (149, 51))
        self.assertEqual(events, ["pre", "post"])

    def _corner_center(self, image, center_x, center_y, half_size=10):
        return image.crop(
            (
                center_x - half_size,
                center_y - half_size,
                center_x + half_size,
                center_y + half_size,
            )
        )

    def _has_dark_pixels(self, image):
        for y in range(image.height):
            for x in range(image.width):
                pixel = image.getpixel((x, y))
                if pixel[0] < 80 and pixel[1] < 80 and pixel[2] < 80:
                    return True
        return False


if __name__ == "__main__":
    unittest.main()
