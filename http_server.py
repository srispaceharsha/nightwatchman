"""
HTTP Server - Video Streaming for Home Assistant
Provides MJPEG stream and snapshot endpoints
"""

from flask import Flask, Response, jsonify
from flask_cors import CORS
import cv2
import threading
import time
from typing import Optional, Dict
import numpy as np


class VideoStreamServer:
    """HTTP server for video streaming."""

    def __init__(self, config: Dict):
        """
        Initialize video stream server.

        Args:
            config: HTTP configuration from config.yaml
        """
        self.config = config
        self.enabled = config.get('enabled', False)

        if not self.enabled:
            print("HTTP server disabled in config")
            return

        self.host = config.get('host', '0.0.0.0')
        self.port = config.get('port', 5000)
        self.stream_fps = config.get('stream_fps', 5)
        self.stream_width = config.get('stream_width', 320)
        self.stream_height = config.get('stream_height', 240)

        # Current frame storage
        self.current_frame = None
        self.frame_lock = threading.Lock()
        self.last_frame_time = time.time()

        # Flask app
        self.app = Flask(__name__)
        CORS(self.app)  # Enable CORS for HA access

        # Setup routes
        self._setup_routes()

        # Server thread
        self.server_thread = None
        self.running = False

    def _setup_routes(self):
        """Setup Flask routes."""

        @self.app.route('/')
        def index():
            """Root endpoint."""
            return jsonify({
                'service': 'Nightwatchman Video Stream',
                'endpoints': {
                    'video_feed': '/video_feed',
                    'snapshot': '/snapshot',
                    'status': '/status'
                }
            })

        @self.app.route('/status')
        def status():
            """Status endpoint."""
            with self.frame_lock:
                has_frame = self.current_frame is not None
                frame_age = time.time() - self.last_frame_time if has_frame else None

            return jsonify({
                'running': self.running,
                'has_frame': has_frame,
                'frame_age_seconds': frame_age,
                'stream_fps': self.stream_fps,
                'resolution': f"{self.stream_width}x{self.stream_height}"
            })

        @self.app.route('/snapshot')
        def snapshot():
            """Single frame snapshot."""
            with self.frame_lock:
                if self.current_frame is None:
                    # Return placeholder image
                    placeholder = self._create_placeholder()
                    _, buffer = cv2.imencode('.jpg', placeholder)
                    return Response(buffer.tobytes(), mimetype='image/jpeg')

                # Encode current frame as JPEG
                _, buffer = cv2.imencode('.jpg', self.current_frame,
                                        [cv2.IMWRITE_JPEG_QUALITY, 80])
                return Response(buffer.tobytes(), mimetype='image/jpeg')

        @self.app.route('/video_feed')
        def video_feed():
            """MJPEG video stream."""
            return Response(self._generate_frames(),
                          mimetype='multipart/x-mixed-replace; boundary=frame')

    def _generate_frames(self):
        """Generate frames for MJPEG stream."""
        frame_delay = 1.0 / self.stream_fps

        while self.running:
            with self.frame_lock:
                if self.current_frame is None:
                    # Send placeholder if no frame available
                    frame = self._create_placeholder()
                else:
                    frame = self.current_frame.copy()

            # Encode frame as JPEG
            _, buffer = cv2.imencode('.jpg', frame,
                                    [cv2.IMWRITE_JPEG_QUALITY, 70])

            # Yield frame in MJPEG format
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

            time.sleep(frame_delay)

    def _create_placeholder(self):
        """Create placeholder image when no frame available."""
        img = np.zeros((self.stream_height, self.stream_width, 3), dtype=np.uint8)
        text = "No Frame"
        font = cv2.FONT_HERSHEY_SIMPLEX
        text_size = cv2.getTextSize(text, font, 0.7, 2)[0]
        text_x = (self.stream_width - text_size[0]) // 2
        text_y = (self.stream_height + text_size[1]) // 2
        cv2.putText(img, text, (text_x, text_y), font, 0.7, (255, 255, 255), 2)
        return img

    def update_frame(self, frame):
        """
        Update current frame for streaming.

        Args:
            frame: OpenCV frame (BGR format)
        """
        if not self.enabled:
            return

        # Resize frame to stream resolution
        resized = cv2.resize(frame, (self.stream_width, self.stream_height))

        with self.frame_lock:
            self.current_frame = resized
            self.last_frame_time = time.time()

    def start(self):
        """Start HTTP server in background thread."""
        if not self.enabled:
            return

        self.running = True

        def run_server():
            print(f"Starting HTTP server on {self.host}:{self.port}...")
            print(f"  Video feed: http://{self.host}:{self.port}/video_feed")
            print(f"  Snapshot: http://{self.host}:{self.port}/snapshot")
            self.app.run(host=self.host, port=self.port, threaded=True,
                        debug=False, use_reloader=False)

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        time.sleep(1)  # Give server time to start
        print("✓ HTTP server started")

    def stop(self):
        """Stop HTTP server."""
        if not self.enabled:
            return

        print("Stopping HTTP server...")
        self.running = False
        # Note: Flask doesn't have a clean shutdown method when running in thread
        # The daemon thread will terminate when main program exits
