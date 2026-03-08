import { useQuery } from "@tanstack/react-query";
import { fetchThemes } from "../api/client";
import ThemeCard from "../components/ThemeCard";

export default function Dashboard() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["themes"],
    queryFn: fetchThemes,
    refetchInterval: 30000,
  });

  return (
    <div className="page">
      <div className="page-header">
        <h1>테마 강도 순위</h1>
        <button className="refresh-btn" onClick={() => refetch()}>
          새로고침
        </button>
      </div>

      {isLoading && <div className="loading">데이터 로딩 중...</div>}
      {isError && (
        <div className="error">
          데이터 조회 실패. API 키 설정 및 서버 상태를 확인하세요.
        </div>
      )}

      <div className="theme-grid">
        {data?.map((theme, idx) => (
          <ThemeCard key={theme.theme_id} theme={theme} rank={idx + 1} />
        ))}
      </div>
    </div>
  );
}
