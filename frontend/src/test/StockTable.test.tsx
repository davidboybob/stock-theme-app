import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import StockTable from "../components/StockTable";
import type { StockPrice } from "../api/client";

const mockStocks: StockPrice[] = [
  {
    code: "005930",
    name: "삼성전자",
    current_price: 78000,
    change_price: 1000,
    change_rate: 1.30,
    volume: 5000000,
    high_price: 79000,
    low_price: 77000,
    open_price: 77500,
  },
  {
    code: "000660",
    name: "SK하이닉스",
    current_price: 180000,
    change_price: -2000,
    change_rate: -1.10,
    volume: 2000000,
    high_price: 183000,
    low_price: 179000,
    open_price: 182000,
  },
];

describe("StockTable", () => {
  it("종목 이름과 현재가를 렌더링한다", () => {
    render(<StockTable stocks={mockStocks} onSelect={vi.fn()} />);
    expect(screen.getByText("삼성전자")).toBeInTheDocument();
    expect(screen.getByText("SK하이닉스")).toBeInTheDocument();
  });

  it("상승 종목에 + 부호를 표시한다", () => {
    render(<StockTable stocks={mockStocks} onSelect={vi.fn()} />);
    expect(screen.getByText("+1.30%")).toBeInTheDocument();
  });

  it("하락 종목에 음수 등락률을 표시한다", () => {
    render(<StockTable stocks={mockStocks} onSelect={vi.fn()} />);
    expect(screen.getByText("-1.10%")).toBeInTheDocument();
  });

  it("종목 클릭 시 onSelect가 호출된다", () => {
    const onSelect = vi.fn();
    render(<StockTable stocks={mockStocks} onSelect={onSelect} />);
    fireEvent.click(screen.getByText("삼성전자"));
    expect(onSelect).toHaveBeenCalledWith("005930");
  });

  it("onSelect 없이도 렌더링된다", () => {
    render(<StockTable stocks={mockStocks} />);
    expect(screen.getByText("삼성전자")).toBeInTheDocument();
  });

  it("빈 목록일 때 테이블 헤더만 렌더링된다", () => {
    render(<StockTable stocks={[]} />);
    expect(screen.getByText("종목명")).toBeInTheDocument();
    expect(screen.queryByText("삼성전자")).not.toBeInTheDocument();
  });

  it("등락률 기준 내림차순으로 정렬된다", () => {
    render(<StockTable stocks={mockStocks} />);
    const rows = screen.getAllByRole("row");
    // 헤더 제외, 첫 번째 데이터 행이 상승률 높은 삼성전자여야 함
    expect(rows[1]).toHaveTextContent("삼성전자");
    expect(rows[2]).toHaveTextContent("SK하이닉스");
  });
});
