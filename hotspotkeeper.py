"""
HotspotKeeper
A lightweight system tray application that automatically enables Windows Mobile Hotspot when WiFi connects.
Version: 1.1.0 - FIXED
"""

import sys
import subprocess
import winreg
import os
import ctypes
import json
import logging
from datetime import datetime
from pathlib import Path
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QPushButton, QSystemTrayIcon, 
                               QMenu, QCheckBox, QFrame, QDialog, QSpinBox, QMessageBox,
                               QGroupBox, QTextEdit)
from PySide6.QtCore import QTimer, Qt, Signal, QThread, QMutex, QSharedMemory
from PySide6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor
import requests


# Configure logging
def setup_logging():
    """Setup logging to file"""
    log_dir = Path(os.path.expanduser("~")) / "AppData" / "Local" / "HotspotKeeper"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "hotspotkeeper.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return log_file


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
            logging.error(f"Failed to elevate privileges: {e}")
            sys.exit(1)


class SettingsManager:
    """Manage application settings with JSON persistence"""
    
    def __init__(self):
        self.settings_dir = Path(os.path.expanduser("~")) / "AppData" / "Local" / "HotspotKeeper"
        self.settings_dir.mkdir(parents=True, exist_ok=True)
        self.settings_file = self.settings_dir / "settings.json"
        self.settings = self.load_settings()
    
    def load_settings(self):
        """Load settings from JSON file"""
        default_settings = {
            "auto_hotspot_enabled": True,
            "check_interval": 3,  # seconds
            "auto_disable_on_wifi_disconnect": False,
            "show_notifications": True,
            "debounce_time": 10,  # seconds before re-enabling after manual disable
            "battery_threshold": 0,  # 0 = disabled
            "last_manual_disable_time": None
        }
        
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r') as f:
                    loaded = json.load(f)
                    # Merge with defaults to add any new settings
                    default_settings.update(loaded)
                    logging.info("Settings loaded successfully")
            except Exception as e:
                logging.error(f"Error loading settings: {e}")
        
        return default_settings
    
    def save_settings(self):
        """Save settings to JSON file"""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=4)
            logging.info("Settings saved successfully")
        except Exception as e:
            logging.error(f"Error saving settings: {e}")
    
    def get(self, key, default=None):
        """Get a setting value"""
        return self.settings.get(key, default)
    
    def set(self, key, value):
        """Set a setting value and save"""
        self.settings[key] = value
        self.save_settings()


