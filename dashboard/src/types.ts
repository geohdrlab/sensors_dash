export const metricKeys = [
  "co2",
  "pm1_0",
  "pm2_5",
  "pm4_0",
  "pm10",
  "voc",
  "nox",
  "temperature",
  "humidity",
  "pressure",
  "rssi",
] as const;

export type MetricKey = (typeof metricKeys)[number];

export interface Telemetry {
  sensor_id: string;
  online: boolean;
  stale: boolean;
  last_seen: string | null;
  timestamp: string;
  co2: number | null;
  pm1_0: number | null;
  pm2_5: number | null;
  pm4_0: number | null;
  pm10: number | null;
  voc: number | null;
  nox: number | null;
  temperature: number | null;
  humidity: number | null;
  pressure: number | null;
  rssi: number | null;
}

export interface SensorSummary {
  id: string;
  name: string;
  hostname: string;
  online: boolean;
  stale: boolean;
  last_seen: string | null;
  timestamp: string;
  ip_address: string | null;
  mac: string | null;
  model: string;
  firmware_version: string | null;
  esphome_version: string | null;
}

export interface Sensor extends SensorSummary {
  latest: Telemetry | null;
}

export interface SensorListResponse {
  count: number;
  sensors: SensorSummary[];
}

export interface HistoryPoint {
  timestamp: string;
  value: number;
}

export interface HistoryResponse {
  sensor_id: string;
  metric: MetricKey;
  hours: number;
  count: number;
  truncated: boolean;
  data: HistoryPoint[];
}

export interface MetricDefinition {
  key: MetricKey;
  label: string;
  unit: string;
}

export interface MetricsResponse {
  metrics: MetricDefinition[];
}

export type StreamState = "connecting" | "live" | "polling" | "error";

export interface InitialStateMessage {
  type: "initial_state";
  timestamp: string;
  data: Sensor[];
}

export interface SensorUpdateMessage {
  type: "sensor_update";
  timestamp: string;
  data: Sensor;
}

export type StreamMessage = InitialStateMessage | SensorUpdateMessage;
