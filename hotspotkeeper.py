"""
HotspotKeeper
A lightweight system tray application that automatically enables Windows Mobile Hotspot when WiFi connects.
"""

import sys
import subprocess
import winreg
import os
import ctypes
from pathlib import Path
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QPushButton, QSystemTrayIcon, 
                               QMenu, QCheckBox, QFrame)
from PySide6.QtCore import QTimer, Qt, Signal, QThread
from PySide6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor


def is_admin():
    """Check if the script is running with admin privileges"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def run_as_admin():
    """Re-run the script with admin privileges"""
    if not is_admin():
        try:
            # Get the path to pythonw.exe to run without console
            python_path = sys.executable.replace('python.exe', 'pythonw.exe')
            if not os.path.exists(python_path):
                python_path = sys.executable
            
            script = os.path.abspath(__file__)
            params = ' '.join([script] + sys.argv[1:])
            
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", python_path, params, None, 1
            )
            sys.exit(0)
        except Exception as e:
            print(f"Failed to elevate privileges: {e}")
            sys.exit(1)


class NetworkMonitor(QThread):
    """Monitor network connectivity changes"""
    wifi_connected = Signal()
    wifi_disconnected = Signal()
    
    def __init__(self):
        super().__init__()
        self.running = True
        self.was_connected = False
        
    def run(self):
        while self.running:
            connected = self.check_wifi_connection()
            
            if connected and not self.was_connected:
                self.wifi_connected.emit()
                self.was_connected = True
            elif not connected and self.was_connected:
                self.wifi_disconnected.emit()
                self.was_connected = False
                
            self.msleep(2000)  # Check every 2 seconds
    
    def check_wifi_connection(self):
        """Check if WiFi is connected using netsh"""
        try:
            # Hide console window
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            result = subprocess.run(
                ['netsh', 'wlan', 'show', 'interfaces'],
                capture_output=True,
                text=True,
                timeout=5,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return 'State' in result.stdout and 'connected' in result.stdout.lower()
        except Exception:
            return False
    
    def stop(self):
        self.running = False


class HotspotManager:
    """Manage Windows Mobile Hotspot"""
    
    @staticmethod
    def is_hotspot_enabled():
        """Check if hotspot is currently enabled"""
        try:
            # Hide PowerShell window
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            result = subprocess.run(
                ['powershell', '-Command', 
                 'Get-NetConnectionProfile | Where-Object { $_.NetworkCategory -eq "Public" -and $_.InterfaceAlias -like "*Local*" }'],
                capture_output=True,
                text=True,
                timeout=5,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            # Alternative check using netsh
            result2 = subprocess.run(
                ['netsh', 'wlan', 'show', 'hostednetwork'],
                capture_output=True,
                text=True,
                timeout=5,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return 'started' in result2.stdout.lower()
        except Exception:
            return False
    
    @staticmethod
    def enable_hotspot():
        """Enable Windows Mobile Hotspot"""
        try:
            # Hide PowerShell window
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            # Use PowerShell to enable hotspot
            script = '''
            $connectionProfile = [Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime]::GetInternetConnectionProfile()
            $tetheringManager = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime]::CreateFromConnectionProfile($connectionProfile)
            $result = $tetheringManager.StartTetheringAsync()
            '''
            
            subprocess.run(
                ['powershell', '-Command', script],
                capture_output=True,
                timeout=10,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return True
        except Exception as e:
            print(f"Error enabling hotspot: {e}")
            return False
    
    @staticmethod
    def disable_hotspot():
        """Disable Windows Mobile Hotspot"""
        try:
            # Hide PowerShell window
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            script = '''
            $connectionProfile = [Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime]::GetInternetConnectionProfile()
            $tetheringManager = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime]::CreateFromConnectionProfile($connectionProfile)
            $result = $tetheringManager.StopTetheringAsync()
            '''
            
            subprocess.run(
                ['powershell', '-Command', script],
                capture_output=True,
                timeout=10,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return True
        except Exception as e:
            print(f"Error disabling hotspot: {e}")
            return False


class StartupManager:
    """Manage Windows startup registration"""
    
    REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
    APP_NAME = "HotspotKeeper"
    
    @staticmethod
    def is_startup_enabled():
        """Check if app is registered for startup"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, StartupManager.REG_PATH, 0, winreg.KEY_READ)
            try:
                winreg.QueryValueEx(key, StartupManager.APP_NAME)
                winreg.CloseKey(key)
                return True
            except WindowsError:
                winreg.CloseKey(key)
                return False
        except Exception:
            return False
    
    @staticmethod
    def enable_startup():
        """Add app to Windows startup"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, StartupManager.REG_PATH, 0, winreg.KEY_WRITE)
            
            # Get the path to pythonw.exe to run without console
            python_path = sys.executable.replace('python.exe', 'pythonw.exe')
            if not os.path.exists(python_path):
                python_path = sys.executable
            
            script_path = os.path.abspath(__file__)
            command = f'"{python_path}" "{script_path}"'
            
            winreg.SetValueEx(key, StartupManager.APP_NAME, 0, winreg.REG_SZ, command)
            winreg.CloseKey(key)
            return True
        except Exception as e:
            print(f"Error enabling startup: {e}")
            return False
    
    @staticmethod
    def disable_startup():
        """Remove app from Windows startup"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, StartupManager.REG_PATH, 0, winreg.KEY_WRITE)
            winreg.DeleteValue(key, StartupManager.APP_NAME)
            winreg.CloseKey(key)
            return True
        except Exception:
            return False


