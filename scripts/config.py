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


def _get_choice(name, default, choices):
    value = (os.getenv(name) or default).strip().lower() or default
    if value not in choices:
        raise ValueError(f"{name} must be one of: {', '.join(choices)}; got {value!r}")
    return value


# ===========================
# Model Parameters
# ===========================
LLM_API_ENDPOINT = os.getenv("LLM_API_ENDPOINT")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME") or "gpt-6.1-sol"
LLM_TIMEOUT_SECONDS = _get_float("LLM_TIMEOUT_SECONDS", 300.0)  # 0 uses the SDK's default timeout
LLM_MAX_RETRIES = _get_int("LLM_MAX_RETRIES", 1)
LLM_REASONING_EFFORT = _get_choice(
    "LLM_REASONING_EFFORT", "low", ("none", "minimal", "low", "medium", "high", "xhigh", "max", "omit"),
)


def reasoning_request_kwargs():
    """Chat Completions request parameters, separate from client configuration."""
    return {} if LLM_REASONING_EFFORT == "omit" else {"reasoning_effort": LLM_REASONING_EFFORT}

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
MAX_STEPS = _get_int("MAX_STEPS", 500)                    # Max steps per task to prevent infinite loops
DEBUG_MODE = _get_bool("DEBUG_MODE", False)               # Whether to save screenshots locally
LOG_WINDOW_MODE = _get_choice("LOG_WINDOW_MODE", "normal", ("normal", "hidden", "secondary"))
ACTION_SETTLE_SECONDS = _get_float("ACTION_SETTLE_SECONDS", 0.2)
TYPE_INTERVAL_SECONDS = _get_float("TYPE_INTERVAL_SECONDS", 0.01)
CLIPBOARD_TEXT_THRESHOLD = _get_int("CLIPBOARD_TEXT_THRESHOLD", 30)

# ===========================
# Memory Parameters
# ===========================
MEMORY_SHORT_TOKEN_BUDGET = _get_int("MEMORY_SHORT_TOKEN_BUDGET", 256000)
MEMORY_LONG_TOKEN_BUDGET = _get_int("MEMORY_LONG_TOKEN_BUDGET", 256000)
MEMORY_RECENT_INTERACTIONS_TO_KEEP = _get_int("MEMORY_RECENT_INTERACTIONS_TO_KEEP", 3)
MEMORY_CHARS_PER_TOKEN = _get_float("MEMORY_CHARS_PER_TOKEN", 4.0)
MEMORY_IMAGE_ROUNDS = _get_int("MEMORY_IMAGE_ROUNDS", -1)  # Includes the current round; -1 keeps all
if MEMORY_IMAGE_ROUNDS != -1 and MEMORY_IMAGE_ROUNDS < 1:
    raise ValueError("MEMORY_IMAGE_ROUNDS must be -1 or a positive integer")
MEMORY_IMAGE_TOKEN_MULTIPLIER = _get_float("MEMORY_IMAGE_TOKEN_MULTIPLIER", 1.2)
if not 0 < MEMORY_IMAGE_TOKEN_MULTIPLIER < float("inf"):
    raise ValueError("MEMORY_IMAGE_TOKEN_MULTIPLIER must be finite and positive")


_WARNED_INVALID_TLS_ENV_VARS = set()


def _drop_invalid_tls_cert_env_vars():
    for name in ("SSL_CERT_FILE", "CURL_CA_BUNDLE"):
        value = os.environ.get(name)
        if not value or os.path.exists(value):
            continue
        os.environ.pop(name, None)
        if name not in _WARNED_INVALID_TLS_ENV_VARS:
            print(f"Warning: ignored invalid {name}={value!r}; file does not exist.")
            _WARNED_INVALID_TLS_ENV_VARS.add(name)


def openai_client_kwargs():
    _drop_invalid_tls_cert_env_vars()
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
