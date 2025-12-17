# Raspberry Pi 5 + Home Assistant + Nightwatchman Setup Guide

**Target Setup**: Single Raspberry Pi 5 (8GB RAM) running both Home Assistant and Nightwatchman with MQTT integration.

---

## Table of Contents
1. [Raspberry Pi OS Setup](#1-raspberry-pi-os-setup)
2. [Install Home Assistant (Docker)](#2-install-home-assistant-docker)
3. [Install MQTT Broker (Mosquitto)](#3-install-mqtt-broker-mosquitto)
4. [Install Nightwatchman](#4-install-nightwatchman)
5. [Configure Home Assistant](#5-configure-home-assistant)
6. [Setup Mobile App](#6-setup-mobile-app)
7. [Testing & Verification](#7-testing--verification)

---

## 1. Raspberry Pi OS Setup

### Prerequisites
- Raspberry Pi 5 with Raspberry Pi OS (64-bit) installed
- Connected to network (ethernet or WiFi)
- SSH enabled or keyboard/monitor connected

### Initial Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y git python3-pip python3-venv \
    docker.io docker-compose \
    mosquitto mosquitto-clients \
    libcamera-dev python3-libcamera \
    avahi-daemon

# Add user to docker group (to run docker without sudo)
sudo usermod -aG docker $USER

# Reboot to apply group changes
sudo reboot
```

After reboot, verify Docker is working:
```bash
docker --version
docker ps
```

---

## 2. Install Home Assistant (Docker)

### Option A: Home Assistant Container (Recommended for Pi 5)

```bash
# Create directory for HA config
mkdir -p ~/homeassistant

# Run Home Assistant container
docker run -d \
  --name homeassistant \
  --restart=unless-stopped \
  --privileged \
  -e TZ=America/New_York \
  -v ~/homeassistant:/config \
  --network=host \
  ghcr.io/home-assistant/home-assistant:stable
```

**Note**: Change `TZ=America/New_York` to your timezone.

### Verify Installation

```bash
# Check container is running
docker ps | grep homeassistant

# View logs
docker logs -f homeassistant
```

Wait 2-3 minutes, then access Home Assistant:
- Open browser: `http://<PI_IP>:8123`
- Or: `http://homeassistant.local:8123`

### Initial HA Setup (Web UI)
1. Create your account (username, password)
2. Set home location & timezone
3. Skip integrations for now (we'll add them later)
4. Complete onboarding

---

## 3. Install MQTT Broker (Mosquitto)

Mosquitto was already installed in Step 1, now configure it:

### Configure Mosquitto

```bash
# Create password file
sudo mosquitto_passwd -c /etc/mosquitto/passwd nightwatchman
# Enter password when prompted (e.g., "nightwatch123")

# Create config file
sudo nano /etc/mosquitto/conf.d/nightwatchman.conf
```

Add this content:
```
listener 1883
allow_anonymous false
password_file /etc/mosquitto/passwd
```

Save and exit (Ctrl+X, Y, Enter)

### Start Mosquitto

```bash
# Enable and start Mosquitto
sudo systemctl enable mosquitto
sudo systemctl restart mosquitto

# Check status
sudo systemctl status mosquitto
```

### Test MQTT (Optional)

Open two terminals:

**Terminal 1 (Subscribe):**
```bash
mosquitto_sub -h localhost -t test/topic -u nightwatchman -P nightwatch123
```

**Terminal 2 (Publish):**
```bash
mosquitto_pub -h localhost -t test/topic -m "Hello MQTT" -u nightwatchman -P nightwatch123
```

You should see "Hello MQTT" appear in Terminal 1.

---

## 4. Install Nightwatchman

### Clone Repository

```bash
cd ~
git clone https://github.com/YOUR_USERNAME/nightwatchman.git
cd nightwatchman
```

**Note**: If you haven't pushed to GitHub yet, you can copy files manually or use SCP.

### Install Dependencies

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install Python packages
pip install --upgrade pip
pip install -r requirements.txt

# Install additional packages for HA integration
pip install paho-mqtt flask flask-cors
```

### Update requirements.txt

Add these lines to `requirements.txt`:
```bash
echo "paho-mqtt>=1.6.1" >> requirements.txt
echo "flask>=2.3.0" >> requirements.txt
echo "flask-cors>=4.0.0" >> requirements.txt
```

### Configure Nightwatchman

Edit `config.yaml`:
```bash
nano config.yaml
```

Add these sections at the end:

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

# HTTP Server (for video streaming)
http:
  enabled: true
  host: "0.0.0.0"
  port: 5000
  stream_fps: 5
  stream_width: 320
  stream_height: 240
```

Save and exit.

### Get Pi's IP Address

```bash
hostname -I
# Note this IP address (e.g., 192.168.1.100)
```

---

## 5. Configure Home Assistant

### Add MQTT Integration

1. Open Home Assistant: `http://<PI_IP>:8123`
2. Go to **Settings** → **Devices & Services**
3. Click **+ Add Integration**
4. Search for "MQTT"
5. Enter:
   - Broker: `localhost` (or `127.0.0.1`)
   - Port: `1883`
   - Username: `nightwatchman`
   - Password: `nightwatch123`
6. Click **Submit**

### Edit Configuration YAML

```bash
# Edit HA configuration file
nano ~/homeassistant/configuration.yaml
```

Add this content (or merge with existing):

```yaml
# MQTT Sensors and Controls
mqtt:
  sensor:
    # System State
    - name: "Nightwatchman System State"
      state_topic: "nightwatchman/state"
      icon: mdi:monitor-eye

    # Posture State
    - name: "Nightwatchman Posture"
      state_topic: "nightwatchman/posture"
      icon: mdi:human

    # Alert Count
    - name: "Nightwatchman Alert Count"
      state_topic: "nightwatchman/stats"
      value_template: "{{ value_json.alert_count }}"
      icon: mdi:counter

    # Uptime
    - name: "Nightwatchman Uptime"
      state_topic: "nightwatchman/stats"
      value_template: "{{ value_json.uptime }}"
      icon: mdi:clock-outline

  # Control Buttons
  button:
    - name: "Nightwatchman Start"
      command_topic: "nightwatchman/command"
      payload_press: "start"
      icon: mdi:play

    - name: "Nightwatchman Stop"
      command_topic: "nightwatchman/command"
      payload_press: "stop"
      icon: mdi:stop

    - name: "Nightwatchman Pause"
      command_topic: "nightwatchman/command"
      payload_press: "pause"
      icon: mdi:pause

    - name: "Nightwatchman Resume"
      command_topic: "nightwatchman/command"
      payload_press: "resume"
      icon: mdi:play-pause

# Camera for video streaming
camera:
  - platform: generic
    name: Nightwatchman Camera
    still_image_url: "http://localhost:5000/snapshot"
    stream_source: "http://localhost:5000/video_feed"
    framerate: 5

# Automations for notifications
automation:
  # Alert when person sits up
  - alias: "Nightwatchman Person Sitting Alert"
    trigger:
      platform: mqtt
      topic: "nightwatchman/alert"
      payload: "PERSON_SITTING_UP"
    action:
      - service: notify.mobile_app_<YOUR_PHONE>
        data:
          title: "🚨 Nightwatchman Alert"
          message: "Person sitting up detected!"
          data:
            image: "http://<PI_IP>:5000/snapshot"
            tag: "nightwatchman-alert"
            actions:
              - action: "VIEW_CAMERA"
                title: "View Camera"

  # Notify on state changes
  - alias: "Nightwatchman State Change Notification"
    trigger:
      platform: mqtt
      topic: "nightwatchman/state"
    action:
      - service: notify.mobile_app_<YOUR_PHONE>
        data:
          title: "Nightwatchman Status"
          message: "State changed to: {{ trigger.payload }}"
          data:
            tag: "nightwatchman-state"

# Input helpers for UI (optional - for prettier dashboard)
input_select:
  nightwatchman_command:
    name: Nightwatchman Control
    options:
      - Start
      - Stop
      - Pause
      - Resume
    icon: mdi:monitor-eye
```

**Important**:
- Replace `<YOUR_PHONE>` with your actual device name (see Mobile App section)
- Replace `<PI_IP>` with your Pi's IP address

### Restart Home Assistant

```bash
# Restart HA container
docker restart homeassistant

# Or via HA UI: Settings → System → Restart
```

Wait 30 seconds, then refresh your browser.

---

## 6. Setup Mobile App

### Install Home Assistant Companion App

**iOS**: [App Store Link](https://apps.apple.com/app/home-assistant/id1099568401)
**Android**: [Play Store Link](https://play.google.com/store/apps/details?id=io.homeassistant.companion.android)

### Connect App to HA

1. Open the app
2. Tap "Manual Setup" or enter your HA URL:
   - If on same WiFi: `http://<PI_IP>:8123`
   - Or use: `http://homeassistant.local:8123`
3. Login with your HA credentials
4. Allow notifications when prompted
5. Grant location permissions (optional)

### Find Your Device Name

In Home Assistant:
1. Go to **Settings** → **Devices & Services**
2. Click **Mobile App** integration
3. You'll see your device listed (e.g., `mobile_app_johns_iphone`)
4. **Note this name** - you'll need it for notifications

### Update Configuration with Device Name

Edit `~/homeassistant/configuration.yaml` and replace:
```yaml
notify.mobile_app_<YOUR_PHONE>
```

With your actual device name:
```yaml
notify.mobile_app_johns_iphone
```

Restart HA again:
```bash
docker restart homeassistant
```

---

## 7. Testing & Verification

### Test MQTT Connection

```bash
# Subscribe to all nightwatchman topics
mosquitto_sub -h localhost -t "nightwatchman/#" -u nightwatchman -P nightwatch123
```

Leave this running in a terminal.

### Test Camera Access

Open browser:
- Snapshot: `http://<PI_IP>:5000/snapshot`
- Video stream: `http://<PI_IP>:5000/video_feed`

(This won't work until Nightwatchman is updated with integration code - see next steps)

### Create Dashboard in HA

1. Go to **Overview** (home screen)
2. Click **⋮** (three dots) → **Edit Dashboard**
3. Click **+ Add Card**
4. Add these cards:

**Entities Card**:
- Add all Nightwatchman sensors
- Add all Nightwatchman buttons

**Picture Entity Card**:
- Entity: `camera.nightwatchman_camera`
- Tap Action: More info (opens full camera view)

**Example Dashboard Layout**:
```yaml
type: vertical-stack
cards:
  - type: picture-entity
    entity: camera.nightwatchman_camera
    name: Nightwatchman Feed
    show_state: false
  - type: entities
    title: Status
    entities:
      - entity: sensor.nightwatchman_system_state
      - entity: sensor.nightwatchman_posture
      - entity: sensor.nightwatchman_alert_count
      - entity: sensor.nightwatchman_uptime
  - type: horizontal-stack
    cards:
      - type: button
        entity: button.nightwatchman_start
        name: Start
      - type: button
        entity: button.nightwatchman_pause
        name: Pause
      - type: button
        entity: button.nightwatchman_resume
        name: Resume
      - type: button
        entity: button.nightwatchman_stop
        name: Stop
```

---

## Troubleshooting

### Home Assistant not accessible
```bash
# Check if container is running
docker ps | grep homeassistant

# Check logs
docker logs homeassistant

# Restart
docker restart homeassistant
```

### MQTT not working
```bash
# Check Mosquitto status
sudo systemctl status mosquitto

# Check logs
sudo journalctl -u mosquitto -f

# Test connection
mosquitto_pub -h localhost -t test -m "hello" -u nightwatchman -P nightwatch123
```

### Camera not streaming
- Ensure Nightwatchman HTTP server is running (port 5000)
- Check firewall: `sudo ufw status`
- Test URL directly in browser: `http://<PI_IP>:5000/snapshot`

### Notifications not working
- Check device name in Mobile App integration
- Verify notification permissions in phone settings
- Test notification: Developer Tools → Services → `notify.mobile_app_<device>`

---

## Next Steps

**After completing this setup**, you'll need to:

1. **Update Nightwatchman code** to add MQTT and HTTP server functionality
   - I'll create these code changes separately
   - This includes MQTT publishing/subscribing and Flask server

2. **Create systemd service** to run Nightwatchman automatically:
   ```bash
   sudo nano /etc/systemd/system/nightwatchman.service
   ```

3. **Test the full integration** end-to-end

**Ready to proceed with code changes?** Let me know when you've completed this setup and I'll provide the Nightwatchman integration code!

---

## Quick Reference

**Pi IP**: `<YOUR_PI_IP>`
**Home Assistant**: `http://<PI_IP>:8123`
**MQTT Broker**: `localhost:1883`
**MQTT User**: `nightwatchman`
**MQTT Password**: `nightwatch123`
**Video Stream**: `http://<PI_IP>:5000/video_feed`
**Snapshot**: `http://<PI_IP>:5000/snapshot`

**Useful Commands**:
```bash
# Restart Home Assistant
docker restart homeassistant

# View HA logs
docker logs -f homeassistant

# Test MQTT
mosquitto_sub -h localhost -t "nightwatchman/#" -u nightwatchman -P nightwatch123

# Restart Mosquitto
sudo systemctl restart mosquitto
```
