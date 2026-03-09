import { useState, useEffect, useRef } from "react";

interface SearchResult {
  name: string;
  code: string;
}

interface Props {
  onSelect: (code: string) => void;
}

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function SearchBar({ onSelect }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
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
        const res = await fetch(
          `${API_BASE}/api/stocks/search?q=${encodeURIComponent(query)}`
        );
        const data: SearchResult[] = await res.json();
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
