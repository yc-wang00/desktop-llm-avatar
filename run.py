import sys
import os
import json
import mss
import cv2
import numpy as np
import base64
from datetime import datetime
from PyQt5.QtWidgets import QApplication, QLabel, QWidget
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QMovie, QFont
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class AnalysisThread(QThread):
    """Thread for non-blocking LLM analysis"""

    analysis_complete = pyqtSignal(dict)

    def __init__(self, base64_image):
        super().__init__()
        self.base64_image = base64_image

    def run(self):
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": [
                            {
                                "type": "text",
                                "text": "As a cute avatar representing the Razer brand, analyze screenshots and respond with JSON containing 'comment' and 'action'. Actions: 'idle' for normal content, 'engage' for gaming/exciting content. Keep comments under 50 characters, be playful and gaming-focused.",
                            }
                        ],
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": 'Analyze this screen and respond with JSON: {"comment": "your short friendly comment", "action": "idle or engage"}. Use \'engage\' for games, action scenes, or exciting content. Use \'idle\' for normal desktop/browsing.',
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{self.base64_image}"
                                },
                            },
                        ],
                    },
                ],
                response_format={"type": "json_object"},
                temperature=1,
                max_completion_tokens=2048,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0,
            )
            content = response.choices[0].message.content
            result = json.loads(content)
            self.analysis_complete.emit(result)
        except Exception as e:
            print(f"LLM analysis error: {e}")
            fallback = {"comment": "Watching closely! 👀", "action": "idle"}
            self.analysis_complete.emit(fallback)


