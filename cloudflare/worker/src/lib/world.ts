export interface WorldIndex {
  stooq: string;
  yahoo: string;
  name: string;
  country: string;
  iso: string;
  lat: number;
  lng: number;
  finnhub?: string;
}

export const WORLD_INDICES: WorldIndex[] = [
  { stooq: "^spx", yahoo: "^GSPC", name: "S&P 500", country: "United States", iso: "USA", lat: 38.9, lng: -95.0, finnhub: "SPY" },
  { stooq: "^dji", yahoo: "^DJI",  name: "Dow Jones", country: "United States", iso: "USA", lat: 32.5, lng: -88.0, finnhub: "DIA" },
  { stooq: "^ndq", yahoo: "^IXIC", name: "Nasdaq", country: "United States", iso: "USA", lat: 44.0, lng: -89.0, finnhub: "QQQ" },
  { stooq: "^ftm", yahoo: "^FTSE", name: "FTSE 100", country: "United Kingdom", iso: "GBR", lat: 53.0, lng: -2.0 },
  { stooq: "^dax", yahoo: "^GDAXI", name: "DAX", country: "Germany", iso: "DEU", lat: 52.0, lng: 12.0 },
  { stooq: "^cac", yahoo: "^FCHI", name: "CAC 40", country: "France", iso: "FRA", lat: 46.5, lng: 2.5 },
  { stooq: "^nkx", yahoo: "^N225", name: "Nikkei 225", country: "Japan", iso: "JPN", lat: 38.0, lng: 138.5 },
  { stooq: "^hsi", yahoo: "^HSI",  name: "Hang Seng", country: "Hong Kong", iso: "HKG", lat: 22.5, lng: 114.2 },
  { stooq: "^kospi", yahoo: "^KS11", name: "KOSPI", country: "South Korea", iso: "KOR", lat: 36.5, lng: 127.8 },
  { stooq: "^xjo", yahoo: "^AXJO", name: "ASX 200", country: "Australia", iso: "AUS", lat: -25.0, lng: 134.0 },
  { stooq: "^shc", yahoo: "000001.SS", name: "Shanghai Composite", country: "China", iso: "CHN", lat: 31.5, lng: 118.0 },
  { stooq: "^bsx", yahoo: "^BSESN", name: "Sensex", country: "India", iso: "IND", lat: 22.0, lng: 78.0 },
  { stooq: "^nse", yahoo: "^NSEI",  name: "Nifty 50", country: "India", iso: "IND", lat: 18.5, lng: 78.5 },
  { stooq: "^twse", yahoo: "^TWII", name: "TWSE", country: "Taiwan", iso: "TWN", lat: 24.0, lng: 121.0 },
  { stooq: "^sti",  yahoo: "^STI",  name: "Singapore STI", country: "Singapore", iso: "SGP", lat: 1.4, lng: 103.8 },
];

export function getIndexMeta(stooqSymbol: string): WorldIndex | undefined {
  const needle = stooqSymbol.toLowerCase();
  return WORLD_INDICES.find((m) => m.stooq.toLowerCase() === needle);
}
