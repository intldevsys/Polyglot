import customtkinter as ctk
from tkinter import messagebox, simpledialog
import pyautogui
from PIL import Image, ImageTk, ImageDraw, ImageFont
import pytesseract
import threading
import time
import queue
import json
import os
from pynput import keyboard
import cv2
import numpy as np
from collections import OrderedDict
import hashlib
import ctypes
from ctypes import wintypes
import requests

# Set CustomTkinter appearance and theme
ctk.set_appearance_mode("dark")  # "dark" or "light"
ctk.set_default_color_theme("blue")  # "blue", "green", or "dark-blue"

# Google Cloud Translation
try:
    from google.cloud import translate_v2 as translate
    GOOGLE_CLOUD_AVAILABLE = True
except ImportError:
    GOOGLE_CLOUD_AVAILABLE = False
    print("Google Cloud Translation not available. Install with: pip install google-cloud-translate")

# Windows API for click-through
try:
    import win32gui
    import win32con
    import win32api
    WINDOWS_AVAILABLE = True
except ImportError:
    WINDOWS_AVAILABLE = False
    print("Note: pywin32 not installed. Overlays may not be fully click-through.")
    print("Install with: pip install pywin32")

# Configuration
CONFIG = {
    "tesseract_path": r"C:\Program Files\Tesseract-OCR\tesseract.exe",  # Update this path 
    "deepl_api_key": "API_KEY",  # Your DeepL API key
    "update_interval": 500,  # milliseconds
    "cache_size": 1000,
    "default_target_lang": "en",  # English by default, change as needed
    "overlay_bg_color": "#2C3E50",
    "overlay_text_color": "#FFFFFF",
    "overlay_opacity": 0.95,
    "font_size": 13,
    "min_confidence": 30,  # Minimum OCR confidence threshold
    "max_text_length": 5000  # Maximum text length to translate
}

# Set Tesseract path if needed
if os.path.exists(CONFIG["tesseract_path"]):
    pytesseract.pytesseract.tesseract_cmd = CONFIG["tesseract_path"]

class TranslationCache:
    """LRU cache for translations"""
    def __init__(self, max_size=1000):
        self.cache = OrderedDict()
        self.max_size = max_size
    
    def get(self, text, source_lang, target_lang):
        key = f"{text}_{source_lang}_{target_lang}"
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        return None
    
    def put(self, text, translation, source_lang, target_lang):
        key = f"{text}_{source_lang}_{target_lang}"
        self.cache[key] = translation
        if len(self.cache) > self.max_size:
            self.cache.popitem(last=False)

class RegionSelector:
    """Transparent overlay for selecting screen regions"""
    def __init__(self, callback):
        self.callback = callback
        self.root = None
        self.start_x = None
        self.start_y = None
        self.rect = None
        
    def start_selection(self):
        # Use regular tkinter for the selection overlay since CustomTkinter doesn't support fullscreen overlays well
        import tkinter as tk
        self.root = tk.Tk()
        self.root.attributes('-fullscreen', True)
        self.root.attributes('-alpha', 0.3)
        self.root.attributes('-topmost', True)
        self.root.configure(background='grey')
        
        self.canvas = tk.Canvas(self.root, cursor="cross", bg='grey', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Escape>", lambda e: self.cancel())
        
        # Instructions
        self.canvas.create_text(
            self.root.winfo_screenwidth() // 2,
            50,
            text="Drag to select region for translation (ESC to cancel)",
            font=("Segoe UI", 16),
            fill="white"
        )
        
        self.root.mainloop()
    
    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline='#1f538d', width=3, fill='#1f538d', stipple='gray50'
        )
    
    def on_drag(self, event):
        if self.rect:
            self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)
    
    def on_release(self, event):
        if self.start_x and self.start_y:
            x1 = min(self.start_x, event.x)
            y1 = min(self.start_y, event.y)
            x2 = max(self.start_x, event.x)
            y2 = max(self.start_y, event.y)
            
            if abs(x2 - x1) > 10 and abs(y2 - y1) > 10:  # Minimum size
                self.root.destroy()
                self.callback((x1, y1, x2, y2))
            else:
                messagebox.showwarning("Invalid Selection", "Please select a larger region")
    
    def cancel(self):
        if self.root:
            self.root.destroy()

