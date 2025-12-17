# Home Assistant Integration - Implementation Summary

## What Was Done

Successfully integrated Nightwatchman with Home Assistant for remote control, notifications, and video streaming.

---

## Files Created

### 1. **mqtt_client.py** (New)
MQTT client for bidirectional communication with Home Assistant:
- **Publishes**:
  - System state changes (WAITING_FOR_START, ACTIVE_MONITORING, PAUSED)
  - Posture state changes (MONITORING_LYING, SITTING_DETECTED, etc.)
  - Alert events (PERSON_SITTING_UP)
  - Statistics (alert count, uptime, frame count)
- **Subscribes**:
  - Commands from HA (start, stop, pause, resume)

### 2. **http_server.py** (New)
Flask HTTP server for video streaming:
- **Endpoints**:
  - `GET /` - Service info
  - `GET /status` - Server status (JSON)
  - `GET /snapshot` - Single JPEG frame
  - `GET /video_feed` - MJPEG stream (5 FPS, 320x240)
- **Features**:
  - Thread-safe frame updates
  - Configurable resolution and FPS
  - Placeholder image when no frame available
  - CORS enabled for HA access

### 3. **pi_ha_setup.md** (New)
Complete setup guide for Raspberry Pi 5 with:
- Raspberry Pi OS configuration
- Docker-based Home Assistant installation
- Mosquitto MQTT broker setup
- Nightwatchman installation
- Home Assistant YAML configuration
- Mobile app setup instructions
- Testing procedures
- Troubleshooting section

---

## Files Modified

### 1. **main.py**
**Changes**:
- Imported `mqtt_client` and `http_server` modules
- Initialize MQTT client with command callback
- Initialize HTTP server for video streaming
- Added `_handle_mqtt_command()` - queues incoming MQTT commands
- Added `_process_mqtt_command()` - processes start/stop/pause/resume commands
- Updated main loop:
  - Sends each frame to HTTP server for streaming
  - Processes pending MQTT commands
  - Publishes stats to MQTT every 30 seconds
- Updated `_handle_transition()` - publishes posture changes and alerts to MQTT
- Updated `_log_system_state_change()` - publishes system state changes to MQTT
- Updated `_cleanup()` - properly closes MQTT and HTTP connections

**Integration Behavior**:
- MQTT commands and gesture controls have **equal priority**
- **Latest command wins** (whether from gesture or MQTT)
- Both can start, stop, pause, or resume monitoring

### 2. **config.yaml**
**Added Sections**:

```yaml
# MQTT Integration
mqtt:
  enabled: true
  broker: "localhost"
  port: 1883
  username: "nightwatchman"
  password: "nightwatch123"
  topics:
    state: "nightwatchman/state"
    posture: "nightwatchman/posture"
    alert: "nightwatchman/alert"
    stats: "nightwatchman/stats"
    command: "nightwatchman/command"

# HTTP Server
http:
  enabled: true
  host: "0.0.0.0"
  port: 5000
  stream_fps: 5
  stream_width: 320
  stream_height: 240
```

### 3. **requirements.txt**
**Added Dependencies**:
- `paho-mqtt>=1.6.1` - MQTT client library
- `flask>=2.3.0` - HTTP server
- `flask-cors>=4.0.0` - CORS support for HA

### 4. **gesture_detector.py** (Previous Change)
**Modified**: Hand size threshold from 0.08 → 0.15 (15% of frame)

### 5. **system_state.py** (Previous Change)
**Removed**: Posture-based gesture filtering (now uses size-based filtering only)

---

## Home Assistant Integration Features

### Control Panel (HA Dashboard)
- **Sensors**:
  - System State (WAITING_FOR_START / ACTIVE_MONITORING / PAUSED)
  - Posture State (MONITORING_LYING / SITTING_DETECTED / etc.)
  - Alert Count
  - Uptime

- **Control Buttons**:
  - Start Monitoring
  - Stop Monitoring
  - Pause Monitoring
  - Resume Monitoring

- **Camera**:
  - Live video stream (320x240 @ 5 FPS)
  - Snapshot view

