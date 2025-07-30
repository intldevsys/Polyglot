<img width="1556" height="701" alt="image" src="https://github.com/user-attachments/assets/b0d573f7-ce8c-4073-a0fe-d733e5d786f0" />


# Polyglot
Translate anything on your screen in real-time without the need for a web browser. Can be used with a local googletrans libary or Google's Cloud Translation API (recommended)

## Key Features

1. **Region Selection**: Click and drag to select any area on screen
2. **Real-time Monitoring**: Automatically detects when text changes in selected regions
3. **Smart Change Detection**: Uses perceptual hashing to only process when content actually changes
4. **Translation Overlay**: Translation window will overlay the original text
5. **Multi-region Support**: Monitor multiple areas simultaneously
6. **Caching**: Stores translations to avoid repeated API calls
7. **Global Hotkeys**: 
   - `Ctrl+Shift+T` - Start region selection
   - `Ctrl+Shift+C` - Clear all translations


## Setup Instructions

1. **Install Python dependencies**:
```bash
pip install pyautogui pillow pytesseract googletrans==4.0.0-rc1 pynput opencv-python numpy
```

2. **Install Tesseract OCR**:
   - Windows: Download from [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki)
   - macOS: `brew install tesseract`
   - Linux: `sudo apt-get install tesseract-ocr`

3. **Update the Tesseract path** in the CONFIG section if needed (line 32)

4. **Run the application**:
```bash
python desktop_translator.py
```

## How It Works

1. The app creates a control panel where you can:
   - Select target language
   - Add/remove monitoring regions
   - View active regions

2. When you select a region:
   - A transparent overlay appears for selection
   - The app captures that region every 500ms
   - Uses perceptual hashing to detect changes
   - Only processes OCR/translation when content changes


## Advanced Features

- **Image Preprocessing**: Enhances text for better OCR accuracy
- **LRU Cache**: Stores up to 1000 translations
- **Multi-threading**: Monitoring runs in background thread
- **Error Handling**: Gracefully handles OCR and translation errors

## Customization Options

You can modify the CONFIG dictionary to:
- Change update frequency
- Adjust overlay appearance (colors, opacity, font size)
- Set different default language
- Modify cache size
