# Stream Deck Editor - Project Documentation

## Overview

This project creates a DIY Stream Deck using a Raspberry Pi with a touchscreen display. It consists of two main components:

1. **Windows Editor** (`streamdeck_editor_v3.py`) - GUI application for designing button layouts
2. **Pi Script** (`streamdeck_fast.py`) - Runs on the Pi, displays buttons and handles touch input

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        WINDOWS PC                                │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │           streamdeck_editor_v3.py (GUI)                 │    │
│  │  - Design button layouts                                │    │
│  │  - Configure actions, icons, GIFs                       │    │
│  │  - Save/load profiles                                   │    │
│  │  - Deploy to Pi via SSH                                 │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                    SSH/SFTP Deploy                               │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │           windows_receiver.py (HTTP Server)             │    │
│  │  - Listens on port 5555                                 │    │
│  │  - Receives action commands from Pi                     │    │
│  │  - Executes media keys, launches apps, etc.             │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ HTTP requests (actions)
                              │
┌─────────────────────────────────────────────────────────────────┐
│                      RASPBERRY PI                                │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              streamdeck_fast.py                         │    │
│  │  - Renders UI to framebuffer (/dev/fb1)                 │    │
│  │  - Handles touch input (/dev/input/event0)              │    │
│  │  - Animates GIFs                                        │    │
│  │  - Sends HTTP requests to Windows PC                    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────┐  ┌──────────────────┐                     │
│  │  Touchscreen     │  │   Framebuffer    │                     │
│  │  /dev/input/     │  │   /dev/fb1       │                     │
│  │  event0          │  │   480x320 RGB565 │                     │
│  └──────────────────┘  └──────────────────┘                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Windows Side

### Files

| File | Purpose |
|------|---------|
| `streamdeck_editor_v3.py` | Main GUI editor application |
| `deploy_to_pi.py` | Standalone deployment script |
| `streamdeck_config_v3.json` | Current configuration |
| `button_library.json` | Saved button presets |
| `streamdeck_icons/` | Local icons/GIFs folder |
| `profiles/` | Saved profile configurations |
| `giphy_key.txt` | GIPHY API key (optional) |

### Editor Features

- **Button Library**: Drag & drop predefined buttons
- **Profile System**: Save/load different configurations
- **GIPHY Integration**: Search and download GIFs directly
- **Live Preview**: See button layouts before deploying
- **Multi-page Support**: Create multiple button pages
- **SSH Deploy**: One-click deployment to Pi

### Configuration Structure

```json
{
  "windows_ip": "192.168.1.13",
  "background_color": [25, 25, 35],
  "current_profile": "Default",
  "pages": [
    {
      "name": "Page 1",
      "buttons": [
        {
          "label": "PLAY",
          "action": "media_playpause",
          "color": [46, 204, 113],
          "icon": null,
          "background": "streamdeck_icons/some.gif",
          "app_path": null
        }
        // ... 6 buttons per page
      ]
    }
  ]
}
```

### Available Actions

| Action | Description |
|--------|-------------|
| `media_playpause` | Play/Pause media |
| `media_next` | Next track |
| `media_prev` | Previous track |
| `media_stop` | Stop media |
| `volume_up` | Increase volume |
| `volume_down` | Decrease volume |
| `volume_mute` | Mute/unmute |
| `obs_record` | Toggle OBS recording |
| `obs_stream` | Toggle OBS streaming |
| `lock_screen` | Lock Windows |
| `screenshot` | Take screenshot |
| `copy` | Ctrl+C |
| `paste` | Ctrl+V |
| `undo` | Ctrl+Z |
| `select_all` | Ctrl+A |
| `custom_app` | Launch application (requires `app_path`) |

### Deployment Process

1. Editor generates Python script with embedded config
2. Connects to Pi via SSH (paramiko)
3. Uploads icons to `/home/cem/streamdeck_icons/`
4. Uploads script to `/home/cem/streamdeck_fast.py`
5. Kills old script process
6. Starts new script in background

---

## Pi Side

### Hardware Requirements

- Raspberry Pi (tested on Pi Zero W, Pi 3, Pi 4)
- 480x320 TFT touchscreen (SPI, uses /dev/fb1)
- Touch input on /dev/input/event0

### Files on Pi

| Path | Purpose |
|------|---------|
| `/home/cem/streamdeck_fast.py` | Main script |
| `/home/cem/streamdeck_icons/` | Icons and GIFs |

### Dependencies (Pi)

```bash
pip install pillow numpy requests evdev
```

### Script Structure

The Pi script has two main page types:

#### 1. Dashboard (Page 0)
- Shows system stats: CPU, Memory, Disk, Temperature
- Updates every 1 second
- Color-coded progress bars (green/yellow/red)

#### 2. Button Pages (Page 1+)
- 6 buttons per page (3x2 grid)
- Support for static images and animated GIFs
- Pre-rendered frames for performance

### Performance Optimizations

| Optimization | Impact |
|--------------|--------|
| **Pre-rendered GIF frames** | All GIF frames converted to RGB565 at startup |
| **Frame caching** | Button frames cached as bytes, no PIL at runtime |
| **Page-aware animation** | Only animate current page's GIFs |
| **Adaptive frame rate** | Auto-adjusts 60-120ms based on CPU load |
| **Partial framebuffer updates** | Only update changed button regions |

