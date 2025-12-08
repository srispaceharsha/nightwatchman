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


def is_hand_deliberately_presented(hand_landmarks):
    """
    Check if hand is deliberately presented to camera (intentional gesture).

    Distinguishes between:
    - Caretaker deliberately showing hand
    - Sleeping person's random hand position

    Uses very lenient checks - main filtering happens via posture state.

    Args:
        hand_landmarks: MediaPipe hand landmarks

    Returns:
        bool: True if hand appears to be deliberately presented
    """
    wrist = hand_landmarks.landmark[0]
    middle_tip = hand_landmarks.landmark[12]

    # Check: Hand size (apparent size indicates proximity)
    # Calculate hand length from wrist to middle fingertip
    hand_length = math.sqrt(
        (middle_tip.x - wrist.x)**2 +
        (middle_tip.y - wrist.y)**2
    )
    is_large_enough = hand_length > 0.08  # Very lenient - just filter tiny distant hands
    print(f"[HAND CHECK] Size: hand_length={hand_length:.3f}, is_large={is_large_enough} (need > 0.08)")

    # Note: Removed strict proximity and position checks
    # Main false-positive prevention happens via posture state filtering

    print(f"[HAND CHECK] Result: {'✓ PASSES' if is_large_enough else '✗ TOO SMALL'}")

    return is_large_enough


def classify_thumbs_up(hand_landmarks):
    """
    Detect thumbs up gesture.

    Returns:
        is_up (bool), variant (str or None), folded_count (int)
    """
    MIN_FOLDED_FINGERS = 2
    FOLDED_ANGLE_MAX = 120

    lm = hand_landmarks.landmark

    print("[THUMBS UP] Checking gesture...")

    # Check if hand is deliberately presented (close to camera, raised up)
    if not is_hand_deliberately_presented(hand_landmarks):
        print("[THUMBS UP] ✗ REJECTED - Hand not deliberately presented")
        return False, None, 0

    # Thumb up: tip higher (smaller y) than MCP + index MCP
    thumb_tip = lm[4]
    thumb_mcp = lm[2]
    index_mcp = lm[5]
    thumb_up = (thumb_tip.y < thumb_mcp.y) and (thumb_tip.y < index_mcp.y)
    print(f"[THUMBS UP] Thumb direction: tip.y={thumb_tip.y:.3f} < mcp.y={thumb_mcp.y:.3f} and < index.y={index_mcp.y:.3f} = {thumb_up}")

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
    print(f"[THUMBS UP] Folded fingers: {folded_count} (need >= {MIN_FOLDED_FINGERS})")

    if not thumb_up:
        print("[THUMBS UP] ✗ REJECTED - Thumb not pointing up")
        return False, None, folded_count

    if folded_count < MIN_FOLDED_FINGERS:
        print(f"[THUMBS UP] ✗ REJECTED - Not enough folded fingers ({folded_count} < {MIN_FOLDED_FINGERS})")
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

    print(f"[THUMBS UP] ✓ DETECTED - variant={variant}, folded={folded_count}")
    return True, variant, folded_count


def classify_thumbs_down(hand_landmarks):
    """
    Detect thumbs down gesture.

    Returns:
        is_down (bool), variant (str or None), folded_count (int)
    """
    MIN_FOLDED_FINGERS = 2
    FOLDED_ANGLE_MAX = 120

    lm = hand_landmarks.landmark

    print("[THUMBS DOWN] Checking gesture...")

    # Check if hand is deliberately presented (close to camera, raised up)
    if not is_hand_deliberately_presented(hand_landmarks):
        print("[THUMBS DOWN] ✗ REJECTED - Hand not deliberately presented")
        return False, None, 0

    # Thumb down: tip lower (larger y) than MCP + index MCP
    thumb_tip = lm[4]
    thumb_mcp = lm[2]
    index_mcp = lm[5]
    thumb_down = (thumb_tip.y > thumb_mcp.y) and (thumb_tip.y > index_mcp.y)
    print(f"[THUMBS DOWN] Thumb direction: tip.y={thumb_tip.y:.3f} > mcp.y={thumb_mcp.y:.3f} and > index.y={index_mcp.y:.3f} = {thumb_down}")

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
    print(f"[THUMBS DOWN] Folded fingers: {folded_count} (need >= {MIN_FOLDED_FINGERS})")

    if not thumb_down:
        print("[THUMBS DOWN] ✗ REJECTED - Thumb not pointing down")
        return False, None, folded_count

    if folded_count < MIN_FOLDED_FINGERS:
        print(f"[THUMBS DOWN] ✗ REJECTED - Not enough folded fingers ({folded_count} < {MIN_FOLDED_FINGERS})")
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

    print(f"[THUMBS DOWN] ✓ DETECTED - variant={variant}, folded={folded_count}")
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
            print("\n[HAND DETECTED] Processing hand landmarks...")

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

            print("")  # Blank line for readability
        else:
            # No hand detected this frame
            pass

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
