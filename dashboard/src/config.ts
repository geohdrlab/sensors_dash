export interface DashboardConfig {
  apiBaseUrl: string;
  refreshIntervalMs: number;
}

const DEFAULT_REFRESH_INTERVAL_MS = 30000;
const MIN_REFRESH_INTERVAL_MS = 5000;

export function normalizeBaseUrl(value: string | undefined): string {
  const trimmed = value?.trim() ?? "";
  if (!trimmed || trimmed === "/") return "";
  return trimmed.replace(/\/+$/, "");
}

export function normalizeRefreshInterval(value: number | undefined): number {
  if (!Number.isFinite(value) || value === undefined) return DEFAULT_REFRESH_INTERVAL_MS;
  return Math.max(MIN_REFRESH_INTERVAL_MS, Math.floor(value));
}

export async function loadDashboardConfig(): Promise<DashboardConfig> {
  let runtime: Partial<DashboardConfig> = {};
  try {
    const response = await fetch(`${import.meta.env.BASE_URL}dashboard-config.json`, {
      cache: "no-store",
    });
    if (response.ok) runtime = (await response.json()) as Partial<DashboardConfig>;
  } catch {
    // Same-origin defaults keep the dashboard usable when no runtime file is present.
  }
  return {
    apiBaseUrl: normalizeBaseUrl(runtime.apiBaseUrl),
    refreshIntervalMs: normalizeRefreshInterval(runtime.refreshIntervalMs),
  };
}
