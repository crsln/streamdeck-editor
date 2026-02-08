#!/usr/bin/env python3
"""
Stream Deck Editor v3
- Button Library with drag & drop
- Profile system for saving/loading configurations
- Custom icons/images for buttons
- Background customization
- Multi-page support
- SSH upload to Pi
- GIPHY browser integration

Requirements: pip install paramiko pillow requests
"""

import tkinter as tk
from tkinter import ttk, colorchooser, filedialog, simpledialog
from PIL import Image, ImageTk, ImageDraw
import json
import os
import shutil
import copy
import requests
import threading
import io

def cover_resize(img, target_w, target_h):
    """Resize image to cover target area, maintaining aspect ratio (crop if needed)"""
    img_w, img_h = img.size
    img_ratio = img_w / img_h
    target_ratio = target_w / target_h

    if img_ratio > target_ratio:
        # Image is wider - fit height, crop width
        new_h = target_h
        new_w = int(new_h * img_ratio)
    else:
        # Image is taller - fit width, crop height
        new_w = target_w
        new_h = int(new_w / img_ratio)

    img = img.resize((new_w, new_h), Image.LANCZOS)

    # Crop to center
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return img.crop((left, top, left + target_w, top + target_h))

# Pi connection
PI_HOST = "192.168.1.112"
PI_USER = "cem"
PI_PASS = "3235"
PI_SCRIPT = "/home/cem/streamdeck_fast.py"
PI_ICONS_DIR = "/home/cem/streamdeck_icons"

CONFIG_FILE = "streamdeck_config_v3.json"
LIBRARY_FILE = "button_library.json"
PROFILES_DIR = "profiles"
LOCAL_ICONS_DIR = "streamdeck_icons"

# GIPHY API - Get your free key at https://developers.giphy.com/
GIPHY_API_KEY = ""  # Set your API key here or in giphy_key.txt
GIPHY_KEY_FILE = "giphy_key.txt"

def load_giphy_key():
    global GIPHY_API_KEY
    if os.path.exists(GIPHY_KEY_FILE):
        with open(GIPHY_KEY_FILE, 'r') as f:
            GIPHY_API_KEY = f.read().strip()
    return GIPHY_API_KEY


class GiphyBrowser:
    """GIPHY search and download dialog with animated thumbnails and pagination"""

    def __init__(self, parent, callback, for_background=False):
        self.callback = callback
        self.for_background = for_background
        self.selected_url = None
        self.thumbnails = []  # Keep references to prevent GC
        self.animated_labels = []  # Labels with animation
        self.animation_running = True
        self.current_offset = 0
        self.current_query = None
        self.current_mode = "trending"  # "trending" or "search"
        self.all_gifs = []  # Store current results

        self.window = tk.Toplevel(parent)
        self.window.title("GIPHY Browser")
        self.window.geometry("850x650")
        self.window.configure(bg="#1a1a2e")
        self.window.transient(parent)
        self.window.grab_set()
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

        # Check API key
        api_key = load_giphy_key()
        if not api_key:
            self.show_api_key_prompt()
            return

        self.create_ui()
        self._start_animation()

        # Load trending on open
        self.search_trending()

    def _on_close(self):
        self.animation_running = False
        self.window.destroy()

    def show_api_key_prompt(self):
        frame = tk.Frame(self.window, bg="#1a1a2e")
        frame.pack(expand=True, fill=tk.BOTH, padx=20, pady=20)

        tk.Label(frame, text="GIPHY API Key Required", font=("Segoe UI", 16, "bold"),
                bg="#1a1a2e", fg="white").pack(pady=20)

        tk.Label(frame, text="1. Go to developers.giphy.com and create a free account",
                bg="#1a1a2e", fg="#aaa", font=("Segoe UI", 11)).pack(pady=5)
        tk.Label(frame, text="2. Create an App and copy your API Key",
                bg="#1a1a2e", fg="#aaa", font=("Segoe UI", 11)).pack(pady=5)
        tk.Label(frame, text="3. Paste it below:",
                bg="#1a1a2e", fg="#aaa", font=("Segoe UI", 11)).pack(pady=5)

        self.key_entry = tk.Entry(frame, width=50, font=("Segoe UI", 11))
        self.key_entry.pack(pady=15)

        tk.Button(frame, text="Save API Key", command=self.save_api_key,
                 bg="#27ae60", fg="white", font=("Segoe UI", 11, "bold"),
                 padx=20, pady=8).pack(pady=10)

    def save_api_key(self):
        global GIPHY_API_KEY
        key = self.key_entry.get().strip()
        if key:
            GIPHY_API_KEY = key
            with open(GIPHY_KEY_FILE, 'w') as f:
                f.write(key)
            # Recreate UI
            for widget in self.window.winfo_children():
                widget.destroy()
            self.create_ui()
            self._start_animation()
            self.search_trending()

    def create_ui(self):
        # Search bar
        search_frame = tk.Frame(self.window, bg="#1a1a2e")
        search_frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(search_frame, text="Search:", bg="#1a1a2e", fg="white",
                font=("Segoe UI", 11)).pack(side=tk.LEFT, padx=5)

        self.search_entry = tk.Entry(search_frame, width=40, font=("Segoe UI", 11))
        self.search_entry.pack(side=tk.LEFT, padx=5)
        self.search_entry.bind("<Return>", lambda e: self.search())

        tk.Button(search_frame, text="Search", command=self.search,
                 bg="#3498db", fg="white", font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=5)

        tk.Button(search_frame, text="Trending", command=self.search_trending,
                 bg="#9b59b6", fg="white", font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=5)

        # Results area with scrollbar
        results_container = tk.Frame(self.window, bg="#16213e")
        results_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        canvas = tk.Canvas(results_container, bg="#16213e", highlightthickness=0)
        scrollbar = ttk.Scrollbar(results_container, orient="vertical", command=canvas.yview)
        self.results_frame = tk.Frame(canvas, bg="#16213e")

        self.results_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.results_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Mouse wheel scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.canvas = canvas

        # Bottom bar with status and Load More
        bottom_frame = tk.Frame(self.window, bg="#1a1a2e")
        bottom_frame.pack(fill=tk.X, padx=10, pady=5)

        self.status_label = tk.Label(bottom_frame, text="", bg="#1a1a2e", fg="#888",
                                     font=("Segoe UI", 10))
        self.status_label.pack(side=tk.LEFT)

        self.load_more_btn = tk.Button(bottom_frame, text="Load More", command=self.load_more,
                                       bg="#e67e22", fg="white", font=("Segoe UI", 10, "bold"),
                                       padx=15)
        self.load_more_btn.pack(side=tk.RIGHT, padx=5)

    def _start_animation(self):
        """Start the animation loop for thumbnails"""
        def animate():
            if not self.animation_running:
                return
            for item in self.animated_labels:
                if item.get("frames") and len(item["frames"]) > 1:
                    item["current"] = (item["current"] + 1) % len(item["frames"])
                    try:
                        item["label"].config(image=item["frames"][item["current"]])
                    except:
                        pass
            if self.animation_running:
                self.window.after(100, animate)
        animate()

    def search(self):
        query = self.search_entry.get().strip()
        if not query:
            return
        self.current_query = query
        self.current_mode = "search"
        self.current_offset = 0
        self.all_gifs = []
        self.status_label.config(text=f"Searching for '{query}'...")
        threading.Thread(target=self._fetch_search, args=(query, 0), daemon=True).start()

    def search_trending(self):
        self.current_mode = "trending"
        self.current_query = None
        self.current_offset = 0
        self.all_gifs = []
        self.status_label.config(text="Loading trending GIFs...")
        threading.Thread(target=self._fetch_trending, args=(0,), daemon=True).start()

    def load_more(self):
        self.current_offset += 25
        self.status_label.config(text="Loading more...")
        if self.current_mode == "search" and self.current_query:
            threading.Thread(target=self._fetch_search, args=(self.current_query, self.current_offset), daemon=True).start()
        else:
            threading.Thread(target=self._fetch_trending, args=(self.current_offset,), daemon=True).start()

    def _fetch_search(self, query, offset):
        try:
            url = f"https://api.giphy.com/v1/gifs/search?api_key={GIPHY_API_KEY}&q={query}&limit=25&offset={offset}&rating=g"
            response = requests.get(url, timeout=10)
            data = response.json()
            gifs = data.get("data", [])
            is_append = offset > 0
            self.window.after(0, lambda: self._display_results(gifs, append=is_append))
        except Exception as e:
            self.window.after(0, lambda: self.status_label.config(text=f"Error: {e}"))

    def _fetch_trending(self, offset):
        try:
            url = f"https://api.giphy.com/v1/gifs/trending?api_key={GIPHY_API_KEY}&limit=25&offset={offset}&rating=g"
            response = requests.get(url, timeout=10)
            data = response.json()
            gifs = data.get("data", [])
            is_append = offset > 0
            self.window.after(0, lambda: self._display_results(gifs, append=is_append))
        except Exception as e:
            self.window.after(0, lambda: self.status_label.config(text=f"Error: {e}"))

    def _display_results(self, gifs, append=False):
        if not append:
            # Clear previous results
            for widget in self.results_frame.winfo_children():
                widget.destroy()
            self.thumbnails.clear()
            self.animated_labels.clear()
            self.all_gifs = []

        if not gifs:
            if not append:
                self.status_label.config(text="No results found")
            else:
                self.status_label.config(text="No more results")
            return

        start_idx = len(self.all_gifs)
        self.all_gifs.extend(gifs)

        self.status_label.config(text=f"Showing {len(self.all_gifs)} GIFs - click to select")

        # Display in grid (5 columns)
        cols = 5
        for i, gif in enumerate(gifs):
            idx = start_idx + i
            row, col = idx // cols, idx % cols

            # Get thumbnail URL - use fixed_width for better animation
            thumb_url = gif.get("images", {}).get("fixed_width_small", {}).get("url", "")
            original_url = gif.get("images", {}).get("original", {}).get("url", "")
            title = gif.get("title", "GIF")[:20]

            # Create frame for this GIF
            gif_frame = tk.Frame(self.results_frame, bg="#2a2a4a", padx=3, pady=3)
            gif_frame.grid(row=row, column=col, padx=5, pady=5, sticky="n")

            # Load thumbnail async with animation
            self._load_thumbnail(gif_frame, thumb_url, original_url, title)

    def _load_thumbnail(self, frame, thumb_url, original_url, title):
        def load():
            try:
                response = requests.get(thumb_url, timeout=10)
                img_data = io.BytesIO(response.content)
                img = Image.open(img_data)

                # Load frames for animation (limit to 15 frames to save memory)
                frames = []
                max_frames = min(15, getattr(img, 'n_frames', 1))
                try:
                    for frame_idx in range(max_frames):
                        img.seek(frame_idx)
                        f = img.copy().convert("RGBA").resize((100, 75), Image.LANCZOS)
                        frames.append(ImageTk.PhotoImage(f))
                except EOFError:
                    pass

                if not frames:
                    img = img.convert("RGBA").resize((100, 75), Image.LANCZOS)
                    frames = [ImageTk.PhotoImage(img)]

                def update_ui():
                    self.thumbnails.extend(frames)  # Keep reference

                    label = tk.Label(frame, image=frames[0], bg="#2a2a4a", cursor="hand2")
                    label.pack()
                    label.bind("<Button-1>", lambda e: self._select_gif(original_url, title))

                    # Store for animation
                    if len(frames) > 1:
                        self.animated_labels.append({
                            "label": label,
                            "frames": frames,
                            "current": 0
                        })

                    name_label = tk.Label(frame, text=title, bg="#2a2a4a", fg="#aaa",
                                         font=("Segoe UI", 8), wraplength=100)
                    name_label.pack()
                    name_label.bind("<Button-1>", lambda e: self._select_gif(original_url, title))

                self.window.after(0, update_ui)
            except:
                pass

        threading.Thread(target=load, daemon=True).start()

    def _select_gif(self, url, title):
        self.status_label.config(text=f"Downloading '{title}'...")
        threading.Thread(target=self._download_gif, args=(url, title), daemon=True).start()

    def _download_gif(self, url, title):
        try:
            response = requests.get(url, timeout=30)

            # Create safe filename
            safe_name = "".join(c for c in title if c.isalnum() or c in " -_")[:30].strip()
            if not safe_name:
                safe_name = "giphy"
            filename = f"{safe_name}.gif"

            # Ensure unique filename
            filepath = os.path.join(LOCAL_ICONS_DIR, filename)
            counter = 1
            while os.path.exists(filepath):
                filename = f"{safe_name}_{counter}.gif"
                filepath = os.path.join(LOCAL_ICONS_DIR, filename)
                counter += 1

            # Save file
            os.makedirs(LOCAL_ICONS_DIR, exist_ok=True)
            with open(filepath, 'wb') as f:
                f.write(response.content)

            def done():
                self.callback(filepath)
                self.window.destroy()

            self.window.after(0, done)
        except Exception as e:
            self.window.after(0, lambda: self.status_label.config(text=f"Download failed: {e}"))