class UpdateChecker(QThread):
    """Check for updates on GitHub"""
    update_available = Signal(str, str)  # version, url
    
    def __init__(self):
        super().__init__()
        self.current_version = "1.1.0"
    
    def run(self):
        try:
            # Check GitHub API for latest release
            response = requests.get(
                "https://api.github.com/repos/Moanesbbr/HotspotKeeper/releases/latest",
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                latest_version = data.get("tag_name", "").replace("v", "")
                
                if latest_version and self.compare_versions(latest_version, self.current_version):
                    download_url = data.get("html_url", "")
                    self.update_available.emit(latest_version, download_url)
                    logging.info(f"Update available: {latest_version}")
        except Exception as e:
            logging.warning(f"Update check failed: {e}")
    
    def compare_versions(self, latest, current):
        """Compare version strings (simple comparison)"""
        try:
            latest_parts = [int(x) for x in latest.split('.')]
            current_parts = [int(x) for x in current.split('.')]
            return latest_parts > current_parts
        except:
            return False


class BatteryMonitor:
    """Monitor battery level"""
    
    @staticmethod
    def get_battery_percentage():
        """Get current battery percentage"""
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            result = subprocess.run(
                ['powershell', '-Command', 
                 '(Get-WmiObject Win32_Battery).EstimatedChargeRemaining'],
                capture_output=True,
                text=True,
                timeout=5,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.stdout.strip():
                return int(result.stdout.strip())
            return 100  # Assume full if not on battery
        except Exception as e:
            logging.warning(f"Error getting battery level: {e}")
            return 100
    
    @staticmethod
    def is_plugged_in():
        """Check if device is plugged in"""
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            result = subprocess.run(
                ['powershell', '-Command', 
                 '(Get-WmiObject Win32_Battery).BatteryStatus'],
                capture_output=True,
                text=True,
                timeout=5,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            # BatteryStatus: 2 = AC Power
            if result.stdout.strip():
                return '2' in result.stdout.strip()
            return True  # Assume plugged in if can't determine
        except Exception as e:
            logging.warning(f"Error checking power status: {e}")
            return True


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
                logging.info("WiFi connected")
            elif not connected and self.was_connected:
                self.wifi_disconnected.emit()
                self.was_connected = False
                logging.info("WiFi disconnected")
                
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
        except Exception as e:
            logging.error(f"Error checking WiFi: {e}")
            return False
    
    def stop(self):
        self.running = False


class HotspotManager:
    """Manage Windows Mobile Hotspot"""
    
    @staticmethod
    def is_hotspot_enabled():
        """
        Check if hotspot is currently enabled - improved detection with multiple methods
        
        FIXED: Now uses multiple detection strategies:
        1. PowerShell WinRT API (most reliable for Windows 10/11)
        2. Network adapter check (looks for Microsoft Hosted Network adapters)
        3. Legacy hosted network check (fallback)
        """
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            # ===== METHOD 1: PowerShell WinRT API (MOST RELIABLE) =====
            # This directly queries the TetheringOperationalState
            script = '''
            try {
                $connectionProfile = [Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime]::GetInternetConnectionProfile()
                $tetheringManager = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime]::CreateFromConnectionProfile($connectionProfile)
                
                # Get the current operational state
                # 0 = Unknown, 1 = On, 2 = Off, 3 = InTransition
                $state = $tetheringManager.TetheringOperationalState
                
                if ($state -eq 1) {
                    Write-Output "ENABLED"
                } else {
                    Write-Output "DISABLED"
                }
                exit 0
            } catch {
                # If WinRT API fails, output error for fallback methods
                Write-Output "ERROR"
                exit 1
            }
            '''
            
            result_ps = subprocess.run(
                ['powershell', '-Command', script],
                capture_output=True,
                text=True,
                timeout=5,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            # Check PowerShell method result
            if result_ps.returncode == 0 and 'ENABLED' in result_ps.stdout:
                logging.debug("Hotspot detected as ENABLED via PowerShell WinRT API")
                return True
            elif result_ps.returncode == 0 and 'DISABLED' in result_ps.stdout:
                logging.debug("Hotspot detected as DISABLED via PowerShell WinRT API")
                # Don't return False yet - try fallback methods
                pass
            
            # ===== METHOD 2: Network Adapter Check (FALLBACK) =====
            # Look for Microsoft-hosted network adapters
            result_adapter = subprocess.run(
                ['netsh', 'interface', 'show', 'interface'],
                capture_output=True,
                text=True,
                timeout=5,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            # Look for various adapter name patterns (case-insensitive)
            adapter_output_lower = result_adapter.stdout.lower()
            hotspot_indicators = [
                'local area connection* ',  # Windows 10/11 Mobile Hotspot
                'microsoft wi-fi direct virtual adapter',
                'microsoft hosted network virtual adapter',
            ]
            
            adapter_detected = any(indicator in adapter_output_lower for indicator in hotspot_indicators)
            
            # Check if adapter is connected
            if adapter_detected and 'connected' in adapter_output_lower:
                logging.debug("Hotspot detected as ENABLED via network adapter check")
                return True
            
            # ===== METHOD 3: Legacy Hosted Network (FALLBACK) =====
            result_legacy = subprocess.run(
                ['netsh', 'wlan', 'show', 'hostednetwork'],
                capture_output=True,
                text=True,
                timeout=5,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if 'started' in result_legacy.stdout.lower():
                logging.debug("Hotspot detected as ENABLED via legacy hosted network")
                return True
            
            # All methods indicate disabled
            logging.debug("Hotspot detected as DISABLED (all methods)")
            return False
            
        except Exception as e:
            logging.error(f"Error checking hotspot status: {e}")
            return False
    
    @staticmethod
    def enable_hotspot():
        """Enable Windows Mobile Hotspot"""
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            # Use PowerShell to enable hotspot - simplified approach that works
            script = '''
            try {
                $connectionProfile = [Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime]::GetInternetConnectionProfile()
                $tetheringManager = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime]::CreateFromConnectionProfile($connectionProfile)
                
                # Start tethering - this is async but we just initiate it
                $tetheringManager.StartTetheringAsync() | Out-Null
                
                # Give it a moment to start
                Start-Sleep -Milliseconds 1000
                
                # Success if we got here without exceptions
                exit 0
            } catch {
                Write-Error $_.Exception.Message
                exit 1
            }
            '''
            
            result = subprocess.run(
                ['powershell', '-Command', script],
                capture_output=True,
                text=True,
                timeout=10,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            # If the command executed without throwing an exception, consider it successful
            # The actual hotspot activation happens asynchronously
            success = result.returncode == 0
            
            if success:
                logging.info("Hotspot enable command sent successfully")
            else:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                logging.error(f"Hotspot enable command failed with code {result.returncode}: {error_msg}")
            
            return success
        except Exception as e:
            logging.error(f"Exception when enabling hotspot: {e}")
            return False
    
    @staticmethod
    def disable_hotspot():
        """Disable Windows Mobile Hotspot"""
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            script = '''
            try {
                $connectionProfile = [Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime]::GetInternetConnectionProfile()
                $tetheringManager = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime]::CreateFromConnectionProfile($connectionProfile)
                
                # Stop tethering (don't wait for async completion)
                $tetheringManager.StopTetheringAsync() | Out-Null
                
                # Give it a moment to stop
                Start-Sleep -Milliseconds 1000
                
                # Success if we got here without exceptions
                exit 0
            } catch {
                Write-Error $_.Exception.Message
                exit 1
            }
            '''
            
            result = subprocess.run(
                ['powershell', '-Command', script],
                capture_output=True,
                text=True,
                timeout=10,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            success = result.returncode == 0
            
            if success:
                logging.info("Hotspot disable command sent successfully")
            else:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                logging.error(f"Hotspot disable command failed with code {result.returncode}: {error_msg}")
            
            return success
        except Exception as e:
            logging.error(f"Exception when disabling hotspot: {e}")
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
            
            # Detect if running as .exe or .py script
            if getattr(sys, 'frozen', False):
                # Running as compiled .exe - add --minimized flag
                app_path = sys.executable
                command = f'"{app_path}" --minimized'
            else:
                # Running as Python script - use pythonw.exe with --minimized flag
                python_path = sys.executable.replace('python.exe', 'pythonw.exe')
                if not os.path.exists(python_path):
                    python_path = sys.executable
                
                script_path = os.path.abspath(__file__)
                command = f'"{python_path}" "{script_path}" --minimized'
            
            winreg.SetValueEx(key, StartupManager.APP_NAME, 0, winreg.REG_SZ, command)
            winreg.CloseKey(key)
            logging.info("Startup enabled")
            return True
        except Exception as e:
            logging.error(f"Error enabling startup: {e}")
            return False
    
    @staticmethod
    def disable_startup():
        """Remove app from Windows startup"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, StartupManager.REG_PATH, 0, winreg.KEY_WRITE)
            winreg.DeleteValue(key, StartupManager.APP_NAME)
            winreg.CloseKey(key)
            logging.info("Startup disabled")
            return True
        except Exception:
            return False


class SettingsDialog(QDialog):
    """Settings dialog window"""
    
    def __init__(self, parent, settings_manager):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.init_ui()
    
    def init_ui(self):
        """Initialize settings dialog UI"""
        self.setWindowTitle("Settings")
        self.setMinimumSize(500, 550)  # Increased size for better visibility
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Monitoring settings
        monitor_group = QGroupBox("Monitoring")
        monitor_layout = QVBoxLayout()
        monitor_layout.setSpacing(12)
        
        # Check interval
        interval_layout = QHBoxLayout()
        interval_label = QLabel("Check interval (seconds):")
        interval_label.setMinimumWidth(180)
        interval_layout.addWidget(interval_label)
        
        self.interval_spin = QSpinBox()
        self.interval_spin.setMinimumWidth(100)
        self.interval_spin.setMinimumHeight(30)
        self.interval_spin.setRange(1, 60)
        self.interval_spin.setValue(self.settings_manager.get("check_interval", 3))
        interval_layout.addWidget(self.interval_spin)
        interval_layout.addStretch()
        monitor_layout.addLayout(interval_layout)
        
        # Debounce time
        debounce_layout = QHBoxLayout()
        debounce_label = QLabel("Debounce time (seconds):")
        debounce_label.setMinimumWidth(180)
        debounce_layout.addWidget(debounce_label)
        
        self.debounce_spin = QSpinBox()
        self.debounce_spin.setMinimumWidth(100)
        self.debounce_spin.setMinimumHeight(30)
        self.debounce_spin.setRange(0, 300)
        self.debounce_spin.setValue(self.settings_manager.get("debounce_time", 10))
        debounce_layout.addWidget(self.debounce_spin)
        debounce_layout.addStretch()
        monitor_layout.addLayout(debounce_layout)
        
        monitor_group.setLayout(monitor_layout)
        layout.addWidget(monitor_group)
        
        # Behavior settings
        behavior_group = QGroupBox("Behavior")
        behavior_layout = QVBoxLayout()
        behavior_layout.setSpacing(12)
        
        self.auto_disable_check = QCheckBox("Auto-disable hotspot when WiFi disconnects")
        self.auto_disable_check.setMinimumHeight(25)
        self.auto_disable_check.setChecked(
            self.settings_manager.get("auto_disable_on_wifi_disconnect", False)
        )
        behavior_layout.addWidget(self.auto_disable_check)
        
        behavior_group.setLayout(behavior_layout)
        layout.addWidget(behavior_group)
        
        # Notifications
        notif_group = QGroupBox("Notifications")
        notif_layout = QVBoxLayout()
        notif_layout.setSpacing(12)
        
        self.notifications_check = QCheckBox("Show notifications")
        self.notifications_check.setMinimumHeight(25)
        self.notifications_check.setChecked(
            self.settings_manager.get("show_notifications", True)
        )
        notif_layout.addWidget(self.notifications_check)
        
        notif_group.setLayout(notif_layout)
        layout.addWidget(notif_group)
        
        # Battery
        battery_group = QGroupBox("Battery Awareness")
        battery_layout = QVBoxLayout()
        battery_layout.setSpacing(12)
        
        battery_info = QLabel("Disable auto-hotspot when battery is below:")
        battery_layout.addWidget(battery_info)
        
        battery_control_layout = QHBoxLayout()
        self.battery_spin = QSpinBox()
        self.battery_spin.setMinimumWidth(100)
        self.battery_spin.setMinimumHeight(30)
        self.battery_spin.setRange(0, 100)
        self.battery_spin.setSuffix("%")
        self.battery_spin.setValue(self.settings_manager.get("battery_threshold", 0))
        battery_control_layout.addWidget(self.battery_spin)
        
        battery_note = QLabel("(0 = disabled)")
        battery_note.setStyleSheet("color: #888888; font-size: 11px;")
        battery_control_layout.addWidget(battery_note)
        battery_control_layout.addStretch()
        battery_layout.addLayout(battery_control_layout)
        
        battery_group.setLayout(battery_layout)
        layout.addWidget(battery_group)
        
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        
        save_btn = QPushButton("Save")
        save_btn.setMinimumHeight(35)
        save_btn.setMinimumWidth(100)
        save_btn.clicked.connect(self.save_settings)
        button_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumHeight(35)
        cancel_btn.setMinimumWidth(100)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # Apply dark theme with better input visibility
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: #e8e8e8;
            }
            QGroupBox {
                color: #e8e8e8;
                border: 1px solid #3a3a3a;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QLabel {
                color: #d8d8d8;
            }
            QCheckBox {
                color: #d8d8d8;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QSpinBox {
                background-color: #2a2a2a;
                color: #e8e8e8;
                border: 2px solid #4a4a4a;
                border-radius: 4px;
                padding: 5px;
                font-size: 13px;
            }
            QSpinBox:focus {
                border: 2px solid #8b7355;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #3a3a3a;
                border: none;
                width: 20px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #4a4a4a;
            }
            QPushButton {
                background-color: #8b7355;
                color: #f5f5dc;
                border: 2px solid #6b5344;
                border-radius: 5px;
                padding: 8px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #9b8365;
            }
        """)
    
    def save_settings(self):
        """Save settings and close"""
        self.settings_manager.set("check_interval", self.interval_spin.value())
        self.settings_manager.set("debounce_time", self.debounce_spin.value())
        self.settings_manager.set("auto_disable_on_wifi_disconnect", self.auto_disable_check.isChecked())
        self.settings_manager.set("show_notifications", self.notifications_check.isChecked())
        self.settings_manager.set("battery_threshold", self.battery_spin.value())
        
        self.accept()


class LogViewerDialog(QDialog):
    """Log viewer dialog"""
    
    def __init__(self, parent, log_file):
        super().__init__(parent)
        self.log_file = log_file
        self.init_ui()
    
    def init_ui(self):
        """Initialize log viewer UI"""
        self.setWindowTitle("Log Viewer")
        self.setMinimumSize(600, 400)
        
        layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                color: #e8e8e8;
                font-family: Consolas, monospace;
                font-size: 10pt;
            }
        """)
        
        # Load log file
        try:
            with open(self.log_file, 'r') as f:
                self.log_text.setPlainText(f.read())
        except Exception as e:
            self.log_text.setPlainText(f"Error loading log: {e}")
        
        layout.addWidget(self.log_text)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_log)
        button_layout.addWidget(refresh_btn)
        
        clear_btn = QPushButton("Clear Log")
        clear_btn.clicked.connect(self.clear_log)
        button_layout.addWidget(clear_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # Dark theme
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
            }
            QPushButton {
                background-color: #8b7355;
                color: #f5f5dc;
                border: 2px solid #6b5344;
                border-radius: 5px;
                padding: 8px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #9b8365;
            }
        """)
    
    def refresh_log(self):
        """Refresh log content"""
        try:
            with open(self.log_file, 'r') as f:
                self.log_text.setPlainText(f.read())
            # Scroll to bottom
            self.log_text.verticalScrollBar().setValue(
                self.log_text.verticalScrollBar().maximum()
            )
        except Exception as e:
            self.log_text.setPlainText(f"Error loading log: {e}")
    
    def clear_log(self):
        """Clear log file"""
        reply = QMessageBox.question(
            self, 'Clear Log',
            'Are you sure you want to clear the log file?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                with open(self.log_file, 'w') as f:
                    f.write("")
                self.log_text.clear()
                logging.info("Log file cleared by user")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to clear log: {e}")


class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self, start_minimized=False, settings_manager=None, log_file=None):
        super().__init__()
        self.settings_manager = settings_manager
        self.log_file = log_file
        self.auto_hotspot_enabled = self.settings_manager.get("auto_hotspot_enabled", True)
        self.is_processing = False
        self.start_minimized = start_minimized
        self.last_manual_disable_time = None
        self.last_enable_time = None  # Track when we last enabled hotspot
        
        # Add retry tracking to prevent spam
        self.consecutive_failures = 0
        self.max_consecutive_failures = 3  # Stop trying after 3 failures
        self.last_failure_time = None
        self.failure_cooldown = 60  # Wait 60 seconds after max failures before trying again
        
        # FIXED: Track verification attempts to prevent spam
        self.pending_verification = False
        self.verification_attempts = 0
        self.max_verification_attempts = 3
        
        self.init_ui()
        self.init_monitoring()
        
        # Check for updates
        self.update_checker = UpdateChecker()
        self.update_checker.update_available.connect(self.show_update_notification)
        self.update_checker.start()
        
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("HotspotKeeper v1.1.0")
        self.setFixedSize(450, 400)
        
        # Set window icon
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
        
        self.battery_status = QLabel("Battery: Checking...")
        self.battery_status.setStyleSheet("font-size: 13px; color: #b8b8b8;")
        status_layout.addWidget(self.battery_status)
        
        layout.addWidget(status_frame)
        
        # Settings
        self.auto_enable_check = QCheckBox("Enable Auto-Hotspot")
        self.auto_enable_check.setChecked(self.auto_hotspot_enabled)
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
        
        # Settings button
        settings_btn = QPushButton("⚙ Settings")
        settings_btn.setFixedHeight(35)
        settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #5a5a5a;
                color: #f5f5dc;
                border: 2px solid #4a4a4a;
                border-radius: 5px;
                padding: 5px 15px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #6a6a6a;
            }
        """)
        settings_btn.clicked.connect(self.show_settings)
        layout.addWidget(settings_btn)
        
        # Info label
        info = QLabel("Continuously monitors and keeps hotspot enabled when WiFi is connected.")
        info.setWordWrap(True)
        info.setStyleSheet("font-size: 11px; color: #888888;")
        layout.addWidget(info)
        
        # GitHub link
        github_link = QLabel('<a href="https://github.com/Moanesbbr/HotspotKeeper" style="color: #8b7355;">Open Source on GitHub</a>')
        github_link.setOpenExternalLinks(True)
        github_link.setStyleSheet("font-size: 11px;")
        github_link.setAlignment(Qt.AlignCenter)
        layout.addWidget(github_link)
        
        # Apply dark theme
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
        
        # Status update timer - interval from settings
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        interval = self.settings_manager.get("check_interval", 3) * 1000
        self.status_timer.start(interval)
        
        # System tray
        self.create_tray_icon()
        
        # Initial status update
        self.update_status()
    
    def create_tray_icon(self):
        """Create system tray icon and menu"""
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'icon.ico')
        
        if os.path.exists(icon_path):
            self.base_icon = QIcon(icon_path)
        else:
            # Fallback icon
            pixmap = QPixmap(64, 64)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setBrush(QColor("#8b7355"))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(20, 40, 24, 24)
            for i in range(3):
                radius = 15 + (i * 8)
                painter.drawArc(32 - radius, 32 - radius, radius * 2, radius * 2, 0, 180 * 16)
            painter.end()
            self.base_icon = QIcon(pixmap)
        
        self.tray_icon = QSystemTrayIcon(self.base_icon, self)
        
        # Create menu
        tray_menu = QMenu()
        
        show_action = QAction("Show Window", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)
        
        tray_menu.addSeparator()
        
        self.auto_action = QAction("Auto-Hotspot Enabled", self)
        self.auto_action.setCheckable(True)
        self.auto_action.setChecked(self.auto_hotspot_enabled)
        self.auto_action.triggered.connect(self.toggle_auto_from_tray)
        tray_menu.addAction(self.auto_action)
        
        tray_menu.addSeparator()
        
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.show_settings)
        tray_menu.addAction(settings_action)
        
        logs_action = QAction("View Logs", self)
        logs_action.triggered.connect(self.show_logs)
        tray_menu.addAction(logs_action)
        
        tray_menu.addSeparator()
        
        quit_action = QAction("Exit", self)
        quit_action.triggered.connect(self.quit_app)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
        self.tray_icon.show()
    
    def update_tray_icon_status(self, wifi_on, hotspot_on):
        """Update tray icon based on status (visual feedback)"""
        # This creates a simple colored indicator overlay
        # You could make this more sophisticated
        if wifi_on and hotspot_on:
            self.tray_icon.setToolTip("HotspotKeeper - WiFi & Hotspot Active")
        elif wifi_on:
            self.tray_icon.setToolTip("HotspotKeeper - WiFi Active")
        else:
            self.tray_icon.setToolTip("HotspotKeeper - Monitoring")
    
    def tray_icon_activated(self, reason):
        """Handle tray icon clicks"""
        if reason == QSystemTrayIcon.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.activateWindow()
    
    def update_status(self):
        """Update WiFi and hotspot status, and auto-enable if needed - FIXED VERSION"""
        wifi_connected = self.monitor.check_wifi_connection()
        hotspot_enabled = HotspotManager.is_hotspot_enabled()
        battery_level = BatteryMonitor.get_battery_percentage()
        is_plugged = BatteryMonitor.is_plugged_in()
        
        # FIXED: Extended grace period to 15 seconds (hotspot takes time to start)
        grace_period = 15  # seconds (increased from 5)
        in_grace_period = False
        
        if self.last_enable_time:
            elapsed_since_enable = (datetime.now() - self.last_enable_time).total_seconds()
            in_grace_period = elapsed_since_enable < grace_period
            
            if in_grace_period:
                # During grace period, assume hotspot is enabled
                # Don't override if we actually detected it as enabled
                if not hotspot_enabled:
                    logging.debug(f"In grace period ({elapsed_since_enable:.1f}s/{grace_period}s) - assuming hotspot is starting")
                    hotspot_enabled = True
        
        # FIXED: Reset failure counter only if hotspot is truly enabled (not grace period assumption)
        actual_hotspot_status = HotspotManager.is_hotspot_enabled()
        if actual_hotspot_status and self.consecutive_failures > 0:
            logging.info(f"Hotspot confirmed enabled. Resetting failure counter (was {self.consecutive_failures})")
            self.consecutive_failures = 0
            self.last_failure_time = None
            self.verification_attempts = 0
            self.pending_verification = False
        
        # Update WiFi status
        if wifi_connected:
            self.wifi_status.setText("WiFi: ✓ Connected")
            self.wifi_status.setStyleSheet("font-size: 13px; color: #7fb57f;")
        else:
            self.wifi_status.setText("WiFi: ✗ Disconnected")
            self.wifi_status.setStyleSheet("font-size: 13px; color: #b8b8b8;")
        
        # Update hotspot status
        if hotspot_enabled:
            self.hotspot_status.setText("Hotspot: ✓ Enabled")
            self.hotspot_status.setStyleSheet("font-size: 13px; color: #7fb57f;")
        else:
            self.hotspot_status.setText("Hotspot: ✗ Disabled")
            self.hotspot_status.setStyleSheet("font-size: 13px; color: #b8b8b8;")
        
        # Update battery status
        if is_plugged:
            self.battery_status.setText(f"Battery: {battery_level}% (Plugged In)")
            self.battery_status.setStyleSheet("font-size: 13px; color: #7fb57f;")
        else:
            self.battery_status.setText(f"Battery: {battery_level}%")
            if battery_level < 20:
                self.battery_status.setStyleSheet("font-size: 13px; color: #d08c8c;")
            else:
                self.battery_status.setStyleSheet("font-size: 13px; color: #b8b8b8;")
        
        # Update tray icon tooltip
        self.update_tray_icon_status(wifi_connected, hotspot_enabled)
        
        # Check battery threshold
        battery_threshold = self.settings_manager.get("battery_threshold", 0)
        battery_ok = (battery_threshold == 0 or 
                     battery_level >= battery_threshold or 
                     is_plugged)
        
        # Check debounce time
        debounce_time = self.settings_manager.get("debounce_time", 10)
        debounce_ok = True
        if self.last_manual_disable_time:
            elapsed = (datetime.now() - self.last_manual_disable_time).total_seconds()
            debounce_ok = elapsed >= debounce_time
        
        # FIXED: Check failure cooldown
        if self.consecutive_failures >= self.max_consecutive_failures:
            if self.last_failure_time:
                elapsed_since_failure = (datetime.now() - self.last_failure_time).total_seconds()
                if elapsed_since_failure < self.failure_cooldown:
                    return
                else:
                    logging.info(f"Cooldown expired. Resetting retry counter.")
                    self.consecutive_failures = 0
                    self.last_failure_time = None
        
        # CRITICAL FIX: Auto-enable ONLY when all conditions met
        # Added check for pending_verification to prevent re-triggering during verification
        if (self.auto_hotspot_enabled and 
            wifi_connected and  # WiFi must be connected
            not hotspot_enabled and  # Hotspot must be disabled
            not self.is_processing and  # Not currently processing
            not self.pending_verification and  # NEW: Not waiting for verification
            battery_ok and
            debounce_ok):
            
            self.is_processing = True
            self.pending_verification = True  # NEW: Mark as pending verification
            
            # Only show notification on first attempt, not during grace period retries
            if self.consecutive_failures == 0 and self.settings_manager.get("show_notifications", True):
                self.tray_icon.showMessage(
                    "Auto-Hotspot",
                    "Hotspot was disabled. Re-enabling...",
                    QSystemTrayIcon.Information,
                    2000
                )
            
            logging.info(f"Auto-enabling hotspot (WiFi connected) - Attempt {self.consecutive_failures + 1}")
            success = HotspotManager.enable_hotspot()
            
            if success:
                self.consecutive_failures = 0
                self.last_failure_time = None
                self.last_enable_time = datetime.now()
                self.verification_attempts = 0
                
                # FIXED: Wait longer (5 seconds) before doing verification check
                QTimer.singleShot(5000, lambda: self._verify_hotspot_enabled())
            else:
                self.consecutive_failures += 1
                self.last_failure_time = datetime.now()
                self.is_processing = False
                self.pending_verification = False
                
                logging.warning(f"Auto-enable failed (attempt {self.consecutive_failures}/{self.max_consecutive_failures})")
                
                if self.consecutive_failures >= self.max_consecutive_failures:
                    if self.settings_manager.get("show_notifications", True):
                        self.tray_icon.showMessage(
                            "Auto-Hotspot Failed",
                            f"Failed {self.max_consecutive_failures} times. Will retry in {self.failure_cooldown}s.\n\n"
                            "Please check:\n• Mobile Hotspot is configured\n• You have admin privileges",
                            QSystemTrayIcon.Warning,
                            8000
                        )
                    logging.error(f"Max failures reached. Cooldown: {self.failure_cooldown}s")
        
        # Auto-disable on WiFi disconnect if enabled
        if (self.settings_manager.get("auto_disable_on_wifi_disconnect", False) and
            not wifi_connected and hotspot_enabled and 
            not self.is_processing and not in_grace_period):
            self.is_processing = True
            logging.info("Auto-disabling hotspot (WiFi disconnected)")
            if HotspotManager.disable_hotspot():
                self.last_enable_time = None
                QTimer.singleShot(2500, lambda: self._finish_auto_enable())
            else:
                self.is_processing = False
    
    def _verify_hotspot_enabled(self):
        """
        NEW METHOD: Verify hotspot was actually enabled after enable command
        This prevents infinite re-enable loops
        """
        self.verification_attempts += 1
        
        # Check if hotspot is now actually enabled
        actual_status = HotspotManager.is_hotspot_enabled()
        
        if actual_status:
            # Success! Hotspot is confirmed enabled
            logging.info(f"Hotspot verified as enabled after {self.verification_attempts} check(s)")
            self.is_processing = False
            self.pending_verification = False
            self.verification_attempts = 0
            self.consecutive_failures = 0
            self.update_status()
        else:
            # Still not detected - retry up to max attempts
            if self.verification_attempts < self.max_verification_attempts:
                logging.warning(f"Hotspot not yet detected, verification attempt {self.verification_attempts}/{self.max_verification_attempts}")
                # Wait another 3 seconds and check again
                QTimer.singleShot(3000, lambda: self._verify_hotspot_enabled())
            else:
                # Max verification attempts reached - consider it failed
                logging.error(f"Hotspot not detected after {self.max_verification_attempts} verification attempts")
                self.is_processing = False
                self.pending_verification = False
                self.verification_attempts = 0
                self.consecutive_failures += 1
                
                if self.settings_manager.get("show_notifications", True):
                    self.tray_icon.showMessage(
                        "Hotspot Enable Issue",
                        "Hotspot command sent but not detected as active.\n"
                        "Please check Windows Mobile Hotspot settings.",
                        QSystemTrayIcon.Warning,
                        5000
                    )
                
                self.update_status()
    
    def _finish_auto_enable(self):
        """Complete auto-enable/disable process"""
        self.is_processing = False
        self.pending_verification = False
        self.update_status()
    
    def on_wifi_connected(self):
        """Handle WiFi connection event"""
        logging.info("WiFi connection detected")
        self.update_status()
    
    def on_wifi_disconnected(self):
        """Handle WiFi disconnection event"""
        logging.info("WiFi disconnection detected")
        self.update_status()
    
    def toggle_auto_hotspot(self, state):
        """Toggle auto-hotspot feature"""
        self.auto_hotspot_enabled = state == Qt.Checked
        # Update tray menu checkbox immediately
        self.auto_action.setChecked(self.auto_hotspot_enabled)
        self.settings_manager.set("auto_hotspot_enabled", self.auto_hotspot_enabled)
        logging.info(f"Auto-hotspot {'enabled' if self.auto_hotspot_enabled else 'disabled'}")
    
    def toggle_auto_from_tray(self):
        """Toggle auto-hotspot from tray menu"""
        self.auto_hotspot_enabled = self.auto_action.isChecked()
        # Update main window checkbox immediately
        self.auto_enable_check.blockSignals(True)  # Prevent signal loop
        self.auto_enable_check.setChecked(self.auto_hotspot_enabled)
        self.auto_enable_check.blockSignals(False)
        self.settings_manager.set("auto_hotspot_enabled", self.auto_hotspot_enabled)
        logging.info(f"Auto-hotspot {'enabled' if self.auto_hotspot_enabled else 'disabled'} from tray")
    
    def toggle_startup(self, state):
        """Toggle Windows startup"""
        if state == Qt.Checked:
            if StartupManager.enable_startup():
                if self.settings_manager.get("show_notifications", True):
                    self.tray_icon.showMessage(
                        "Startup Enabled",
                        "App will start minimized in tray with Windows",
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
        
        if self.settings_manager.get("show_notifications", True):
            self.tray_icon.showMessage(
                "HotspotKeeper",
                "Enabling Mobile Hotspot...",
                QSystemTrayIcon.Information,
                2000
            )
        
        logging.info("Manual hotspot enable requested")
        QTimer.singleShot(100, self._do_enable_hotspot)
    
    def _do_enable_hotspot(self):
        """Internal method to enable hotspot"""
        success = HotspotManager.enable_hotspot()
        
        self.enable_btn.setText("Enable Hotspot")
        self.enable_btn.setEnabled(True)
        self.disable_btn.setEnabled(True)
        self.is_processing = False
        
        # Reset failure counter on successful manual enable
        if success:
            self.consecutive_failures = 0
            self.last_failure_time = None
            self.last_enable_time = datetime.now()  # Track when we enabled
        
        # Wait longer before checking status
        QTimer.singleShot(2500, self.update_status)
        
        if self.settings_manager.get("show_notifications", True):
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
                    "Failed to enable hotspot. Please check:\n• Mobile Hotspot is configured\n• You have admin privileges",
                    QSystemTrayIcon.Warning,
                    5000
                )
    
    def manual_disable_hotspot(self):
        """Manually disable hotspot"""
        if self.is_processing:
            return
        
        self.is_processing = True
        self.enable_btn.setEnabled(False)
        self.disable_btn.setEnabled(False)
        self.disable_btn.setText("Disabling...")
        
        # Record manual disable time for debounce
        self.last_manual_disable_time = datetime.now()
        
        if self.settings_manager.get("show_notifications", True):
            self.tray_icon.showMessage(
                "HotspotKeeper",
                "Disabling Mobile Hotspot...",
                QSystemTrayIcon.Information,
                2000
            )
        
        logging.info("Manual hotspot disable requested")
        QTimer.singleShot(100, self._do_disable_hotspot)
    
    def _do_disable_hotspot(self):
        """Internal method to disable hotspot"""
        success = HotspotManager.disable_hotspot()
        
        self.disable_btn.setText("Disable Hotspot")
        self.enable_btn.setEnabled(True)
        self.disable_btn.setEnabled(True)
        self.is_processing = False
        
        # Clear enable time since we're disabling
        if success:
            self.last_enable_time = None
        
        # Wait longer before checking status
        QTimer.singleShot(2500, self.update_status)
        
        if self.settings_manager.get("show_notifications", True):
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
    
    def show_settings(self):
        """Show settings dialog"""
        dialog = SettingsDialog(self, self.settings_manager)
        if dialog.exec() == QDialog.Accepted:
            # Restart timer with new interval
            interval = self.settings_manager.get("check_interval", 3) * 1000
            self.status_timer.stop()
            self.status_timer.start(interval)
            logging.info("Settings updated")
    
    def show_logs(self):
        """Show log viewer"""
        dialog = LogViewerDialog(self, self.log_file)
        dialog.exec()
    
    def show_update_notification(self, version, url):
        """Show update available notification"""
        if self.settings_manager.get("show_notifications", True):
            self.tray_icon.showMessage(
                "Update Available",
                f"Version {version} is available! Click to download.",
                QSystemTrayIcon.Information,
                5000
            )
    
    def closeEvent(self, event):
        """Handle window close event"""
        event.ignore()
        self.hide()
        if not self.start_minimized and self.settings_manager.get("show_notifications", True):
            self.tray_icon.showMessage(
                "Still Running",
                "App is running in system tray",
                QSystemTrayIcon.Information,
                2000
            )
    
    def quit_app(self):
        """Quit the application"""
        logging.info("Application shutting down")
        self.monitor.stop()
        self.monitor.wait()
        QApplication.quit()


def main():
    # Setup logging first
    log_file = setup_logging()
    logging.info("=== HotspotKeeper v1.1.0 Starting ===")
    
    # Check for multiple instances
    app = QApplication(sys.argv)
    
    # Use QSharedMemory to prevent multiple instances
    shared_memory = QSharedMemory("HotspotKeeperUniqueInstance")
    if not shared_memory.create(1):
        logging.warning("Another instance is already running")
        QMessageBox.warning(
            None,
            "Already Running",
            "HotspotKeeper is already running in the system tray.",
            QMessageBox.Ok
        )
        sys.exit(0)
    
    # Check if running with --minimized flag
    start_minimized = '--minimized' in sys.argv
    
    # Request admin privileges
    run_as_admin()
    
    app.setQuitOnLastWindowClosed(False)
    
    # Set application icon
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'icon.ico')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    # Load settings
    settings_manager = SettingsManager()
    
    # Create main window
    window = MainWindow(start_minimized=start_minimized, settings_manager=settings_manager, log_file=log_file)
    
    # Start minimized or show window
    if start_minimized:
        window.hide()
        if settings_manager.get("show_notifications", True):
            window.tray_icon.showMessage(
                "HotspotKeeper Started",
                "Running in system tray",
                QSystemTrayIcon.Information,
                2000
            )
        logging.info("Started minimized to tray")
    else:
        window.show()
        logging.info("Main window shown")
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()