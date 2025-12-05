"""
Gesture Detector - Hand gesture recognition for system control
Uses thumbs up/down detection algorithms
"""

import mediapipe as mp
import time
import math
import statistics
from typing import Optional, Tuple, Dict


def angle_at(p1, p2, p3):
    """Angle (in degrees) at point p2 formed by p1-p2-p3 using 3D coords."""
    v1 = (p1.x - p2.x, p1.y - p2.y, p1.z - p2.z)
    v2 = (p3.x - p2.x, p3.y - p2.y, p3.z - p2.z)

    dot = v1[0]*v2[0] + v1[1]*v2[1] + v1[2]*v2[2]
    n1 = math.sqrt(v1[0]**2 + v1[1]**2 + v1[2]**2)
    n2 = math.sqrt(v2[0]**2 + v2[1]**2 + v2[2]**2)
    if n1 == 0 or n2 == 0:
        return 0.0
    cosang = max(-1.0, min(1.0, dot / (n1 * n2)))
    return math.degrees(math.acos(cosang))


def calculate_thumb_vertical_angle(p_base, p_tip):
    """
    Calculate angle (in degrees) between thumb direction and vertical axis in 2D (x-y plane).
    Ignores z-component (depth) since we only care about the screen-space angle.

    Args:
        p_base: Base point (e.g., thumb MCP)
        p_tip: Tip point (e.g., thumb tip)

    Returns:
        Angle in degrees from vertical (0° = straight up, 180° = straight down)
    """
    # Thumb direction vector in 2D (x-y plane only, ignoring z/depth)
    thumb_vec_2d = (p_tip.x - p_base.x, p_tip.y - p_base.y)

    print(f"[DEBUG] Thumb vector 2D: ({thumb_vec_2d[0]:.3f}, {thumb_vec_2d[1]:.3f})")

    # Vertical vector (pointing up in image coordinates: negative y direction)
    vertical_vec = (0, -1)

    # Calculate angle using dot product in 2D
    dot = thumb_vec_2d[0]*vertical_vec[0] + thumb_vec_2d[1]*vertical_vec[1]
    thumb_len = math.sqrt(thumb_vec_2d[0]**2 + thumb_vec_2d[1]**2)

    if thumb_len == 0:
        return 90.0  # Undefined, return perpendicular

    cosang = max(-1.0, min(1.0, dot / thumb_len))
    angle = math.degrees(math.acos(cosang))
    print(f"[DEBUG] Dot: {dot:.3f}, Length: {thumb_len:.3f}, Angle: {angle:.2f}°")
    return angle


def classify_thumbs_up(hand_landmarks):
    """
    Detect thumbs up gesture.

    Returns:
        is_up (bool), variant (str or None), folded_count (int)
    """
    MIN_FOLDED_FINGERS = 2
    FOLDED_ANGLE_MAX = 120
    MAX_VERTICAL_DEVIATION = 20.0  # degrees from perfect vertical

    lm = hand_landmarks.landmark

    # Thumb up: tip higher (smaller y) than MCP + index MCP
    thumb_tip = lm[4]
    thumb_mcp = lm[2]
    index_mcp = lm[5]
    thumb_up = (thumb_tip.y < thumb_mcp.y) and (thumb_tip.y < index_mcp.y)

    # Check if thumb is pointing straight up (within ±8 degrees)
    if thumb_up:
        vertical_angle = calculate_thumb_vertical_angle(thumb_mcp, thumb_tip)
        # For thumbs up, angle should be close to 0° (straight up)
        print(f"[DEBUG] Thumbs UP - Vertical angle: {vertical_angle:.2f}°, Max allowed: {MAX_VERTICAL_DEVIATION}°")
        if vertical_angle > MAX_VERTICAL_DEVIATION:
            print(f"[DEBUG] Thumbs UP REJECTED - angle {vertical_angle:.2f}° > {MAX_VERTICAL_DEVIATION}°")
            thumb_up = False

    # Fold detection via angles at PIP joints
    finger_joints = {
        "index": (5, 6, 8),
        "middle": (9, 10, 12),
        "ring": (13, 14, 16),
        "pinky": (17, 18, 20),
    }

    folded = {}
    for name, (mcp_i, pip_i, tip_i) in finger_joints.items():
        a = angle_at(lm[mcp_i], lm[pip_i], lm[tip_i])
        folded[name] = a < FOLDED_ANGLE_MAX

    folded_count = sum(1 for v in folded.values() if v)

    if not thumb_up or folded_count < MIN_FOLDED_FINGERS:
        return False, None, folded_count

    # Orientation: palm / back / fist
    fingertip_ids = [8, 12, 16, 20]
    mcp_ids = [5, 9, 13, 17]
    tip_z_avg = statistics.mean(lm[i].z for i in fingertip_ids)
    mcp_z_avg = statistics.mean(lm[i].z for i in mcp_ids)

    if folded_count >= 3:
        variant = "fist"
    else:
        if tip_z_avg < mcp_z_avg - 0.01:
            variant = "palm"
        elif tip_z_avg > mcp_z_avg + 0.01:
            variant = "back"
        else:
            variant = "palm"

    return True, variant, folded_count


