"""
System State Manager - High-level control flow for gesture-based monitoring
"""

from enum import Enum
import time
from typing import Optional, Dict


class SystemState(Enum):
    """System-level states for monitoring control."""
    WAITING_FOR_START = "WAITING_FOR_START"  # Waiting for thumbs up to begin
    ACTIVE_MONITORING = "ACTIVE_MONITORING"  # Normal monitoring active
    PAUSED = "PAUSED"                        # Monitoring paused by wave gesture


class SystemStateManager:
    """Manages high-level system state based on gesture controls."""

    def __init__(self, config: Dict):
        """
        Initialize system state manager.

        Args:
            config: Gesture configuration dictionary
        """
        self.config = config
        self.current_state = SystemState.WAITING_FOR_START
        self.pause_start_time = None

    def update(self, gesture_result: Dict, posture_state_machine) -> Optional[str]:
        """
        Update system state based on gestures and posture state.

        Args:
            gesture_result: Dictionary from GestureDetector
            posture_state_machine: The posture monitoring state machine

        Returns:
            Status message if state changed, None otherwise
        """
        from state_machine import State

        old_state = self.current_state

        # During WAITING_FOR_START, allow gestures regardless of posture
        # (so caretaker can start monitoring even while person is lying down)
        if self.current_state != SystemState.WAITING_FOR_START:
            # After started, only process gestures when person is sitting up or standing
            # Ignore gestures when lying down to prevent false positives from sleeping person
            posture_state = posture_state_machine.current_state
            gesture_enabled_states = [
                State.SITTING_DETECTED,
                State.ALERT_ACTIVE,
                State.ALERT_COOLDOWN
            ]

            # If person is lying down, ignore all gestures
            if posture_state not in gesture_enabled_states:
                # Don't process gestures when person is lying/restless
                if gesture_result.get('hand_detected', False):
                    print(f"[GESTURE FILTER] Ignoring gestures - person is {posture_state.value} (need sitting/standing)")
                return None

        if self.current_state == SystemState.WAITING_FOR_START:
            # Wait for thumbs up to start (must be held)
            if gesture_result.get('thumbs_up_held', False):
                self.current_state = SystemState.ACTIVE_MONITORING
                return "👍 Thumbs up held! Monitoring started."

        elif self.current_state == SystemState.ACTIVE_MONITORING:
            # Check for thumbs down gesture to pause (must be held)
            if gesture_result.get('thumbs_down_held', False):
                self.current_state = SystemState.PAUSED
                self.pause_start_time = time.time()
                # Get cooldown duration from posture state machine
                from state_machine import State
                cooldown_duration = posture_state_machine.config['cooldown_duration']
                return f"👎 Thumbs down held! Monitoring paused for {cooldown_duration}s."

        elif self.current_state == SystemState.PAUSED:
            # Check for thumbs up to resume (must be held)
            if gesture_result.get('thumbs_up_held', False):
                self.current_state = SystemState.ACTIVE_MONITORING
                self.pause_start_time = None
                return "👍 Thumbs up held! Monitoring resumed."

            # Check if cooldown period expired
            if self.pause_start_time is not None:
                from state_machine import State
                cooldown_duration = posture_state_machine.config['cooldown_duration']
                elapsed = time.time() - self.pause_start_time
                if elapsed >= cooldown_duration:
                    self.current_state = SystemState.ACTIVE_MONITORING
                    self.pause_start_time = None
                    return f"⏰ Pause period ({cooldown_duration}s) expired. Monitoring resumed."

        return None

    def is_monitoring_active(self) -> bool:
        """
        Check if monitoring should be active.

        Returns:
            True if in ACTIVE_MONITORING state
        """
        return self.current_state == SystemState.ACTIVE_MONITORING

    def get_pause_remaining(self) -> Optional[float]:
        """
        Get remaining pause time in seconds.

        Returns:
            Remaining seconds, or None if not paused
        """
        if self.current_state != SystemState.PAUSED or self.pause_start_time is None:
            return None

        # This will be set from the state machine config
        # For now, return a placeholder
        return 0.0

    def get_state_display(self) -> str:
        """
        Get human-readable state description.

        Returns:
            State description string
        """
        if self.current_state == SystemState.WAITING_FOR_START:
            return "WAITING FOR START (show thumbs up 👍)"
        elif self.current_state == SystemState.ACTIVE_MONITORING:
            return "ACTIVE MONITORING (thumbs down to pause 👎)"
        elif self.current_state == SystemState.PAUSED:
            return "PAUSED (thumbs up to resume 👍)"
        return self.current_state.value
