import { Search, SlidersHorizontal, X } from "lucide-react";
import { metricDefinitions } from "../metrics";
import { metricKeys, type MetricKey } from "../types";

interface ControlsProps {
  query: string;
  onQueryChange: (value: string) => void;
  selectedMetrics: MetricKey[];
  onMetricToggle: (metric: MetricKey) => void;
  onShowAll: () => void;
}

export function Controls({
  query,
  onQueryChange,
  selectedMetrics,
  onMetricToggle,
  onShowAll,
}: ControlsProps) {
  return (
    <section className="controls" aria-label="Sensor filters">
      <div className="search-wrap">
        <Search size={18} aria-hidden="true" />
        <input
          type="search"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="Search sensor ID, name, or hostname"
          aria-label="Search sensors"
        />
        {query && (
          <button type="button" onClick={() => onQueryChange("")} aria-label="Clear search">
            <X size={16} />
          </button>
        )}
      </div>
      <div className="metric-filter">
        <span className="filter-label">
          <SlidersHorizontal size={15} aria-hidden="true" /> Display
        </span>
        <button
          type="button"
          className={selectedMetrics.length === 0 ? "filter-chip active" : "filter-chip"}
          onClick={onShowAll}
        >
          Overview
        </button>
        {metricKeys.map((key) => (
          <button
            type="button"
            key={key}
            className={selectedMetrics.includes(key) ? "filter-chip active" : "filter-chip"}
            onClick={() => onMetricToggle(key)}
          >
            {metricDefinitions[key].label}
          </button>
        ))}
      </div>
    </section>
  );
}
