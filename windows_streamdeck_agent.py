#!/usr/bin/env python3
"""
Windows Stream Deck Agent
Bu scripti Windows PC'de çalıştır.
Gerekli: pip install flask pyautogui
"""

from flask import Flask
import pyautogui
import subprocess
import os

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

if __name__ == "__main__":
    print("=" * 50)
    print("  STREAM DECK AGENT")
    print("=" * 50)
    print(f"Listening on http://0.0.0.0:5555")
    print(f"Available actions: {len(ACTIONS)}")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5555, debug=False)
