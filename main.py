import sys
import signal
import time
import logging
# Conditionally import keyboard or pynput
if sys.platform == 'win32':
    try:
        import keyboard
    except ImportError:
        print("Error: keyboard library not found. Please install it using:")
        print("pip install keyboard")
        sys.exit(1)
elif sys.platform == 'darwin':
    try:
        from pynput import keyboard as pynput_keyboard
    except ImportError:
        print("Error: pynput library not found. Please install it using:")
        print("pip install pynput")
        sys.exit(1)
else:
    # Optionally handle other platforms or raise an error
    print(f"Warning: Hotkey support not explicitly implemented for platform '{sys.platform}'.")
    pynput_keyboard = None # Ensure the variable exists
    keyboard = None

from io import BytesIO
from PIL import Image
import threading
from functools import partial
import os
from datetime import datetime
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTimer, QObject, Signal, Slot, Qt

from overlay import OverlayWindow
from api_client import ApiClient  # Import our new ApiClient instead of BackendClient

# Add necessary imports
import subprocess
import tempfile

if sys.platform == 'win32':
    try:
        import mss
        import mss.tools
    except ImportError:
        print("Error: mss not installed. Please run: pip install mss")
        sys.exit(1)

# Platform specific imports
if sys.platform == 'darwin':

    try:
        from Cocoa import NSApplication, NSApp, NSApplicationActivationPolicyAccessory
    except ImportError:
        print("Error: PyObjC not installed. Please run: pip install pyobjc-framework-cocoa")
        sys.exit(1)

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
SCREENSHOT_DELAY_MS = 300 # Increased delay slightly for macOS/screencapture
MOVEMENT_STEP = 50  # Pixels to move the overlay window
# DELAY_SECONDS = 0.5 # Delay for screenshot - replaced by SCREENSHOT_DELAY_MS

class SignalHandler(QObject):
    def __init__(self, app):
        super().__init__()
        self.app = app

    def handle_signal(self, signum, frame):
        logger.info(f"Signal {signum} received, shutting down...")
        self.app.quit()

