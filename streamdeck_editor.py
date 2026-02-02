#!/usr/bin/env python3
"""
Stream Deck Button Editor
Windows'ta çalıştır - Pi'deki butonları düzenle
Gerekli: pip install paramiko
"""

import tkinter as tk
from tkinter import ttk, colorchooser, messagebox
import json
import os

# Pi bağlantı bilgileri
PI_HOST = "192.168.1.112"
PI_USER = "cem"
PI_PASS = "3235"
PI_SCRIPT_PATH = "/home/cem/streamdeck.py"

# Varsayılan butonlar
DEFAULT_BUTTONS = [
    {"label": "Play/\nPause", "action": "media_playpause", "color": [46, 204, 113]},
    {"label": "Next", "action": "media_next", "color": [52, 152, 219]},
    {"label": "Prev", "action": "media_prev", "color": [155, 89, 182]},
    {"label": "Vol+", "action": "volume_up", "color": [241, 196, 15]},
    {"label": "Vol-", "action": "volume_down", "color": [230, 126, 34]},
    {"label": "Mute", "action": "volume_mute", "color": [231, 76, 60]},
    {"label": "OBS\nRec", "action": "obs_record", "color": [192, 57, 43]},
    {"label": "OBS\nStream", "action": "obs_stream", "color": [142, 68, 173]},
    {"label": "Note-\npad", "action": "open_notepad", "color": [22, 160, 133]},
]

AVAILABLE_ACTIONS = [
    "media_playpause", "media_next", "media_prev", "media_stop",
    "volume_up", "volume_down", "volume_mute",
    "obs_record", "obs_stream", "obs_scene1", "obs_scene2",
    "open_notepad", "open_calculator", "open_browser",
    "lock_screen", "screenshot",
    "copy", "paste", "undo", "select_all"
]

CONFIG_FILE = "streamdeck_config.json"

class ButtonEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("🎮 Stream Deck Editor")
        self.root.geometry("800x600")
        self.root.configure(bg="#2c2c2c")
        
        self.buttons = self.load_config()
        self.selected_index = None
        self.windows_ip = tk.StringVar(value="192.168.1.XXX")
        
        self.create_ui()
        self.refresh_grid()
    
    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return [b.copy() for b in DEFAULT_BUTTONS]
    
    def save_config(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.buttons, f, indent=2)
    
    def create_ui(self):
        # Ana frame
        main = tk.Frame(self.root, bg="#2c2c2c")
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Sol: Buton grid önizleme
        left = tk.Frame(main, bg="#1a1a1a", width=350)
        left.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0,10))
        
        tk.Label(left, text="📱 Önizleme", font=("Arial", 14, "bold"), 
                bg="#1a1a1a", fg="white").pack(pady=10)
        
        self.grid_frame = tk.Frame(left, bg="#1a1a1a")
        self.grid_frame.pack(padx=20, pady=10)
        
        # Sağ: Editor
        right = tk.Frame(main, bg="#2c2c2c")
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Windows IP
        ip_frame = tk.Frame(right, bg="#2c2c2c")
        ip_frame.pack(fill=tk.X, pady=(0,20))
        tk.Label(ip_frame, text="Windows IP:", font=("Arial", 11),
                bg="#2c2c2c", fg="white").pack(side=tk.LEFT)
        tk.Entry(ip_frame, textvariable=self.windows_ip, width=15,
                font=("Arial", 11)).pack(side=tk.LEFT, padx=10)
        
        # Buton editor
        tk.Label(right, text="✏️ Buton Düzenle", font=("Arial", 14, "bold"),
                bg="#2c2c2c", fg="white").pack(anchor=tk.W)
        tk.Label(right, text="(Soldaki butona tıkla)", font=("Arial", 10),
                bg="#2c2c2c", fg="gray").pack(anchor=tk.W)
        
        edit_frame = tk.Frame(right, bg="#3c3c3c", padx=15, pady=15)
        edit_frame.pack(fill=tk.X, pady=10)
        
        # Label
        tk.Label(edit_frame, text="Label:", bg="#3c3c3c", fg="white").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.label_entry = tk.Entry(edit_frame, width=20, font=("Arial", 11))
        self.label_entry.grid(row=0, column=1, pady=5, padx=10)
        tk.Label(edit_frame, text="(\\n = yeni satır)", bg="#3c3c3c", fg="gray", font=("Arial", 9)).grid(row=0, column=2)
        
        # Action
        tk.Label(edit_frame, text="Action:", bg="#3c3c3c", fg="white").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.action_combo = ttk.Combobox(edit_frame, values=AVAILABLE_ACTIONS, width=18, font=("Arial", 11))
        self.action_combo.grid(row=1, column=1, pady=5, padx=10)
        
        # Color
        tk.Label(edit_frame, text="Renk:", bg="#3c3c3c", fg="white").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.color_btn = tk.Button(edit_frame, text="     ", width=10, command=self.pick_color)
        self.color_btn.grid(row=2, column=1, pady=5, padx=10, sticky=tk.W)
        
        # Uygula butonu
        tk.Button(edit_frame, text="✓ Uygula", command=self.apply_changes,
                 bg="#27ae60", fg="white", font=("Arial", 11, "bold"),
                 padx=20, pady=5).grid(row=3, column=1, pady=15)
        
        # Alt butonlar
        bottom = tk.Frame(right, bg="#2c2c2c")
        bottom.pack(fill=tk.X, pady=20)
        
        tk.Button(bottom, text="💾 Kaydet", command=self.save_config,
                 bg="#3498db", fg="white", font=("Arial", 11),
                 padx=15, pady=8).pack(side=tk.LEFT, padx=5)
        
        tk.Button(bottom, text="📤 Pi'ye Gönder", command=self.upload_to_pi,
                 bg="#9b59b6", fg="white", font=("Arial", 11),
                 padx=15, pady=8).pack(side=tk.LEFT, padx=5)
        
        tk.Button(bottom, text="🚀 Pi'de Başlat", command=self.start_on_pi,
                 bg="#e74c3c", fg="white", font=("Arial", 11),
                 padx=15, pady=8).pack(side=tk.LEFT, padx=5)
        
        # Action listesi
        tk.Label(right, text="📋 Kullanılabilir Action'lar:", font=("Arial", 11, "bold"),
                bg="#2c2c2c", fg="white").pack(anchor=tk.W, pady=(20,5))
        
        actions_text = tk.Text(right, height=8, width=50, bg="#1a1a1a", fg="#aaa",
                              font=("Consolas", 9))
        actions_text.pack(anchor=tk.W)
        actions_text.insert(tk.END, "\n".join(AVAILABLE_ACTIONS))
        actions_text.config(state=tk.DISABLED)
    
    def refresh_grid(self):
        for widget in self.grid_frame.winfo_children():
            widget.destroy()
        
        for i, btn in enumerate(self.buttons):
            row, col = i // 3, i % 3
            color = "#{:02x}{:02x}{:02x}".format(*btn["color"])
            
            frame = tk.Frame(self.grid_frame, bg=color, width=100, height=80)
            frame.grid(row=row, column=col, padx=3, pady=3)
            frame.grid_propagate(False)
            
            label = tk.Label(frame, text=btn["label"].replace("\\n", "\n"), 
                           bg=color, fg="white", font=("Arial", 10, "bold"))
            label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
            
            # Click binding
            for widget in [frame, label]:
                widget.bind("<Button-1>", lambda e, idx=i: self.select_button(idx))
    
    def select_button(self, index):
        self.selected_index = index
        btn = self.buttons[index]
        
        self.label_entry.delete(0, tk.END)
        self.label_entry.insert(0, btn["label"])
        
        self.action_combo.set(btn["action"])
        
        color = "#{:02x}{:02x}{:02x}".format(*btn["color"])
        self.color_btn.configure(bg=color)
        
        self.refresh_grid()
    
    def pick_color(self):
        color = colorchooser.askcolor(title="Renk Seç")[0]
        if color:
            self.current_color = [int(c) for c in color]
            hex_color = "#{:02x}{:02x}{:02x}".format(*self.current_color)
            self.color_btn.configure(bg=hex_color)
    
    def apply_changes(self):
        if self.selected_index is None:
            messagebox.showwarning("Uyarı", "Önce bir buton seç!")
            return
        
        self.buttons[self.selected_index]["label"] = self.label_entry.get()
        self.buttons[self.selected_index]["action"] = self.action_combo.get()
        if hasattr(self, 'current_color'):
            self.buttons[self.selected_index]["color"] = self.current_color
        
        self.save_config()
        self.refresh_grid()
        messagebox.showinfo("OK", "Buton güncellendi!")
    
    def generate_pi_script(self):
        buttons_str = json.dumps(self.buttons, indent=4).replace('"', '\\"')
        
        script = f'''#!/usr/bin/env python3
import pygame
import requests
import os
import json

WINDOWS_PC_IP = "{self.windows_ip.get()}"
WINDOWS_PORT = 5555
SCREEN_WIDTH = 480
SCREEN_HEIGHT = 320

BUTTONS = {json.dumps(self.buttons, indent=4)}

COLS = 3
ROWS = 3
BTN_MARGIN = 10
BTN_WIDTH = (SCREEN_WIDTH - (COLS + 1) * BTN_MARGIN) // COLS
BTN_HEIGHT = (SCREEN_HEIGHT - (ROWS + 1) * BTN_MARGIN) // ROWS

def send_action(action):
    try:
        url = f"http://{{WINDOWS_PC_IP}}:{{WINDOWS_PORT}}/action/{{action}}"
        requests.get(url, timeout=2)
        return True
    except:
        return False

def get_button_rect(index):
    row = index // COLS
    col = index % COLS
    x = BTN_MARGIN + col * (BTN_WIDTH + BTN_MARGIN)
    y = BTN_MARGIN + row * (BTN_HEIGHT + BTN_MARGIN)
    return pygame.Rect(x, y, BTN_WIDTH, BTN_HEIGHT)

def main():
    os.environ["SDL_FBDEV"] = "/dev/fb1"
    os.environ["SDL_MOUSEDEV"] = "/dev/input/event0"
    os.environ["SDL_MOUSEDRV"] = "TSLIB"
    
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.mouse.set_visible(False)
    font = pygame.font.Font(None, 28)
    
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                for i, btn in enumerate(BUTTONS):
                    rect = get_button_rect(i)
                    if rect.collidepoint(event.pos):
                        send_action(btn["action"])
                        pygame.draw.rect(screen, (255,255,255), rect)
                        pygame.display.flip()
                        pygame.time.wait(100)
        
        screen.fill((30, 30, 30))
        for i, btn in enumerate(BUTTONS):
            rect = get_button_rect(i)
            color = tuple(btn["color"])
            pygame.draw.rect(screen, color, rect, border_radius=10)
            pygame.draw.rect(screen, (255,255,255), rect, 2, border_radius=10)
            
            lines = btn["label"].replace("\\\\n", "\\n").split("\\n")
            total_height = len(lines) * 25
            start_y = rect.centery - total_height // 2
            for j, line in enumerate(lines):
                text = font.render(line, True, (255, 255, 255))
                text_rect = text.get_rect(center=(rect.centerx, start_y + j * 25 + 12))
                screen.blit(text, text_rect)
        
        pygame.display.flip()
        pygame.time.wait(50)
    
    pygame.quit()

if __name__ == "__main__":
    main()
'''
        return script
    
    def upload_to_pi(self):
        try:
            import paramiko
        except ImportError:
            messagebox.showerror("Hata", "paramiko gerekli!\npip install paramiko")
            return
        
        try:
            script = self.generate_pi_script()
            
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(PI_HOST, username=PI_USER, password=PI_PASS, timeout=10)
            
            sftp = ssh.open_sftp()
            with sftp.file(PI_SCRIPT_PATH, 'w') as f:
                f.write(script)
            sftp.close()
            ssh.close()
            
            messagebox.showinfo("OK", "Script Pi'ye yüklendi!")
        except Exception as e:
            messagebox.showerror("Hata", f"Yükleme hatası:\n{e}")
    
    def start_on_pi(self):
        try:
            import paramiko
        except ImportError:
            messagebox.showerror("Hata", "paramiko gerekli!\npip install paramiko")
            return
        
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(PI_HOST, username=PI_USER, password=PI_PASS, timeout=10)
            
            # Önce varsa öldür
            ssh.exec_command("pkill -f streamdeck.py")
            import time
            time.sleep(1)
            
            # Başlat
            ssh.exec_command(f"cd /home/cem && sudo python3 streamdeck.py &")
            ssh.close()
            
            messagebox.showinfo("OK", "Stream Deck Pi'de başlatıldı!")
        except Exception as e:
            messagebox.showerror("Hata", f"Başlatma hatası:\n{e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = ButtonEditor(root)
    root.mainloop()
