import sys
import signal
import time
import logging
import keyboard
from io import BytesIO
from PIL import Image
import mss
import mss.tools
import threading
from functools import partial  # Added for partial function application
import os
from datetime import datetime
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTimer, QObject, Signal, Slot, Qt

from overlay import OverlayWindow
from api_client import ApiClient  # Import our new ApiClient instead of BackendClient

# --- High DPI Scaling --- (Set BEFORE QApplication import)
# Enable High DPI scaling for better rendering on scaled displays
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
os.environ["QT_SCALE_FACTOR"] = "1.25" # Start with 1, adjust if needed
# ----------------------

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.dirname(__file__), 'cognicoder.log'))
    ]
)
logger = logging.getLogger(__name__)

# Disable third-party loggers
logging.getLogger('PIL').setLevel(logging.WARNING)
logging.getLogger('requests').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('websocket').setLevel(logging.WARNING)

# Change to True to test without the backend
MOCK_MODE = False

# API configuration
API_BASE_URL = "http://localhost:5000"

# Constants for screenshot capture
SCREENSHOT_DELAY_MS = 200  # Delay before taking screenshot in milliseconds
MOVEMENT_STEP = 50  # Pixels to move the overlay window
DELAY_SECONDS = 0.5 # Delay for screenshot to avoid capturing the overlay

class SignalHandler(QObject):
    def __init__(self, app):
        super().__init__()
        self.app = app

    def handle_signal(self, signum, frame):
        logger.info(f"Signal {signum} received, shutting down...")
        self.app.quit()

# Global hotkey handler that emits signals for Qt to process
class HotkeyHandler(QObject):
    capture_signal = Signal()
    toggle_signal = Signal()
    process_signal = Signal()
    move_left_signal = Signal()
    move_right_signal = Signal()
    move_up_signal = Signal()
    move_down_signal = Signal()
    toggle_capture_visibility_signal = Signal()
    reset_screenshots_signal = Signal()  # New signal for resetting screenshots
    follow_up_signal = Signal()  # New signal for follow-up dialog

    def __init__(self):
        super().__init__()
        
        # Register hotkeys with suppress=True to prevent them from being passed to other applications
        keyboard.add_hotkey('ctrl+shift+h', self.on_capture, suppress=True)
        keyboard.add_hotkey('ctrl+shift+enter', self.on_process, suppress=True)
        keyboard.add_hotkey('ctrl+b', self.on_toggle, suppress=True)
        keyboard.add_hotkey('ctrl+alt+left', self.on_move_left, suppress=True)
        keyboard.add_hotkey('ctrl+alt+right', self.on_move_right, suppress=True)
        keyboard.add_hotkey('ctrl+alt+up', self.on_move_up, suppress=True)
        keyboard.add_hotkey('ctrl+alt+down', self.on_move_down, suppress=True)
        keyboard.add_hotkey('ctrl+shift+v', self.toggle_capture_visibility, suppress=True)
        keyboard.add_hotkey('ctrl+shift+r', self.on_reset_screenshots, suppress=True)
        keyboard.add_hotkey('ctrl+l', self.on_follow_up, suppress=True)  # New hotkey for follow-up
        
        logger.debug("Hotkeys registered with suppression enabled")

    def on_capture(self):
        logger.debug("Capture hotkey pressed")
        self.capture_signal.emit()

    def on_toggle(self):
        """Toggle overlay visibility"""
        logger.debug("Toggle visibility hotkey pressed")
        self.toggle_signal.emit()

    def on_process(self):
        logger.debug("Process hotkey pressed")
        self.process_signal.emit()

    def on_move_left(self):
        logger.debug("Move left hotkey pressed")
        self.move_left_signal.emit()

    def on_move_right(self):
        logger.debug("Move right hotkey pressed")
        self.move_right_signal.emit()

    def on_move_up(self):
        logger.debug("Move up hotkey pressed")
        self.move_up_signal.emit()

    def on_move_down(self):
        logger.debug("Move down hotkey pressed")
        self.move_down_signal.emit()

    def toggle_capture_visibility(self):
        logger.debug("Toggle capture visibility hotkey pressed")
        self.toggle_capture_visibility_signal.emit()

    def on_reset_screenshots(self):
        """Reset screenshots"""
        logger.debug("Reset screenshots hotkey pressed")
        self.reset_screenshots_signal.emit()

    def on_follow_up(self):
        """Show follow-up dialog"""
        logger.debug("Follow-up hotkey pressed")
        self.follow_up_signal.emit()

# Screenshot and navigation functions
def take_screenshot(overlay):
    logger.debug("Taking screenshot")
    # Hide overlay first
    overlay.hide()

    # Schedule the actual screenshot after a small delay to ensure overlay is hidden
    QTimer.singleShot(SCREENSHOT_DELAY_MS, partial(delayed_capture, overlay))

