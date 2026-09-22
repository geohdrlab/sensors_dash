import { describe, expect, it } from "vitest";
import { normalizeBaseUrl, normalizeRefreshInterval } from "./config";

describe("dashboard configuration", () => {
  it("normalizes same-origin and absolute API URLs", () => {
    expect(normalizeBaseUrl(undefined)).toBe("");
    expect(normalizeBaseUrl("/")).toBe("");
    expect(normalizeBaseUrl(" https://api.example.edu/// ")).toBe("https://api.example.edu");
  });

  it("bounds the polling interval", () => {
    expect(normalizeRefreshInterval(undefined)).toBe(30000);
    expect(normalizeRefreshInterval(100)).toBe(5000);
    expect(normalizeRefreshInterval(12500.9)).toBe(12500);
  });
});
