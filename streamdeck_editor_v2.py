#!/usr/bin/env python3
"""
Stream Deck Editor v2
- Custom icons/images for buttons
- Background customization
- Multi-page support
- SSH upload to Pi

Requirements: pip install paramiko pillow
"""

import tkinter as tk
from tkinter import ttk, colorchooser, filedialog
from PIL import Image, ImageTk, ImageDraw
import json
import os
import shutil

# Pi connection
PI_HOST = "192.168.1.112"
PI_USER = "cem"
PI_PASS = "3235"
PI_SCRIPT = "/home/cem/streamdeck_fast.py"
PI_ICONS_DIR = "/home/cem/streamdeck_icons"

CONFIG_FILE = "streamdeck_config_v2.json"
LOCAL_ICONS_DIR = "streamdeck_icons"

AVAILABLE_ACTIONS = [
    "media_playpause", "media_next", "media_prev", "media_stop",
    "volume_up", "volume_down", "volume_mute",
    "obs_record", "obs_stream", "obs_scene1", "obs_scene2",
    "lock_screen", "screenshot", "copy", "paste", "undo", "select_all",
    "custom_app"
]

DEFAULT_CONFIG = {
    "windows_ip": "192.168.1.13",
    "background_color": [25, 25, 35],
    "pages": [
        {
            "name": "Media",
            "buttons": [
                {"label": "PLAY", "action": "media_playpause", "color": [46, 204, 113], "icon": None},
                {"label": "NEXT", "action": "media_next", "color": [52, 152, 219], "icon": None},
                {"label": "PREV", "action": "media_prev", "color": [155, 89, 182], "icon": None},
                {"label": "VOL+", "action": "volume_up", "color": [241, 196, 15], "icon": None},
                {"label": "VOL-", "action": "volume_down", "color": [230, 126, 34], "icon": None},
                {"label": "MUTE", "action": "volume_mute", "color": [231, 76, 60], "icon": None},
            ]
        },
        {
            "name": "Apps",
            "buttons": [
                {"label": "REC", "action": "obs_record", "color": [192, 57, 43], "icon": None},
                {"label": "STREAM", "action": "obs_stream", "color": [142, 68, 173], "icon": None},
                {"label": "NOTE", "action": "open_notepad", "color": [22, 160, 133], "icon": None},
                {"label": "LOCK", "action": "lock_screen", "color": [44, 62, 80], "icon": None},
                {"label": "SNAP", "action": "screenshot", "color": [41, 128, 185], "icon": None},
                {"label": "WEB", "action": "open_browser", "color": [39, 174, 96], "icon": None},
            ]
        }
    ]
}

class StreamDeckEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("🎮 Stream Deck Editor v2")
        self.root.geometry("1000x700")
        self.root.configure(bg="#1a1a2e")
        
        # Ensure icons directory exists
        os.makedirs(LOCAL_ICONS_DIR, exist_ok=True)
        
        self.config = self.load_config()
        self.current_page = 0
        self.selected_button = None
        
        self.create_ui()
        self.refresh_preview()
    
    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return DEFAULT_CONFIG.copy()
    
    def save_config(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=2)
        self.show_status("Configuration saved!")
    
    def create_ui(self):
        # Main container
        main = tk.Frame(self.root, bg="#1a1a2e")
        main.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Left panel - Preview
        left = tk.Frame(main, bg="#16213e", width=500)
        left.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 15))
        
        tk.Label(left, text="📱 Preview", font=("Segoe UI", 16, "bold"),
                bg="#16213e", fg="white").pack(pady=10)
        
        # Preview canvas
        self.preview_frame = tk.Frame(left, bg="#0f0f23", width=480, height=320)
        self.preview_frame.pack(padx=10, pady=10)
        self.preview_frame.pack_propagate(False)
        
        self.preview_canvas = tk.Canvas(self.preview_frame, width=480, height=320,
                                        bg="#0f0f23", highlightthickness=0)
        self.preview_canvas.pack()
        
        # Page navigation
        nav_frame = tk.Frame(left, bg="#16213e")
        nav_frame.pack(pady=10)
        
        tk.Button(nav_frame, text="◀ Prev Page", command=self.prev_page,
                 bg="#4a4a6a", fg="white", font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=5)
        
        self.page_label = tk.Label(nav_frame, text="Page 1/2", font=("Segoe UI", 12),
                                   bg="#16213e", fg="white")
        self.page_label.pack(side=tk.LEFT, padx=20)
        
        tk.Button(nav_frame, text="Next Page ▶", command=self.next_page,
                 bg="#4a4a6a", fg="white", font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=5)
        
        tk.Button(nav_frame, text="+ Add Page", command=self.add_page,
                 bg="#2d6a4f", fg="white", font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=15)
        
        # Right panel - Editor
        right = tk.Frame(main, bg="#1a1a2e")
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Settings
        settings_frame = tk.LabelFrame(right, text="⚙️ Settings", font=("Segoe UI", 12, "bold"),
                                       bg="#16213e", fg="white", padx=10, pady=10)
        settings_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Windows IP
        ip_row = tk.Frame(settings_frame, bg="#16213e")
        ip_row.pack(fill=tk.X, pady=5)
        tk.Label(ip_row, text="Windows IP:", bg="#16213e", fg="white",
                font=("Segoe UI", 10)).pack(side=tk.LEFT)
        self.ip_entry = tk.Entry(ip_row, width=15, font=("Segoe UI", 10))
        self.ip_entry.insert(0, self.config.get("windows_ip", "192.168.1.13"))
        self.ip_entry.pack(side=tk.LEFT, padx=10)
        
        # Background color
        bg_row = tk.Frame(settings_frame, bg="#16213e")
        bg_row.pack(fill=tk.X, pady=5)
        tk.Label(bg_row, text="Background:", bg="#16213e", fg="white",
                font=("Segoe UI", 10)).pack(side=tk.LEFT)
        self.bg_color_btn = tk.Button(bg_row, text="   ", width=5,
                                      command=self.pick_bg_color)
        self.bg_color_btn.pack(side=tk.LEFT, padx=10)
        self.update_bg_color_btn()
        
        # Button editor
        self.editor_frame = tk.LabelFrame(right, text="✏️ Button Editor", 
                                          font=("Segoe UI", 12, "bold"),
                                          bg="#16213e", fg="white", padx=10, pady=10)
        self.editor_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        tk.Label(self.editor_frame, text="Click a button in preview to edit",
                bg="#16213e", fg="#888", font=("Segoe UI", 10, "italic")).pack(pady=20)
        
        # Bottom buttons
        bottom = tk.Frame(right, bg="#1a1a2e")
        bottom.pack(fill=tk.X)

        tk.Button(bottom, text="💾 Save Config", command=self.save_config,
                 bg="#3498db", fg="white", font=("Segoe UI", 11, "bold"),
                 padx=15, pady=8).pack(side=tk.LEFT, padx=5)

        tk.Button(bottom, text="🚀 Deploy to Pi", command=self.deploy_to_pi,
                 bg="#27ae60", fg="white", font=("Segoe UI", 11, "bold"),
                 padx=20, pady=8).pack(side=tk.LEFT, padx=5)

        # Status bar
        self.status_label = tk.Label(right, text="", font=("Segoe UI", 10),
                                     bg="#1a1a2e", fg="#888", anchor="w")
        self.status_label.pack(fill=tk.X, pady=(10, 0))
    
    def update_bg_color_btn(self):
        color = self.config.get("background_color", [25, 25, 35])
        hex_color = "#{:02x}{:02x}{:02x}".format(*color)
        self.bg_color_btn.configure(bg=hex_color)

    def show_status(self, message, is_error=False):
        """Show status message in the status bar"""
        color = "#e74c3c" if is_error else "#2ecc71"
        self.status_label.config(text=message, fg=color)
        # Clear after 5 seconds
        self.root.after(5000, lambda: self.status_label.config(text="", fg="#888"))
    
    def pick_bg_color(self):
        color = colorchooser.askcolor(title="Background Color")[0]
        if color:
            self.config["background_color"] = [int(c) for c in color]
            self.update_bg_color_btn()
            self.refresh_preview()
    
    def refresh_preview(self):
        self.preview_canvas.delete("all")
        
        bg = self.config.get("background_color", [25, 25, 35])
        bg_hex = "#{:02x}{:02x}{:02x}".format(*bg)
        self.preview_canvas.configure(bg=bg_hex)
        
        page = self.config["pages"][self.current_page]
        buttons = page["buttons"]
        
        # Button dimensions
        cols, rows = 3, 2
        margin = 10
        nav_height = 70
        btn_w = (480 - (cols + 1) * margin) // cols
        btn_h = (320 - nav_height - (rows + 1) * margin) // rows
        
        self.button_rects = []
        
        if not hasattr(self, 'photos'):
            self.photos = []
        self.photos.clear()

        for i, btn in enumerate(buttons):
            row, col = i // cols, i % cols
            x1 = margin + col * (btn_w + margin)
            y1 = margin + row * (btn_h + margin)
            x2 = x1 + btn_w
            y2 = y1 + btn_h

            color = btn.get("color", [100, 100, 100])
            hex_color = "#{:02x}{:02x}{:02x}".format(*color)

            # Draw button background color first
            self.preview_canvas.create_rectangle(x1, y1, x2, y2, fill=hex_color,
                                                  outline="white", width=2)

            # Draw background image (fills button)
            bg_path = btn.get("background")
            if bg_path and os.path.exists(bg_path):
                try:
                    img = Image.open(bg_path).resize((btn_w - 4, btn_h - 4))
                    photo = ImageTk.PhotoImage(img)
                    self.preview_canvas.create_image(x1 + 2, y1 + 2, image=photo, anchor="nw")
                    self.photos.append(photo)
                except:
                    pass

            # Draw icon (small, centered top)
            icon_path = btn.get("icon")
            if icon_path and os.path.exists(icon_path):
                try:
                    img = Image.open(icon_path).resize((50, 50))
                    photo = ImageTk.PhotoImage(img)
                    self.preview_canvas.create_image((x1+x2)//2, y1 + 35, image=photo)
                    self.photos.append(photo)
                except:
                    pass

            # Label at bottom
            label = btn.get("label", "")
            self.preview_canvas.create_text((x1+x2)//2, y2 - 15, text=label,
                                            fill="white", font=("Segoe UI", 10, "bold"))
            
            self.button_rects.append((x1, y1, x2, y2, i))
        
        # Navigation bar
        nav_y = 320 - nav_height
        self.preview_canvas.create_rectangle(0, nav_y, 480, 320, fill="#282840", outline="")
        
        # Page indicator
        page_text = f"{self.current_page + 1}/{len(self.config['pages'])}"
        self.preview_canvas.create_text(240, nav_y + 35, text=page_text,
                                        fill="#aaa", font=("Segoe UI", 14))
        
        self.page_label.config(text=f"Page {self.current_page + 1}/{len(self.config['pages'])}")
        
        # Bind click
        self.preview_canvas.bind("<Button-1>", self.on_preview_click)
    
    def on_preview_click(self, event):
        for x1, y1, x2, y2, idx in self.button_rects:
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                self.select_button(idx)
                return
    
    def select_button(self, idx):
        self.selected_button = idx
        btn = self.config["pages"][self.current_page]["buttons"][idx]

        # Initialize selections with current values
        self.selected_background = btn.get("background")
        self.selected_icon = btn.get("icon")

        # Clear editor frame
        for widget in self.editor_frame.winfo_children():
            widget.destroy()
        
        tk.Label(self.editor_frame, text=f"Editing Button {idx + 1}",
                bg="#16213e", fg="white", font=("Segoe UI", 12, "bold")).pack(pady=5)
        
        # Label
        label_row = tk.Frame(self.editor_frame, bg="#16213e")
        label_row.pack(fill=tk.X, pady=5)
        tk.Label(label_row, text="Label:", bg="#16213e", fg="white", width=10,
                anchor="w").pack(side=tk.LEFT)
        self.label_entry = tk.Entry(label_row, width=20, font=("Segoe UI", 10))
        self.label_entry.insert(0, btn.get("label", ""))
        self.label_entry.pack(side=tk.LEFT, padx=5)
        
        # Action
        action_row = tk.Frame(self.editor_frame, bg="#16213e")
        action_row.pack(fill=tk.X, pady=5)
        tk.Label(action_row, text="Action:", bg="#16213e", fg="white", width=10,
                anchor="w").pack(side=tk.LEFT)
        self.action_combo = ttk.Combobox(action_row, values=AVAILABLE_ACTIONS, width=18)
        self.action_combo.set(btn.get("action", ""))
        self.action_combo.pack(side=tk.LEFT, padx=5)

        # App Path (for custom_app action)
        app_row = tk.Frame(self.editor_frame, bg="#16213e")
        app_row.pack(fill=tk.X, pady=5)
        tk.Label(app_row, text="App Path:", bg="#16213e", fg="white", width=10,
                anchor="w").pack(side=tk.LEFT)

        app_path = btn.get("app_path", "")
        self.app_path_label = tk.Label(app_row, text=os.path.basename(app_path) if app_path else "None",
                                       bg="#16213e", fg="#aaa", width=12, anchor="w")
        self.app_path_label.pack(side=tk.LEFT, padx=5)
        self.selected_app_path = app_path

        tk.Button(app_row, text="Browse", command=self.pick_app_path,
                 bg="#4a4a6a", fg="white").pack(side=tk.LEFT, padx=2)
        tk.Button(app_row, text="Clear", command=self.clear_app_path,
                 bg="#6a4a4a", fg="white").pack(side=tk.LEFT, padx=2)

        # Color
        color_row = tk.Frame(self.editor_frame, bg="#16213e")
        color_row.pack(fill=tk.X, pady=5)
        tk.Label(color_row, text="Color:", bg="#16213e", fg="white", width=10,
                anchor="w").pack(side=tk.LEFT)
        self.btn_color = btn.get("color", [100, 100, 100])
        hex_color = "#{:02x}{:02x}{:02x}".format(*self.btn_color)
        self.color_btn = tk.Button(color_row, text="   ", bg=hex_color, width=5,
                                   command=self.pick_btn_color)
        self.color_btn.pack(side=tk.LEFT, padx=5)
        
        # Background image (fills button)
        bg_row = tk.Frame(self.editor_frame, bg="#16213e")
        bg_row.pack(fill=tk.X, pady=5)
        tk.Label(bg_row, text="Background:", bg="#16213e", fg="white", width=10,
                anchor="w").pack(side=tk.LEFT)

        bg_path = btn.get("background", "")
        self.bg_label = tk.Label(bg_row, text=os.path.basename(bg_path) if bg_path else "None",
                                 bg="#16213e", fg="#aaa", width=12, anchor="w")
        self.bg_label.pack(side=tk.LEFT, padx=5)

        tk.Button(bg_row, text="Browse", command=self.pick_background,
                 bg="#4a4a6a", fg="white").pack(side=tk.LEFT, padx=2)
        tk.Button(bg_row, text="Clear", command=self.clear_background,
                 bg="#6a4a4a", fg="white").pack(side=tk.LEFT, padx=2)

        # Icon (small, on top)
        icon_row = tk.Frame(self.editor_frame, bg="#16213e")
        icon_row.pack(fill=tk.X, pady=5)
        tk.Label(icon_row, text="Icon:", bg="#16213e", fg="white", width=10,
                anchor="w").pack(side=tk.LEFT)

        icon_path = btn.get("icon", "")
        self.icon_label = tk.Label(icon_row, text=os.path.basename(icon_path) if icon_path else "None",
                                   bg="#16213e", fg="#aaa", width=12, anchor="w")
        self.icon_label.pack(side=tk.LEFT, padx=5)

        tk.Button(icon_row, text="Browse", command=self.pick_icon,
                 bg="#4a4a6a", fg="white").pack(side=tk.LEFT, padx=2)
        tk.Button(icon_row, text="Clear", command=self.clear_icon,
                 bg="#6a4a4a", fg="white").pack(side=tk.LEFT, padx=2)

        # Apply button
        tk.Button(self.editor_frame, text="✓ Apply Changes", command=self.apply_changes,
                 bg="#27ae60", fg="white", font=("Segoe UI", 11, "bold"),
                 padx=20, pady=8).pack(pady=20)
    
    def pick_btn_color(self):
        color = colorchooser.askcolor(title="Button Color")[0]
        if color:
            self.btn_color = [int(c) for c in color]
            hex_color = "#{:02x}{:02x}{:02x}".format(*self.btn_color)
            self.color_btn.configure(bg=hex_color)
    
    def pick_app_path(self):
        path = filedialog.askopenfilename(
            filetypes=[("Executables", "*.exe *.lnk *.bat *.cmd"), ("All files", "*.*")]
        )
        if path:
            self.selected_app_path = path
            self.app_path_label.config(text=os.path.basename(path))

    def clear_app_path(self):
        self.selected_app_path = None
        self.app_path_label.config(text="None")

    def pick_background(self):
        path = filedialog.askopenfilename(
            filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.bmp")]
        )
        if path:
            filename = os.path.basename(path)
            dest = os.path.join(LOCAL_ICONS_DIR, filename)
            shutil.copy(path, dest)
            self.selected_background = dest
            self.bg_label.config(text=filename)

    def clear_background(self):
        self.selected_background = None
        self.bg_label.config(text="None")

    def pick_icon(self):
        path = filedialog.askopenfilename(
            filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.bmp")]
        )
        if path:
            filename = os.path.basename(path)
            dest = os.path.join(LOCAL_ICONS_DIR, filename)
            shutil.copy(path, dest)
            self.selected_icon = dest
            self.icon_label.config(text=filename)

    def clear_icon(self):
        self.selected_icon = None
        self.icon_label.config(text="None")
    
    def apply_changes(self):
        if self.selected_button is None:
            return

        btn = self.config["pages"][self.current_page]["buttons"][self.selected_button]
        btn["label"] = self.label_entry.get()
        btn["action"] = self.action_combo.get()
        btn["color"] = self.btn_color

        if hasattr(self, 'selected_app_path'):
            btn["app_path"] = self.selected_app_path

        if hasattr(self, 'selected_background'):
            btn["background"] = self.selected_background

        if hasattr(self, 'selected_icon'):
            btn["icon"] = self.selected_icon

        self.save_config()
        self.refresh_preview()
    
    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.refresh_preview()
    
    def next_page(self):
        if self.current_page < len(self.config["pages"]) - 1:
            self.current_page += 1
            self.refresh_preview()
    
    def add_page(self):
        new_page = {
            "name": f"Page {len(self.config['pages']) + 1}",
            "buttons": [
                {"label": f"BTN{i+1}", "action": "", "color": [80, 80, 100], "icon": None, "background": None}
                for i in range(6)
            ]
        }
        self.config["pages"].append(new_page)
        self.current_page = len(self.config["pages"]) - 1
        self.refresh_preview()
    
    def generate_pi_script(self):
        """Generate the Pi script with current config"""
        config = self.config
        pages_code = json.dumps(config["pages"], indent=4)
        pages_code = pages_code.replace("null", "None").replace("true", "True").replace("false", "False")
        bg_color = config.get("background_color", [25, 25, 35])
        windows_ip = self.ip_entry.get()
        
        script = f'''#!/usr/bin/env python3
import os, mmap, time, requests
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from evdev import InputDevice, ecodes

WINDOWS_PC_IP = "{windows_ip}"
WINDOWS_PORT = 5555
FB_DEV = "/dev/fb1"
TOUCH_DEV = "/dev/input/event0"
WIDTH, HEIGHT = 480, 320
ICONS_DIR = "{PI_ICONS_DIR}"

CAL_X_MIN, CAL_X_MAX = 600, 3550
CAL_Y_MIN, CAL_Y_MAX = 750, 3300
INVERT_Y = True

BG_COLOR = tuple({bg_color})

PAGES = {pages_code}

COLS, ROWS = 3, 2
MARGIN = 10
NAV_HEIGHT = 70
BTN_W = (WIDTH - (COLS + 1) * MARGIN) // COLS
BTN_H = (HEIGHT - NAV_HEIGHT - (ROWS + 1) * MARGIN) // ROWS

fb = os.open(FB_DEV, os.O_RDWR)
fb_mmap = mmap.mmap(fb, WIDTH * HEIGHT * 2)

current_page = 0

def get_btn_rect(idx):
    row, col = idx // COLS, idx % COLS
    x = MARGIN + col * (BTN_W + MARGIN)
    y = MARGIN + row * (BTN_H + MARGIN)
    return (x, y, x + BTN_W, y + BTN_H)

NAV_Y = HEIGHT - NAV_HEIGHT
LEFT_NAV = (0, NAV_Y, 120, HEIGHT)
RIGHT_NAV = (WIDTH - 120, NAV_Y, WIDTH, HEIGHT)

print("Loading fonts...")
try:
    font_btn = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
except:
    font_btn = ImageFont.load_default()
try:
    font_nav = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
except:
    font_nav = font_btn

def load_image(path, size):
    if not path:
        return None
    # Handle both Windows and Unix paths - get just the filename
    filename = path.split("/")[-1].split(chr(92))[-1]
    pi_path = os.path.join(ICONS_DIR, filename)
    if os.path.exists(pi_path):
        try:
            img = Image.open(pi_path).convert("RGBA").resize(size)
            return img
        except:
            pass
    return None

def make_frame_bytes(page_idx, highlight=-1):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    buttons = PAGES[page_idx]["buttons"]

    for i, btn in enumerate(buttons):
        x1, y1, x2, y2 = get_btn_rect(i)
        color = tuple(btn.get("color", [100, 100, 100]))
        if i == highlight:
            color = (255, 255, 255)

        # Draw button background color
        draw.rounded_rectangle([x1, y1, x2, y2], radius=12, fill=color, outline=(255,255,255), width=2)

        # Only draw images if not highlighted (flash effect)
        if i != highlight:
            # Draw background image (fills button)
            bg_img = load_image(btn.get("background"), (BTN_W - 4, BTN_H - 4))
            if bg_img:
                img.paste(bg_img, (x1 + 2, y1 + 2), bg_img)

            # Draw icon (small, top center)
            icon = load_image(btn.get("icon"), (50, 50))
            if icon:
                icon_x = x1 + (BTN_W - 50) // 2
                icon_y = y1 + 10
                img.paste(icon, (icon_x, icon_y), icon)

        # Label at bottom
        label = btn.get("label", "")
        if label:
            bbox = draw.textbbox((0,0), label, font=font_btn)
            tw = bbox[2] - bbox[0]
            draw.text((x1 + (BTN_W - tw)//2, y2 - 25), label, fill=(255,255,255), font=font_btn)
    
    # Navigation
    draw.rectangle([0, NAV_Y, WIDTH, HEIGHT], fill=(40, 40, 55))
    
    left_color = (70, 130, 180) if page_idx > 0 else (50, 50, 65)
    draw.rectangle(LEFT_NAV, fill=left_color)
    draw.text((40, NAV_Y + 15), "<", fill=(255,255,255), font=font_nav)
    
    right_color = (70, 130, 180) if page_idx < len(PAGES) - 1 else (50, 50, 65)
    draw.rectangle(RIGHT_NAV, fill=right_color)
    draw.text((WIDTH - 80, NAV_Y + 15), ">", fill=(255,255,255), font=font_nav)
    
    page_text = f"{{page_idx + 1}}/{{len(PAGES)}}"
    bbox = draw.textbbox((0,0), page_text, font=font_btn)
    tw = bbox[2] - bbox[0]
    draw.text((WIDTH//2 - tw//2, NAV_Y + 22), page_text, fill=(200,200,220), font=font_btn)
    
    arr = np.array(img, dtype=np.uint16)
    rgb565 = ((arr[:,:,0] >> 3) << 11) | ((arr[:,:,1] >> 2) << 5) | (arr[:,:,2] >> 3)
    return rgb565.astype(np.uint16).tobytes()

print("Pre-rendering pages...")
frame_cache = {{}}
for p in range(len(PAGES)):
    frame_cache[(p, -1)] = make_frame_bytes(p, -1)
    for i in range(len(PAGES[p]["buttons"])):
        frame_cache[(p, i)] = make_frame_bytes(p, i)
print(f"Cached {{len(frame_cache)}} frames!")

def show(page, highlight=-1):
    fb_mmap.seek(0)
    fb_mmap.write(frame_cache[(page, highlight)])

def send_action(action, app_path=None):
    if not action:
        return
    try:
        if action == "custom_app" and app_path:
            import urllib.parse
            encoded_path = urllib.parse.quote(app_path, safe='')
            requests.get(f"http://{{WINDOWS_PC_IP}}:{{WINDOWS_PORT}}/launch?path={{encoded_path}}", timeout=0.5)
        else:
            requests.get(f"http://{{WINDOWS_PC_IP}}:{{WINDOWS_PORT}}/action/{{action}}", timeout=0.3)
    except:
        pass

def touch_to_screen(tx, ty):
    sx = int((tx - CAL_X_MIN) / (CAL_X_MAX - CAL_X_MIN) * WIDTH)
    sy = int((ty - CAL_Y_MIN) / (CAL_Y_MAX - CAL_Y_MIN) * HEIGHT)
    if INVERT_Y:
        sy = HEIGHT - sy
    return max(0, min(WIDTH-1, sx)), max(0, min(HEIGHT-1, sy))

print("Ready!")
show(current_page)
touch = InputDevice(TOUCH_DEV)

touch_x, touch_y = 0, 0
touching = False
pending_touch = False

for event in touch.read_loop():
    if event.type == ecodes.EV_ABS:
        if event.code == ecodes.ABS_X:
            touch_x = event.value
        elif event.code == ecodes.ABS_Y:
            touch_y = event.value
    elif event.type == ecodes.EV_KEY and event.code == ecodes.BTN_TOUCH:
        if event.value == 1:
            pending_touch = True
            touching = True
        else:
            touching = False
    elif event.type == ecodes.EV_SYN and event.code == ecodes.SYN_REPORT:
        if pending_touch and touching:
            pending_touch = False
            sx, sy = touch_to_screen(touch_x, touch_y)
            
            if sx >= RIGHT_NAV[0] and sy >= NAV_Y:
                if current_page < len(PAGES) - 1:
                    current_page += 1
                    show(current_page)
                continue
            
            if sx <= LEFT_NAV[2] and sy >= NAV_Y:
                if current_page > 0:
                    current_page -= 1
                    show(current_page)
                continue
            
            for i, btn in enumerate(PAGES[current_page]["buttons"]):
                x1, y1, x2, y2 = get_btn_rect(i)
                if x1 <= sx <= x2 and y1 <= sy <= y2:
                    show(current_page, i)
                    send_action(btn.get("action"), btn.get("app_path"))
                    time.sleep(0.05)
                    show(current_page)
                    break
'''
        return script
    
    def upload_to_pi(self):
        try:
            import paramiko
        except ImportError:
            self.show_status("paramiko required! pip install paramiko", is_error=True)
            return

        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(PI_HOST, username=PI_USER, password=PI_PASS, timeout=10)

            sftp = ssh.open_sftp()

            # Create icons directory
            try:
                sftp.mkdir(PI_ICONS_DIR)
            except:
                pass

            # Upload icons
            if os.path.exists(LOCAL_ICONS_DIR):
                for filename in os.listdir(LOCAL_ICONS_DIR):
                    local_path = os.path.join(LOCAL_ICONS_DIR, filename)
                    remote_path = f"{PI_ICONS_DIR}/{filename}"
                    sftp.put(local_path, remote_path)

            # Upload script
            script = self.generate_pi_script()
            with sftp.file(PI_SCRIPT, 'w') as f:
                f.write(script)

            sftp.close()
            ssh.close()

            self.show_status("Uploaded to Pi!")
        except Exception as e:
            self.show_status(f"Upload failed: {e}", is_error=True)
    
    def start_on_pi(self):
        try:
            import paramiko
        except ImportError:
            self.show_status("paramiko required! pip install paramiko", is_error=True)
            return

        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(PI_HOST, username=PI_USER, password=PI_PASS, timeout=10)

            ssh.exec_command("sudo pkill -f streamdeck_fast.py")
            import time
            time.sleep(1)
            ssh.exec_command(f"nohup sudo python3 {PI_SCRIPT} &")
            ssh.close()

            self.show_status("Stream Deck started on Pi!")
        except Exception as e:
            self.show_status(f"Start failed: {e}", is_error=True)

    def deploy_to_pi(self):
        """Upload config and restart script on Pi in one click"""
        try:
            import paramiko
        except ImportError:
            self.show_status("paramiko required! pip install paramiko", is_error=True)
            return

        try:
            # Save current config first
            self.config["windows_ip"] = self.ip_entry.get()
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=2)

            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(PI_HOST, username=PI_USER, password=PI_PASS, timeout=10)

            sftp = ssh.open_sftp()

            # Create icons directory
            try:
                sftp.mkdir(PI_ICONS_DIR)
            except:
                pass

            # Upload icons
            if os.path.exists(LOCAL_ICONS_DIR):
                for filename in os.listdir(LOCAL_ICONS_DIR):
                    local_path = os.path.join(LOCAL_ICONS_DIR, filename)
                    remote_path = f"{PI_ICONS_DIR}/{filename}"
                    sftp.put(local_path, remote_path)

            # Upload script
            script = self.generate_pi_script()
            with sftp.file(PI_SCRIPT, 'w') as f:
                f.write(script)

            sftp.close()

            # Stop old script - wait for completion
            stdin, stdout, stderr = ssh.exec_command("sudo pkill -9 -f streamdeck_fast.py")
            stdout.channel.recv_exit_status()  # Wait for command to complete

            import time
            time.sleep(2)

            # Start new script
            ssh.exec_command(f"sudo python3 {PI_SCRIPT} > /dev/null 2>&1 &")
            time.sleep(1)

            ssh.close()

            self.show_status("Deployed to Pi!")
        except Exception as e:
            self.show_status(f"Deploy failed: {e}", is_error=True)

if __name__ == "__main__":
    root = tk.Tk()
    app = StreamDeckEditor(root)
    root.mainloop()
