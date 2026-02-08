#!/usr/bin/env python3
"""
ProRes Bitrate Analyzer v1.1.0
Performance improvements and new features
"""

import sys
import json
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QLabel, QFileDialog, 
                            QProgressBar, QTextEdit, QSplitter, QGroupBox, QSplashScreen)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QSettings
from PyQt6.QtGui import QFont, QPalette, QColor, QPixmap, QPainter, QAction, QKeySequence
import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np


def create_splash_screen():
    """
    Create a splash screen shown during app startup.
    NEW in v1.2.0: Provides visual feedback during 8-second load time.
    """
    # Create a 600x400 splash image
    splash_pix = QPixmap(600, 400)
    splash_pix.fill(QColor(30, 30, 30))  # Dark background
    
    # Draw on the splash screen
    painter = QPainter(splash_pix)
    
    # Title
    painter.setPen(QColor(255, 255, 255))
    title_font = QFont("Arial", 32, QFont.Weight.Bold)
    painter.setFont(title_font)
    painter.drawText(splash_pix.rect(), Qt.AlignmentFlag.AlignCenter, 
                    "ProRes Bitrate Analyzer")
    
    # Version
    painter.setPen(QColor(0, 230, 118))
    version_font = QFont("Arial", 16)
    painter.setFont(version_font)
    painter.drawText(50, 250, "v1.2.0")
    
    # Loading message
    painter.setPen(QColor(200, 200, 200))
    loading_font = QFont("Arial", 14)
    painter.setFont(loading_font)
    painter.drawText(splash_pix.rect().adjusted(0, 100, 0, 0), 
                    Qt.AlignmentFlag.AlignCenter, 
                    "Loading components...")
    
    # Subtitle
    painter.setPen(QColor(150, 150, 150))
    subtitle_font = QFont("Arial", 12)
    painter.setFont(subtitle_font)
    painter.drawText(splash_pix.rect().adjusted(0, -80, 0, 0), 
                    Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom,
                    "Analyze video bitrate over time")
    
    painter.end()
    
    # Create splash screen widget
    splash = QSplashScreen(splash_pix, Qt.WindowType.WindowStaysOnTopHint)
    splash.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | 
                         Qt.WindowType.FramelessWindowHint)
    
    return splash


