import { loadHistory, saveToHistory, RecentRoute } from "./RecentRoutes";

const STORAGE_KEY = "route-weather-history";

function makeEntry(overrides?: Partial<RecentRoute>): RecentRoute {
  return {
    origin: "San Francisco, CA",
    destination: "Los Angeles, CA",
    originDisplay: "San Francisco",
    destinationDisplay: "Los Angeles",
    timestamp: Date.now(),
    ...overrides,
  };
}

describe("RecentRoutes", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  describe("loadHistory", () => {
    it("returns empty array when localStorage is empty", () => {
      expect(loadHistory()).toEqual([]);
    });

    it("returns parsed JSON from localStorage", () => {
      const entries = [makeEntry()];
      localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
      const result = loadHistory();
      expect(result).toHaveLength(1);
      expect(result[0].origin).toBe("San Francisco, CA");
    });

    it("returns empty array on corrupted JSON", () => {
      localStorage.setItem(STORAGE_KEY, "not valid json{{{");
      expect(loadHistory()).toEqual([]);
    });
  });

  describe("saveToHistory", () => {
    it("adds a new entry to empty history", () => {
      const entry = makeEntry();
      saveToHistory(entry);
      const result = loadHistory();
      expect(result).toHaveLength(1);
      expect(result[0].origin).toBe("San Francisco, CA");
    });

    it("deduplicates by origin and destination", () => {
      const entry1 = makeEntry({ timestamp: 1000 });
      const entry2 = makeEntry({ timestamp: 2000 });
      saveToHistory(entry1);
      saveToHistory(entry2);
      const result = loadHistory();
      expect(result).toHaveLength(1);
      expect(result[0].timestamp).toBe(2000);
    });

    it("limits history to 5 entries", () => {
      for (let i = 0; i < 7; i++) {
        saveToHistory(makeEntry({ origin: `City ${i}`, destination: `City ${i + 10}` }));
      }
      const result = loadHistory();
      expect(result).toHaveLength(5);
    });
  });

});
