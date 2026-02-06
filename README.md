# WiFi Hotspot Auto-Enable for Windows 11

A lightweight Python application that automatically enables Windows Mobile Hotspot when WiFi connects.

## Features

- ✅ **Auto-start with Windows** - Optionally launch on system startup
- 🔍 **Real-time WiFi monitoring** - Detects WiFi connection changes instantly
- 📡 **Smart hotspot control** - Only enables hotspot if it's currently off
- 🎯 **System tray integration** - Runs quietly in the background
- 🎨 **Modern GUI** - Clean, minimal interface
- ⚡ **Lightweight** - Low resource usage
- 🛡️ **Error handling** - Gracefully handles network issues

## Requirements

- Windows 11
- Python 3.8 or higher
- Administrator privileges (for hotspot control)

## Installation

### Step 1: Install Python

Download and install Python from [python.org](https://www.python.org/downloads/)

**Important:** Check "Add Python to PATH" during installation

### Step 2: Download the Application

Download or clone this repository to your local machine.

### Step 3: Install Dependencies

Open Command Prompt or PowerShell in the application folder and run:

```bash
pip install -r requirements.txt
```

## Usage

### First Time Setup

1. **Run as Administrator** (required for hotspot control):
   - Right-click on `wifi_hotspot_auto.py`
   - Select "Run as administrator" or use:
   
   ```bash
   python wifi_hotspot_auto.py
   ```

2. **Configure Settings:**
   - Check "Enable Auto-Hotspot" to enable automatic hotspot
   - Check "Start with Windows" to run on startup
   - The app will minimize to system tray

### System Tray

The app runs in the system tray (notification area). Right-click the icon for options:

- **Show Window** - Display the main interface
- **Auto-Hotspot Enabled** - Toggle automatic hotspot
- **Exit** - Quit the application

### Manual Control

You can also manually enable/disable the hotspot using the buttons in the main window.

## How It Works

1. **WiFi Monitoring**: The app continuously monitors WiFi connection status every 2 seconds
2. **Auto-Enable**: When WiFi connects, the app checks if hotspot is off
3. **Smart Activation**: If hotspot is off and auto-mode is enabled, it starts the hotspot
4. **Notifications**: System tray notifications inform you of status changes

## Building an Executable (Optional)

To create a standalone .exe file:

1. Install PyInstaller:
   ```bash
   pip install pyinstaller
   ```

2. Build the executable:
   ```bash
   pyinstaller --onefile --windowed --icon=NONE --name="WiFiHotspotAuto" wifi_hotspot_auto.py
   ```

3. The executable will be in the `dist` folder

## Technical Details

### Architecture

- **NetworkMonitor**: Background thread monitoring WiFi status
- **HotspotManager**: PowerShell-based hotspot control
- **StartupManager**: Windows registry integration for auto-start
- **MainWindow**: PySide6 GUI with system tray support

### Windows APIs Used

- `netsh wlan` - WiFi status detection
- PowerShell `NetworkOperatorTetheringManager` - Hotspot control
- Windows Registry - Startup registration

### File Structure

```
wifi_hotspot_auto.py    # Main application
requirements.txt        # Python dependencies
README.md              # This file
```

## Troubleshooting

### Hotspot won't enable

- **Solution**: Run the app as Administrator
- Ensure Mobile Hotspot is configured in Windows Settings first
- Check that your WiFi adapter supports hosting

### App doesn't start with Windows

- **Solution**: 
  - Run the app as Administrator once
  - Re-enable "Start with Windows" checkbox
  - Check Windows Task Manager > Startup tab

### WiFi detection not working

- **Solution**: 
  - Ensure WiFi adapter is properly installed
  - Check Windows network settings
  - Restart the application

### High CPU usage

- **Solution**: This shouldn't happen. If it does:
  - Close and restart the app
  - Check for Windows updates
  - Report the issue

## Permissions

The app requires:

- **Administrator rights** - To control Mobile Hotspot
- **Registry access** - To add/remove startup entry (HKEY_CURRENT_USER only)
- **Network access** - To monitor WiFi status

## Security

- No data is collected or transmitted
- No internet connection required (except for Windows hotspot functionality)
- Registry modifications are limited to HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run
- All code is open source and auditable

## Limitations

- Windows 11 only (uses specific PowerShell commands)
- Requires initial Mobile Hotspot configuration in Windows Settings
- Needs Administrator privileges for hotspot control
- Cannot configure hotspot settings (name, password) - use Windows Settings

## Uninstallation

1. Uncheck "Start with Windows" in the app
2. Exit the application
3. Delete the application folder
4. (Optional) Remove Python if not needed for other apps

## License

This software is provided as-is for educational and personal use.

## Support

For issues or questions:
1. Check the Troubleshooting section above
2. Ensure you're running as Administrator
3. Verify Windows 11 Mobile Hotspot works manually first

## Credits

Built with:
- Python 3
- PySide6 (Qt for Python)
- Windows PowerShell
- Windows Registry API
