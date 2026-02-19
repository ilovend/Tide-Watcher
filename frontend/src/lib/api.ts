const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "Unknown error");
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

// ---------- 股票 ----------

export const stockApi = {
  list: () => request<{ count: number; data: StockItem[] }>("/api/stocks/list"),
  realtime: (code: string) => request<{ data: RealtimeQuote }>(`/api/stocks/realtime/${code}`),
  realtimeAll: () => request<{ count: number; data: RealtimeQuote[] }>("/api/stocks/realtime"),
  klineLatest: (code: string, level = "d", limit = 60) =>
    request<{ count: number; data: KlineBar[] }>(
      `/api/stocks/kline/${code}/latest?level=${level}&adjust=n&limit=${limit}`
    ),
  company: (code: string, type: string) =>
    request<{ data: Record<string, unknown> }>(`/api/stocks/company/${code}/${type}`),
  instrument: (code: string) => request<{ data: InstrumentInfo }>(`/api/stocks/instrument/${code}`),
};

// ---------- 股池 ----------

export const poolApi = {
  types: () => request<{ data: PoolType[] }>("/api/pools/types"),
  get: (type: string, date: string) =>
    request<{ pool_type: string; pool_name: string; date: string; count: number; data: PoolStock[] }>(
      `/api/pools/${type}/${date}`
    ),
  historyZtgc: (params?: { date?: string; code?: string; limit?: number }) => {
    const sp = new URLSearchParams();
    if (params?.date) sp.set("date", params.date);
    if (params?.code) sp.set("code", params.code);
    if (params?.limit) sp.set("limit", String(params.limit));
    const qs = sp.toString();
    return request<{ count: number; data: LimitUpRecord[] }>(`/api/pools/history/ztgc${qs ? `?${qs}` : ""}`);
  },
  historyZbgc: (params?: { date?: string; limit?: number }) => {
    const sp = new URLSearchParams();
    if (params?.date) sp.set("date", params.date);
    if (params?.limit) sp.set("limit", String(params.limit));
    const qs = sp.toString();
    return request<{ count: number; data: Record<string, unknown>[] }>(`/api/pools/history/zbgc${qs ? `?${qs}` : ""}`);
  },
  emotionLatest: (limit = 30) =>
    request<{ count: number; data: EmotionSnapshot[] }>(`/api/pools/emotion/latest?limit=${limit}`),
  emotionByDate: (date: string) =>
    request<{ data: EmotionSnapshot | null }>(`/api/pools/emotion/${date}`),
  sectors: (type = "", limit = 500) => {
    const sp = new URLSearchParams();
    if (type) sp.set("sector_type", type);
    if (limit) sp.set("limit", String(limit));
    const qs = sp.toString();
    return request<{ count: number; data: SectorInfo[] }>(`/api/pools/sectors${qs ? `?${qs}` : ""}`);
  },
  sectorStocks: (sectorCode: string) =>
    request<{ sector_code: string; count: number; data: { stock_code: string; sector_name: string }[] }>(
      `/api/pools/sectors/${sectorCode}/stocks`
    ),
  stockSectors: (code: string) =>
    request<{ code: string; count: number; data: { sector_code: string; sector_name: string }[] }>(
      `/api/pools/sectors/stock/${code}`
    ),
  watchlist: () => request<{ count: number; data: WatchlistItem[] }>("/api/pools/watchlist"),
  addWatchlist: (code: string, name = "", note = "", tags = "") =>
    request<{ message: string; data: WatchlistItem }>(
      `/api/pools/watchlist?code=${code}&name=${encodeURIComponent(name)}&note=${encodeURIComponent(note)}&tags=${encodeURIComponent(tags)}`,
      { method: "POST" }
    ),
  removeWatchlist: (code: string) =>
    request<{ message: string }>(`/api/pools/watchlist/${code}`, { method: "DELETE" }),
  riskCheck: (code: string) =>
    request<RiskCheckResult>(`/api/pools/risk/check/${code}`),
  riskList: () =>
    request<{ count: number; data: RiskItem[] }>("/api/pools/risk/list"),
  timingToday: () =>
    request<TimingSignal>("/api/pools/timing/today"),
  timingByDate: (date: string) =>
    request<TimingSignal>(`/api/pools/timing/${date}`),
  timingCalendar: () =>
    request<SettlementCalendar>("/api/pools/timing/calendar"),
  globalStatus: () =>
    request<GlobalStatus>("/api/pools/global-status"),
};

// ---------- 策略 ----------

