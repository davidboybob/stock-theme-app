import { useState, useEffect, useRef, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, CartesianGrid,
} from "recharts";
import {
  getTradingConfig, updateTradingConfig, toggleEngine, resetPaperBalance,
  getWatchlist, addToWatchlist, removeFromWatchlist,
  getPositions, getTradeHistory, runBacktest,
} from "../api/trading";
import type {
  TradingConfig, TradingSignal, Position, TradeHistory, WatchlistItem,
  BacktestResult,
} from "../api/trading";
import { searchStocks } from "../api/client";
import { useToast } from "../hooks/useToast";
import Toast from "../components/Toast";

export default function Trading() {
  const qc = useQueryClient();
  const { toasts, show: showToast, remove: removeToast } = useToast();
  const [signalLog, setSignalLog] = useState<TradingSignal[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<{ code: string; name: string }[]>([]);
  const [configForm, setConfigForm] = useState<Partial<TradingConfig>>({});
  const [showStartConfirm, setShowStartConfirm] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectDelay = useRef(1000);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [backtestResult, setBacktestResult] = useState<BacktestResult | null>(null);
  const [backtestLoading, setBacktestLoading] = useState(false);

  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  useEffect(() => {
    const handler = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener("resize", handler);
    return () => window.removeEventListener("resize", handler);
  }, []);

  const { data: config } = useQuery({ queryKey: ["trading-config"], queryFn: getTradingConfig, refetchInterval: 15000 });
  const { data: watchlist = [] } = useQuery({ queryKey: ["watchlist"], queryFn: getWatchlist });
  const { data: positions = [] } = useQuery({ queryKey: ["positions"], queryFn: getPositions, refetchInterval: 30000 });
  const { data: history = [] } = useQuery({ queryKey: ["trade-history"], queryFn: getTradeHistory, refetchInterval: 30000 });

  const toggleMut = useMutation({
    mutationFn: (running: boolean) => toggleEngine(running),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["trading-config"] }),
    onError: () => showToast("엔진 상태 변경에 실패했습니다.", "error"),
  });

  const updateConfigMut = useMutation({
    mutationFn: updateTradingConfig,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["trading-config"] });
      setConfigForm({});
      showToast("설정이 저장되었습니다.", "success");
    },
    onError: () => showToast("설정 저장에 실패했습니다.", "error"),
  });

  const resetBalanceMut = useMutation({
    mutationFn: resetPaperBalance,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["trading-config"] }); showToast("잔고가 초기화되었습니다.", "success"); },
    onError: () => showToast("잔고 초기화에 실패했습니다.", "error"),
  });

  const addWatchMut = useMutation({
    mutationFn: addToWatchlist,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["watchlist"] }); setSearchQuery(""); setSearchResults([]); },
    onError: (e: Error) => showToast(e.message ?? "종목 추가에 실패했습니다.", "error"),
  });

  const removeWatchMut = useMutation({
    mutationFn: removeFromWatchlist,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["watchlist"] }),
    onError: () => showToast("종목 삭제에 실패했습니다.", "error"),
  });

  // WebSocket 연결
  const connectWs = useCallback(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${window.location.host}/api/ws/trading`);
    wsRef.current = ws;

    ws.onmessage = (e) => {
      const signal: TradingSignal = JSON.parse(e.data);
      setSignalLog((prev) => [signal, ...prev].slice(0, 50));
      if (signal.reason === "kill_switch") {
        showToast("⚠️ 일일 손실한도 초과 — 자동매매가 정지되었습니다.", "error");
      }
      qc.invalidateQueries({ queryKey: ["positions"] });
      qc.invalidateQueries({ queryKey: ["trade-history"] });
      qc.invalidateQueries({ queryKey: ["trading-config"] });
    };

    ws.onopen = () => {
      reconnectDelay.current = 1000; // reset on successful connection
    };

    ws.onclose = () => {
      reconnectTimer.current = setTimeout(() => {
        reconnectDelay.current = Math.min(reconnectDelay.current * 2, 30000);
        connectWs();
      }, reconnectDelay.current);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [qc]);

  useEffect(() => {
    connectWs();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connectWs]);

  // 종목 검색
  useEffect(() => {
    if (searchQuery.length < 1) { setSearchResults([]); return; }
    const timer = setTimeout(async () => {
      try {
        const results = await searchStocks(searchQuery);
        setSearchResults(results);
      } catch { setSearchResults([]); }
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const paperBalance = config?.paper_balance ?? 0;
  const paperInitial = config?.paper_initial_capital ?? 10_000_000;
  const returnRate = paperInitial > 0 ? ((paperBalance - paperInitial) / paperInitial * 100) : 0;
  const paperPositions = positions.filter(p => p.mode === "paper");

  // 자산곡선: 거래 내역에서 누적 잔고 변화 계산 (오래된 순)
  const equityCurve = (() => {
    const paperTrades = [...(history as TradeHistory[])]
      .filter(h => h.mode === "paper" && h.signal_type === "SELL" && h.profit_loss != null)
      .sort((a, b) => new Date(a.executed_at).getTime() - new Date(b.executed_at).getTime());
    let running = paperInitial;
    const points = [{ time: "시작", balance: running, returnRate: 0 }];
    for (const t of paperTrades) {
      running += t.profit_loss!;
      const rate = (running - paperInitial) / paperInitial * 100;
      points.push({
        time: new Date(t.executed_at).toLocaleDateString("ko-KR", { month: "2-digit", day: "2-digit" }),
        balance: running,
        returnRate: Math.round(rate * 100) / 100,
      });
    }
    return points;
  })();

  return (
    <div style={{ padding: isMobile ? "16px" : "24px", maxWidth: "1200px", margin: "0 auto" }}>
      <div style={{ position: "fixed", top: "16px", right: "16px", zIndex: 200, display: "flex", flexDirection: "column", gap: "8px" }}>
        {toasts.map(t => (
          <Toast key={t.id} message={t.message} type={t.type} onClose={() => removeToast(t.id)} />
        ))}
      </div>
      <h1 style={{ fontSize: "1.5rem", fontWeight: 700, marginBottom: "24px" }}>자동매매</h1>

      {/* 상단 제어 패널 */}
      <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr", gap: "16px", marginBottom: "24px" }}>
        {/* 엔진 상태 */}
        <div style={{ background: "var(--card-bg)", border: "1px solid var(--border)", borderRadius: "12px", padding: "20px" }}>
          <h2 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "16px" }}>엔진 상태</h2>
          <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "12px" }}>
            <span style={{
              display: "inline-flex", alignItems: "center", gap: "6px",
              padding: "4px 12px", borderRadius: "999px", fontSize: "0.875rem",
              background: config?.is_running ? "#dcfce7" : "#fee2e2",
              color: config?.is_running ? "#16a34a" : "#dc2626",
            }}>
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: "currentColor", display: "inline-block" }} />
              {config?.is_running ? "실행 중" : "정지"}
            </span>
            <button
              onClick={() => {
                if (!config?.is_running) {
                  setShowStartConfirm(true); // show confirm dialog
                } else {
                  toggleMut.mutate(false); // stop directly
                }
              }}
              disabled={toggleMut.isPending}
              style={{
                padding: "6px 16px", borderRadius: "8px", border: "none", cursor: "pointer",
                background: config?.is_running ? "#ef4444" : "#22c55e", color: "#fff", fontWeight: 600,
              }}
            >
              {config?.is_running ? "정지" : "시작"}
            </button>
          </div>
          <div style={{ fontSize: "0.875rem", color: "var(--text-muted)" }}>
            모의투자는 24시간 / 실거래는 장중(09:00~15:30)만 실행
          </div>
        </div>

        {/* 모의투자 잔고 */}
        <div style={{ background: "var(--card-bg)", border: "1px solid var(--border)", borderRadius: "12px", padding: "20px" }}>
          <h2 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "16px" }}>모의투자 계좌</h2>
          <div style={{ fontSize: "1.5rem", fontWeight: 700, marginBottom: "4px" }}>
            {paperBalance.toLocaleString()}원
          </div>
          <div style={{ fontSize: "0.875rem", color: returnRate >= 0 ? "#dc2626" : "#2563eb", marginBottom: "12px" }}>
            {returnRate >= 0 ? "▲" : "▼"} {Math.abs(returnRate).toFixed(2)}%
            <span style={{ color: "var(--text-muted)", marginLeft: "8px" }}>
              (초기: {paperInitial.toLocaleString()}원)
            </span>
          </div>
          <button
            onClick={() => resetBalanceMut.mutate()}
            style={{ fontSize: "0.75rem", padding: "4px 10px", borderRadius: "6px", border: "1px solid var(--border)", background: "transparent", cursor: "pointer" }}
          >
            잔고 초기화
          </button>
        </div>
      </div>

      {/* 전략 설정 */}
      <div style={{ background: "var(--card-bg)", border: "1px solid var(--border)", borderRadius: "12px", padding: "20px", marginBottom: "24px" }}>
        <h2 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "16px" }}>전략 설정</h2>

        {/* 전략 선택 탭 */}
        <div style={{ display: "flex", gap: "8px", marginBottom: "16px" }}>
          {([
            { value: "ma_cross", label: "이동평균 크로스" },
            { value: "rsi", label: "RSI" },
            { value: "macd", label: "MACD" },
          ] as const).map(({ value, label }) => {
            const active = (configForm.strategy ?? config?.strategy ?? "ma_cross") === value;
            return (
              <button
                key={value}
                onClick={() => setConfigForm(prev => ({ ...prev, strategy: value }))}
                style={{
                  padding: "6px 14px", borderRadius: "8px", border: "1px solid var(--border)",
                  cursor: "pointer", fontSize: "0.875rem", fontWeight: active ? 700 : 400,
                  background: active ? "#3b82f6" : "transparent",
                  color: active ? "#fff" : "inherit",
                }}
              >{label}</button>
            );
          })}
        </div>

        {/* 전략별 파라미터 */}
        {(() => {
          const strategy = configForm.strategy ?? config?.strategy ?? "ma_cross";
          const inputStyle = { width: "100%", padding: "8px", border: "1px solid var(--border)", borderRadius: "6px", fontSize: "0.875rem", background: "var(--input-bg)", boxSizing: "border-box" as const };
          const fields: { label: string; key: keyof TradingConfig; defaultVal: number | undefined }[] =
            strategy === "rsi"
              ? [
                  { label: "RSI 기간 (일)", key: "rsi_period", defaultVal: config?.rsi_period },
                  { label: "과매도 기준 (매수)", key: "rsi_oversold", defaultVal: config?.rsi_oversold },
                  { label: "과매수 기준 (매도)", key: "rsi_overbought", defaultVal: config?.rsi_overbought },
                  { label: "손절 (%)", key: "stop_loss_pct", defaultVal: config?.stop_loss_pct },
                  { label: "익절 (%)", key: "take_profit_pct", defaultVal: config?.take_profit_pct },
                ]
              : strategy === "macd"
              ? [
                  { label: "단기 EMA (일)", key: "macd_fast", defaultVal: config?.macd_fast },
                  { label: "장기 EMA (일)", key: "macd_slow", defaultVal: config?.macd_slow },
                  { label: "시그널 (일)", key: "macd_signal", defaultVal: config?.macd_signal },
                  { label: "손절 (%)", key: "stop_loss_pct", defaultVal: config?.stop_loss_pct },
                  { label: "익절 (%)", key: "take_profit_pct", defaultVal: config?.take_profit_pct },
                ]
              : [
                  { label: "단기 이동평균 (일)", key: "short_ma", defaultVal: config?.short_ma },
                  { label: "장기 이동평균 (일)", key: "long_ma", defaultVal: config?.long_ma },
                  { label: "손절 (%)", key: "stop_loss_pct", defaultVal: config?.stop_loss_pct },
                  { label: "익절 (%)", key: "take_profit_pct", defaultVal: config?.take_profit_pct },
                ];
          return (
            <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr 1fr" : "repeat(5, 1fr)", gap: "12px" }}>
              {fields.map(({ label, key, defaultVal }) => (
                <div key={key}>
                  <label style={{ display: "block", fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "4px" }}>{label}</label>
                  <input
                    type="number"
                    key={`${key}-${config?.strategy}`}
                    defaultValue={defaultVal}
                    onChange={(e) => setConfigForm(prev => ({ ...prev, [key]: parseFloat(e.target.value) }))}
                    style={inputStyle}
                  />
                </div>
              ))}
            </div>
          );
        })()}

        <div style={{ display: "flex", alignItems: "flex-end", gap: "12px", marginTop: "16px" }}>
          <div>
            <label style={{ display: "block", fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "4px" }}>
              일일 손실한도 (%) — Kill Switch
            </label>
            <input
              type="number"
              key={`daily_loss-${config?.daily_loss_limit_pct}`}
              defaultValue={config?.daily_loss_limit_pct ?? 5}
              step={0.5}
              min={0.5}
              onChange={(e) => setConfigForm(prev => ({ ...prev, daily_loss_limit_pct: parseFloat(e.target.value) }))}
              style={{ width: "120px", padding: "8px", border: "1px solid var(--border)", borderRadius: "6px", fontSize: "0.875rem", background: "var(--input-bg)" }}
            />
          </div>
          <button
            onClick={() => updateConfigMut.mutate(configForm)}
            disabled={updateConfigMut.isPending || Object.keys(configForm).length === 0}
            style={{ padding: "8px 20px", background: "#3b82f6", color: "#fff", border: "none", borderRadius: "8px", cursor: "pointer", fontWeight: 600 }}
          >
            설정 저장
          </button>
        </div>
      </div>

      {/* 감시 종목 */}
      <div style={{ background: "var(--card-bg)", border: "1px solid var(--border)", borderRadius: "12px", padding: "20px", marginBottom: "24px" }}>
        <h2 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "16px" }}>감시 종목</h2>
        {/* 검색 추가 */}
        <div style={{ position: "relative", marginBottom: "16px" }}>
          <input
            type="text"
            placeholder="종목명 또는 코드 검색..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ width: "280px", padding: "8px 12px", border: "1px solid var(--border)", borderRadius: "8px", fontSize: "0.875rem" }}
          />
          {searchResults.length > 0 && (
            <div style={{ position: "absolute", top: "100%", left: 0, zIndex: 10, background: "var(--card-bg)", border: "1px solid var(--border)", borderRadius: "8px", boxShadow: "0 4px 12px rgba(0,0,0,.1)", minWidth: "280px" }}>
              {searchResults.map((r) => (
                <button
                  key={r.code}
                  onClick={() => addWatchMut.mutate({ stock_code: r.code, stock_name: r.name })}
                  style={{ display: "block", width: "100%", textAlign: "left", padding: "10px 14px", border: "none", background: "transparent", cursor: "pointer", fontSize: "0.875rem" }}
                >
                  {r.name} <span style={{ color: "var(--text-muted)" }}>{r.code}</span>
                </button>
              ))}
            </div>
          )}
        </div>
        {/* 감시 목록 */}
        {watchlist.length === 0 ? (
          <p style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>감시 종목이 없습니다. 종목을 검색하여 추가하세요.</p>
        ) : (
          <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
            {watchlist.map((item: WatchlistItem) => (
              <div key={item.id} style={{ display: "flex", alignItems: "center", gap: "6px", padding: "6px 12px", background: "var(--tag-bg)", borderRadius: "999px", fontSize: "0.875rem" }}>
                <span>{item.stock_name}</span>
                <span style={{ color: "var(--text-muted)" }}>{item.stock_code}</span>
                <button
                  onClick={() => removeWatchMut.mutate(item.id)}
                  style={{ border: "none", background: "transparent", cursor: "pointer", color: "var(--text-muted)", padding: "0", lineHeight: 1 }}
                >×</button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 현재 포지션 */}
      <div style={{ background: "var(--card-bg)", border: "1px solid var(--border)", borderRadius: "12px", padding: "20px", marginBottom: "24px" }}>
        <h2 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "16px" }}>
          현재 포지션 (모의) <span style={{ color: "var(--text-muted)", fontWeight: 400, fontSize: "0.875rem" }}>{paperPositions.length}종목</span>
        </h2>
        {paperPositions.length === 0 ? (
          <p style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>보유 포지션이 없습니다.</p>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  {["종목", "수량", "매수가", "현재가", "수익률", "평가손익", "손절가", "익절가", "매수일시"].map(h => (
                    <th key={h} style={{ padding: "8px 12px", textAlign: "left", color: "var(--text-muted)", fontWeight: 500 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {paperPositions.map((p: Position) => (
                  <tr key={p.id} style={{ borderBottom: "1px solid var(--border)" }}>
                    <td style={{ padding: "10px 12px", fontWeight: 600 }}>{p.stock_name} <span style={{ color: "var(--text-muted)" }}>{p.stock_code}</span></td>
                    <td style={{ padding: "10px 12px" }}>{p.quantity.toLocaleString()}주</td>
                    <td style={{ padding: "10px 12px" }}>{p.entry_price.toLocaleString()}원</td>
                    <td style={{ padding: "10px 12px", color: p.current_price == null ? "var(--text-muted)" : p.current_price > p.entry_price ? "#dc2626" : "#2563eb" }}>
                      {p.current_price != null ? `${p.current_price.toLocaleString()}원` : "-"}
                    </td>
                    <td style={{ padding: "10px 12px", color: p.return_rate == null ? "var(--text-muted)" : p.return_rate >= 0 ? "#dc2626" : "#2563eb" }}>
                      {p.return_rate != null ? `${p.return_rate >= 0 ? "▲" : "▼"} ${p.return_rate.toFixed(2)}%` : "-"}
                    </td>
                    <td style={{ padding: "10px 12px", color: p.unrealized_profit_loss == null ? "var(--text-muted)" : p.unrealized_profit_loss >= 0 ? "#dc2626" : "#2563eb" }}>
                      {p.unrealized_profit_loss != null ? `${p.unrealized_profit_loss >= 0 ? "+" : ""}${p.unrealized_profit_loss.toLocaleString()}원` : "-"}
                    </td>
                    <td style={{ padding: "10px 12px", color: "#2563eb" }}>{p.stop_loss_price.toLocaleString()}원</td>
                    <td style={{ padding: "10px 12px", color: "#dc2626" }}>{p.take_profit_price.toLocaleString()}원</td>
                    <td style={{ padding: "10px 12px", color: "var(--text-muted)" }}>{new Date(p.entered_at).toLocaleString("ko-KR")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 자산곡선 차트 */}
      {equityCurve.length >= 2 && (
        <div style={{ background: "var(--card-bg)", border: "1px solid var(--border)", borderRadius: "12px", padding: "20px", marginBottom: "24px" }}>
          <h2 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "4px" }}>모의투자 자산곡선</h2>
          <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "12px" }}>매도 체결 기준 누적 수익률</div>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={equityCurve} margin={{ left: 10, right: 20 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" tick={{ fontSize: 11 }} />
              <YAxis tickFormatter={(v: number) => `${v > 0 ? "+" : ""}${v.toFixed(1)}%`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => [`${Number(v) >= 0 ? "+" : ""}${Number(v).toFixed(2)}%`, "수익률"]} />
              <ReferenceLine y={0} stroke="#888" strokeDasharray="3 3" />
              <Line type="monotone" dataKey="returnRate" stroke="#8b5cf6" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr", gap: "16px" }}>
        {/* 거래 내역 */}
        <div style={{ background: "var(--card-bg)", border: "1px solid var(--border)", borderRadius: "12px", padding: "20px" }}>
          <h2 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "16px" }}>거래 내역</h2>
          {history.length === 0 ? (
            <p style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>거래 내역이 없습니다.</p>
          ) : (
            <div style={{ maxHeight: "300px", overflowY: "auto" }}>
              {(history as TradeHistory[]).slice(0, 30).map((h: TradeHistory) => (
                <div key={h.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 0", borderBottom: "1px solid var(--border)", fontSize: "0.8125rem" }}>
                  <div>
                    <span style={{ fontWeight: 600, color: h.signal_type === "BUY" ? "#dc2626" : "#2563eb", marginRight: "6px" }}>
                      {h.signal_type === "BUY" ? "매수" : "매도"}
                    </span>
                    {h.stock_name}
                    <span style={{ color: "var(--text-muted)", marginLeft: "4px" }}>{h.reason}</span>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div>{h.price.toLocaleString()}원 × {h.quantity}</div>
                    {h.profit_loss != null && (
                      <div style={{ color: h.profit_loss >= 0 ? "#dc2626" : "#2563eb" }}>
                        {h.profit_loss >= 0 ? "+" : ""}{h.profit_loss.toLocaleString()}원
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 실시간 시그널 로그 */}
        <div style={{ background: "var(--card-bg)", border: "1px solid var(--border)", borderRadius: "12px", padding: "20px" }}>
          <h2 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "16px" }}>실시간 시그널</h2>
          {signalLog.length === 0 ? (
            <p style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>대기 중...</p>
          ) : (
            <div style={{ maxHeight: "300px", overflowY: "auto", fontFamily: "monospace", fontSize: "0.8125rem" }}>
              {signalLog.map((s, i) => (
                <div key={i} style={{ padding: "4px 0", borderBottom: "1px solid var(--border)", color: s.signal_type === "BUY" ? "#dc2626" : "#2563eb" }}>
                  [{new Date(s.timestamp).toLocaleTimeString("ko-KR")}] {s.signal_type} {s.stock_name} | {s.message}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 백테스트 */}
      <div style={{ background: "var(--card-bg)", border: "1px solid var(--border)", borderRadius: "12px", padding: "20px", marginTop: "24px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "16px" }}>
          <h2 style={{ fontSize: "1rem", fontWeight: 600, margin: 0 }}>백테스트</h2>
          <button
            onClick={async () => {
              if (watchlist.length === 0) return alert("감시 종목을 먼저 추가하세요.");
              setBacktestLoading(true);
              setBacktestResult(null);
              try {
                const strategy = config?.strategy ?? "ma_cross";
                const result = await runBacktest({
                  stock_codes: watchlist.map((w: WatchlistItem) => w.stock_code),
                  stock_names: watchlist.map((w: WatchlistItem) => w.stock_name),
                  strategy,
                  short_ma: config?.short_ma ?? 5,
                  long_ma: config?.long_ma ?? 20,
                  stop_loss_pct: config?.stop_loss_pct ?? 5,
                  take_profit_pct: config?.take_profit_pct ?? 10,
                  initial_capital: config?.paper_initial_capital ?? 10_000_000,
                  count: 180,
                  rsi_period: config?.rsi_period ?? 14,
                  rsi_oversold: config?.rsi_oversold ?? 30,
                  rsi_overbought: config?.rsi_overbought ?? 70,
                  macd_fast: config?.macd_fast ?? 12,
                  macd_slow: config?.macd_slow ?? 26,
                  macd_signal_period: config?.macd_signal ?? 9,
                });
                setBacktestResult(result);
              } catch (e) {
                alert("백테스트 실패: " + (e instanceof Error ? e.message : "알 수 없는 오류"));
              } finally {
                setBacktestLoading(false);
              }
            }}
            disabled={backtestLoading}
            style={{ padding: "6px 16px", background: "#8b5cf6", color: "#fff", border: "none", borderRadius: "8px", cursor: "pointer", fontWeight: 600, fontSize: "0.875rem" }}
          >
            {backtestLoading ? "분석 중..." : "감시 종목 백테스트 (180일)"}
          </button>
        </div>

        {backtestResult && (
          <>
            {/* 합산 지표 */}
            <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr 1fr" : "repeat(3, 1fr)", gap: "12px", marginBottom: "16px" }}>
              {[
                { label: "전체 수익률", value: `${backtestResult.total_return_rate >= 0 ? "+" : ""}${backtestResult.total_return_rate.toFixed(2)}%`, color: backtestResult.total_return_rate >= 0 ? "#dc2626" : "#2563eb" },
                { label: "평균 승률", value: `${backtestResult.avg_win_rate.toFixed(1)}%`, color: "inherit" },
                { label: "평균 최대낙폭", value: `${backtestResult.avg_max_drawdown.toFixed(2)}%`, color: "#dc2626" },
              ].map(({ label, value, color }) => (
                <div key={label} style={{ background: "var(--tag-bg)", borderRadius: "8px", padding: "12px 16px" }}>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "4px" }}>{label}</div>
                  <div style={{ fontSize: "1.25rem", fontWeight: 700, color }}>{value}</div>
                </div>
              ))}
            </div>

            {/* 종목별 결과 */}
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border)" }}>
                    {["종목", "최종잔고", "수익률", "승률", "총거래", "최대낙폭"].map(h => (
                      <th key={h} style={{ padding: "8px 12px", textAlign: "left", color: "var(--text-muted)", fontWeight: 500 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {backtestResult.results.map((r) => (
                    <tr key={r.stock_code} style={{ borderBottom: "1px solid var(--border)" }}>
                      <td style={{ padding: "10px 12px", fontWeight: 600 }}>{r.stock_name} <span style={{ color: "var(--text-muted)" }}>{r.stock_code}</span></td>
                      <td style={{ padding: "10px 12px" }}>{r.final_balance.toLocaleString()}원</td>
                      <td style={{ padding: "10px 12px", color: r.return_rate >= 0 ? "#dc2626" : "#2563eb", fontWeight: 600 }}>
                        {r.return_rate >= 0 ? "+" : ""}{r.return_rate.toFixed(2)}%
                      </td>
                      <td style={{ padding: "10px 12px" }}>{r.win_rate.toFixed(1)}%</td>
                      <td style={{ padding: "10px 12px" }}>{r.total_trades}건</td>
                      <td style={{ padding: "10px 12px", color: "#dc2626" }}>{r.max_drawdown.toFixed(2)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {!backtestResult && !backtestLoading && (
          <p style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>감시 종목을 추가하고 버튼을 눌러 현재 전략을 백테스트하세요.</p>
        )}
      </div>

      {showStartConfirm && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", zIndex: 100, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div style={{ background: "var(--card-bg)", borderRadius: 12, padding: 24, maxWidth: 400, width: "90%" }}>
            <h3 style={{ margin: "0 0 12px", fontSize: "1rem", fontWeight: 700 }}>자동매매 시작 확인</h3>
            <p style={{ margin: "0 0 20px", fontSize: "0.875rem", lineHeight: 1.6, color: "var(--text-muted)" }}>
              모의투자 모드로 자동매매를 시작합니다.<br/>실거래 API 미연동 상태이므로 실제 주문은 발생하지 않습니다.
            </p>
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button
                onClick={() => setShowStartConfirm(false)}
                style={{ padding: "8px 16px", borderRadius: 8, border: "1px solid var(--border)", background: "transparent", cursor: "pointer", fontSize: "0.875rem" }}
              >취소</button>
              <button
                onClick={() => { toggleMut.mutate(true); setShowStartConfirm(false); }}
                style={{ padding: "8px 16px", borderRadius: 8, border: "none", background: "#22c55e", color: "#fff", cursor: "pointer", fontWeight: 600, fontSize: "0.875rem" }}
              >시작</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
