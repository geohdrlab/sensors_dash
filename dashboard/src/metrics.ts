import type { MetricKey } from "./types";

export const metricDefinitions: Record<MetricKey, { label: string; unit: string }> = {
  co2: { label: "CO₂", unit: "ppm" },
  pm1_0: { label: "PM1.0", unit: "µg/m³" },
  pm2_5: { label: "PM2.5", unit: "µg/m³" },
  pm4_0: { label: "PM4.0", unit: "µg/m³" },
  pm10: { label: "PM10", unit: "µg/m³" },
  voc: { label: "VOC", unit: "index" },
  nox: { label: "NOx", unit: "index" },
  temperature: { label: "Temperature", unit: "°F" },
  humidity: { label: "Humidity", unit: "%" },
  pressure: { label: "Pressure", unit: "hPa" },
  rssi: { label: "Wi-Fi signal", unit: "dBm" },
};

export function metricTone(metric: MetricKey, value: number | null): string {
  if (value === null) return "neutral";
  if (metric === "pm2_5") {
    if (value <= 9) return "good";
    if (value <= 35.4) return "moderate";
    return "poor";
  }
  if (metric === "voc") {
    if (value < 100) return "good";
    if (value < 200) return "moderate";
    return "poor";
  }
  if (metric === "nox") {
    if (value < 2) return "good";
    if (value < 10) return "moderate";
    return "poor";
  }
  if (metric === "rssi") {
    if (value >= -65) return "good";
    if (value >= -78) return "moderate";
    return "poor";
  }
  return "neutral";
}

export function formatMetric(value: number | null): string {
  if (value === null) return "No data";
  if (Number.isInteger(value)) return value.toLocaleString();
  return value.toLocaleString(undefined, { maximumFractionDigits: 1 });
}
