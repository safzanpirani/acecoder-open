from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QTextEdit, QLabel, QHBoxLayout, QPushButton, QMenu
from PySide6.QtCore import (Qt, QPoint, Slot, QObject, Signal as QtSignal, QOperatingSystemVersion, 
                           QThread, QTimer, QPropertyAnimation, QEasingCurve, QCoreApplication)
from PySide6.QtGui import QColor, QPalette
from pygments import highlight
from pygments.lexers import get_lexer_by_name, PythonLexer
from pygments.formatters import HtmlFormatter
import markdown
import re
import logging
import sys
import os
from functools import lru_cache

# Set up logging
logger = logging.getLogger(__name__)

# Constants for styling
PYGMENTS_STYLE = """
<style>
    body { color: white; font-family: 'Segoe UI', Arial, sans-serif; }
    h1, h2, h3 { color: #e6e6e6; }
    a { color: #58a6ff; }
    blockquote { border-left: 4px solid #565656; padding-left: 10px; margin-left: 20px; color: #a0a0a0; }
    table { border-collapse: collapse; }
    th, td { border: 1px solid #565656; padding: 6px; }
    th { background-color: #424242; }

    .codehilite pre {
        white-space: pre-wrap;
        word-wrap: break-word;
    }

    /* Pygments styling */
    div.codehilite { background-color: rgba(45,45,45,0.5); padding: 10px; border-radius: 5px; overflow-x: auto; margin: 1em 0; }
    pre { margin: 0; }
    .codehilite .hll { background-color: #49483e }
    .codehilite .c { color: #75715e } /* Comment */
    .codehilite .err { color: #f92672; } /* Error */
    .codehilite .k { color: #66d9ef; font-weight: bold } /* Keyword */
    .codehilite .l { color: #ae81ff } /* Literal */
    .codehilite .n { color: #f8f8f2 } /* Name */
    .codehilite .o { color: #f92672 } /* Operator */
    .codehilite .p { color: #f8f8f2 } /* Punctuation */
    .codehilite .cm { color: #75715e } /* Comment.Multiline */
    .codehilite .cp { color: #75715e } /* Comment.Preproc */
    .codehilite .c1 { color: #75715e } /* Comment.Single */
    .codehilite .cs { color: #75715e } /* Comment.Special */
    .codehilite .ge { font-style: italic } /* Generic.Emph */
    .codehilite .gs { font-weight: bold } /* Generic.Strong */
    .codehilite .kc { color: #66d9ef; font-weight: bold } /* Keyword.Constant */
    .codehilite .kd { color: #66d9ef; font-weight: bold } /* Keyword.Declaration */
    .codehilite .kn { color: #f92672 } /* Keyword.Namespace */
    .codehilite .kp { color: #66d9ef } /* Keyword.Pseudo */
    .codehilite .kr { color: #66d9ef; font-weight: bold } /* Keyword.Reserved */
    .codehilite .kt { color: #66d9ef } /* Keyword.Type */
    .codehilite .ld { color: #e6db74 } /* Literal.Date */
    .codehilite .m { color: #ae81ff } /* Literal.Number */
    .codehilite .s { color: #e6db74 } /* Literal.String */
    .codehilite .na { color: #a6e22e } /* Name.Attribute */
    .codehilite .nb { color: #f8f8f2 } /* Name.Builtin */
    .codehilite .nc { color: #a6e22e; font-weight: bold } /* Name.Class */
    .codehilite .no { color: #66d9ef } /* Name.Constant */
    .codehilite .nd { color: #a6e22e } /* Name.Decorator */
    .codehilite .ni { color: #f8f8f2 } /* Name.Entity */
    .codehilite .ne { color: #a6e22e } /* Name.Exception */
    .codehilite .nf { color: #a6e22e } /* Name.Function */
    .codehilite .nl { color: #f8f8f2 } /* Name.Label */
    .codehilite .nn { color: #f8f8f2 } /* Name.Namespace */
    .codehilite .nx { color: #a6e22e } /* Name.Other */
    .codehilite .py { color: #f8f8f2 } /* Name.Property */
    .codehilite .nt { color: #f92672 } /* Name.Tag */
    .codehilite .nv { color: #f8f8f2 } /* Name.Variable */
    .codehilite .ow { color: #f92672 } /* Operator.Word */
    .codehilite .w { color: #f8f8f2 } /* Text.Whitespace */
    .codehilite .mf { color: #ae81ff } /* Literal.Number.Float */
    .codehilite .mh { color: #ae81ff } /* Literal.Number.Hex */
    .codehilite .mi { color: #ae81ff } /* Literal.Number.Integer */
    .codehilite .mo { color: #ae81ff } /* Literal.Number.Oct */
    .codehilite .sb { color: #e6db74 } /* Literal.String.Backtick */
    .codehilite .sc { color: #e6db74 } /* Literal.String.Char */
    .codehilite .sd { color: #e6db74 } /* Literal.String.Doc */
    .codehilite .s2 { color: #e6db74 } /* Literal.String.Double */
    .codehilite .se { color: #ae81ff } /* Literal.String.Escape */
    .codehilite .sh { color: #e6db74 } /* Literal.String.Heredoc */
    .codehilite .si { color: #e6db74 } /* Literal.String.Interpol */
    .codehilite .sx { color: #e6db74 } /* Literal.String.Other */
    .codehilite .sr { color: #e6db74 } /* Literal.String.Regex */
    .codehilite .s1 { color: #e6db74 } /* Literal.String.Single */
    .codehilite .ss { color: #e6db74 } /* Literal.String.Symbol */
    .codehilite .bp { color: #f8f8f2 } /* Name.Builtin.Pseudo */
    .codehilite .vc { color: #f8f8f2 } /* Name.Variable.Class */
    .codehilite .vg { color: #f8f8f2 } /* Name.Variable.Global */
    .codehilite .vi { color: #f8f8f2 } /* Name.Variable.Instance */
    .codehilite .il { color: #ae81ff } /* Literal.Number.Integer.Long */
</style>
"""

