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
from gesture_detector import GestureDetector
from system_state import SystemStateManager, SystemState
from mqtt_client import MQTTClient
from http_server import VideoStreamServer


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
        self.gesture_detector = GestureDetector(self.config.get('gestures', {}))
        self.system_state = SystemStateManager(self.config.get('gestures', {}))

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

        # Gesture tracking for logging
        self.last_thumbs_up_state = False
        self.last_thumbs_down_state = False
        self.last_system_state = SystemState.WAITING_FOR_START

        # Statistics
        self.start_time = time.time()
        self.frame_count = 0
        self.alert_count = 0

        # MQTT Integration
        mqtt_config = self.config.get('mqtt', {})
        self.mqtt_client = MQTTClient(mqtt_config, self._handle_mqtt_command)

        # HTTP Server for video streaming
        http_config = self.config.get('http', {})
        self.http_server = VideoStreamServer(http_config)

        # MQTT command pending flag
        self.pending_mqtt_command = None

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

    def _handle_mqtt_command(self, command: str):
        """
        Handle MQTT command from Home Assistant.

        Args:
            command: Command string (start, stop, pause, resume)
        """
        self.pending_mqtt_command = command
        print(f"[MQTT] Queued command: {command}")

    def _process_mqtt_command(self, command: str):
        """
        Process MQTT command (simulates gesture input).

        Args:
            command: Command string (start, stop, pause, resume)
        """
        timestamp = self._format_timestamp()

        if command == "start":
            if self.system_state.current_state == SystemState.WAITING_FOR_START:
                self.system_state.current_state = SystemState.ACTIVE_MONITORING
                print(f"[{timestamp}] [MQTT] Monitoring started via HA command")
                self._log_message("SYSTEM | Monitoring started via MQTT command")
                self.mqtt_client.publish_state("ACTIVE_MONITORING")

        elif command == "stop":
            self.system_state.current_state = SystemState.WAITING_FOR_START
            print(f"[{timestamp}] [MQTT] Monitoring stopped via HA command")
            self._log_message("SYSTEM | Monitoring stopped via MQTT command")
            self.mqtt_client.publish_state("WAITING_FOR_START")

        elif command == "pause":
            if self.system_state.current_state == SystemState.ACTIVE_MONITORING:
                self.system_state.current_state = SystemState.PAUSED
                self.system_state.pause_start_time = time.time()
                print(f"[{timestamp}] [MQTT] Monitoring paused via HA command")
                self._log_message("SYSTEM | Monitoring paused via MQTT command")
                self.mqtt_client.publish_state("PAUSED")

        elif command == "resume":
            if self.system_state.current_state == SystemState.PAUSED:
                self.system_state.current_state = SystemState.ACTIVE_MONITORING
                self.system_state.pause_start_time = None
                print(f"[{timestamp}] [MQTT] Monitoring resumed via HA command")
                self._log_message("SYSTEM | Monitoring resumed via MQTT command")
                self.mqtt_client.publish_state("ACTIVE_MONITORING")

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

        # Publish posture state to MQTT
        self.mqtt_client.publish_posture(to_state)

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
            # Publish alert to MQTT
            self.mqtt_client.publish_alert("PERSON_SITTING_UP")

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
        print("=" * 60)

        # Setup camera
        self._setup_camera()

        # Start HTTP server
        self.http_server.start()

        print(f"Config loaded from: config.yaml")
        print("\n🖐️  GESTURE CONTROLS ENABLED:")
        print("  👍 Thumbs Up   - Start/Resume monitoring")
        print("  👎 Thumbs Down - Pause monitoring")
        print("\n📱 HOME ASSISTANT INTEGRATION:")
        if self.mqtt_client.connected:
            print("  ✓ MQTT connected - Commands available via HA")
        if self.http_server.enabled:
            print(f"  ✓ Video stream: http://localhost:{self.http_server.port}/video_feed")
        print("=" * 60)
        print("\n⏳ Waiting for thumbs up or HA start command...")
        self._log_message("SYSTEM | Application started - waiting for start gesture or command")
        print()

        show_window = self.config['display']['show_camera_window']

        # Calculate frame delay based on configured processing FPS
        processing_fps = self.config['camera'].get('processing_fps', 30)
        frame_delay = 1.0 / processing_fps
        print(f"Processing rate: {processing_fps} FPS (frame every {frame_delay:.3f}s)")

        # Stats publishing interval (every 30 seconds)
        last_stats_publish = time.time()
        stats_interval = 30

        try:
            while True:
                # Read frame
                success, frame = self.camera.read()
                if not success:
                    print("Failed to read frame from camera")
                    break

                self.frame_count += 1

                # Update HTTP server with current frame
                self.http_server.update_frame(frame)

                # Process pending MQTT command (if any)
                if self.pending_mqtt_command:
                    self._process_mqtt_command(self.pending_mqtt_command)
                    self.pending_mqtt_command = None

                # Detect gestures (always active for control)
                gesture_result = self.gesture_detector.detect(frame)

                # Log gesture detection changes
                self._log_gesture_events(gesture_result)

                # Update system state based on gestures
                old_system_state = self.system_state.current_state
                system_msg = self.system_state.update(gesture_result, self.state_machine)

                # Log system state changes
                if system_msg:
                    timestamp = self._format_timestamp()
                    print(f"[{timestamp}] {system_msg}")
                    self._log_message(f"SYSTEM | {system_msg}")

                    # Reset gesture tracking after state changes
                    if "Thumbs down held" in system_msg:
                        self.gesture_detector.reset_thumbs_down()
                    elif "Thumbs up held" in system_msg:
                        self.gesture_detector.reset_thumbs_up()

                # Log ongoing waiting state
                if self.system_state.current_state != old_system_state:
                    self._log_system_state_change(old_system_state, self.system_state.current_state)

                # Only run posture monitoring if system is active
                if self.system_state.is_monitoring_active():
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
                    # Display system state (top)
                    system_state_text = f"System: {self.system_state.get_state_display()}"
                    cv2.putText(frame, system_state_text, (10, 30),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

                    # Display posture state (below system state) if monitoring active
                    if self.system_state.is_monitoring_active():
                        posture_state_text = f"Posture: {self.state_machine.current_state.value}"
                        cv2.putText(frame, posture_state_text, (10, 60),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

                    # Show gesture hints
                    if gesture_result['hand_detected']:
                        hand_text = "Hand detected"
                        if gesture_result.get('thumbs_up', False):
                            progress = int(gesture_result.get('thumbs_up_progress', 0) * 100)
                            if gesture_result.get('thumbs_up_held', False):
                                hand_text += " - THUMBS UP CONFIRMED!"
                            else:
                                hand_text += f" - THUMBS UP (hold: {progress}%)"
                        elif gesture_result.get('thumbs_down', False):
                            progress = int(gesture_result.get('thumbs_down_progress', 0) * 100)
                            if gesture_result.get('thumbs_down_held', False):
                                hand_text += " - THUMBS DOWN CONFIRMED!"
                            else:
                                hand_text += f" - THUMBS DOWN (hold: {progress}%)"
                        cv2.putText(frame, hand_text, (10, 90),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 2)

                    cv2.imshow("SeniorCare Monitor", frame)

                    # Check for 'q' key to quit
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        print("\nUser requested quit...")
                        break

                # Publish stats periodically to MQTT
                if time.time() - last_stats_publish >= stats_interval:
                    self.mqtt_client.publish_stats(self.alert_count, self.frame_count)
                    last_stats_publish = time.time()

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

    def _log_gesture_events(self, gesture_result: dict):
        """Log gesture detection events to console."""
        timestamp = self._format_timestamp()

        # Log thumbs up detection and hold progress
        is_thumbs_up = gesture_result.get('thumbs_up', False)
        thumbs_up_progress = gesture_result.get('thumbs_up_progress', 0.0)
        thumbs_up_held = gesture_result.get('thumbs_up_held', False)

        if is_thumbs_up and not self.last_thumbs_up_state:
            hold_duration = self.config.get('gestures', {}).get('thumbs_up_hold_duration', 2.0)
            print(f"[{timestamp}] 👍 Thumbs up detected! Hold for {hold_duration}s...")
            self._log_message(f"GESTURE | Thumbs up detected (hold required: {hold_duration}s)")

        # Show progress for holding thumbs up
        if is_thumbs_up and thumbs_up_progress > 0 and thumbs_up_progress < 1.0:
            progress_percent = int(thumbs_up_progress * 100)
            if progress_percent % 25 == 0 and progress_percent > 0:  # 25%, 50%, 75%
                if not hasattr(self, '_last_thumbs_up_progress') or self._last_thumbs_up_progress != progress_percent:
                    print(f"[{timestamp}] 👍 Holding... {progress_percent}%")
                    self._last_thumbs_up_progress = progress_percent

        if thumbs_up_held and not self.last_thumbs_up_state:
            print(f"[{timestamp}] ✅ Thumbs up confirmed!")
            self._log_message("GESTURE | Thumbs up held successfully")
            if hasattr(self, '_last_thumbs_up_progress'):
                delattr(self, '_last_thumbs_up_progress')

        self.last_thumbs_up_state = is_thumbs_up

        # Log thumbs down detection and hold progress
        is_thumbs_down = gesture_result.get('thumbs_down', False)
        thumbs_down_progress = gesture_result.get('thumbs_down_progress', 0.0)
        thumbs_down_held = gesture_result.get('thumbs_down_held', False)

        if is_thumbs_down and not self.last_thumbs_down_state:
            hold_duration = self.config.get('gestures', {}).get('thumbs_down_hold_duration', 2.0)
            print(f"[{timestamp}] 👎 Thumbs down detected! Hold for {hold_duration}s...")
            self._log_message(f"GESTURE | Thumbs down detected (hold required: {hold_duration}s)")

        # Show progress for holding thumbs down
        if is_thumbs_down and thumbs_down_progress > 0 and thumbs_down_progress < 1.0:
            progress_percent = int(thumbs_down_progress * 100)
            if progress_percent % 25 == 0 and progress_percent > 0:  # 25%, 50%, 75%
                if not hasattr(self, '_last_thumbs_down_progress') or self._last_thumbs_down_progress != progress_percent:
                    print(f"[{timestamp}] 👎 Holding... {progress_percent}%")
                    self._last_thumbs_down_progress = progress_percent

        if thumbs_down_held and not self.last_thumbs_down_state:
            print(f"[{timestamp}] ✅ Thumbs down confirmed!")
            self._log_message("GESTURE | Thumbs down held successfully")
            if hasattr(self, '_last_thumbs_down_progress'):
                delattr(self, '_last_thumbs_down_progress')

        self.last_thumbs_down_state = is_thumbs_down

    def _log_system_state_change(self, old_state: SystemState, new_state: SystemState):
        """Log system state transitions."""
        timestamp = self._format_timestamp()

        # Publish state change to MQTT
        self.mqtt_client.publish_state(new_state.value)

        if new_state == SystemState.WAITING_FOR_START:
            print(f"[{timestamp}] ⏳ Waiting for thumbs up to start monitoring...")
            self._log_message("SYSTEM | Waiting for start gesture")

        elif new_state == SystemState.ACTIVE_MONITORING:
            if old_state == SystemState.WAITING_FOR_START:
                print(f"[{timestamp}] ✅ Monitoring started")
                self._log_message("SYSTEM | Monitoring started")
            elif old_state == SystemState.PAUSED:
                print(f"[{timestamp}] ▶️  Monitoring resumed")
                self._log_message("SYSTEM | Monitoring resumed")

        elif new_state == SystemState.PAUSED:
            print(f"[{timestamp}] ⏸️  Monitoring paused")
            self._log_message("SYSTEM | Monitoring paused")

    def _cleanup(self):
        """Clean up resources."""
        # Close gesture detector
        if hasattr(self, 'gesture_detector'):
            self.gesture_detector.cleanup()

        # Close MQTT connection
        if hasattr(self, 'mqtt_client'):
            self.mqtt_client.cleanup()

        # Stop HTTP server
        if hasattr(self, 'http_server'):
            self.http_server.stop()

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
