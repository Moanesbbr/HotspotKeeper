# Changelog

All notable changes to HotspotKeeper will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-02-06

### Added

- Initial release of HotspotKeeper
- Automatic Mobile Hotspot enablement when WiFi connects
- System tray integration with icon and menu
- Manual hotspot enable/disable controls
- WiFi and Hotspot status monitoring
- Windows startup integration option
- Auto-hotspot toggle feature
- Night mode UI with modern design
- Admin privilege elevation
- Minimize to tray functionality
- Toast notifications for status updates
- "Never Forget Hotspot Again" slogan
- Open source GitHub link in UI

### Features

- Real-time network monitoring (checks every 2 seconds)
- Status updates every 3 seconds
- Custom system tray icon with fallback
- Professional UI with brown/beige color scheme
- Persistent background operation
- Double-click tray icon to show/hide window
- Clickable GitHub link to repository

### Technical

- Built with PySide6 (Qt for Python)
- Windows-only application
- Requires administrator privileges
- Uses PowerShell for hotspot management
- Registry integration for Windows startup