DASHBOARD_TYPES = {
    "system_monitor": {"name": "System Monitor", "refresh_interval": 2},
    "windows_pc": {"name": "Windows PC", "refresh_interval": 2},
    "pihole": {"name": "Pi-hole", "refresh_interval": 5},
    "docker": {"name": "Docker", "refresh_interval": 3},
}

AVAILABLE_ACTIONS = [
    "media_playpause", "media_next", "media_prev", "media_stop",
    "volume_up", "volume_down", "volume_mute",
    "obs_record", "obs_stream", "obs_scene1", "obs_scene2",
    "lock_screen", "screenshot", "copy", "paste", "undo", "select_all",
    "custom_app"
]

# Default button library with common Windows tools
DEFAULT_LIBRARY = [
    {"name": "Play/Pause", "label": "PLAY", "action": "media_playpause", "color": [46, 204, 113], "icon": None, "background": None, "app_path": None},
    {"name": "Next Track", "label": "NEXT", "action": "media_next", "color": [52, 152, 219], "icon": None, "background": None, "app_path": None},
    {"name": "Prev Track", "label": "PREV", "action": "media_prev", "color": [155, 89, 182], "icon": None, "background": None, "app_path": None},
    {"name": "Volume Up", "label": "VOL+", "action": "volume_up", "color": [241, 196, 15], "icon": None, "background": None, "app_path": None},
    {"name": "Volume Down", "label": "VOL-", "action": "volume_down", "color": [230, 126, 34], "icon": None, "background": None, "app_path": None},
    {"name": "Mute", "label": "MUTE", "action": "volume_mute", "color": [231, 76, 60], "icon": None, "background": None, "app_path": None},
    {"name": "OBS Record", "label": "REC", "action": "obs_record", "color": [192, 57, 43], "icon": None, "background": None, "app_path": None},
    {"name": "OBS Stream", "label": "STREAM", "action": "obs_stream", "color": [142, 68, 173], "icon": None, "background": None, "app_path": None},
    {"name": "Lock Screen", "label": "LOCK", "action": "lock_screen", "color": [44, 62, 80], "icon": None, "background": None, "app_path": None},
    {"name": "Screenshot", "label": "SNAP", "action": "screenshot", "color": [41, 128, 185], "icon": None, "background": None, "app_path": None},
    {"name": "Copy", "label": "COPY", "action": "copy", "color": [39, 174, 96], "icon": None, "background": None, "app_path": None},
    {"name": "Paste", "label": "PASTE", "action": "paste", "color": [211, 84, 0], "icon": None, "background": None, "app_path": None},
    {"name": "Undo", "label": "UNDO", "action": "undo", "color": [127, 140, 141], "icon": None, "background": None, "app_path": None},
]

DEFAULT_CONFIG = {
    "windows_ip": "192.168.1.13",
    "background_color": [25, 25, 35],
    "current_profile": "Default",
    "pages": [
        {
            "name": "Page 1",
            "type": "button",
            "buttons": [
                {"label": "", "action": "", "color": [60, 60, 80], "icon": None, "background": None, "app_path": None}
                for _ in range(6)
            ]
        }
    ]
}

class StreamDeckEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("Stream Deck Editor v3")
        self.root.geometry("1300x750")
        self.root.configure(bg="#1a1a2e")

        # Ensure directories exist
        os.makedirs(LOCAL_ICONS_DIR, exist_ok=True)
        os.makedirs(PROFILES_DIR, exist_ok=True)

        self.config = self.load_config()
        self.migrate_config()
        self.library = self.load_library()
        self.current_page = 0
        self.selected_button = None
        self.dragging_button = None
        self.gif_animations = {}  # Store GIF animation data
        self.animation_running = False

        self.create_ui()
        self.refresh_preview()
        self.refresh_library()
        self.start_gif_animation()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return copy.deepcopy(DEFAULT_CONFIG)

    def migrate_config(self):
        """Add 'type' field to pages that don't have it (backwards compatibility)"""
        for page in self.config.get("pages", []):
            if "type" not in page:
                if "buttons" in page:
                    page["type"] = "button"
                else:
                    page["type"] = "dashboard"

    def is_dashboard_page(self, page_idx=None):
        if page_idx is None:
            page_idx = self.current_page
        page = self.config["pages"][page_idx]
        return page.get("type") == "dashboard"

    def get_button_pages(self):
        """Return only button-type pages (for script generation)"""
        return [p for p in self.config["pages"] if p.get("type", "button") == "button"]

    def get_dashboard_pages(self):
        """Return only dashboard-type pages"""
        return [p for p in self.config["pages"] if p.get("type") == "dashboard"]

    def save_config(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=2)
        self.show_status("Configuration saved!")

    def load_library(self):
        if os.path.exists(LIBRARY_FILE):
            try:
                with open(LIBRARY_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return copy.deepcopy(DEFAULT_LIBRARY)

    def save_library(self):
        with open(LIBRARY_FILE, 'w') as f:
            json.dump(self.library, f, indent=2)

    def create_ui(self):
        # Main container with 3 columns
        main = tk.Frame(self.root, bg="#1a1a2e")
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left panel - Button Library
        left = tk.Frame(main, bg="#16213e", width=280)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left.pack_propagate(False)

        self.create_library_panel(left)

        # Center panel - Preview
        center = tk.Frame(main, bg="#16213e", width=500)
        center.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 10))
        center.pack_propagate(False)

        self.create_preview_panel(center)

        # Right panel - Editor & Settings
        right = tk.Frame(main, bg="#1a1a2e")
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.create_settings_panel(right)
        self.create_editor_panel(right)
        self.create_bottom_buttons(right)

    def create_library_panel(self, parent):
        tk.Label(parent, text="Button Library", font=("Segoe UI", 14, "bold"),
                bg="#16213e", fg="white").pack(pady=10)

        # Library buttons frame with scrollbar
        lib_container = tk.Frame(parent, bg="#16213e")
        lib_container.pack(fill=tk.BOTH, expand=True, padx=5)

        canvas = tk.Canvas(lib_container, bg="#16213e", highlightthickness=0)
        scrollbar = ttk.Scrollbar(lib_container, orient="vertical", command=canvas.yview)
        self.library_frame = tk.Frame(canvas, bg="#16213e")

        self.library_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.library_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Library action buttons
        btn_frame = tk.Frame(parent, bg="#16213e")
        btn_frame.pack(fill=tk.X, pady=10, padx=5)

        tk.Button(btn_frame, text="+ Add", command=self.add_to_library,
                 bg="#27ae60", fg="white", font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="Edit", command=self.edit_library_item,
                 bg="#3498db", fg="white", font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="Delete", command=self.delete_library_item,
                 bg="#e74c3c", fg="white", font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=2)

    def create_preview_panel(self, parent):
        tk.Label(parent, text="Preview", font=("Segoe UI", 14, "bold"),
                bg="#16213e", fg="white").pack(pady=10)

        # Profile selector
        profile_frame = tk.Frame(parent, bg="#16213e")
        profile_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(profile_frame, text="Profile:", bg="#16213e", fg="white",
                font=("Segoe UI", 10)).pack(side=tk.LEFT)

        self.profile_combo = ttk.Combobox(profile_frame, width=15)
        self.profile_combo.pack(side=tk.LEFT, padx=5)
        self.profile_combo.bind("<<ComboboxSelected>>", self.on_profile_change)
        self.refresh_profiles()

        tk.Button(profile_frame, text="Save", command=self.save_profile,
                 bg="#27ae60", fg="white", font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=2)
        tk.Button(profile_frame, text="Save As", command=self.save_profile_as,
                 bg="#3498db", fg="white", font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=2)
        tk.Button(profile_frame, text="Delete", command=self.delete_profile,
                 bg="#e74c3c", fg="white", font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=2)

        # Preview canvas
        self.preview_frame = tk.Frame(parent, bg="#0f0f23", width=480, height=320)
        self.preview_frame.pack(padx=10, pady=10)
        self.preview_frame.pack_propagate(False)

        self.preview_canvas = tk.Canvas(self.preview_frame, width=480, height=320,
                                        bg="#0f0f23", highlightthickness=0)
        self.preview_canvas.pack()

        # Enable drop on canvas
        self.preview_canvas.bind("<Button-1>", self.on_preview_click)

        # Page navigation
        nav_frame = tk.Frame(parent, bg="#16213e")
        nav_frame.pack(pady=10)

        tk.Button(nav_frame, text="< Prev", command=self.prev_page,
                 bg="#4a4a6a", fg="white", font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=5)

        self.page_label = tk.Label(nav_frame, text="Page 1/1", font=("Segoe UI", 12),
                                   bg="#16213e", fg="white")
        self.page_label.pack(side=tk.LEFT, padx=20)

        tk.Button(nav_frame, text="Next >", command=self.next_page,
                 bg="#4a4a6a", fg="white", font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=5)

        tk.Button(nav_frame, text="+ Page", command=self.add_page,
                 bg="#2d6a4f", fg="white", font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=15)

        tk.Button(nav_frame, text="+ Dashboard", command=self.add_dashboard_page,
                 bg="#4a2d6a", fg="white", font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=5)

        tk.Button(nav_frame, text="- Page", command=self.delete_page,
                 bg="#6a2d2d", fg="white", font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=5)

    def create_settings_panel(self, parent):
        settings_frame = tk.LabelFrame(parent, text="Settings", font=("Segoe UI", 11, "bold"),
                                       bg="#16213e", fg="white", padx=10, pady=5)
        settings_frame.pack(fill=tk.X, pady=(0, 10))

        # Windows IP
        ip_row = tk.Frame(settings_frame, bg="#16213e")
        ip_row.pack(fill=tk.X, pady=3)
        tk.Label(ip_row, text="Windows IP:", bg="#16213e", fg="white",
                font=("Segoe UI", 10)).pack(side=tk.LEFT)
        self.ip_entry = tk.Entry(ip_row, width=15, font=("Segoe UI", 10))
        self.ip_entry.insert(0, self.config.get("windows_ip", "192.168.1.13"))
        self.ip_entry.pack(side=tk.LEFT, padx=10)

        # Background color
        bg_row = tk.Frame(settings_frame, bg="#16213e")
        bg_row.pack(fill=tk.X, pady=3)
        tk.Label(bg_row, text="Background:", bg="#16213e", fg="white",
                font=("Segoe UI", 10)).pack(side=tk.LEFT)
        self.bg_color_btn = tk.Button(bg_row, text="   ", width=5,
                                      command=self.pick_bg_color)
        self.bg_color_btn.pack(side=tk.LEFT, padx=10)
        self.update_bg_color_btn()

    def create_editor_panel(self, parent):
        self.editor_frame = tk.LabelFrame(parent, text="Button Editor",
                                          font=("Segoe UI", 11, "bold"),
                                          bg="#16213e", fg="white", padx=10, pady=5)
        self.editor_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        tk.Label(self.editor_frame, text="Click a button to edit\nor drag from library",
                bg="#16213e", fg="#888", font=("Segoe UI", 10, "italic")).pack(pady=30)

    def create_bottom_buttons(self, parent):
        bottom = tk.Frame(parent, bg="#1a1a2e")
        bottom.pack(fill=tk.X)

        tk.Button(bottom, text="Save Config", command=self.save_config,
                 bg="#3498db", fg="white", font=("Segoe UI", 11, "bold"),
                 padx=15, pady=8).pack(side=tk.LEFT, padx=5)

        tk.Button(bottom, text="Deploy to Pi", command=self.deploy_to_pi,
                 bg="#27ae60", fg="white", font=("Segoe UI", 11, "bold"),
                 padx=20, pady=8).pack(side=tk.LEFT, padx=5)

        # Status bar
        self.status_label = tk.Label(parent, text="", font=("Segoe UI", 10),
                                     bg="#1a1a2e", fg="#888", anchor="w")
        self.status_label.pack(fill=tk.X, pady=(10, 0))

    def show_status(self, message, is_error=False):
        color = "#e74c3c" if is_error else "#2ecc71"
        self.status_label.config(text=message, fg=color)
        self.root.after(5000, lambda: self.status_label.config(text="", fg="#888"))

    def start_gif_animation(self):
        """Start the GIF animation loop"""
        self.animation_running = True
        self.animation_interval = 100  # Start at 100ms (10fps)
        self.animate_gifs()

    def animate_gifs(self):
        """Cycle through GIF frames with adaptive rate"""
        if not self.animation_running:
            return

        # Count active GIFs for adaptive rate
        active_gifs = len(self.gif_animations)

        for key, data in self.gif_animations.items():
            frames = data["frames"]
            if len(frames) > 1:
                data["current"] = (data["current"] + 1) % len(frames)
                try:
                    self.preview_canvas.itemconfig(data["canvas_id"], image=frames[data["current"]])
                except:
                    pass  # Canvas item may no longer exist

        # Adaptive animation rate: slow down when many GIFs active
        if active_gifs > 6:
            self.animation_interval = min(200, 100 + (active_gifs - 6) * 15)
        else:
            self.animation_interval = 100

        # Schedule next frame
        self.root.after(self.animation_interval, self.animate_gifs)

    def refresh_library(self):
        # Clear existing
        for widget in self.library_frame.winfo_children():
            widget.destroy()

        self.library_buttons = []

        for i, item in enumerate(self.library):
            btn_frame = tk.Frame(self.library_frame, bg="#2a2a4a", padx=5, pady=5)
            btn_frame.pack(fill=tk.X, pady=2, padx=5)

            # Color indicator
            color = item.get("color", [100, 100, 100])
            hex_color = "#{:02x}{:02x}{:02x}".format(*color)

            color_box = tk.Label(btn_frame, bg=hex_color, width=3)
            color_box.pack(side=tk.LEFT, padx=(0, 5))

            # Name label
            name = item.get("name", item.get("label", "Button"))
            lbl = tk.Label(btn_frame, text=name, bg="#2a2a4a", fg="white",
                          font=("Segoe UI", 10), anchor="w")
            lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

            # Bind drag events
            for widget in [btn_frame, color_box, lbl]:
                widget.bind("<Button-1>", lambda e, idx=i: self.start_drag(idx))
                widget.bind("<B1-Motion>", self.on_drag)
                widget.bind("<ButtonRelease-1>", self.end_drag)

            self.library_buttons.append(btn_frame)

    def start_drag(self, idx):
        self.dragging_button = idx
        self.selected_library_idx = idx
        # Highlight selected
        for i, btn in enumerate(self.library_buttons):
            btn.configure(bg="#27ae60" if i == idx else "#2a2a4a")
            for child in btn.winfo_children():
                if isinstance(child, tk.Label) and child.cget("width") != 3:
                    child.configure(bg="#27ae60" if i == idx else "#2a2a4a")

    def on_drag(self, event):
        pass  # Visual feedback could be added here

    def end_drag(self, event):
        if self.dragging_button is None:
            return

        if self.is_dashboard_page():
            self.dragging_button = None
            return

        # Get mouse position relative to preview canvas
        x = self.preview_canvas.winfo_pointerx() - self.preview_canvas.winfo_rootx()
        y = self.preview_canvas.winfo_pointery() - self.preview_canvas.winfo_rooty()

        # Check if dropped on a button
        dropped = False
        for rect in self.button_rects:
            x1, y1, x2, y2, idx = rect
            if x1 <= x <= x2 and y1 <= y <= y2:
                # Copy library button to this slot
                lib_btn = copy.deepcopy(self.library[self.dragging_button])
                # Remove 'name' field as it's library-only
                lib_btn.pop('name', None)
                self.config["pages"][self.current_page]["buttons"][idx] = lib_btn
                self.refresh_preview()
                self.root.update_idletasks()
                self.select_button(idx)
                self.show_status(f"Button added to slot {idx + 1}")
                dropped = True
                break

        self.dragging_button = None

    MAX_GIF_FRAMES = 45  # Limit frames for memory/performance

    def load_gif_frames(self, path, size, use_cover=False):
        """Load frames from a GIF or animated WebP file (limited to MAX_GIF_FRAMES)"""
        frames = []
        try:
            img = Image.open(path)
            frame_count = min(getattr(img, 'n_frames', 1), self.MAX_GIF_FRAMES)
            for frame_num in range(frame_count):
                img.seek(frame_num)
                frame = img.copy().convert('RGBA')
                if use_cover:
                    frame = cover_resize(frame, size[0], size[1])
                else:
                    frame = frame.resize(size)
                frames.append(ImageTk.PhotoImage(frame))
        except:
            pass
        return frames

    def is_animated_image(self, path):
        """Check if path is a GIF or WebP (potentially animated)"""
        if not path:
            return False
        lower = path.lower()
        return lower.endswith('.gif') or lower.endswith('.webp')

    def refresh_preview(self):
        self.preview_canvas.delete("all")

        # Cleanup old PhotoImage objects before creating new ones
        if not hasattr(self, 'photos'):
            self.photos = []
        else:
            # Explicitly delete old photos to free memory
            for photo in self.photos:
                try:
                    del photo
                except:
                    pass
        self.photos.clear()
        self.gif_animations = {}  # Reset GIF data

        # Force garbage collection to free memory from old frames
        import gc
        gc.collect()

        bg = self.config.get("background_color", [25, 25, 35])
        bg_hex = "#{:02x}{:02x}{:02x}".format(*bg)
        self.preview_canvas.configure(bg=bg_hex)

        page = self.config["pages"][self.current_page]

        # Dashboard pages: show info label instead of button grid
        if page.get("type") == "dashboard":
            self.button_rects = []
            dashboard_type = page.get("dashboard_type", "unknown")
            display_name = DASHBOARD_TYPES.get(dashboard_type, {}).get("name", dashboard_type)
            refresh = page.get("refresh_interval", 2)

            # Draw dashboard placeholder
            self.preview_canvas.create_rectangle(40, 40, 440, 200, fill="#1e1e3a", outline="#4a4a8a", width=2)
            self.preview_canvas.create_text(240, 90, text=display_name,
                                            fill="#9b59b6", font=("Segoe UI", 20, "bold"))
            self.preview_canvas.create_text(240, 125, text="Dashboard Page",
                                            fill="#888", font=("Segoe UI", 12))
            self.preview_canvas.create_text(240, 155, text=f"Refresh: {refresh}s",
                                            fill="#666", font=("Segoe UI", 10))
            self.preview_canvas.create_text(240, 180, text="(rendered on Pi at runtime)",
                                            fill="#555", font=("Segoe UI", 9, "italic"))

            # Navigation bar
            nav_y = 320 - 70
            self.preview_canvas.create_rectangle(0, nav_y, 480, 320, fill="#282840", outline="")
            page_text = f"{self.current_page + 1}/{len(self.config['pages'])}"
            self.preview_canvas.create_text(240, nav_y + 35, text=page_text,
                                            fill="#aaa", font=("Segoe UI", 14))
            self.page_label.config(text=f"Page {self.current_page + 1}/{len(self.config['pages'])} - {display_name}")

            # Clear button editor for dashboard pages
            for widget in self.editor_frame.winfo_children():
                widget.destroy()
            tk.Label(self.editor_frame, text=f"{display_name} Dashboard",
                    bg="#16213e", fg="#9b59b6", font=("Segoe UI", 12, "bold")).pack(pady=10)
            tk.Label(self.editor_frame, text="Dashboard pages are rendered\ndirectly on the Pi at runtime.\n\nNo button editing needed.",
                    bg="#16213e", fg="#888", font=("Segoe UI", 10, "italic")).pack(pady=20)

            # Refresh interval editor
            interval_frame = tk.Frame(self.editor_frame, bg="#16213e")
            interval_frame.pack(fill=tk.X, pady=5, padx=10)
            tk.Label(interval_frame, text="Refresh (s):", bg="#16213e", fg="white",
                    font=("Segoe UI", 10)).pack(side=tk.LEFT)
            interval_entry = tk.Entry(interval_frame, width=5, font=("Segoe UI", 10))
            interval_entry.insert(0, str(refresh))
            interval_entry.pack(side=tk.LEFT, padx=5)

            def apply_interval(entry=interval_entry):
                try:
                    val = int(entry.get())
                    if val > 0:
                        self.config["pages"][self.current_page]["refresh_interval"] = val
                        self.show_status(f"Refresh interval set to {val}s")
                except ValueError:
                    self.show_status("Invalid interval", is_error=True)

            tk.Button(interval_frame, text="Apply", command=apply_interval,
                     bg="#27ae60", fg="white", font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=5)
            return

        buttons = page.get("buttons", [])

        # Button dimensions
        cols, rows = 3, 2
        margin = 10
        nav_height = 70
        btn_w = (480 - (cols + 1) * margin) // cols
        btn_h = (320 - nav_height - (rows + 1) * margin) // rows

        self.button_rects = []

        for i, btn in enumerate(buttons[:6]):  # Max 6 buttons
            row, col = i // cols, i % cols
            x1 = margin + col * (btn_w + margin)
            y1 = margin + row * (btn_h + margin)
            x2 = x1 + btn_w
            y2 = y1 + btn_h

            color = btn.get("color", [100, 100, 100])
            hex_color = "#{:02x}{:02x}{:02x}".format(*color)

            # Draw button
            self.preview_canvas.create_rectangle(x1, y1, x2, y2, fill=hex_color,
                                                  outline="white", width=2)

            # Draw background image
            bg_path = btn.get("background")
            if bg_path and os.path.exists(bg_path):
                try:
                    if self.is_animated_image(bg_path):
                        # Animated GIF/WebP
                        frames = self.load_gif_frames(bg_path, (btn_w - 4, btn_h - 4), use_cover=True)
                        if frames and len(frames) > 1:
                            canvas_id = self.preview_canvas.create_image(x1 + 2, y1 + 2, image=frames[0], anchor="nw")
                            self.gif_animations[f"bg_{i}"] = {
                                "frames": frames, "current": 0, "canvas_id": canvas_id
                            }
                            self.photos.extend(frames)
                        elif frames:
                            # Single frame WebP/GIF
                            self.preview_canvas.create_image(x1 + 2, y1 + 2, image=frames[0], anchor="nw")
                            self.photos.extend(frames)
                    else:
                        img = cover_resize(Image.open(bg_path), btn_w - 4, btn_h - 4)
                        photo = ImageTk.PhotoImage(img)
                        self.preview_canvas.create_image(x1 + 2, y1 + 2, image=photo, anchor="nw")
                        self.photos.append(photo)
                except:
                    pass

            # Draw icon
            icon_path = btn.get("icon")
            if icon_path and os.path.exists(icon_path):
                try:
                    if self.is_animated_image(icon_path):
                        # Animated GIF/WebP
                        frames = self.load_gif_frames(icon_path, (50, 50))
                        if frames and len(frames) > 1:
                            canvas_id = self.preview_canvas.create_image((x1+x2)//2, y1 + 35, image=frames[0])
                            self.gif_animations[f"icon_{i}"] = {
                                "frames": frames, "current": 0, "canvas_id": canvas_id
                            }
                            self.photos.extend(frames)
                        elif frames:
                            # Single frame WebP/GIF
                            self.preview_canvas.create_image((x1+x2)//2, y1 + 35, image=frames[0])
                            self.photos.extend(frames)
                    else:
                        img = Image.open(icon_path).resize((50, 50))
                        photo = ImageTk.PhotoImage(img)
                        self.preview_canvas.create_image((x1+x2)//2, y1 + 35, image=photo)
                        self.photos.append(photo)
                except:
                    pass

            # Label
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

        page_name = page.get("name", f"Page {self.current_page + 1}")
        self.page_label.config(text=f"Page {self.current_page + 1}/{len(self.config['pages'])} - {page_name}")

    def on_preview_click(self, event):
        if self.is_dashboard_page():
            return
        for x1, y1, x2, y2, idx in self.button_rects:
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                self.select_button(idx)
                return

    def select_button(self, idx):
        self.selected_button = idx
        btn = self.config["pages"][self.current_page]["buttons"][idx]

        # Initialize selections
        self.selected_app_path = btn.get("app_path")
        self.selected_background = btn.get("background")
        self.selected_icon = btn.get("icon")

        # Clear editor frame
        for widget in self.editor_frame.winfo_children():
            widget.destroy()

        tk.Label(self.editor_frame, text=f"Editing Button {idx + 1}",
                bg="#16213e", fg="white", font=("Segoe UI", 12, "bold")).pack(pady=5)

        # Label
        row = tk.Frame(self.editor_frame, bg="#16213e")
        row.pack(fill=tk.X, pady=3)
        tk.Label(row, text="Label:", bg="#16213e", fg="white", width=10, anchor="w").pack(side=tk.LEFT)
        self.label_entry = tk.Entry(row, width=20, font=("Segoe UI", 10))
        self.label_entry.insert(0, btn.get("label", ""))
        self.label_entry.pack(side=tk.LEFT, padx=5)

        # Action
        row = tk.Frame(self.editor_frame, bg="#16213e")
        row.pack(fill=tk.X, pady=3)
        tk.Label(row, text="Action:", bg="#16213e", fg="white", width=10, anchor="w").pack(side=tk.LEFT)
        self.action_combo = ttk.Combobox(row, values=AVAILABLE_ACTIONS, width=18)
        self.action_combo.set(btn.get("action", ""))
        self.action_combo.pack(side=tk.LEFT, padx=5)

        # App Path
        row = tk.Frame(self.editor_frame, bg="#16213e")
        row.pack(fill=tk.X, pady=3)
        tk.Label(row, text="App Path:", bg="#16213e", fg="white", width=10, anchor="w").pack(side=tk.LEFT)
        app_path = btn.get("app_path", "")
        self.app_path_label = tk.Label(row, text=os.path.basename(app_path) if app_path else "None",
                                       bg="#16213e", fg="#aaa", width=12, anchor="w")
        self.app_path_label.pack(side=tk.LEFT, padx=5)
        tk.Button(row, text="Browse", command=self.pick_app_path, bg="#4a4a6a", fg="white").pack(side=tk.LEFT, padx=2)
        tk.Button(row, text="Clear", command=self.clear_app_path, bg="#6a4a4a", fg="white").pack(side=tk.LEFT, padx=2)

        # Color
        row = tk.Frame(self.editor_frame, bg="#16213e")
        row.pack(fill=tk.X, pady=3)
        tk.Label(row, text="Color:", bg="#16213e", fg="white", width=10, anchor="w").pack(side=tk.LEFT)
        self.btn_color = btn.get("color", [100, 100, 100])
        hex_color = "#{:02x}{:02x}{:02x}".format(*self.btn_color)
        self.color_btn = tk.Button(row, text="   ", bg=hex_color, width=5, command=self.pick_btn_color)
        self.color_btn.pack(side=tk.LEFT, padx=5)

        # Background
        row = tk.Frame(self.editor_frame, bg="#16213e")
        row.pack(fill=tk.X, pady=3)
        tk.Label(row, text="Background:", bg="#16213e", fg="white", width=10, anchor="w").pack(side=tk.LEFT)
        bg_path = btn.get("background", "")
        self.bg_label = tk.Label(row, text=os.path.basename(bg_path) if bg_path else "None",
                                 bg="#16213e", fg="#aaa", width=12, anchor="w")
        self.bg_label.pack(side=tk.LEFT, padx=5)
        tk.Button(row, text="Browse", command=self.pick_background, bg="#4a4a6a", fg="white").pack(side=tk.LEFT, padx=2)
        tk.Button(row, text="GIPHY", command=self.pick_background_giphy, bg="#00ff99", fg="black").pack(side=tk.LEFT, padx=2)
        tk.Button(row, text="Clear", command=self.clear_background, bg="#6a4a4a", fg="white").pack(side=tk.LEFT, padx=2)

        # Icon
        row = tk.Frame(self.editor_frame, bg="#16213e")
        row.pack(fill=tk.X, pady=3)
        tk.Label(row, text="Icon:", bg="#16213e", fg="white", width=10, anchor="w").pack(side=tk.LEFT)
        icon_path = btn.get("icon", "")
        self.icon_label = tk.Label(row, text=os.path.basename(icon_path) if icon_path else "None",
                                   bg="#16213e", fg="#aaa", width=12, anchor="w")
        self.icon_label.pack(side=tk.LEFT, padx=5)
        tk.Button(row, text="Browse", command=self.pick_icon, bg="#4a4a6a", fg="white").pack(side=tk.LEFT, padx=2)
        tk.Button(row, text="GIPHY", command=self.pick_icon_giphy, bg="#00ff99", fg="black").pack(side=tk.LEFT, padx=2)
        tk.Button(row, text="Clear", command=self.clear_icon, bg="#6a4a4a", fg="white").pack(side=tk.LEFT, padx=2)

        # Buttons
        btn_row = tk.Frame(self.editor_frame, bg="#16213e")
        btn_row.pack(fill=tk.X, pady=10)

        tk.Button(btn_row, text="Apply", command=self.apply_changes,
                 bg="#27ae60", fg="white", font=("Segoe UI", 10, "bold"), padx=15).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_row, text="Save to Library", command=self.save_btn_to_library,
                 bg="#9b59b6", fg="white", font=("Segoe UI", 10), padx=10).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_row, text="Clear Button", command=self.clear_button,
                 bg="#e74c3c", fg="white", font=("Segoe UI", 10), padx=10).pack(side=tk.LEFT, padx=5)

    # Button editor methods
    def pick_app_path(self):
        path = filedialog.askopenfilename(filetypes=[("Executables", "*.exe *.lnk *.bat"), ("All", "*.*")])
        if path:
            self.selected_app_path = path
            self.app_path_label.config(text=os.path.basename(path))

    def clear_app_path(self):
        self.selected_app_path = None
        self.app_path_label.config(text="None")

    def pick_btn_color(self):
        color = colorchooser.askcolor(title="Button Color")[0]
        if color:
            self.btn_color = [int(c) for c in color]
            self.color_btn.configure(bg="#{:02x}{:02x}{:02x}".format(*self.btn_color))

    def pick_background(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.webp *.bmp")])
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
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.webp *.bmp")])
        if path:
            filename = os.path.basename(path)
            dest = os.path.join(LOCAL_ICONS_DIR, filename)
            shutil.copy(path, dest)
            self.selected_icon = dest
            self.icon_label.config(text=filename)

    def clear_icon(self):
        self.selected_icon = None
        self.icon_label.config(text="None")

    def pick_background_giphy(self):
        def callback(filepath):
            self.selected_background = filepath
            self.bg_label.config(text=os.path.basename(filepath))
            self.show_status(f"Downloaded: {os.path.basename(filepath)}")
        GiphyBrowser(self.root, callback, for_background=True)

    def pick_icon_giphy(self):
        def callback(filepath):
            self.selected_icon = filepath
            self.icon_label.config(text=os.path.basename(filepath))
            self.show_status(f"Downloaded: {os.path.basename(filepath)}")
        GiphyBrowser(self.root, callback, for_background=False)

    def apply_changes(self):
        if self.selected_button is None:
            return

        btn = self.config["pages"][self.current_page]["buttons"][self.selected_button]
        btn["label"] = self.label_entry.get()
        btn["action"] = self.action_combo.get()
        btn["color"] = self.btn_color
        btn["app_path"] = self.selected_app_path
        btn["background"] = self.selected_background
        btn["icon"] = self.selected_icon

        self.refresh_preview()
        self.show_status("Button updated!")

    def clear_button(self):
        if self.selected_button is None:
            return

        self.config["pages"][self.current_page]["buttons"][self.selected_button] = {
            "label": "", "action": "", "color": [60, 60, 80],
            "icon": None, "background": None, "app_path": None
        }
        self.refresh_preview()
        self.select_button(self.selected_button)
        self.show_status("Button cleared!")

    def save_btn_to_library(self):
        if self.selected_button is None:
            return

        name = simpledialog.askstring("Save to Library", "Enter button name:")
        if name:
            btn = copy.deepcopy(self.config["pages"][self.current_page]["buttons"][self.selected_button])
            btn["name"] = name
            self.library.append(btn)
            self.save_library()
            self.refresh_library()
            self.show_status(f"'{name}' added to library!")

    # Library methods
    def add_to_library(self):
        name = simpledialog.askstring("Add to Library", "Enter button name:")
        if name:
            new_btn = {
                "name": name, "label": name[:6].upper(), "action": "",
                "color": [100, 100, 100], "icon": None, "background": None, "app_path": None
            }
            self.library.append(new_btn)
            self.save_library()
            self.refresh_library()
            self.show_status(f"'{name}' added to library!")

    def edit_library_item(self):
        if not hasattr(self, 'selected_library_idx'):
            self.show_status("Select a library item first!", is_error=True)
            return

        idx = self.selected_library_idx
        item = self.library[idx]

        # Simple edit dialog
        name = simpledialog.askstring("Edit", "Button name:", initialvalue=item.get("name", ""))
        if name:
            item["name"] = name
            self.save_library()
            self.refresh_library()

    def delete_library_item(self):
        if not hasattr(self, 'selected_library_idx'):
            self.show_status("Select a library item first!", is_error=True)
            return

        idx = self.selected_library_idx
        del self.library[idx]
        self.save_library()
        self.refresh_library()
        self.show_status("Item deleted from library!")

    # Profile methods
    def refresh_profiles(self):
        profiles = ["Default"]
        if os.path.exists(PROFILES_DIR):
            for f in os.listdir(PROFILES_DIR):
                if f.endswith('.json'):
                    profiles.append(f[:-5])
        self.profile_combo['values'] = profiles
        current = self.config.get("current_profile", "Default")
        if current in profiles:
            self.profile_combo.set(current)
        else:
            self.profile_combo.set("Default")

    def on_profile_change(self, event):
        profile_name = self.profile_combo.get()
        if profile_name == "Default":
            self.config = copy.deepcopy(DEFAULT_CONFIG)
        else:
            path = os.path.join(PROFILES_DIR, f"{profile_name}.json")
            if os.path.exists(path):
                with open(path, 'r') as f:
                    self.config = json.load(f)

        self.migrate_config()
        self.config["current_profile"] = profile_name
        self.current_page = 0
        self.ip_entry.delete(0, tk.END)
        self.ip_entry.insert(0, self.config.get("windows_ip", "192.168.1.13"))
        self.update_bg_color_btn()
        self.refresh_preview()
        self.show_status(f"Profile '{profile_name}' loaded!")

    def save_profile(self):
        profile_name = self.profile_combo.get()
        if profile_name == "Default":
            self.save_config()
            return

        self.config["windows_ip"] = self.ip_entry.get()
        self.config["current_profile"] = profile_name

        path = os.path.join(PROFILES_DIR, f"{profile_name}.json")
        with open(path, 'w') as f:
            json.dump(self.config, f, indent=2)
        self.show_status(f"Profile '{profile_name}' saved!")

    def save_profile_as(self):
        name = simpledialog.askstring("Save Profile As", "Enter profile name:")
        if name:
            self.config["windows_ip"] = self.ip_entry.get()
            self.config["current_profile"] = name

            path = os.path.join(PROFILES_DIR, f"{name}.json")
            with open(path, 'w') as f:
                json.dump(self.config, f, indent=2)

            self.refresh_profiles()
            self.profile_combo.set(name)
            self.show_status(f"Profile '{name}' created!")

    def delete_profile(self):
        profile_name = self.profile_combo.get()
        if profile_name == "Default":
            self.show_status("Cannot delete Default profile!", is_error=True)
            return

        path = os.path.join(PROFILES_DIR, f"{profile_name}.json")
        if os.path.exists(path):
            os.remove(path)

        self.refresh_profiles()
        self.profile_combo.set("Default")
        self.on_profile_change(None)
        self.show_status(f"Profile '{profile_name}' deleted!")

    # Page methods
    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.refresh_preview()

    def next_page(self):
        if self.current_page < len(self.config["pages"]) - 1:
            self.current_page += 1
            self.refresh_preview()

    def add_page(self):
        button_count = sum(1 for p in self.config["pages"] if p.get("type", "button") == "button")
        new_page = {
            "name": f"Page {button_count + 1}",
            "type": "button",
            "buttons": [
                {"label": "", "action": "", "color": [60, 60, 80], "icon": None, "background": None, "app_path": None}
                for _ in range(6)
            ]
        }
        self.config["pages"].append(new_page)
        self.current_page = len(self.config["pages"]) - 1
        self.refresh_preview()

    def add_dashboard_page(self):
        """Show a menu to select which dashboard type to add"""
        existing = {p.get("dashboard_type") for p in self.config["pages"] if p.get("type") == "dashboard"}
        available = {k: v for k, v in DASHBOARD_TYPES.items() if k not in existing}

        if not available:
            self.show_status("All dashboard types already added!", is_error=True)
            return

        menu = tk.Menu(self.root, tearoff=0)
        for dtype, info in available.items():
            menu.add_command(label=info["name"],
                           command=lambda dt=dtype, inf=info: self._do_add_dashboard(dt, inf))
        try:
            menu.tk_popup(self.root.winfo_pointerx(), self.root.winfo_pointery())
        finally:
            menu.grab_release()

    def _do_add_dashboard(self, dashboard_type, info):
        new_page = {
            "name": info["name"],
            "type": "dashboard",
            "dashboard_type": dashboard_type,
            "refresh_interval": info["refresh_interval"],
        }
        self.config["pages"].append(new_page)
        self.current_page = len(self.config["pages"]) - 1
        self.refresh_preview()
        self.show_status(f"{info['name']} dashboard added!")

    def delete_page(self):
        if len(self.config["pages"]) <= 1:
            self.show_status("Cannot delete last page!", is_error=True)
            return

        page = self.config["pages"][self.current_page]
        # Ensure at least one button page remains
        if page.get("type", "button") == "button":
            button_pages = [p for p in self.config["pages"] if p.get("type", "button") == "button"]
            if len(button_pages) <= 1:
                self.show_status("Cannot delete last button page!", is_error=True)
                return

        del self.config["pages"][self.current_page]
        if self.current_page >= len(self.config["pages"]):
            self.current_page = len(self.config["pages"]) - 1
        self.refresh_preview()
        self.show_status("Page deleted!")

    def update_bg_color_btn(self):
        color = self.config.get("background_color", [25, 25, 35])
        hex_color = "#{:02x}{:02x}{:02x}".format(*color)
        self.bg_color_btn.configure(bg=hex_color)

    def pick_bg_color(self):
        color = colorchooser.askcolor(title="Background Color")[0]
        if color:
            self.config["background_color"] = [int(c) for c in color]
            self.update_bg_color_btn()
            self.refresh_preview()

    def generate_pi_script(self):
        """Generate the Pi script with dashboard + button pages from config"""
        config = self.config
        button_pages = self.get_button_pages()
        dashboard_pages = self.get_dashboard_pages()

        pages_code = json.dumps(button_pages, indent=4)
        pages_code = pages_code.replace("null", "None").replace("true", "True").replace("false", "False")

        # Build ordered page list: each entry is ("dashboard_type", index) or ("button", index)
        page_order = []
        dash_idx = 0
        btn_idx = 0
        for p in config["pages"]:
            if p.get("type") == "dashboard":
                page_order.append(("dashboard", p.get("dashboard_type", "system_monitor"), dash_idx))
                dash_idx += 1
            else:
                page_order.append(("button", None, btn_idx))
                btn_idx += 1

        # Build the DASHBOARD_TYPES list for the generated script
        dashboard_types_list = [p.get("dashboard_type") for p in dashboard_pages]
        num_dashboard = len(dashboard_pages)

        bg_color = config.get("background_color", [25, 25, 35])
        windows_ip = self.ip_entry.get()

        # Determine which dashboard render functions to include
        has_system = "system_monitor" in dashboard_types_list
        has_windows = "windows_pc" in dashboard_types_list
        has_pihole = "pihole" in dashboard_types_list
        has_docker = "docker" in dashboard_types_list

        script = f'''#!/usr/bin/env python3
"""
Unified StreamDeck - Cyberpunk Dashboards + Button Pages
Auto-generated by StreamDeck Editor v3
"""
import os, mmap, time, requests, threading, select, subprocess, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from evdev import InputDevice, ecodes

# ============== CONFIG ==============
WINDOWS_PC_IP = "{windows_ip}"
WINDOWS_PORT = 5555
FB_DEV = "/dev/fb1"
TOUCH_DEV = "/dev/input/event0"
WIDTH, HEIGHT = 480, 320
ICONS_DIR = "{PI_ICONS_DIR}"

CAL_X_MIN, CAL_X_MAX = 600, 3550
CAL_Y_MIN, CAL_Y_MAX = 750, 3300
INVERT_Y = True

PIHOLE_PASSWORD = "3235"
PIHOLE_URL = "http://localhost"

# Colors - Cyberpunk theme
BG_COLOR = (8, 8, 18)
CARD_BG = (15, 15, 25)
CARD_BORDER = (45, 48, 65)
TEXT_PRIMARY = (255, 255, 255)
TEXT_SECONDARY = (140, 145, 165)
TEXT_MUTED = (90, 95, 110)
CYBER_ORANGE = (255, 160, 0)
CYBER_GOLD = (255, 200, 50)
CYBER_BRIGHT = (255, 230, 120)
CYBER_DIM = (180, 130, 40)
CYBER_CYAN = (0, 220, 255)
CYBER_GREEN = (0, 255, 120)
CYBER_RED = (255, 80, 80)
CYBER_PURPLE = (200, 100, 255)

# Page layout - ordered list of page types
DASHBOARD_TYPES = {dashboard_types_list}
NUM_DASHBOARD_PAGES = {num_dashboard}

BUTTON_PAGES = {pages_code}

TOTAL_PAGES = NUM_DASHBOARD_PAGES + len(BUTTON_PAGES)

# Layout
COLS, ROWS = 3, 2
MARGIN = 10
NAV_HEIGHT = 38
NAV_Y = HEIGHT - NAV_HEIGHT
BTN_W = (WIDTH - (COLS + 1) * MARGIN) // COLS
BTN_H = (HEIGHT - NAV_HEIGHT - (ROWS + 1) * MARGIN) // ROWS
LEFT_NAV = (0, NAV_Y, 75, HEIGHT)
RIGHT_NAV = (WIDTH - 75, NAV_Y, WIDTH, HEIGHT)

# Framebuffer
fb = os.open(FB_DEV, os.O_RDWR)
fb_mmap = mmap.mmap(fb, WIDTH * HEIGHT * 2)

current_page = 0
gif_frame_indices = {{}}
gif_cache = {{}}
pihole_sid = None
pihole_sid_time = 0

# ============== FONTS ==============
print("Loading fonts...")
try:
    font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
    font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
    font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
    font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
    font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
    font_tiny = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
    font_btn = font_medium
    font_nav = font_large
except:
    font_title = font_big = font_large = font_medium = font_small = font_tiny = font_btn = font_nav = ImageFont.load_default()

# ============== HELPER FUNCTIONS ==============
def write_to_fb(img):
    arr = np.array(img, dtype=np.uint16)
    rgb565 = ((arr[:,:,0] >> 3) << 11) | ((arr[:,:,1] >> 2) << 5) | (arr[:,:,2] >> 3)
    fb_mmap.seek(0)
    fb_mmap.write(rgb565.astype(np.uint16).tobytes())

def draw_nav_bar(draw, page_num):
    draw.rectangle([0, NAV_Y, WIDTH, HEIGHT], fill=(10, 10, 18))
    draw.line([0, NAV_Y, WIDTH, NAV_Y], fill=CYBER_ORANGE, width=2)
    if page_num > 0:
        draw.rectangle([LEFT_NAV[0]+2, NAV_Y+4, LEFT_NAV[2]-2, HEIGHT-4], outline=CYBER_ORANGE, width=2)
        draw.text((30, NAV_Y + 8), "<", fill=CYBER_BRIGHT, font=font_medium)
    else:
        draw.rectangle([LEFT_NAV[0]+2, NAV_Y+4, LEFT_NAV[2]-2, HEIGHT-4], outline=(80, 60, 20), width=1)
        draw.text((30, NAV_Y + 8), "<", fill=(80, 60, 20), font=font_medium)
    if page_num < TOTAL_PAGES - 1:
        draw.rectangle([RIGHT_NAV[0]+2, NAV_Y+4, RIGHT_NAV[2]-2, HEIGHT-4], outline=CYBER_ORANGE, width=2)
        draw.text((WIDTH - 45, NAV_Y + 8), ">", fill=CYBER_BRIGHT, font=font_medium)
    else:
        draw.rectangle([RIGHT_NAV[0]+2, NAV_Y+4, RIGHT_NAV[2]-2, HEIGHT-4], outline=(80, 60, 20), width=1)
        draw.text((WIDTH - 45, NAV_Y + 8), ">", fill=(80, 60, 20), font=font_medium)
    center_x = WIDTH // 2
    dot_spacing = 18
    total_dots_width = (TOTAL_PAGES - 1) * dot_spacing
    btn_w = total_dots_width + 40
    draw.rectangle([center_x - btn_w//2, NAV_Y+4, center_x + btn_w//2, HEIGHT-4], outline=CYBER_ORANGE, width=2)
    dots_start_x = center_x - total_dots_width // 2
    dot_y = NAV_Y + (HEIGHT - NAV_Y) // 2
    for i in range(TOTAL_PAGES):
        dot_x = dots_start_x + i * dot_spacing
        if i == page_num:
            draw.ellipse([dot_x - 5, dot_y - 5, dot_x + 5, dot_y + 5], fill=CYBER_ORANGE)
        else:
            draw.ellipse([dot_x - 3, dot_y - 3, dot_x + 3, dot_y + 3], fill=(200, 200, 200))

def draw_cyber_box(draw, x, y, w, h, color=CYBER_ORANGE):
    glow = (color[0]//4, color[1]//4, color[2]//4)
    draw.rectangle([x-1, y-1, x+w+1, y+h+1], outline=glow, width=1)
    draw.rectangle([x, y, x+w, y+h], outline=color, width=3)
    corner_len = 15
    draw.line([x, y+corner_len, x, y], fill=color, width=3)
    draw.line([x, y, x+corner_len, y], fill=color, width=3)
    draw.line([x+corner_len, y, x+corner_len, y+8], fill=color, width=2)
    draw.ellipse([x+corner_len-2, y+8, x+corner_len+2, y+12], fill=color)
    draw.line([x+w-corner_len, y, x+w, y], fill=color, width=3)
    draw.line([x+w, y, x+w, y+corner_len], fill=color, width=3)
    draw.line([x+w-corner_len, y, x+w-corner_len, y+8], fill=color, width=2)
    draw.ellipse([x+w-corner_len-2, y+8, x+w-corner_len+2, y+12], fill=color)
    draw.line([x, y+h-corner_len, x, y+h], fill=color, width=3)
    draw.line([x, y+h, x+corner_len, y+h], fill=color, width=3)
    draw.line([x+corner_len, y+h, x+corner_len, y+h-8], fill=color, width=2)
    draw.ellipse([x+corner_len-2, y+h-12, x+corner_len+2, y+h-8], fill=color)
    draw.line([x+w-corner_len, y+h, x+w, y+h], fill=color, width=3)
    draw.line([x+w, y+h-corner_len, x+w, y+h], fill=color, width=3)
    draw.line([x+w-corner_len, y+h, x+w-corner_len, y+h-8], fill=color, width=2)
    draw.ellipse([x+w-corner_len-2, y+h-12, x+w-corner_len+2, y+h-8], fill=color)

def get_gradient_color(percent):
    if percent < 30:
        return (0, 255, 100)
    elif percent < 50:
        t = (percent - 30) / 20
        return (int(255 * t), 255, int(100 * (1 - t)))
    elif percent < 70:
        t = (percent - 50) / 20
        return (255, int(255 - 55 * t), 0)
    elif percent < 85:
        t = (percent - 70) / 15
        return (255, int(200 - 150 * t), 0)
    else:
        return (255, 50, 30)

def draw_segmented_bar(draw, x, y, w, h, percent, color=None, segments=10):
    gap = 3
    segment_w = (w - (segments - 1) * gap) // segments
    filled = int(segments * percent / 100)
    for i in range(segments):
        sx = x + i * (segment_w + gap)
        if i < filled:
            seg_percent = (i + 1) * 100 / segments
            seg_color = get_gradient_color(seg_percent)
            draw.rectangle([sx, y, sx + segment_w, y + h], fill=seg_color)
            highlight = (min(seg_color[0]+40, 255), min(seg_color[1]+40, 255), min(seg_color[2]+40, 255))
            draw.line([sx+1, y+1, sx + segment_w-1, y+1], fill=highlight, width=1)
        else:
            draw.rectangle([sx, y, sx + segment_w, y + h], fill=(20, 20, 30), outline=(50, 50, 60))

def draw_progress_bar(draw, x, y, w, h, percent, color, bg_color=(40, 42, 55)):
    draw.rounded_rectangle([x, y, x + w, y + h], radius=3, fill=bg_color)
    fill_w = int((w - 2) * min(percent, 100) / 100)
    if fill_w > 0:
        draw.rounded_rectangle([x + 1, y + 1, x + 1 + fill_w, y + h - 1], radius=2, fill=color)

# ============== PI SYSTEM FUNCTIONS ==============
def get_cpu_usage():
    try:
        with open('/proc/stat', 'r') as f:
            line = f.readline()
        parts = line.split()
        idle = int(parts[4])
        total = sum(int(p) for p in parts[1:])
        if not hasattr(get_cpu_usage, 'last'):
            get_cpu_usage.last = (idle, total)
            return 0
        last_idle, last_total = get_cpu_usage.last
        get_cpu_usage.last = (idle, total)
        idle_delta = idle - last_idle
        total_delta = total - last_total
        return int(100 * (1 - idle_delta / total_delta)) if total_delta else 0
    except:
        return 0

def get_memory_usage():
    try:
        with open('/proc/meminfo', 'r') as f:
            lines = f.readlines()
        mem = {{}}
        for line in lines[:5]:
            parts = line.split()
            mem[parts[0].rstrip(':')] = int(parts[1])
        total = mem.get('MemTotal', 1)
        available = mem.get('MemAvailable', 0)
        used = total - available
        percent = int(100 * used / total)
        return percent, used // 1024, total // 1024
    except:
        return 0, 0, 0

def get_cpu_temp():
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            return int(f.read().strip()) / 1000
    except:
        return 0

def get_uptime():
    try:
        with open('/proc/uptime', 'r') as f:
            seconds = float(f.read().split()[0])
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        mins = int((seconds % 3600) // 60)
        if days > 0:
            return f"{{days}}d {{hours}}h"
        elif hours > 0:
            return f"{{hours}}h {{mins}}m"
        else:
            return f"{{mins}}m"
    except:
        return "?"

def get_ip_address():
    try:
        result = subprocess.run(['hostname', '-I'], capture_output=True, text=True, timeout=2)
        ips = result.stdout.strip().split()
        return ips[0] if ips else "No IP"
    except:
        return "?"

def get_disk_usage():
    try:
        st = os.statvfs('/')
        total = st.f_blocks * st.f_frsize
        free = st.f_bavail * st.f_frsize
        used = total - free
        percent = int(100 * used / total)
        return percent, used // (1024**3), total // (1024**3)
    except:
        return 0, 0, 0
'''

        # Conditionally include dashboard render functions
        if has_system:
            script += '''
# ============== DASHBOARD: PI SYSTEM ==============
def render_system_monitor_dashboard(page_num):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)
    cpu = get_cpu_usage()
    mem_pct, mem_used, mem_total = get_memory_usage()
    temp = get_cpu_temp()
    uptime = get_uptime()
    ip = get_ip_address()
    disk_pct, disk_used, disk_total = get_disk_usage()
    available_h = NAV_Y - 10
    box_w = (WIDTH - 30) // 2
    box_h = available_h - 10
    gap = 10
    start_x, start_y = 5, 5
    bx, by = start_x, start_y
    draw_cyber_box(draw, bx, by, box_w, box_h, CYBER_ORANGE)
    draw.text((bx + 10, by + 8), "RASPBERRY PI", fill=CYBER_BRIGHT, font=font_medium)
    row_y = by + 35
    draw_segmented_bar(draw, bx + 10, row_y, 95, 16, cpu, CYBER_ORANGE, 8)
    draw.text((bx + 115, row_y), f"CPU: {cpu}%", fill=CYBER_GOLD, font=font_small)
    row_y += 28
    draw_segmented_bar(draw, bx + 10, row_y, 95, 16, temp, CYBER_ORANGE, 8)
    draw.text((bx + 115, row_y), f"TEMP: {temp:.0f}C", fill=CYBER_GOLD, font=font_small)
    row_y += 28
    draw_segmented_bar(draw, bx + 10, row_y, 95, 16, mem_pct, CYBER_ORANGE, 8)
    draw.text((bx + 115, row_y), f"MEM: {mem_pct}%", fill=CYBER_GOLD, font=font_small)
    row_y += 28
    draw_segmented_bar(draw, bx + 10, row_y, 95, 16, disk_pct, CYBER_ORANGE, 8)
    draw.text((bx + 115, row_y), f"DISK: {disk_pct}%", fill=CYBER_GOLD, font=font_small)
    bx = start_x + box_w + gap
    draw_cyber_box(draw, bx, by, box_w, box_h, CYBER_ORANGE)
    draw.text((bx + 10, by + 8), "SYSTEM", fill=CYBER_BRIGHT, font=font_medium)
    row_y = by + 38
    draw.text((bx + 10, row_y), "IP:", fill=CYBER_DIM, font=font_small)
    draw.text((bx + 35, row_y), ip, fill=CYBER_CYAN, font=font_small)
    row_y += 28
    draw.text((bx + 10, row_y), "UP:", fill=CYBER_DIM, font=font_small)
    draw.text((bx + 35, row_y), uptime, fill=CYBER_BRIGHT, font=font_medium)
    row_y += 32
    draw.text((bx + 10, row_y), f"RAM: {mem_used}/{mem_total}MB", fill=CYBER_GOLD, font=font_small)
    row_y += 26
    draw.text((bx + 10, row_y), f"DISK: {disk_used}/{disk_total}GB", fill=CYBER_GOLD, font=font_small)
    draw_nav_bar(draw, page_num)
    write_to_fb(img)
'''

        if has_windows:
            script += '''
# ============== DASHBOARD: WINDOWS PC ==============
def get_windows_stats():
    try:
        resp = requests.get(f"http://{WINDOWS_PC_IP}:{WINDOWS_PORT}/system/stats", timeout=3)
        return resp.json()
    except:
        return None

def render_windows_pc_dashboard(page_num):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)
    stats = get_windows_stats()
    if not stats or 'error' in stats:
        draw_cyber_box(draw, 100, 80, 280, 120, CYBER_ORANGE)
        draw.text((180, 110), "WINDOWS", fill=CYBER_BRIGHT, font=font_big)
        draw.text((175, 145), "OFFLINE", fill=CYBER_RED, font=font_medium)
        draw_nav_bar(draw, page_num)
        write_to_fb(img)
        return
    available_h = NAV_Y - 10
    box_w = (WIDTH - 30) // 2
    box_h = (available_h - 15) // 2
    gap = 10
    start_x, start_y = 5, 5
    bx, by = start_x, start_y
    draw_cyber_box(draw, bx, by, box_w, box_h, CYBER_ORANGE)
    cpu = stats.get('cpu_percent', 0)
    cpu_temp = stats.get('cpu_temp', 0)
    cpu_count = stats.get('cpu_count', 0)
    cpu_freq = stats.get('cpu_freq_current', stats.get('cpu_freq', 0))
    draw.text((bx + 10, by + 8), f"CPU ({cpu_count}c)", fill=CYBER_BRIGHT, font=font_medium)
    row_y = by + 32
    draw_segmented_bar(draw, bx + 10, row_y, 95, 16, cpu_temp, CYBER_ORANGE, 8)
    draw.text((bx + 115, row_y), f"TEMP: {cpu_temp:.0f}C", fill=CYBER_GOLD, font=font_small)
    row_y += 26
    draw_segmented_bar(draw, bx + 10, row_y, 95, 16, cpu, CYBER_ORANGE, 8)
    draw.text((bx + 115, row_y), f"LOAD: {cpu:.0f}%", fill=CYBER_GOLD, font=font_small)
    row_y += 26
    freq_pct = min(cpu_freq / 5000 * 100, 100)
    draw_segmented_bar(draw, bx + 10, row_y, 95, 16, freq_pct, CYBER_ORANGE, 8)
    draw.text((bx + 115, row_y), f"FREQ: {int(cpu_freq)}", fill=CYBER_GOLD, font=font_small)
    bx = start_x + box_w + gap
    draw_cyber_box(draw, bx, by, box_w, box_h, CYBER_ORANGE)
    gpu = stats.get('gpu_percent', 0)
    gpu_temp = stats.get('gpu_temp', 0)
    gpu_power = stats.get('gpu_power_w', 0)
    gpu_name = stats.get('gpu_name', 'GPU').replace('NVIDIA ', '').replace('GeForce ', '')
    draw.text((bx + 10, by + 8), f"GPU: {gpu_name[:10]}", fill=CYBER_BRIGHT, font=font_medium)
    row_y = by + 32
    draw_segmented_bar(draw, bx + 10, row_y, 95, 16, gpu_temp, CYBER_ORANGE, 8)
    draw.text((bx + 115, row_y), f"TEMP: {gpu_temp}C", fill=CYBER_GOLD, font=font_small)
    row_y += 26
    draw_segmented_bar(draw, bx + 10, row_y, 95, 16, gpu, CYBER_ORANGE, 8)
    draw.text((bx + 115, row_y), f"LOAD: {gpu}%", fill=CYBER_GOLD, font=font_small)
    row_y += 26
    pwr_pct = min(gpu_power / 320 * 100, 100)
    draw_segmented_bar(draw, bx + 10, row_y, 95, 16, pwr_pct, CYBER_ORANGE, 8)
    draw.text((bx + 115, row_y), f"PWR: {gpu_power:.0f}W", fill=CYBER_GOLD, font=font_small)
    bx, by = start_x, start_y + box_h + gap
    draw_cyber_box(draw, bx, by, box_w, box_h, CYBER_ORANGE)
    ram = stats.get('ram_percent', 0)
    ram_used = stats.get('ram_used_gb', 0)
    ram_total = stats.get('ram_total_gb', 0)
    disk = stats.get('disk_percent', 0)
    disk_free = stats.get('disk_free_gb', 0)
    draw.text((bx + 10, by + 8), f"RAM: {ram_used:.0f}/{ram_total:.0f}GB", fill=CYBER_BRIGHT, font=font_medium)
    draw.text((bx + 10, by + 30), f"USED: {ram:.0f}%", fill=CYBER_GOLD, font=font_small)
    draw_segmented_bar(draw, bx + 10, by + 52, box_w - 25, 18, ram, CYBER_ORANGE, 12)
    draw.text((bx + 10, by + 80), f"DISK: {disk:.0f}%  |  {disk_free:.0f}GB FREE", fill=CYBER_GOLD, font=font_small)
    bx = start_x + box_w + gap
    draw_cyber_box(draw, bx, by, box_w, box_h, CYBER_ORANGE)
    gpu_fan = stats.get('gpu_fan_percent', 0)
    uptime_h = stats.get('uptime_hours', 0)
    net_recv = stats.get('net_recv_gb', 0)
    if uptime_h >= 24:
        uptime_str = f"{int(uptime_h // 24)}D {int(uptime_h % 24):02d}H"
    else:
        uptime_str = f"{uptime_h:.1f}H"
    draw.text((bx + 10, by + 8), "SYS", fill=CYBER_BRIGHT, font=font_medium)
    draw.text((bx + 10, by + 32), "FAN:", fill=CYBER_DIM, font=font_small)
    draw.text((bx + 55, by + 32), f"{gpu_fan}%", fill=CYBER_GOLD, font=font_small)
    draw.text((bx + 10, by + 56), "NET:", fill=CYBER_DIM, font=font_small)
    draw.text((bx + 55, by + 56), f"{net_recv:.1f}GB", fill=CYBER_GOLD, font=font_small)
    draw.text((bx + 10, by + 80), "UP:", fill=CYBER_DIM, font=font_small)
    draw.text((bx + 55, by + 80), uptime_str, fill=CYBER_BRIGHT, font=font_medium)
    draw_nav_bar(draw, page_num)
    write_to_fb(img)
'''

        if has_pihole:
            script += '''
# ============== DASHBOARD: PI-HOLE ==============
def pihole_auth():
    global pihole_sid, pihole_sid_time
    if pihole_sid and time.time() - pihole_sid_time < 1500:
        return pihole_sid
    try:
        resp = requests.post(f"{PIHOLE_URL}/api/auth", json={"password": PIHOLE_PASSWORD}, timeout=3)
        data = resp.json()
        if data.get("session", {}).get("valid"):
            pihole_sid = data["session"]["sid"]
            pihole_sid_time = time.time()
            return pihole_sid
    except:
        pass
    return None

def get_pihole_stats():
    sid = pihole_auth()
    if not sid:
        return None
    try:
        resp = requests.get(f"{PIHOLE_URL}/api/stats/summary", headers={"sid": sid}, timeout=3)
        data = resp.json()
        return data if "queries" in data else None
    except:
        return None

def render_pihole_dashboard(page_num):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)
    stats = get_pihole_stats()
    if not stats:
        draw_cyber_box(draw, 100, 80, 280, 120, CYBER_ORANGE)
        draw.text((170, 110), "PI-HOLE", fill=CYBER_BRIGHT, font=font_big)
        draw.text((160, 145), "CONNECTING...", fill=CYBER_GOLD, font=font_small)
        draw_nav_bar(draw, page_num)
        write_to_fb(img)
        return
    queries = stats.get("queries", {})
    total = queries.get("total", 0)
    blocked = queries.get("blocked", 0)
    pct = queries.get("percent_blocked", 0)
    cached = queries.get("cached", 0)
    forwarded = queries.get("forwarded", 0)
    clients = stats.get("clients", {}).get("active", 0)
    domains = stats.get("gravity", {}).get("domains_being_blocked", 0)
    available_h = NAV_Y - 10
    box_w = (WIDTH - 30) // 2
    box_h = (available_h - 15) // 2
    gap = 10
    start_x, start_y = 5, 5
    bx, by = start_x, start_y
    draw_cyber_box(draw, bx, by, box_w, box_h, CYBER_ORANGE)
    draw.text((bx + 10, by + 8), "QUERIES", fill=CYBER_BRIGHT, font=font_medium)
    draw.text((bx + 10, by + 32), f"{total:,}", fill=CYBER_CYAN, font=font_big)
    draw.text((bx + 10, by + 65), f"{clients} CLIENTS", fill=CYBER_GOLD, font=font_small)
    bx = start_x + box_w + gap
    draw_cyber_box(draw, bx, by, box_w, box_h, CYBER_ORANGE)
    draw.text((bx + 10, by + 8), "BLOCKED", fill=CYBER_BRIGHT, font=font_medium)
    draw.text((bx + 10, by + 32), f"{blocked:,}", fill=CYBER_RED, font=font_big)
    draw_segmented_bar(draw, bx + 10, by + 65, 120, 14, pct, CYBER_ORANGE, 10)
    draw.text((bx + 140, by + 65), f"{pct:.1f}%", fill=CYBER_GOLD, font=font_small)
    bx, by = start_x, start_y + box_h + gap
    draw_cyber_box(draw, bx, by, box_w, box_h, CYBER_ORANGE)
    draw.text((bx + 10, by + 8), "TRAFFIC", fill=CYBER_BRIGHT, font=font_medium)
    draw.text((bx + 10, by + 35), "CACHED:", fill=CYBER_GOLD, font=font_small)
    draw.text((bx + 80, by + 35), f"{cached:,}", fill=CYBER_PURPLE, font=font_small)
    draw.text((bx + 10, by + 59), "FWD:", fill=CYBER_GOLD, font=font_small)
    draw.text((bx + 80, by + 59), f"{forwarded:,}", fill=CYBER_CYAN, font=font_small)
    bx = start_x + box_w + gap
    draw_cyber_box(draw, bx, by, box_w, box_h, CYBER_ORANGE)
    draw.text((bx + 10, by + 8), "BLOCKLIST", fill=CYBER_BRIGHT, font=font_medium)
    draw.text((bx + 10, by + 35), f"{domains:,}", fill=CYBER_GREEN, font=font_medium)
    draw.text((bx + 10, by + 58), "DOMAINS", fill=CYBER_GOLD, font=font_small)
    draw_nav_bar(draw, page_num)
    write_to_fb(img)
'''

        if has_docker:
            script += '''
# ============== DASHBOARD: DOCKER ==============
def get_docker_data():
    try:
        resp = requests.get(f"http://{WINDOWS_PC_IP}:{WINDOWS_PORT}/docker/containers", timeout=5)
        data = resp.json()
        return data.get('containers', []), data.get('count', 0)
    except:
        return [], 0

def render_docker_dashboard(page_num):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)
    containers, count = get_docker_data()
    if not containers:
        draw_cyber_box(draw, 100, 80, 280, 120, CYBER_ORANGE)
        draw.text((180, 110), "DOCKER", fill=CYBER_BRIGHT, font=font_big)
        draw.text((155, 145), "NO CONTAINERS", fill=CYBER_GOLD, font=font_medium)
        draw_nav_bar(draw, page_num)
        write_to_fb(img)
        return
    cols, rows = 3, 4
    margin = 5
    start_y = 5
    card_w = (WIDTH - margin * (cols + 1)) // cols
    card_h = (NAV_Y - start_y - margin * (rows + 1)) // rows
    for i, c in enumerate(containers[:12]):
        row, col = i // cols, i % cols
        x = margin + col * (card_w + margin)
        y = start_y + row * (card_h + margin)
        status = c.get('status', '')
        is_healthy = 'healthy' in status.lower()
        is_up = 'up' in status.lower()
        if is_healthy:
            status_color = CYBER_GREEN
        elif is_up:
            status_color = CYBER_CYAN
        else:
            status_color = CYBER_RED
        draw.rectangle([x, y, x+card_w, y+card_h], fill=(15, 15, 25), outline=CYBER_ORANGE, width=2)
        draw.rectangle([x+2, y+2, x+5, y+card_h-2], fill=status_color)
        name = c.get('name', '?')
        for p in ['compassionate_', 'nervous_', 'elated_', 'determined_', 'naughty_', 'flamboyant_', 'upbeat_', 'suspicious_']:
            if name.startswith(p):
                name = name[len(p):]
                break
        name = name[:11] + '..' if len(name) > 13 else name
        draw.text((x+10, y+4), name, fill=CYBER_BRIGHT, font=font_small)
        image = c.get('image', '').split('/')[-1].split(':')[0]
        image = image[:13] + '..' if len(image) > 15 else image
        draw.text((x+10, y+20), image, fill=(100, 80, 30), font=font_tiny)
        if 'Up' in status:
            parts = status.replace('(healthy)', '').strip().split()
            up = f"{parts[1]}{parts[2][0]}" if len(parts) >= 3 else "Up"
            draw.text((x+card_w-32, y+card_h-14), up, fill=status_color, font=font_tiny)
    draw_nav_bar(draw, page_num)
    write_to_fb(img)
'''

        # Build the dispatch map and page selector
        # Build render_current_page dispatch
        dispatch_lines = []
        for i, dtype in enumerate(dashboard_types_list):
            func_name = f"render_{dtype}_dashboard"
            dispatch_lines.append(f"    {'if' if i == 0 else 'elif'} current_page == {i}:")
            dispatch_lines.append(f"        {func_name}({i})")

        if dashboard_types_list:
            dispatch_lines.append(f"    else:")
            dispatch_lines.append(f"        show_button_page(current_page - NUM_DASHBOARD_PAGES)")
        else:
            dispatch_lines.append(f"    show_button_page(current_page)")

        dispatch_code = "\n".join(dispatch_lines)

        script += f'''
# ============== PAGE SELECTOR GRID ==============
page_selector_active = False

def render_page_selector():
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)
    draw.text((WIDTH//2 - 60, 8), "SELECT PAGE", fill=CYBER_BRIGHT, font=font_medium)
    cols, rows = 3, 2
    margin = 15
    start_y = 40
    card_w = (WIDTH - margin * (cols + 1)) // cols
    card_h = (NAV_Y - start_y - margin * (rows + 1)) // rows
    for i in range(min(TOTAL_PAGES, 6)):
        row, col = i // cols, i % cols
        x = margin + col * (card_w + margin)
        y = start_y + row * (card_h + margin)
        if i == current_page:
            draw_cyber_box(draw, x, y, card_w, card_h, CYBER_CYAN)
            text_color = CYBER_CYAN
        else:
            draw_cyber_box(draw, x, y, card_w, card_h, CYBER_ORANGE)
            text_color = CYBER_BRIGHT
        if i < NUM_DASHBOARD_PAGES:
            name = DASHBOARD_TYPES[i].upper().replace("_", " ")[:8]
        else:
            bp = BUTTON_PAGES[i - NUM_DASHBOARD_PAGES]
            name = bp.get("name", f"PAGE {{i+1}}")[:8].upper()
        bbox = draw.textbbox((0, 0), name, font=font_medium)
        tw = bbox[2] - bbox[0]
        draw.text((x + (card_w - tw) // 2, y + card_h // 2 - 10), name, fill=text_color, font=font_medium)
        draw.text((x + 10, y + 8), f"{{i+1}}", fill=CYBER_ORANGE, font=font_small)
    draw.text((WIDTH//2 - 70, NAV_Y + 8), "TAP OUTSIDE TO CANCEL", fill=(100, 80, 40), font=font_tiny)
    write_to_fb(img)

def get_page_from_grid(sx, sy):
    cols, rows = 3, 2
    margin = 15
    start_y = 40
    card_w = (WIDTH - margin * (cols + 1)) // cols
    card_h = (NAV_Y - start_y - margin * (rows + 1)) // rows
    for i in range(min(TOTAL_PAGES, 6)):
        row, col = i // cols, i % cols
        x = margin + col * (card_w + margin)
        y = start_y + row * (card_h + margin)
        if x <= sx <= x + card_w and y <= sy <= y + card_h:
            return i
    return -1

# ============== BUTTON PAGE FUNCTIONS ==============
def get_btn_rect(idx):
    row, col = idx // COLS, idx % COLS
    x = MARGIN + col * (BTN_W + MARGIN)
    y = MARGIN + row * (BTN_H + MARGIN)
    return (x, y, x + BTN_W, y + BTN_H)

def is_animated_ext(path):
    if not path:
        return False
    lower = path.lower()
    return lower.endswith('.gif') or lower.endswith('.webp')

def load_gif_frames(path, size, use_cover=False):
    if not path or not is_animated_ext(path):
        return None
    pi_path = os.path.join(ICONS_DIR, os.path.basename(path.replace('\\\\', '/')))
    try:
        img = Image.open(pi_path)
        frames = []
        for frame_num in range(getattr(img, 'n_frames', 1)):
            img.seek(frame_num)
            frame = img.convert("RGBA")
            if use_cover:
                frame = cover_resize(frame, size[0], size[1])
            else:
                frame = frame.resize(size, Image.LANCZOS)
            frames.append(frame)
        return frames if frames else None
    except:
        return None

def cover_resize(img, target_w, target_h):
    img_w, img_h = img.size
    img_ratio = img_w / img_h
    target_ratio = target_w / target_h
    if img_ratio > target_ratio:
        new_h = target_h
        new_w = int(new_h * img_ratio)
    else:
        new_w = target_w
        new_h = int(new_w / img_ratio)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return img.crop((left, top, left + target_w, top + target_h))

def load_image(path, size, frame_idx=0, use_cover=False):
    if not path:
        return None
    pi_path = os.path.join(ICONS_DIR, os.path.basename(path.replace('\\\\', '/')))
    if is_animated_ext(path):
        cache_key = (pi_path, size, use_cover)
        if cache_key not in gif_cache:
            frames = load_gif_frames(path, size, use_cover)
            if frames:
                gif_cache[cache_key] = frames
        if cache_key in gif_cache:
            frames = gif_cache[cache_key]
            return frames[frame_idx % len(frames)]
    try:
        img = Image.open(pi_path).convert("RGBA")
        return cover_resize(img, size[0], size[1]) if use_cover else img.resize(size, Image.LANCZOS)
    except:
        return None

def make_button_frame_bytes(page_idx, highlight=-1):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)
    buttons = BUTTON_PAGES[page_idx]["buttons"]
    for i, btn in enumerate(buttons):
        x1, y1, x2, y2 = get_btn_rect(i)
        color = tuple(btn.get("color", [60, 60, 80]))
        if i == highlight:
            color = (255, 255, 255)
        draw.rounded_rectangle([x1, y1, x2, y2], radius=12, fill=color, outline=CYBER_ORANGE, width=2)
        if i != highlight:
            bg_frame = gif_frame_indices.get(f"bg_{{page_idx}}_{{i}}", 0)
            bg_img = load_image(btn.get("background"), (BTN_W - 4, BTN_H - 4), bg_frame, use_cover=True)
            if bg_img:
                img.paste(bg_img, (x1 + 2, y1 + 2), bg_img)
            icon_frame = gif_frame_indices.get(f"icon_{{page_idx}}_{{i}}", 0)
            icon = load_image(btn.get("icon"), (50, 50), icon_frame)
            if icon:
                img.paste(icon, (x1 + (BTN_W - 50) // 2, y1 + 10), icon)
        label = btn.get("label", "")
        if label:
            bbox = draw.textbbox((0, 0), label, font=font_btn)
            tw = bbox[2] - bbox[0]
            draw.text((x1 + (BTN_W - tw) // 2, y2 - 25), label, fill=CYBER_BRIGHT, font=font_btn)
    draw_nav_bar(draw, NUM_DASHBOARD_PAGES + page_idx)
    arr = np.array(img, dtype=np.uint16)
    rgb565 = ((arr[:,:,0] >> 3) << 11) | ((arr[:,:,1] >> 2) << 5) | (arr[:,:,2] >> 3)
    return rgb565.astype(np.uint16).tobytes()

def has_animated():
    for page in BUTTON_PAGES:
        for btn in page["buttons"]:
            if is_animated_ext(btn.get("background", "")) or is_animated_ext(btn.get("icon", "")):
                return True
    return False

HAS_GIFS = has_animated()

gif_buttons_per_page = {{}}
for p_idx, page in enumerate(BUTTON_PAGES):
    gif_buttons_per_page[p_idx] = []
    for b_idx, btn in enumerate(page["buttons"]):
        if is_animated_ext(btn.get("background", "")) or is_animated_ext(btn.get("icon", "")):
            gif_buttons_per_page[p_idx].append(b_idx)
            gif_frame_indices[f"btn_{{p_idx}}_{{b_idx}}"] = 0

print("Pre-rendering button pages...")
frame_cache = {{}}
for p in range(len(BUTTON_PAGES)):
    frame_cache[(p, -1)] = make_button_frame_bytes(p, -1)
    for i in range(len(BUTTON_PAGES[p]["buttons"])):
        frame_cache[(p, i)] = make_button_frame_bytes(p, i)
print(f"Cached {{len(frame_cache)}} button frames!")

print("Pre-rendering GIF frames...")
gif_frame_cache = {{}}
for p_idx, page in enumerate(BUTTON_PAGES):
    for b_idx in gif_buttons_per_page.get(p_idx, []):
        btn = page["buttons"][b_idx]
        bg_frames = load_gif_frames(btn.get("background"), (BTN_W - 4, BTN_H - 4), use_cover=True)
        icon_frames = load_gif_frames(btn.get("icon"), (50, 50))
        num_frames = max(len(bg_frames) if bg_frames else 1, len(icon_frames) if icon_frames else 1)
        for f_idx in range(num_frames):
            btn_img = Image.new("RGB", (BTN_W, BTN_H), tuple(btn.get("color", [60, 60, 80])))
            draw = ImageDraw.Draw(btn_img)
            draw.rounded_rectangle([0, 0, BTN_W-1, BTN_H-1], radius=12, outline=CYBER_ORANGE, width=2)
            if bg_frames:
                btn_img.paste(bg_frames[f_idx % len(bg_frames)], (2, 2), bg_frames[f_idx % len(bg_frames)])
            if icon_frames:
                btn_img.paste(icon_frames[f_idx % len(icon_frames)], ((BTN_W - 50) // 2, 10), icon_frames[f_idx % len(icon_frames)])
            label = btn.get("label", "")
            if label:
                bbox = draw.textbbox((0, 0), label, font=font_btn)
                draw.text(((BTN_W - bbox[2] + bbox[0]) // 2, BTN_H - 25), label, fill=CYBER_BRIGHT, font=font_btn)
            arr = np.array(btn_img, dtype=np.uint16)
            rgb565 = ((arr[:,:,0] >> 3) << 11) | ((arr[:,:,1] >> 2) << 5) | (arr[:,:,2] >> 3)
            gif_frame_cache[(p_idx, b_idx, f_idx)] = rgb565.astype(np.uint16).tobytes()
        gif_frame_indices[f"btn_{{p_idx}}_{{b_idx}}_max"] = num_frames

print(f"Pre-rendered {{len(gif_frame_cache)}} GIF frames!")

def show_button_page(page_idx, highlight=-1):
    fb_mmap.seek(0)
    fb_mmap.write(frame_cache[(page_idx, highlight)])

def render_button_to_fb(page_idx, btn_idx):
    x1, y1, x2, y2 = get_btn_rect(btn_idx)
    frame_idx = gif_frame_indices.get(f"btn_{{page_idx}}_{{btn_idx}}", 0)
    max_frames = gif_frame_indices.get(f"btn_{{page_idx}}_{{btn_idx}}_max", 1)
    btn_bytes = gif_frame_cache.get((page_idx, btn_idx, frame_idx % max_frames))
    if not btn_bytes:
        return
    for row in range(BTN_H):
        offset = ((y1 + row) * WIDTH + x1) * 2
        row_start = row * BTN_W * 2
        fb_mmap[offset:offset + BTN_W * 2] = btn_bytes[row_start:row_start + BTN_W * 2]

def update_gif_buttons(page_idx):
    for btn_idx in gif_buttons_per_page.get(page_idx, []):
        render_button_to_fb(page_idx, btn_idx)

def advance_gif_frames():
    for key in gif_frame_indices:
        if not key.endswith("_max"):
            gif_frame_indices[key] += 1

def send_action(action, app_path=None):
    if not action:
        return
    try:
        if action == "custom_app" and app_path:
            from urllib.parse import quote
            requests.get(f"http://{{WINDOWS_PC_IP}}:{{WINDOWS_PORT}}/launch?path={{quote(app_path, safe='')}}", timeout=0.5)
        else:
            requests.get(f"http://{{WINDOWS_PC_IP}}:{{WINDOWS_PORT}}/action/{{action}}", timeout=0.3)
    except:
        pass

# ============== MAIN LOOP ==============
def touch_to_screen(tx, ty):
    sx = int((tx - CAL_X_MIN) / (CAL_X_MAX - CAL_X_MIN) * WIDTH)
    sy = int((ty - CAL_Y_MIN) / (CAL_Y_MAX - CAL_Y_MIN) * HEIGHT)
    if INVERT_Y:
        sy = HEIGHT - sy
    return max(0, min(WIDTH-1, sx)), max(0, min(HEIGHT-1, sy))

def render_current_page():
{dispatch_code}

print("Ready!")
render_current_page()
touch = InputDevice(TOUCH_DEV)

touch_x, touch_y = 0, 0
touching = False
pending_touch = False
page_selector_active = False
last_gif_update = time.time()
last_dashboard_update = time.time()
GIF_INTERVAL = 0.06
DASHBOARD_INTERVAL = 1.0

while True:
    if current_page < NUM_DASHBOARD_PAGES:
        timeout = 0.5
    elif HAS_GIFS:
        timeout = 0.03
    else:
        timeout = None

    r, w, x = select.select([touch.fd], [], [], timeout)

    if not page_selector_active:
        if current_page < NUM_DASHBOARD_PAGES and time.time() - last_dashboard_update > DASHBOARD_INTERVAL:
            render_current_page()
            last_dashboard_update = time.time()
        if current_page >= NUM_DASHBOARD_PAGES and HAS_GIFS and time.time() - last_gif_update > GIF_INTERVAL:
            advance_gif_frames()
            update_gif_buttons(current_page - NUM_DASHBOARD_PAGES)
            last_gif_update = time.time()

    if r:
        for event in touch.read():
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

                    if page_selector_active:
                        selected = get_page_from_grid(sx, sy)
                        if selected >= 0:
                            current_page = selected
                        page_selector_active = False
                        render_current_page()
                        continue

                    if sx >= RIGHT_NAV[0] and sy >= NAV_Y:
                        if current_page < TOTAL_PAGES - 1:
                            current_page += 1
                            render_current_page()
                        continue

                    if sx <= LEFT_NAV[2] and sy >= NAV_Y:
                        if current_page > 0:
                            current_page -= 1
                            render_current_page()
                        continue

                    if LEFT_NAV[2] < sx < RIGHT_NAV[0] and sy >= NAV_Y:
                        page_selector_active = True
                        render_page_selector()
                        continue

                    if current_page >= NUM_DASHBOARD_PAGES:
                        btn_page_idx = current_page - NUM_DASHBOARD_PAGES
                        for i, btn in enumerate(BUTTON_PAGES[btn_page_idx]["buttons"]):
                            x1, y1, x2, y2 = get_btn_rect(i)
                            if x1 <= sx <= x2 and y1 <= sy <= y2:
                                show_button_page(btn_page_idx, i)
                                send_action(btn.get("action"), btn.get("app_path"))
                                time.sleep(0.05)
                                show_button_page(btn_page_idx)
                                break
'''
        return script

    def deploy_to_pi(self):
        """Upload config and restart script on Pi in one click"""
        try:
            import paramiko
        except ImportError:
            self.show_status("paramiko required! pip install paramiko", is_error=True)
            return

        try:
            self.config["windows_ip"] = self.ip_entry.get()
            self.save_config()

            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(PI_HOST, username=PI_USER, password=PI_PASS, timeout=10)

            sftp = ssh.open_sftp()

            try:
                sftp.mkdir(PI_ICONS_DIR)
            except:
                pass

            # Upload icons (recursively including subdirectories)
            if os.path.exists(LOCAL_ICONS_DIR):
                for root_dir, dirs, files in os.walk(LOCAL_ICONS_DIR):
                    rel_root = os.path.relpath(root_dir, LOCAL_ICONS_DIR)
                    if rel_root != ".":
                        remote_sub = f"{PI_ICONS_DIR}/{rel_root}".replace("\\", "/")
                        try:
                            sftp.mkdir(remote_sub)
                        except:
                            pass
                    for filename in files:
                        local_path = os.path.join(root_dir, filename)
                        if rel_root == ".":
                            remote_path = f"{PI_ICONS_DIR}/{filename}"
                        else:
                            remote_path = f"{PI_ICONS_DIR}/{rel_root}/{filename}".replace("\\", "/")
                        sftp.put(local_path, remote_path)

            # Upload script
            script = self.generate_pi_script()
            with sftp.file(PI_SCRIPT, 'w') as f:
                f.write(script)

            sftp.close()

            # Stop old script - wait for completion
            stdin, stdout, stderr = ssh.exec_command("sudo pkill -9 -f streamdeck_fast.py")
            stdout.channel.recv_exit_status()

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
