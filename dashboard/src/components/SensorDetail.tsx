import { useEffect, useMemo, useRef, useState } from "react";
import { X } from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getHistory } from "../api";
import type { DashboardConfig } from "../config";
import { formatMetric, metricDefinitions, metricTone } from "../metrics";
import { metricKeys, type HistoryPoint, type MetricKey, type Sensor } from "../types";

interface SensorDetailProps {
  sensor: Sensor;
  config: DashboardConfig;
  onClose: () => void;
}

function formatTimestamp(value: string | null): string {
  if (!value) return "Never";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Never" : date.toLocaleString();
}

export function SensorDetail({ sensor, config, onClose }: SensorDetailProps) {
  const [metric, setMetric] = useState<MetricKey>("co2");
  const [hours, setHours] = useState(24);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const panelRef = useRef<HTMLElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setHistoryError(null);
    getHistory(config.apiBaseUrl, sensor.id, metric, hours, controller.signal)
      .then((response) => setHistory(response.data))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setHistoryError(error instanceof Error ? error.message : "Unable to load history");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [config.apiBaseUrl, hours, metric, sensor.id]);

  useEffect(() => {
    const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeButtonRef.current?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab" || !panelRef.current) return;

      const focusable = Array.from(
        panelRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ),
      ).filter((element) => !element.hasAttribute("hidden"));
      if (!focusable.length) {
        event.preventDefault();
        panelRef.current.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      previouslyFocused?.focus();
    };
  }, [onClose]);

  const chartData = useMemo(
    () =>
      history.map((point) => ({
        value: point.value,
        timestamp: new Date(point.timestamp).toLocaleString([], {
          month: "short",
          day: "numeric",
          hour: "numeric",
          minute: "2-digit",
        }),
      })),
    [history],
  );

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        ref={panelRef}
        className="detail-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="sensor-detail-title"
        tabIndex={-1}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="detail-header">
          <div>
            <p className="eyebrow">{sensor.id}</p>
            <h2 id="sensor-detail-title">{sensor.name}</h2>
            <p className="detail-subtitle">{sensor.hostname}</p>
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            className="icon-button"
            onClick={onClose}
            aria-label="Close details"
          >
            <X size={20} />
          </button>
        </div>

        <div className="detail-summary">
          <div><span>Status</span><strong>{sensor.online ? (sensor.stale ? "Stale" : "Online") : "Offline"}</strong></div>
          <div><span>Last reading</span><strong>{formatTimestamp(sensor.last_seen)}</strong></div>
          <div><span>Model</span><strong>{sensor.model}</strong></div>
          <div><span>ESPHome</span><strong>{sensor.esphome_version ?? "Not reported"}</strong></div>
        </div>

        <div className="detail-metrics" aria-label="Current readings">
          {metricKeys.map((key) => {
            const value = sensor.latest?.[key] ?? null;
            const definition = metricDefinitions[key];
            return (
              <button
                type="button"
                key={key}
                className={`detail-metric tone-${metricTone(key, value)} ${metric === key ? "selected" : ""}`}
                onClick={() => setMetric(key)}
              >
                <span>{definition.label}</span>
                <strong>{formatMetric(value)}</strong>
                <small>{value === null ? "" : definition.unit}</small>
              </button>
            );
          })}
        </div>

        <div className="chart-section">
          <div className="chart-heading">
            <div>
              <p className="eyebrow">Recorded history</p>
              <h3>{metricDefinitions[metric].label}</h3>
            </div>
            <div className="range-selector" aria-label="History range">
              {[1, 6, 24, 72, 168].map((option) => (
                <button
                  type="button"
                  key={option}
                  className={hours === option ? "active" : ""}
                  onClick={() => setHours(option)}
                >
                  {option >= 24 ? `${option / 24}d` : `${option}h`}
                </button>
              ))}
            </div>
          </div>

          <div className="chart-area">
            {loading ? (
              <p className="empty-state">Loading recorded readings…</p>
            ) : historyError ? (
              <p className="empty-state error-text">{historyError}</p>
            ) : chartData.length === 0 ? (
              <p className="empty-state">No recorded readings in this period.</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="4 4" stroke="#203248" vertical={false} />
                  <XAxis dataKey="timestamp" stroke="#7890aa" fontSize={11} tickLine={false} minTickGap={40} />
                  <YAxis stroke="#7890aa" fontSize={11} tickLine={false} axisLine={false} domain={["auto", "auto"]} />
                  <Tooltip
                    contentStyle={{
                      background: "#0b1828",
                      border: "1px solid #2b415b",
                      borderRadius: 10,
                      color: "#edf7ff",
                    }}
                    formatter={(value) => [`${String(value)} ${metricDefinitions[metric].unit}`, metricDefinitions[metric].label]}
                  />
                  <Line type="monotone" dataKey="value" stroke="#43d5c3" strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
