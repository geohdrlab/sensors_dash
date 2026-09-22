# AIR-1 dashboard

This directory contains a static React dashboard for the AIR-1 API. It is a separate application from the Python service:

- It has its own dependencies, tests, build, and output directory.
- The API does not import, build, mount, or serve dashboard files.
- Deploying or restarting the dashboard does not restart the collector or API.
- The dashboard only makes read-only requests to the public `/api/v1` endpoints.

## Local development

Node.js 22 or newer is recommended.

```bash
cd dashboard
npm ci
npm run dev
```

The development server proxies `/api` and WebSocket requests to `http://127.0.0.1:8000`. Start the API separately with `./scripts/start.sh` from the repository root.

## Checks and static build

```bash
cd dashboard
npm test
npm run lint
npm run build
```

The production files are written to `dashboard/dist/`. Any static web server can serve that directory. The build does not need Node.js after it finishes.

## Runtime API address

The production build reads `dashboard-config.json` before React starts. Edit the copy in `dist/` when deploying to a different API address:

```json
{
  "apiBaseUrl": "https://api.omsserver.online",
  "refreshIntervalMs": 30000
}
```

An empty `apiBaseUrl` uses the dashboard's origin. This is useful when a reverse proxy sends `/api/v1/*` to the API. A full HTTPS URL is required when the dashboard and API use different origins.

Do not put an API key in this file. Static files are public to every visitor. The intended public dashboard configuration leaves API authentication optional so read-only measurements are available while IP and MAC fields remain redacted.

For a cross-origin deployment, add the exact dashboard origin to the API environment. An origin has no path:

```bash
AIR_CORS_ORIGINS=https://geohdrlab.github.io
```

The browser will use `wss://` automatically when the API address starts with `https://`. If the WebSocket is unavailable, the dashboard continues refreshing with REST requests.

## GitHub Pages readiness

The Vite build uses relative asset paths, so `dist/` can be hosted at `/sensors_dash/`. A Pages workflow is intentionally not included until a repository maintainer enables GitHub Pages. Adding the dashboard does not change the API deployment.