def delayed_capture(overlay):
    logger.debug("Delayed capture executing")
    try:
        # Take screenshot
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            screenshot = sct.grab(monitor)

            # Convert to PIL Image
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

            # Store screenshot
            buffer = BytesIO()
            img.save(buffer, format="WEBP", quality=70)  # Changed from JPEG to WebP with quality 70
            image_bytes = buffer.getvalue()

            # Store in app global
            QApplication.instance().screenshots.append(image_bytes)

            # Update status
            overlay.update_status(f"Screenshot {len(QApplication.instance().screenshots)} captured. Press CTRL+SHIFT+ENTER to process.")

            # Show overlay again
            overlay.show()
    except Exception as e:
        logger.error(f"Screenshot error: {e}")
        overlay.update_status(f"Screenshot error: {e}")
        overlay.show()  # Ensure overlay is shown even on error

def process_screenshots(overlay):
    logger.debug("Processing screenshots")
    screenshots = QApplication.instance().screenshots

    if not screenshots:
        overlay.update_status("No screenshots to process. Press CTRL+SHIFT+H to capture.")
        return

    overlay.update_status("Processing screenshots...")

    # Reset the output area before starting
    overlay.update_output("# Analyzing Problem...\n\n*Processing your screenshots and generating solution...*")

    if MOCK_MODE:
        # Use mock data for testing without backend
        logger.debug("Using mock data (MOCK_MODE is enabled)")
        mock_output = """# Two Sum

## Problem Description
Given an array of integers `nums` and an integer `target`, return indices of the two numbers such that they add up to target.
You may assume that each input would have exactly one solution, and you may not use the same element twice.
You can return the answer in any order.

## Constraints
- 2 <= nums.length <= 10^4
- -10^9 <= nums[i] <= 10^9
- -10^9 <= target <= 10^9
- Only one valid answer exists

### Problem Analysis
We need to find two indices in the array whose values sum up to the target.

### Solution Strategy
1. Use a hash map to store values we've seen and their indices
2. For each number, check if (target - current number) exists in the hash map
3. If it does, we found our solution
4. Otherwise, add the current number and its index to the hash map

### Complexity Analysis
- Time Complexity: O(n) where n is the length of nums, as we only traverse the array once
- Space Complexity: O(n) in the worst case if we need to store all numbers in the hash map

### Solution Code (Python)
```python
def twoSum(self, nums: List[int], target: int) -> List[int]:
    seen = {}  # value -> index

    for i, num in enumerate(nums):
        complement = target - num

        if complement in seen:
            return [seen[complement], i]

        seen[num] = i

    return []  # No solution found
```

### Solution Code (Java)
```java
public int[] twoSum(int[] nums, int target) {
    Map<Integer, Integer> map = new HashMap<>();

    for (int i = 0; i < nums.length; i++) {
        int complement = target - nums[i];

        if (map.containsKey(complement)) {
            return new int[] { map.get(complement), i };
        }

        map.put(nums[i], i);
    }

    return new int[0]; // No solution found
}
```

### Example Walkthrough
For example, if nums = [2, 7, 11, 15] and target = 9:
1. Start with empty hash map: seen = {}
2. i=0: num=2, complement=7, 7 not in seen, add 2->0 to seen
3. i=1: num=7, complement=2, 2 is in seen with index 0, return [0, 1]

### Additional Test Cases
- nums = [3, 3], target = 6 → Output: [0, 1]
- nums = [3, 2, 4], target = 6 → Output: [1, 2]
- nums = [-1, -2, -3, -4, -5], target = -8 → Output: [2, 4]

### Common Pitfalls
- Be careful with duplicate values: our solution handles this correctly
- Remember that array indices are 0-based
- Make sure to check if the complement exists before adding the current number
"""
        # Simulate async process
        def mock_response():
            time.sleep(1)  # Simulate a short delay
            overlay.update_output(mock_output)
            overlay.update_status("Processing complete. Use Ctrl+Alt+Arrows to move the window.")
            QApplication.instance().screenshots = []  # Clear screenshots after processing

        # Start mock processing in a separate thread
        mock_thread = threading.Thread(target=mock_response)
        mock_thread.daemon = True
        mock_thread.start()
    else:
        # Use the direct API client instead of backend
        try:
            # Use our ApiClient for direct processing
            api_client = ApiClient()
            
            # Connect signals
            api_client.output_update_signal.connect(overlay.update_output)
            api_client.status_update_signal.connect(overlay.update_status)
            
            # Process the images directly
            result = api_client.process_images(screenshots)
            
            # We don't need to store last_problem_data in the app instance anymore
            # since we're using static class variables in ApiClient
            
            # Processing continues asynchronously, will update UI via signals
        except Exception as e:
            logger.error(f"Error in API processing: {e}")
            overlay.update_status(f"Error: {str(e)}")
            overlay.update_output(f"# Error Processing Screenshots\n\nThere was an error processing your screenshots:\n\n```\n{str(e)}\n```\n\nPlease try again.")
            QApplication.instance().screenshots = []

