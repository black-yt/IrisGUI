import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# ===========================
# 模型参数
# ===========================
# 建议使用 gpt-4o 或 gpt-5.1 等强视觉模型
LLM_API_ENDPOINT = os.getenv("LLM_API_ENDPOINT")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME")

# ===========================
# 视觉参数
# ===========================
GRID_STEP = int(os.getenv("GRID_STEP", 100))          # 全局网格线的间距，单位像素
LOCAL_GRID_STEP = int(os.getenv("LOCAL_GRID_STEP", 30)) # 局部细网格线的间距
CROP_SIZE = int(os.getenv("CROP_SIZE", 500))          # 局部截图的宽高，单位像素
GRID_COLOR = os.getenv("GRID_COLOR", "red")           # 网格标记的颜色
GRID_WIDTH = int(os.getenv("GRID_WIDTH", 1))          # 网格标记的线宽
MOUSE_COLOR = os.getenv("MOUSE_COLOR", "blue")        # 鼠标标记的颜色
MOUSE_WIDTH = int(os.getenv("MOUSE_WIDTH", 5))        # 鼠标标记的线宽

# ===========================
# 运行参数
# ===========================
MAX_STEPS = int(os.getenv("MAX_STEPS", 100))          # 单次任务最大步数防止死循环
DEBUG_MODE = os.getenv("DEBUG_MODE", "True").lower() == "true" # 是否保存截图到本地

# ===========================
# 记忆参数
# ===========================
MAX_LONG_MEMORY = int(os.getenv("MAX_LONG_MEMORY", 10))     # 最大的长记忆数量
MAX_SHORT_MEMORY = int(os.getenv("MAX_SHORT_MEMORY", 10))    # 最大的短记忆数量
COMPRESSION_RATIO = int(os.getenv("COMPRESSION_RATIO", 5))    # 每5条消息压缩为1条

if __name__ == "__main__":
    print("Testing config.py...")
    print(f"LLM_API_ENDPOINT: {LLM_API_ENDPOINT}")
    print(f"LLM_MODEL_NAME: {LLM_MODEL_NAME}")
    print(f"GRID_STEP: {GRID_STEP}")
    print(f"LOCAL_GRID_STEP: {LOCAL_GRID_STEP}")
    print(f"CROP_SIZE: {CROP_SIZE}")
    print(f"MAX_STEPS: {MAX_STEPS}")
    print(f"DEBUG_MODE: {DEBUG_MODE}")