export const strategyApi = {
  list: () => request<{ count: number; data: StrategyInfo[] }>("/api/strategies/list"),
  run: (name: string, date?: string) =>
    request<{ strategy: string; signal_count: number; signals: Signal[] }>(
      `/api/strategies/run/${encodeURIComponent(name)}${date ? `?date=${date}` : ""}`,
      { method: "POST" }
    ),
  runAll: (date?: string) =>
    request<{ strategy_count: number; results: Record<string, { signal_count: number; signals: Signal[] }> }>(
      `/api/strategies/run-all${date ? `?date=${date}` : ""}`,
      { method: "POST" }
    ),
  signals: (params?: { strategy_name?: string; date?: string; limit?: number }) => {
    const sp = new URLSearchParams();
    if (params?.strategy_name) sp.set("strategy_name", params.strategy_name);
    if (params?.date) sp.set("date", params.date);
    if (params?.limit) sp.set("limit", String(params.limit));
    const qs = sp.toString();
    return request<{ count: number; data: SignalRecord[] }>(`/api/strategies/signals${qs ? `?${qs}` : ""}`);
  },
};

// ---------- 类型定义 ----------

export interface StockItem {
  dm: string;
  mc: string;
  jys: string;
}

export interface RealtimeQuote {
  dm?: string;
  t: string;
  p: number;
  pc: number;
  ud: number;
  o: number;
  h: number;
  l: number;
  yc: number;
  v: number;
  cje: number;
  zf: number;
  hs: number;
  pe: number;
  lb: number;
  sz: number;
  lt: number;
  zs: number;
  sjl: number;
}

export interface KlineBar {
  t: string;
  o: number;
  h: number;
  l: number;
  c: number;
  v: number;
  a: number;
  pc: number;
}

export interface PoolType {
  code: string;
  name: string;
}

export interface PoolStock {
  dm: string;
  mc?: string;
  p?: number;
  zf?: number;
  lbc?: number;
  zj?: number;
  zbc?: number;
  fbt?: string;
  lbt?: string;
  hs?: number;
  tj?: string;
  lb?: number;
  zs?: number;
  nh?: number;
  cje?: number;
  lt?: number;
  zsz?: number;
}

export interface StrategyInfo {
  name: string;
  schedule: string;
  description: string;
  enabled: boolean;
  tags: string[];
}

export interface Signal {
  stock_code: string;
  stock_name: string;
  score: number;
  reason: string;
  extra: Record<string, unknown>;
}

export interface SignalRecord extends Signal {
  id: number;
  strategy_name: string;
  signal_date: string;
  extra_data: string;
  created_at: string | null;
}

export interface InstrumentInfo {
  ei: string;
  ii: string;
  name: string;
  od: string;
  pc: number;
  up: number;
  dp: number;
  fv: number;
  tv: number;
  is: number;
}

// ---------- 新表结构类型 ----------

export interface LimitUpRecord {
  id: number;
  trade_date: string;
  code: string;
  name: string;
  price: number | null;
  change_pct: number | null;
  amount: number | null;
  float_mv: number | null;
  total_mv: number | null;
  turnover: number | null;
  limit_count: number;
  first_limit_time: string | null;
  last_limit_time: string | null;
  limit_amount: number | null;
  break_count: number;
  limit_stat: string | null;
}

export interface EmotionSnapshot {
  id: number;
  trade_date: string;
  limit_up_count: number;
  broken_board_count: number;
  broken_rate: number;
  max_streak: number;
  first_board_count: number;
  promotion_rate: number;
  total_limit_amount: number;
  phase: string;
  phase_score: number;
}

export interface SectorInfo {
  id: number;
  sector_code: string;
  sector_name: string;
  sector_type: string;
  stock_count: number;
  is_active: boolean;
}

export interface RiskCheckResult {
  code: string;
  has_risk: boolean;
  risk_type?: string;
  risk_level?: string;
  reason?: string;
  loss_years?: number;
  cumulative_loss?: number;
  latest_revenue?: number;
  scan_date?: string;
}

export interface RiskItem {
  code: string;
  name: string;
  risk_type: string;
  risk_level: string;
  reason: string;
  loss_years: number;
  cumulative_loss: number | null;
  latest_revenue: number | null;
  scan_date: string;
}

export interface TimingSignal {
  date: string;
  level: number;
  light: string;
  action: string;
  reason: string;
  details: string[];
  is_trading_day: boolean;
  is_holiday: boolean;
  holiday_name: string;
  next_open_date: string;
}

export interface SettlementCalendar {
  today: string;
  futures_day: string;
  options_day: string;
  next_futures_day: string;
  next_options_day: string;
  days_to_futures: number;
  days_to_options: number;
  is_futures_week: boolean;
  is_options_week: boolean;
}

export interface GlobalStatus {
  date: string;
  is_trading_day: boolean;
  is_holiday: boolean;
  holiday_name: string;
  next_open_date: string;
  timing_light: string;
  timing_action: string;
  timing_reason: string;
  risk_stock_total: number;
  risk_stock_extreme: number;
  risk_codes: string[];
}

export interface WatchlistItem {
  id: number;
  code: string;
  name: string;
  note: string;
  tags: string;
  added_at: string;
}
