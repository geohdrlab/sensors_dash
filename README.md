# GeoHDR Lab AIR-1 sensors

This repository contains two independent applications:

- `backend/` is the Python collector and read-only FastAPI service.
- `dashboard/` is a static React client that reads the versioned API.

Each application has its own dependencies and startup process. The API does not mount or serve the dashboard, so dashboard builds and deployments do not restart or modify sensor collection.

```text
Apollo AIR-1 sensors
        ↓ HTTP REST/SSE
asynchronous collector
        ↓
SQLite
        ↓
FastAPI
        ↓ REST API / WebSocket ─────→ static dashboard
        ↓
other research clients
```

See [dashboard/README.md](dashboard/README.md) for dashboard development and deployment. The earlier Next.js dashboard remains preserved on the `old-dashboard` branch of the source repository.

## Metrics

| API field | Unit |
| --- | --- |
| `co2` | ppm |
| `pm1_0`, `pm2_5`, `pm4_0`, `pm10` | µg/m³ |
| `voc`, `nox` | index |
| `temperature` | °F |
| `humidity` | % |
| `pressure` | hPa |
| `rssi` | dBm |

Temperature remains Fahrenheit so new data stays compatible with existing SQLite history.

## Development setup

Python 3.11 or newer is required.

```bash
./scripts/install.sh
./scripts/start.sh
```

The API listens on `http://127.0.0.1:8000` by default. Interactive documentation is available at `http://127.0.0.1:8000/docs`.

The collector reads [config/sensors.json](config/sensors.json). The `.dyn.uncc.edu` names are authoritative. A sensor that cannot resolve or connect remains in the API with `online: false` while the collector retries.

## API routes

```text
GET /api/v1/health
GET /api/v1/sensors
GET /api/v1/sensors/{sensor_id}
GET /api/v1/sensors/{sensor_id}/latest
GET /api/v1/sensors/{sensor_id}/readings
GET /api/v1/sensors/{sensor_id}/history
GET /api/v1/metrics
WS  /api/v1/ws
```

Historical queries accept `hours` from 1 through 720 and `limit` from 1 through 5000. `/history` returns one validated metric. `/readings` returns multi-metric snapshots.

```bash
curl http://127.0.0.1:8000/api/v1/health
curl http://127.0.0.1:8000/api/v1/sensors
curl http://127.0.0.1:8000/api/v1/sensors/air-sensor-07/latest
curl "http://127.0.0.1:8000/api/v1/sensors/air-sensor-07/history?hours=24&metric=co2"
```

## API-key authentication

Authentication is optional during development. To require it, set a key outside Git:

```bash
export AIR_REQUIRE_API_KEY=true
export AIR_API_KEY='replace-with-a-long-random-value'
./scripts/start.sh
```

Then send the key in `X-API-Key`:

```bash
curl -H "X-API-Key: YOUR_KEY" http://127.0.0.1:8000/api/v1/sensors
```

When authentication is required, a WebSocket client must send this JSON within five seconds of connecting:

```json
{"type":"authenticate","api_key":"YOUR_KEY"}
```

The server then sends `initial_state`, followed by `sensor_update` messages. Clients may send the text message `ping` and receive a JSON `pong`. Non-browser clients may instead provide `X-API-Key` during the WebSocket handshake.

The root descriptor, health endpoint, OpenAPI schema, `/docs`, and `/redoc` remain public. Sensor data endpoints require a key when `AIR_REQUIRE_API_KEY=true`. IP and MAC fields are returned only to a caller that provides the configured key.

## Configuration

Copy `.env.example` as a reference. The service reads environment variables directly; it does not automatically load a `.env` file.

- `AIR_HOST`, default `127.0.0.1`
- `AIR_PORT`, default `8000`
- `AIR_DATABASE_PATH`, default `backend/air_sensors.db`
- `AIR_SENSOR_CONFIG_PATH`, default `config/sensors.json`
- `AIR_SNAPSHOT_INTERVAL_SECONDS`, default `30`
- `AIR_HISTORY_RETENTION_DAYS`, default `30`
- `AIR_STALE_AFTER_SECONDS`, default `180`
- `AIR_REQUIRE_API_KEY`, default `false`
- `AIR_API_KEY`, no default
- `AIR_CORS_ORIGINS`, comma-separated and empty by default
- `AIR_LOG_LEVEL`, default `INFO`

## Tests

```bash
backend/venv/bin/python -m pytest -q
cd dashboard
npm ci
npm test
npm run lint
npm run build
```

See [docs/architecture.md](docs/architecture.md) for collector and storage details and [docs/deployment.md](docs/deployment.md) for no-root Linux operation.