def move_overlay(overlay, direction):
    logger.debug(f"Moving overlay: {direction}")
    pos = overlay.pos()

    if direction == 'left':
        overlay.move(pos.x() - MOVEMENT_STEP, pos.y())
    elif direction == 'right':
        overlay.move(pos.x() + MOVEMENT_STEP, pos.y())
    elif direction == 'up':
        overlay.move(pos.x(), pos.y() - MOVEMENT_STEP)
    elif direction == 'down':
        overlay.move(pos.x(), pos.y() + MOVEMENT_STEP)

def reset_screenshots(overlay):
    """Reset/clear all captured screenshots"""
    app = QApplication.instance()
    previous_count = len(app.screenshots) if hasattr(app, 'screenshots') else 0
    
    # Clear screenshots
    app.screenshots = []
    
    # Update UI
    overlay.update_status(f"Screenshots reset. {previous_count} screenshot(s) cleared.")
    
    logger.debug(f"Reset {previous_count} screenshots")

def show_follow_up_dialog(overlay):
    """Show the follow-up input at the bottom of the overlay"""
    # Check if there is context to follow up on using the static solution content variable
    if not ApiClient._last_solution_content:
        logger.debug("Follow-up requested, but no previous context found in _last_solution_content.")
        overlay.update_status("No previous solution to follow up on. Process a problem first.")
        return

    # If context exists, proceed to show the input field in the overlay
    logger.debug("Follow-up requested, context found in _last_solution_content. Showing input.")
    overlay.show_follow_up_input()

def main():
    # Create Qt application
    app = QApplication(sys.argv)

    # Set up signal handling
    signal_handler = SignalHandler(app)

    # Set up signal handlers for SIGINT (Ctrl+C) and SIGTERM
    signal.signal(signal.SIGINT, signal_handler.handle_signal)
    signal.signal(signal.SIGTERM, signal_handler.handle_signal)

    # Install a signal handler for Qt's event loop
    # This ensures signal delivery even during Qt event processing
    timer = QTimer()
    timer.start(500)  # Check for signals every 500ms
    timer.timeout.connect(lambda: None)  # Just wake up the event loop

    # Create overlay window
    overlay = OverlayWindow()

    # Create screenshots list
    app.screenshots = []

    # Create hotkey handler
    hotkey_handler = HotkeyHandler()

    # Connect signals to slots
    hotkey_handler.capture_signal.connect(lambda: take_screenshot(overlay))
    hotkey_handler.toggle_signal.connect(overlay.toggle_visibility)
    hotkey_handler.process_signal.connect(lambda: process_screenshots(overlay))
    hotkey_handler.move_left_signal.connect(lambda: move_overlay(overlay, 'left'))
    hotkey_handler.move_right_signal.connect(lambda: move_overlay(overlay, 'right'))
    hotkey_handler.move_up_signal.connect(lambda: move_overlay(overlay, 'up'))
    hotkey_handler.move_down_signal.connect(lambda: move_overlay(overlay, 'down'))
    hotkey_handler.toggle_capture_visibility_signal.connect(overlay.toggle_capture_visibility)
    hotkey_handler.reset_screenshots_signal.connect(lambda: reset_screenshots(overlay))
    hotkey_handler.follow_up_signal.connect(lambda: show_follow_up_dialog(overlay))

    # Initialize UI
    overlay.update_status("Ready. Press CTRL+SHIFT+H to capture screen.")

    # Welcome message with instructions
    welcome_msg = """# Welcome to Acecoder

## Quick Instructions
1. Press **Ctrl+Shift+H** to capture a screenshot of the coding problem
2. Press **Ctrl+Shift+Enter** to process the captured screenshots
3. Use **Ctrl+Alt+Arrow keys** to move this window around
4. Press **Ctrl+B** to hide/show this overlay
5. Press **Ctrl+L** to open the follow-up chat when you need help with the solution

The assistant will analyze the problem and provide a solution. If you have questions or encounter errors with the solution, use the follow-up feature to get additional help without losing context."""

    overlay.update_output(welcome_msg)

    # Create a cleanup handler
    def cleanup():
        logger.info("Cleaning up before exit...")
        keyboard.unhook_all()  # Remove all keyboard hooks

    app.aboutToQuit.connect(cleanup)

    return app.exec()

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.info("Application terminated by keyboard interrupt")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