class TranslationOverlay:
    """Overlay window to display translations"""
    def __init__(self):
        self.windows = []
        self.active = True
        
    def show_translation(self, x, y, width, height, original_text, translated_text):
        """Create overlay that covers the original text"""
        import tkinter as tk
        # Create new overlay window using regular tkinter for better overlay support
        overlay = tk.Toplevel()
        overlay.attributes('-topmost', True)
        overlay.overrideredirect(True)
        
        # Set window size and position first
        overlay.geometry(f"{width}x{height}+{x}+{y}")
        
        # Create frame with background color
        frame = tk.Frame(overlay, bg=CONFIG["overlay_bg_color"])
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Calculate font size based on region height
        font_size = max(10, min(CONFIG["font_size"], int(height * 0.5)))
        
        # Create label with translated text
        label = tk.Label(
            frame,
            text=translated_text,
            bg=CONFIG["overlay_bg_color"],
            fg=CONFIG["overlay_text_color"],
            font=("Segoe UI", font_size, "bold"),
            wraplength=width - 10,
            justify="center"
        )
        label.place(relx=0.5, rely=0.5, anchor="center")
        
        # Set transparency
        overlay.attributes('-alpha', CONFIG["overlay_opacity"])
        
        # Make click-through on Windows
        if WINDOWS_AVAILABLE:
            overlay.update()
            hwnd = ctypes.windll.user32.GetParent(overlay.winfo_id())
            # Set extended window style for click-through
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            style |= win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style)
        
        self.windows.append(overlay)
        
        # Auto-hide after delay
        overlay.after(10000, lambda: self.remove_overlay(overlay))
        
        return overlay
    
    def remove_overlay(self, overlay):
        """Remove specific overlay"""
        if overlay in self.windows:
            self.windows.remove(overlay)
            overlay.destroy()
    
    def clear_all(self):
        """Remove all overlays"""
        for window in self.windows:
            window.destroy()
        self.windows.clear()

