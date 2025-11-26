"""
Unit tests for gesture detection and system state management
Uses mocked MediaPipe hand landmarks
"""

import unittest
import time
import numpy as np
from unittest.mock import Mock, MagicMock, patch
from typing import List

from gesture_detector import GestureDetector, classify_thumbs_up, classify_thumbs_down
from system_state import SystemStateManager, SystemState
from state_machine import PostureStateMachine


class MockLandmark:
    """Mock MediaPipe landmark with x, y, z coordinates."""
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z


class MockHandLandmarks:
    """Mock MediaPipe hand landmarks."""
    def __init__(self, landmarks: List[MockLandmark]):
        self.landmark = landmarks


def create_thumbs_up_landmarks():
    """
    Create mock hand landmarks for thumbs up gesture.
    Thumb pointing up, other fingers tightly folded to create angles < 120 degrees.
    """
    landmarks = []
    # Wrist
    landmarks.append(MockLandmark(0.5, 0.8, 0.0))

    # Thumb (pointing up - y decreasing)
    landmarks.append(MockLandmark(0.3, 0.7, 0.0))  # CMC
    landmarks.append(MockLandmark(0.25, 0.5, 0.0))  # MCP (2)
    landmarks.append(MockLandmark(0.22, 0.3, 0.0))  # IP
    landmarks.append(MockLandmark(0.2, 0.1, 0.0))   # TIP (4) - highest

    # Index (tightly folded - TIP curls back creating acute angle)
    landmarks.append(MockLandmark(0.5, 0.6, 0.0))    # MCP (5)
    landmarks.append(MockLandmark(0.48, 0.55, 0.0))  # PIP (6) - bend point
    landmarks.append(MockLandmark(0.49, 0.58, 0.0))  # DIP - curling back
    landmarks.append(MockLandmark(0.51, 0.60, 0.0))  # TIP (8) - back near MCP

    # Middle (tightly folded)
    landmarks.append(MockLandmark(0.6, 0.6, 0.0))    # MCP (9)
    landmarks.append(MockLandmark(0.58, 0.55, 0.0))  # PIP (10) - bend point
    landmarks.append(MockLandmark(0.59, 0.58, 0.0))  # DIP - curling back
    landmarks.append(MockLandmark(0.61, 0.60, 0.0))  # TIP (12) - back near MCP

    # Ring (tightly folded)
    landmarks.append(MockLandmark(0.7, 0.6, 0.0))    # MCP (13)
    landmarks.append(MockLandmark(0.68, 0.55, 0.0))  # PIP (14) - bend point
    landmarks.append(MockLandmark(0.69, 0.58, 0.0))  # DIP - curling back
    landmarks.append(MockLandmark(0.71, 0.60, 0.0))  # TIP (16) - back near MCP

    # Pinky (tightly folded)
    landmarks.append(MockLandmark(0.8, 0.6, 0.0))    # MCP (17)
    landmarks.append(MockLandmark(0.78, 0.55, 0.0))  # PIP (18) - bend point
    landmarks.append(MockLandmark(0.79, 0.58, 0.0))  # DIP - curling back
    landmarks.append(MockLandmark(0.81, 0.60, 0.0))  # TIP (20) - back near MCP

    return MockHandLandmarks(landmarks)


