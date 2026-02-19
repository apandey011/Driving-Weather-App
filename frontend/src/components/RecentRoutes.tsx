export interface RecentRoute {
  origin: string;
  destination: string;
  originDisplay: string;
  destinationDisplay: string;
  timestamp: number;
}

const STORAGE_KEY = "route-weather-history";
const MAX_ENTRIES = 5;

export function loadHistory(): RecentRoute[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function saveToHistory(entry: RecentRoute): void {
  const history = loadHistory();
  const filtered = history.filter(
    (h) => !(h.origin === entry.origin && h.destination === entry.destination)
  );
  filtered.unshift(entry);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(filtered.slice(0, MAX_ENTRIES)));
}