# Raspberry Pi Stream Deck Editor

Windows uygulaması ile Raspberry Pi üzerinde çalışan Stream Deck'i düzenle.

## Dosyalar

- **`windows_streamdeck_agent.py`** - Windows'ta çalışan agent (Flask server). Buton aksiyonlarını alır ve çalıştırır.
- **`streamdeck_editor_v2.py`** - GUI editör (Tkinter). Butonları düzenle, kaydet.
- **`streamdeck_editor.py`** - İlk versiyon (referans için)

## Kurulum

### Windows PC
```bash
pip install flask pyautogui
python windows_streamdeck_agent.py
```

### Raspberry Pi
Stream Deck web arayüzü zaten kurulu (Flask app).

## Kullanım

1. Windows'ta agent'ı başlat
2. Editor'ü aç: `python streamdeck_editor_v2.py`
3. Butonları düzenle (sürükle-bırak, renk, ikon, aksiyon)
4. Kaydet → Pi'deki config güncellenir

## Aksiyonlar

- Medya kontrolleri (play/pause, next, prev)
- Ses (volume up/down/mute)
- OBS kontrolleri
- Uygulama açma
- Sistem (lock, screenshot)
- Özel kısayollar