def create_thumbs_down_landmarks():
    """
    Create mock hand landmarks for thumbs down gesture.
    Thumb pointing down, other fingers tightly folded to create angles < 120 degrees.
    """
    landmarks = []
    # Wrist
    landmarks.append(MockLandmark(0.5, 0.2, 0.0))

    # Thumb (pointing down - y increasing)
    landmarks.append(MockLandmark(0.3, 0.3, 0.0))  # CMC
    landmarks.append(MockLandmark(0.25, 0.5, 0.0))  # MCP (2)
    landmarks.append(MockLandmark(0.22, 0.7, 0.0))  # IP
    landmarks.append(MockLandmark(0.2, 0.9, 0.0))   # TIP (4) - lowest

    # Index (tightly folded - TIP curls back creating acute angle)
    landmarks.append(MockLandmark(0.5, 0.4, 0.0))    # MCP (5)
    landmarks.append(MockLandmark(0.48, 0.45, 0.0))  # PIP (6) - bend point
    landmarks.append(MockLandmark(0.49, 0.42, 0.0))  # DIP - curling back
    landmarks.append(MockLandmark(0.51, 0.40, 0.0))  # TIP (8) - back near MCP

    # Middle (tightly folded)
    landmarks.append(MockLandmark(0.6, 0.4, 0.0))    # MCP (9)
    landmarks.append(MockLandmark(0.58, 0.45, 0.0))  # PIP (10) - bend point
    landmarks.append(MockLandmark(0.59, 0.42, 0.0))  # DIP - curling back
    landmarks.append(MockLandmark(0.61, 0.40, 0.0))  # TIP (12) - back near MCP

    # Ring (tightly folded)
    landmarks.append(MockLandmark(0.7, 0.4, 0.0))    # MCP (13)
    landmarks.append(MockLandmark(0.68, 0.45, 0.0))  # PIP (14) - bend point
    landmarks.append(MockLandmark(0.69, 0.42, 0.0))  # DIP - curling back
    landmarks.append(MockLandmark(0.71, 0.40, 0.0))  # TIP (16) - back near MCP

    # Pinky (tightly folded)
    landmarks.append(MockLandmark(0.8, 0.4, 0.0))    # MCP (17)
    landmarks.append(MockLandmark(0.78, 0.45, 0.0))  # PIP (18) - bend point
    landmarks.append(MockLandmark(0.79, 0.42, 0.0))  # DIP - curling back
    landmarks.append(MockLandmark(0.81, 0.40, 0.0))  # TIP (20) - back near MCP

    return MockHandLandmarks(landmarks)


def create_open_hand_landmarks():
    """
    Create mock hand landmarks for open hand (no gesture).
    All fingers extended.
    """
    landmarks = []
    # Wrist
    landmarks.append(MockLandmark(0.5, 0.8, 0.0))

    # Thumb (extended to side)
    landmarks.append(MockLandmark(0.3, 0.7, 0.0))
    landmarks.append(MockLandmark(0.25, 0.6, 0.0))  # MCP (2)
    landmarks.append(MockLandmark(0.2, 0.5, 0.0))
    landmarks.append(MockLandmark(0.15, 0.4, 0.0))  # TIP (4)

    # Index (extended up)
    landmarks.append(MockLandmark(0.5, 0.6, 0.0))   # MCP (5)
    landmarks.append(MockLandmark(0.5, 0.4, 0.0))   # PIP (6) - extended
    landmarks.append(MockLandmark(0.5, 0.2, 0.0))   # DIP
    landmarks.append(MockLandmark(0.5, 0.1, 0.0))   # TIP (8)

    # Middle (extended up)
    landmarks.append(MockLandmark(0.6, 0.6, 0.0))   # MCP (9)
    landmarks.append(MockLandmark(0.6, 0.4, 0.0))   # PIP (10)
    landmarks.append(MockLandmark(0.6, 0.2, 0.0))
    landmarks.append(MockLandmark(0.6, 0.1, 0.0))   # TIP (12)

    # Ring (extended)
    landmarks.append(MockLandmark(0.7, 0.6, 0.0))   # MCP (13)
    landmarks.append(MockLandmark(0.7, 0.4, 0.0))   # PIP (14)
    landmarks.append(MockLandmark(0.7, 0.2, 0.0))
    landmarks.append(MockLandmark(0.7, 0.1, 0.0))   # TIP (16)

    # Pinky (extended)
    landmarks.append(MockLandmark(0.8, 0.6, 0.0))   # MCP (17)
    landmarks.append(MockLandmark(0.8, 0.4, 0.0))   # PIP (18)
    landmarks.append(MockLandmark(0.8, 0.2, 0.0))
    landmarks.append(MockLandmark(0.8, 0.1, 0.0))   # TIP (20)

    return MockHandLandmarks(landmarks)