# Windows specific settings
if sys.platform == 'win32':
    try:
        import ctypes
        from ctypes import windll, c_int, byref, sizeof, Structure, POINTER, WINFUNCTYPE, c_void_p, c_bool
        from ctypes.wintypes import DWORD, HWND, ULONG, POINT, RECT, UINT

        class WINDOWCOMPOSITIONATTRIBDATA(Structure):
            _fields_ = [
                ("Attrib", DWORD),
                ("pvData", c_void_p),
                ("cbData", c_int)
            ]

        # Constants for Windows 11
        DWMWA_EXCLUDED_FROM_PEEK = 12
        DWMWA_CLOAK = 13  # This is the key attribute for hiding from captures
        DWMWA_WINDOW_CORNER_PREFERENCE = 33
        DWMWA_SYSTEMBACKDROP_TYPE = 38
        DWM_WINDOW_CORNER_PREFERENCE = 1  # Round corners

        WDA_EXCLUDEFROMCAPTURE = 0x00000011  # Windows 10 1803+ capture exclusion flag
        WCA_EXCLUDED_FROM_LIVEPREVIEW = 1

        # Windows 11 composition attribute for capture exclusion
        ACCENT_ENABLE_BLURBEHIND = 3
        WCA_ACCENT_POLICY = 19

        # Flag to track if we successfully loaded Windows APIs
        WINDOWS_APIS_LOADED = True

    except ImportError as e:
        logger.error(f"Could not import Windows-specific libraries: {e}")
        WINDOWS_APIS_LOADED = False
else:
    WINDOWS_APIS_LOADED = False

# Signal helper for thread-safe UI updates
class SignalHelper(QObject):
    update_text_signal = QtSignal(str)
    append_text_signal = QtSignal(str)
    update_status_signal = QtSignal(str)
    stop_pulse_signal = QtSignal()  # New signal to safely stop the pulse timer

class OverlayWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        logger.debug("Initializing OverlayWindow")
        self.setWindowTitle("Hyper-V Host Service")

        # Basic window flags
        base_flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        self.setWindowFlags(base_flags)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Create signal helper for thread-safe updates
        self.signal_helper = SignalHelper()
        self.signal_helper.update_text_signal.connect(self._update_output_text)
        self.signal_helper.append_text_signal.connect(self._append_output_text)
        self.signal_helper.update_status_signal.connect(self._update_status_text)
        self.signal_helper.stop_pulse_signal.connect(self._stop_pulse_timer, Qt.ConnectionType.QueuedConnection)
        
        # Worker thread for processing follow-up requests
        self.worker_thread = None
        self.pulse_timer = None
        
        # Store exclusion status
        self._excluded_from_capture = True

        # Apply Windows-specific capture exclusion after window is created
        if sys.platform == 'win32' and WINDOWS_APIS_LOADED:
            # Schedule this to run after window is created
            from PySide6.QtCore import QTimer
            QTimer.singleShot(100, self.exclude_from_capture)

        # Current markdown content
        self.current_markdown = ""

        # Set default size and position
        desktop = self.screen().geometry()
        self.resize(int(desktop.width() * 0.25), desktop.height())
        self.move(desktop.width() - self.width(), 0)

        # Create central widget with semi-transparent background
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        # Set semi-transparent dark background
        palette = self.central_widget.palette()
        palette.setColor(QPalette.Window, QColor(30, 30, 30, 25))
        self.central_widget.setPalette(palette)
        self.central_widget.setAutoFillBackground(True)

        # Main layout
        self.layout = QVBoxLayout(self.central_widget)

        # Header with version info and key shortcuts
        self.header = QLabel("acecoder (beta)")
        self.header.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")
        self.header.setAlignment(Qt.AlignCenter)

        # Keyboard shortcuts helper
        self.shortcuts = QLabel(
            "shortcuts: Ctrl+Shift+H=Capture, Ctrl+Shift+Enter=Process, Ctrl+Alt+Arrows=Move, Ctrl+B=Toggle, Ctrl+Shift+R=Reset, Ctrl+L=Follow-up"
        )
        self.shortcuts.setStyleSheet("color: #aaaaaa; font-size: 10px;")
        self.shortcuts.setAlignment(Qt.AlignCenter)
        self.shortcuts.setWordWrap(True)

        # Output area for code and explanations
        self.output_area = QTextEdit()
        self.output_area.setReadOnly(True)
        self.output_area.setStyleSheet("""
            QTextEdit {
                background-color: rgba(40, 40, 40, 10);
                color: white;
                border: 1px solid rgba(60, 60, 60, 10);
                border-radius: 5px;
                padding: 8px;
                font-family: 'JetBrains Mono', 'SF Pro Display', monospace;
                font-size: 15px;
            }
        """)
        
        # Custom context menu for output area that will be excluded from screenshots
        self.output_area.setContextMenuPolicy(Qt.CustomContextMenu)
        self.output_area.customContextMenuRequested.connect(self.show_context_menu)

        # Create the follow-up chat input area at the bottom
        self.follow_up_container = QWidget()
        self.follow_up_container.setMaximumHeight(100)
        self.follow_up_container.setVisible(False)  # Hidden by default
        
        # Use horizontal layout for the follow-up input and submit button
        follow_up_layout = QHBoxLayout(self.follow_up_container)
        follow_up_layout.setContentsMargins(0, 5, 0, 0)
        follow_up_layout.setSpacing(5)
        
        # The follow-up text input
        self.follow_up_input = QTextEdit()
        self.follow_up_input.setPlaceholderText("type your follow-up request here...")
        self.follow_up_input.setStyleSheet("""
            QTextEdit {
                background-color: rgba(30, 30, 30, 150);
                color: white;
                border: 1px solid rgba(80, 80, 80, 150);
                border-radius: 5px;
                padding: 8px;
                font-family: 'JetBrains Mono', 'SF Pro Display', monospace;
                font-size: 14px;
            }
        """)
        self.follow_up_input.setMaximumHeight(80)
        
        # Install an event filter to handle key presses directly in the input
        self.follow_up_input.installEventFilter(self)
        
        # Submit button
        self.submit_button = QPushButton("send")
        self.submit_button.setStyleSheet("""
            QPushButton {
                background-color: #2980b9;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 5px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3498db;
            }
            QPushButton:pressed {
                background-color: #1c6ea4;
            }
        """)
        self.submit_button.setMaximumWidth(80)
        self.submit_button.clicked.connect(self.submit_follow_up)
        
        # Add to horizontal layout
        follow_up_layout.addWidget(self.follow_up_input, 7)  # 70% width
        follow_up_layout.addWidget(self.submit_button, 3)    # 30% width

        # Status bar
        self.status = QLabel("Press CTRL+SHIFT+H to capture screen")
        self.status.setStyleSheet("color: rgba(200, 200, 200, 200); font-style: italic; font-size: 11px;")
        self.status.setAlignment(Qt.AlignCenter)

        # Add widgets to layout
        self.layout.addWidget(self.header)
        self.layout.addWidget(self.shortcuts)
        self.layout.addWidget(self.output_area)
        self.layout.addWidget(self.follow_up_container)  # Add follow-up container instead
        self.layout.addWidget(self.status)

        # Initialize visibility
        self.is_visible = True
        self.show()
        logger.debug("OverlayWindow initialized and shown")

    def exclude_from_capture(self):
        """Apply Windows-specific methods to exclude window from capture but keep visible to user"""
        if not sys.platform == 'win32' or not WINDOWS_APIS_LOADED:
            logger.debug("Skipping Windows-specific capture exclusion")
            return

        try:
            # Get window handle as integer
            if self.winId() is None:
                logger.error("Window ID is None")
                return

            hwnd = int(self.winId())

            # Use ONLY SetWindowDisplayAffinity which makes window invisible to capture but visible to user
            # DO NOT use DwmSetWindowAttribute with DWMWA_CLOAK which makes window completely invisible
            try:
                # Define the SetWindowDisplayAffinity function
                SetWindowDisplayAffinity = windll.user32.SetWindowDisplayAffinity
                SetWindowDisplayAffinity.restype = c_bool
                SetWindowDisplayAffinity.argtypes = [HWND, DWORD]

                # Apply the capture exclusion flag
                result = SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
                if result:
                    logger.debug("Applied Window Display Affinity exclusion")
                    self._excluded_from_capture = True
                else:
                    error = windll.kernel32.GetLastError()
                    logger.error(f"Failed to set Window Display Affinity: error {error}")
            except Exception as e:
                logger.error(f"Error applying Window Display Affinity: {e}")

        except Exception as e:
            logger.error(f"Failed to exclude window from capture: {e}")

    def showEvent(self, event):
        """Override show event to reapply capture exclusion each time window is shown"""
        super().showEvent(event)
        # Re-apply exclusion flags when window is shown
        if sys.platform == 'win32' and WINDOWS_APIS_LOADED:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(100, self.exclude_from_capture)

    def toggle_capture_visibility(self):
        """Toggle whether the window appears in screenshots/recordings"""
        if not sys.platform == 'win32' or not WINDOWS_APIS_LOADED:
            self.update_status("Capture exclusion only available on Windows")
            return

        try:
            hwnd = int(self.winId())

            # Toggle the state
            self._excluded_from_capture = not self._excluded_from_capture

            # Apply display affinity (most effective method)
            SetWindowDisplayAffinity = windll.user32.SetWindowDisplayAffinity

            # Apply or remove the capture exclusion
            if self._excluded_from_capture:
                result = SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
            else:
                # 0 = normal window behavior, visible in captures
                result = SetWindowDisplayAffinity(hwnd, 0)

            if result:
                status = "excluded from" if self._excluded_from_capture else "visible in"
                self.update_status(f"Window now {status} screen captures")
            else:
                error = windll.kernel32.GetLastError()
                self.update_status(f"Error changing capture visibility: {error}")

        except Exception as e:
            self.update_status(f"Error toggling capture visibility: {e}")

    @Slot()
    def toggle_visibility(self):
        logger.debug("Toggling visibility")
        if self.is_visible:
            self.hide()
            self.is_visible = False
        else:
            self.show()
            self.is_visible = True

    @Slot(str)
    def update_output(self, content):
        """Thread-safe output update"""
        # Only log occasional updates to reduce spam
        if not hasattr(self, '_log_count'):
            self._log_count = 0
        
        self._log_count += 1
        if self._log_count % 20 == 0:  # Only log every 20th update
            logger.debug(f"Updating output (update #{self._log_count})")
            
        self.signal_helper.update_text_signal.emit(content)
        
    @Slot(str)
    def append_output(self, content):
        """Thread-safe output append"""
        # Only log occasional updates to reduce spam
        if not hasattr(self, '_append_log_count'):
            self._append_log_count = 0
        
        self._append_log_count += 1
        if self._append_log_count % 20 == 0:  # Only log every 20th append
            logger.debug(f"Appending output (append #{self._append_log_count})")
            
        self.signal_helper.append_text_signal.emit(content)

    @Slot(str)
    def update_status(self, text):
        """Thread-safe status update"""
        logger.debug(f"Updating status: {text}")
        # Use the signal to ensure thread safety
        self.signal_helper.update_status_signal.emit(text)

    @Slot(str)
    def _update_status_text(self, text):
        """Update status text (must be called from main thread)"""
        self.status.setText(text)

    @lru_cache(maxsize=32)
    def markdown_to_html(self, md_text):
        """Convert markdown to HTML with syntax highlighting"""
        try:
            # Use global style instead of creating it every time
            pygments_style = PYGMENTS_STYLE
            
            # Create markdown processor once and reuse
            if not hasattr(self, '_markdown_processor'):
                logger.debug("Initializing markdown processor")
                self._markdown_processor = markdown.Markdown(
                    extensions=[
                        'fenced_code',
                        'tables',
                        'nl2br',
                        CodeBlockExtension()
                    ]
                )
            
            # Preprocess code blocks to apply syntax highlighting
            preprocessed_text = self.preprocess_code_blocks(md_text)
            
            # Convert to HTML using the cached processor
            html = self._markdown_processor.convert(preprocessed_text)
            
            # Reset the processor to clear any state
            self._markdown_processor.reset()
            
            # Use the full HTML document format with styling
            full_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                {pygments_style}
                <style>
                    body {{ 
                        background-color: rgba(40, 40, 40, 0.1);
                        color: white;
                        font-family: 'Segoe UI', Arial, sans-serif;
                        padding: 0;
                        margin: 0;
                    }}
                    pre, code, .codehilite {{
                        font-family: 'JetBrains Mono', 'Consolas', monospace;
                    }}
                    h1 {{ font-size: 24px; margin-top: 10px; }}
                    h2 {{ font-size: 20px; margin-top: 8px; }}
                    h3 {{ font-size: 16px; margin-top: 6px; }}
                    p {{ margin: 8px 0; }}
                    ul, ol {{ margin: 8px 0; padding-left: 20px; }}
                </style>
            </head>
            <body>
                {html}
            </body>
            </html>
            """
            
            return full_html
        except Exception as e:
            logger.error(f"Error converting markdown to HTML: {str(e)}")
            return f"<p>Error rendering markdown: {str(e)}</p><pre>{md_text}</pre>"

    def preprocess_code_blocks(self, text):
        """Process code blocks in markdown for syntax highlighting"""
        # Regular expression to find code blocks with language specification
        pattern = r'```(\w+)?\n(.*?)```'
        
        def replace_code_block(match):
            lang = match.group(1) or 'text'
            code = match.group(2)
            
            # Get the appropriate lexer for the specified language
            try:
                lexer = get_lexer_by_name(lang, stripall=True)
            except:
                lexer = PythonLexer()  # Default to Python if language not recognized
                
            # Highlight the code
            formatter = HtmlFormatter(style='monokai')
            highlighted = highlight(code, lexer, formatter)
            
            # Return the highlighted code with the div wrapper
            return f'<div class="codehilite">{highlighted}</div>'
            
        # Replace all code blocks in the text
        return re.sub(pattern, replace_code_block, text, flags=re.DOTALL)

    # Remove the now-obsolete CodeBlockExtension and CodeBlockPreprocessor classes
    # They are replaced by the more efficient preprocess_code_blocks method

    def highlight_code(self, code):
        """Directly highlight a code snippet without markdown processing"""
        try:
            lexer = PythonLexer()
            formatter = HtmlFormatter(style='monokai')
            return highlight(code, lexer, formatter)
        except Exception as e:
            logger.error(f"Error highlighting code: {e}")
            return f"<pre>{code}</pre>"

    def contextMenuEvent(self, event):
        """Override to prevent default context menu and use our custom one"""
        event.accept()
        
    def show_context_menu(self, pos):
        """Show a custom context menu that's also excluded from screenshots"""
        context_menu = QMenu(self)
        
        # Apply the same exclusion from capture that we use for the main window
        if sys.platform == 'win32' and WINDOWS_APIS_LOADED:
            try:
                # Get window handle as integer
                # The menu might not have a window ID until it's shown, 
                # so we'll set up a one-shot timer to apply the exclusion after showing
                
                # Add copy and select all actions
                copy_action = context_menu.addAction("Copy (Ctrl+C)")
                select_all_action = context_menu.addAction("Select All (Ctrl+A)")
                
                # Show the menu first
                context_menu.aboutToShow.connect(lambda: self._try_exclude_menu_from_capture(context_menu))
                
                # Show the menu and handle action
                action = context_menu.exec_(self.output_area.mapToGlobal(pos))
                
                if action == copy_action:
                    self.output_area.copy()
                elif action == select_all_action:
                    self.output_area.selectAll()
                
                return
            except Exception as e:
                logger.error(f"Error setting up context menu: {e}")
        
        # Fallback to simple menu if exclusion setup fails
        copy_action = context_menu.addAction("Copy (Ctrl+C)")
        select_all_action = context_menu.addAction("Select All (Ctrl+A)")
        
        # Show the menu and handle action
        action = context_menu.exec_(self.output_area.mapToGlobal(pos))
        
        if action == copy_action:
            self.output_area.copy()
        elif action == select_all_action:
            self.output_area.selectAll()
            
    def _try_exclude_menu_from_capture(self, menu):
        """Try to exclude menu from capture after it's shown"""
        if not sys.platform == 'win32' or not WINDOWS_APIS_LOADED:
            return
            
        try:
            if menu.winId() is not None:
                hwnd = int(menu.winId())
                
                # Define the SetWindowDisplayAffinity function
                SetWindowDisplayAffinity = windll.user32.SetWindowDisplayAffinity
                SetWindowDisplayAffinity.restype = c_bool
                SetWindowDisplayAffinity.argtypes = [HWND, DWORD]
                
                # Apply the capture exclusion flag
                result = SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
                if not result:
                    error = windll.kernel32.GetLastError()
                    logger.error(f"Failed to set capture exclusion on context menu: error {error}")
        except Exception as e:
            logger.error(f"Error applying capture exclusion to context menu: {e}")

    @Slot()
    def show_follow_up_input(self):
        """Show the follow-up input area"""
        # Show the follow-up container
        self.follow_up_container.setVisible(True)
        self.follow_up_input.setFocus()
        self.status.setText("Type your follow-up request and press Enter or click Send.")

    def submit_follow_up(self):
        """Submit the follow-up request"""
        follow_up_text = self.follow_up_input.toPlainText().strip()
        if not follow_up_text:
            return
            
        # Hide the follow-up container
        self.follow_up_container.setVisible(False)
        self.follow_up_input.clear()
        
        # Show immediate visual feedback
        self.update_output("# Processing Follow-up Request...\n\n*Please wait while we analyze your follow-up request...*")
        
        # Update status with a more visible message
        self.status.setText("⚡ Processing your follow-up request...")
        self.status.setStyleSheet("""
            color: white; 
            font-weight: bold;
            font-size: 12px;
            background-color: rgba(52, 152, 219, 180);
            border-radius: 3px;
            padding: 3px;
        """)
        
        # Add a pulsing effect to make it very obvious
        # Create a pulse animation for the status bar
        self.pulse_timer = QTimer(self)
        self.pulse_opacity = 180
        self.pulse_increasing = True
        
        def pulse_effect():
            # Change opacity to create a pulsing effect
            if self.pulse_increasing:
                self.pulse_opacity += 5
                if self.pulse_opacity >= 240:
                    self.pulse_opacity = 240
                    self.pulse_increasing = False
            else:
                self.pulse_opacity -= 5
                if self.pulse_opacity <= 180:
                    self.pulse_opacity = 180
                    self.pulse_increasing = True
            
            # Update style with new opacity
            self.status.setStyleSheet(f"""
                color: white; 
                font-weight: bold;
                font-size: 12px;
                background-color: rgba(52, 152, 219, {self.pulse_opacity});
                border-radius: 3px;
                padding: 3px;
            """)
        
        # Connect and start the timer
        self.pulse_timer.timeout.connect(pulse_effect)
        self.pulse_timer.start(50)  # 50ms for smooth animation
        
        # Force UI update before starting processing
        QCoreApplication.processEvents()
        
        # Create a very simple worker thread using a direct approach
        class DirectWorkerThread(QThread):
            # Define signals as class attributes for PySide6 compatibility
            result_ready = QtSignal(str)
            status_update = QtSignal(str)
            
            def __init__(self, parent, follow_up_text):
                super().__init__(parent)
                self.follow_up_text = follow_up_text
                self.parent = parent
                
                # Connect signals to parent methods
                self.result_ready.connect(parent.update_output)
                self.status_update.connect(parent.update_status)
            
            def run(self):
                try:
                    # Import the API client module directly
                    import sys
                    import importlib
                    import traceback
                    from types import MethodType
                    
                    # Add our directory to path if needed
                    current_dir = os.path.dirname(os.path.abspath(__file__))
                    if current_dir not in sys.path:
                        sys.path.append(current_dir)
                    
                    # Import the API client
                    from api_client import ApiClient
                    
                    # Create an API client instance for the follow-up call
                    api_client = ApiClient()
                    
                    # Store references to the original methods
                    original_output_update = api_client.output_update_signal
                    original_status_update = api_client.status_update_signal
                    
                    # Connect our signals to capture the API client's output
                    # This is a workaround for signals that we can't override
                    def connect_signals():
                        # Define handlers to forward to our signals
                        def output_handler(text):
                            self.result_ready.emit(text)
                            
                        def status_handler(text):
                            self.status_update.emit(text)
                        
                        # Connect to our handlers - save the connections to disconnect later
                        conn1 = api_client.output_update_signal.connect(output_handler)
                        conn2 = api_client.status_update_signal.connect(status_handler)
                        return conn1, conn2
                    
                    # Connect our signal handlers
                    connections = connect_signals()
                    
                    # Emit debug message to confirm signal connections are working
                    self.result_ready.emit("# Processing Follow-up Request\n\nConnecting to API to process your request. Please wait...")
                    
                    # Process follow-up - output will be captured by our signal handlers
                    self.status_update.emit("Processing follow-up request...")
                    
                    # Set a flag to track if we received any output
                    received_output = False
                    
                    # Create a custom output handler that sets the flag
                    def output_received(text):
                        nonlocal received_output
                        received_output = True
                    
                    # Connect our output tracking handler
                    output_tracker_connection = api_client.output_update_signal.connect(output_received)
                    
                    # Process the follow-up
                    api_client.process_follow_up(self.follow_up_text)
                    
                    # If we didn't receive any output, show a fallback message
                    if not received_output:
                        logger.warning("No output signals received from API client during follow-up")
                        self.result_ready.emit(
                            "# Follow-up Processing Issue\n\n"
                            "The follow-up was processed, but no response was received from the AI.\n\n"
                            "This can happen if:\n"
                            "- The AI service had a temporary issue\n"
                            "- The follow-up request was unclear\n"
                            "- There was an internal processing error\n\n"
                            "Please try again with a more specific follow-up request."
                        )
                except Exception as e:
                    error_text = f"Error in follow-up processing: {str(e)}"
                    error_trace = traceback.format_exc()
                    logger.error(error_text)
                    logger.error(error_trace)
                    self.status_update.emit(f"Error: {str(e)}")
                    self.result_ready.emit(f"# Error Processing Follow-up\n\nThere was an error processing your follow-up:\n\n```\n{str(e)}\n{error_trace}\n```\n\nPlease try again.")
                finally:
                    # Signal to stop the pulse timer
                    # Use QTimer.singleShot which is available in both PyQt and PySide
                    QTimer.singleShot(100, self.parent._stop_pulse_timer)
        
        # Create and start the thread
        self.worker_thread = DirectWorkerThread(self, follow_up_text)
        self.worker_thread.start()

    def eventFilter(self, watched, event):
        """Filter events for the follow-up input to handle Enter key"""
        if watched == self.follow_up_input and event.type() == event.Type.KeyPress:
            key_event = event
            
            # Check for Enter key without Shift
            if key_event.key() == Qt.Key_Return and not key_event.modifiers() & Qt.ShiftModifier:
                # Submit the follow-up
                self.submit_follow_up()
                return True  # Event handled
            # Check for Escape key
            elif key_event.key() == Qt.Key_Escape:
                # Cancel follow-up
                self.follow_up_container.setVisible(False)
                self.follow_up_input.clear()
                self.status.setText("Follow-up cancelled.")
                return True  # Event handled
                
        # Pass other events to the default handler
        return super().eventFilter(watched, event)
        
    def keyPressEvent(self, event):
        """Handle key press events for the main window"""
        # Global keyboard shortcuts
        if self.follow_up_container.isVisible() and event.key() == Qt.Key_Escape:
            # Cancel follow-up on ESC
            self.follow_up_container.setVisible(False)
            self.follow_up_input.clear()
            self.status.setText("Follow-up cancelled.")
            event.accept()
        else:
            super().keyPressEvent(event)

    @Slot(str)
    def _update_output_text(self, content):
        """This method is safely called in the UI thread via signal"""
        try:
            html_content = self.markdown_to_html(content)
            self.output_area.setHtml(html_content)
            # Auto-scroll to bottom
            self.output_area.verticalScrollBar().setValue(
                self.output_area.verticalScrollBar().maximum()
            )
        except Exception as e:
            logger.error(f"Error updating output: {e}")
            self.output_area.setPlainText(f"Error formatting output: {e}\n\n{content}")

    @Slot(str)
    def _append_output_text(self, content):
        """This method is safely called in the UI thread via signal"""
        try:
            # Re-render the entire content for proper markdown formatting
            html_content = self.markdown_to_html(self.current_markdown)
            self.output_area.setHtml(html_content)
            # Auto-scroll to bottom
            self.output_area.verticalScrollBar().setValue(
                self.output_area.verticalScrollBar().maximum()
            )
        except Exception as e:
            logger.error(f"Error appending output: {e}")
            # Fall back to plain text append
            self.output_area.append(content)

    @Slot()
    def _stop_pulse_timer(self):
        """Safely stop the pulse timer from the main thread"""
        try:
            if hasattr(self, 'pulse_timer') and self.pulse_timer is not None:
                if self.pulse_timer.isActive():
                    self.pulse_timer.stop()
                self.pulse_timer = None
                
            # Reset status bar style
            self.status.setStyleSheet("color: rgba(200, 200, 200, 200); font-style: italic; font-size: 11px;")
        except Exception as e:
            logger.error(f"Error stopping pulse timer: {e}")
            # Try to reset the status bar style anyway
            try:
                self.status.setStyleSheet("color: rgba(200, 200, 200, 200); font-style: italic; font-size: 11px;")
            except:
                pass

# Create the CodeBlockExtension class for compatibility
class CodeBlockExtension(markdown.extensions.Extension):
    def extendMarkdown(self, md):
        # This is now a no-op since we're preprocessing the code blocks
        pass
