import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchOpenOrders,
  fetchOrderLog,
  cancelOrder,
  type Order,
  type OrderLogEntry,
} from "../api/client";
import { useTradingAccount } from "../hooks/useTradingAccount";

const STATUS_LABELS: Record<string, string> = {
  PENDING: "대기중",
  PARTIAL_FILLED: "부분체결",
  PENDING_CANCEL: "취소 처리중",
  PENDING_REPLACE: "정정 처리중",
  FILLED: "체결완료",
  CANCELED: "취소됨",
  REJECTED: "거부됨",
};

function fmtTime(iso: string | null): string {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("ko-KR", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export default function Orders() {
  const qc = useQueryClient();
  const { available, loading, accountSeq } = useTradingAccount();

  const openOrders = useQuery({
    queryKey: ["open-orders", accountSeq],
    queryFn: () => fetchOpenOrders(accountSeq!),
    enabled: accountSeq != null,
    refetchInterval: 15000,
  });

  const log = useQuery({
    queryKey: ["order-log", accountSeq],
    queryFn: () => fetchOrderLog(accountSeq!),
    enabled: accountSeq != null,
  });

  const cancel = useMutation({
    mutationFn: (orderId: string) => cancelOrder(accountSeq!, orderId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["open-orders"] });
      qc.invalidateQueries({ queryKey: ["order-log"] });
    },
  });

  if (loading) return <div className="page"><p>확인 중...</p></div>;
  if (!available) {
    return (
      <div className="page">
        <h1>주문</h1>
        <p className="error-message">
          트레이딩 기능이 비활성화되어 있습니다. 백엔드 .env의 TRADING_ENABLED / 토스 API 키를 확인하세요.
        </p>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>주문</h1>
        <button className="refresh-btn" onClick={() => { openOrders.refetch(); log.refetch(); }}>
          새로고침
        </button>
      </div>

      <h2 style={{ fontSize: "1.05rem" }}>대기중 주문</h2>
      {openOrders.isLoading && <p>조회 중...</p>}
      {openOrders.data && openOrders.data.length === 0 && <p>대기중인 주문이 없습니다.</p>}
      {openOrders.data && openOrders.data.length > 0 && (
        <table className="stock-table">
          <thead>
            <tr>
              <th>종목</th>
              <th>구분</th>
              <th>가격</th>
              <th>수량(체결)</th>
              <th>상태</th>
              <th>주문시간</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {openOrders.data.map((o: Order) => (
              <tr key={o.order_id}>
                <td>{o.symbol}</td>
                <td style={{ color: o.side === "BUY" ? "#e53935" : "#1e88e5" }}>
                  {o.side === "BUY" ? "매수" : "매도"} {o.order_type === "LIMIT" ? "지정가" : "시장가"}
                </td>
                <td>{o.price != null ? `${o.price.toLocaleString()}원` : "-"}</td>
                <td>
                  {o.quantity.toLocaleString()} ({o.filled_quantity.toLocaleString()})
                </td>
                <td>{STATUS_LABELS[o.status] ?? o.status}</td>
                <td>{fmtTime(o.ordered_at)}</td>
                <td>
                  <button
                    onClick={() => cancel.mutate(o.order_id)}
                    disabled={cancel.isPending}
                  >
                    취소
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h2 style={{ fontSize: "1.05rem", marginTop: "2rem" }}>주문 이력</h2>
      {log.data && log.data.length === 0 && <p>주문 이력이 없습니다.</p>}
      {log.data && log.data.length > 0 && (
        <table className="stock-table">
          <thead>
            <tr>
              <th>시간</th>
              <th>동작</th>
              <th>종목</th>
              <th>구분</th>
              <th>가격/수량</th>
              <th>결과</th>
            </tr>
          </thead>
          <tbody>
            {log.data.map((e: OrderLogEntry) => (
              <tr key={e.id}>
                <td>{fmtTime(e.created_at)}</td>
                <td>{e.action}{e.source === "bot" ? " (봇)" : ""}</td>
                <td>{e.symbol ?? "-"}</td>
                <td style={{ color: e.side === "BUY" ? "#e53935" : e.side === "SELL" ? "#1e88e5" : undefined }}>
                  {e.side === "BUY" ? "매수" : e.side === "SELL" ? "매도" : "-"}
                </td>
                <td>
                  {e.price != null ? `${e.price.toLocaleString()}원` : "시장가"}
                  {e.quantity != null && ` × ${e.quantity}`}
                </td>
                <td>
                  {e.success === true && "✅"}
                  {e.success === false && (
                    <span style={{ color: "#e53935" }} title={e.error_message ?? ""}>
                      ❌ {e.error_code}
                    </span>
                  )}
                  {e.status && ` ${STATUS_LABELS[e.status] ?? e.status}`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
