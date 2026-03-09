import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
  ResponsiveContainer,
  LabelList,
} from "recharts";
import { fetchThemes } from "../api/client";
import ThemeCard from "../components/ThemeCard";
import SkeletonCard from "../components/SkeletonCard";
import { useFavorites } from "../hooks/useFavorites";

type ViewMode = "card" | "chart";
type FilterTab = "all" | "fav";

export default function Dashboard() {
  const [viewMode, setViewMode] = useState<ViewMode>("card");
  const [filterTab, setFilterTab] = useState<FilterTab>("all");
  const { isFavorite, toggle } = useFavorites();

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["themes"],
    queryFn: fetchThemes,
    refetchInterval: 30000,
  });

  const displayed =
    filterTab === "fav"
      ? (data ?? []).filter((t) => isFavorite(t.theme_id))
      : (data ?? []);

  const chartData = displayed
    ?.map((t) => ({
      name: t.theme_name,
      value: t.avg_change_rate,
    }))
    .reverse();

  return (
    <div className="page">
      <div className="page-header">
        <h1>테마 강도 순위</h1>
        <div className="view-tabs">
          <button
            className={viewMode === "card" ? "active" : ""}
            onClick={() => setViewMode("card")}
          >
            카드
          </button>
          <button
            className={viewMode === "chart" ? "active" : ""}
            onClick={() => setViewMode("chart")}
          >
            차트
          </button>
        </div>
        <button className="refresh-btn" onClick={() => refetch()}>
          새로고침
        </button>
      </div>

      <div className="filter-tabs">
        <button
          className={filterTab === "all" ? "active" : ""}
          onClick={() => setFilterTab("all")}
        >
          전체
        </button>
        <button
          className={filterTab === "fav" ? "active" : ""}
          onClick={() => setFilterTab("fav")}
        >
          즐겨찾기
        </button>
      </div>

      {isError && (
        <div className="error">
          데이터 조회 실패. API 키 설정 및 서버 상태를 확인하세요.
        </div>
      )}

      {filterTab === "fav" && !isLoading && displayed.length === 0 && (
        <div className="fav-empty">
          ★ 테마 카드의 별 버튼을 눌러 즐겨찾기를 추가하세요
        </div>
      )}

      {viewMode === "card" && (
        <div className="theme-grid">
          {isLoading
            ? Array.from({ length: 8 }).map((_, i) => <SkeletonCard key={i} />)
            : displayed.map((theme, idx) => (
                <ThemeCard
                  key={theme.theme_id}
                  theme={theme}
                  rank={idx + 1}
                  isFavorite={isFavorite(theme.theme_id)}
                  onToggleFavorite={toggle}
                />
              ))
          }
        </div>
      )}

      {viewMode === "chart" && (
        <div className="chart-container">
          <ResponsiveContainer width="100%" height={360}>
            <BarChart
              data={chartData}
              layout="vertical"
              margin={{ left: 80, right: 60, top: 8, bottom: 8 }}
            >
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                type="number"
                tickFormatter={(v: number) => `${v.toFixed(1)}%`}
              />
              <YAxis
                type="category"
                dataKey="name"
                width={75}
                tick={{ fontSize: 13 }}
              />
              <Tooltip
                formatter={(v) => [
                  typeof v === "number" ? `${v.toFixed(2)}%` : v,
                  "평균 등락률",
                ]}
              />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {chartData?.map((entry, index) => (
                  <Cell
                    key={index}
                    fill={entry.value >= 0 ? "#c0392b" : "#2980b9"}
                  />
                ))}
                <LabelList
                  dataKey="value"
                  position="right"
                  formatter={(v: unknown) => {
                    const n = Number(v);
                    return `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;
                  }}
                  style={{ fontSize: 12 }}
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
