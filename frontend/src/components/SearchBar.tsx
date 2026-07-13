import { useState, useEffect, useRef } from "react";
import { searchStocks } from "../api/client";
import type { StockSearchResult } from "../api/client";

interface Props {
  onSelect: (code: string) => void;
}

export default function SearchBar({ onSelect }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<StockSearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      setOpen(false);
      return;
    }
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(async () => {
      try {
        const data = await searchStocks(query);
        setResults(data);
        setOpen(data.length > 0);
      } catch {
        setResults([]);
      }
    }, 300);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [query]);

  const handleSelect = (code: string) => {
    setQuery("");
    setResults([]);
    setOpen(false);
    onSelect(code);
  };

  return (
    <div className="search-bar">
      <input
        type="text"
        placeholder="종목 검색..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onFocus={() => results.length > 0 && setOpen(true)}
        className="search-input"
      />
      {open && (
        <ul className="search-dropdown">
          {results.map((r) => (
            <li
              key={r.code}
              onMouseDown={() => handleSelect(r.code)}
              className="search-item"
            >
              <span className="search-name">{r.name}</span>
              <span className="search-code">{r.code}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