# Global hotkey handler using platform-specific library
class HotkeyHandler(QObject):
    capture_signal = Signal()
    toggle_signal = Signal()
    process_signal = Signal()
    move_left_signal = Signal()
    move_right_signal = Signal()
    move_up_signal = Signal()
    move_down_signal = Signal()
    toggle_capture_visibility_signal = Signal()
    reset_screenshots_signal = Signal()
    follow_up_signal = Signal()
    focus_signal = Signal()

    def __init__(self):
        super().__init__()
        # pynput specific attributes, initialize only if needed
        self.listener = None
        self.listener_thread = None

    def start_listener(self):
        """Starts the appropriate hotkey listener based on the OS."""
        if sys.platform == 'win32' and keyboard:
            logger.debug("Registering hotkeys using 'keyboard' library (Windows)...")
            # Register hotkeys using keyboard library
            # Use suppress=True to prevent the key press from propagating
            keyboard.add_hotkey('ctrl+shift+h', self.on_capture, suppress=True)
            keyboard.add_hotkey('ctrl+shift+enter', self.on_process, suppress=True)
            keyboard.add_hotkey('ctrl+b', self.on_toggle, suppress=True)
            keyboard.add_hotkey('ctrl+alt+left', self.on_move_left, suppress=True)
            keyboard.add_hotkey('ctrl+alt+right', self.on_move_right, suppress=True)
            keyboard.add_hotkey('ctrl+alt+up', self.on_move_up, suppress=True)
            keyboard.add_hotkey('ctrl+alt+down', self.on_move_down, suppress=True)
            keyboard.add_hotkey('ctrl+shift+v', self.toggle_capture_visibility, suppress=True)
            keyboard.add_hotkey('ctrl+shift+r', self.on_reset_screenshots, suppress=True)
            keyboard.add_hotkey('ctrl+l', self.on_follow_up, suppress=True)
            keyboard.add_hotkey('ctrl+shift+f', self.on_focus, suppress=True)
            logger.info("'keyboard' hotkeys registered.")
            # Note: 'keyboard' library doesn't require a separate listener thread typically.
            # It hooks into the system event loop.

        elif sys.platform == 'darwin' and pynput_keyboard:
            logger.debug("Starting pynput hotkey listener (macOS)...")
            # Define hotkeys map for pynput
            hotkeys_map = {
                '<ctrl>+<shift>+h': self.on_capture,
                '<ctrl>+<shift>+<enter>': self.on_process,
                '<ctrl>+b': self.on_toggle,
                '<ctrl>+<alt>+<left>': self.on_move_left,
                '<ctrl>+<alt>+<right>': self.on_move_right,
                '<ctrl>+<alt>+<up>': self.on_move_up,
                '<ctrl>+<alt>+<down>': self.on_move_down,
                '<ctrl>+<shift>+v': self.toggle_capture_visibility,
                '<ctrl>+<shift>+r': self.on_reset_screenshots,
                '<ctrl>+l': self.on_follow_up,
                '<ctrl>+<shift>+f': self.on_focus
            }

            # Run listener in a separate thread for pynput
            def run_listener():
                try:
                    self.listener = pynput_keyboard.GlobalHotKeys(hotkeys_map)
                    self.listener.start() # Use start() for non-blocking
                    logger.info("pynput GlobalHotKeys listener started.")
                    self.listener.join() # Block this thread until listener stops
                    logger.info("pynput GlobalHotKeys listener stopped.")
                except Exception as e:
                    logger.error(f"Failed to start or run pynput listener: {e}", exc_info=True)

            self.listener_thread = threading.Thread(target=run_listener, daemon=True)
            self.listener_thread.start()

        else:
            logger.warning(f"Hotkey listener not started (unsupported platform '{sys.platform}' or library missing).")

    def stop_listener(self):
        """Stops the appropriate hotkey listener based on the OS."""
        if sys.platform == 'win32' and keyboard:
            logger.info("Unhooking all 'keyboard' hotkeys...")
            try:
                keyboard.unhook_all()
                logger.info("'keyboard' hotkeys unhooked.")
            except Exception as e:
                 logger.error(f"Error unhooking 'keyboard' hotkeys: {e}", exc_info=True)

        elif sys.platform == 'darwin' and pynput_keyboard:
            if self.listener:
                logger.info("Stopping pynput hotkey listener...")
                try:
                    self.listener.stop()
                    if self.listener_thread and self.listener_thread.is_alive():
                        self.listener_thread.join(timeout=1.0)
                        if self.listener_thread.is_alive():
                            logger.warning("pynput listener thread did not exit cleanly.")
                except Exception as e:
                    logger.error(f"Error stopping pynput listener: {e}", exc_info=True)
                self.listener = None
                self.listener_thread = None
                logger.info("pynput listener stopped.")
            else:
                logger.debug("pynput listener was not running.")
        else:
             logger.debug("No active hotkey listener to stop for this platform.")

    # --- Signal emitting methods ---
    def on_capture(self):
        logger.debug("Capture hotkey pressed: <ctrl>+<shift>+h")
        self.capture_signal.emit()

    def on_toggle(self):
        logger.debug("Toggle visibility hotkey pressed: <ctrl>+b")
        self.toggle_signal.emit()

    def on_process(self):
        logger.debug("Process hotkey pressed: <ctrl>+<shift>+<enter>")
        self.process_signal.emit()

    def on_move_left(self):
        logger.debug("Move left hotkey pressed: <ctrl>+<alt>+<left>")
        self.move_left_signal.emit()

    def on_move_right(self):
        logger.debug("Move right hotkey pressed: <ctrl>+<alt>+<right>")
        self.move_right_signal.emit()

    def on_move_up(self):
        logger.debug("Move up hotkey pressed: <ctrl>+<alt>+<up>")
        self.move_up_signal.emit()

    def on_move_down(self):
        logger.debug("Move down hotkey pressed: <ctrl>+<alt>+<down>")
        self.move_down_signal.emit()

    def toggle_capture_visibility(self):
        logger.debug("Toggle capture visibility hotkey pressed: <ctrl>+<shift>+v")
        self.toggle_capture_visibility_signal.emit()

    def on_reset_screenshots(self):
        logger.debug("Reset screenshots hotkey pressed: <ctrl>+<shift>+r")
        self.reset_screenshots_signal.emit()

    def on_follow_up(self):
        logger.debug("Follow-up hotkey pressed: <ctrl>+l")
        self.follow_up_signal.emit()

    def on_focus(self):
        logger.debug("Focus overlay hotkey pressed: <ctrl>+<shift>+f")
        self.focus_signal.emit()