def classify_thumbs_down(hand_landmarks):
    """
    Detect thumbs down gesture.

    Returns:
        is_down (bool), variant (str or None), folded_count (int)
    """
    MIN_FOLDED_FINGERS = 2
    FOLDED_ANGLE_MAX = 120
    MAX_VERTICAL_DEVIATION = 20.0  # degrees from perfect vertical

    lm = hand_landmarks.landmark

    # Thumb down: tip lower (larger y) than MCP + index MCP
    thumb_tip = lm[4]
    thumb_mcp = lm[2]
    index_mcp = lm[5]
    thumb_down = (thumb_tip.y > thumb_mcp.y) and (thumb_tip.y > index_mcp.y)

    # Check if thumb is pointing straight down (within ±10 degrees)
    if thumb_down:
        vertical_angle = calculate_thumb_vertical_angle(thumb_mcp, thumb_tip)
        # For thumbs down, angle should be close to 180° (straight down)
        print(f"[DEBUG] Thumbs DOWN - Vertical angle: {vertical_angle:.2f}°, Max allowed: 180±{MAX_VERTICAL_DEVIATION}°")
        if abs(vertical_angle - 180.0) > MAX_VERTICAL_DEVIATION:
            print(f"[DEBUG] Thumbs DOWN REJECTED - angle {vertical_angle:.2f}° not within 180±{MAX_VERTICAL_DEVIATION}°")
            thumb_down = False

    # Fold detection via angles at PIP joints
    finger_joints = {
        "index": (5, 6, 8),
        "middle": (9, 10, 12),
        "ring": (13, 14, 16),
        "pinky": (17, 18, 20),
    }

    folded = {}
    for name, (mcp_i, pip_i, tip_i) in finger_joints.items():
        a = angle_at(lm[mcp_i], lm[pip_i], lm[tip_i])
        folded[name] = a < FOLDED_ANGLE_MAX

    folded_count = sum(1 for v in folded.values() if v)

    if not thumb_down or folded_count < MIN_FOLDED_FINGERS:
        return False, None, folded_count

    # Orientation: palm / back / fist
    fingertip_ids = [8, 12, 16, 20]
    mcp_ids = [5, 9, 13, 17]
    tip_z_avg = statistics.mean(lm[i].z for i in fingertip_ids)
    mcp_z_avg = statistics.mean(lm[i].z for i in mcp_ids)

    if folded_count >= 3:
        variant = "fist"
    else:
        if tip_z_avg < mcp_z_avg - 0.01:
            variant = "palm"
        elif tip_z_avg > mcp_z_avg + 0.01:
            variant = "back"
        else:
            variant = "palm"

    return True, variant, folded_count


