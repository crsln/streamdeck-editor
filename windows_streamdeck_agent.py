#!/usr/bin/env python3
"""
Windows Stream Deck Agent
Bu scripti Windows PC'de çalıştır.
Gerekli: pip install flask pyautogui psutil
"""

from flask import Flask, jsonify, request
from urllib.parse import unquote
import pyautogui
import subprocess
import os
import json
import time

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
    "obs_record": lambda: pyautogui.hotkey("ctrl", "shift", "r"),
    "obs_stream": lambda: pyautogui.hotkey("ctrl", "shift", "s"),
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
    """Return Windows system stats (CPU, RAM, Disk, GPU, Temps, Fans)"""
    import psutil
    stats = {}
    
    try:
        # CPU
        stats['cpu_percent'] = psutil.cpu_percent(interval=0.5)
        stats['cpu_count'] = psutil.cpu_count()
        freq = psutil.cpu_freq()
        stats['cpu_freq_current'] = round(freq.current, 0) if freq else 0
        stats['cpu_freq_max'] = round(freq.max, 0) if freq else 0
        
        # CPU per-core usage
        stats['cpu_per_core'] = psutil.cpu_percent(interval=0.1, percpu=True)
        
        # RAM
        mem = psutil.virtual_memory()
        stats['ram_percent'] = mem.percent
        stats['ram_used_gb'] = round(mem.used / (1024**3), 1)
        stats['ram_total_gb'] = round(mem.total / (1024**3), 1)
        stats['ram_available_gb'] = round(mem.available / (1024**3), 1)
        
        # Disk (C:)
        disk = psutil.disk_usage('C:\\')
        stats['disk_percent'] = round(disk.percent, 1)
        stats['disk_used_gb'] = round(disk.used / (1024**3), 0)
        stats['disk_total_gb'] = round(disk.total / (1024**3), 0)
        stats['disk_free_gb'] = round(disk.free / (1024**3), 0)
        
        # Network
        net = psutil.net_io_counters()
        stats['net_sent_gb'] = round(net.bytes_sent / (1024**3), 2)
        stats['net_recv_gb'] = round(net.bytes_recv / (1024**3), 2)
        
        # GPU (nvidia-smi with extended info)
        try:
            gpu_result = subprocess.run(
                ['nvidia-smi', '--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,fan.speed,power.draw,power.limit,clocks.current.graphics,name', '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=5
            )
            if gpu_result.returncode == 0:
                parts = [p.strip() for p in gpu_result.stdout.strip().split(', ')]
                stats['gpu_percent'] = int(parts[0])
                stats['gpu_mem_used_mb'] = int(parts[1])
                stats['gpu_mem_total_mb'] = int(parts[2])
                stats['gpu_temp'] = int(parts[3])
                stats['gpu_fan_percent'] = int(parts[4]) if parts[4] != '[N/A]' else 0
                stats['gpu_power_w'] = round(float(parts[5]), 1) if parts[5] != '[N/A]' else 0
                stats['gpu_power_limit_w'] = round(float(parts[6]), 1) if parts[6] != '[N/A]' else 0
                stats['gpu_clock_mhz'] = int(parts[7]) if parts[7] != '[N/A]' else 0
                stats['gpu_name'] = parts[8] if len(parts) > 8 else 'Unknown'
            else:
                stats['gpu_percent'] = 0
                stats['gpu_temp'] = 0
                stats['gpu_fan_percent'] = 0
        except:
            stats['gpu_percent'] = 0
            stats['gpu_temp'] = 0
            stats['gpu_fan_percent'] = 0
        
        # CPU Temperature from LibreHardwareMonitor HTTP API (port 8085)
        stats['cpu_temp'] = 0
        try:
            lhm_resp = requests.get('http://localhost:8085/data.json', timeout=2)
            lhm_data = lhm_resp.json()
            
            def find_cpu_temp(node):
                """Recursively search for CPU temperature in LHM JSON"""
                if isinstance(node, dict):
                    # Check if this is a CPU temp sensor
                    text = node.get('Text', '')
                    if 'CPU' in text and node.get('Min') and 'Core' in text:
                        try:
                            # Value format: "44 °C" or similar
                            val = node.get('Value', '0')
                            if '°C' in str(val):
                                return float(val.replace('°C', '').strip())
                        except:
                            pass
                    # Check children
                    for child in node.get('Children', []):
                        result = find_cpu_temp(child)
                        if result:
                            return result
                return None
            
            temp = find_cpu_temp(lhm_data)
            if temp:
                stats['cpu_temp'] = round(temp, 1)
        except:
            pass
        
        # Uptime
        stats['uptime_hours'] = round((time.time() - psutil.boot_time()) / 3600, 1)
        stats['uptime_days'] = round((time.time() - psutil.boot_time()) / 86400, 2)
        
        # Process count
        stats['process_count'] = len(psutil.pids())
        
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
        ps_result = subprocess.run(
            ['docker', 'ps', '-q'],
            capture_output=True, text=True, timeout=5
        )
        running = len([x for x in ps_result.stdout.strip().split('\n') if x])
        
        ps_all = subprocess.run(
            ['docker', 'ps', '-aq'],
            capture_output=True, text=True, timeout=5
        )
        total = len([x for x in ps_all.stdout.strip().split('\n') if x])
        
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
    print("Endpoints: /system/stats, /docker/containers, /docker/stats")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5555, debug=False)
