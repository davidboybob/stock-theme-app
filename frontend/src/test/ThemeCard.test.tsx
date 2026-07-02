import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import ThemeCard from "../components/ThemeCard";
import type { ThemeStrength } from "../api/client";

const mockTheme: ThemeStrength = {
  theme_id: "ai",
  theme_name: "AI·인공지능",
  avg_change_rate: 1.23,
  rising_count: 4,
  falling_count: 1,
  total: 5,
};

const mockThemeDown: ThemeStrength = {
  ...mockTheme,
  avg_change_rate: -0.85,
  rising_count: 1,
  falling_count: 4,
};

function renderCard(props?: Partial<Parameters<typeof ThemeCard>[0]>) {
  return render(
    <MemoryRouter>
      <ThemeCard theme={mockTheme} rank={1} {...props} />
    </MemoryRouter>
  );
}

describe("ThemeCard", () => {
  it("테마 이름과 순위를 렌더링한다", () => {
    renderCard();
    expect(screen.getByText("AI·인공지능")).toBeInTheDocument();
    expect(screen.getByText("#1")).toBeInTheDocument();
  });

  it("상승 테마는 up 스타일이 적용된다", () => {
    renderCard();
    expect(screen.getByText("+1.23%")).toBeInTheDocument();
  });

  it("하락 테마는 음수 등락률을 표시한다", () => {
    renderCard({ theme: mockThemeDown });
    expect(screen.getByText("-0.85%")).toBeInTheDocument();
  });

  it("즐겨찾기 버튼 클릭 시 onToggleFavorite이 호출된다", () => {
    const onToggle = vi.fn();
    renderCard({ onToggleFavorite: onToggle });
    const favBtn = screen.getByTitle("즐겨찾기 추가");
    fireEvent.click(favBtn);
    expect(onToggle).toHaveBeenCalledWith("ai");
  });

  it("즐겨찾기 활성화 시 ★ 아이콘을 표시한다", () => {
    renderCard({ isFavorite: true });
    expect(screen.getByTitle("즐겨찾기 해제")).toHaveTextContent("★");
  });

  it("상승/하락 종목 수를 표시한다", () => {
    renderCard();
    expect(screen.getByText("▲ 4")).toBeInTheDocument();
    expect(screen.getByText("▼ 1")).toBeInTheDocument();
    expect(screen.getByText("(5종목)")).toBeInTheDocument();
  });
});