### Display Specifications

- Resolution: 480x320
- Color format: RGB565 (16-bit)
- Framebuffer: /dev/fb1 (memory-mapped)
- Button grid: 3 columns x 2 rows
- Navigation bar: 70px at bottom

### Touch Calibration

```python
CAL_X_MIN, CAL_X_MAX = 600, 3550
CAL_Y_MIN, CAL_Y_MAX = 750, 3300
INVERT_Y = True
```

Adjust these values if touch is misaligned.

---

## Network Communication

### Pi → Windows (Actions)

When a button is pressed, Pi sends HTTP GET request:

```
http://192.168.1.13:5555/action/media_playpause
http://192.168.1.13:5555/launch?path=C%3A%5CProgram%20Files%5Capp.exe
```

### Windows Receiver

The Windows side needs a receiver script running:

```python
# windows_receiver.py (simplified)
from http.server import HTTPServer, BaseHTTPRequestHandler
import pyautogui

class ActionHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if '/action/' in self.path:
            action = self.path.split('/action/')[1]
            execute_action(action)
        self.send_response(200)
        self.end_headers()

HTTPServer(('0.0.0.0', 5555), ActionHandler).serve_forever()
```

---

## Configuration Constants

### Pi Script Constants

```python
WINDOWS_PC_IP = "192.168.1.13"  # Windows PC IP
WINDOWS_PORT = 5555              # Receiver port
FB_DEV = "/dev/fb1"              # Framebuffer device
TOUCH_DEV = "/dev/input/event0"  # Touch input device
WIDTH, HEIGHT = 480, 320         # Screen resolution
MAX_GIF_FRAMES = 30              # Max frames per GIF
GIF_INTERVAL = 0.06              # Animation speed (60ms)
DASHBOARD_INTERVAL = 1.0         # Dashboard refresh rate
```

### Editor Constants

```python
PI_HOST = "192.168.1.112"        # Pi IP address
PI_USER = "cem"                  # SSH username
PI_PASS = "3235"                 # SSH password
PI_SCRIPT = "/home/cem/streamdeck_fast.py"
PI_ICONS_DIR = "/home/cem/streamdeck_icons"
```

---

## Troubleshooting

### Pi Issues

| Problem | Solution |
|---------|----------|
| Screen blank | Check if script is running: `ps aux \| grep streamdeck` |
| Touch not working | Verify touch device: `evtest /dev/input/event0` |
| GIFs slow/laggy | Reduce MAX_GIF_FRAMES or increase GIF_INTERVAL |
| High CPU | Check with `htop`, reduce GIF count |
| Script crashes | Run manually to see errors: `sudo python3 /home/cem/streamdeck_fast.py` |

### Windows Issues

| Problem | Solution |
|---------|----------|
| Deploy fails | Check VPN is off, Pi is reachable: `ping 192.168.1.112` |
| Actions don't work | Ensure windows_receiver.py is running |
| SSH denied | Check Pi SSH service: `sudo systemctl status ssh` |

### Network Issues

| Problem | Solution |
|---------|----------|
| VPN blocking | Enable local network sharing or disconnect VPN |
| Firewall | Allow port 5555 inbound on Windows |
| Wrong IP | Update `windows_ip` in editor and redeploy |

---

## Adding New Features

### Adding a New Action

1. Add to `AVAILABLE_ACTIONS` list in editor
2. Add handler in `windows_receiver.py`
3. Redeploy to Pi

### Adding Dashboard Widgets

Edit `render_dashboard()` function in the Pi script template:

```python
def render_dashboard():
    # Add new stats here
    # Use draw.text() and draw_progress_bar()
```

### Changing Button Layout

Modify these constants:
```python
COLS, ROWS = 3, 2  # Change grid size
MARGIN = 10        # Spacing between buttons
NAV_HEIGHT = 70    # Navigation bar height
```

---

## File Locations Summary

### Windows
```
E:/github/streamdeck-editor/
├── streamdeck_editor_v3.py    # Main editor
├── deploy_to_pi.py            # Deployment script
├── streamdeck_config_v3.json  # Config
├── button_library.json        # Button presets
├── streamdeck_icons/          # Icons/GIFs
├── profiles/                  # Saved profiles
└── DOCUMENTATION.md           # This file
```

### Raspberry Pi
```
/home/cem/
├── streamdeck_fast.py         # Main script
└── streamdeck_icons/          # Icons/GIFs
```

---

## Quick Commands

### Deploy from command line
```bash
cd E:/github/streamdeck-editor
python deploy_to_pi.py
```

### Check Pi script status
```bash
ssh cem@192.168.1.112 "ps aux | grep streamdeck"
```

### Restart Pi script manually
```bash
ssh cem@192.168.1.112 "sudo pkill -f streamdeck_fast.py; sudo python3 /home/cem/streamdeck_fast.py &"
```

### View Pi resource usage
```bash
ssh cem@192.168.1.112 "top -bn1 | head -10"
```