### Notifications
All configured in HA YAML (see pi_ha_setup.md):
- Alert when person sits up (with snapshot image)
- State change notifications (start/stop/pause/resume)
- Sent to HA mobile app

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Raspberry Pi 5                          │
│                                                             │
│  ┌──────────────────┐          ┌──────────────────┐        │
│  │  Home Assistant  │          │  Nightwatchman   │        │
│  │    (Docker)      │          │   (Python App)   │        │
│  │                  │          │                  │        │
│  │  - Dashboard     │◄────────►│  - MQTT Client   │        │
│  │  - Automations   │   MQTT   │  - HTTP Server   │        │
│  │  - Notifications │          │  - Camera        │        │
│  └─────────┬────────┘          └─────────┬────────┘        │
│            │                             │                 │
│            │    ┌─────────────────┐      │                 │
│            └───►│    Mosquitto    │◄─────┘                 │
│                 │  MQTT Broker    │                        │
│                 └─────────────────┘                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ Network
                          ▼
               ┌──────────────────────┐
               │   Mobile App (iOS/   │
               │     Android)         │
               │                      │
               │  - Control buttons   │
               │  - Video stream      │
               │  - Notifications     │
               └──────────────────────┘
```

---

## Communication Flow

### 1. **Monitoring Start** (via HA)
```
User taps "Start" in HA app
    ↓
HA publishes: nightwatchman/command = "start"
    ↓
MQTT client receives command
    ↓
main.py processes command, changes state to ACTIVE_MONITORING
    ↓
MQTT client publishes: nightwatchman/state = "ACTIVE_MONITORING"
    ↓
HA updates dashboard
    ↓
HA sends notification: "Monitoring started"
```

### 2. **Alert When Person Sits Up**
```
Person sits up for 3 seconds
    ↓
State machine transitions to ALERT_ACTIVE
    ↓
MQTT client publishes:
  - nightwatchman/posture = "ALERT_ACTIVE"
  - nightwatchman/alert = "PERSON_SITTING_UP"
    ↓
HA automation triggers
    ↓
HA sends push notification to phone with snapshot image
    ↓
User taps notification → Opens camera feed in app
```

### 3. **Video Stream Request**
```
User taps camera in HA app
    ↓
HA requests: http://<pi-ip>:5000/video_feed
    ↓
HTTP server sends MJPEG stream (5 FPS)
    ↓
HA displays live video in app
```

---

## Testing Checklist

After setup, verify:

- [ ] MQTT broker running: `sudo systemctl status mosquitto`
- [ ] HA accessible: `http://<pi-ip>:8123`
- [ ] Nightwatchman connects to MQTT on startup
- [ ] HTTP server accessible: `http://<pi-ip>:5000/status`
- [ ] Snapshot works: `http://<pi-ip>:5000/snapshot`
- [ ] Video stream works: `http://<pi-ip>:5000/video_feed`
- [ ] HA dashboard shows Nightwatchman sensors
- [ ] Start button in HA starts monitoring
- [ ] Stop button in HA stops monitoring
- [ ] Pause/Resume buttons work
- [ ] Mobile app receives notifications
- [ ] Camera view works in mobile app

---

## Next Steps

1. **Follow pi_ha_setup.md** to set up your Pi 5
2. **Test locally first** before deploying
3. **Adjust thresholds** in config.yaml as needed:
   - Hand size threshold (currently 0.15)
   - Sitting detection thresholds
   - Stream FPS and resolution
4. **Create systemd service** for auto-start (see below)
5. **Configure HA automations** for your specific needs

---

## Optional: Create Systemd Service

To run Nightwatchman automatically on boot:

```bash
sudo nano /etc/systemd/system/nightwatchman.service
```

Add:
```ini
[Unit]
Description=Nightwatchman Posture Monitor
After=network.target mosquitto.service docker.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/nightwatchman
ExecStart=/home/pi/nightwatchman/.venv/bin/python /home/pi/nightwatchman/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable nightwatchman
sudo systemctl start nightwatchman
sudo systemctl status nightwatchman
```

View logs:
```bash
sudo journalctl -u nightwatchman -f
```

---

## Configuration Tips

### Lower Bandwidth (if needed)
```yaml
http:
  stream_fps: 3           # Instead of 5
  stream_width: 240       # Instead of 320
  stream_height: 180      # Instead of 240
```

### Disable Features
```yaml
mqtt:
  enabled: false          # Disable MQTT integration

http:
  enabled: false          # Disable video streaming
```

### Change MQTT Topics
```yaml
mqtt:
  topics:
    state: "home/monitor/state"      # Custom topic names
    alert: "home/monitor/alert"
```

---

## Troubleshooting

See **pi_ha_setup.md** section "Troubleshooting" for common issues and solutions.

---

## Summary

**Total Changes**: 3 new files, 5 modified files

**New Capabilities**:
✅ Remote start/stop/pause/resume via HA app
✅ Real-time state monitoring in HA dashboard
✅ Push notifications to mobile device
✅ Live video streaming on-demand
✅ Alert history tracking
✅ Dual control: Gestures OR HA commands (latest wins)

**Ready to deploy!** Follow `pi_ha_setup.md` to get started.
