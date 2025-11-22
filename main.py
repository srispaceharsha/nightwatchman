#!/usr/bin/env python3
"""
SeniorCare Posture Monitor - Main Entry Point

Command-line application that monitors posture using webcam and MediaPipe Pose.
"""

import argparse
import cv2
import yaml
import time
import os
import sys
import mediapipe as mp
from pathlib import Path
from datetime import datetime

from pose_detector import PoseDetector
from metrics_calculator import MetricsCalculator
from state_machine import PostureStateMachine, State


class PostureMonitor:
    """Main orchestrator for posture monitoring."""

    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize the posture monitor.

        Args:
            config_path: Path to configuration YAML file
        """
        # Load configuration
        self.config = self._load_config(config_path)

        # Initialize components
        self.pose_detector = PoseDetector()
        self.metrics_calculator = MetricsCalculator(self.config['detection'])
        self.state_machine = PostureStateMachine(self.config['detection'])

        # MediaPipe drawing utilities for skeleton overlay
        self.mp_pose = mp.solutions.pose
        self.mp_drawing = mp.solutions.drawing_utils

        # Camera
        self.camera = None

        # Logging
        self.log_file = None
        self._setup_logging()

        # Detection state
        self.first_detection_done = False

        # Statistics
        self.start_time = time.time()
        self.frame_count = 0
        self.alert_count = 0

    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file."""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            return config
        except FileNotFoundError:
            print(f"Error: Config file not found: {config_path}")
            sys.exit(1)
        except yaml.YAMLError as e:
            print(f"Error parsing config file: {e}")
            sys.exit(1)

    def _setup_logging(self):
        """Setup log file with timestamp if enabled."""
        if self.config['logging']['log_to_file']:
            log_path_template = self.config['logging']['log_file']
            log_dir = os.path.dirname(log_path_template)

            # Create logs directory if it doesn't exist
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)

            # Create timestamped log filename
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            log_filename = f"state_transitions_{timestamp}.log"
            log_path = os.path.join(log_dir, log_filename)

            # Open log file
            self.log_file = open(log_path, 'w')
            self.log_file_path = log_path

    def _setup_camera(self):
        """Initialize camera capture."""
        camera_id = self.config['camera']['device_id']
        self.camera = cv2.VideoCapture(camera_id)

        if not self.camera.isOpened():
            print(f"Error: Failed to open camera with ID {camera_id}")
            sys.exit(1)

        # Set camera properties
        width = self.config['camera']['resolution_width']
        height = self.config['camera']['resolution_height']
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        actual_width = int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(self.camera.get(cv2.CAP_PROP_FPS))

        print(f"Camera initialized: {actual_width}x{actual_height} @ {fps}fps")

    def _format_timestamp(self) -> str:
        """Get formatted timestamp for output."""
        elapsed = time.time() - self.start_time
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _log_message(self, message: str):
        """Log message to terminal and/or file."""
        if self.config['logging']['log_to_file'] and self.log_file:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            self.log_file.write(f"{timestamp} | {message}\n")
            self.log_file.flush()

    def _play_alert_sound(self):
        """Play audio alert (3 dings)."""
        for _ in range(3):
            os.system('afplay /System/Library/Sounds/Glass.aiff')
            time.sleep(0.15)  # Small delay between dings

    def _handle_first_detection(self, metrics: dict):
        """Handle the first successful pose detection."""
        if self.first_detection_done:
            return

        self.first_detection_done = True
        posture = metrics['posture']
        confidence = metrics['confidence']
        angle = metrics['angle']

        # Map posture to user-friendly description
        posture_descriptions = {
            'LYING': 'lying down',
            'SITTING': 'sitting up',
            'PROPPED': 'propped up',
            'TRANSITIONING': 'in transition'
        }
        description = posture_descriptions.get(posture, posture.lower())

        # Log and print first detection
        msg = f"DETECTION | First detection: Person found {description} (confidence={confidence:.2f}, angle={angle:.0f}°)"
        self._log_message(msg)
        print(f"First detection: Person found {description} (confidence={confidence:.2f}, angle={angle:.0f}°)")
        print(f"Initial state: {self.state_machine.current_state.value}\n")

    def _handle_transition(self, transition):
        """Handle a state transition."""
        timestamp = self._format_timestamp()
        from_state = transition.from_state.value
        to_state = transition.to_state.value
        metrics = transition.metrics

        angle = metrics['angle']
        confidence = metrics['confidence']
        vdiff = metrics['vertical_diff']

        # Log transition
        msg = f"TRANSITION | {from_state} → {to_state} | confidence={confidence:.2f} angle={angle:.0f}° vdiff={vdiff:.2f}"
        self._log_message(msg)

        # Terminal output
        print(f"[{timestamp}] STATE: {to_state} (confidence={confidence:.2f}, angle={angle:.0f}°)")

        # Handle specific state transitions
        if transition.to_state == State.SITTING_DETECTED:
            duration = self.config['detection']['persistence_duration']
            print(f"[{timestamp}] Timer started ({duration}s)")
            msg = f"TIMER | persistence_timer started ({duration}s)"
            self._log_message(msg)

        elif transition.to_state == State.ALERT_ACTIVE:
            print(f"[{timestamp}] 🚨 ALERT: PERSON SITTING UP 🚨")
            msg = "ALERT | PERSON SITTING UP"
            self._log_message(msg)
            self.alert_count += 1
            # Play audio alert
            self._play_alert_sound()

        elif transition.to_state == State.ALERT_COOLDOWN:
            if transition.from_state == State.ALERT_ACTIVE:
                print(f"[{timestamp}] Alert auto-dismissed (person lying back down)")
                cooldown = self.config['detection']['cooldown_duration']
                print(f"[{timestamp}] Cooldown period: {cooldown}s ({cooldown//60} minutes)")
                msg = f"ALERT | Auto-dismissed (lying detected)"
                self._log_message(msg)

        elif transition.to_state == State.MONITORING_LYING:
            if transition.from_state == State.ALERT_COOLDOWN:
                print(f"[{timestamp}] Cooldown complete")

    def run(self):
        """Run the main monitoring loop."""
        print("SeniorCare Posture Monitor - Starting...")

        # Setup camera
        self._setup_camera()

        print(f"Config loaded from: config.yaml")
        print("Detection started...")
        print("Waiting for person detection...\n")

        show_window = self.config['display']['show_camera_window']

        # Calculate frame delay based on configured processing FPS
        processing_fps = self.config['camera'].get('processing_fps', 30)
        frame_delay = 1.0 / processing_fps
        print(f"Processing rate: {processing_fps} FPS (frame every {frame_delay:.3f}s)")

        try:
            while True:
                # Read frame
                success, frame = self.camera.read()
                if not success:
                    print("Failed to read frame from camera")
                    break

                self.frame_count += 1

                # Detect pose
                landmarks_dict = self.pose_detector.detect(frame)

                if landmarks_dict:
                    # Get current posture for hysteresis
                    current_posture = self.state_machine.get_expected_posture_for_hysteresis()

                    # Calculate metrics (with hysteresis if applicable)
                    metrics = self.metrics_calculator.calculate_metrics(landmarks_dict, current_posture)

                    # Handle first detection
                    if not self.first_detection_done:
                        self._handle_first_detection(metrics)

                    # Update state machine
                    transition = self.state_machine.update(metrics)

                    # Handle transition if one occurred
                    if transition:
                        self._handle_transition(transition)

                    # Draw skeleton overlay if window is enabled
                    if show_window:
                        # Convert landmarks back to MediaPipe format for drawing
                        # (This is a bit hacky but works for visualization)
                        frame = self._draw_pose_overlay(frame, landmarks_dict)

                # Show camera window if enabled
                if show_window:
                    # Add current state text to frame
                    state_text = f"State: {self.state_machine.current_state.value}"
                    cv2.putText(frame, state_text, (10, 30),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                    cv2.imshow("SeniorCare Monitor", frame)

                    # Check for 'q' key to quit
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        print("\nUser requested quit...")
                        break

                # Frame rate control - sleep to achieve configured FPS
                time.sleep(frame_delay)

        except KeyboardInterrupt:
            print("\n\nShutting down...")

        finally:
            self._cleanup()

    def _draw_pose_overlay(self, frame, landmarks_dict):
        """Draw pose skeleton overlay on frame."""
        # We need to reconstruct MediaPipe landmarks from our dict
        # This is a simplified version that just draws key points
        h, w, _ = frame.shape

        # Draw key landmarks
        points = []
        for key in ['left_shoulder', 'right_shoulder', 'left_hip', 'right_hip']:
            lm = landmarks_dict[key]
            x = int(lm['x'] * w)
            y = int(lm['y'] * h)
            points.append((x, y))
            # Draw circles for key points
            cv2.circle(frame, (x, y), 5, (0, 255, 0), -1)

        # Draw lines connecting shoulders and hips
        cv2.line(frame, points[0], points[1], (0, 255, 0), 2)  # shoulders
        cv2.line(frame, points[2], points[3], (0, 255, 0), 2)  # hips
        cv2.line(frame, points[0], points[2], (0, 255, 0), 2)  # left side
        cv2.line(frame, points[1], points[3], (0, 255, 0), 2)  # right side

        return frame

    def _cleanup(self):
        """Clean up resources."""
        # Close CV windows
        cv2.destroyAllWindows()

        # Print statistics
        elapsed = time.time() - self.start_time
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        runtime = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        print(f"\nTotal runtime: {runtime}")
        print(f"Total alerts: {self.alert_count}")

        if self.config['logging']['log_to_file'] and hasattr(self, 'log_file_path'):
            print(f"State transitions logged to: {self.log_file_path}")

        # Release resources
        if self.camera:
            self.camera.release()

        if self.log_file:
            self.log_file.close()

        self.pose_detector.cleanup()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="SeniorCare Posture Monitor - Detects when a person sits up from lying down"
    )
    parser.add_argument(
        '--config',
        type=str,
        default='config.yaml',
        help='Path to configuration YAML file (default: config.yaml)'
    )

    args = parser.parse_args()

    # Create and run monitor
    monitor = PostureMonitor(config_path=args.config)
    monitor.run()


if __name__ == "__main__":
    main()