# Screenshot and navigation functions
def take_screenshot(overlay):
    """Hides overlay and triggers delayed capture."""
    logger.debug("Initiating screenshot capture")
    # Hide overlay first
    overlay.hide()

    # Schedule the actual screenshot after a delay to ensure overlay is hidden
    QTimer.singleShot(SCREENSHOT_DELAY_MS, partial(delayed_capture, overlay))

def delayed_capture(overlay):
    """Performs the actual screen capture using platform-specific methods."""
    logger.debug("Delayed capture executing")
    image_bytes = None
    try:
        if sys.platform == 'darwin':
            # macOS implementation using screencapture utility
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
                tmp_filename = tmp_file.name
            logger.debug(f"Using temporary file for screenshot: {tmp_filename}")

            # Command: screencapture -x (no sound, no cursor) <filename>
            command = ["screencapture", "-x", tmp_filename]

            try:
                # Run the command
                result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=10)
                logger.debug(f"screencapture command executed successfully.")
                # Optional: Check result.stderr for potential warnings, though usually empty on success
                if result.stderr:
                    logger.warning(f"screencapture stderr: {result.stderr.strip()}")

                # Read the captured image file using PIL
                with Image.open(tmp_filename) as img:
                    logger.debug(f"Screenshot opened from {tmp_filename} (mode: {img.mode}, size: {img.size})")
                    # Convert to RGB if it has alpha (PNGs often do)
                    if img.mode == 'RGBA':
                        logger.debug("Converting image from RGBA to RGB")
                        img = img.convert('RGB')

                    # Save to BytesIO buffer as WEBP
                    buffer = BytesIO()
                    img.save(buffer, format="WEBP", quality=70)
                    image_bytes = buffer.getvalue()
                    logger.debug(f"Screenshot saved to buffer as WEBP (size: {len(image_bytes)} bytes)")

            except FileNotFoundError:
                 logger.error("Error: 'screencapture' command not found. Ensure macOS is running and the command is in PATH.")
                 overlay.update_status("Error: screencapture command not found.")
                 return # Stop processing this screenshot attempt
            except subprocess.CalledProcessError as e:
                # Log error details from the failed command
                logger.error(f"screencapture command failed with return code {e.returncode}")
                if e.stdout:
                    logger.error(f"stdout: {e.stdout.strip()}")
                if e.stderr:
                    logger.error(f"stderr: {e.stderr.strip()}")
                overlay.update_status(f"Screenshot failed (screencapture error {e.returncode}).")
                return # Stop processing this screenshot attempt
            except subprocess.TimeoutExpired:
                logger.error("screencapture command timed out after 10 seconds.")
                overlay.update_status("Screenshot failed (timeout).")
                return # Stop processing this screenshot attempt
            except Exception as e:
                 logger.error(f"Error processing screenshot file {tmp_filename}: {e}", exc_info=True)
                 overlay.update_status(f"Error reading screenshot: {e}")
                 return # Stop processing this screenshot attempt
            finally:
                # Clean up the temporary file regardless of success/failure reading it
                if os.path.exists(tmp_filename):
                    try:
                        os.remove(tmp_filename)
                        logger.debug(f"Removed temporary file: {tmp_filename}")
                    except OSError as e:
                        logger.warning(f"Could not remove temporary screenshot file {tmp_filename}: {e}")

        elif sys.platform == 'win32':
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
                    #QApplication.instance().screenshots.append(image_bytes)

                    # Update status
                    overlay.update_status(f"Screenshot {len(QApplication.instance().screenshots)} captured. Press CTRL+SHIFT+ENTER to process.")

                    # Show overlay again
                    overlay.show()
            except Exception as e:
                logger.error(f"Screenshot error: {e}")
                overlay.update_status(f"Screenshot error: {e}")
                overlay.show()

        else:
             logger.warning(f"Screenshot functionality not supported on platform: {sys.platform}")
             overlay.update_status(f"Screenshot not supported on this OS ({sys.platform}).")
             return # Stop processing

        # If we got image_bytes, store it
        if image_bytes:
            app_instance = QApplication.instance()
            if not hasattr(app_instance, 'screenshots'):
                app_instance.screenshots = [] # Initialize if somehow missing
            app_instance.screenshots.append(image_bytes)
            screenshot_count = len(app_instance.screenshots)
            overlay.update_status(f"Screenshot {screenshot_count} captured. Press CTRL+SHIFT+ENTER to process.")
            logger.info(f"Screenshot {screenshot_count} captured and stored.")
        else:
            # This case should ideally be covered by the returns above, but as a fallback:
            logger.warning("Screenshot capture resulted in no image data.")
            overlay.update_status("Screenshot capture failed to produce image.")

    except Exception as e:
        # General error catching for the whole function
        logger.error(f"Unexpected error during delayed_capture: {e}", exc_info=True)
        overlay.update_status(f"Screenshot error: {e}")
    finally:
        # Ensure overlay is shown again, even if errors occurred
        if not overlay.isVisible():
             logger.debug("Showing overlay after capture attempt.")
             overlay.show()

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
    # --- macOS Specific Setup ---
    # Moved policy setting to after QApplication init
    # if sys.platform == 'darwin':
    #     # Hide Dock icon by setting activation policy BEFORE QApplication init
    #     try:
    #         logger.debug("Setting macOS Activation Policy to Accessory")
    #         app_instance = NSApplication.sharedApplication()
    #         app_instance.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    #         logger.debug("macOS Activation Policy set.")
    #     except Exception as e:
    #         logger.error(f"Failed to set macOS Activation Policy: {e}")
    # ---------------------------

    # Create Qt application
    app = QApplication(sys.argv)

    # --- macOS Specific Setup (Attempt 2: After QApplication) ---
    if sys.platform == 'darwin' and 'NSApplication' in globals(): # Check if import succeeded
        try:
            logger.debug("Attempting to set macOS Activation Policy to Accessory (after QApplication init)")
            # NSApp should be available now
            NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
            logger.info("macOS Activation Policy set to Accessory.")
        except Exception as e:
            logger.error(f"Failed to set macOS Activation Policy (after QApplication init): {e}", exc_info=True)
    # ---------------------------------------------------------

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

    # Create and start hotkey handler
    hotkey_handler = HotkeyHandler()
    hotkey_handler.start_listener() # Start the listener thread

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
    hotkey_handler.focus_signal.connect(overlay.bring_to_front)

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
        hotkey_handler.stop_listener() # Stop the appropriate listener

    app.aboutToQuit.connect(cleanup)

    return app.exec()

if __name__ == "__main__":
    try:
        # Platform-specific library check is now done at the top-level import
        # No need for checks here anymore

        sys.exit(main())
    except KeyboardInterrupt:
        logger.info("Application terminated by keyboard interrupt")
