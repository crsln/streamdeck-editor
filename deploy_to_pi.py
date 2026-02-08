#!/usr/bin/env python3
"""Deploy optimized streamdeck script to Pi with Dashboard"""
import json
import os
import sys

# Constants
PI_HOST = '192.168.1.112'
PI_USER = 'cem'
PI_PASS = '3235'
PI_SCRIPT = '/home/cem/streamdeck_fast.py'
PI_ICONS_DIR = '/home/cem/streamdeck_icons'
LOCAL_ICONS_DIR = 'streamdeck_icons'
CONFIG_FILE = 'streamdeck_config_v3.json'

def generate_pi_script(config):
    pages_code = json.dumps(config['pages'], indent=4)
    pages_code = pages_code.replace('null', 'None').replace('true', 'True').replace('false', 'False')
    bg_color = config.get('background_color', [25, 25, 35])
    windows_ip = config.get('windows_ip', '192.168.1.13')

    script = f'''#!/usr/bin/env python3
import os, mmap, time, requests, threading, select, subprocess
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

# Button pages (dashboard is page 0, these start at page 1)
BUTTON_PAGES = {pages_code}

# Total pages = 1 (dashboard) + button pages
TOTAL_PAGES = 1 + len(BUTTON_PAGES)

COLS, ROWS = 3, 2
MARGIN = 10
NAV_HEIGHT = 70
BTN_W = (WIDTH - (COLS + 1) * MARGIN) // COLS
BTN_H = (HEIGHT - NAV_HEIGHT - (ROWS + 1) * MARGIN) // ROWS

fb = os.open(FB_DEV, os.O_RDWR)
fb_mmap = mmap.mmap(fb, WIDTH * HEIGHT * 2)

current_page = 0  # 0 = dashboard, 1+ = button pages
gif_frame_indices = {{}}
gif_cache = {{}}

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
    font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
    font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
    font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    font_tiny = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
except:
    font_large = font_medium = font_small = font_tiny = ImageFont.load_default()

font_btn = font_medium
font_nav = font_large

# ============== DASHBOARD FUNCTIONS ==============

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
        if total_delta == 0:
            return 0
        return int(100 * (1 - idle_delta / total_delta))
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
            temp = int(f.read().strip()) / 1000
        return temp
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
            return f"{{days}}d {{hours}}h {{mins}}m"
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

def draw_progress_bar(draw, x, y, w, h, percent, color, bg_color=(40, 40, 50)):
    """Draw a progress bar"""
    draw.rectangle([x, y, x + w, y + h], fill=bg_color, outline=(80, 80, 90))
    fill_w = int((w - 2) * percent / 100)
    if fill_w > 0:
        draw.rectangle([x + 1, y + 1, x + 1 + fill_w, y + h - 1], fill=color)

def render_dashboard():
    """Render the system dashboard"""
    img = Image.new("RGB", (WIDTH, HEIGHT), (20, 22, 30))
    draw = ImageDraw.Draw(img)

    # Title
    draw.text((WIDTH // 2 - 80, 8), "SYSTEM MONITOR", fill=(100, 200, 255), font=font_large)

    # Stats
    cpu = get_cpu_usage()
    mem_pct, mem_used, mem_total = get_memory_usage()
    temp = get_cpu_temp()
    uptime = get_uptime()
    ip = get_ip_address()
    disk_pct, disk_used, disk_total = get_disk_usage()

    y_start = 45
    row_h = 38
    bar_w = 200
    bar_h = 16

    # CPU
    y = y_start
    cpu_color = (46, 204, 113) if cpu < 50 else (241, 196, 15) if cpu < 80 else (231, 76, 60)
    draw.text((15, y), "CPU", fill=(180, 180, 200), font=font_medium)
    draw.text((380, y), f"{{cpu}}%", fill=cpu_color, font=font_medium)
    draw_progress_bar(draw, 70, y + 3, bar_w, bar_h, cpu, cpu_color)

    # Memory
    y += row_h
    mem_color = (46, 204, 113) if mem_pct < 60 else (241, 196, 15) if mem_pct < 85 else (231, 76, 60)
    draw.text((15, y), "MEM", fill=(180, 180, 200), font=font_medium)
    draw.text((350, y), f"{{mem_used}}/{{mem_total}}MB", fill=(150, 150, 170), font=font_small)
    draw_progress_bar(draw, 70, y + 3, bar_w, bar_h, mem_pct, mem_color)

    # Disk
    y += row_h
    disk_color = (46, 204, 113) if disk_pct < 70 else (241, 196, 15) if disk_pct < 90 else (231, 76, 60)
    draw.text((15, y), "DISK", fill=(180, 180, 200), font=font_medium)
    draw.text((350, y), f"{{disk_used}}/{{disk_total}}GB", fill=(150, 150, 170), font=font_small)
    draw_progress_bar(draw, 70, y + 3, bar_w, bar_h, disk_pct, disk_color)

    # Temperature
    y += row_h
    temp_color = (46, 204, 113) if temp < 50 else (241, 196, 15) if temp < 70 else (231, 76, 60)
    draw.text((15, y), "TEMP", fill=(180, 180, 200), font=font_medium)
    draw.text((150, y), f"{{temp:.1f}}C", fill=temp_color, font=font_medium)

    # Uptime
    draw.text((250, y), "UP", fill=(180, 180, 200), font=font_medium)
    draw.text((300, y), uptime, fill=(100, 180, 255), font=font_medium)

    # IP Address
    y += row_h
    draw.text((15, y), "IP", fill=(180, 180, 200), font=font_medium)
    draw.text((70, y), ip, fill=(150, 220, 150), font=font_medium)

    # Navigation bar
    draw.rectangle([0, NAV_Y, WIDTH, HEIGHT], fill=(40, 40, 55))

    # No prev on dashboard
    draw.rectangle(LEFT_NAV, fill=(50, 50, 65))
    draw.text((40, NAV_Y + 15), "<", fill=(100, 100, 120), font=font_nav)

    # Next button (to buttons page)
    draw.rectangle(RIGHT_NAV, fill=(70, 130, 180))
    draw.text((WIDTH - 80, NAV_Y + 15), ">", fill=(255, 255, 255), font=font_nav)

    # Page indicator
    page_text = f"1/{{TOTAL_PAGES}}"
    bbox = draw.textbbox((0, 0), page_text, font=font_btn)
    tw = bbox[2] - bbox[0]
    draw.text((WIDTH // 2 - tw // 2, NAV_Y + 22), page_text, fill=(200, 200, 220), font=font_btn)

    # Convert to RGB565 and write
    arr = np.array(img, dtype=np.uint16)
    rgb565 = ((arr[:,:,0] >> 3) << 11) | ((arr[:,:,1] >> 2) << 5) | (arr[:,:,2] >> 3)
    fb_mmap.seek(0)
    fb_mmap.write(rgb565.astype(np.uint16).tobytes())

# ============== BUTTON PAGE FUNCTIONS ==============

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

def is_animated_ext(path):
    if not path:
        return False
    lower = path.lower()
    return lower.endswith('.gif') or lower.endswith('.webp')

MAX_GIF_FRAMES = 30

def load_gif_frames(path, size, use_cover=False):
    if not path:
        return None
    filename = path.split("/")[-1].split(chr(92))[-1]
    pi_path = os.path.join(ICONS_DIR, filename)
    if not os.path.exists(pi_path):
        return None
    if not is_animated_ext(pi_path):
        return None
    try:
        img = Image.open(pi_path)
        frames = []
        frame_count = min(getattr(img, 'n_frames', 1), MAX_GIF_FRAMES)
        for i in range(frame_count):
            img.seek(i)
            frame = img.copy().convert("RGBA")
            if use_cover:
                frame = cover_resize(frame, size[0], size[1])
            else:
                frame = frame.resize(size)
            frames.append(frame)
        return frames if len(frames) > 1 else None
    except:
        return None

def load_image(path, size, frame_idx=0, use_cover=False):
    if not path:
        return None
    filename = path.split("/")[-1].split(chr(92))[-1]
    pi_path = os.path.join(ICONS_DIR, filename)
    if not os.path.exists(pi_path):
        return None

    cache_key = (pi_path, size, use_cover)
    if cache_key in gif_cache:
        frames = gif_cache[cache_key]
        return frames[frame_idx % len(frames)]

    if is_animated_ext(pi_path):
        frames = load_gif_frames(path, size, use_cover)
        if frames:
            gif_cache[cache_key] = frames
            return frames[frame_idx % len(frames)]

    try:
        img = Image.open(pi_path).convert("RGBA")
        if use_cover:
            img = cover_resize(img, size[0], size[1])
        else:
            img = img.resize(size)
        return img
    except:
        return None

def make_button_frame_bytes(page_idx, highlight=-1):
    """Render a button page (page_idx is 0-based index into BUTTON_PAGES)"""
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    buttons = BUTTON_PAGES[page_idx]["buttons"]

    for i, btn in enumerate(buttons):
        x1, y1, x2, y2 = get_btn_rect(i)
        color = tuple(btn.get("color", [100, 100, 100]))
        if i == highlight:
            color = (255, 255, 255)

        draw.rounded_rectangle([x1, y1, x2, y2], radius=12, fill=color, outline=(255,255,255), width=2)

        if i != highlight:
            bg_key = f"bg_{{page_idx}}_{{i}}"
            bg_frame = gif_frame_indices.get(bg_key, 0)
            bg_img = load_image(btn.get("background"), (BTN_W - 4, BTN_H - 4), bg_frame, use_cover=True)
            if bg_img:
                img.paste(bg_img, (x1 + 2, y1 + 2), bg_img)

            icon_key = f"icon_{{page_idx}}_{{i}}"
            icon_frame = gif_frame_indices.get(icon_key, 0)
            icon = load_image(btn.get("icon"), (50, 50), icon_frame)
            if icon:
                icon_x = x1 + (BTN_W - 50) // 2
                icon_y = y1 + 10
                img.paste(icon, (icon_x, icon_y), icon)

        label = btn.get("label", "")
        if label:
            bbox = draw.textbbox((0,0), label, font=font_btn)
            tw = bbox[2] - bbox[0]
            draw.text((x1 + (BTN_W - tw)//2, y2 - 25), label, fill=(255,255,255), font=font_btn)

    # Navigation
    draw.rectangle([0, NAV_Y, WIDTH, HEIGHT], fill=(40, 40, 55))

    # Actual page number for display (1 = dashboard, 2+ = button pages)
    display_page = page_idx + 2  # +1 for 0-index, +1 for dashboard

    left_color = (70, 130, 180)  # Always can go back (to dashboard or prev)
    draw.rectangle(LEFT_NAV, fill=left_color)
    draw.text((40, NAV_Y + 15), "<", fill=(255,255,255), font=font_nav)

    right_color = (70, 130, 180) if page_idx < len(BUTTON_PAGES) - 1 else (50, 50, 65)
    draw.rectangle(RIGHT_NAV, fill=right_color)
    draw.text((WIDTH - 80, NAV_Y + 15), ">", fill=(255,255,255), font=font_nav)

    page_text = f"{{display_page}}/{{TOTAL_PAGES}}"
    bbox = draw.textbbox((0,0), page_text, font=font_btn)
    tw = bbox[2] - bbox[0]
    draw.text((WIDTH//2 - tw//2, NAV_Y + 22), page_text, fill=(200,200,220), font=font_btn)

    arr = np.array(img, dtype=np.uint16)
    rgb565 = ((arr[:,:,0] >> 3) << 11) | ((arr[:,:,1] >> 2) << 5) | (arr[:,:,2] >> 3)
    return rgb565.astype(np.uint16).tobytes()

def has_animated():
    for page in BUTTON_PAGES:
        for btn in page["buttons"]:
            bg = btn.get("background", "")
            icon = btn.get("icon", "")
            if is_animated_ext(bg) or is_animated_ext(icon):
                return True
    return False

HAS_GIFS = has_animated()

# Track GIF buttons per page (page_idx is 0-based into BUTTON_PAGES)
gif_buttons_per_page = {{}}
for p_idx, page in enumerate(BUTTON_PAGES):
    gif_buttons_per_page[p_idx] = []
    for b_idx, btn in enumerate(page["buttons"]):
        bg = btn.get("background", "")
        icon = btn.get("icon", "")
        if is_animated_ext(bg) or is_animated_ext(icon):
            gif_buttons_per_page[p_idx].append(b_idx)
            gif_frame_indices[f"btn_{{p_idx}}_{{b_idx}}"] = 0

print("Pre-rendering button pages...")
frame_cache = {{}}
for p in range(len(BUTTON_PAGES)):
    frame_cache[(p, -1)] = make_button_frame_bytes(p, -1)
    for i in range(len(BUTTON_PAGES[p]["buttons"])):
        frame_cache[(p, i)] = make_button_frame_bytes(p, i)
print(f"Cached {{len(frame_cache)}} button frames!")

# Pre-render GIF frames
print("Pre-rendering GIF frames...")
gif_frame_cache = {{}}

for p_idx, page in enumerate(BUTTON_PAGES):
    for b_idx in gif_buttons_per_page.get(p_idx, []):
        btn = page["buttons"][b_idx]
        bg_path = btn.get("background")
        icon_path = btn.get("icon")

        bg_frames = load_gif_frames(bg_path, (BTN_W - 4, BTN_H - 4), use_cover=True) if bg_path else None
        icon_frames = load_gif_frames(icon_path, (50, 50)) if icon_path else None

        num_frames = max(
            len(bg_frames) if bg_frames else 1,
            len(icon_frames) if icon_frames else 1
        )

        for f_idx in range(num_frames):
            btn_img = Image.new("RGB", (BTN_W, BTN_H), tuple(btn.get("color", [100, 100, 100])))
            draw = ImageDraw.Draw(btn_img)
            draw.rounded_rectangle([0, 0, BTN_W-1, BTN_H-1], radius=12, outline=(255,255,255), width=2)

            if bg_frames:
                bg_frame = bg_frames[f_idx % len(bg_frames)]
                btn_img.paste(bg_frame, (2, 2), bg_frame)

            if icon_frames:
                icon_frame = icon_frames[f_idx % len(icon_frames)]
                icon_x = (BTN_W - 50) // 2
                btn_img.paste(icon_frame, (icon_x, 10), icon_frame)

            label = btn.get("label", "")
            if label:
                bbox = draw.textbbox((0,0), label, font=font_btn)
                tw = bbox[2] - bbox[0]
                draw.text(((BTN_W - tw)//2, BTN_H - 25), label, fill=(255,255,255), font=font_btn)

            arr = np.array(btn_img, dtype=np.uint16)
            rgb565 = ((arr[:,:,0] >> 3) << 11) | ((arr[:,:,1] >> 2) << 5) | (arr[:,:,2] >> 3)
            gif_frame_cache[(p_idx, b_idx, f_idx)] = rgb565.astype(np.uint16).tobytes()

        gif_frame_indices[f"btn_{{p_idx}}_{{b_idx}}_max"] = num_frames

print(f"Pre-rendered {{len(gif_frame_cache)}} GIF frames!")

def show_button_page(page_idx, highlight=-1):
    """Show a button page (page_idx is 0-based into BUTTON_PAGES)"""
    fb_mmap.seek(0)
    fb_mmap.write(frame_cache[(page_idx, highlight)])

def render_button_to_fb(page_idx, btn_idx):
    """Render a pre-cached GIF frame to framebuffer"""
    x1, y1, x2, y2 = get_btn_rect(btn_idx)

    frame_idx = gif_frame_indices.get(f"btn_{{page_idx}}_{{btn_idx}}", 0)
    max_frames = gif_frame_indices.get(f"btn_{{page_idx}}_{{btn_idx}}_max", 1)
    actual_frame = frame_idx % max_frames

    btn_bytes = gif_frame_cache.get((page_idx, btn_idx, actual_frame))
    if not btn_bytes:
        return

    for row in range(BTN_H):
        offset = ((y1 + row) * WIDTH + x1) * 2
        row_start = row * BTN_W * 2
        fb_mmap[offset:offset + BTN_W * 2] = btn_bytes[row_start:row_start + BTN_W * 2]

def update_gif_buttons(page_idx):
    """Update all GIF buttons for a button page"""
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
# Start on dashboard
render_dashboard()
touch = InputDevice(TOUCH_DEV)

touch_x, touch_y = 0, 0
touching = False
pending_touch = False
last_gif_update = time.time()
last_dashboard_update = time.time()
GIF_INTERVAL = 0.06
GIF_INTERVAL_MIN = 0.06
GIF_INTERVAL_MAX = 0.12
DASHBOARD_INTERVAL = 1.0  # Update dashboard every second

while True:
    # Timeout depends on current page
    if current_page == 0:
        timeout = 0.5  # Dashboard updates
    elif HAS_GIFS and current_page > 0:
        timeout = 0.03  # GIF animation
    else:
        timeout = None

    r, w, x = select.select([touch.fd], [], [], timeout)

    # Dashboard update
    if current_page == 0 and time.time() - last_dashboard_update > DASHBOARD_INTERVAL:
        render_dashboard()
        last_dashboard_update = time.time()

    # GIF animation (only on button pages)
    if current_page > 0 and HAS_GIFS and time.time() - last_gif_update > GIF_INTERVAL:
        render_start = time.time()
        advance_gif_frames()
        update_gif_buttons(current_page - 1)  # -1 because button pages are 0-indexed
        render_time = time.time() - render_start
        last_gif_update = time.time()

        # Adaptive frame rate
        if render_time > GIF_INTERVAL * 0.5:
            GIF_INTERVAL = min(GIF_INTERVAL_MAX, GIF_INTERVAL + 0.005)
        elif render_time < GIF_INTERVAL * 0.2 and GIF_INTERVAL > GIF_INTERVAL_MIN:
            GIF_INTERVAL = max(GIF_INTERVAL_MIN, GIF_INTERVAL - 0.005)

    # Touch handling
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

                    # Navigation - Next
                    if sx >= RIGHT_NAV[0] and sy >= NAV_Y:
                        if current_page < TOTAL_PAGES - 1:
                            current_page += 1
                            if current_page == 0:
                                render_dashboard()
                            else:
                                show_button_page(current_page - 1)
                        continue

                    # Navigation - Prev
                    if sx <= LEFT_NAV[2] and sy >= NAV_Y:
                        if current_page > 0:
                            current_page -= 1
                            if current_page == 0:
                                render_dashboard()
                            else:
                                show_button_page(current_page - 1)
                        continue

                    # Button press (only on button pages)
                    if current_page > 0:
                        btn_page_idx = current_page - 1
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

def main():
    try:
        import paramiko
    except ImportError:
        print("ERROR: paramiko required. Run: pip install paramiko")
        sys.exit(1)

    # Load config
    if not os.path.exists(CONFIG_FILE):
        print(f"ERROR: Config file not found: {CONFIG_FILE}")
        sys.exit(1)

    with open(CONFIG_FILE, 'r') as f:
        config = json.load(f)

    print(f"Config loaded: {len(config.get('pages', []))} button pages + 1 dashboard")

    # Generate script
    script = generate_pi_script(config)
    print(f"Generated script: {len(script)} bytes")

    # Connect to Pi
    print(f"Connecting to {PI_HOST}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(PI_HOST, username=PI_USER, password=PI_PASS, timeout=10)
    print("Connected!")

    sftp = ssh.open_sftp()

    # Create icons dir if needed
    try:
        sftp.mkdir(PI_ICONS_DIR)
    except:
        pass

    # Upload icons
    if os.path.exists(LOCAL_ICONS_DIR):
        files = os.listdir(LOCAL_ICONS_DIR)
        print(f"Uploading {len(files)} icons...")
        for filename in files:
            local_path = os.path.join(LOCAL_ICONS_DIR, filename)
            remote_path = f'{PI_ICONS_DIR}/{filename}'
            sftp.put(local_path, remote_path)
            print(f"  {filename}")

    # Upload script
    print("Uploading script...")
    with sftp.file(PI_SCRIPT, 'w') as f:
        f.write(script)

    sftp.close()

    # Stop old script
    print("Stopping old script...")
    stdin, stdout, stderr = ssh.exec_command('sudo pkill -9 -f streamdeck_fast.py')
    stdout.channel.recv_exit_status()

    import time
    time.sleep(2)

    # Start new script
    print("Starting new script...")
    ssh.exec_command(f'sudo python3 {PI_SCRIPT} > /dev/null 2>&1 &')
    time.sleep(1)

    ssh.close()
    print("Deployed successfully!")

if __name__ == "__main__":
    main()
