import express from "express";
import http from "http";
import cors from "cors";
import dotenv from "dotenv";
import { apiRouter } from "./routes/apiRoutes.js";
import { setupWebSocketServer } from "./websocket/sensorSocket.js";

dotenv.config();

const app = express();
const port = process.env.PORT || 3001;

// Middlewares
app.use(cors());
app.use(express.json({ limit: "5mb" }));

// Routes
app.use("/api", apiRouter);

// Root route
app.get("/", (_req, res) => {
  res.json({
    name: "Kaaka Sensors Telemetry Backend",
    version: "1.0.0",
    endpoints: {
      health: "/api/health",
      ingestTelemetry: "POST /api/telemetry",
      latestTelemetry: "GET /api/telemetry/latest",
      telemetryHistory: "GET /api/telemetry/history",
      alerts: "GET /api/telemetry/alerts",
      devices: "GET /api/devices",
      stats: "GET /api/stats",
      webSocket: "/ws"
    }
  });
});

const server = http.createServer(app);

// Setup WebSocket server
setupWebSocketServer(server);

server.listen(port, () => {
  console.log(`[Kaaka Sensors Backend] Server listening on port ${port}`);
  console.log(`[WebSocket] Live stream available at ws://localhost:${port}/ws`);
});
