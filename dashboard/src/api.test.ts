import { describe, expect, it } from "vitest";
import { applyStreamMessage, endpoint, mergeRestSensors, parseStreamMessage } from "./api";
import type { Sensor } from "./types";

const sensor = (id: string, co2: number): Sensor => ({
  id,
  name: id,
  hostname: `${id}.example`,
  online: true,
  stale: false,
  last_seen: "2026-09-22T12:00:00Z",
  timestamp: "2026-09-22T12:00:00Z",
  ip_address: null,
  mac: null,
  model: "Apollo AIR-1",
  firmware_version: null,
  esphome_version: null,
  latest: {
    sensor_id: id,
    online: true,
    stale: false,
    last_seen: "2026-09-22T12:00:00Z",
    timestamp: "2026-09-22T12:00:00Z",
    co2,
    pm1_0: null,
    pm2_5: null,
    pm4_0: null,
    pm10: null,
    voc: null,
    nox: null,
    temperature: null,
    humidity: null,
    pressure: null,
    rssi: null,
  },
});

describe("API helpers", () => {
  it("joins API paths without changing a configured base URL", () => {
    expect(endpoint("https://api.example.edu", "/api/v1/sensors")).toBe(
      "https://api.example.edu/api/v1/sensors",
    );
  });

  it("rejects malformed and unrelated WebSocket messages", () => {
    expect(parseStreamMessage("not-json")).toBeNull();
    expect(parseStreamMessage('{"type":"pong"}')).toBeNull();
  });

  it("replaces one sensor without dropping the rest", () => {
    const current = [sensor("air-sensor-01", 400), sensor("air-sensor-02", 500)];
    const updated = sensor("air-sensor-01", 450);
    const result = applyStreamMessage(current, {
      type: "sensor_update",
      timestamp: "2026-09-22T12:01:00Z",
      data: updated,
    });
    expect(result).toHaveLength(2);
    expect(result[0].latest?.co2).toBe(450);
    expect(result[1].latest?.co2).toBe(500);
  });

  it("does not let an older REST response replace a newer stream reading", () => {
    const current = sensor("air-sensor-01", 500);
    current.latest!.timestamp = "2026-09-22T12:02:00Z";
    current.last_seen = "2026-09-22T12:02:00Z";
    const older = sensor("air-sensor-01", 400);
    const result = mergeRestSensors([current], [older]);
    expect(result[0].latest?.co2).toBe(500);
    expect(result[0].last_seen).toBe("2026-09-22T12:02:00Z");
  });

  it("preserves a stored reading when initial stream state has no current reading", () => {
    const stored = sensor("air-sensor-01", 425);
    const empty = { ...sensor("air-sensor-01", 0), latest: null, last_seen: null };
    const result = applyStreamMessage([stored], {
      type: "initial_state",
      timestamp: "2026-09-22T12:03:00Z",
      data: [empty],
    });
    expect(result[0].latest?.co2).toBe(425);
  });
});
