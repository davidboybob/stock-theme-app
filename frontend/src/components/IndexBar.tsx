import { useQuery } from "@tanstack/react-query";
import { fetchIndices } from "../api/client";
import type { IndexPrice } from "../api/client";

function IndexItem({ index }: { index: IndexPrice }) {
  const isUp = index.change_rate >= 0;
  return (
    <div className="index-item">
      <span className="index-name">{index.name}</span>
      <span className="index-value">
        {index.current_value.toLocaleString("ko-KR", {
          maximumFractionDigits: 2,
        })}
      </span>
      <span className={`index-change ${isUp ? "up" : "down"}`}>
        {isUp ? "▲" : "▼"}{" "}
        {Math.abs(index.change_value).toLocaleString("ko-KR", {
          maximumFractionDigits: 2,
        })}{" "}
        ({isUp ? "+" : ""}
        {index.change_rate.toFixed(2)}%)
      </span>
    </div>
  );
}

interface IndexBarProps {
  onToggleTheme: () => void;
  theme: "light" | "dark";
}

export default function IndexBar({ onToggleTheme, theme }: IndexBarProps) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["indices"],
    queryFn: fetchIndices,
    refetchInterval: 30000,
  });

  if (isLoading) return (
    <div className="index-bar">
      <span>지수 로딩 중...</span>
      <button className="theme-toggle" onClick={onToggleTheme} title="테마 전환">
        {theme === "dark" ? "☀️" : "🌙"}
      </button>
    </div>
  );
  if (isError) return (
    <div className="index-bar index-error">
      <span>지수 조회 실패</span>
      <button className="theme-toggle" onClick={onToggleTheme} title="테마 전환">
        {theme === "dark" ? "☀️" : "🌙"}
      </button>
    </div>
  );

  return (
    <div className="index-bar">
      {data?.map((idx) => <IndexItem key={idx.code} index={idx} />)}
      <button className="theme-toggle" onClick={onToggleTheme} title="테마 전환" style={{ marginLeft: "auto" }}>
        {theme === "dark" ? "☀️" : "🌙"}
      </button>
    </div>
  );
}
