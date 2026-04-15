import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const api = axios.create({ baseURL: `${BASE_URL}/api` });

// ─── Types ───────────────────────────────────────────────────────────────────

export interface TradingConfig {
  id?: string;
  short_ma: number;
  long_ma: number;
  stop_loss_pct: number;
  take_profit_pct: number;
  paper_initial_capital: number;
  paper_balance: number;
  is_running: boolean;
}

export interface WatchlistItem {
  id: string;
  stock_code: string;
  stock_name: string;
  theme_id?: string;
  is_active: boolean;
  added_at: string;
}

export interface Position {
  id: string;
  mode: "paper" | "real";
  stock_code: string;
  stock_name: string;
  quantity: number;
  entry_price: number;
  stop_loss_price: number;
  take_profit_price: number;
  entered_at: string;
  current_price?: number;
  unrealized_profit_loss?: number;
  return_rate?: number;
}

export interface TradeHistory {
  id: number;
  mode: "paper" | "real";
  stock_code: string;
  stock_name: string;
  signal_type: "BUY" | "SELL";
  price: number;
  quantity: number;
  reason: string;
  profit_loss?: number;
  executed_at: string;
}

export interface TradingSignal {
  stock_code: string;
  stock_name: string;
  signal_type: "BUY" | "SELL";
  price: number;
  quantity: number;
  reason: string;
  mode: string;
  message: string;
  timestamp: string;
}

// ─── API Functions ────────────────────────────────────────────────────────────

export const getTradingConfig = () =>
  api.get<TradingConfig>("/trading/config").then((r) => r.data);

export const updateTradingConfig = (data: Partial<TradingConfig>) =>
  api.put<TradingConfig>("/trading/config", data).then((r) => r.data);

export const toggleEngine = (is_running: boolean) =>
  api.post<TradingConfig>("/trading/config/toggle", { is_running }).then((r) => r.data);

export const resetPaperBalance = () =>
  api.post<TradingConfig>("/trading/config/reset-balance").then((r) => r.data);

export const getWatchlist = () =>
  api.get<WatchlistItem[]>("/trading/watchlist").then((r) => r.data);

export const addToWatchlist = (data: { stock_code: string; stock_name: string; theme_id?: string }) =>
  api.post<WatchlistItem>("/trading/watchlist", data).then((r) => r.data);

export const removeFromWatchlist = (id: string) =>
  api.delete(`/trading/watchlist/${id}`).then((r) => r.data);

export const getPositions = () =>
  api.get<Position[]>("/trading/positions").then((r) => r.data);

export const getTradeHistory = () =>
  api.get<TradeHistory[]>("/trading/history").then((r) => r.data);
