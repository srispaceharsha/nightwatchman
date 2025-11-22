"""
Pose Detector - MediaPipe wrapper for extracting pose landmarks
"""

import mediapipe as mp
import cv2
from typing import Optional, Dict


class PoseDetector:
    """Wraps MediaPipe Pose to extract relevant landmarks."""

    def __init__(self):
        """Initialize MediaPipe Pose."""
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )

    def detect(self, frame) -> Optional[Dict]:
        """
        Detect pose landmarks in a frame.

        Args:
            frame: OpenCV BGR image

        Returns:
            Dictionary with landmarks and confidence, or None if no person detected
            {
                'left_shoulder': {'x': float, 'y': float, 'confidence': float},
                'right_shoulder': {'x': float, 'y': float, 'confidence': float},
                'left_hip': {'x': float, 'y': float, 'confidence': float},
                'right_hip': {'x': float, 'y': float, 'confidence': float},
                'avg_confidence': float
            }
        """
        # Convert BGR to RGB for MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Process with MediaPipe
        results = self.pose.process(rgb_frame)

        if not results.pose_landmarks:
            return None

        landmarks = results.pose_landmarks.landmark

        # Extract the 4 key landmarks
        left_shoulder = landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER]
        right_shoulder = landmarks[self.mp_pose.PoseLandmark.RIGHT_SHOULDER]
        left_hip = landmarks[self.mp_pose.PoseLandmark.LEFT_HIP]
        right_hip = landmarks[self.mp_pose.PoseLandmark.RIGHT_HIP]

        # Calculate average confidence
        confidences = [
            left_shoulder.visibility,
            right_shoulder.visibility,
            left_hip.visibility,
            right_hip.visibility
        ]
        avg_confidence = sum(confidences) / len(confidences)

        return {
            'left_shoulder': {
                'x': left_shoulder.x,
                'y': left_shoulder.y,
                'confidence': left_shoulder.visibility
            },
            'right_shoulder': {
                'x': right_shoulder.x,
                'y': right_shoulder.y,
                'confidence': right_shoulder.visibility
            },
            'left_hip': {
                'x': left_hip.x,
                'y': left_hip.y,
                'confidence': left_hip.visibility
            },
            'right_hip': {
                'x': right_hip.x,
                'y': right_hip.y,
                'confidence': right_hip.visibility
            },
            'avg_confidence': avg_confidence
        }

    def cleanup(self):
        """Release MediaPipe resources."""
        self.pose.close()
