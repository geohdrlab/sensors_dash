import { describe, expect, it } from "vitest";
import { applyStreamMessage, endpoint, parseStreamMessage } from "./api";
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
});