class PetWindow(QWidget):
    def __init__(self, idle_gif="idle.gif", engage_gif="engage.gif", monitor_index=1):
        super().__init__()
        
        # Monitor selection for multi-screen setups
        self.monitor_index = monitor_index

        # Set window properties for a true desktop overlay
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool  # Hide from taskbar
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow)  # macOS specific

        # Make it slightly transparent
        self.setWindowOpacity(0.95)

        # Force it to be always on top on macOS
        if sys.platform == "darwin":
            try:
                # Try to set the window level higher on macOS
                import objc
                from AppKit import NSApp, NSWindow

                # This is advanced but ensures it stays on top
                self.raise_()
            except ImportError:
                pass  # objc not available, use standard approach

        # Animation setup
        self.animations = {"idle": QMovie(idle_gif), "engage": QMovie(engage_gif)}
        self.current_action = "idle"

        # Create label to show pet animation
        self.pet_label = QLabel(self)
        self.current_movie = self.animations["idle"]
        self.pet_label.setMovie(self.current_movie)
        self.current_movie.start()

        # Resize to native size
        self.resize(self.current_movie.frameRect().size())

        # Create chat bubble (textbox)
        self.text_label = QLabel("Hi! I'm your pet!", self)
        self.text_label.setStyleSheet("""
            QLabel {
                background-color: rgba(255, 255, 255, 240);
                color: #2c3e50;
                border: 2px solid #3498db;
                border-radius: 15px;
                padding: 8px 12px;
                font-weight: bold;
                box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            }
        """)
        self.text_label.setFont(QFont("Segoe UI", 11))
        self.text_label.setWordWrap(True)
        self.text_label.setMaximumWidth(200)
        self.text_label.adjustSize()

        # Position bubble to the right of the pet
        pet_width = self.current_movie.frameRect().width()
        pet_height = self.current_movie.frameRect().height()
        bubble_x = pet_width + 10
        bubble_y = 10
        self.text_label.move(bubble_x, bubble_y)

        # Resize window to include bubble
        total_width = pet_width + self.text_label.width() + 20
        total_height = max(pet_height, self.text_label.height() + 20)
        self.resize(total_width, total_height)
        self.text_label.show()

        self.old_pos = None
        self.show()

        # Auto-hide textbox after 5 seconds (optional)
        QTimer.singleShot(5000, self.text_label.hide)

        # Screen capture setup
        self.sct = mss.mss()
        self.screenshot_count = 0
        
        # Print available monitors
        self.print_available_monitors()
        
        # Validate monitor selection
        if self.monitor_index >= len(self.sct.monitors):
            print(f"Monitor {self.monitor_index} not found, using primary monitor (1)")
            self.monitor_index = 1

        # Create debug directory
        self.debug_dir = "debug_screenshots"
        if not os.path.exists(self.debug_dir):
            os.makedirs(self.debug_dir)
            print(f"Created debug directory: {self.debug_dir}")

        self.analysis_timer = QTimer()
        self.analysis_timer.timeout.connect(self.analyze_screen)
        self.analysis_timer.start(5000)  # Analyze every 5 seconds

        # Lightweight visibility check - only when hidden
        self.visibility_timer = QTimer()
        self.visibility_timer.timeout.connect(self.check_visibility)
        self.visibility_timer.start(2000)  # Check every 2 seconds

        # Track dragging state
        self.is_dragging = False

    def print_available_monitors(self):
        """Print information about available monitors"""
        print("=" * 50)
        print("Available Monitors:")
        print("=" * 50)
        for i, monitor in enumerate(self.sct.monitors):
            if i == 0:
                print(f"Monitor {i}: All monitors combined")
                print(f"  Size: {monitor['width']}x{monitor['height']}")
            else:
                print(f"Monitor {i}: Individual monitor")
                print(f"  Position: ({monitor['left']}, {monitor['top']})")
                print(f"  Size: {monitor['width']}x{monitor['height']}")
        print(f"Currently using: Monitor {self.monitor_index}")
        print("=" * 50)
    
    def check_visibility(self):
        """Ensure window stays visible - only acts if actually hidden"""
        if not self.isVisible():
            print("Window was hidden, restoring...")
            self.show()
            self.raise_()

    def mousePressEvent(self, event):
        """Handle mouse press for dragging"""
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPos()
            self.is_dragging = True

    def mouseMoveEvent(self, event):
        """Handle dragging the pet around"""
        if self.old_pos and self.is_dragging:
            delta = event.globalPos() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPos()

    def mouseReleaseEvent(self, event):
        """Handle mouse release"""
        if event.button() == Qt.LeftButton:
            self.is_dragging = False
            self.old_pos = None

    def showEvent(self, event):
        """Ensure window appears on top when shown"""
        super().showEvent(event)
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        """Clean up when closing"""
        for movie in self.animations.values():
            movie.stop()
        event.accept()

    def update_text(self, message: str, duration: int = 3000):
        # Update text immediately without recalculating layout
        self.text_label.setText(message)
        self.text_label.show()

        # Schedule layout update in next event loop cycle for smooth rendering
        QTimer.singleShot(0, self._update_layout)

        # Hide after duration
        QTimer.singleShot(duration, self.text_label.hide)

    def _update_layout(self):
        """Update layout without blocking UI"""
        self.text_label.adjustSize()

        # Reposition bubble after text change
        pet_width = self.current_movie.frameRect().width()
        bubble_x = pet_width + 10
        bubble_y = 10
        self.text_label.move(bubble_x, bubble_y)

        # Resize window to include new bubble size
        total_width = pet_width + self.text_label.width() + 20
        total_height = max(
            self.current_movie.frameRect().height(), self.text_label.height() + 20
        )
        self.resize(total_width, total_height)

    def switch_animation(self, action):
        """Switch between idle and engage animations"""
        if action not in self.animations or action == self.current_action:
            return

        # Stop current animation
        self.current_movie.stop()

        # Switch to new animation
        self.current_action = action
        self.current_movie = self.animations[action]
        self.pet_label.setMovie(self.current_movie)
        self.current_movie.start()

        # Update window size for new animation
        self.resize(self.current_movie.frameRect().size())
        self._update_layout()

        print(f"Animation switched to: {action}")

    def capture_screen(self):
        """Capture screen for analysis"""
        try:
            monitor = self.sct.monitors[self.monitor_index]
            print(f"Capturing from Monitor {self.monitor_index}: {monitor['width']}x{monitor['height']}")
            screenshot = self.sct.grab(monitor)
            img = np.array(screenshot)
            img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            # Save screenshot locally for debugging
            self.screenshot_count += 1
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            debug_path = os.path.join(
                self.debug_dir,
                f"screenshot_monitor{self.monitor_index}_{timestamp}_{self.screenshot_count:04d}.png",
            )
            cv2.imwrite(debug_path, img_bgr)
            print(f"Saved screenshot: {debug_path}")

            # Encode to base64 for API
            _, buffer = cv2.imencode(".jpg", img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 80])
            base64_image = base64.b64encode(buffer).decode("utf-8")
            return base64_image, debug_path
        except Exception as e:
            print(f"Screen capture error: {e}")
            return None, None

    def analyze_screen(self):
        """Capture and analyze screen, then update pet comment"""
        print("Analyzing screen...")

        # Capture screen
        result = self.capture_screen()
        if not result or not result[0]:
            return

        base64_image, debug_path = result
        print(f"Debug screenshot saved: {debug_path}")

        # Start analysis in background thread
        self.analysis_thread = AnalysisThread(base64_image)
        self.analysis_thread.analysis_complete.connect(self.on_analysis_complete)
        self.analysis_thread.start()

    def on_analysis_complete(self, result):
        """Handle LLM analysis completion"""
        comment = result.get("comment", "Watching closely! 👀")
        action = result.get("action", "idle")

        print(f"Pet comment: {comment}")
        print(f"Pet action: {action}")

        # Switch animation based on action
        self.switch_animation(action)

        # Update text
        self.update_text(comment, duration=8000)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Monitor selection examples:
    # monitor_index=1 -> Primary monitor (default)
    # monitor_index=2 -> Secondary monitor 
    # monitor_index=0 -> All monitors combined
    
    # Change the monitor_index to capture different screens
    pet = PetWindow("assets/idle.gif", "assets/engage.gif", monitor_index=1)
    pet.update_text("Let's win this game!", duration=5000)
    sys.exit(app.exec_())
