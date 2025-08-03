<img width="1796" height="856" alt="image" src="https://github.com/user-attachments/assets/6db87f16-7484-4828-bf17-f1d69ccfec0e" />

# 🌐 Polyglot v1.0 - Real-time Desktop Translation

A powerful desktop application that provides real-time translation of on-screen text with a modern dark UI. Select any region on your screen and get instant, high-quality translations overlaid directly over the original text.

##  Features

- ** Real-time translation** of any on-screen text
- ** Click-and-drag region selection** for targeted translation
- ** Automatic content monitoring** with change detection
- ** Modern dark UI** built with CustomTkinter
- ** Multiple translation services** with intelligent fallback
- ** High-quality translations** powered by DeepL and Google Cloud
- **  Global hotkeys** for quick access
- ** Translation caching** for improved performance
- **  Click-through overlays** that don't interfere with your workflow

## Translation Services

### Primary Services
- ** Google Cloud Translation** - Premium accuracy with extensive language support
- ** DeepL API** - Superior quality for European languages (500k chars/month free)

### Fallback Option
- ** googletrans** - Free backup service when APIs are unavailable

## 📋 Requirements

### Python Dependencies
```bash
pip install pyautogui pillow pytesseract pynput opencv-python numpy customtkinter requests
```

### Optional Dependencies
```bash
# For Google Cloud Translation
pip install google-cloud-translate

# For Windows click-through overlays
pip install pywin32

# For fallback translation
pip install googletrans==4.0.0-rc1
```

### System Requirements
- **Tesseract OCR**: Download from [GitHub](https://github.com/UB-Mannheim/tesseract/wiki)
- **Python 3.7+**
- **Windows** (Linux/Mac support with minor modifications)

## 🛠️ Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/desktop-translator.git
   cd desktop-translator
   ```

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Tesseract OCR**
   - Download from: https://github.com/UB-Mannheim/tesseract/wiki
   - Update `tesseract_path` in the script if not in PATH

4. **Configure API keys** (optional but recommended)
   ```python
   # In the CONFIG section of the script
   CONFIG = {
       "deepl_api_key": "your-deepl-api-key-here",  # Get free at deepl.com/pro-api
       "google_cloud_api_key": "your-google-api-key-here",  # Optional
       # ... other settings
   }
   ```

## API Key Setup

### DeepL API (Recommended)
1. Visit [DeepL Pro API](https://www.deepl.com/pro-api)
2. Sign up for a free account
3. Get your API key (500,000 characters/month free)
4. Add it to the script or use the built-in configuration dialog

### Google Cloud Translation (Optional)
1. Visit [Google Cloud Console](https://console.cloud.google.com/)
2. Enable the Translation API
3. Create an API key
4. Add it to the script configuration

## 🎮 Usage

### Basic Operation
1. **Run the application**
   ```bash
   python desktop_translator.py
   ```

2. **Select a region**
   - Click "Select Region to Translate" or press `Ctrl+Shift+T`
   - Drag to select the area containing text you want to translate

3. **View translations**
   - Translations appear automatically as overlays
   - Overlays update when the underlying text changes

### Hotkeys
- `Ctrl+Shift+T` - Select new translation region
- `Ctrl+Shift+C` - Clear all translation overlays

### Language Support
The application supports translation to:
- Spanish, French, German, Italian, Portuguese
- Russian, Japanese, Korean, Chinese (Simplified/Traditional)
- Arabic, Hindi, Dutch, Polish, Swedish, Danish
- Finnish, Norwegian, Czech, Hungarian, Romanian
- And many more depending on the translation service

##  Configuration

### Basic Settings
```python
CONFIG = {
    "update_interval": 500,        # Translation update frequency (ms)
    "cache_size": 1000,           # Number of cached translations
    "min_confidence": 30,         # Minimum OCR confidence threshold
    "overlay_opacity": 0.95,      # Translation overlay transparency
    "font_size": 13,             # Overlay text size
}
```

### Advanced Settings
- **OCR Language**: Modify Tesseract language settings for better accuracy
- **Overlay Styling**: Customize colors, fonts, and positioning
- **Performance Tuning**: Adjust cache size and update intervals

## Troubleshooting

### Common Issues

**Tesseract not found**
```bash
# Update the path in CONFIG
"tesseract_path": r"C:\Program Files\Tesseract-OCR\tesseract.exe"
```

**Poor OCR accuracy**
- Ensure text is clear and well-lit
- Try adjusting the `min_confidence` setting
- Select smaller regions with less visual noise

**Translation not working**
- Check your internet connection
- Verify API keys are correct
- Test connections using the built-in test buttons

**Overlays not click-through**
- Install `pywin32`: `pip install pywin32`
- Run as administrator if needed

### Development Setup
1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and test thoroughly
4. Submit a pull request with a clear description


## Use Cases

- **Language Learning** - Translate foreign language content in real-time
- **International Business** - Understand foreign language documents and websites
- ** Gaming** - Translate in-game text in foreign language games
- **Research** - Read academic papers and documents in other languages
- **Professional** - Handle multilingual customer support and documentation

## Privacy

- All translations are processed through the selected APIs
- No text data is stored permanently by the application
- Local caching is used only for performance optimization
- API keys are stored locally and never transmitted elsewhere

