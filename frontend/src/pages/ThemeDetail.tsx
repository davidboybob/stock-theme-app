import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchThemeDetail } from "../api/client";
import StockTable from "../components/StockTable";

export default function ThemeDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["theme", id],
    queryFn: () => fetchThemeDetail(id!),
    refetchInterval: 30000,
    enabled: !!id,
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

      <h2>종목 현황</h2>
      {data.stock_prices.length > 0 ? (
        <StockTable stocks={data.stock_prices} />
      ) : (
        <div className="empty">종목 데이터를 불러올 수 없습니다.</div>
      )}
    </div>
  );
}
