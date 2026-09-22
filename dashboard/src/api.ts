import type {
  HistoryResponse,
  MetricKey,
  Sensor,
  SensorListResponse,
  SensorSummary,
  StreamMessage,
} from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

export function endpoint(baseUrl: string, path: string): string {
  return `${baseUrl}${path}`;
}

export function websocketEndpoint(baseUrl: string): string {
  const absoluteBase = baseUrl || window.location.origin;
  const url = new URL("/api/v1/ws", absoluteBase);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}

async function request<T>(baseUrl: string, path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(endpoint(baseUrl, path), {
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) {
    let message = `API request failed with status ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string | { detail?: string } };
      if (typeof body.detail === "string") message = body.detail;
      if (typeof body.detail === "object" && body.detail?.detail) message = body.detail.detail;
    } catch {
      // Keep the status-based message when the response is not JSON.
    }
    throw new ApiError(message, response.status);
  }
  return (await response.json()) as T;
}

export async function getSensors(baseUrl: string, signal?: AbortSignal): Promise<Sensor[]> {
  const list = await request<SensorListResponse>(baseUrl, "/api/v1/sensors", signal);
  return Promise.all(
    list.sensors.map(async (summary) => {
      try {
        return await request<Sensor>(baseUrl, `/api/v1/sensors/${encodeURIComponent(summary.id)}`, signal);
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) {
          return { ...summary, latest: null };
        }
        throw error;
      }
    }),
  );
}

export function mergeSummaries(current: Sensor[], summaries: SensorSummary[]): Sensor[] {
  return summaries.map((summary) => ({
    ...summary,
    latest: current.find((sensor) => sensor.id === summary.id)?.latest ?? null,
  }));
}

export function applyStreamMessage(current: Sensor[], message: StreamMessage): Sensor[] {
  if (message.type === "initial_state") {
    return [...message.data].sort((left, right) => left.id.localeCompare(right.id));
  }
  const existing = current.findIndex((sensor) => sensor.id === message.data.id);
  if (existing === -1) {
    return [...current, message.data].sort((left, right) => left.id.localeCompare(right.id));
  }
  const next = [...current];
  next[existing] = message.data;
  return next;
}

export function parseStreamMessage(value: string): StreamMessage | null {
  try {
    const parsed = JSON.parse(value) as Partial<StreamMessage>;
    if (parsed.type === "initial_state" && Array.isArray(parsed.data)) return parsed as StreamMessage;
    if (parsed.type === "sensor_update" && parsed.data && !Array.isArray(parsed.data)) {
      return parsed as StreamMessage;
    }
  } catch {
    return null;
  }
  return null;
}

export function getHistory(
  baseUrl: string,
  sensorId: string,
  metric: MetricKey,
  hours: number,
  signal?: AbortSignal,
): Promise<HistoryResponse> {
  const query = new URLSearchParams({ metric, hours: String(hours), limit: "1000" });
  return request<HistoryResponse>(
    baseUrl,
    `/api/v1/sensors/${encodeURIComponent(sensorId)}/history?${query.toString()}`,
    signal,
  );
}
