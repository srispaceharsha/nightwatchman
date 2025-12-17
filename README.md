# Nightwatchman - Features & Workflow Guide

## Overview

Nightwatchman (SeniorCare Posture Monitor) is a computer vision-based monitoring system that watches a person lying down and alerts caretakers when the person sits up. The system uses MediaPipe for pose and hand gesture detection.

**Primary Use Case**: Monitor elderly or care-dependent individuals who are lying down and need assistance when they sit up.

## Core Features

### 1. Posture Monitoring
- **Real-time pose detection** using MediaPipe Pose landmarks
- **Automatic posture classification**: LYING, SITTING, PROPPED, TRANSITIONING
- **Persistence timer**: Alerts only trigger after person maintains sitting posture for configured duration
- **Auto-dismiss**: Alert automatically dismisses when person lies back down
- **Cooldown period**: After alert dismissal, system enters cooldown to prevent repeated alerts

### 2. Gesture Controls
- **Thumbs Up**: Start/Resume monitoring
- **Thumbs Down**: Pause monitoring temporarily
- **Hold duration requirement**: Gestures must be held for 2 seconds to prevent accidental triggers
- **Grace period**: Brief gesture loss (0.4s) doesn't reset hold timer
- **Hand deliberateness check**: Filters out random hand positions from sleeping person

### 3. System States
- **WAITING_FOR_START**: Initial state, waiting for thumbs up to begin
- **ACTIVE_MONITORING**: System actively monitoring posture
- **PAUSED**: Monitoring paused by thumbs down gesture

### 4. Posture States
- **MONITORING_LYING**: Person is lying down (normal state)
- **RESTLESS_MOVEMENT**: Person moving but not sitting
- **SITTING_DETECTED**: Person sitting up, persistence timer running
- **ALERT_ACTIVE**: Alert triggered, person has been sitting for configured duration
- **ALERT_COOLDOWN**: Alert dismissed, cooldown period active

### 5. Additional Features
- **Audio alerts**: Plays system sound (3 dings) when alert triggers
- **Camera overlay**: Shows skeleton and system/posture state on video feed
- **Logging**: Timestamped logs of all state transitions and events
- **Configurable parameters**: All thresholds, timers, and detection settings via YAML config
- **Frame rate control**: Configurable processing FPS to balance performance/accuracy

## System Workflow

```
[Camera Input]
    |
    v
[Gesture Detection] --> [System State Manager] --> Controls monitoring on/off
    |                                                         |
    v                                                         v
[Pose Detection] <-- Only active when monitoring is ON
    |
    v
[Metrics Calculation]
    |
    v
[Posture State Machine] --> Triggers alerts
    |
    v
[Actions: Audio Alert, Logging, Display]
```

### Detailed Workflow

1. **Initialization**
   - Load config.yaml
   - Initialize camera and MediaPipe models
   - System starts in WAITING_FOR_START state

2. **Gesture Control Loop** (Always Active)
   - Detect hand gestures in each frame
   - Update system state based on gestures
   - Thumbs up (held 2s) → Start/Resume monitoring
   - Thumbs down (held 2s) → Pause monitoring

3. **Posture Monitoring Loop** (Only when ACTIVE_MONITORING)
   - Detect pose landmarks (shoulders, hips)
   - Calculate torso angle and vertical difference
   - Classify posture (LYING/SITTING/PROPPED/TRANSITIONING)
   - Update state machine
   - Trigger actions based on state transitions

4. **State Transitions**
   - MONITORING_LYING → RESTLESS_MOVEMENT (when movement detected)
   - RESTLESS_MOVEMENT → SITTING_DETECTED (when sitting posture detected)
   - SITTING_DETECTED → ALERT_ACTIVE (after persistence timer expires)
   - ALERT_ACTIVE → ALERT_COOLDOWN (when person lies back down)
   - ALERT_COOLDOWN → MONITORING_LYING (after cooldown period expires)

## Gesture Detection Algorithm

### Thumbs Up Detection

**Criteria**:
1. **Hand Deliberateness Check**:
   - Hand size > 0.15 (15% of frame - filters distant/small hands)

2. **Thumb Orientation**:
   - Thumb tip Y < Thumb MCP Y (tip higher than base)
   - Thumb tip Y < Index MCP Y (thumb pointing upward)

3. **Finger Folding**:
   - At least 2 fingers folded (angle at PIP joint < 120°)
   - Checks index, middle, ring, pinky fingers

4. **Hold Duration**:
   - Gesture must be continuously detected for 2 seconds
   - Grace period: 0.4s loss of detection doesn't reset timer

**Variant Classification**:
- **Fist**: 3+ fingers folded
- **Palm**: Fingertips Z < MCP Z (palm facing camera)
- **Back**: Fingertips Z > MCP Z (back of hand facing camera)

### Thumbs Down Detection

Same algorithm as thumbs up, but with inverted thumb direction:
- Thumb tip Y > Thumb MCP Y (tip lower than base)
- Thumb tip Y > Index MCP Y (thumb pointing downward)

### Gesture Filtering

**Size-Based Filtering**: Gestures are filtered based on hand size in the frame. Hand must be at least 15% of frame size (wrist to middle fingertip). This prevents false positives from a sleeping person's distant hands while allowing caregivers to control the system at any time.

**How It Works**:
- **Caregiver** standing near camera with hand raised → Hand appears large (>15%) → ✅ Gesture accepted
- **Sleeping person** lying far from camera → Hand appears small (<15%) → ✗ Gesture rejected

## Posture Detection Algorithm

