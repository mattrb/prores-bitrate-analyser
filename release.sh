#!/bin/bash
# ProRes Analyser - Automated Release Script
# Creates DMG and publishes to GitHub

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_step() {
    echo -e "${BLUE}▶${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Check if version provided
if [ -z "$1" ]; then
    print_error "Usage: ./release.sh <version> [release notes]"
    echo "Example: ./release.sh 1.1.0"
    echo "         ./release.sh 1.1.0 'Performance improvements'"
    exit 1
fi

VERSION=$1
RELEASE_NOTES=${2:-"Release v${VERSION}"}
DMG_NAME="ProResAnalyser-v${VERSION}.dmg"
APP_NAME="ProRes Bitrate Analyser"

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  ProRes Bitrate Analyser - Automated Release               ║"
echo "║  Version: ${VERSION}                                       ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Step 1: Check if we're in the right directory
print_step "Checking project directory..."
if [ ! -f "prores_analyser.py" ]; then
    print_error "prores_analyser.py not found!"
    echo "Make sure you're in the ProRes Analyser directory"
    exit 1
fi
print_success "Found prores_analyser.py"

# Step 2: Check for uncommitted changes
print_step "Checking for uncommitted changes..."
if [[ -n $(git status -s) ]]; then
    print_warning "You have uncommitted changes:"
    git status -s
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_error "Aborted"
        exit 1
    fi
fi
print_success "Git status clean (or continuing with changes)"

# Step 3: Activate virtual environment
print_step "Activating virtual environment..."
if [ ! -d "venv" ]; then
    print_error "Virtual environment not found!"
    echo "Create one with: python3 -m venv venv"
    exit 1
fi
source venv/bin/activate
print_success "Virtual environment activated"

# Step 4: Check dependencies
print_step "Checking dependencies..."
if ! pip show pyinstaller > /dev/null 2>&1; then
    print_warning "PyInstaller not found, installing..."
    pip install pyinstaller
fi
# Experimental check: see if ffprobe is even on your system
if ! command -v ffprobe &> /dev/null; then
    print_warning "ffprobe not found in PATH. The app might not work locally."
fi
print_success "Dependencies OK"

# Step 5: Clean previous builds
print_step "Cleaning previous builds..."

# 1. Close any Finder windows looking at the project to release the 'lock'
osascript -e "tell application \"Finder\" to close (every window whose target is (POSIX file \"$(pwd)\" as alias))" 2>/dev/null || true

# 2. Kill the app if it's currently running
pkill -f "$APP_NAME" || true

# 3. Force remove with a 'nuclear' option
# We use -rf. If it fails, we wait 1 second and try once more.
rm -rf build dist || (sleep 1 && rm -rf build dist)

# 4. Final sweep for spec files
rm -f *.spec

print_success "Build directories cleaned"

# Step 6: Build the application
print_step "Building application with PyInstaller..."
# Using --noconfirm ensures it doesn't stop to ask if it can overwrite files
pyinstaller --noconfirm --windowed \
  --name "$APP_NAME" \
  --osx-bundle-identifier "com.local.proresanalyser" \
  --hidden-import "PyQt6" \
  --collect-all "PyQt6" \
  --clean \
  prores_analyser.py > build.log 2>&1

# Note: We use --noconfirm and handle the name carefully to avoid pathing errors
pyinstaller --noconfirm --windowed \
  --name "$APP_NAME" \
  --icon "AppIcon.icns" \
  --osx-bundle-identifier "com.local.proresanalyser" \
  --hidden-import "PyQt6" \
  --collect-all "PyQt6" \
  --add-binary "/opt/homebrew/bin/ffprobe:." \
  --clean \
  prores_analyser.py > build.log 2>&1

if [ $? -ne 0 ]; then
    print_error "Build failed! Check build.log for details"
    tail -n 20 build.log
    exit 1
fi
print_success "Application built successfully"

# Step 7: Test the application (Modified for reliability)
print_step "Testing application..."
echo "Opening app for 5 seconds..."
# Use -a to ensure we open the specific path
open -a "./dist/$APP_NAME.app"
APP_PID=$!
sleep 5

# Check if the process is running by name since 'open' returns quickly
if pgrep -f "$APP_NAME" > /dev/null; then
    print_success "App appears to be running"
    pkill -f "$APP_NAME"
else
    print_warning "App not found in process list - check build.log"
fi

# ... [Keep the rest of your DMG and GitHub Release logic] ...

# Step 8: Create DMG
print_step "Creating DMG installer..."
if [ -f "$DMG_NAME" ]; then
    rm "$DMG_NAME"
fi

hdiutil create -volname "$APP_NAME" \
  -srcfolder "dist/$APP_NAME.app" \
  -ov -format UDZO \
  "$DMG_NAME" > /dev/null 2>&1

if [ $? -ne 0 ]; then
    print_error "DMG creation failed"
    exit 1
fi

DMG_SIZE=$(du -h "$DMG_NAME" | cut -f1)
print_success "DMG created: $DMG_NAME ($DMG_SIZE)"

# Step 9: Git tag
print_step "Creating git tag v${VERSION}..."
if git rev-parse "v${VERSION}" >/dev/null 2>&1; then
    print_warning "Tag v${VERSION} already exists"
    read -p "Delete and recreate? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git tag -d "v${VERSION}"
        git push origin ":refs/tags/v${VERSION}" 2>/dev/null || true
    else
        print_error "Aborted - tag already exists"
        exit 1
    fi
fi

git tag -a "v${VERSION}" -m "Release v${VERSION}"
git push origin "v${VERSION}"
print_success "Git tag created and pushed"

# Step 9.5: Get previous tag for changelog link
print_step "Calculating changelog range..."
PREVIOUS_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")

if [ -z "$PREVIOUS_TAG" ]; then
    CHANGELOG_URL="First release"
else
    # Create the comparison link (e.g., v1.0.0...v1.1.0)
    CHANGELOG_URL="https://github.com/mattrb/prores-bitrate-analyser/compare/${PREVIOUS_TAG}...v${VERSION}"
fi

# Step 10: Create GitHub release
print_step "Creating GitHub release..."

# Check if gh is installed
if ! command -v gh &> /dev/null; then
    print_error "GitHub CLI (gh) not found"
    echo "Install with: brew install gh"
    echo ""
    echo "Manual release steps:"
    echo "1. Go to: https://github.com/mattrb/prores-bitrate-analyser/releases/new"
    echo "2. Tag: v${VERSION}"
    echo "3. Upload: $DMG_NAME"
    exit 1
fi

# Create release notes
cat > release_notes.tmp << EOF
## What's New in v${VERSION}

${RELEASE_NOTES}

### Installation

1. Download \`${DMG_NAME}\` below
2. Mount the DMG
3. Drag **${APP_NAME}.app** to Applications
4. Install FFmpeg if needed: \`brew install ffmpeg\`
5. Right-click app and choose "Open" (first time only)

### System Requirements
- macOS 10.13 or later
- FFmpeg (install via Homebrew)

### Known Issues
- App takes ~8 seconds to load on first launch (PyInstaller initialization)
- Requires right-click → Open on first launch (unsigned app)

---

**Full changelog**: https://github.com/mattrb/prores-bitrate-analyser/compare/v$((${VERSION%.*}.${VERSION##*.}-1))...v${VERSION}
EOF

gh release create "v${VERSION}" \
  "$DMG_NAME" \
  --title "${APP_NAME} v${VERSION}" \
  --notes-file release_notes.tmp

if [ $? -eq 0 ]; then
    print_success "GitHub release published!"
    rm release_notes.tmp
else
    print_error "GitHub release failed"
    echo "Release notes saved to: release_notes.tmp"
    exit 1
fi

# Step 11: Summary
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  Release Complete! 🎉                                      ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Version:  v${VERSION}"
echo "DMG:      ${DMG_NAME} (${DMG_SIZE})"
echo "Release:  https://github.com/mattrb/prores-bitrate-analyser/releases/tag/v${VERSION}"
echo ""
print_success "All done!"

# Cleanup
rm -f build.log

# Optional: Open release page
read -p "Open release page in browser? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    open "https://github.com/mattrb/prores-bitrate-analyzer/releases/tag/v${VERSION}"
fi