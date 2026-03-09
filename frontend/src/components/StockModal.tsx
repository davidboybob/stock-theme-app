import { useEffect, useState } from "react";
import type { StockDetail } from "../api/client";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

interface Props {
  code: string;
  onClose: () => void;
}

export default function StockModal({ code, onClose }: Props) {
  const [data, setData] = useState<StockDetail | null>(null);
  const [loading, setLoading] = useState(true);

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

  const isUp = (data?.change_rate ?? 0) >= 0;

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
          </>
        )}
        {!loading && !data && (
          <div className="error">데이터를 불러올 수 없습니다.</div>
        )}
      </div>
    </div>
  );
}
