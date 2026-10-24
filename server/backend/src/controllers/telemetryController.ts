import { Request, Response } from "express";
import { telemetryStore } from "../services/telemetryStore.js";
import { DeviceTelemetryPacket } from "../types/telemetry.js";
import { broadcastTelemetry } from "../websocket/sensorSocket.js";

export function handlePostTelemetry(req: Request, res: Response) {
  const data = req.body as DeviceTelemetryPacket;

  if (!data || !data.deviceId || !data.sensors) {
    res.status(400).json({ error: "Invalid telemetry packet format. Must include deviceId and sensors." });
    return;
  }

  const { packet, newAlerts } = telemetryStore.ingest(data);

  // Broadcast to all active WebSocket dashboard clients
  broadcastTelemetry(packet);

  res.status(200).json({
    success: true,
    packetId: packet.id,
    alerts: newAlerts,
    receivedAt: packet.receivedAt
  });
}

export function handleGetLatest(req: Request, res: Response) {
  const deviceId = req.query.deviceId as string | undefined;
  const latest = telemetryStore.getLatest(deviceId);
  if (!latest) {
    res.status(404).json({ message: "No telemetry data recorded yet." });
    return;
  }
  res.status(200).json(latest);
}

export function handleGetHistory(req: Request, res: Response) {
  const limit = parseInt((req.query.limit as string) || "50", 10);
  const deviceId = req.query.deviceId as string | undefined;
  const history = telemetryStore.getHistory(limit, deviceId);
  res.status(200).json({
    count: history.length,
    packets: history
  });
}

export function handleGetAlerts(req: Request, res: Response) {
  const limit = parseInt((req.query.limit as string) || "20", 10);
  const alerts = telemetryStore.getAlerts(limit);
  res.status(200).json({ count: alerts.length, alerts });
}

export function handleGetDevices(_req: Request, res: Response) {
  const devices = telemetryStore.getDevices();
  res.status(200).json({ count: devices.length, devices });
}

export function handleGetStats(_req: Request, res: Response) {
  const stats = telemetryStore.getStats();
  res.status(200).json(stats);
}
