import type { StockPrice } from "../api/client";

interface Props {
  stocks: StockPrice[];
  onSelect?: (code: string) => void;
}

export default function StockTable({ stocks, onSelect }: Props) {
  const sorted = [...stocks].sort((a, b) => b.change_rate - a.change_rate);

  return (
    <div className="table-wrapper">
      <table className="stock-table">
        <thead>
          <tr>
            <th>종목코드</th>
            <th>종목명</th>
            <th>현재가</th>
            <th>등락금액</th>
            <th>등락률</th>
            <th>거래량</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((stock) => {
            const isUp = stock.change_rate >= 0;
            return (
              <tr
                key={stock.code}
                className={isUp ? "row-up" : "row-down"}
                onClick={() => onSelect?.(stock.code)}
                style={onSelect ? { cursor: "pointer" } : undefined}
              >
                <td>{stock.code}</td>
                <td>{stock.name || "-"}</td>
                <td>{stock.current_price.toLocaleString("ko-KR")}원</td>
                <td className={isUp ? "up" : "down"}>
                  {isUp ? "+" : ""}
                  {stock.change_price.toLocaleString("ko-KR")}
                </td>
                <td className={isUp ? "up" : "down"}>
                  {isUp ? "+" : ""}
                  {stock.change_rate.toFixed(2)}%
                </td>
                <td>{stock.volume.toLocaleString("ko-KR")}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