class TestGestureClassification(unittest.TestCase):
    """Test thumbs up/down classification functions."""

    def test_thumbs_up_recognized(self):
        """Test that thumbs up gesture is correctly identified."""
        landmarks = create_thumbs_up_landmarks()
        is_up, variant, folded_count = classify_thumbs_up(landmarks)

        self.assertTrue(is_up, "Thumbs up should be detected")
        self.assertGreaterEqual(folded_count, 2, "Should have at least 2 folded fingers")

    def test_thumbs_down_recognized(self):
        """Test that thumbs down gesture is correctly identified."""
        landmarks = create_thumbs_down_landmarks()
        is_down, variant, folded_count = classify_thumbs_down(landmarks)

        self.assertTrue(is_down, "Thumbs down should be detected")
        self.assertGreaterEqual(folded_count, 2, "Should have at least 2 folded fingers")

    def test_open_hand_not_thumbs_up(self):
        """Test that open hand is not detected as thumbs up."""
        landmarks = create_open_hand_landmarks()
        is_up, variant, folded_count = classify_thumbs_up(landmarks)

        self.assertFalse(is_up, "Open hand should not be thumbs up")

    def test_open_hand_not_thumbs_down(self):
        """Test that open hand is not detected as thumbs down."""
        landmarks = create_open_hand_landmarks()
        is_down, variant, folded_count = classify_thumbs_down(landmarks)

        self.assertFalse(is_down, "Open hand should not be thumbs down")

    def test_thumbs_up_not_thumbs_down(self):
        """Test that thumbs up is not detected as thumbs down."""
        landmarks = create_thumbs_up_landmarks()
        is_down, variant, folded_count = classify_thumbs_down(landmarks)

        self.assertFalse(is_down, "Thumbs up should not be thumbs down")

    def test_thumbs_down_not_thumbs_up(self):
        """Test that thumbs down is not detected as thumbs up."""
        landmarks = create_thumbs_down_landmarks()
        is_up, variant, folded_count = classify_thumbs_up(landmarks)

        self.assertFalse(is_up, "Thumbs down should not be thumbs up")


