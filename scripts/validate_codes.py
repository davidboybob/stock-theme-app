from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import httpx

BASE_URL = "https://polling.finance.naver.com"
HEADERS = {
    "Referer": "https://finance.naver.com/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}
TIMEOUT = 10.0


def load_themes(themes_path: Path) -> list[dict]:
    with themes_path.open(encoding="utf-8") as f:
        data = json.load(f)
    return data["themes"]


def validate_code(code: str) -> Optional[tuple[str, int]]:
    """종목코드 검증. 유효하면 (종목명, 현재가) 반환, 무효면 None 반환."""
    url = f"{BASE_URL}/api/realtime/domestic/stock/{code}"
    try:
        response = httpx.get(url, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()
        item = data["datas"][0]
        name = item.get("stockName", "")
        close_price_str = item.get("closePrice", "0").replace(",", "").strip()
        current_price = int(float(close_price_str)) if close_price_str else 0
        return (name, current_price)
    except Exception:
        return None


def format_price(price: int) -> str:
    return f"{price:,}"


def main() -> None:
    # themes.json 경로: 스크립트 위치 기준으로 찾거나, cwd 기준으로 찾음
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    themes_path = project_root / "backend" / "app" / "data" / "themes.json"
    if not themes_path.exists():
        # cwd 기준으로 재시도
        themes_path = Path("app/data/themes.json")
    if not themes_path.exists():
        print(f"themes.json 을 찾을 수 없습니다: {themes_path}", file=sys.stderr)
        sys.exit(1)

    themes = load_themes(themes_path)

    total_valid = 0
    total_invalid = 0

    for theme in themes:
        theme_name = theme["name"]
        stocks = theme["stocks"]
        print(f"[{theme_name}]")

        for code in stocks:
            result = validate_code(code)
            if result is not None:
                name, price = result
                print(f"  ✅ {code} ({name}) — 현재가: {format_price(price)}")
                total_valid += 1
            else:
                print(f"  ❌ {code} — 응답 없음")
                total_invalid += 1

        print()

    print("---")
    print(f"유효: {total_valid}개 / 무효: {total_invalid}개")


if __name__ == "__main__":
    main()
