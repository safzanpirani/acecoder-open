import os

# --- API Configuration ---
# Load API Key from environment variable (recommended for security)
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

# OpenRouter Headers (Optional)
# Set env vars OPENROUTER_REFERRER_URL and OPENROUTER_SITE_TITLE if you want these
OPENROUTER_REFERRER_URL = os.environ.get("OPENROUTER_REFERRER_URL", "acecoder.dev")
OPENROUTER_SITE_TITLE = os.environ.get("OPENROUTER_SITE_TITLE", "AceCoder")

# --- Model Configuration ---
# You can find model identifiers at https://openrouter.ai/models
# Ensure the models support multimodal inputs (image and text)
DEFAULT_MODEL_NAME = "google/gemini-2.5-pro-preview-03-25"        # Main model for standard processing
DETECTION_MODEL_NAME = "google/gemini-2.0-flash-lite-001" # Model for content detection (needs to be fast)
FAST_MODEL_NAME = "google/gemini-2.5-pro-preview-03-25"            # Model for fast processing (skips detection)

# Default content type to assume when using fast mode (skipping detection)
# Options: "coding", "multiple_choice", "debugging", "system_design", "general"
FAST_MODE_DEFAULT_CONTENT_TYPE = "general"

# Model Generation Parameters
DEFAULT_TEMPERATURE = 0.1  # Lower temperature for more deterministic outputs
DEFAULT_MAX_TOKENS = 8192  # Max tokens for the response

# API Request Settings
DEFAULT_RETRY_COUNT = 2    # Number of retries for failed API calls
DEFAULT_TIMEOUT = 120      # Timeout in seconds for API requests

# --- Application Settings ---
# Logging
MAX_LOG_SIZE_MB = 50       # Maximum size for log files in megabytes

# Screenshotting
SCREENSHOT_DELAY_MS = 100 # Delay in milliseconds before taking screenshot after hiding overlay

# Overlay Window
OVERLAY_MOVEMENT_STEP = 50 # Pixels to move the overlay window with hotkeys

# --- Hotkeys ---
# Format: Use lowercase letters. Modifiers: ctrl, shift, alt, cmd (macOS only for cmd)
# Examples: 'ctrl+shift+h', 'alt+enter'
# Note: Key names might vary slightly between Windows ('enter') and macOS ('<enter>') for pynput.
# The HotkeyHandler in main.py attempts to normalize common differences.
HOTKEY_CAPTURE = 'ctrl+shift+h'
HOTKEY_PROCESS = 'ctrl+shift+enter'
HOTKEY_PROCESS_FAST = 'alt+shift+enter' # New hotkey for fast mode
HOTKEY_TOGGLE_VISIBILITY = 'ctrl+b'
HOTKEY_MOVE_LEFT = 'ctrl+alt+left'
HOTKEY_MOVE_RIGHT = 'ctrl+alt+right'
HOTKEY_MOVE_UP = 'ctrl+alt+up'
HOTKEY_MOVE_DOWN = 'ctrl+alt+down'
HOTKEY_TOGGLE_CAPTURE_VISIBILITY = 'ctrl+shift+v'
HOTKEY_RESET_SCREENSHOTS = 'ctrl+shift+r'
HOTKEY_FOLLOW_UP = 'ctrl+l'
HOTKEY_FOCUS_OVERLAY = 'ctrl+shift+l'

# --- Mock Mode ---
# Set to True to simulate API responses without actual calls (for testing UI)
MOCK_MODE = False 