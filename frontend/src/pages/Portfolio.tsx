import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  fetchTossAccounts,
  fetchHoldings,
  type HoldingItem,
  type CurrencyAmount,
  type ProfitLossInfo,
} from "../api/client";

const fmtKrw = (v: number | null | undefined) =>
  v == null ? "-" : `${Math.round(v).toLocaleString("ko-KR")}원`;

const amountOf = (a: CurrencyAmount | null | undefined): number | null =>
  a?.krw ?? null;

const plColor = (v: number | null | undefined) =>
  v == null || v === 0 ? undefined : v > 0 ? "var(--color-rise, #e53935)" : "var(--color-fall, #1e88e5)";

function PlText({ pl }: { pl: ProfitLossInfo | null | undefined }) {
  // 백엔드가 원본 구조를 전달: amount가 통화별 dict인 경우와 숫자인 경우 모두 처리
  const rawAmount = pl?.amount as unknown;
  const amount =
    typeof rawAmount === "number"
      ? rawAmount
      : amountOf(rawAmount as CurrencyAmount | null);
  const rate = typeof pl?.rate === "number" ? pl.rate : null;
  return (
    <span style={{ color: plColor(amount) }}>
      {amount == null ? "-" : `${amount > 0 ? "+" : ""}${fmtKrw(amount)}`}
      {rate != null && ` (${(rate * 100).toFixed(2)}%)`}
    </span>
  );
}

export default function Portfolio() {
  const [accountSeq, setAccountSeq] = useState<number | null>(null);

  const accounts = useQuery({
    queryKey: ["toss-accounts"],
    queryFn: fetchTossAccounts,
    staleTime: Infinity,
    retry: 0,
  });

  useEffect(() => {
    if (accountSeq == null && accounts.data && accounts.data.length > 0) {
      setAccountSeq(accounts.data[0].account_seq);
    }
  }, [accounts.data, accountSeq]);

  const holdings = useQuery({
    queryKey: ["holdings", accountSeq],
    queryFn: () => fetchHoldings(accountSeq!),
    enabled: accountSeq != null,
    refetchInterval: 30000,
  });

  if (accounts.isLoading) return <div className="page"><p>계좌 조회 중...</p></div>;

  if (accounts.isError) {
    return (
      <div className="page">
        <h1>내 계좌</h1>
        <p className="error-message">
          계좌 조회에 실패했습니다. 백엔드의 TRADING_ENABLED / TOSS_CLIENT_ID /
          TOSS_CLIENT_SECRET 설정을 확인하세요.
        </p>
      </div>
    );
  }

  const summary = holdings.data;

  return (
    <div className="page">
      <div className="page-header">
        <h1>내 계좌</h1>
        {accounts.data && accounts.data.length > 1 && (
          <select
            value={accountSeq ?? ""}
            onChange={(e) => setAccountSeq(Number(e.target.value))}
          >
            {accounts.data.map((a) => (
              <option key={a.account_seq} value={a.account_seq}>
                {a.account_no} ({a.account_type})
              </option>
            ))}
          </select>
        )}
        <button className="refresh-btn" onClick={() => holdings.refetch()}>
          새로고침
        </button>
      </div>

      {holdings.isLoading && <p>잔고 조회 중...</p>}
      {holdings.isError && <p className="error-message">잔고 조회에 실패했습니다.</p>}

      {summary && (
        <>
          <div className="portfolio-summary" style={{ display: "flex", gap: "2rem", flexWrap: "wrap", margin: "1rem 0" }}>
            <div>
              <div style={{ opacity: 0.7, fontSize: "0.85rem" }}>투자원금</div>
              <strong>{fmtKrw(amountOf(summary.total_purchase_amount))}</strong>
            </div>
            <div>
              <div style={{ opacity: 0.7, fontSize: "0.85rem" }}>평가금액</div>
              <strong>{fmtKrw(amountOf(summary.market_value))}</strong>
            </div>
            <div>
              <div style={{ opacity: 0.7, fontSize: "0.85rem" }}>총 손익</div>
              <strong><PlText pl={summary.profit_loss} /></strong>
            </div>
            <div>
              <div style={{ opacity: 0.7, fontSize: "0.85rem" }}>일간 손익</div>
              <strong><PlText pl={summary.daily_profit_loss} /></strong>
            </div>
          </div>

          {summary.items.length === 0 ? (
            <p>보유 종목이 없습니다.</p>
          ) : (
            <table className="stock-table">
              <thead>
                <tr>
                  <th>종목</th>
                  <th>수량</th>
                  <th>평균단가</th>
                  <th>현재가</th>
                  <th>평가손익</th>
                  <th>일간손익</th>
                </tr>
              </thead>
              <tbody>
                {summary.items.map((h: HoldingItem) => (
                  <tr key={h.symbol}>
                    <td>
                      {h.name} <span style={{ opacity: 0.6, fontSize: "0.8rem" }}>{h.symbol}</span>
                    </td>
                    <td>{h.quantity.toLocaleString("ko-KR")}</td>
                    <td>{fmtKrw(h.average_purchase_price)}</td>
                    <td>{fmtKrw(h.last_price)}</td>
                    <td><PlText pl={h.profit_loss} /></td>
                    <td><PlText pl={h.daily_profit_loss} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </div>
  );
}
