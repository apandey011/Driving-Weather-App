import { fetchRouteWeather } from "./api";
import { makeRouteData } from "./test/fixtures";

describe("fetchRouteWeather", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns parsed JSON on successful request", async () => {
    const mockData = makeRouteData();
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockData),
    });
    vi.stubGlobal("fetch", mockFetch);

    const result = await fetchRouteWeather("SF", "LA");
    expect(result).toEqual(mockData);
  });

  it("sends departure_time in request body", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(makeRouteData()),
    });
    vi.stubGlobal("fetch", mockFetch);

    await fetchRouteWeather("SF", "LA", "2026-02-16T10:00:00Z");

    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body.departure_time).toBe("2026-02-16T10:00:00Z");
  });

  it("converts naive departure_time to timezone-aware ISO string", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(makeRouteData()),
    });
    vi.stubGlobal("fetch", mockFetch);

    const naive = "2026-02-16T10:00";
    await fetchRouteWeather("SF", "LA", naive);

    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body.departure_time).toBe(new Date(naive).toISOString());
  });

  it("sends null departure_time when undefined", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(makeRouteData()),
    });
    vi.stubGlobal("fetch", mockFetch);

    await fetchRouteWeather("SF", "LA");

    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body.departure_time).toBeNull();
  });

  it("throws on invalid departure_time format before fetch", async () => {
    const mockFetch = vi.fn();
    vi.stubGlobal("fetch", mockFetch);

    await expect(
      fetchRouteWeather("SF", "LA", "not-a-date")
    ).rejects.toThrow("Invalid departure time format");
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("throws with detail message on HTTP error with JSON body", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      json: () => Promise.resolve({ detail: "Invalid origin address" }),
    });
    vi.stubGlobal("fetch", mockFetch);

    await expect(fetchRouteWeather("", "LA")).rejects.toThrow("Invalid origin address");
  });

  it("throws generic message on HTTP error with non-JSON body", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.reject(new Error("not json")),
    });
    vi.stubGlobal("fetch", mockFetch);

    await expect(fetchRouteWeather("SF", "LA")).rejects.toThrow("Failed to fetch route weather");
  });

  it("re-throws network errors", async () => {
    const mockFetch = vi.fn().mockRejectedValue(new TypeError("Network error"));
    vi.stubGlobal("fetch", mockFetch);

    await expect(fetchRouteWeather("SF", "LA")).rejects.toThrow("Network error");
  });

  it("throws 'Request timed out' on AbortError", async () => {
    const abortError = new DOMException("The operation was aborted", "AbortError");
    const mockFetch = vi.fn().mockRejectedValue(abortError);
    vi.stubGlobal("fetch", mockFetch);

    await expect(fetchRouteWeather("SF", "LA")).rejects.toThrow(
      "Request timed out — please try again"
    );
  });

  it("sends correct Content-Type header", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(makeRouteData()),
    });
    vi.stubGlobal("fetch", mockFetch);

    await fetchRouteWeather("SF", "LA");

    const headers = mockFetch.mock.calls[0][1].headers;
    expect(headers["Content-Type"]).toBe("application/json");
  });
});
