import { Router } from "express";
import {
  handlePostTelemetry,
  handleGetLatest,
  handleGetHistory,
  handleGetAlerts,
  handleGetDevices,
  handleGetStats
} from "../controllers/telemetryController.js";

export const apiRouter = Router();

apiRouter.get("/health", (_req, res) => {
  res.json({
    status: "ok",
    service: "Kaaka Sensors Telemetry Backend",
    timestamp: Date.now(),
    uptime: process.uptime()
  });
});

apiRouter.post("/telemetry", handlePostTelemetry);
apiRouter.get("/telemetry/latest", handleGetLatest);
apiRouter.get("/telemetry/history", handleGetHistory);
apiRouter.get("/telemetry/alerts", handleGetAlerts);
apiRouter.get("/devices", handleGetDevices);
apiRouter.get("/stats", handleGetStats);
