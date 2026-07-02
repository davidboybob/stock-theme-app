import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { isAxiosError } from "axios";
import {
  createOrder,
  fetchBuyingPower,
  fetchSellableQuantity,
  type OrderCreate,
} from "../api/client";

interface Props {
  accountSeq: number;
  symbol: string;
  name: string;
  currentPrice: number;
  side: "BUY" | "SELL";
  onDone: () => void;
}

const HIGH_VALUE = 100_000_000;

function errMessage(e: unknown): string {
  if (isAxiosError(e)) {
    const d = e.response?.data?.detail;
    if (d?.message) return `${d.message} (${d.code})`;
  }
  return "주문 처리에 실패했습니다.";
}

export default function OrderPanel({ accountSeq, symbol, name, currentPrice, side, onDone }: Props) {
  const qc = useQueryClient();
  const [orderType, setOrderType] = useState<"LIMIT" | "MARKET">("LIMIT");
  const [price, setPrice] = useState<number>(currentPrice);
  const [quantity, setQuantity] = useState<number>(1);
  const [confirming, setConfirming] = useState(false);

  const buyingPower = useQuery({
    queryKey: ["buying-power", accountSeq],
    queryFn: () => fetchBuyingPower(accountSeq),
    enabled: side === "BUY",
    staleTime: 10000,
  });

  const sellable = useQuery({
    queryKey: ["sellable", accountSeq, symbol],
    queryFn: () => fetchSellableQuantity(accountSeq, symbol),
    enabled: side === "SELL",
    staleTime: 10000,
  });

  const mutation = useMutation({
    mutationFn: (data: OrderCreate) => createOrder(accountSeq, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["open-orders"] });
      qc.invalidateQueries({ queryKey: ["holdings"] });
      qc.invalidateQueries({ queryKey: ["order-log"] });
    },
  });

  const estimated = orderType === "LIMIT" ? price * quantity : currentPrice * quantity;
  const isHighValue = estimated >= HIGH_VALUE;
  const sideLabel = side === "BUY" ? "매수" : "매도";
  const sideColor = side === "BUY" ? "#e53935" : "#1e88e5";

  const valid =
    quantity > 0 && (orderType === "MARKET" || price > 0);

  const submit = () => {
    mutation.mutate({
      symbol,
      side,
      order_type: orderType,
      quantity,
      price: orderType === "LIMIT" ? price : null,
      confirm_high_value: isHighValue,
    });
    setConfirming(false);
  };

  if (mutation.isSuccess) {
    const o = mutation.data;
    return (
      <div className="order-panel" style={{ padding: "1rem", border: `1px solid ${sideColor}`, borderRadius: 8, marginTop: "1rem" }}>
        <p>
          ✅ {sideLabel} 주문 접수 완료 — {o.symbol} {o.quantity}주
          {o.price != null && ` @ ${o.price.toLocaleString()}원`} (상태: {o.status})
        </p>
        <button onClick={onDone}>닫기</button>
      </div>
    );
  }

  return (
    <div className="order-panel" style={{ padding: "1rem", border: `1px solid ${sideColor}`, borderRadius: 8, marginTop: "1rem" }}>
      <h3 style={{ color: sideColor, marginTop: 0 }}>
        {name} {sideLabel}
      </h3>

      {side === "BUY" && buyingPower.data && (
        <p style={{ fontSize: "0.85rem", opacity: 0.8 }}>
          매수 가능: {Number(buyingPower.data.amount ?? 0).toLocaleString()}원
        </p>
      )}
      {side === "SELL" && sellable.data && (
        <p style={{ fontSize: "0.85rem", opacity: 0.8 }}>
          판매 가능: {Number(sellable.data.quantity ?? 0).toLocaleString()}주
        </p>
      )}

      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.5rem" }}>
        <button
          className={orderType === "LIMIT" ? "active" : ""}
          onClick={() => setOrderType("LIMIT")}
        >
          지정가
        </button>
        <button
          className={orderType === "MARKET" ? "active" : ""}
          onClick={() => setOrderType("MARKET")}
        >
          시장가
        </button>
      </div>

      {orderType === "LIMIT" && (
        <label style={{ display: "block", marginBottom: "0.5rem" }}>
          가격 (원)
          <input
            type="number"
            value={price}
            min={1}
            onChange={(e) => setPrice(Number(e.target.value))}
            style={{ width: "100%" }}
          />
        </label>
      )}

      <label style={{ display: "block", marginBottom: "0.5rem" }}>
        수량 (주)
        <input
          type="number"
          value={quantity}
          min={1}
          onChange={(e) => setQuantity(Math.floor(Number(e.target.value)))}
          style={{ width: "100%" }}
        />
      </label>

      <p style={{ fontSize: "0.9rem" }}>
        예상 {sideLabel} 금액: <strong>{estimated.toLocaleString()}원</strong>
        {orderType === "MARKET" && " (시장가 기준 추정)"}
        {isHighValue && <span style={{ color: "#e65100" }}> — 1억원 이상 고액 주문</span>}
      </p>

      {mutation.isError && (
        <p style={{ color: "#e53935", fontSize: "0.85rem" }}>{errMessage(mutation.error)}</p>
      )}

      {!confirming ? (
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button
            disabled={!valid || mutation.isPending}
            onClick={() => setConfirming(true)}
            style={{ background: sideColor, color: "#fff", flex: 1 }}
          >
            {sideLabel} 주문
          </button>
          <button onClick={onDone}>취소</button>
        </div>
      ) : (
        <div style={{ background: "rgba(0,0,0,0.05)", padding: "0.75rem", borderRadius: 6 }}>
          <p style={{ margin: "0 0 0.5rem" }}>
            <strong>
              {name} {quantity}주를{" "}
              {orderType === "LIMIT" ? `${price.toLocaleString()}원에` : "시장가로"} {sideLabel}
            </strong>
            합니다. 진행할까요?
          </p>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button
              onClick={submit}
              disabled={mutation.isPending}
              style={{ background: sideColor, color: "#fff", flex: 1 }}
            >
              {mutation.isPending ? "접수 중..." : `확인 — ${sideLabel} 실행`}
            </button>
            <button onClick={() => setConfirming(false)}>돌아가기</button>
          </div>
        </div>
      )}
    </div>
  );
}
