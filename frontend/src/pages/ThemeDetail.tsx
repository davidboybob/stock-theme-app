import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchThemeDetail, fetchThemeHistory } from "../api/client";
import type { StockPrice } from "../api/client";
import StockTable from "../components/StockTable";
import StockModal from "../components/StockModal";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
  ResponsiveContainer,
  LabelList,
  LineChart,
  Line,
  CartesianGrid,
  ReferenceLine,
} from "recharts";

const getPosition = (stock: StockPrice): number => {
  const range = stock.high_price - stock.low_price;
  if (range === 0) return 50;
  return ((stock.current_price - stock.low_price) / range) * 100;
};

export default function ThemeDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [modalCode, setModalCode] = useState<string | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["theme", id],
    queryFn: () => fetchThemeDetail(id!),
    refetchInterval: 30000,
    enabled: !!id,
  });

  const { data: history } = useQuery({
    queryKey: ["theme-history", id],
    queryFn: () => fetchThemeHistory(id!),
    enabled: !!id,
    refetchInterval: 600000,
  });

  if (isLoading) return <div className="page loading">로딩 중...</div>;
  if (isError)
    return (
      <div className="page error">
        데이터 조회 실패.{" "}
        <button onClick={() => navigate(-1)}>돌아가기</button>
      </div>
    );
  if (!data) return null;

  const { strength } = data;
  const isUp = strength.avg_change_rate >= 0;

  const historyChartData = history?.map((h) => ({
    time: new Date(h.recorded_at).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" }),
    rate: h.avg_change_rate,
  }));

  const chartData = [...data.stock_prices]
    .sort((a, b) => b.change_rate - a.change_rate)
    .map((s) => ({ name: s.name, value: s.change_rate, code: s.code }));

  return (
    <div className="page">
      <div className="page-header">
        <button className="back-btn" onClick={() => navigate(-1)}>
          ← 목록
        </button>
        <h1>{data.name}</h1>
      </div>

      {data.description && <p className="theme-desc">{data.description}</p>}

      <div className="strength-summary">
        <div className={`strength-rate ${isUp ? "up" : "down"}`}>
          평균 등락률: {isUp ? "+" : ""}
          {strength.avg_change_rate.toFixed(2)}%
        </div>
        <div className="strength-counts">
          <span className="up">상승 {strength.rising_count}종목</span>
          {" / "}
          <span className="down">하락 {strength.falling_count}종목</span>
          {" / "}
          <span>보합 {strength.total - strength.rising_count - strength.falling_count}종목</span>
        </div>
      </div>

      {historyChartData && historyChartData.length >= 2 ? (
        <div className="history-chart">
          <h3>당일 테마 강도 추이</h3>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={historyChartData} margin={{ left: 10, right: 20 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" tick={{ fontSize: 11 }} />
              <YAxis tickFormatter={(v: number) => `${v.toFixed(1)}%`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => [v != null ? `${Number(v).toFixed(2)}%` : "-", "평균 등락률"]} />
              <ReferenceLine y={0} stroke="#888" strokeDasharray="3 3" />
              <Line type="monotone" dataKey="rate" stroke="#e74c3c" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="history-empty">히스토리 데이터가 쌓이면 추이 차트가 표시됩니다 (10분 주기 수집)</div>
      )}

      {data.stock_prices.length > 0 && (
        <>
          <h2>종목별 등락률</h2>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height={Math.max(300, chartData.length * 36)}>
              <BarChart data={chartData} layout="vertical" margin={{ left: 70, right: 60 }}>
                <XAxis
                  type="number"
                  tickFormatter={(v: number) => `${v.toFixed(1)}%`}
                  tick={{ fontSize: 11 }}
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={65}
                  tick={{ fontSize: 12 }}
                />
                <Tooltip
                  formatter={(v) => [
                    v !== undefined && v !== null
                      ? `${Number(v as number).toFixed(2)}%`
                      : "-",
                    "등락률",
                  ]}
                />
                <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                  {chartData.map((entry, i) => (
                    <Cell
                      key={i}
                      fill={entry.value >= 0 ? "#c0392b" : "#2980b9"}
                    />
                  ))}
                  <LabelList
                    dataKey="value"
                    position="right"
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    formatter={(v: any) => {
                      if (v == null) return "";
                      const n = Number(v);
                      return `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;
                    }}
                    style={{ fontSize: 11 }}
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <h2>당일 가격 범위 (저가 — 현재가 — 고가)</h2>
          <div className="price-range-list">
            {[...data.stock_prices]
              .sort((a, b) => b.change_rate - a.change_rate)
              .map((stock) => {
                const pos = getPosition(stock);
                const isStockUp = stock.change_rate >= 0;
                return (
                  <div key={stock.code} className="price-range-row">
                    <div className="price-range-name">{stock.name}</div>
                    <div className="price-range-bar-wrap">
                      <span className="price-range-low">
                        {stock.low_price.toLocaleString("ko-KR")}
                      </span>
                      <div className="price-range-bar">
                        <div
                          className="price-range-fill"
                          style={{ width: `${pos}%` }}
                        />
                        <div
                          className="price-range-marker"
                          style={{
                            left: `${pos}%`,
                            backgroundColor: isStockUp ? "#c0392b" : "#2980b9",
                          }}
                          title={`현재가: ${stock.current_price.toLocaleString("ko-KR")}원`}
                        />
                      </div>
                      <span className="price-range-high">
                        {stock.high_price.toLocaleString("ko-KR")}
                      </span>
                    </div>
                    <div
                      className={`price-range-rate ${isStockUp ? "up" : "down"}`}
                    >
                      {isStockUp ? "+" : ""}
                      {stock.change_rate.toFixed(2)}%
                    </div>
                  </div>
                );
              })}
          </div>
        </>
      )}

      <h2>종목 현황</h2>
      {data.stock_prices.length > 0 ? (
        <StockTable stocks={data.stock_prices} onSelect={setModalCode} />
      ) : (
        <div className="empty">종목 데이터를 불러올 수 없습니다.</div>
      )}

      {modalCode && (
        <StockModal code={modalCode} onClose={() => setModalCode(null)} />
      )}
    </div>
  );
}
