import { ArrowUpRight, Clock3, TriangleAlert } from "lucide-react";
import { formatMetric, metricDefinitions, metricTone } from "../metrics";
import type { MetricKey, Sensor } from "../types";

interface SensorCardProps {
  sensor: Sensor;
  selectedMetrics: MetricKey[];
  onSelect: (sensor: Sensor) => void;
}

const overviewMetrics: MetricKey[] = ["co2", "pm2_5", "temperature", "humidity", "voc", "rssi"];

function timeAgo(value: string | null): string {
  if (!value) return "No readings yet";
  const timestamp = new Date(value).getTime();
  if (!Number.isFinite(timestamp)) return "No readings yet";
  const seconds = Math.max(0, Math.floor((Date.now() - timestamp) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

export function SensorCard({ sensor, selectedMetrics, onSelect }: SensorCardProps) {
  const metrics = selectedMetrics.length ? selectedMetrics : overviewMetrics;
  const status = sensor.online ? (sensor.stale ? "stale" : "online") : "offline";

  return (
    <button type="button" className={`sensor-card sensor-${status}`} onClick={() => onSelect(sensor)}>
      <div className="card-heading">
        <div>
          <div className="sensor-title-row">
            <span className={`sensor-dot ${status}`} aria-hidden="true" />
            <h2>{sensor.name}</h2>
          </div>
          <p>{sensor.id}</p>
        </div>
        <ArrowUpRight size={18} className="card-arrow" aria-hidden="true" />
      </div>

      <div className="card-status-row">
        {status === "offline" ? <TriangleAlert size={14} /> : <Clock3 size={14} />}
        <span>{status === "online" ? `Updated ${timeAgo(sensor.last_seen)}` : status}</span>
      </div>

      <div className="metric-grid">
        {metrics.map((key) => {
          const value = sensor.latest?.[key] ?? null;
          const definition = metricDefinitions[key];
          return (
            <div className={`metric-cell tone-${metricTone(key, value)}`} key={key}>
              <span className="metric-label">{definition.label}</span>
              <span className="metric-reading">
                <strong>{formatMetric(value)}</strong>
                {value !== null && <small>{definition.unit}</small>}
              </span>
            </div>
          );
        })}
      </div>

      <div className="card-footer">
        <span>{sensor.hostname}</span>
        <span>{sensor.model}</span>
      </div>
    </button>
  );
}
