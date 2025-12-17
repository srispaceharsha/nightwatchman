"""
MQTT Client - Home Assistant Integration
Publishes state changes and subscribes to commands
"""

import paho.mqtt.client as mqtt
import json
import time
from typing import Dict, Callable, Optional
from datetime import datetime


class MQTTClient:
    """MQTT client for Home Assistant integration."""

    def __init__(self, config: Dict, command_callback: Callable[[str], None]):
        """
        Initialize MQTT client.

        Args:
            config: MQTT configuration from config.yaml
            command_callback: Function to call when command received
        """
        self.config = config
        self.command_callback = command_callback
        self.client = None
        self.connected = False
        self.start_time = time.time()

        if not config.get('enabled', False):
            print("MQTT integration disabled in config")
            return

        # Extract config
        self.broker = config['broker']
        self.port = config['port']
        self.username = config.get('username')
        self.password = config.get('password')
        self.topics = config['topics']

        # Initialize client
        self._setup_client()

    def _setup_client(self):
        """Setup MQTT client with callbacks."""
        self.client = mqtt.Client(client_id="nightwatchman")

        # Set username/password if provided
        if self.username and self.password:
            self.client.username_pw_set(self.username, self.password)

        # Set callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

        # Connect to broker
        try:
            print(f"Connecting to MQTT broker at {self.broker}:{self.port}...")
            self.client.connect(self.broker, self.port, keepalive=60)
            self.client.loop_start()
        except Exception as e:
            print(f"Failed to connect to MQTT broker: {e}")
            self.connected = False

    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to broker."""
        if rc == 0:
            print("✓ Connected to MQTT broker")
            self.connected = True

            # Subscribe to command topic
            command_topic = self.topics['command']
            self.client.subscribe(command_topic)
            print(f"✓ Subscribed to: {command_topic}")

            # Publish initial state
            self.publish_state("INITIALIZING")
        else:
            print(f"✗ Failed to connect to MQTT broker. Return code: {rc}")
            self.connected = False

    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from broker."""
        self.connected = False
        if rc != 0:
            print(f"✗ Unexpected MQTT disconnection. Code: {rc}")
            print("  Attempting to reconnect...")

    def _on_message(self, client, userdata, msg):
        """Callback when message received."""
        try:
            command = msg.payload.decode('utf-8').strip().lower()
            print(f"[MQTT] Received command: {command}")

            # Validate command
            valid_commands = ['start', 'stop', 'pause', 'resume']
            if command in valid_commands:
                self.command_callback(command)
            else:
                print(f"[MQTT] Unknown command: {command}")

        except Exception as e:
            print(f"[MQTT] Error processing message: {e}")

    def publish_state(self, state: str):
        """
        Publish system state.

        Args:
            state: System state (WAITING_FOR_START, ACTIVE_MONITORING, PAUSED)
        """
        if not self.connected:
            return

        topic = self.topics['state']
        try:
            self.client.publish(topic, state, retain=True)
            print(f"[MQTT] Published state: {state}")
        except Exception as e:
            print(f"[MQTT] Failed to publish state: {e}")

    def publish_posture(self, posture: str):
        """
        Publish posture state.

        Args:
            posture: Posture state (MONITORING_LYING, SITTING_DETECTED, etc.)
        """
        if not self.connected:
            return

        topic = self.topics['posture']
        try:
            self.client.publish(topic, posture, retain=True)
        except Exception as e:
            print(f"[MQTT] Failed to publish posture: {e}")

    def publish_alert(self, alert_type: str = "PERSON_SITTING_UP"):
        """
        Publish alert event.

        Args:
            alert_type: Type of alert
        """
        if not self.connected:
            return

        topic = self.topics['alert']
        try:
            self.client.publish(topic, alert_type, retain=False)
            print(f"[MQTT] 🚨 Published alert: {alert_type}")
        except Exception as e:
            print(f"[MQTT] Failed to publish alert: {e}")

    def publish_stats(self, alert_count: int, frame_count: int):
        """
        Publish statistics.

        Args:
            alert_count: Total number of alerts
            frame_count: Total frames processed
        """
        if not self.connected:
            return

        topic = self.topics['stats']
        uptime = int(time.time() - self.start_time)
        hours = uptime // 3600
        minutes = (uptime % 3600) // 60
        seconds = uptime % 60

        stats = {
            "alert_count": alert_count,
            "frame_count": frame_count,
            "uptime": f"{hours:02d}:{minutes:02d}:{seconds:02d}",
            "uptime_seconds": uptime,
            "timestamp": datetime.now().isoformat()
        }

        try:
            self.client.publish(topic, json.dumps(stats), retain=True)
        except Exception as e:
            print(f"[MQTT] Failed to publish stats: {e}")

    def cleanup(self):
        """Disconnect from MQTT broker."""
        if self.client and self.connected:
            print("Disconnecting from MQTT broker...")
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False
