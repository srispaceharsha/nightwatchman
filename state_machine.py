"""
State Machine - 5-state posture monitoring FSM
"""

import time
from enum import Enum
from typing import Dict, Optional, List


class State(Enum):
    """5 core states for posture monitoring."""
    MONITORING_LYING = "MONITORING_LYING"
    RESTLESS_MOVEMENT = "RESTLESS_MOVEMENT"
    SITTING_DETECTED = "SITTING_DETECTED"
    ALERT_ACTIVE = "ALERT_ACTIVE"
    ALERT_COOLDOWN = "ALERT_COOLDOWN"


class StateTransition:
    """Represents a state transition event."""

    def __init__(self, from_state: State, to_state: State, metrics: Dict, reason: str = ""):
        self.timestamp = time.time()
        self.from_state = from_state
        self.to_state = to_state
        self.metrics = metrics
        self.reason = reason


class PostureStateMachine:
    """Manages state transitions for posture monitoring."""

    def __init__(self, config: Dict):
        """
        Initialize state machine.

        Args:
            config: Detection configuration dictionary
        """
        self.config = config
        self.current_state = State.MONITORING_LYING
        self.previous_state = None

        # Timers
        self.state_entry_time = time.time()
        self.persistence_timer_start = None
        self.cooldown_end_time = None

        # History
        self.transitions: List[StateTransition] = []

    def update(self, metrics: Optional[Dict]) -> Optional[StateTransition]:
        """
        Update state machine with new metrics.

        Args:
            metrics: Dictionary with posture metrics (angle, vertical_diff, confidence, posture)

        Returns:
            StateTransition if state changed, None otherwise
        """
        if metrics is None:
            # No detection - for now just stay in current state
            # (We're skipping PERSON_ABSENT state in this version)
            return None

        current_time = time.time()
        old_state = self.current_state
        posture = metrics['posture']
        confidence = metrics['confidence']

        # Check confidence threshold
        if confidence < self.config['confidence_threshold']:
            # For now, just stay in current state if confidence is low
            # (We're skipping DETECTION_UNCERTAIN state in this version)
            return None

        # State transition logic
        new_state = self._determine_next_state(posture, current_time)

        if new_state != old_state:
            transition = self._transition_to(new_state, metrics)
            return transition

        return None

    def _determine_next_state(self, posture: str, current_time: float) -> State:
        """
        Determine the next state based on current state and posture.

        Args:
            posture: Current posture classification
            current_time: Current timestamp

        Returns:
            Next state
        """
        if self.current_state == State.MONITORING_LYING:
            # Transition to RESTLESS_MOVEMENT if any non-lying posture detected
            if posture != 'LYING':
                return State.RESTLESS_MOVEMENT
            return State.MONITORING_LYING

        elif self.current_state == State.RESTLESS_MOVEMENT:
            # If sitting posture detected, move to SITTING_DETECTED
            if posture == 'SITTING':
                return State.SITTING_DETECTED

            # If reverted to lying, go back to MONITORING_LYING
            if posture == 'LYING':
                return State.MONITORING_LYING

            # Otherwise stay in RESTLESS_MOVEMENT
            return State.RESTLESS_MOVEMENT

        elif self.current_state == State.SITTING_DETECTED:
            # Check persistence timer
            if self.persistence_timer_start is not None:
                elapsed = current_time - self.persistence_timer_start
                if elapsed >= self.config['persistence_duration']:
                    # Timer completed - trigger alert
                    return State.ALERT_ACTIVE

            # If person reverted to lying before timer completed
            if posture == 'LYING':
                return State.MONITORING_LYING

            # If posture changed to something other than sitting or lying
            if posture != 'SITTING':
                return State.RESTLESS_MOVEMENT

            # Stay in SITTING_DETECTED while timer runs
            return State.SITTING_DETECTED

        elif self.current_state == State.ALERT_ACTIVE:
            # Auto-dismiss if person lies back down
            if posture == 'LYING':
                return State.ALERT_COOLDOWN

            # Otherwise stay in ALERT_ACTIVE
            return State.ALERT_ACTIVE

        elif self.current_state == State.ALERT_COOLDOWN:
            # Check if cooldown period has elapsed
            if self.cooldown_end_time is not None:
                if current_time >= self.cooldown_end_time:
                    # Cooldown complete
                    if posture == 'LYING':
                        return State.MONITORING_LYING
                    else:
                        return State.RESTLESS_MOVEMENT

            # Stay in cooldown
            return State.ALERT_COOLDOWN

        return self.current_state

    def _transition_to(self, new_state: State, metrics: Dict) -> StateTransition:
        """
        Transition to a new state.

        Args:
            new_state: State to transition to
            metrics: Current metrics

        Returns:
            StateTransition object
        """
        current_time = time.time()
        old_state = self.current_state

        # Create transition record
        transition = StateTransition(old_state, new_state, metrics)

        # Handle state-specific entry logic
        if new_state == State.SITTING_DETECTED:
            # Start persistence timer
            self.persistence_timer_start = current_time

        elif new_state == State.ALERT_ACTIVE:
            # Alert triggered
            self.persistence_timer_start = None

        elif new_state == State.ALERT_COOLDOWN:
            # Start cooldown period
            self.cooldown_end_time = current_time + self.config['cooldown_duration']

        elif new_state == State.MONITORING_LYING:
            # Reset timers
            self.persistence_timer_start = None

        elif new_state == State.RESTLESS_MOVEMENT:
            # Cancel any persistence timer
            self.persistence_timer_start = None

        # Update state
        self.previous_state = old_state
        self.current_state = new_state
        self.state_entry_time = current_time

        # Record transition
        self.transitions.append(transition)

        return transition

    def get_state_duration(self) -> float:
        """Get time elapsed in current state."""
        return time.time() - self.state_entry_time

    def get_persistence_timer_elapsed(self) -> Optional[float]:
        """Get elapsed time on persistence timer, or None if not running."""
        if self.persistence_timer_start is None:
            return None
        return time.time() - self.persistence_timer_start

    def get_cooldown_remaining(self) -> Optional[float]:
        """Get remaining cooldown time, or None if not in cooldown."""
        if self.cooldown_end_time is None:
            return None
        remaining = self.cooldown_end_time - time.time()
        return max(0, remaining)

    def get_expected_posture_for_hysteresis(self) -> Optional[str]:
        """
        Get the posture that should be used for hysteresis based on current state.

        Returns:
            Posture string for hysteresis, or None if no hysteresis needed
        """
        # Apply hysteresis when in SITTING_DETECTED to reduce jitter
        if self.current_state == State.SITTING_DETECTED:
            return 'SITTING'
        elif self.current_state == State.MONITORING_LYING:
            return 'LYING'
        # No hysteresis for other states
        return None
