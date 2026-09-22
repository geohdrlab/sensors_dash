# Architecture

The FastAPI process owns the complete sensor data path:

```text
9 Apollo AIR-1 sensors
        ↓ HTTP port 80, /events SSE
collector tasks
        ↓ current in-memory state
periodic snapshots
        ↓
SQLite in WAL mode
        ↓
REST API and WebSocket clients
```

Each configured sensor has one reconnecting task. ESPHome sends all current states when the `/events` connection opens and sends later changes as `state` events. The parser prefers the firmware 2026.3 `name_id` field and supports the older `id` form. Only known measurement entities are accepted. No control requests are sent to the devices.

DNS names in `config/sensors.json` are authoritative. DNS or connection failures mark a sensor offline and trigger exponential retry with jitter. Stored IP addresses are not used as a fallback.

The in-memory state drives current API responses and WebSocket updates. A snapshot task writes current metric values into the existing `metrics_history` table. Public particulate field names are mapped to existing internal database keys, so no destructive migration is required.

SQLite uses WAL, foreign-key enforcement, and a five-second busy timeout. API queries enforce metric allow-lists, a maximum 30-day lookback, and a maximum 5,000 returned timestamps.

The API has no write, control, firmware, shell, configuration, or deletion endpoints. Optional API-key checks apply to REST data routes and the WebSocket stream. CORS is disabled unless exact origins are configured.

## Dashboard boundary

The `dashboard/` directory is a static TypeScript application. It has no imports from `backend/`, no access to SQLite, and no sensor network access. It reads current state from REST and receives live state through `/api/v1/ws`. If the WebSocket disconnects, periodic REST refreshes continue.

The API does not mount dashboard assets. A dashboard deployment can therefore use GitHub Pages, a static server, or a separate virtual host without changing the API process. `dashboard/dist/dashboard-config.json` selects the API origin after the dashboard is built.
