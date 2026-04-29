import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()


def _get_int(name, default):
    value = os.getenv(name)
    return default if value is None or value == "" else int(value)


def _get_float(name, default):
    value = os.getenv(name)
    return default if value is None or value == "" else float(value)


def _get_bool(name, default=False):
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.lower() == "true"


# ===========================
# Model Parameters
# ===========================
LLM_API_ENDPOINT = os.getenv("LLM_API_ENDPOINT")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME")
LLM_TIMEOUT_SECONDS = _get_float("LLM_TIMEOUT_SECONDS", 0.0)  # 0 disables explicit timeout
LLM_MAX_RETRIES = _get_int("LLM_MAX_RETRIES", 1)

# ===========================
# Vision Parameters
# ===========================
GRID_STEP = _get_int("GRID_STEP", 100)                    # Global grid line spacing, in pixels
LOCAL_GRID_STEP = _get_int("LOCAL_GRID_STEP", 20)         # Local fine grid line spacing
CROP_SIZE = _get_int("CROP_SIZE", 400)                    # Local screenshot width/height, in pixels
GRID_COLOR = os.getenv("GRID_COLOR", "red")               # Grid marker color
GRID_WIDTH = _get_int("GRID_WIDTH", 1)                    # Grid marker line width
MOUSE_COLOR = os.getenv("MOUSE_COLOR", "white")           # Mouse marker color
MOUSE_WIDTH = _get_int("MOUSE_WIDTH", 4)                  # Mouse marker line width

# ===========================
# Runtime Parameters
# ===========================
MAX_STEPS = _get_int("MAX_STEPS", 100)                    # Max steps per task to prevent infinite loops
DEBUG_MODE = _get_bool("DEBUG_MODE", False)               # Whether to save screenshots locally
ACTION_SETTLE_SECONDS = _get_float("ACTION_SETTLE_SECONDS", 0.2)
TYPE_INTERVAL_SECONDS = _get_float("TYPE_INTERVAL_SECONDS", 0.01)
CLIPBOARD_TEXT_THRESHOLD = _get_int("CLIPBOARD_TEXT_THRESHOLD", 30)
SCROLL_LINE_CLICKS = _get_int("SCROLL_LINE_CLICKS", 100)
SCROLL_HALF_CLICKS = _get_int("SCROLL_HALF_CLICKS", 200)
SCROLL_PAGE_CLICKS = _get_int("SCROLL_PAGE_CLICKS", 400)

# ===========================
# Memory Parameters
# ===========================
MEMORY_SHORT_TOKEN_BUDGET = _get_int("MEMORY_SHORT_TOKEN_BUDGET", 128000)
MEMORY_LONG_TOKEN_BUDGET = _get_int("MEMORY_LONG_TOKEN_BUDGET", 128000)
MEMORY_RECENT_INTERACTIONS_TO_KEEP = _get_int("MEMORY_RECENT_INTERACTIONS_TO_KEEP", 3)
MEMORY_CHARS_PER_TOKEN = _get_float("MEMORY_CHARS_PER_TOKEN", 4.0)


def openai_client_kwargs():
    kwargs = {
        "api_key": LLM_API_KEY,
        "base_url": LLM_API_ENDPOINT,
        "max_retries": LLM_MAX_RETRIES,
    }
    if LLM_TIMEOUT_SECONDS > 0:
        kwargs["timeout"] = LLM_TIMEOUT_SECONDS
    return kwargs

if __name__ == "__main__":
    # python -m scripts.config
    print("Testing config.py...")
    print(f"LLM_API_ENDPOINT: {LLM_API_ENDPOINT}")
    print(f"LLM_MODEL_NAME: {LLM_MODEL_NAME}")
    print(f"GRID_STEP: {GRID_STEP}")
    print(f"LOCAL_GRID_STEP: {LOCAL_GRID_STEP}")
    print(f"CROP_SIZE: {CROP_SIZE}")
    print(f"MAX_STEPS: {MAX_STEPS}")
    print(f"DEBUG_MODE: {DEBUG_MODE}")
    print(f"MEMORY_SHORT_TOKEN_BUDGET: {MEMORY_SHORT_TOKEN_BUDGET}")
    print(f"MEMORY_LONG_TOKEN_BUDGET: {MEMORY_LONG_TOKEN_BUDGET}")
