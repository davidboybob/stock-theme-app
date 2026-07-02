import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceLine,
} from "recharts";
import type { StockDetail } from "../api/client";
import OrderPanel from "./OrderPanel";
import { useTradingAccount } from "../hooks/useTradingAccount";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8001";

interface Props {
  code: string;
  onClose: () => void;
}

interface HistoryItem {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

type Period = "20" | "60" | "120";

const PERIOD_LABELS: Record<Period, string> = {
  "20": "1개월",
  "60": "3개월",
  "120": "6개월",
};

function formatDate(raw: string): string {
  // raw = "20240101"
  if (raw.length === 8) return `${raw.slice(4, 6)}/${raw.slice(6, 8)}`;
  return raw;
}

export default function StockModal({ code, onClose }: Props) {
  const [data, setData] = useState<StockDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [period, setPeriod] = useState<Period>("60");
  const [orderSide, setOrderSide] = useState<"BUY" | "SELL" | null>(null);
  const trading = useTradingAccount();

  useEffect(() => {
    setLoading(true);
    setData(null);
    fetch(`${API_BASE}/api/stocks/${code}/detail`)
      .then((r) => r.json())
      .then((d: StockDetail) => {
        setData(d);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [code]);

  useEffect(() => {
    setHistoryLoading(true);
    fetch(`${API_BASE}/api/stocks/${code}/history?count=${period}`)
      .then((r) => r.json())
      .then((d: HistoryItem[]) => {
        setHistory(d);
        setHistoryLoading(false);
      })
      .catch(() => setHistoryLoading(false));
  }, [code, period]);

  const isUp = (data?.change_rate ?? 0) >= 0;
  const chartColor = isUp ? "#ef4444" : "#3b82f6";

  const firstClose = history.length > 0 ? history[0].close : null;
  const minClose = history.length > 0 ? Math.min(...history.map((h) => h.close)) : 0;
  const maxClose = history.length > 0 ? Math.max(...history.map((h) => h.close)) : 0;
  const padding = (maxClose - minClose) * 0.1 || 100;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose}>
          ✕
        </button>

        {loading && <div className="loading">로딩 중...</div>}

        {!loading && data && (
          <>
            <h2>
              {data.name}
              <span className="modal-code">{data.code}</span>
            </h2>
            <div className={`modal-price ${isUp ? "up" : "down"}`}>
              {data.current_price.toLocaleString()}원
              <span className="modal-change">
                {isUp ? "▲" : "▼"} {Math.abs(data.change_price).toLocaleString()} (
                {isUp ? "+" : ""}
                {data.change_rate.toFixed(2)}%)
              </span>
            </div>

            {/* 기간 선택 탭 */}
            <div className="chart-period-tabs">
              {(Object.keys(PERIOD_LABELS) as Period[]).map((p) => (
                <button
                  key={p}
                  className={`chart-period-btn${period === p ? " active" : ""}`}
                  onClick={() => setPeriod(p)}
                >
                  {PERIOD_LABELS[p]}
                </button>
              ))}
            </div>

            {/* 주가 차트 */}
            <div className="chart-wrapper">
              {historyLoading ? (
                <div className="loading">차트 로딩 중...</div>
              ) : history.length > 0 ? (
                <ResponsiveContainer width="100%" height={180}>
                  <LineChart data={history} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
                    <XAxis
                      dataKey="date"
                      tickFormatter={formatDate}
                      tick={{ fontSize: 10, fill: "#9ca3af" }}
                      interval={Math.floor(history.length / 5)}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      domain={[minClose - padding, maxClose + padding]}
                      tickFormatter={(v) => v.toLocaleString()}
                      tick={{ fontSize: 10, fill: "#9ca3af" }}
                      axisLine={false}
                      tickLine={false}
                      width={60}
                    />
                    <Tooltip
                      formatter={(value) => [`${Number(value).toLocaleString()}원`, "종가"]}
                      labelFormatter={(label) => {
                        const s = String(label);
                        if (s.length === 8)
                          return `${s.slice(0, 4)}.${s.slice(4, 6)}.${s.slice(6, 8)}`;
                        return label;
                      }}
                      contentStyle={{ fontSize: 12 }}
                    />
                    {firstClose && (
                      <ReferenceLine
                        y={firstClose}
                        stroke="#d1d5db"
                        strokeDasharray="4 4"
                        strokeWidth={1}
                      />
                    )}
                    <Line
                      type="monotone"
                      dataKey="close"
                      stroke={chartColor}
                      strokeWidth={2}
                      dot={false}
                      activeDot={{ r: 4 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="error" style={{ fontSize: 12 }}>
                  차트 데이터 없음
                </div>
              )}
            </div>

            {/* 상세 지표 테이블 */}
            <table className="modal-table">
              <tbody>
                <tr>
                  <td>시가</td>
                  <td>{data.open_price.toLocaleString()}</td>
                </tr>
                <tr>
                  <td>고가</td>
                  <td className="up">{data.high_price.toLocaleString()}</td>
                </tr>
                <tr>
                  <td>저가</td>
                  <td className="down">{data.low_price.toLocaleString()}</td>
                </tr>
                <tr>
                  <td>거래량</td>
                  <td>{data.volume.toLocaleString()}</td>
                </tr>
                {data.week52_high != null && (
                  <tr>
                    <td>52주 최고</td>
                    <td className="up">{data.week52_high.toLocaleString()}</td>
                  </tr>
                )}
                {data.week52_low != null && (
                  <tr>
                    <td>52주 최저</td>
                    <td className="down">{data.week52_low.toLocaleString()}</td>
                  </tr>
                )}
                {data.per != null && (
                  <tr>
                    <td>PER</td>
                    <td>{data.per.toFixed(2)}배</td>
                  </tr>
                )}
                {data.pbr != null && (
                  <tr>
                    <td>PBR</td>
                    <td>{data.pbr.toFixed(2)}배</td>
                  </tr>
                )}
                {data.market_cap != null && (
                  <tr>
                    <td>시가총액</td>
                    <td>{(data.market_cap / 100_000_000).toLocaleString()}억</td>
                  </tr>
                )}
              </tbody>
            </table>

            {/* 주문 (토스증권 연동 시) */}
            {trading.available && trading.accountSeq != null && (
              orderSide ? (
                <OrderPanel
                  accountSeq={trading.accountSeq}
                  symbol={data.code}
                  name={data.name}
                  currentPrice={data.current_price}
                  side={orderSide}
                  onDone={() => setOrderSide(null)}
                />
              ) : (
                <div style={{ display: "flex", gap: "0.5rem", marginTop: "1rem" }}>
                  <button
                    onClick={() => setOrderSide("BUY")}
                    style={{ flex: 1, background: "#e53935", color: "#fff", padding: "0.6rem", borderRadius: 6, border: "none", cursor: "pointer" }}
                  >
                    매수
                  </button>
                  <button
                    onClick={() => setOrderSide("SELL")}
                    style={{ flex: 1, background: "#1e88e5", color: "#fff", padding: "0.6rem", borderRadius: 6, border: "none", cursor: "pointer" }}
                  >
                    매도
                  </button>
                </div>
              )
            )}
          </>
        )}

        {!loading && !data && (
          <div className="error">데이터를 불러올 수 없습니다.</div>
        )}
      </div>
    </div>
  );
}
