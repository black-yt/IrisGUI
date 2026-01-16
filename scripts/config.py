import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# ===========================
# Model Parameters
# ===========================
# Recommended to use strong vision models like gpt-4o or gpt-5.1
LLM_API_ENDPOINT = os.getenv("LLM_API_ENDPOINT")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME")

# ===========================
# Vision Parameters
# ===========================
GRID_STEP = int(os.getenv("GRID_STEP", 100))          # Global grid line spacing, in pixels
LOCAL_GRID_STEP = int(os.getenv("LOCAL_GRID_STEP", 30)) # Local fine grid line spacing
CROP_SIZE = int(os.getenv("CROP_SIZE", 500))          # Local screenshot width/height, in pixels
GRID_COLOR = os.getenv("GRID_COLOR", "red")           # Grid marker color
GRID_WIDTH = int(os.getenv("GRID_WIDTH", 1))          # Grid marker line width
MOUSE_COLOR = os.getenv("MOUSE_COLOR", "blue")        # Mouse marker color
MOUSE_WIDTH = int(os.getenv("MOUSE_WIDTH", 5))        # Mouse marker line width

# ===========================
# Runtime Parameters
# ===========================
MAX_STEPS = int(os.getenv("MAX_STEPS", 100))          # Max steps per task to prevent infinite loops
DEBUG_MODE = os.getenv("DEBUG_MODE", "True").lower() == "true" # Whether to save screenshots locally

# ===========================
# Memory Parameters
# ===========================
MAX_LONG_MEMORY = int(os.getenv("MAX_LONG_MEMORY", 10))     # Max long-term memory count
MAX_SHORT_MEMORY = int(os.getenv("MAX_SHORT_MEMORY", 10))    # Max short-term memory count
COMPRESSION_RATIO = int(os.getenv("COMPRESSION_RATIO", 5))    # Compress every 5 messages into 1

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
