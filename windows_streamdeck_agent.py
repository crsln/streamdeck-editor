#!/usr/bin/env python3
"""
Windows Stream Deck Agent
Bu scripti Windows PC'de çalıştır.
Gerekli: pip install flask pyautogui
"""

from flask import Flask, jsonify, request
from urllib.parse import unquote
import pyautogui
import subprocess
import os
import json

app = Flask(__name__)

# Aksiyonlar
ACTIONS = {
    # Medya kontrolleri
    "media_playpause": lambda: pyautogui.press("playpause"),
    "media_next": lambda: pyautogui.press("nexttrack"),
    "media_prev": lambda: pyautogui.press("prevtrack"),
    "media_stop": lambda: pyautogui.press("stop"),
    
    # Ses kontrolleri
    "volume_up": lambda: pyautogui.press("volumeup"),
    "volume_down": lambda: pyautogui.press("volumedown"),
    "volume_mute": lambda: pyautogui.press("volumemute"),
    
    # OBS (varsayılan kısayollar)
    "obs_record": lambda: pyautogui.hotkey("ctrl", "shift", "r"),  # OBS kayıt başlat/durdur
    "obs_stream": lambda: pyautogui.hotkey("ctrl", "shift", "s"),  # OBS yayın başlat/durdur
    "obs_scene1": lambda: pyautogui.hotkey("ctrl", "shift", "1"),
    "obs_scene2": lambda: pyautogui.hotkey("ctrl", "shift", "2"),
    
    # Uygulamalar
    "open_notepad": lambda: subprocess.Popen("notepad.exe"),
    "open_calculator": lambda: subprocess.Popen("calc.exe"),
    "open_browser": lambda: subprocess.Popen("start chrome", shell=True),
    
    # Sistem
    "lock_screen": lambda: subprocess.run("rundll32.exe user32.dll,LockWorkStation", shell=True),
    "screenshot": lambda: pyautogui.hotkey("win", "shift", "s"),
    
    # Özel kısayollar
    "copy": lambda: pyautogui.hotkey("ctrl", "c"),
    "paste": lambda: pyautogui.hotkey("ctrl", "v"),
    "undo": lambda: pyautogui.hotkey("ctrl", "z"),
    "select_all": lambda: pyautogui.hotkey("ctrl", "a"),
}

@app.route("/")
def index():
    return "Stream Deck Agent Running! Actions: " + ", ".join(ACTIONS.keys())

@app.route("/action/<action_name>")
def do_action(action_name):
    if action_name in ACTIONS:
        try:
            ACTIONS[action_name]()
            print(f"✓ Executed: {action_name}")
            return f"OK: {action_name}"
        except Exception as e:
            print(f"✗ Error: {action_name} - {e}")
            return f"Error: {e}", 500
    else:
        return f"Unknown action: {action_name}", 404

@app.route("/launch")
def launch_app():
    path = request.args.get("path", "")
    if path:
        path = unquote(path)
        try:
            subprocess.Popen(f'start "" "{path}"', shell=True)
            print(f"✓ Launched: {path}")
            return f"OK: launched {path}"
        except Exception as e:
            print(f"✗ Error launching: {path} - {e}")
            return f"Error: {e}", 500
    return "Error: no path provided", 400

# ============== SYSTEM STATS ENDPOINT ==============

@app.route("/system/stats")
def system_stats():
    """Return Windows system stats (CPU, RAM, Disk, GPU)"""
    import psutil
    stats = {}
    
    try:
        # CPU
        stats['cpu_percent'] = psutil.cpu_percent(interval=0.5)
        stats['cpu_count'] = psutil.cpu_count()
        stats['cpu_freq'] = psutil.cpu_freq().current if psutil.cpu_freq() else 0
        
        # RAM
        mem = psutil.virtual_memory()
        stats['ram_percent'] = mem.percent
        stats['ram_used_gb'] = round(mem.used / (1024**3), 1)
        stats['ram_total_gb'] = round(mem.total / (1024**3), 1)
        
        # Disk (C:)
        disk = psutil.disk_usage('C:\\')
        stats['disk_percent'] = round(disk.percent, 1)
        stats['disk_used_gb'] = round(disk.used / (1024**3), 0)
        stats['disk_total_gb'] = round(disk.total / (1024**3), 0)
        
        # GPU (nvidia-smi)
        try:
            gpu_result = subprocess.run(
                ['nvidia-smi', '--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu', '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=5
            )
            if gpu_result.returncode == 0:
                parts = gpu_result.stdout.strip().split(', ')
                stats['gpu_percent'] = int(parts[0])
                stats['gpu_mem_used_mb'] = int(parts[1])
                stats['gpu_mem_total_mb'] = int(parts[2])
                stats['gpu_temp'] = int(parts[3])
            else:
                stats['gpu_percent'] = 0
                stats['gpu_temp'] = 0
        except:
            stats['gpu_percent'] = 0
            stats['gpu_temp'] = 0
        
        # Uptime
        stats['uptime_hours'] = round((psutil.time.time() - psutil.boot_time()) / 3600, 1)
        
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)})

# ============== DOCKER ENDPOINTS ==============

@app.route("/docker/containers")
def docker_containers():
    """Return running Docker containers as JSON"""
    try:
        result = subprocess.run(
            ['docker', 'ps', '--format', '{{json .}}'],
            capture_output=True, text=True, timeout=10
        )
        containers = []
        for line in result.stdout.strip().split('\n'):
            if line:
                try:
                    c = json.loads(line)
                    containers.append({
                        'name': c.get('Names', ''),
                        'image': c.get('Image', ''),
                        'status': c.get('Status', ''),
                        'ports': c.get('Ports', ''),
                        'state': c.get('State', ''),
                        'id': c.get('ID', '')[:12]
                    })
                except json.JSONDecodeError:
                    pass
        return jsonify({'containers': containers, 'count': len(containers)})
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Docker command timed out', 'containers': []})
    except FileNotFoundError:
        return jsonify({'error': 'Docker not found', 'containers': []})
    except Exception as e:
        return jsonify({'error': str(e), 'containers': []})

@app.route("/docker/stats")
def docker_stats():
    """Return Docker system stats"""
    try:
        # Container count
        ps_result = subprocess.run(
            ['docker', 'ps', '-q'],
            capture_output=True, text=True, timeout=5
        )
        running = len([x for x in ps_result.stdout.strip().split('\n') if x])
        
        # All containers count
        ps_all = subprocess.run(
            ['docker', 'ps', '-aq'],
            capture_output=True, text=True, timeout=5
        )
        total = len([x for x in ps_all.stdout.strip().split('\n') if x])
        
        # Images count
        images = subprocess.run(
            ['docker', 'images', '-q'],
            capture_output=True, text=True, timeout=5
        )
        image_count = len([x for x in images.stdout.strip().split('\n') if x])
        
        return jsonify({
            'running': running,
            'total': total,
            'stopped': total - running,
            'images': image_count
        })
    except Exception as e:
        return jsonify({'error': str(e), 'running': 0, 'total': 0, 'images': 0})

if __name__ == "__main__":
    print("=" * 50)
    print("  STREAM DECK AGENT")
    print("=" * 50)
    print(f"Listening on http://0.0.0.0:5555")
    print(f"Available actions: {len(ACTIONS)}")
    print("Endpoints: /docker/containers, /docker/stats")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5555, debug=False)