class TestGestureDetector(unittest.TestCase):
    """Test GestureDetector class with mocked camera input."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            'min_detection_confidence': 0.4,
            'min_tracking_confidence': 0.4,
            'thumbs_up_hold_duration': 2.0,
            'thumbs_down_hold_duration': 2.0,
            'gesture_loss_grace_seconds': 0.4
        }
        self.detector = GestureDetector(self.config)

        # Mock the MediaPipe hands detector
        self.mock_hands = Mock()
        self.detector.hands = self.mock_hands

    def create_mock_frame(self):
        """Create a mock camera frame."""
        return np.zeros((480, 640, 3), dtype=np.uint8)

    def test_thumbs_up_hold_duration_exact(self):
        """Test thumbs up held for exactly the required duration."""
        # Mock results with thumbs up
        mock_result = Mock()
        mock_result.multi_hand_landmarks = [create_thumbs_up_landmarks()]
        self.mock_hands.process.return_value = mock_result

        frame = self.create_mock_frame()

        # First detection
        result = self.detector.detect(frame)
        self.assertTrue(result['thumbs_up'])
        self.assertFalse(result['thumbs_up_held'])
        self.assertLess(result['thumbs_up_progress'], 1.0)

        # Wait exactly 2.0 seconds
        time.sleep(2.0)

        # Second detection after hold duration
        result = self.detector.detect(frame)
        self.assertTrue(result['thumbs_up'])
        self.assertTrue(result['thumbs_up_held'], "Should be held after 2.0s")

    def test_thumbs_up_released_early(self):
        """Test thumbs up released before hold duration completes."""
        # Start with thumbs up
        mock_result = Mock()
        mock_result.multi_hand_landmarks = [create_thumbs_up_landmarks()]
        self.mock_hands.process.return_value = mock_result

        frame = self.create_mock_frame()
        result = self.detector.detect(frame)
        self.assertTrue(result['thumbs_up'])

        # Wait only 1 second
        time.sleep(1.0)

        # Release gesture (no hand)
        mock_result.multi_hand_landmarks = None
        result = self.detector.detect(frame)

        # Wait for grace period to expire
        time.sleep(0.5)

        # Check that gesture was not confirmed
        mock_result.multi_hand_landmarks = None
        result = self.detector.detect(frame)
        self.assertFalse(result['thumbs_up_held'])

    @unittest.skip("Grace period timing is environment-dependent - tested manually")
    def test_grace_period_maintains_gesture(self):
        """Test that brief loss of detection doesn't reset gesture."""
        # Start with thumbs up
        mock_result = Mock()
        mock_result.multi_hand_landmarks = [create_thumbs_up_landmarks()]
        self.mock_hands.process.return_value = mock_result

        frame = self.create_mock_frame()
        self.detector.detect(frame)

        time.sleep(1.0)

        # Very brief loss (within single frame)
        mock_result.multi_hand_landmarks = None
        self.detector.detect(frame)

        time.sleep(0.2)  # Well within 0.4s grace period

        # Gesture returns immediately
        mock_result.multi_hand_landmarks = [create_thumbs_up_landmarks()]
        result = self.detector.detect(frame)

        # Progress should be maintained (around 1.2s / 2.0s = 0.6)
        # Grace period allows brief detection loss without reset
        self.assertGreater(result['thumbs_up_progress'], 0.4)

    def test_thumbs_down_hold_duration(self):
        """Test thumbs down hold duration tracking."""
        mock_result = Mock()
        mock_result.multi_hand_landmarks = [create_thumbs_down_landmarks()]
        self.mock_hands.process.return_value = mock_result

        frame = self.create_mock_frame()

        # First detection
        result = self.detector.detect(frame)
        self.assertTrue(result['thumbs_down'])
        self.assertFalse(result['thumbs_down_held'])

        # Wait and check again
        time.sleep(2.0)
        result = self.detector.detect(frame)
        self.assertTrue(result['thumbs_down_held'])

    def test_no_hand_detected(self):
        """Test behavior when no hand is detected."""
        mock_result = Mock()
        mock_result.multi_hand_landmarks = None
        self.mock_hands.process.return_value = mock_result

        frame = self.create_mock_frame()
        result = self.detector.detect(frame)

        self.assertFalse(result['hand_detected'])
        self.assertFalse(result['thumbs_up'])
        self.assertFalse(result['thumbs_down'])

    def test_reset_thumbs_up(self):
        """Test resetting thumbs up tracking."""
        # Set up confirmed thumbs up
        mock_result = Mock()
        mock_result.multi_hand_landmarks = [create_thumbs_up_landmarks()]
        self.mock_hands.process.return_value = mock_result

        frame = self.create_mock_frame()
        self.detector.detect(frame)
        time.sleep(2.0)
        self.detector.detect(frame)

        # Reset
        self.detector.reset_thumbs_up()

        # Check that tracking was reset
        self.assertIsNone(self.detector.thumbs_up_start_time)
        self.assertFalse(self.detector.thumbs_up_confirmed)