### Step 1: Landmark Extraction
Uses MediaPipe Pose to extract 4 key landmarks:
- Left Shoulder
- Right Shoulder
- Left Hip
- Right Hip

### Step 2: Metrics Calculation

**Torso Angle**:
- Calculate midpoint of shoulders and hips
- Compute vector from hip midpoint to shoulder midpoint
- Calculate angle using atan2(torso_y, torso_x)
- Normalize to 0-180° range

**Vertical Difference**:
- Difference between hip Y and shoulder Y
- Positive when hips are below shoulders (sitting/standing)
- Near zero when lying flat

**Smoothing**:
- 3-frame moving average to reduce jitter
- Applies to both angle and vertical difference

### Step 3: Posture Classification

**Priority 1 - Nearly Flat Check**:
- If |vertical_diff| < 0.10 → **LYING**
- This handles rolling side-to-side while lying down

**Priority 2 - Sitting Check**:
- Angle: 70-115°
- Vertical diff > 0.15
- Result: **SITTING**

**Priority 3 - Propped Check**:
- Angle: 30-60°
- Vertical diff > 0.08
- Result: **PROPPED**

**Priority 4 - Lying Angle Ranges**:
- Angle in [0-25°] or [155-180°]
- Result: **LYING**

**Fallback**:
- Everything else → **TRANSITIONING**

### Hysteresis

To reduce state oscillation, the system applies hysteresis when in stable states:
- **Angle buffer**: ±10° tolerance
- **Vertical diff buffer**: ±0.05 tolerance

When in SITTING or LYING state, the system requires a stronger change to transition out.

## State Machine Logic

### State: MONITORING_LYING
**Entry**: Person is lying down
**Behavior**: Monitor for any movement
**Transitions**:
- Movement detected (posture != LYING) → RESTLESS_MOVEMENT

### State: RESTLESS_MOVEMENT
**Entry**: Person moving but not sitting
**Behavior**: Track posture changes
**Transitions**:
- Sitting posture detected → SITTING_DETECTED
- Returned to lying → MONITORING_LYING

### State: SITTING_DETECTED
**Entry**: Person detected in sitting posture
**Behavior**:
- Start persistence timer (default: 10 seconds)
- Continue monitoring posture
**Transitions**:
- Timer expires → ALERT_ACTIVE
- Person lies back down → MONITORING_LYING
- Posture changes (not sitting/lying) → RESTLESS_MOVEMENT

### State: ALERT_ACTIVE
**Entry**: Person has been sitting for persistence duration
**Behavior**:
- Play audio alert (3 dings)
- Display alert message
- Increment alert counter
**Transitions**:
- Person lies back down → ALERT_COOLDOWN

### State: ALERT_COOLDOWN
**Entry**: Person dismissed alert by lying down
**Behavior**:
- Wait for cooldown period (default: 15 minutes)
- Prevents repeated alerts for same incident
**Transitions**:
- Cooldown expires + lying → MONITORING_LYING
- Cooldown expires + not lying → RESTLESS_MOVEMENT

## Key Configuration Parameters

### Detection Thresholds
- `confidence_threshold`: 0.5 (minimum pose detection confidence)
- `sitting_angle_min/max`: 70°-115° (sitting angle range)
- `sitting_vertical_diff`: 0.15 (minimum vertical separation for sitting)
- `propped_angle_min/max`: 30°-60° (propped up angle range)
- `propped_vertical_diff`: 0.08 (minimum vertical separation for propped)

### Timing
- `persistence_duration`: 10s (how long sitting must persist to trigger alert)
- `cooldown_duration`: 900s (15 minutes cooldown after alert)
- `thumbs_up_hold_duration`: 2.0s (how long to hold thumbs up)
- `thumbs_down_hold_duration`: 2.0s (how long to hold thumbs down)
- `gesture_loss_grace_seconds`: 0.4s (grace period for brief gesture loss)

### Camera
- `device_id`: 0 (camera index)
- `resolution_width/height`: 1280x720
- `processing_fps`: 30 (frames per second to process)

### Gesture Detection
- `min_detection_confidence`: 0.4 (MediaPipe hands confidence)
- `min_tracking_confidence`: 0.4 (MediaPipe hands tracking)

## File Structure

```
nightwatchman/
├── main.py                  # Main entry point and orchestration
├── pose_detector.py         # MediaPipe Pose wrapper
├── metrics_calculator.py    # Torso angle and posture classification
├── state_machine.py         # 5-state posture FSM
├── gesture_detector.py      # Hand gesture detection
├── system_state.py          # High-level system state management
├── test_gestures.py         # Unit tests for gestures
└── config.yaml             # Configuration parameters
```

## Testing

The project includes comprehensive unit tests for gesture detection:
- Mock hand landmark generation
- Thumbs up/down recognition tests
- Hold duration and grace period tests
- State transition tests
- Edge case handling

Run tests: `python -m pytest test_gestures.py`

## Usage

```bash
# Start monitoring with default config
python main.py

# Start with custom config
python main.py --config custom_config.yaml

# Controls:
# - Show thumbs up (hold 2s) to start/resume monitoring
# - Show thumbs down (hold 2s) to pause monitoring
# - Press 'q' in camera window to quit
```

## Logging

The system logs all events to timestamped log files:
- State transitions
- Gesture detections
- Timer events
- Alert triggers

Log format: `YYYY-MM-DD HH:MM:SS.mmm | TYPE | Message`

Types: SYSTEM, GESTURE, TRANSITION, TIMER, ALERT, DETECTION