class ScreenTranslator:
    """Main translator application"""
    def __init__(self):
        self.translator = None
        self.setup_translator()
        self.cache = TranslationCache(CONFIG["cache_size"])
        self.overlay = TranslationOverlay()
        self.monitoring_regions = []
        self.monitoring_active = False
        self.monitor_thread = None
        self.previous_hashes = {}
        
        # Create main window
        self.create_gui()
        
        # Setup global hotkeys
        self.setup_hotkeys()
    
    def setup_translator(self):
        """Setup Google Cloud Translation or fallback"""
        if GOOGLE_CLOUD_AVAILABLE:
            try:
                # Option 1: Use API key directly
                if CONFIG.get("google_cloud_api_key"):
                    # For API key authentication, we need to use the v3 client
                    from google.cloud import translate_v3 as translate_v3
                    from google.oauth2 import service_account
                    
                    # Create credentials from API key
                    import requests
                    
                    class GoogleTranslateWithAPIKey:
                        def __init__(self, api_key):
                            self.api_key = api_key
                            self.base_url = "https://translation.googleapis.com/language/translate/v2"
                        
                        def translate(self, text, target_language, source_language=None):
                            # Clean and validate text
                            if not text or not text.strip():
                                return {'translatedText': ''}
                            
                            # Limit text length (Google Translate has limits)
                            if len(text) > 5000:
                                text = text[:5000]
                            
                            params = {
                                'q': text.strip(),
                                'target': target_language,
                                'key': self.api_key,
                                'format': 'text'  # Specify plain text format
                            }
                            if source_language and source_language != 'auto':
                                params['source'] = source_language
                            
                            try:
                                response = requests.get(self.base_url, params=params, timeout=10)
                                
                                if response.status_code == 200:
                                    result = response.json()
                                    if 'data' in result and 'translations' in result['data']:
                                        return {
                                            'translatedText': result['data']['translations'][0]['translatedText']
                                        }
                                    else:
                                        print(f"Unexpected API response: {result}")
                                        return {'translatedText': text}
                                else:
                                    error_data = response.json() if response.content else {}
                                    error_msg = error_data.get('error', {}).get('message', 'Unknown error')
                                    print(f"Translation API error {response.status_code}: {error_msg}")
                                    print(f"Request URL: {response.url}")
                                    print(f"Text that failed: {text[:100]}...")
                                    
                                    if response.status_code == 403:
                                        raise Exception(f"API key error: {error_msg}")
                                    elif response.status_code == 400:
                                        # Bad request - possibly due to special characters or language code
                                        print(f"Bad request - text might contain special characters")
                                        return {'translatedText': text}  # Return original text
                                    else:
                                        raise Exception(f"Translation API error: {response.status_code} - {error_msg}")
                            except requests.exceptions.Timeout:
                                print("Translation request timed out")
                                return {'translatedText': text}
                            except requests.exceptions.RequestException as e:
                                print(f"Network error: {e}")
                                return {'translatedText': text}
                    
                    self.translator = GoogleTranslateWithAPIKey(CONFIG["google_cloud_api_key"])
                    print("Using Google Cloud Translation with API key")
                    
                    # Test the API key
                    try:
                        test_result = self.translator.translate("Hello", "es")
                        print(f"API key test successful: Hello -> {test_result['translatedText']}")
                    except Exception as e:
                        print(f"API key test failed: {e}")
                        messagebox.showwarning(
                            "Google Cloud API Error",
                            f"{e}\n\nFalling back to alternative translation service."
                        )
                        self.setup_fallback_translator()
                        return
                    
                # Option 2: Use service account credentials from environment
                elif os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
                    self.translator = translate.Client()
                    print("Using Google Cloud Translation with service account")
                else:
                    print("No Google Cloud credentials found")
                    self.setup_fallback_translator()
            except Exception as e:
                print(f"Error setting up Google Cloud Translation: {e}")
                self.setup_fallback_translator()
        else:
            self.setup_fallback_translator()
    
    def setup_fallback_translator(self):
        """Setup DeepL as fallback translation method"""
        try:
            # Try DeepL API as the primary fallback
            import requests
            
            class DeepLTranslateClient:
                def __init__(self, api_key=None, use_free=True):
                    self.api_key = api_key
                    # DeepL free vs pro API endpoints
                    self.base_url = "https://api-free.deepl.com/v2" if use_free else "https://api.deepl.com/v2"
                    self.session = requests.Session()
                    
                    # Language mapping for DeepL
                    self.lang_map = {
                        'zh-cn': 'ZH',
                        'zh-tw': 'ZH',
                        'zh': 'ZH',
                        'en': 'EN',
                        'es': 'ES',
                        'fr': 'FR',
                        'de': 'DE',
                        'it': 'IT',
                        'pt': 'PT',
                        'ru': 'RU',
                        'ja': 'JA',
                        'ko': 'KO',
                        'ar': 'AR',
                        'hi': 'HI',
                        'nl': 'NL',
                        'pl': 'PL',
                        'sv': 'SV',
                        'da': 'DA',
                        'fi': 'FI',
                        'no': 'NB',
                        'cs': 'CS',
                        'hu': 'HU',
                        'ro': 'RO',
                        'sk': 'SK',
                        'sl': 'SL',
                        'et': 'ET',
                        'lv': 'LV',
                        'lt': 'LT',
                        'bg': 'BG',
                        'el': 'EL',
                        'tr': 'TR',
                        'uk': 'UK',
                        'id': 'ID',
                    }
                    
                    if self.api_key:
                        self._test_connection()
                
                def _test_connection(self):
                    """Test if DeepL API key is valid"""
                    try:
                        headers = {'Authorization': f'DeepL-Auth-Key {self.api_key}'}
                        response = self.session.get(f"{self.base_url}/usage", headers=headers, timeout=5)
                        if response.status_code == 200:
                            usage_data = response.json()
                            print(f"Connected to DeepL API - Usage: {usage_data.get('character_count', 0)}/{usage_data.get('character_limit', 'unlimited')} characters")
                            return True
                        else:
                            raise Exception(f"API returned status {response.status_code}")
                    except Exception as e:
                        raise Exception(f"Cannot connect to DeepL API: {e}")
                
                def translate(self, text, dest, src='auto'):
                    """Translate text using DeepL API"""
                    if not text or not text.strip():
                        return type('obj', (object,), {'text': ''})()
                    
                    # Limit text length (DeepL free has 500,000 char/month limit)
                    if len(text) > 5000:
                        text = text[:5000]
                    
                    # Map language codes to DeepL format
                    target_lang = self.lang_map.get(dest.lower(), dest.upper())
                    source_lang = self.lang_map.get(src.lower(), src.upper()) if src != 'auto' else None
                    
                    # Check if target language is supported
                    if target_lang not in self.lang_map.values():
                        print(f"Language {dest} not supported by DeepL")
                        return type('obj', (object,), {'text': text})()
                    
                    data = {
                        'text': text.strip(),
                        'target_lang': target_lang,
                    }
                    
                    if source_lang and source_lang != 'AUTO':
                        data['source_lang'] = source_lang
                    
                    headers = {
                        'Authorization': f'DeepL-Auth-Key {self.api_key}',
                        'Content-Type': 'application/x-www-form-urlencoded'
                    }
                    
                    try:
                        response = self.session.post(
                            f"{self.base_url}/translate",
                            data=data,
                            headers=headers,
                            timeout=15
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                            translated_text = result['translations'][0]['text']
                            # Create an object similar to googletrans result
                            return type('obj', (object,), {'text': translated_text})()
                        elif response.status_code == 403:
                            print("DeepL API key invalid or quota exceeded")
                            return type('obj', (object,), {'text': text})()
                        elif response.status_code == 456:
                            print("DeepL quota exceeded")
                            return type('obj', (object,), {'text': text})()
                        else:
                            error_msg = f"DeepL API error: {response.status_code}"
                            if response.content:
                                try:
                                    error_data = response.json()
                                    error_msg = error_data.get('message', error_msg)
                                except:
                                    pass
                            print(error_msg)
                            return type('obj', (object,), {'text': text})()
                            
                    except requests.exceptions.Timeout:
                        print("DeepL request timed out")
                        return type('obj', (object,), {'text': text})()
                    except requests.exceptions.RequestException as e:
                        print(f"DeepL network error: {e}")
                        return type('obj', (object,), {'text': text})()
            
            # Check if DeepL API key is available
            deepl_api_key = CONFIG.get("deepl_api_key") or os.environ.get("DEEPL_API_KEY")
            
            if deepl_api_key:
                try:
                    # Determine if it's a free or pro key based on the key format
                    use_free = deepl_api_key.endswith(':fx')
                    self.translator = DeepLTranslateClient(deepl_api_key, use_free)
                    self.fallback_mode = True
                    print(f"Using DeepL API ({'Free' if use_free else 'Pro'} tier)")
                    return
                except Exception as e:
                    print(f"DeepL API setup failed: {e}")
            
            # If no DeepL API key, try googletrans as fallback
            try:
                from googletrans import Translator as GoogleTranslator
                self.translator = GoogleTranslator()
                self.fallback_mode = True
                print("Using googletrans as fallback (DeepL API key not configured)")
                return
            except ImportError:
                pass
            
            # No translation service available
            raise Exception("No translation service available")
            
        except Exception as e:
            print(f"Error setting up fallback translator: {e}")
            messagebox.showerror(
                "Translation Service Error",
                "No translation service available. Please either:\n\n"
                "1. Set up Google Cloud Translation API key\n\n"
                "2. Get a DeepL API key (free tier available):\n"
                "   https://www.deepl.com/pro-api\n\n"
                "3. Install googletrans: pip install googletrans==4.0.0-rc1"
            )
            self.translator = None
        
    def create_gui(self):
        """Create the modern control panel using CustomTkinter"""
        self.root = ctk.CTk()
        self.root.title("Polyglot v1")
        self.root.geometry("450x600")
        self.root.resizable(False, True)
        
        # Configure grid weights
        self.root.grid_columnconfigure(0, weight=1)
        
        # Header frame
        header_frame = ctk.CTkFrame(self.root, corner_radius=10)
        header_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        header_frame.grid_columnconfigure(0, weight=1)
        
        # Title
        title_label = ctk.CTkLabel(
            header_frame,
            text="🌏 Polyglot v1",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title_label.grid(row=0, column=0, padx=20, pady=15)
        
        # Settings frame
        settings_frame = ctk.CTkFrame(self.root, corner_radius=10)
        settings_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        settings_frame.grid_columnconfigure(1, weight=1)
        
        # Always on top toggle
        self.always_on_top = ctk.BooleanVar(value=True)
        always_on_top_switch = ctk.CTkSwitch(
            settings_frame,
            text="Keep window on top",
            variable=self.always_on_top,
            command=self.toggle_always_on_top,
            font=ctk.CTkFont(size=12)
        )
        always_on_top_switch.grid(row=0, column=0, columnspan=2, padx=20, pady=(15, 10), sticky="w")
        
        # Language selection
        lang_label = ctk.CTkLabel(
            settings_frame,
            text="Translate to:",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        lang_label.grid(row=1, column=0, padx=(20, 10), pady=10, sticky="w")
        
        self.target_lang = ctk.StringVar(value="es")
        languages = [
            "Spanish", "French", "German", "Italian", "Portuguese",
            "Russian", "Japanese", "Korean", "Chinese (Simplified)",
            "Chinese (Traditional)", "Arabic", "Hindi", "English"
        ]
        
        self.lang_menu = ctk.CTkComboBox(
            settings_frame,
            values=languages,
            command=self.on_lang_change,
            font=ctk.CTkFont(size=12),
            dropdown_font=ctk.CTkFont(size=11),
            width=200
        )
        self.lang_menu.grid(row=1, column=1, padx=(10, 20), pady=10, sticky="ew")
        self.lang_menu.set("Spanish")
        
        # DeepL API configuration
        deepl_frame = ctk.CTkFrame(settings_frame, corner_radius=8)
        deepl_frame.grid(row=2, column=0, columnspan=2, padx=20, pady=10, sticky="ew")
        deepl_frame.grid_columnconfigure(1, weight=1)
        
        deepl_label = ctk.CTkLabel(
            deepl_frame,
            text="DeepL API Key:",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        deepl_label.grid(row=0, column=0, padx=(15, 10), pady=10, sticky="w")
        
        self.deepl_key = ctk.StringVar(value=CONFIG.get("deepl_api_key", ""))
        self.deepl_entry = ctk.CTkEntry(
            deepl_frame,
            textvariable=self.deepl_key,
            placeholder_text="Enter DeepL API key (optional)",
            font=ctk.CTkFont(size=11),
            width=200,
            show="*"
        )
        self.deepl_entry.grid(row=0, column=1, padx=(10, 15), pady=10, sticky="ew")
        
        # Test API key button
        test_btn = ctk.CTkButton(
            deepl_frame,
            text="Test",
            command=self.test_deepl_connection,
            width=60,
            height=28,
            font=ctk.CTkFont(size=10)
        )
        test_btn.grid(row=0, column=2, padx=(0, 15), pady=10)
        
        # Info label for DeepL
        deepl_info = ctk.CTkLabel(
            deepl_frame,
            text="Get free API key at: deepl.com/pro-api (500k chars/month free)",
            font=ctk.CTkFont(size=9),
            text_color=("gray60", "gray40")
        )
        deepl_info.grid(row=1, column=0, columnspan=3, padx=15, pady=(0, 10), sticky="w")
        
        # Control buttons frame
        controls_frame = ctk.CTkFrame(self.root, corner_radius=10)
        controls_frame.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        controls_frame.grid_columnconfigure(0, weight=1)
        
        # Main action button
        self.select_button = ctk.CTkButton(
            controls_frame,
            text="🎯 Select Region to Translate",
            command=self.select_region,
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40,
            corner_radius=8
        )
        self.select_button.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        
        # Hotkey label
        hotkey_label = ctk.CTkLabel(
            controls_frame,
            text="Hotkey: Ctrl+Shift+T",
            font=ctk.CTkFont(size=11),
            text_color=("gray70", "gray50")
        )
        hotkey_label.grid(row=1, column=0, padx=20, pady=(0, 10))
        
        # Clear button
        clear_button = ctk.CTkButton(
            controls_frame,
            text="🗑️ Clear All Translations",
            command=self.overlay.clear_all,
            font=ctk.CTkFont(size=12),
            height=35,
            fg_color="transparent",
            border_width=2,
            text_color=("gray10", "#DCE4EE"),
            corner_radius=8
        )
        clear_button.grid(row=2, column=0, padx=20, pady=(0, 15), sticky="ew")
        
        # Clear hotkey label
        clear_hotkey_label = ctk.CTkLabel(
            controls_frame,
            text="Hotkey: Ctrl+Shift+C",
            font=ctk.CTkFont(size=11),
            text_color=("gray70", "gray50")
        )
        clear_hotkey_label.grid(row=3, column=0, padx=20, pady=(0, 15))
        
        # Status frame
        status_frame = ctk.CTkFrame(self.root, corner_radius=10)
        status_frame.grid(row=3, column=0, padx=20, pady=10, sticky="ew")
        
        # Status indicator
        self.status_label = ctk.CTkLabel(
            status_frame,
            text="🟢 Ready",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.status_label.grid(row=0, column=0, padx=20, pady=15)
        
        # Active regions frame
        regions_header_frame = ctk.CTkFrame(self.root, corner_radius=10)
        regions_header_frame.grid(row=4, column=0, padx=20, pady=10, sticky="ew")
        
        regions_title = ctk.CTkLabel(
            regions_header_frame,
            text="📍 Active Translation Regions",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        regions_title.grid(row=0, column=0, padx=20, pady=15)
        
        # Scrollable frame for regions
        self.regions_scroll = ctk.CTkScrollableFrame(
            self.root,
            corner_radius=10,
            height=150
        )
        self.regions_scroll.grid(row=5, column=0, padx=20, pady=10, sticky="ew")
        self.regions_scroll.grid_columnconfigure(0, weight=1)
        
        # Instructions frame
        instructions_frame = ctk.CTkFrame(self.root, corner_radius=10)
        instructions_frame.grid(row=6, column=0, padx=20, pady=(10, 20), sticky="ew")
        
        instructions_title = ctk.CTkLabel(
            instructions_frame,
            text="📋 How to Use",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        instructions_title.grid(row=0, column=0, padx=20, pady=(15, 5), sticky="w")
        
        instructions_text = [
            "1. Click 'Select Region' or press Ctrl+Shift+T",
            "2. Drag to select text area on screen",
            "3. Translation appears automatically over text",
            "4. Translations update as content changes",
            "5. Use Ctrl+Shift+C to clear all overlays",
            "",
            "🔑 For best quality, get a free DeepL API key:",
            "   deepl.com/pro-api (500k chars/month free)"
        ]
        
        for i, instruction in enumerate(instructions_text):
            inst_label = ctk.CTkLabel(
                instructions_frame,
                text=instruction,
                font=ctk.CTkFont(size=11),
                text_color=("gray70", "gray50"),
                anchor="w"
            )
            inst_label.grid(row=i+1, column=0, padx=20, pady=2, sticky="w")
        
        # Add some bottom padding
        ctk.CTkLabel(instructions_frame, text="").grid(row=len(instructions_text)+1, column=0, pady=5)
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.toggle_always_on_top()
        
    def test_deepl_connection(self):
        """Test connection to DeepL API"""
        api_key = self.deepl_key.get().strip()
        if not api_key:
            messagebox.showwarning("Missing API Key", "Please enter a DeepL API key")
            return
        
        try:
            import requests
            
            # Determine API endpoint based on key type
            use_free = api_key.endswith(':fx')
            base_url = "https://api-free.deepl.com/v2" if use_free else "https://api.deepl.com/v2"
            
            headers = {'Authorization': f'DeepL-Auth-Key {api_key}'}
            response = requests.get(f"{base_url}/usage", headers=headers, timeout=10)
            
            if response.status_code == 200:
                usage_data = response.json()
                char_count = usage_data.get('character_count', 0)
                char_limit = usage_data.get('character_limit', 'unlimited')
                
                tier = "Free" if use_free else "Pro"
                messagebox.showinfo(
                    "DeepL Connection Successful", 
                    f"✅ Connected to DeepL API!\n\n"
                    f"Tier: {tier}\n"
                    f"Usage: {char_count:,}/{char_limit:,} characters"
                )
                
                # Update the config with the tested key
                CONFIG["deepl_api_key"] = api_key
                
            elif response.status_code == 403:
                messagebox.showerror(
                    "DeepL API Error",
                    "❌ Invalid API key.\n\nPlease check your DeepL API key."
                )
            elif response.status_code == 456:
                messagebox.showerror(
                    "DeepL API Error",
                    "❌ Quota exceeded.\n\nYou've reached your translation limit."
                )
            else:
                messagebox.showerror(
                    "DeepL API Error",
                    f"❌ API returned status {response.status_code}"
                )
        except requests.exceptions.Timeout:
            messagebox.showerror(
                "Connection Failed",
                "❌ Connection timed out.\nPlease check your internet connection."
            )
        except Exception as e:
            messagebox.showerror(
                "Connection Failed",
                f"❌ Error: {str(e)}\n\nGet a free API key at:\nhttps://www.deepl.com/pro-api"
            )
    
    def on_lang_change(self, selection):
        """Handle language selection change"""
        language_map = {
            "Spanish": "es",
            "French": "fr", 
            "German": "de",
            "Italian": "it",
            "Portuguese": "pt",
            "Russian": "ru",
            "Japanese": "ja",
            "Korean": "ko",
            "Chinese (Simplified)": "zh-cn",
            "Chinese (Traditional)": "zh-tw",
            "Arabic": "ar",
            "Hindi": "hi",
            "English": "en"
        }
        self.target_lang.set(language_map.get(selection, "es"))
    
    def toggle_always_on_top(self):
        """Toggle always on top setting"""
        self.root.attributes('-topmost', self.always_on_top.get())
    
    def setup_hotkeys(self):
        """Setup global hotkeys"""
        def on_hotkey():
            self.root.after(0, self.select_region)
        
        def on_clear():
            self.root.after(0, self.overlay.clear_all)
        
        # Start keyboard listener in background
        self.hotkey_listener = keyboard.GlobalHotKeys({
            '<ctrl>+<shift>+t': on_hotkey,
            '<ctrl>+<shift>+c': on_clear
        })
        self.hotkey_listener.start()
    
    def select_region(self):
        """Start region selection"""
        self.root.withdraw()  # Hide main window
        
        def on_region_selected(region):
            self.root.deiconify()  # Show main window again
            self.add_monitoring_region(region)
        
        selector = RegionSelector(on_region_selected)
        selector.start_selection()
    
    def add_monitoring_region(self, region):
        """Add a region to monitor for changes"""
        region_id = len(self.monitoring_regions)
        region_data = {
            'id': region_id,
            'bounds': region,
            'last_text': '',
            'last_translation': '',
            'overlay': None
        }
        
        self.monitoring_regions.append(region_data)
        
        # Add to UI with modern styling
        region_frame = ctk.CTkFrame(self.regions_scroll, corner_radius=8)
        region_frame.grid(row=len(self.monitoring_regions)-1, column=0, padx=10, pady=5, sticky="ew")
        region_frame.grid_columnconfigure(0, weight=1)
        
        # Region info
        region_info = ctk.CTkLabel(
            region_frame,
            text=f"📍 Region {region_id + 1}: {region[2]-region[0]}×{region[3]-region[1]}px",
            font=ctk.CTkFont(size=11),
            anchor="w"
        )
        region_info.grid(row=0, column=0, padx=15, pady=10, sticky="w")
        
        # Remove button
        remove_btn = ctk.CTkButton(
            region_frame,
            text="❌",
            command=lambda: self.remove_region(region_id),
            width=30,
            height=25,
            font=ctk.CTkFont(size=10),
            fg_color="transparent",
            text_color=("gray70", "gray50"),
            hover_color=("gray80", "gray40")
        )
        remove_btn.grid(row=0, column=1, padx=15, pady=10)
        
        region_data['frame'] = region_frame
        
        # Start monitoring if not already active
        if not self.monitoring_active:
            self.start_monitoring()
        
        # Perform initial translation
        self.process_region(region_data)
    
    def remove_region(self, region_id):
        """Remove a monitoring region"""
        for i, region in enumerate(self.monitoring_regions):
            if region['id'] == region_id:
                # Remove overlay
                if region['overlay']:
                    self.overlay.remove_overlay(region['overlay'])
                
                # Remove from UI
                if 'frame' in region:
                    region['frame'].destroy()
                
                # Remove from list
                self.monitoring_regions.pop(i)
                break
        
        # Stop monitoring if no regions left
        if not self.monitoring_regions:
            self.stop_monitoring()
    
    def start_monitoring(self):
        """Start monitoring all regions for changes"""
        self.monitoring_active = True
        self.status_label.configure(text="🔄 Monitoring")
        
        def monitor_loop():
            while self.monitoring_active:
                for region in self.monitoring_regions:
                    self.process_region(region)
                
                time.sleep(CONFIG["update_interval"] / 1000.0)
        
        self.monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop monitoring"""
        self.monitoring_active = False
        self.status_label.configure(text="🟢 Ready")
    
    def process_region(self, region_data):
        """Process a single region - capture, OCR, translate"""
        try:
            # Capture region
            x1, y1, x2, y2 = region_data['bounds']
            screenshot = pyautogui.screenshot(region=(x1, y1, x2-x1, y2-y1))
            
            # Check if content changed using perceptual hash
            img_array = np.array(screenshot)
            img_hash = self.compute_image_hash(img_array)
            
            if region_data['id'] in self.previous_hashes:
                if img_hash == self.previous_hashes[region_data['id']]:
                    return  # No change
            
            self.previous_hashes[region_data['id']] = img_hash
            
            # Preprocess image for better OCR
            processed_img = self.preprocess_image(screenshot)
            
            # Extract text with data about positions
            ocr_data = pytesseract.image_to_data(processed_img, output_type=pytesseract.Output.DICT)
            
            # Combine all text with better filtering
            text_blocks = []
            for i in range(len(ocr_data['level'])):
                conf = int(ocr_data['conf'][i])
                if conf > CONFIG.get('min_confidence', 30):  # Use configurable confidence threshold
                    text = ocr_data['text'][i].strip()
                    if text and len(text) > 1:  # Skip single characters
                        text_blocks.append(text)
            
            # Join text blocks with spaces and clean up
            text = ' '.join(text_blocks)
            # Remove extra whitespace
            text = ' '.join(text.split())
            # Remove any null characters that might cause issues
            text = text.replace('\x00', '').replace('\r', ' ').replace('\n', ' ')
            
            if text and text != region_data['last_text']:
                region_data['last_text'] = text
                
                # Skip if text is too short or just numbers/symbols
                if len(text) < 2 or text.isdigit():
                    return
                
                # Check cache first
                cached = self.cache.get(text, 'auto', self.target_lang.get())
                if cached:
                    translation = cached
                else:
                    # Translate
                    try:
                        # Handle empty text
                        if len(text.strip()) == 0:
                            return
                        
                        if self.translator:
                            if hasattr(self, 'fallback_mode') and self.fallback_mode:
                                # Using googletrans fallback
                                result = self.translator.translate(text, dest=self.target_lang.get())
                                translation = result.text
                            else:
                                # Using Google Cloud Translation
                                result = self.translator.translate(
                                    text, 
                                    target_language=self.target_lang.get()
                                )
                                translation = result['translatedText']
                            
                            self.cache.put(text, translation, 'auto', self.target_lang.get())
                        else:
                            translation = "[Translation service not available]"
                    except Exception as e:
                        print(f"Translation error: {e}")
                        translation = text  # Show original text if translation fails
                
                region_data['last_translation'] = translation
                
                # Update overlay
                if region_data['overlay']:
                    self.overlay.remove_overlay(region_data['overlay'])
                
                # Create overlay directly over the original text
                region_data['overlay'] = self.overlay.show_translation(
                    x1, y1, x2-x1, y2-y1,
                    text, translation
                )
                
        except Exception as e:
            print(f"Error processing region: {e}")
    
    def preprocess_image(self, image):
        """Preprocess image for better OCR accuracy"""
        # Convert PIL image to OpenCV format
        img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Apply thresholding to get better contrast
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Denoise
        denoised = cv2.medianBlur(thresh, 1)
        
        # Convert back to PIL Image
        return Image.fromarray(denoised)
    
    def compute_image_hash(self, img_array):
        """Compute perceptual hash of image for change detection"""
        # Resize to 8x8 and convert to grayscale
        img = cv2.resize(img_array, (8, 8))
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        
        # Compute mean
        mean = gray.mean()
        
        # Create hash based on whether pixels are above or below mean
        hash_str = ''.join(['1' if pixel > mean else '0' for pixel in gray.flatten()])
        
        return hash_str
    
    def on_closing(self):
        """Clean up when closing the application"""
        self.monitoring_active = False
        self.overlay.clear_all()
        if hasattr(self, 'hotkey_listener'):
            self.hotkey_listener.stop()
        self.root.destroy()
    
    def run(self):
        """Start the application"""
        self.root.mainloop()

def main():
    """Entry point"""
    # Check dependencies
    try:
        import pytesseract
        import cv2
        import numpy
        import customtkinter as ctk
    except ImportError as e:
        print(f"Missing dependencies. Please install required packages:")
        print("pip install pyautogui pillow pytesseract pynput opencv-python numpy customtkinter")
        print("For Google Cloud Translation:")
        print("pip install google-cloud-translate")
        print("For LibreTranslate (local translation):")
        print("pip install libretranslate")
        print("For click-through overlays on Windows:")
        print("pip install pywin32")
        print(f"Error: {e}")
        return
    
    # Check Tesseract installation
    try:
        pytesseract.get_tesseract_version()
    except Exception:
        messagebox.showwarning(
            "Tesseract Not Found",
            "Tesseract OCR is not installed or not in PATH.\n\n"
            "Please install from:\n"
            "https://github.com/UB-Mannheim/tesseract/wiki\n\n"
            "Then update the tesseract_path in CONFIG."
        )
    
    # Ask for API keys if not set
    missing_keys = []
    if GOOGLE_CLOUD_AVAILABLE and not CONFIG.get("google_cloud_api_key") and not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        missing_keys.append("Google Cloud")
    if not CONFIG.get("deepl_api_key") and not os.environ.get("DEEPL_API_KEY"):
        missing_keys.append("DeepL")
    
    if missing_keys:
        # Create a dialog for API key input
        root = ctk.CTk()
        root.withdraw()  # Hide the main window
        
        dialog = ctk.CTkToplevel(root)
        dialog.title("API Key Configuration")
        dialog.geometry("600x400")
        dialog.resizable(False, False)
        dialog.transient(root)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        api_key_results = {"google": None, "deepl": None}
        
        # Dialog content
        title_label = ctk.CTkLabel(
            dialog,
            text="🔑 Translation API Configuration",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_label.pack(pady=20)
        
        info_label = ctk.CTkLabel(
            dialog,
            text="Configure translation services for best quality.\nLeave empty to use free fallback options.",
            font=ctk.CTkFont(size=13)
        )
        info_label.pack(pady=10)
        
        # API key frame
        keys_frame = ctk.CTkFrame(dialog)
        keys_frame.pack(padx=40, pady=20, fill="x")
        
        # DeepL API key
        deepl_label = ctk.CTkLabel(
            keys_frame,
            text="DeepL API Key (Recommended - Free tier: 500k chars/month):",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        deepl_label.pack(pady=(20, 5), anchor="w")
        
        deepl_entry = ctk.CTkEntry(
            keys_frame,
            placeholder_text="Enter DeepL API key (get free at deepl.com/pro-api)",
            width=500,
            height=35,
            show="*"
        )
        deepl_entry.pack(pady=(0, 15), padx=20, fill="x")
        
        # Google Cloud API key (if available)
        if "Google Cloud" in missing_keys:
            google_label = ctk.CTkLabel(
                keys_frame,
                text="Google Cloud Translation API Key (Optional):",
                font=ctk.CTkFont(size=12, weight="bold")
            )
            google_label.pack(pady=(10, 5), anchor="w")
            
            google_entry = ctk.CTkEntry(
                keys_frame,
                placeholder_text="Enter Google Cloud API key (optional)",
                width=500,
                height=35,
                show="*"
            )
            google_entry.pack(pady=(0, 20), padx=20, fill="x")
        else:
            google_entry = None
        
        def on_ok():
            api_key_results["deepl"] = deepl_entry.get()
            if google_entry:
                api_key_results["google"] = google_entry.get()
            dialog.destroy()
            root.quit()
        
        def on_skip():
            dialog.destroy()
            root.quit()
        
        button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        button_frame.pack(pady=20)
        
        ok_button = ctk.CTkButton(
            button_frame,
            text="Save Keys",
            command=on_ok,
            width=140,
            height=35
        )
        ok_button.pack(side="left", padx=10)
        
        skip_button = ctk.CTkButton(
            button_frame,
            text="Skip (Use Fallback)",
            command=on_skip,
            width=140,
            height=35,
            fg_color="gray",
            hover_color="darkgray"
        )
        skip_button.pack(side="left", padx=10)
        
        # Bind Enter key to OK
        deepl_entry.bind("<Return>", lambda e: on_ok())
        if google_entry:
            google_entry.bind("<Return>", lambda e: on_ok())
        
        root.mainloop()
        
        # Save the entered keys
        if api_key_results["deepl"]:
            CONFIG["deepl_api_key"] = api_key_results["deepl"]
        if api_key_results["google"]:
            CONFIG["google_cloud_api_key"] = api_key_results["google"]
        
        root.destroy() #Cloud API key if not set
    if GOOGLE_CLOUD_AVAILABLE and not CONFIG.get("google_cloud_api_key") and not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        # Create a simple dialog for API key input
        root = ctk.CTk()
        root.withdraw()  # Hide the main window
        
        dialog = ctk.CTkToplevel(root)
        dialog.title("Google Cloud API Key")
        dialog.geometry("500x300")
        dialog.resizable(False, False)
        dialog.transient(root)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        api_key_result = {"key": None}
        
        # Dialog content
        title_label = ctk.CTkLabel(
            dialog,
            text="🔑 Google Cloud Translation API Key",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        title_label.pack(pady=20)
        
        info_label = ctk.CTkLabel(
            dialog,
            text="Enter your Google Cloud Translation API key (optional):\nLeave empty to use the fallback translation service.",
            font=ctk.CTkFont(size=12)
        )
        info_label.pack(pady=10)
        
        api_key_entry = ctk.CTkEntry(
            dialog,
            placeholder_text="Enter API key here...",
            width=400,
            height=35,
            show="*"
        )
        api_key_entry.pack(pady=20)
        
        def on_ok():
            api_key_result["key"] = api_key_entry.get()
            dialog.destroy()
            root.quit()
        
        def on_skip():
            api_key_result["key"] = ""
            dialog.destroy()
            root.quit()
        
        button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        button_frame.pack(pady=20)
        
        ok_button = ctk.CTkButton(
            button_frame,
            text="Use API Key",
            command=on_ok,
            width=120
        )
        ok_button.pack(side="left", padx=10)
        
        skip_button = ctk.CTkButton(
            button_frame,
            text="Skip",
            command=on_skip,
            width=120,
            fg_color="gray",
            hover_color="darkgray"
        )
        skip_button.pack(side="left", padx=10)
        
        # Bind Enter key to OK
        api_key_entry.bind("<Return>", lambda e: on_ok())
        
        root.mainloop()
        
        if api_key_result["key"]:
            CONFIG["google_cloud_api_key"] = api_key_result["key"]
        
        root.destroy()
    
    # Start application
    app = ScreenTranslator()
    app.run()

if __name__ == "__main__":
    main()