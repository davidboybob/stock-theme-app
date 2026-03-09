import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

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
  (import.meta.env.VITE_WS_URL || "ws://localhost:8000") + "/api/ws/alerts";