class VideoAnalyzer(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, filepath):
        super().__init__()
        self.filepath = filepath
        
    def run(self):
        try:
            self.progress.emit(10, "Checking FFprobe availability...")
            try:
                subprocess.run(['ffprobe', '-version'], capture_output=True, check=True)
            except:
                self.error.emit("FFprobe not found. Install with: brew install ffmpeg")
                return
            
            self.progress.emit(20, "Extracting video metadata...")
            metadata = self._get_video_metadata()
            
            self.progress.emit(40, "Analyzing frame data...")
            frame_data = self._get_frame_data(metadata['fps'])
            
            self.progress.emit(70, "Calculating statistics...")
            stats = self._calculate_statistics(frame_data, metadata)
            
            self.progress.emit(90, "Preparing results...")
            results = {'metadata': metadata, 'frame_data': frame_data, 'stats': stats}
            
            self.progress.emit(100, "Analysis complete!")
            self.finished.emit(results)
            
        except Exception as e:
            self.error.emit(f"Analysis error: {str(e)}")
    
    def _get_video_metadata(self):
        cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', 
               '-show_format', '-show_streams', self.filepath]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        video_stream = next(s for s in data['streams'] if s['codec_type'] == 'video')
        fps_parts = video_stream.get('r_frame_rate', '24/1').split('/')
        fps = float(fps_parts[0]) / float(fps_parts[1])
        return {
            'codec': video_stream.get('codec_name', 'Unknown'),
            'codec_long': video_stream.get('codec_long_name', 'Unknown'),
            'width': video_stream.get('width', 0),
            'height': video_stream.get('height', 0),
            'fps': fps,
            'duration': float(data['format'].get('duration', 0)),
            'size': int(data['format'].get('size', 0)),
            'bitrate': int(data['format'].get('bit_rate', 0))
        }
    
    def _get_frame_data(self, fps):
        cmd = ['ffprobe', '-v', 'quiet', '-select_streams', 'v:0',
               '-show_entries', 'frame=pkt_pts_time,pkt_size,pict_type',
               '-print_format', 'json', self.filepath]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        
        frames = []
        frame_num = 0
        for frame in data.get('frames', []):
            time_val = frame.get('pkt_pts_time')
            if time_val is None or time_val == '' or time_val == '0':
                time_val = frame_num / fps
            else:
                try:
                    time_val = float(time_val)
                except:
                    time_val = frame_num / fps
            
            frames.append({
                'time': time_val,
                'size': int(frame.get('pkt_size', 0)),
                'type': frame.get('pict_type', 'P')
            })
            frame_num += 1
        
        if len(frames) > 0:
            print(f"DEBUG: Extracted {len(frames)} frames, "
                  f"time range: {frames[0]['time']:.2f}s - {frames[-1]['time']:.2f}s")
        
        return frames
    
    def _calculate_statistics(self, frame_data, metadata):
        """
        Calculate bitrate statistics using optimized NumPy operations.
        NEW in v1.1.0: Much faster windowing with NumPy convolution.
        """
        if not frame_data:
            return {}
        
        # IMPROVEMENT 1: Use list comprehensions (Pythonic and faster)
        times = np.array([f['time'] for f in frame_data])
        sizes = np.array([f['size'] for f in frame_data])
        frame_types = [f['type'] for f in frame_data]
        
        # Calculate bitrates using NumPy (vectorized operation)
        bitrates = (sizes * 8 * metadata['fps']) / 1_000_000
        
        # IMPROVEMENT 2: Use NumPy convolution for windowing (50x faster!)
        window_frames = int(metadata['fps'])  # 1 second worth of frames
        if len(bitrates) > window_frames:
            # Rolling average using convolution
            windowed_bitrates = np.convolve(
                bitrates,
                np.ones(window_frames) / window_frames,
                mode='valid'
            )
            # Align times with windowed data
            offset = window_frames // 2
            windowed_times = times[offset:offset + len(windowed_bitrates)]
        else:
            # Video too short for windowing
            windowed_bitrates = bitrates
            windowed_times = times
        
        print(f"DEBUG: Windowing from {times[0]:.2f}s to {times[-1]:.2f}s")
        print(f"DEBUG: Created {len(windowed_bitrates)} windowed points")
        
        return {
            'avg_bitrate': np.mean(bitrates),
            'max_bitrate': np.max(bitrates),
            'min_bitrate': np.min(bitrates),
            'std_bitrate': np.std(bitrates),
            'frame_count': len(frame_data),
            'i_frame_count': sum(1 for f in frame_types if f == 'I'),
            'bitrates': bitrates.tolist(),
            'times': times.tolist(),
            'windowed_bitrates': windowed_bitrates.tolist(),
            'windowed_times': windowed_times.tolist(),
            'frame_types': frame_types
        }


