# ProRes Bitrate Analyzer

A macOS desktop application for analyzing bitrate variations in ProRes video files.

## Features

- 📊 Interactive bitrate graph showing per-frame and averaged data
- 📈 Detailed statistics (average, peak, minimum bitrate)
- 🎬 I-frame detection and analysis
- 💾 JSON export for further analysis
- 🎨 Dark-themed native interface

## Requirements

- macOS 10.13 or later
- FFmpeg (install via: `brew install ffmpeg`)

## Installation

1. Download the latest release from [Releases](https://github.com/YOUR_USERNAME/prores-bitrate-analyzer/releases)
2. Mount the DMG file
3. Drag ProRes Bitrate Analyzer.app to Applications
4. Install FFmpeg: `brew install ffmpeg`
5. Right-click the app and choose "Open" (first time only)

## Usage

1. Launch the application
2. Click "Select Video File"
3. Choose a ProRes video file (.mov, .mp4, .mxf)
4. Wait for analysis to complete
5. View the bitrate graph and statistics
6. Optionally export data as JSON

## Building from Source
```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/prores-bitrate-analyzer.git
cd prores-bitrate-analyzer

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run application
python prores_analyser.py

# Build standalone app
pyinstaller --windowed \
  --name "ProRes Bitrate Analyzer" \
  --hidden-import=PyQt6 \
  --collect-all PyQt6 \
  prores_analyser.py
```

## License

MIT License - see LICENSE file for details

## Author

Matt RB (https://github.com/mattrb)
