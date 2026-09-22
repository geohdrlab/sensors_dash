import { Activity, Clock3, Database, Radio, RefreshCw } from "lucide-react";
import type { StreamState } from "../types";

interface HeaderProps {
  streamState: StreamState;
  online: number;
  total: number;
  lastUpdate: string | null;
  onRefresh: () => void;
}

const stateLabels: Record<StreamState, string> = {
  connecting: "Connecting",
  live: "Live stream",
  polling: "Polling",
  error: "API unavailable",
};

function formatTimestamp(value: string | null): string {
  if (!value) return "Waiting for data";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Waiting for data";
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function Header({ streamState, online, total, lastUpdate, onRefresh }: HeaderProps) {
  return (
    <header className="site-header">
      <div className="header-inner">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">
            <Activity size={24} />
          </div>
          <div>
            <p className="eyebrow">GeoHDR Lab</p>
            <h1>AIR-1 Monitor</h1>
          </div>
        </div>

        <div className="header-stats" aria-label="Dashboard status">
          <div className={`status-pill state-${streamState}`}>
            <Radio size={15} aria-hidden="true" />
            <span>{stateLabels[streamState]}</span>
          </div>
          <div className="header-stat">
            <Database size={15} aria-hidden="true" />
            <span>
              <strong>{online}</strong> of {total} online
            </span>
          </div>
          <div className="header-stat last-update">
            <Clock3 size={15} aria-hidden="true" />
            <span>{formatTimestamp(lastUpdate)}</span>
          </div>
          <button className="icon-button" type="button" onClick={onRefresh} aria-label="Refresh readings">
            <RefreshCw size={17} />
          </button>
        </div>
      </div>
    </header>
  );
}