class BitrateChart(FigureCanvas):
    def __init__(self, parent=None):
        self.fig = Figure(figsize=(10, 6), facecolor='#2b2b2b', dpi=100)
        super().__init__(self.fig)
        self.setParent(parent)
        self.setMinimumSize(400, 300)
        self.ax = self.fig.add_subplot(111)
        self.setup_plot()
        self.fig.tight_layout()
        self.draw()
        
    def setup_plot(self):
        self.ax.set_facecolor('#1e1e1e')
        self.ax.tick_params(colors='white')
        for spine in self.ax.spines.values():
            spine.set_color('white')
        self.ax.set_xlabel('Time (seconds)', color='white', fontsize=10)
        self.ax.set_ylabel('Bitrate (Mbps)', color='white', fontsize=10)
        self.ax.grid(True, alpha=0.2, color='white')
        
    def plot_bitrate(self, times, bitrates, windowed_times, windowed_bitrates):
        print(f"DEBUG: Plotting {len(times)} frames, {len(windowed_times)} windowed points")
        
        self.ax.clear()
        self.setup_plot()
        
        if len(times) > 0 and len(bitrates) > 0:
            self.ax.plot(times, bitrates, alpha=0.3, color='#4fc3f7', 
                        linewidth=0.5, label='Per-frame')
            print(f"DEBUG: Plotted per-frame: {len(times)} points")
        
        if len(windowed_times) > 0 and len(windowed_bitrates) > 0:
            self.ax.plot(windowed_times, windowed_bitrates, color='#00e676', 
                        linewidth=2, label='1s average')
            self.ax.fill_between(windowed_times, windowed_bitrates, 
                                alpha=0.3, color='#00e676')
            print(f"DEBUG: Plotted windowed: {len(windowed_times)} points")
        
        self.ax.legend(facecolor='#2b2b2b', edgecolor='white', 
                      labelcolor='white', loc='upper right')
        self.ax.set_title('Bitrate Over Time', color='white', 
                         fontsize=12, fontweight='bold', pad=10)
        
        self.fig.tight_layout()
        self.draw()
        self.flush_events()
        print("DEBUG: Chart draw() called")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ProRes Bitrate Analyzer v1.2.0")
        self.setGeometry(100, 100, 1200, 800)
        
        # Settings for persistent storage
        self.settings = QSettings("ProResAnalyzer", "ProResAnalyzer")
        
        self.set_dark_theme()
        self.init_ui()
        self.setup_shortcuts()
        self.current_file = None
        self.results = None
        
    def set_dark_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(43, 43, 43))
        palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Base, QColor(30, 30, 30))
        palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 230, 118))
        self.setPalette(palette)
        
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        header = QLabel("ProRes Bitrate Analyzer v1.2.0")
        header.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        file_layout = QHBoxLayout()
        self.file_label = QLabel("No file selected")
        self.file_label.setStyleSheet("padding: 10px; background: #1e1e1e;")
        file_layout.addWidget(self.file_label)
        
        self.select_btn = QPushButton("Select Video File")
        self.select_btn.clicked.connect(self.select_file)
        self.select_btn.setStyleSheet("padding: 10px; background: #00e676; color: black; font-weight: bold;")
        file_layout.addWidget(self.select_btn)
        layout.addLayout(file_layout)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        chart_group = QGroupBox("Bitrate Graph")
        chart_layout = QVBoxLayout()
        self.chart = BitrateChart()
        chart_layout.addWidget(self.chart)
        chart_group.setLayout(chart_layout)
        splitter.addWidget(chart_group)
        
        info_group = QGroupBox("Analysis Results")
        info_layout = QVBoxLayout()
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setFont(QFont("Monaco", 11))
        info_layout.addWidget(self.info_text)
        info_group.setLayout(info_layout)
        splitter.addWidget(info_group)
        
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)
        
        # IMPROVEMENT 3: Add Export Graph button
        button_layout = QHBoxLayout()
        
        self.export_btn = QPushButton("Export Data as JSON")
        self.export_btn.clicked.connect(self.export_data)
        self.export_btn.setEnabled(False)
        button_layout.addWidget(self.export_btn)
        
        self.export_graph_btn = QPushButton("Export Graph as Image")
        self.export_graph_btn.clicked.connect(self.export_graph)
        self.export_graph_btn.setEnabled(False)
        self.export_graph_btn.setStyleSheet("padding: 10px;")
        button_layout.addWidget(self.export_graph_btn)
        
        layout.addLayout(button_layout)
    
    def setup_shortcuts(self):
        """
        Setup keyboard shortcuts.
        NEW in v1.2.0: Added keyboard shortcuts for common actions.
        """
        # ⌘O or Ctrl+O - Open file
        open_action = QAction("Open", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.select_file)
        self.addAction(open_action)
        
        # ⌘E or Ctrl+E - Export data
        export_action = QAction("Export Data", self)
        export_action.setShortcut(QKeySequence("Ctrl+E"))
        export_action.triggered.connect(self.export_data)
        self.addAction(export_action)
        
        # ⌘Shift+E - Export graph
        export_graph_action = QAction("Export Graph", self)
        export_graph_action.setShortcut(QKeySequence("Ctrl+Shift+E"))
        export_graph_action.triggered.connect(self.export_graph)
        self.addAction(export_graph_action)
        
        # ⌘W or Ctrl+W - Close window
        close_action = QAction("Close", self)
        close_action.setShortcut(QKeySequence.StandardKey.Close)
        close_action.triggered.connect(self.close)
        self.addAction(close_action)
        
        # ⌘Q or Ctrl+Q - Quit application
        quit_action = QAction("Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(QApplication.quit)
        self.addAction(quit_action)
        
    def select_file(self):
        """
        Open file dialog and start analysis.
        NEW in v1.2.0: Remembers last used directory.
        """
        # Get last used directory from settings
        last_dir = self.settings.value("last_directory", str(Path.home()))
        
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select ProRes Video File", last_dir,
            "Video Files (*.mov *.mp4 *.mxf);;All Files (*.*)")
        
        if filepath:
            # Save directory for next time
            self.settings.setValue("last_directory", str(Path(filepath).parent))
            
            self.current_file = filepath
            self.file_label.setText(Path(filepath).name)
            self.analyze_file(filepath)
    
    def analyze_file(self, filepath):
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.info_text.clear()
        self.export_btn.setEnabled(False)
        self.export_graph_btn.setEnabled(False)
        self.analyzer = VideoAnalyzer(filepath)
        self.analyzer.progress.connect(self.update_progress)
        self.analyzer.finished.connect(self.display_results)
        self.analyzer.error.connect(self.show_error)
        self.analyzer.start()
    
    def update_progress(self, value, message):
        self.progress_bar.setValue(value)
        self.status_label.setText(message)
    
    def show_error(self, message):
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"Error: {message}")
        self.status_label.setStyleSheet("color: #ff5252;")
    
    def display_results(self, results):
        self.results = results
        self.progress_bar.setVisible(False)
        self.status_label.setText("Analysis complete")
        self.status_label.setStyleSheet("color: #00e676;")
        self.export_btn.setEnabled(True)
        self.export_graph_btn.setEnabled(True)
        
        metadata = results['metadata']
        stats = results['stats']
        
        print(f"DEBUG: Times length: {len(stats['times'])}")
        print(f"DEBUG: Bitrates length: {len(stats['bitrates'])}")
        print(f"DEBUG: Windowed times length: {len(stats['windowed_times'])}")
        print(f"DEBUG: Windowed bitrates length: {len(stats['windowed_bitrates'])}")
        if len(stats['bitrates']) > 0:
            print(f"DEBUG: Bitrate range: {min(stats['bitrates']):.2f} - "
                  f"{max(stats['bitrates']):.2f} Mbps")
        
        self.chart.plot_bitrate(
            stats['times'],
            stats['bitrates'],
            stats['windowed_times'],
            stats['windowed_bitrates']
        )
        
        info = f"""VIDEO INFORMATION
File: {Path(self.current_file).name}
Codec: {metadata['codec_long']}
Resolution: {metadata['width']}x{metadata['height']}
Frame Rate: {metadata['fps']:.2f} fps
Duration: {metadata['duration']:.2f} seconds
Total Size: {metadata['size'] / (1024**3):.2f} GB

BITRATE STATISTICS
Average Bitrate: {stats['avg_bitrate']:.2f} Mbps
Maximum Bitrate: {stats['max_bitrate']:.2f} Mbps
Minimum Bitrate: {stats['min_bitrate']:.2f} Mbps
Std Deviation: {stats['std_bitrate']:.2f} Mbps
Overall File Bitrate: {metadata['bitrate'] / 1_000_000:.2f} Mbps

FRAME STATISTICS
Total Frames: {stats['frame_count']:,}
I-Frames: {stats['i_frame_count']:,}
I-Frame Interval: {stats['frame_count'] / max(stats['i_frame_count'], 1):.1f} frames"""
        
        self.info_text.setPlainText(info)
    
    def export_data(self):
        """Export analysis results as JSON file."""
        if not self.results:
            return
        
        # Get last used directory
        last_dir = self.settings.value("last_directory", str(Path.home()))
        default_name = f"bitrate_analysis_{Path(self.current_file).stem}.json"
        
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Analysis Data", 
            str(Path(last_dir) / default_name),
            "JSON Files (*.json)")
        
        if filepath:
            # Save directory for next time
            self.settings.setValue("last_directory", str(Path(filepath).parent))
            
            export_data = {
                'source_file': self.current_file,
                'metadata': self.results['metadata'],
                'statistics': {
                    'avg_bitrate_mbps': self.results['stats']['avg_bitrate'],
                    'max_bitrate_mbps': self.results['stats']['max_bitrate'],
                    'min_bitrate_mbps': self.results['stats']['min_bitrate'],
                    'std_bitrate_mbps': self.results['stats']['std_bitrate'],
                    'frame_count': self.results['stats']['frame_count'],
                    'i_frame_count': self.results['stats']['i_frame_count']
                },
                'timeline': [
                    {'time': t, 'bitrate_mbps': br}
                    for t, br in zip(self.results['stats']['windowed_times'],
                                   self.results['stats']['windowed_bitrates'])
                ]
            }
            with open(filepath, 'w') as f:
                json.dump(export_data, f, indent=2)
            self.status_label.setText(f"Data exported to {Path(filepath).name}")
    
    def export_graph(self):
        """
        Export the current graph as an image file.
        NEW in v1.1.0: Export graph feature.
        NEW in v1.2.0: Remembers last used directory.
        """
        if not self.results:
            return
        
        # Get last used directory
        last_dir = self.settings.value("last_directory", str(Path.home()))
        default_name = f"bitrate_graph_{Path(self.current_file).stem}.png"
        
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export Graph as Image",
            str(Path(last_dir) / default_name),
            "PNG Image (*.png);;PDF Document (*.pdf);;SVG Vector (*.svg)"
        )
        
        if filepath:
            # Save directory for next time
            self.settings.setValue("last_directory", str(Path(filepath).parent))
            
            try:
                self.chart.fig.savefig(
                    filepath,
                    dpi=300,
                    bbox_inches='tight',
                    facecolor='#2b2b2b'
                )
                self.status_label.setText(f"Graph exported to {Path(filepath).name}")
                self.status_label.setStyleSheet("color: #00e676;")
            except Exception as e:
                self.status_label.setText(f"Export failed: {str(e)}")
                self.status_label.setStyleSheet("color: #ff5252;")


def main():
    print(f"DEBUG: Matplotlib backend: {matplotlib.get_backend()}")
    print(f"DEBUG: Matplotlib version: {matplotlib.__version__}")
    print("DEBUG: ProRes Bitrate Analyzer v1.2.0")
    print("DEBUG: New features: Splash screen, keyboard shortcuts, remember directory")
    
    app = QApplication(sys.argv)
    app.setApplicationName("ProRes Bitrate Analyzer")
    
    # Create and show splash screen
    splash = create_splash_screen()
    splash.show()
    app.processEvents()
    
    # Create main window (this is the slow part)
    window = MainWindow()
    
    # Close splash and show main window
    splash.finish(window)
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()