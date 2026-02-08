#!/usr/bin/env python3
import sys
import json
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QLabel, QFileDialog, 
                            QProgressBar, QTextEdit, QSplitter, QGroupBox)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QFont, QPalette, QColor
import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np

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
            # Try to get timestamp, fall back to frame number if not available
            time_val = frame.get('pkt_pts_time')
            if time_val is None or time_val == '' or time_val == '0':
                # Calculate time from frame number if timestamp missing
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
            print(f"DEBUG: Extracted {len(frames)} frames, time range: {frames[0]['time']:.2f}s - {frames[-1]['time']:.2f}s")
        return frames
    
    def _calculate_statistics(self, frame_data, metadata):
        if not frame_data:
            return {}
        bitrates = []
        times = []
        for frame in frame_data:
            bitrate_bps = frame['size'] * 8 * metadata['fps']
            bitrate_mbps = bitrate_bps / 1_000_000
            bitrates.append(bitrate_mbps)
            times.append(frame['time'])
        
        # Calculate window-based averages (1-second windows)
        window_size = 1.0
        windowed_bitrates = []
        windowed_times = []
        if times and len(times) > 0:
            current_time = times[0]  # Start from first frame time, not 0
            max_time = times[-1]
            print(f"DEBUG: Windowing from {current_time:.2f}s to {max_time:.2f}s")
            
            while current_time < max_time:
                window_end = current_time + window_size
                window_frames = [br for t, br in zip(times, bitrates) 
                               if current_time <= t < window_end]
                if window_frames:
                    windowed_bitrates.append(np.mean(window_frames))
                    windowed_times.append(current_time + window_size/2)
                current_time += window_size
            
            print(f"DEBUG: Created {len(windowed_bitrates)} windowed points")
        
        return {
            'avg_bitrate': np.mean(bitrates),
            'max_bitrate': np.max(bitrates),
            'min_bitrate': np.min(bitrates),
            'std_bitrate': np.std(bitrates),
            'frame_count': len(frame_data),
            'i_frame_count': sum(1 for f in frame_data if f['type'] == 'I'),
            'bitrates': bitrates,
            'times': times,
            'windowed_bitrates': windowed_bitrates,
            'windowed_times': windowed_times
        }


class BitrateChart(FigureCanvas):
    def __init__(self, parent=None):
        self.fig = Figure(figsize=(10, 6), facecolor='#2b2b2b', dpi=100)
        super().__init__(self.fig)
        self.setParent(parent)
        self.setMinimumSize(400, 300)
        self.ax = self.fig.add_subplot(111)
        self.setup_plot()
        # Draw initial empty plot
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
        
        # Plot data
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
        
        # Force update
        self.fig.tight_layout()
        self.draw()
        self.flush_events()
        print("DEBUG: Chart draw() called")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ProRes Bitrate Analyzer")
        self.setGeometry(100, 100, 1200, 800)
        self.set_dark_theme()
        self.init_ui()
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
        
        header = QLabel("ProRes Bitrate Analyzer")
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
        self.info_text.setFont(QFont("Monaco", 11))  # Changed from Courier to Monaco
        info_layout.addWidget(self.info_text)
        info_group.setLayout(info_layout)
        splitter.addWidget(info_group)
        
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)
        
        self.export_btn = QPushButton("Export Data as JSON")
        self.export_btn.clicked.connect(self.export_data)
        self.export_btn.setEnabled(False)
        layout.addWidget(self.export_btn)
        
    def select_file(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select ProRes Video File", str(Path.home()),
            "Video Files (*.mov *.mp4 *.mxf);;All Files (*.*)")
        if filepath:
            self.current_file = filepath
            self.file_label.setText(Path(filepath).name)
            self.analyze_file(filepath)
    
    def analyze_file(self, filepath):
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.info_text.clear()
        self.export_btn.setEnabled(False)
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
        
        metadata = results['metadata']
        stats = results['stats']
        
        # DEBUG: Print data info
        print(f"DEBUG: Times length: {len(stats['times'])}")
        print(f"DEBUG: Bitrates length: {len(stats['bitrates'])}")
        print(f"DEBUG: Windowed times length: {len(stats['windowed_times'])}")
        print(f"DEBUG: Windowed bitrates length: {len(stats['windowed_bitrates'])}")
        if len(stats['bitrates']) > 0:
            print(f"DEBUG: Bitrate range: {min(stats['bitrates']):.2f} - {max(stats['bitrates']):.2f} Mbps")
        
        # Update chart
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
        if not self.results:
            return
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Analysis Data", str(Path.home() / "bitrate_analysis.json"),
            "JSON Files (*.json)")
        if filepath:
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
                'timeline': [{'time': t, 'bitrate_mbps': br}
                    for t, br in zip(self.results['stats']['windowed_times'],
                                   self.results['stats']['windowed_bitrates'])]
            }
            with open(filepath, 'w') as f:
                json.dump(export_data, f, indent=2)
            self.status_label.setText(f"Data exported to {Path(filepath).name}")


def main():
    print(f"DEBUG: Matplotlib backend: {matplotlib.get_backend()}")
    print(f"DEBUG: Matplotlib version: {matplotlib.__version__}")
    
    app = QApplication(sys.argv)
    app.setApplicationName("ProRes Bitrate Analyzer")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()