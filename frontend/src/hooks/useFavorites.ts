import { useState, useCallback } from "react";

const KEY = "stock-theme-favorites";

function load(): Set<string> {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? new Set(JSON.parse(raw)) : new Set();
  } catch {
    return new Set();
  }
}

function save(set: Set<string>) {
  localStorage.setItem(KEY, JSON.stringify([...set]));
}

export function useFavorites() {
  const [favorites, setFavorites] = useState<Set<string>>(load);

  const toggle = useCallback((id: string) => {
    setFavorites(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      save(next);
      return next;
    });
  }, []);

  const isFavorite = useCallback((id: string) => favorites.has(id), [favorites]);

  return { favorites, toggle, isFavorite };
}
