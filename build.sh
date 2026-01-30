#!/bin/bash
echo "Building ProRes Bitrate Analyzer..."

# Clean
rm -rf build dist

# Build
python setup.py py2app

# Test
echo "Build complete! Testing..."
open dist/ProRes\ Bitrate\ Analyzer.app

echo "If the app works, create installer with:"
echo "create-dmg --volname 'ProRes Bitrate Analyzer' --window-size 800 400 --app-drop-link 600 185 ProResAnalyzer.dmg dist#!/bin/bash
