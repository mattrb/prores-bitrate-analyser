#!/bin/bash

# Configuration
VERSION=${1:-"1.0.0"}
APP_NAME="ProRes Bitrate Analyser"
SPEC_FILE="ProResAnalyser.spec"
APP_PATH="dist/${APP_NAME}.app"
DMG_NAME="ProResAnalyser-v${VERSION}.dmg"

echo "🔨 Starting Build for $APP_NAME v$VERSION..."

# 1. Environment Setup
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "✓ Virtual environment activated"
else
    echo "❌ venv not found. Please create it first."
    exit 1
fi

# 2. Clean previous builds
echo "▶ Cleaning previous builds..."
rm -rf build/ dist/ "$DMG_NAME"
echo "✓ Workspace cleared"

# 3. Run PyInstaller
echo "📦 Running PyInstaller..."
pyinstaller --noconfirm "$SPEC_FILE"

if [ $? -ne 0 ]; then
    echo "❌ PyInstaller build failed"
    exit 1
fi

# 4. Slimming (Remove Intel x86_64 architecture for Apple Silicon)
# This reduces the size significantly by keeping only the arm64 slice
echo "✂️  Slimming app bundle (arm64 only)..."
find "$APP_PATH" -type f \( -name "*.so" -o -name "*.dylib" -o -path "*/MacOS/*" \) | while read -r file; do
    if file "$file" | grep -q "Mach-O"; then
        if lipo -info "$file" | grep -q "x86_64"; then
            lipo -thin arm64 "$file" -output "$file" 2>/dev/null
        fi
    fi
done
echo "✓ Slimming complete"

# 5. Test launch
echo "🚀 Performing test launch..."
# Redirecting output to /dev/null prevents 'Broken Pipe' errors in the terminal
open -a "$APP_PATH" > /dev/null 2>&1
sleep 5

# Check if process is running
if pgrep -f "$APP_NAME" > /dev/null; then
    echo "✓ App launched and verified."
    # Kill the test process gracefully
    pkill -f "$APP_NAME"
else
    echo "⚠️  App test launch could not be verified automatically."
    echo "   Check if the icon appears in your dock."
fi

# 6. Create DMG
echo "💿 Creating DMG..."
DMG_TEMP="dmg_temp"
rm -rf "$DMG_TEMP"
mkdir -p "$DMG_TEMP"

cp -r "$APP_PATH" "$DMG_TEMP/"
ln -s /Applications "$DMG_TEMP/Applications"

hdiutil create -volname "$APP_NAME" \
  -srcfolder "$DMG_TEMP" \
  -ov -format UDZO \
  "$DMG_NAME"

rm -rf "$DMG_TEMP"

if [ $? -eq 0 ]; then
    echo "--------------------------------------------------"
    echo "🎉 SUCCESS!"
    echo "App: $APP_PATH"
    echo "DMG: $DMG_NAME"
    ls -lh "$DMG_NAME"
    echo "--------------------------------------------------"
else
    echo "❌ DMG creation failed"
    exit 1
fi