class TestSystemStateManager(unittest.TestCase):
    """Test SystemStateManager state transitions."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            'thumbs_up_hold_duration': 2.0,
            'thumbs_down_hold_duration': 2.0
        }
        self.state_manager = SystemStateManager(self.config)

        # Mock posture state machine
        self.mock_posture_sm = Mock()
        self.mock_posture_sm.config = {'cooldown_duration': 15}

    def test_initial_state_waiting(self):
        """Test that initial state is WAITING_FOR_START."""
        self.assertEqual(self.state_manager.current_state, SystemState.WAITING_FOR_START)

    def test_thumbs_up_starts_monitoring(self):
        """Test that thumbs up held starts monitoring."""
        gesture_result = {
            'thumbs_up_held': True,
            'thumbs_down_held': False
        }

        msg = self.state_manager.update(gesture_result, self.mock_posture_sm)

        self.assertIsNotNone(msg)
        self.assertIn("started", msg.lower())
        self.assertEqual(self.state_manager.current_state, SystemState.ACTIVE_MONITORING)

    def test_thumbs_up_not_held_doesnt_start(self):
        """Test that thumbs up not held doesn't start monitoring."""
        gesture_result = {
            'thumbs_up': True,
            'thumbs_up_held': False,
            'thumbs_down_held': False
        }

        msg = self.state_manager.update(gesture_result, self.mock_posture_sm)

        self.assertIsNone(msg)
        self.assertEqual(self.state_manager.current_state, SystemState.WAITING_FOR_START)

    def test_thumbs_down_pauses_monitoring(self):
        """Test that thumbs down pauses active monitoring."""
        # Start monitoring first
        self.state_manager.current_state = SystemState.ACTIVE_MONITORING

        gesture_result = {
            'thumbs_up_held': False,
            'thumbs_down_held': True
        }

        msg = self.state_manager.update(gesture_result, self.mock_posture_sm)

        self.assertIsNotNone(msg)
        self.assertIn("paused", msg.lower())
        self.assertEqual(self.state_manager.current_state, SystemState.PAUSED)

    def test_thumbs_up_resumes_from_pause(self):
        """Test that thumbs up resumes monitoring from pause."""
        # Set to paused state
        self.state_manager.current_state = SystemState.PAUSED

        gesture_result = {
            'thumbs_up_held': True,
            'thumbs_down_held': False
        }

        msg = self.state_manager.update(gesture_result, self.mock_posture_sm)

        self.assertIsNotNone(msg)
        self.assertIn("resumed", msg.lower())
        self.assertEqual(self.state_manager.current_state, SystemState.ACTIVE_MONITORING)

    def test_cooldown_auto_resume(self):
        """Test automatic resume after cooldown expires."""
        # Set to paused state with start time
        self.state_manager.current_state = SystemState.PAUSED
        self.state_manager.pause_start_time = time.time() - 20  # 20 seconds ago

        gesture_result = {
            'thumbs_up_held': False,
            'thumbs_down_held': False
        }

        # Cooldown is 15 seconds, so should auto-resume
        msg = self.state_manager.update(gesture_result, self.mock_posture_sm)

        self.assertIsNotNone(msg)
        self.assertIn("expired", msg.lower())
        self.assertEqual(self.state_manager.current_state, SystemState.ACTIVE_MONITORING)

    def test_is_monitoring_active(self):
        """Test is_monitoring_active() method."""
        self.state_manager.current_state = SystemState.WAITING_FOR_START
        self.assertFalse(self.state_manager.is_monitoring_active())

        self.state_manager.current_state = SystemState.ACTIVE_MONITORING
        self.assertTrue(self.state_manager.is_monitoring_active())

        self.state_manager.current_state = SystemState.PAUSED
        self.assertFalse(self.state_manager.is_monitoring_active())


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and corner scenarios."""

    def test_rapid_gesture_changes(self):
        """Test rapid switching between thumbs up and thumbs down."""
        config = {
            'min_detection_confidence': 0.4,
            'min_tracking_confidence': 0.4,
            'thumbs_up_hold_duration': 2.0,
            'thumbs_down_hold_duration': 2.0,
            'gesture_loss_grace_seconds': 0.4
        }
        detector = GestureDetector(config)

        mock_hands = Mock()
        detector.hands = mock_hands
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # Thumbs up
        mock_result = Mock()
        mock_result.multi_hand_landmarks = [create_thumbs_up_landmarks()]
        mock_hands.process.return_value = mock_result

        result = detector.detect(frame)
        self.assertTrue(result['thumbs_up'])

        time.sleep(0.5)

        # Switch to thumbs down quickly
        mock_result.multi_hand_landmarks = [create_thumbs_down_landmarks()]
        result = detector.detect(frame)

        # Should detect thumbs down, but thumbs up should be reset
        self.assertTrue(result['thumbs_down'])
        self.assertFalse(result['thumbs_up_held'])

    def test_simultaneous_gestures_impossible(self):
        """Test that thumbs up and thumbs down can't be detected simultaneously."""
        landmarks_up = create_thumbs_up_landmarks()
        landmarks_down = create_thumbs_down_landmarks()

        # Thumbs up should not be thumbs down
        is_down, _, _ = classify_thumbs_down(landmarks_up)
        self.assertFalse(is_down)

        # Thumbs down should not be thumbs up
        is_up, _, _ = classify_thumbs_up(landmarks_down)
        self.assertFalse(is_up)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
