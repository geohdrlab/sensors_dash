import { useCallback, useEffect, useRef, useState } from "react";
import {
  applyStreamMessage,
  getSensors,
  mergeRestSensors,
  parseStreamMessage,
  websocketEndpoint,
} from "./api";
import type { DashboardConfig } from "./config";
import type { Sensor, StreamState } from "./types";

const MAX_RECONNECT_DELAY_MS = 30000;

export interface SensorDataState {
  sensors: Sensor[];
  streamState: StreamState;
  error: string | null;
  lastUpdate: string | null;
  refresh: () => Promise<void>;
}

export function useSensorData(config: DashboardConfig): SensorDataState {
  const [sensors, setSensors] = useState<Sensor[]>([]);
  const [streamState, setStreamState] = useState<StreamState>("connecting");
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const refresh = useCallback(async () => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const result = await getSensors(config.apiBaseUrl, controller.signal);
      setSensors((current) => mergeRestSensors(current, result));
      setLastUpdate(new Date().toISOString());
      setError(null);
      setStreamState((current) => (current === "live" ? current : "polling"));
    } catch (caught) {
      if (controller.signal.aborted) return;
      setError(caught instanceof Error ? caught.message : "Unable to reach the sensor API");
      setStreamState("error");
    }
  }, [config.apiBaseUrl]);

  useEffect(() => {
    void refresh();
    const interval = window.setInterval(() => void refresh(), config.refreshIntervalMs);
    return () => {
      window.clearInterval(interval);
      abortRef.current?.abort();
    };
  }, [config.refreshIntervalMs, refresh]);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let reconnectTimer: number | undefined;
    let pingTimer: number | undefined;
    let stopped = false;
    let attempts = 0;

    const connect = () => {
      if (stopped) return;
      setStreamState((current) => (current === "live" ? current : "connecting"));
      socket = new WebSocket(websocketEndpoint(config.apiBaseUrl));

      socket.addEventListener("open", () => {
        attempts = 0;
        setStreamState("live");
        setError(null);
        pingTimer = window.setInterval(() => {
          if (socket?.readyState === WebSocket.OPEN) socket.send("ping");
        }, 25000);
      });

      socket.addEventListener("message", (event) => {
        if (typeof event.data !== "string") return;
        const message = parseStreamMessage(event.data);
        if (!message) return;
        setSensors((current) => applyStreamMessage(current, message));
        setLastUpdate(message.timestamp);
      });

      socket.addEventListener("error", () => socket?.close());
      socket.addEventListener("close", () => {
        if (pingTimer !== undefined) window.clearInterval(pingTimer);
        if (stopped) return;
        setStreamState("polling");
        const delay = Math.min(1000 * 2 ** attempts, MAX_RECONNECT_DELAY_MS);
        attempts += 1;
        reconnectTimer = window.setTimeout(connect, delay);
      });
    };

    connect();
    return () => {
      stopped = true;
      if (reconnectTimer !== undefined) window.clearTimeout(reconnectTimer);
      if (pingTimer !== undefined) window.clearInterval(pingTimer);
      socket?.close();
    };
  }, [config.apiBaseUrl]);

  return { sensors, streamState, error, lastUpdate, refresh };
}
