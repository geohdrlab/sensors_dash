# Linux deployment

The service can run entirely from a user-owned directory. It does not require root, Docker, Nginx, or ports 80 and 443.

## Manual no-root operation

```bash
git clone https://github.com/geohdrlab/sensors_dash.git
cd sensors_dash
./scripts/install.sh
export AIR_REQUIRE_API_KEY=true
export AIR_API_KEY='replace-with-a-long-random-value'
./scripts/start.sh
```

The default binding is `127.0.0.1:8000`. Set `AIR_HOST` only when another interface must reach the process. Put persistent SQLite storage in a user-writable location with `AIR_DATABASE_PATH`.

## Optional systemd user service

The included `systemd/air-sensor-api.service` assumes the checkout is at `%h/dr-li-air-sensors`. Edit its paths to the actual checkout before installing it, then run:

```bash
mkdir -p ~/.config/systemd/user
cp systemd/air-sensor-api.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now air-sensor-api
journalctl --user -u air-sensor-api -f
```

Create `%h/.config/air-sensor-api.env` with permissions `0600` for production environment values. Do not commit that file.

## Verification

```bash
curl http://127.0.0.1:8000/
curl http://127.0.0.1:8000/api/v1/health
curl -H "X-API-Key: YOUR_KEY" http://127.0.0.1:8000/api/v1/sensors
```

Cloudflare Tunnel and public-domain configuration are intentionally outside this repository phase.

## Dashboard deployment

The dashboard is not part of the API service. Build it with `npm ci && npm run build` inside `dashboard/`, then publish only `dashboard/dist/` with a static web server. Do not copy its files into `backend/`, add a FastAPI static mount, or change the API systemd unit.

Before publishing, set the API address in the built `dashboard/dist/dashboard-config.json`. The dashboard and API may use separate HTTPS hostnames. See [../dashboard/README.md](../dashboard/README.md) for the runtime configuration and CORS requirements.

The static dashboard cannot keep an API key secret. Its compatible API profile is therefore:

```bash
AIR_REQUIRE_API_KEY=false
AIR_CORS_ORIGINS=https://dashboard.example.edu
```

Replace the origin with the actual dashboard origin. This exposes read-only measurements and keeps IP and MAC metadata redacted. The authenticated API-only example earlier in this document is a different deployment profile and will return 401 to the static dashboard. Do not weaken authentication on an existing deployment without confirming that public telemetry is acceptable.
