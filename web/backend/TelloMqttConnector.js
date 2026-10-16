const mqtt = require('mqtt');
const EventEmitter = require('events');

class TelloMqttConnector extends EventEmitter {
  constructor(brokerUrl = 'mqtt://localhost:1883', username = 'tello', password = 'tello') {
    super();
    this.brokerUrl = brokerUrl;
    this.username = username;
    this.password = password;
    this.client = null;

    // Topics
    this.archiveTopic = 'tello/archive/+';
    this.statusTopic = 'tello/status';
    this.cmdTopic = 'tello/commands';
  }

  connect() {
    this.client = mqtt.connect(this.brokerUrl, {
      clientId: `tello_node_api_${Math.random().toString(16).substring(2, 8)}`,
      username: this.username,
      password: this.password,
      reconnectPeriod: 2000
    });

    this.client.on('connect', () => {
      console.log(`[MQTT] Connected to ${this.brokerUrl}`);
      // Subscribe to both axis archives and status
      this.client.subscribe([this.archiveTopic, this.statusTopic], (err) => {
        if (err) console.error('[MQTT] Subscription error:', err);
      });
    });

    this.client.on('message', (topic, message) => {
      try {
        const payload = JSON.parse(message.toString());

        // 1. Status Telemetry
        if (topic === this.statusTopic) {
          const data = JSON.parse(message.toString());

          this.emit('status', {
            ...data,
            timestamp: Date.now() / 1000
          });
          return;
        }

        // 2. Axis Archive Telemetry
        if (topic.startsWith('tello/archive/')) {
          const parts = topic.split('/');
          const axis = parts[parts.length - 1].toUpperCase();

          const record = {
            axis,
            timestamp: payload.timestamp ?? Date.now() / 1000,
            reference: payload.axis_command_reference ?? payload.reference ?? 0,
            command: payload.axis_corrected_command ?? payload.command ?? 0,
            measure: payload.measure ?? payload.measurement ?? 0
          };

          this.emit('telemetry', record);
        }
      } catch (err) {
        console.error('[MQTT] Parse error:', err.message);
      }
    });

    this.client.on('error', (err) => {
      console.error('[MQTT] Connection error:', err.message);
    });
  }

  /**
   * Publishes control references to tello/commands.
   */
  publishCommand(x, y, z, yaw) {
    if (!this.client || !this.client.connected) {
      throw new Error('MQTT client is not connected');
    }
    const payload = JSON.stringify({
      X: Number(x),
      Y: Number(y),
      Z: Number(z),
      YAW: Number(yaw)
    });
    this.client.publish(this.cmdTopic, payload, { qos: 0 });
  }

  /**
   * Deadman switch: sets all axes references to -69
   */
  publishDeadman() {
    this.publishCommand(-69, -69, -69, -69);
  }
}

module.exports = TelloMqttConnector;
