import { useNavigate } from "react-router-dom";
import type { ThemeStrength } from "../api/client";

interface Props {
  theme: ThemeStrength;
  rank: number;
  isFavorite?: boolean;
  onToggleFavorite?: (id: string) => void;
}

export default function ThemeCard({ theme, rank, isFavorite, onToggleFavorite }: Props) {
  const navigate = useNavigate();
  const isUp = theme.avg_change_rate >= 0;

  return (
    <div
      className={`theme-card ${isUp ? "theme-up" : "theme-down"}`}
      onClick={() => navigate(`/themes/${theme.theme_id}`)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && navigate(`/themes/${theme.theme_id}`)}
    >
      <button
        className={`fav-btn ${isFavorite ? "fav-active" : ""}`}
        onClick={(e) => { e.stopPropagation(); onToggleFavorite?.(theme.theme_id); }}
        title={isFavorite ? "즐겨찾기 해제" : "즐겨찾기 추가"}
      >
        {isFavorite ? "★" : "☆"}
      </button>
      <div className="theme-rank">#{rank}</div>
      <div className="theme-name">{theme.theme_name}</div>
      <div className={`theme-change-rate ${isUp ? "up" : "down"}`}>
        {isUp ? "+" : ""}
        {theme.avg_change_rate.toFixed(2)}%
      </div>
      <div className="theme-counts">
        <span className="up">▲ {theme.rising_count}</span>
        <span className="separator"> / </span>
        <span className="down">▼ {theme.falling_count}</span>
        <span className="total"> ({theme.total}종목)</span>
      </div>
    </div>
  );
}
