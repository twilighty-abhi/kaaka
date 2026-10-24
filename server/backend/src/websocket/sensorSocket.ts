import { WebSocketServer, WebSocket } from "ws";
import { Server } from "http";
import { DeviceTelemetryPacket } from "../types/telemetry.js";
import { telemetryStore } from "../services/telemetryStore.js";

let wss: WebSocketServer | null = null;
const clients = new Set<WebSocket>();

export function setupWebSocketServer(server: Server) {
  wss = new WebSocketServer({ server, path: "/ws" });

  wss.on("connection", (ws: WebSocket) => {
    clients.add(ws);

    // Send latest available packet immediately upon connection
    const latest = telemetryStore.getLatest();
    if (latest) {
      ws.send(JSON.stringify({ type: "INITIAL_STATE", data: latest }));
    }

    ws.on("message", (message: string) => {
      try {
        const parsed = JSON.parse(message.toString());
        if (parsed.type === "TELEMETRY" && parsed.data) {
          const { packet } = telemetryStore.ingest(parsed.data);
          broadcastTelemetry(packet);
        }
      } catch {
        // Ignore unparseable frames
      }
    });

    ws.on("close", () => {
      clients.delete(ws);
    });

    ws.on("error", () => {
      clients.delete(ws);
    });
  });

  return wss;
}

export function broadcastTelemetry(packet: DeviceTelemetryPacket) {
  if (!wss || clients.size === 0) return;

  const payload = JSON.stringify({
    type: "TELEMETRY_UPDATE",
    data: packet
  });

  for (const client of clients) {
    if (client.readyState === WebSocket.OPEN) {
      client.send(payload);
    }
  }
}
