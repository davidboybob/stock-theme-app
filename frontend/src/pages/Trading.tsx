import { useState, useEffect, useRef, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getTradingConfig, updateTradingConfig, toggleEngine, resetPaperBalance,
  getWatchlist, addToWatchlist, removeFromWatchlist,
  getPositions, getTradeHistory,
  TradingConfig, TradingSignal, Position, TradeHistory, WatchlistItem,
} from "../api/trading";
import { searchStocks } from "../api/client";

export default function Trading() {
  const qc = useQueryClient();
  const [signalLog, setSignalLog] = useState<TradingSignal[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<{ code: string; name: string }[]>([]);
  const [configForm, setConfigForm] = useState<Partial<TradingConfig>>({});
  const [showStartConfirm, setShowStartConfirm] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectDelay = useRef(1000);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  useEffect(() => {
    const handler = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener("resize", handler);
    return () => window.removeEventListener("resize", handler);
  }, []);

  const { data: config } = useQuery({ queryKey: ["trading-config"], queryFn: getTradingConfig, refetchInterval: 30000 });
  const { data: watchlist = [] } = useQuery({ queryKey: ["watchlist"], queryFn: getWatchlist });
  const { data: positions = [] } = useQuery({ queryKey: ["positions"], queryFn: getPositions, refetchInterval: 30000 });
  const { data: history = [] } = useQuery({ queryKey: ["trade-history"], queryFn: getTradeHistory, refetchInterval: 30000 });

  const toggleMut = useMutation({
    mutationFn: (running: boolean) => toggleEngine(running),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["trading-config"] }),
  });

  const updateConfigMut = useMutation({
    mutationFn: updateTradingConfig,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["trading-config"] }); setConfigForm({}); },
  });

  const resetBalanceMut = useMutation({
    mutationFn: resetPaperBalance,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["trading-config"] }),
  });

  const addWatchMut = useMutation({
    mutationFn: addToWatchlist,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["watchlist"] }); setSearchQuery(""); setSearchResults([]); },
  });

  const removeWatchMut = useMutation({
    mutationFn: removeFromWatchlist,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["watchlist"] }),
  });

  // WebSocket 연결
  const connectWs = useCallback(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${window.location.host}/api/ws/trading`);
    wsRef.current = ws;

    ws.onmessage = (e) => {
      const signal: TradingSignal = JSON.parse(e.data);
      setSignalLog((prev) => [signal, ...prev].slice(0, 50));
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

  return (
    <div style={{ padding: isMobile ? "16px" : "24px", maxWidth: "1200px", margin: "0 auto" }}>
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
        <h2 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "16px" }}>전략 설정 (골든/데드크로스)</h2>
        <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr 1fr" : "repeat(4, 1fr)", gap: "12px" }}>
          {[
            { label: "단기 이동평균 (일)", key: "short_ma", value: config?.short_ma },
            { label: "장기 이동평균 (일)", key: "long_ma", value: config?.long_ma },
            { label: "손절 (%)", key: "stop_loss_pct", value: config?.stop_loss_pct },
            { label: "익절 (%)", key: "take_profit_pct", value: config?.take_profit_pct },
          ].map(({ label, key, value }) => (
            <div key={key}>
              <label style={{ display: "block", fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "4px" }}>{label}</label>
              <input
                type="number"
                defaultValue={value}
                onChange={(e) => setConfigForm(prev => ({ ...prev, [key]: parseFloat(e.target.value) }))}
                style={{ width: "100%", padding: "8px", border: "1px solid var(--border)", borderRadius: "6px", fontSize: "0.875rem", background: "var(--input-bg)", boxSizing: "border-box" }}
              />
            </div>
          ))}
        </div>
        <button
          onClick={() => updateConfigMut.mutate(configForm)}
          disabled={updateConfigMut.isPending || Object.keys(configForm).length === 0}
          style={{ marginTop: "12px", padding: "8px 20px", background: "#3b82f6", color: "#fff", border: "none", borderRadius: "8px", cursor: "pointer", fontWeight: 600 }}
        >
          설정 저장
        </button>
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
