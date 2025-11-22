"""
Metrics Calculator - Computes torso angle and posture classification
"""

import math
from typing import Dict, Optional
from collections import deque


class MetricsCalculator:
    """Calculates posture metrics from landmarks."""

    def __init__(self, config: Dict, smoothing_frames: int = 3):
        """
        Initialize with configuration parameters.

        Args:
            config: Detection configuration dictionary
            smoothing_frames: Number of frames to average for smoothing (default 3)
        """
        self.config = config
        self.smoothing_frames = smoothing_frames

        # Frame buffers for smoothing
        self.angle_buffer = deque(maxlen=smoothing_frames)
        self.vdiff_buffer = deque(maxlen=smoothing_frames)

    def calculate_metrics(self, landmarks: Dict, current_posture: Optional[str] = None) -> Optional[Dict]:
        """
        Calculate posture metrics from landmarks.

        Args:
            landmarks: Dictionary with shoulder and hip landmarks
            current_posture: Optional current posture for hysteresis

        Returns:
            Dictionary with metrics:
            {
                'angle': float (degrees, 0-180),
                'vertical_diff': float (normalized),
                'confidence': float (0-1),
                'posture': str ('SITTING', 'PROPPED', 'LYING', 'TRANSITIONING')
            }
        """
        if not landmarks:
            return None

        # Calculate midpoints
        shoulder_mid_x = (landmarks['left_shoulder']['x'] + landmarks['right_shoulder']['x']) / 2
        shoulder_mid_y = (landmarks['left_shoulder']['y'] + landmarks['right_shoulder']['y']) / 2

        hip_mid_x = (landmarks['left_hip']['x'] + landmarks['right_hip']['x']) / 2
        hip_mid_y = (landmarks['left_hip']['y'] + landmarks['right_hip']['y']) / 2

        # Calculate torso vector (from hip to shoulder)
        torso_x = shoulder_mid_x - hip_mid_x
        torso_y = shoulder_mid_y - hip_mid_y

        # Calculate angle using atan2
        angle_rad = math.atan2(torso_y, torso_x)
        angle_deg = math.degrees(angle_rad)

        # Normalize to 0-180 range
        if angle_deg < 0:
            angle_deg += 180

        # Calculate vertical difference (positive when hip is below shoulder)
        vertical_diff = hip_mid_y - shoulder_mid_y

        # Add to smoothing buffers
        self.angle_buffer.append(angle_deg)
        self.vdiff_buffer.append(vertical_diff)

        # Calculate smoothed values (average of buffer)
        smoothed_angle = sum(self.angle_buffer) / len(self.angle_buffer)
        smoothed_vdiff = sum(self.vdiff_buffer) / len(self.vdiff_buffer)

        # Get confidence
        confidence = landmarks['avg_confidence']

        # Classify posture using smoothed values (with hysteresis if applicable)
        if current_posture:
            posture = self.classify_with_hysteresis(smoothed_angle, smoothed_vdiff, current_posture)
        else:
            posture = self._classify_posture(smoothed_angle, smoothed_vdiff)

        return {
            'angle': smoothed_angle,
            'vertical_diff': smoothed_vdiff,
            'confidence': confidence,
            'posture': posture
        }

    def _classify_posture(self, angle: float, vertical_diff: float) -> str:
        """
        Classify posture based on angle and vertical difference.
        Priority: vertical_diff is the primary indicator for lying/sitting detection.

        Args:
            angle: Torso angle in degrees (0-180)
            vertical_diff: Vertical difference between hip and shoulder

        Returns:
            Posture classification: 'SITTING', 'PROPPED', 'LYING', or 'TRANSITIONING'
        """
        cfg = self.config

        # PRIORITY CHECK: If nearly flat (vdiff close to 0), classify as LYING
        # This handles rolling side-to-side while lying down
        if abs(vertical_diff) < 0.10:
            return 'LYING'

        # Check for sitting (70-115 degrees and significant vertical diff)
        if (cfg['sitting_angle_min'] <= angle <= cfg['sitting_angle_max'] and
                vertical_diff > cfg['sitting_vertical_diff']):
            return 'SITTING'

        # Check for propped up (30-60 degrees and moderate vertical diff)
        if (cfg['propped_angle_min'] <= angle <= cfg['propped_angle_max'] and
                vertical_diff > cfg['propped_vertical_diff']):
            return 'PROPPED'

        # Fallback: Check for lying by angle ranges (for edge cases)
        for angle_range in cfg['lying_angle_ranges']:
            if angle_range[0] <= angle <= angle_range[1]:
                return 'LYING'

        # Everything else is transitioning
        return 'TRANSITIONING'

    def classify_with_hysteresis(self, angle: float, vertical_diff: float, current_posture: str) -> str:
        """
        Classify posture with hysteresis - apply extra tolerance if staying in current state.
        Uses same vertical_diff priority as base classification.

        Args:
            angle: Torso angle in degrees (0-180)
            vertical_diff: Vertical difference between hip and shoulder
            current_posture: Current posture state to apply hysteresis for

        Returns:
            Posture classification with hysteresis applied
        """
        cfg = self.config
        angle_buffer = cfg.get('hysteresis_angle_buffer', 10)
        vdiff_buffer = cfg.get('hysteresis_vdiff_buffer', 0.05)

        # PRIORITY: If nearly flat, stay LYING (with hysteresis buffer)
        if current_posture == 'LYING' and abs(vertical_diff) < 0.10 + vdiff_buffer:
            return 'LYING'

        # Apply hysteresis based on current state
        if current_posture == 'SITTING':
            # If already sitting, be more lenient
            if (cfg['sitting_angle_min'] - angle_buffer <= angle <= cfg['sitting_angle_max'] + angle_buffer and
                    vertical_diff > cfg['sitting_vertical_diff'] - vdiff_buffer):
                return 'SITTING'

        elif current_posture == 'PROPPED':
            # If already propped, be more lenient
            if (cfg['propped_angle_min'] - angle_buffer <= angle <= cfg['propped_angle_max'] + angle_buffer and
                    vertical_diff > cfg['propped_vertical_diff'] - vdiff_buffer):
                return 'PROPPED'

        elif current_posture == 'LYING':
            # If already lying, be more lenient with angle ranges (fallback)
            for angle_range in cfg['lying_angle_ranges']:
                if angle_range[0] - angle_buffer <= angle <= angle_range[1] + angle_buffer:
                    return 'LYING'

        # If hysteresis doesn't apply, use normal classification
        return self._classify_posture(angle, vertical_diff)