class GestureDetector:
    """Detects hand gestures using MediaPipe Hands."""

    def __init__(self, config: Dict):
        """
        Initialize gesture detector.

        Args:
            config: Gesture configuration dictionary
        """
        self.config = config
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=config.get('min_detection_confidence', 0.4),
            min_tracking_confidence=config.get('min_tracking_confidence', 0.4)
        )

        # Thumbs up tracking
        self.thumbs_up_start_time = None
        self.thumbs_up_last_seen = None
        self.thumbs_up_hold_duration = config.get('thumbs_up_hold_duration', 2.0)
        self.thumbs_up_confirmed = False

        # Thumbs down tracking
        self.thumbs_down_start_time = None
        self.thumbs_down_last_seen = None
        self.thumbs_down_hold_duration = config.get('thumbs_down_hold_duration', 2.0)
        self.thumbs_down_confirmed = False

        # Grace period for brief gesture loss
        self.grace_period = config.get('gesture_loss_grace_seconds', 0.4)

    def detect(self, frame) -> Dict:
        """
        Detect hand gestures in frame.

        Args:
            frame: BGR image from camera

        Returns:
            Dictionary with gesture detection results
        """
        current_time = time.time()

        # Convert BGR to RGB
        rgb_frame = frame[:, :, ::-1]

        # Process frame
        results = self.hands.process(rgb_frame)

        gesture_result = {
            'thumbs_up': False,
            'thumbs_up_held': False,
            'thumbs_up_progress': 0.0,
            'thumbs_down': False,
            'thumbs_down_held': False,
            'thumbs_down_progress': 0.0,
            'hand_detected': False
        }

        thumbs_up_now = False
        thumbs_down_now = False

        if results.multi_hand_landmarks:
            hand_landmarks = results.multi_hand_landmarks[0]
            gesture_result['hand_detected'] = True

            # Detect thumbs up
            is_up, _, _ = classify_thumbs_up(hand_landmarks)
            if is_up:
                thumbs_up_now = True
                gesture_result['thumbs_up'] = True

            # Detect thumbs down
            is_down, _, _ = classify_thumbs_down(hand_landmarks)
            if is_down:
                thumbs_down_now = True
                gesture_result['thumbs_down'] = True

        # Track thumbs up with hold duration and grace period
        if thumbs_up_now:
            if self.thumbs_up_start_time is None:
                self.thumbs_up_start_time = current_time
                self.thumbs_up_last_seen = current_time
                self.thumbs_up_confirmed = False
            else:
                self.thumbs_up_last_seen = current_time

            elapsed = current_time - self.thumbs_up_start_time
            gesture_result['thumbs_up_progress'] = min(1.0, elapsed / self.thumbs_up_hold_duration)

            if not self.thumbs_up_confirmed and elapsed >= self.thumbs_up_hold_duration:
                self.thumbs_up_confirmed = True
                gesture_result['thumbs_up_held'] = True
            elif self.thumbs_up_confirmed:
                gesture_result['thumbs_up_held'] = True
        else:
            # Check grace period
            if self.thumbs_up_last_seen is not None and self.thumbs_up_start_time is not None:
                if current_time - self.thumbs_up_last_seen > self.grace_period:
                    # Reset thumbs up tracking
                    self.thumbs_up_start_time = None
                    self.thumbs_up_last_seen = None
                    self.thumbs_up_confirmed = False
                elif self.thumbs_up_confirmed:
                    # Within grace period and was confirmed
                    gesture_result['thumbs_up_held'] = True

        # Track thumbs down with hold duration and grace period
        if thumbs_down_now:
            if self.thumbs_down_start_time is None:
                self.thumbs_down_start_time = current_time
                self.thumbs_down_last_seen = current_time
                self.thumbs_down_confirmed = False
            else:
                self.thumbs_down_last_seen = current_time

            elapsed = current_time - self.thumbs_down_start_time
            gesture_result['thumbs_down_progress'] = min(1.0, elapsed / self.thumbs_down_hold_duration)

            if not self.thumbs_down_confirmed and elapsed >= self.thumbs_down_hold_duration:
                self.thumbs_down_confirmed = True
                gesture_result['thumbs_down_held'] = True
            elif self.thumbs_down_confirmed:
                gesture_result['thumbs_down_held'] = True
        else:
            # Check grace period
            if self.thumbs_down_last_seen is not None and self.thumbs_down_start_time is not None:
                if current_time - self.thumbs_down_last_seen > self.grace_period:
                    # Reset thumbs down tracking
                    self.thumbs_down_start_time = None
                    self.thumbs_down_last_seen = None
                    self.thumbs_down_confirmed = False
                elif self.thumbs_down_confirmed:
                    # Within grace period and was confirmed
                    gesture_result['thumbs_down_held'] = True

        return gesture_result

    def reset_thumbs_up(self):
        """Reset thumbs up tracking."""
        self.thumbs_up_start_time = None
        self.thumbs_up_last_seen = None
        self.thumbs_up_confirmed = False

    def reset_thumbs_down(self):
        """Reset thumbs down tracking."""
        self.thumbs_down_start_time = None
        self.thumbs_down_last_seen = None
        self.thumbs_down_confirmed = False

    def cleanup(self):
        """Release resources."""
        self.hands.close()
