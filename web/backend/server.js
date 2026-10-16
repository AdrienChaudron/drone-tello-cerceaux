const express = require('express');
const cors = require('cors');
const TelloMqttConnector = require('./TelloMqttConnector');

const app = express();
const PORT = 3000;

// Middleware
app.use(cors());
app.use(express.json()); // Essential for parsing POST JSON bodies

const mqttConnector = new TelloMqttConnector();
mqttConnector.connect();

// Telemetry & Status In-Memory State
const recentHistory = [];
const MAX_HISTORY_SECONDS = 120;
let latestStatus = {
  battery: null,
  is_flying: false,
  temperature: null,
  flight_time: null,
  tof: null,
  yaw: null,
  timestamp: 0
};

// Listen to Axis Telemetry
mqttConnector.on('telemetry', (data) => {
  recentHistory.push(data);
  const cutoff = Date.now() / 1000 - MAX_HISTORY_SECONDS;
  while (recentHistory.length > 0 && recentHistory[0].timestamp < cutoff) {
    recentHistory.shift();
  }
});

// Listen to Drone Status
mqttConnector.on('status', (data) => {
  latestStatus = data;
});

// -----------------------------------------------------------------------------
// SSE Endpoint (Data to React)
// -----------------------------------------------------------------------------
app.get('/events', (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.flushHeaders();

  // 1. Initial burst: History and current status
  res.write(`data: ${JSON.stringify({ type: 'history', data: recentHistory })}\n\n`);
  res.write(`data: ${JSON.stringify({ type: 'status', data: latestStatus })}\n\n`);

  // 2. Stream real-time telemetry updates
  const onTelemetry = (data) => {
    res.write(`data: ${JSON.stringify({ type: 'live', data })}\n\n`);
  };

  // 3. Stream real-time status updates
  const onStatus = (data) => {
    res.write(`data: ${JSON.stringify({ type: 'status', data })}\n\n`);
  };

  mqttConnector.on('telemetry', onTelemetry);
  mqttConnector.on('status', onStatus);

  // Cleanup on connection drop
  req.on('close', () => {
    mqttConnector.removeListener('telemetry', onTelemetry);
    mqttConnector.removeListener('status', onStatus);
    res.end();
  });
});

// -----------------------------------------------------------------------------
// REST API Command Endpoints (From React)
// -----------------------------------------------------------------------------

// Deadman Switch route
app.post('/api/deadman', (req, res) => {
  try {
    mqttConnector.publishDeadman();
    console.log('[API] Deadman switch triggered (-69)');
    res.json({ success: true, message: 'Deadman switch activated' });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// Custom Command route
// Expects JSON: { "x": 0, "y": 0, "z": 80, "yaw": 10 }
app.post('/api/command', (req, res) => {
  const { x, y, z, yaw } = req.body;

  if (x === undefined || y === undefined || z === undefined || yaw === undefined) {
    return res.status(400).json({
      success: false,
      error: 'Missing parameters. Provide x, y, z, and yaw in the request body.'
    });
  }

  try {
    mqttConnector.publishCommand(x, y, z, yaw);
    res.json({ success: true, command: { x, y, z, yaw } });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// One-off status fetch
app.get('/api/status', (req, res) => {
  res.json(latestStatus);
});

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', time: Date.now() });
});

app.listen(PORT, () => {
  console.log(`[HTTP] Server listening on http://localhost:${PORT}`);
});
