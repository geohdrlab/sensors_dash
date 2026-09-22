import { lazy, Suspense, useMemo, useState } from "react";
import { AlertCircle, FlaskConical } from "lucide-react";
import type { DashboardConfig } from "./config";
import { Controls } from "./components/Controls";
import { Header } from "./components/Header";
import { SensorCard } from "./components/SensorCard";
import { useSensorData } from "./useSensorData";
import type { MetricKey, Sensor } from "./types";

const SensorDetail = lazy(() =>
  import("./components/SensorDetail").then((module) => ({ default: module.SensorDetail })),
);

export default function App({ config }: { config: DashboardConfig }) {
  const { sensors, streamState, error, lastUpdate, refresh } = useSensorData(config);
  const [query, setQuery] = useState("");
  const [selectedMetrics, setSelectedMetrics] = useState<MetricKey[]>([]);
  const [selectedSensorId, setSelectedSensorId] = useState<string | null>(null);

  const filteredSensors = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return sensors;
    return sensors.filter((sensor) =>
      [sensor.id, sensor.name, sensor.hostname].some((value) => value.toLowerCase().includes(normalized)),
    );
  }, [query, sensors]);

  const selectedSensor = sensors.find((sensor) => sensor.id === selectedSensorId) ?? null;
  const online = sensors.filter((sensor) => sensor.online && !sensor.stale).length;

  const toggleMetric = (metric: MetricKey) => {
    setSelectedMetrics((current) =>
      current.includes(metric) ? current.filter((item) => item !== metric) : [...current, metric],
    );
  };

  const chooseSensor = (sensor: Sensor) => setSelectedSensorId(sensor.id);

  return (
    <div className="app-shell">
      <Header
        streamState={streamState}
        online={online}
        total={sensors.length}
        lastUpdate={lastUpdate}
        onRefresh={() => void refresh()}
      />

      <main>
        <section className="intro">
          <div>
            <p className="eyebrow">Indoor environmental telemetry</p>
            <h2>Live conditions across the AIR-1 fleet</h2>
            <p className="intro-copy">
              Current and recorded measurements from nine laboratory sensors. Select a sensor to inspect its history.
            </p>
          </div>
          <div className="fleet-summary" aria-label="Fleet summary">
            <FlaskConical size={22} aria-hidden="true" />
            <div>
              <strong>{online}/{sensors.length || 9}</strong>
              <span>reporting now</span>
            </div>
          </div>
        </section>

        {error && (
          <div className="error-banner" role="alert">
            <AlertCircle size={18} aria-hidden="true" />
            <div>
              <strong>Unable to refresh from the API</strong>
              <span>{error}. The dashboard will keep retrying.</span>
            </div>
          </div>
        )}

        <Controls
          query={query}
          onQueryChange={setQuery}
          selectedMetrics={selectedMetrics}
          onMetricToggle={toggleMetric}
          onShowAll={() => setSelectedMetrics([])}
        />

        {filteredSensors.length ? (
          <section className="sensor-grid" aria-label="Sensors">
            {filteredSensors.map((sensor) => (
              <SensorCard
                key={sensor.id}
                sensor={sensor}
                selectedMetrics={selectedMetrics}
                onSelect={chooseSensor}
              />
            ))}
          </section>
        ) : (
          <div className="no-results">
            <h3>{sensors.length ? "No sensors match that search" : "Waiting for sensor inventory"}</h3>
            <p>{sensors.length ? "Try a sensor ID such as air-sensor-04." : "The dashboard will update when the API responds."}</p>
          </div>
        )}
      </main>

      <footer>
        <span>GeoHDR Lab AIR-1 monitoring</span>
        <span>Read-only dashboard</span>
      </footer>

      {selectedSensor && (
        <Suspense fallback={null}>
          <SensorDetail sensor={selectedSensor} config={config} onClose={() => setSelectedSensorId(null)} />
        </Suspense>
      )}
    </div>
  );
}
