"""
Setup configuration for building ProRes Analyzer as a macOS application
"""
from setuptools import setup

# Main application file
APP = ['prores_analyser.py']

# Additional data files (if any - currently none needed)
DATA_FILES = []

# py2app options
OPTIONS = {
    'argv_emulation': True,  # Allows drag-and-drop onto app icon
    'packages': ['PyQt6', 'matplotlib', 'numpy'],  # Include these packages
    'includes': ['PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets'],
    'excludes': ['tkinter'],  # Don't include tkinter (we don't use it)
    'plist': {
        'CFBundleName': 'ProRes Bitrate Analyzer',
        'CFBundleDisplayName': 'ProRes Bitrate Analyzer',
        'CFBundleIdentifier': 'com.yourname.proresanalyzer',  # Change yourname
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHumanReadableCopyright': '© 2025 Your Name',  # Change this
        'NSHighResolutionCapable': True,  # Support retina displays
    }
}

setup(
    name='ProRes Bitrate Analyzer',
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
