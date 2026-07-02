import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchBotStatus,
  fetchBotSignals,
  startBot,
  stopBot,
  setBotMode,
} from "../api/client";
import { useTradingAccount } from "../hooks/useTradingAccount";

function fmtTime(iso: string | null): string {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export default function Bot() {
  const qc = useQueryClient();
  const { available, loading, accountSeq } = useTradingAccount();
  const [intervalMin, setIntervalMin] = useState<number>(5);
  const [threshold, setThreshold] = useState<number>(2.0);

  const status = useQuery({
    queryKey: ["bot-status"],
    queryFn: fetchBotStatus,
    refetchInterval: 10000,
    enabled: available,
  });

  const signals = useQuery({
    queryKey: ["bot-signals"],
    queryFn: () => fetchBotSignals(100),
    refetchInterval: 15000,
    enabled: available,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["bot-status"] });
    qc.invalidateQueries({ queryKey: ["bot-signals"] });
  };

  const start = useMutation({
    mutationFn: () =>
      startBot({
        account_seq: accountSeq ?? undefined,
        interval_minutes: intervalMin,
        threshold,
      }),
    onSuccess: invalidate,
  });

  const stop = useMutation({ mutationFn: stopBot, onSuccess: invalidate });

  const mode = useMutation({
    mutationFn: (dryRun: boolean) => setBotMode(dryRun),
    onSuccess: invalidate,
  });

  if (loading) return <div className="page"><p>확인 중...</p></div>;
  if (!available) {
    return (
      <div className="page">
        <h1>자동매매 봇</h1>
        <p className="error-message">
          트레이딩 기능이 비활성화되어 있습니다. 백엔드 .env의 TRADING_ENABLED / 토스 API 키를 확인하세요.
        </p>
      </div>
    );
  }

  const s = status.data;

  return (
    <div className="page">
      <div className="page-header">
        <h1>자동매매 봇</h1>
        <button className="refresh-btn" onClick={invalidate}>새로고침</button>
      </div>

      {s && (
        <div className="strength-summary">
          <div className={`strength-rate ${s.running ? "up" : "down"}`}>
            {s.running ? "● 실행 중" : "■ 중지됨"}
            {"  "}
            <span style={{ fontSize: "0.85em", opacity: 0.85 }}>
              {s.dry_run ? "[DRY-RUN — 시그널 기록만]" : "[실주문 모드]"}
            </span>
          </div>
          <div className="strength-counts">
            <span>장 {s.market_open ? "열림" : "닫힘"}</span>
            {" / "}
            <span>주기 {s.interval_minutes}분</span>
            {" / "}
            <span>임계 +{s.threshold.toFixed(1)}%</span>
            {" / "}
            <span>오늘 시그널 {s.signals_today}/{s.max_signals_per_day}</span>
          </div>
          <div className="strength-counts" style={{ marginTop: 4 }}>
            <span>마지막 실행: {fmtTime(s.last_run_at)}</span>
            {s.last_run_result && <span> — {s.last_run_result}</span>}
          </div>
        </div>
      )}

      <div className="page-header" style={{ gap: 12, flexWrap: "wrap" }}>
        {!s?.running ? (
          <>
            <label>
              주기(분){" "}
              <input
                type="number"
                min={1}
                max={60}
                value={intervalMin}
                onChange={(e) => setIntervalMin(Number(e.target.value))}
                style={{ width: 64 }}
              />
            </label>
            <label>
              테마 임계(%){" "}
              <input
                type="number"
                step={0.5}
                min={0.5}
                value={threshold}
                onChange={(e) => setThreshold(Number(e.target.value))}
                style={{ width: 64 }}
              />
            </label>
            <button className="refresh-btn" onClick={() => start.mutate()} disabled={start.isPending}>
              ▶ 봇 시작 (dry-run)
            </button>
          </>
        ) : (
          <button className="refresh-btn" onClick={() => stop.mutate()} disabled={stop.isPending}>
            ■ 봇 중지
          </button>
        )}

        {s && (
          <label title={!s.live_allowed ? "BOT_LIVE_TRADING=true 환경변수가 필요합니다" : ""}>
            <input
              type="checkbox"
              checked={!s.dry_run}
              disabled={!s.live_allowed || mode.isPending}
              onChange={(e) => mode.mutate(!e.target.checked)}
            />{" "}
            실주문 모드 {!s.live_allowed && "(dry-run 강제 — 환경변수 잠금)"}
          </label>
        )}
      </div>

      {mode.isError && (
        <p className="error-message">모드 전환 실패: 서버가 실주문 전환을 거부했습니다.</p>
      )}

      <h2 style={{ fontSize: "1.05rem" }}>시그널 로그</h2>
      {signals.isLoading && <p>조회 중...</p>}
      {signals.data && signals.data.length === 0 && (
        <p>아직 시그널이 없습니다. 장 운영시간(평일 09:00~15:30) 중 임계값을 넘는 테마가 나오면 기록됩니다.</p>
      )}
      {signals.data && signals.data.length > 0 && (
        <table className="stock-table">
          <thead>
            <tr>
              <th>시각</th>
              <th>구분</th>
              <th>종목</th>
              <th>가격</th>
              <th>수량</th>
              <th>모드</th>
              <th>사유</th>
            </tr>
          </thead>
          <tbody>
            {signals.data.map((sig, i) => (
              <tr key={`${sig.created_at}-${sig.symbol}-${i}`}>
                <td>{fmtTime(sig.created_at)}</td>
                <td className={sig.action === "BUY" ? "up" : "down"}>{sig.action}</td>
                <td>{sig.symbol_name || sig.symbol}</td>
                <td>{sig.price != null ? sig.price.toLocaleString("ko-KR") : "-"}</td>
                <td>{sig.quantity || "-"}</td>
                <td>
                  {sig.dry_run ? "dry-run" : sig.executed ? `주문됨(${sig.order_id})` : `실패: ${sig.error ?? "?"}`}
                </td>
                <td style={{ fontSize: "0.85em" }}>{sig.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
