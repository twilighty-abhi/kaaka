import { DeviceTelemetryPacket, TelemetryAlert } from "../types/telemetry.js";

export class AlertEngine {
  private lastAlertMap = new Map<string, number>();

  evaluate(packet: DeviceTelemetryPacket): TelemetryAlert[] {
    const alerts: TelemetryAlert[] = [];
    const now = Date.now();
    const { accelerometer, gyroscope, magnetometer, ambientLight, pedometer } = packet.sensors;

    // 1. High Impact / Freefall Alert
    if (accelerometer.magnitude > 18.0) {
      if (this.canTrigger(`impact_${packet.deviceId}`, now, 3000)) {
        alerts.push({
          id: `alert_${now}_impact`,
          type: "IMPACT",
          severity: "CRITICAL",
          message: `High G-force impact detected: ${accelerometer.magnitude.toFixed(1)} m/s²`,
          timestamp: now
        });
      }
    } else if (accelerometer.magnitude < 2.0) {
      if (this.canTrigger(`freefall_${packet.deviceId}`, now, 3000)) {
        alerts.push({
          id: `alert_${now}_freefall`,
          type: "IMPACT",
          severity: "WARNING",
          message: `Possible free-fall detected: ${accelerometer.magnitude.toFixed(1)} m/s²`,
          timestamp: now
        });
      }
    }

    // 2. High Angular Rotation Alert
    if (gyroscope.rate > 3.5) {
      if (this.canTrigger(`rotation_${packet.deviceId}`, now, 3000)) {
        alerts.push({
          id: `alert_${now}_rot`,
          type: "ROTATION",
          severity: "WARNING",
          message: `High spin rotation rate: ${gyroscope.rate.toFixed(2)} rad/s`,
          timestamp: now
        });
      }
    }

    // 3. Magnetic Anomaly / EMF Spike
    if (magnetometer.fieldStrength > 110) {
      if (this.canTrigger(`emf_${packet.deviceId}`, now, 5000)) {
        alerts.push({
          id: `alert_${now}_emf`,
          type: "MAGNETIC_ANOMALY",
          severity: "WARNING",
          message: `Strong electromagnetic anomaly detected: ${magnetometer.fieldStrength.toFixed(1)} µT`,
          timestamp: now
        });
      }
    }

    // 4. Extreme Low Light Alert
    if (ambientLight.lux < 5) {
      if (this.canTrigger(`dark_${packet.deviceId}`, now, 10000)) {
        alerts.push({
          id: `alert_${now}_dark`,
          type: "LOW_LIGHT",
          severity: "INFO",
          message: `Near total darkness detected: ${ambientLight.lux} lx`,
          timestamp: now
        });
      }
    }

    // 5. Pedometer Step Milestone Alert
    if (pedometer.steps > 0 && pedometer.steps % 1000 === 0) {
      if (this.canTrigger(`step_${packet.deviceId}_${pedometer.steps}`, now, 30000)) {
        alerts.push({
          id: `alert_${now}_step`,
          type: "STEP_MILESTONE",
          severity: "INFO",
          message: `Milestone reached: ${pedometer.steps} steps completed!`,
          timestamp: now
        });
      }
    }

    return alerts;
  }

  private canTrigger(key: string, now: number, cooldownMs: number): boolean {
    const last = this.lastAlertMap.get(key) || 0;
    if (now - last > cooldownMs) {
      this.lastAlertMap.set(key, now);
      return true;
    }
    return false;
  }
}

export const alertEngine = new AlertEngine();
