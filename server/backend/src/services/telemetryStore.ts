import { DeviceTelemetryPacket, TelemetryAlert } from "../types/telemetry.js";
import { alertEngine } from "./alertEngine.js";

export class TelemetryStore {
  private buffer: DeviceTelemetryPacket[] = [];
  private maxBufferSize = 500;
  private activeDevices = new Map<string, { lastSeen: number; platform: string; latestPacket: DeviceTelemetryPacket }>();
  private allAlerts: TelemetryAlert[] = [];
  private maxAlertsSize = 100;
  private totalPacketsCount = 0;

  ingest(packet: DeviceTelemetryPacket): { packet: DeviceTelemetryPacket; newAlerts: TelemetryAlert[] } {
    const now = Date.now();
    const packetWithMeta: DeviceTelemetryPacket = {
      ...packet,
      id: `pkt_${now}_${Math.random().toString(36).slice(2, 7)}`,
      receivedAt: now
    };

    // Evaluate alerts
    const alerts = alertEngine.evaluate(packetWithMeta);
    packetWithMeta.alerts = alerts;

    if (alerts.length > 0) {
      this.allAlerts.unshift(...alerts);
      if (this.allAlerts.length > this.maxAlertsSize) {
        this.allAlerts.length = this.maxAlertsSize;
      }
    }

    // Add to ring buffer
    this.buffer.unshift(packetWithMeta);
    if (this.buffer.length > this.maxBufferSize) {
      this.buffer.length = this.maxBufferSize;
    }

    // Update active devices
    this.activeDevices.set(packet.deviceId, {
      lastSeen: now,
      platform: packet.platform,
      latestPacket: packetWithMeta
    });

    this.totalPacketsCount++;

    return { packet: packetWithMeta, newAlerts: alerts };
  }

  getLatest(deviceId?: string): DeviceTelemetryPacket | null {
    if (deviceId) {
      const dev = this.activeDevices.get(deviceId);
      return dev ? dev.latestPacket : null;
    }
    return this.buffer[0] || null;
  }

  getHistory(limit = 50, deviceId?: string): DeviceTelemetryPacket[] {
    const list = deviceId
      ? this.buffer.filter((p) => p.deviceId === deviceId)
      : this.buffer;
    return list.slice(0, Math.min(limit, 200));
  }

  getAlerts(limit = 20): TelemetryAlert[] {
    return this.allAlerts.slice(0, limit);
  }

  getDevices() {
    const list: Array<{ deviceId: string; platform: string; lastSeen: number; online: boolean }> = [];
    const now = Date.now();
    for (const [id, info] of this.activeDevices.entries()) {
      list.push({
        deviceId: id,
        platform: info.platform,
        lastSeen: info.lastSeen,
        online: now - info.lastSeen < 10000 // online if seen in last 10 seconds
      });
    }
    return list;
  }

  getStats() {
    return {
      totalPacketsIngested: this.totalPacketsCount,
      activeDevicesCount: this.activeDevices.size,
      totalAlertsGenerated: this.allAlerts.length,
      bufferUtilization: `${this.buffer.length}/${this.maxBufferSize}`
    };
  }
}

export const telemetryStore = new TelemetryStore();
