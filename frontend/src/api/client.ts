import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8001";

export const apiClient = axios.create({
  baseURL: `${BASE_URL}/api`,
  timeout: 15000,
});

// Types
export interface ThemeStrength {
  theme_id: string;
  theme_name: string;
  avg_change_rate: number;
  rising_count: number;
  falling_count: number;
  total: number;
}

export interface StockPrice {
  code: string;
  name: string;
  current_price: number;
  change_price: number;
  change_rate: number;
  volume: number;
  high_price: number;
  low_price: number;
  open_price: number;
}

export interface StockDetail extends StockPrice {
  week52_high: number | null;
  week52_low: number | null;
  per: number | null;
  pbr: number | null;
  market_cap: number | null;
}

export interface ThemeDetail {
  id: string;
  name: string;
  description: string | null;
  strength: ThemeStrength;
  stock_prices: StockPrice[];
}

export interface IndexPrice {
  code: string;
  name: string;
  current_value: number;
  change_value: number;
  change_rate: number;
}

export interface Alert {
  id: string;
  target_type: string;
  target_id: string;
  target_name: string;
  condition: string;
  threshold: number;
  is_active: boolean;
  created_at: string;
}

export interface AlertCreate {
  target_type: string;
  target_id: string;
  condition: string;
  threshold: number;
}

export interface ThemeHistory {
  avg_change_rate: number;
  rising_count: number;
  falling_count: number;
  total: number;
  recorded_at: string;
}

// API functions
export const fetchStockDetail = (code: string) =>
  apiClient.get<StockDetail>(`/stocks/${code}/detail`).then((r) => r.data);

export const fetchThemes = () =>
  apiClient.get<ThemeStrength[]>("/themes").then((r) => r.data);

export const fetchThemeDetail = (id: string) =>
  apiClient.get<ThemeDetail>(`/themes/${id}`).then((r) => r.data);

export const fetchIndices = () =>
  apiClient.get<IndexPrice[]>("/indices").then((r) => r.data);

export const fetchAlerts = () =>
  apiClient.get<Alert[]>("/alerts").then((r) => r.data);

export const createAlert = (data: AlertCreate) =>
  apiClient.post<Alert>("/alerts", data).then((r) => r.data);

export const deleteAlert = (id: string) =>
  apiClient.delete(`/alerts/${id}`).then((r) => r.data);

export const toggleAlert = (id: string) =>
  apiClient.patch<Alert>(`/alerts/${id}`).then((r) => r.data);

export interface AlertHistory {
  id: number;
  alert_id: string;
  target_name: string;
  current_value: number;
  threshold: number;
  condition: string;
  triggered_at: string;
}

export const fetchAlertHistory = () =>
  apiClient.get<AlertHistory[]>("/alerts/history").then((r) => r.data);

export const fetchThemeHistory = (id: string, period = "1d") =>
  apiClient.get<ThemeHistory[]>(`/themes/${id}/history`, { params: { period } }).then((r) => r.data);

export const WS_URL =
  (import.meta.env.VITE_WS_URL || "ws://localhost:8001") + "/api/ws/alerts";

// ── 트레이딩 (토스증권) ──────────────────────────────────

export interface TossAccount {
  account_no: string;
  account_seq: number;
  account_type: string;
}

export interface CurrencyAmount {
  krw?: number | null;
  usd?: number | null;
  [key: string]: unknown;
}

export interface ProfitLossInfo {
  amount?: number;
  amountAfterCost?: number;
  rate?: number;
  rateAfterCost?: number;
  [key: string]: unknown;
}

export interface HoldingItem {
  symbol: string;
  name: string;
  market_country: string;
  currency: string;
  quantity: number;
  last_price: number;
  average_purchase_price: number;
  market_value: CurrencyAmount | null;
  profit_loss: ProfitLossInfo | null;
  daily_profit_loss: ProfitLossInfo | null;
}

export interface PortfolioSummary {
  total_purchase_amount: CurrencyAmount | null;
  market_value: CurrencyAmount | null;
  profit_loss: ProfitLossInfo | null;
  daily_profit_loss: ProfitLossInfo | null;
  items: HoldingItem[];
}

export const fetchTossAccounts = () =>
  apiClient.get<TossAccount[]>("/account").then((r) => r.data);

export const fetchHoldings = (accountSeq: number) =>
  apiClient
    .get<PortfolioSummary>("/account/holdings", { params: { account_seq: accountSeq } })
    .then((r) => r.data);

// ── 주문 ──────────────────────────────────────────────

export interface OrderCreate {
  symbol: string;
  side: "BUY" | "SELL";
  order_type: "LIMIT" | "MARKET";
  quantity: number;
  price?: number | null;
  confirm_high_value?: boolean;
}

export interface Order {
  order_id: string;
  symbol: string;
  side: string;
  order_type: string;
  status: string;
  price: number | null;
  quantity: number;
  filled_quantity: number;
  currency: string;
  ordered_at: string | null;
  canceled_at: string | null;
}

export interface OrderLogEntry {
  id: number;
  action: string;
  source: string;
  symbol: string | null;
  side: string | null;
  order_type: string | null;
  quantity: number | null;
  price: number | null;
  order_id: string | null;
  status: string | null;
  success: boolean | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
}

const acct = (accountSeq: number) => ({ params: { account_seq: accountSeq } });

export const createOrder = (accountSeq: number, data: OrderCreate) =>
  apiClient.post<Order>("/orders", data, acct(accountSeq)).then((r) => r.data);

export const fetchOpenOrders = (accountSeq: number) =>
  apiClient.get<Order[]>("/orders", acct(accountSeq)).then((r) => r.data);

export const cancelOrder = (accountSeq: number, orderId: string) =>
  apiClient.post<Order>(`/orders/${orderId}/cancel`, {}, acct(accountSeq)).then((r) => r.data);

export const modifyOrder = (
  accountSeq: number,
  orderId: string,
  data: { quantity?: number; price?: number }
) =>
  apiClient.post<Order>(`/orders/${orderId}/modify`, data, acct(accountSeq)).then((r) => r.data);

export const fetchOrderLog = (accountSeq: number) =>
  apiClient.get<OrderLogEntry[]>("/orders/log", acct(accountSeq)).then((r) => r.data);

export const fetchBuyingPower = (accountSeq: number) =>
  apiClient
    .get<{ amount?: number; [k: string]: unknown }>("/orders/buying-power", acct(accountSeq))
    .then((r) => r.data);

export const fetchSellableQuantity = (accountSeq: number, symbol: string) =>
  apiClient
    .get<{ quantity?: number; [k: string]: unknown }>("/orders/sellable-quantity", {
      params: { account_seq: accountSeq, symbol },
    })
    .then((r) => r.data);