class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.auto_hotspot_enabled = True
        self.is_processing = False  # Track if hotspot operation is in progress
        self.init_ui()
        self.init_monitoring()
        
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("HotspotKeeper")
        self.setFixedSize(450, 320)
        
        # Set window icon if icon.ico exists
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'icon.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("HotspotKeeper")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #e8e8e8;")
        layout.addWidget(title)
        
        # Slogan
        slogan = QLabel("Never Forget Hotspot Again.")
        slogan.setStyleSheet("font-size: 12px; font-style: italic; color: #a8a8a8;")
        layout.addWidget(slogan)
        
        # Status frame
        status_frame = QFrame()
        status_frame.setFrameStyle(QFrame.StyledPanel)
        status_frame.setStyleSheet("""
            QFrame {
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        status_layout = QVBoxLayout(status_frame)
        
        self.wifi_status = QLabel("WiFi: Checking...")
        self.wifi_status.setStyleSheet("font-size: 13px; color: #b8b8b8;")
        status_layout.addWidget(self.wifi_status)
        
        self.hotspot_status = QLabel("Hotspot: Checking...")
        self.hotspot_status.setStyleSheet("font-size: 13px; color: #b8b8b8;")
        status_layout.addWidget(self.hotspot_status)
        
        layout.addWidget(status_frame)
        
        # Settings
        self.auto_enable_check = QCheckBox("Enable Auto-Hotspot")
        self.auto_enable_check.setChecked(True)
        self.auto_enable_check.setStyleSheet("""
            QCheckBox {
                font-size: 13px;
                color: #d8d8d8;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 3px;
                border: 2px solid #6b5344;
                background-color: #2a2a2a;
            }
            QCheckBox::indicator:checked {
                background-color: #8b7355;
                border-color: #8b7355;
            }
        """)
        self.auto_enable_check.stateChanged.connect(self.toggle_auto_hotspot)
        layout.addWidget(self.auto_enable_check)
        
        self.startup_check = QCheckBox("Start with Windows")
        self.startup_check.setChecked(StartupManager.is_startup_enabled())
        self.startup_check.setStyleSheet("""
            QCheckBox {
                font-size: 13px;
                color: #d8d8d8;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 3px;
                border: 2px solid #6b5344;
                background-color: #2a2a2a;
            }
            QCheckBox::indicator:checked {
                background-color: #8b7355;
                border-color: #8b7355;
            }
        """)
        self.startup_check.stateChanged.connect(self.toggle_startup)
        layout.addWidget(self.startup_check)
        
        # Manual controls
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(10)
        
        self.enable_btn = QPushButton("Enable Hotspot")
        self.enable_btn.setMinimumWidth(180)
        self.enable_btn.setFixedHeight(40)
        self.enable_btn.setStyleSheet("""
            QPushButton {
                background-color: #8b7355;
                color: #f5f5dc;
                border: 2px solid #6b5344;
                border-radius: 5px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #9b8365;
                border-color: #7b6354;
            }
            QPushButton:pressed {
                background-color: #6b5344;
            }
            QPushButton:disabled {
                background-color: #4a4a4a;
                color: #808080;
                border-color: #3a3a3a;
            }
        """)
        self.enable_btn.clicked.connect(self.manual_enable_hotspot)
        controls_layout.addWidget(self.enable_btn)
        
        self.disable_btn = QPushButton("Disable Hotspot")
        self.disable_btn.setMinimumWidth(180)
        self.disable_btn.setFixedHeight(40)
        self.disable_btn.setStyleSheet("""
            QPushButton {
                background-color: #8b6f47;
                color: #f5f5dc;
                border: 2px solid #6b5337;
                border-radius: 5px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #9b7f57;
                border-color: #7b6347;
            }
            QPushButton:pressed {
                background-color: #6b5337;
            }
            QPushButton:disabled {
                background-color: #4a4a4a;
                color: #808080;
                border-color: #3a3a3a;
            }
        """)
        self.disable_btn.clicked.connect(self.manual_disable_hotspot)
        controls_layout.addWidget(self.disable_btn)
        
        layout.addLayout(controls_layout)
        
        # Info label
        info = QLabel("The app will automatically enable hotspot when WiFi connects.")
        info.setWordWrap(True)
        info.setStyleSheet("font-size: 11px; color: #888888;")
        layout.addWidget(info)
        
        # GitHub link
        github_link = QLabel('<a href="https://github.com/Moanesbbr/HotspotKeeper" style="color: #8b7355;">Open Source on GitHub</a>')
        github_link.setOpenExternalLinks(True)
        github_link.setStyleSheet("font-size: 11px;")
        github_link.setAlignment(Qt.AlignCenter)
        layout.addWidget(github_link)
        
        # Apply night mode styling
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
        """)
    
    def init_monitoring(self):
        """Initialize network monitoring and system tray"""
        # Network monitor
        self.monitor = NetworkMonitor()
        self.monitor.wifi_connected.connect(self.on_wifi_connected)
        self.monitor.wifi_disconnected.connect(self.on_wifi_disconnected)
        self.monitor.start()
        
        # Status update timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(3000)  # Update every 3 seconds
        
        # System tray
        self.create_tray_icon()
        
        # Initial status update
        self.update_status()
    
    def create_tray_icon(self):
        """Create system tray icon and menu"""
        # Try to load icon.ico if it exists
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'icon.ico')
        
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
        else:
            # Create a simple icon as fallback
            pixmap = QPixmap(64, 64)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # Draw WiFi icon
            painter.setBrush(QColor("#8b7355"))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(20, 40, 24, 24)
            
            painter.setBrush(QColor("#8b7355"))
            for i in range(3):
                radius = 15 + (i * 8)
                painter.drawArc(32 - radius, 32 - radius, radius * 2, radius * 2, 0, 180 * 16)
            
            painter.end()
            
            icon = QIcon(pixmap)
        
        self.tray_icon = QSystemTrayIcon(icon, self)
        
        # Create menu
        tray_menu = QMenu()
        
        show_action = QAction("Show Window", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)
        
        tray_menu.addSeparator()
        
        self.auto_action = QAction("Auto-Hotspot Enabled", self)
        self.auto_action.setCheckable(True)
        self.auto_action.setChecked(True)
        self.auto_action.triggered.connect(self.toggle_auto_from_tray)
        tray_menu.addAction(self.auto_action)
        
        tray_menu.addSeparator()
        
        quit_action = QAction("Exit", self)
        quit_action.triggered.connect(self.quit_app)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
        self.tray_icon.show()
    
    def tray_icon_activated(self, reason):
        """Handle tray icon clicks"""
        if reason == QSystemTrayIcon.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.activateWindow()
    
    def update_status(self):
        """Update WiFi and hotspot status"""
        wifi_connected = self.monitor.check_wifi_connection()
        hotspot_enabled = HotspotManager.is_hotspot_enabled()
        
        if wifi_connected:
            self.wifi_status.setText("WiFi: ✓ Connected")
            self.wifi_status.setStyleSheet("font-size: 13px; color: #7fb57f;")
        else:
            self.wifi_status.setText("WiFi: ✗ Disconnected")
            self.wifi_status.setStyleSheet("font-size: 13px; color: #d08c8c;")
        
        if hotspot_enabled:
            self.hotspot_status.setText("Hotspot: ✓ Enabled")
            self.hotspot_status.setStyleSheet("font-size: 13px; color: #7fb57f;")
        else:
            self.hotspot_status.setText("Hotspot: ✗ Disabled")
            self.hotspot_status.setStyleSheet("font-size: 13px; color: #b8b8b8;")
    
    def on_wifi_connected(self):
        """Handle WiFi connection event"""
        self.update_status()
        if self.auto_hotspot_enabled and not self.is_processing:
            if not HotspotManager.is_hotspot_enabled():
                self.tray_icon.showMessage(
                    "WiFi Connected",
                    "Enabling Mobile Hotspot...",
                    QSystemTrayIcon.Information,
                    2000
                )
                if HotspotManager.enable_hotspot():
                    QTimer.singleShot(1500, self.update_status)
    
    def on_wifi_disconnected(self):
        """Handle WiFi disconnection event"""
        self.update_status()
    
    def toggle_auto_hotspot(self, state):
        """Toggle auto-hotspot feature"""
        self.auto_hotspot_enabled = state == Qt.Checked
        self.auto_action.setChecked(self.auto_hotspot_enabled)
    
    def toggle_auto_from_tray(self):
        """Toggle auto-hotspot from tray menu"""
        self.auto_hotspot_enabled = self.auto_action.isChecked()
        self.auto_enable_check.setChecked(self.auto_hotspot_enabled)
    
    def toggle_startup(self, state):
        """Toggle Windows startup"""
        if state == Qt.Checked:
            if StartupManager.enable_startup():
                self.tray_icon.showMessage(
                    "Startup Enabled",
                    "App will start with Windows",
                    QSystemTrayIcon.Information,
                    2000
                )
        else:
            StartupManager.disable_startup()
    
    def manual_enable_hotspot(self):
        """Manually enable hotspot"""
        if self.is_processing:
            return
        
        self.is_processing = True
        self.enable_btn.setEnabled(False)
        self.disable_btn.setEnabled(False)
        self.enable_btn.setText("Enabling...")
        
        # Show immediate feedback
        self.tray_icon.showMessage(
            "HotspotKeeper",
            "Enabling Mobile Hotspot...",
            QSystemTrayIcon.Information,
            2000
        )
        
        # Process in background to avoid blocking UI
        QTimer.singleShot(100, self._do_enable_hotspot)
    
    def _do_enable_hotspot(self):
        """Internal method to enable hotspot"""
        success = HotspotManager.enable_hotspot()
        
        # Reset buttons
        self.enable_btn.setText("Enable Hotspot")
        self.enable_btn.setEnabled(True)
        self.disable_btn.setEnabled(True)
        self.is_processing = False
        
        # Update status and show result
        QTimer.singleShot(1500, self.update_status)
        
        if success:
            self.tray_icon.showMessage(
                "HotspotKeeper",
                "Mobile Hotspot enabled successfully!",
                QSystemTrayIcon.Information,
                2000
            )
        else:
            self.tray_icon.showMessage(
                "HotspotKeeper",
                "Failed to enable hotspot. Please try again.",
                QSystemTrayIcon.Warning,
                3000
            )
    
    def manual_disable_hotspot(self):
        """Manually disable hotspot"""
        if self.is_processing:
            return
        
        self.is_processing = True
        self.enable_btn.setEnabled(False)
        self.disable_btn.setEnabled(False)
        self.disable_btn.setText("Disabling...")
        
        # Show immediate feedback
        self.tray_icon.showMessage(
            "HotspotKeeper",
            "Disabling Mobile Hotspot...",
            QSystemTrayIcon.Information,
            2000
        )
        
        # Process in background to avoid blocking UI
        QTimer.singleShot(100, self._do_disable_hotspot)
    
    def _do_disable_hotspot(self):
        """Internal method to disable hotspot"""
        success = HotspotManager.disable_hotspot()
        
        # Reset buttons
        self.disable_btn.setText("Disable Hotspot")
        self.enable_btn.setEnabled(True)
        self.disable_btn.setEnabled(True)
        self.is_processing = False
        
        # Update status and show result
        QTimer.singleShot(1500, self.update_status)
        
        if success:
            self.tray_icon.showMessage(
                "HotspotKeeper",
                "Mobile Hotspot disabled successfully!",
                QSystemTrayIcon.Information,
                2000
            )
        else:
            self.tray_icon.showMessage(
                "HotspotKeeper",
                "Failed to disable hotspot. Please try again.",
                QSystemTrayIcon.Warning,
                3000
            )
    
    def closeEvent(self, event):
        """Handle window close event - minimize to tray instead"""
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "Still Running",
            "App is running in system tray",
            QSystemTrayIcon.Information,
            2000
        )
    
    def quit_app(self):
        """Quit the application"""
        self.monitor.stop()
        self.monitor.wait()
        QApplication.quit()


def main():
    # Request admin privileges if not already running as admin
    run_as_admin()
    
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Keep running in tray
    
    # Set application icon if icon.ico exists
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'icon.ico')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()