import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchAlerts, createAlert, deleteAlert, WS_URL } from "../api/client";
import type { AlertCreate } from "../api/client";

const THEME_OPTIONS = [
  { id: "ai", name: "인공지능(AI)" },
  { id: "semiconductor", name: "반도체" },
  { id: "bio", name: "바이오/제약" },
  { id: "battery", name: "2차전지" },
  { id: "defense", name: "방산" },
  { id: "robot", name: "로봇" },
  { id: "game", name: "게임" },
  { id: "eco", name: "친환경/ESG" },
];

export default function Alerts() {
  const queryClient = useQueryClient();
  const wsRef = useRef<WebSocket | null>(null);
  const [wsMessages, setWsMessages] = useState<string[]>([]);
  const [form, setForm] = useState<AlertCreate>({
    target_type: "theme",
    target_id: "ai",
    condition: "above",
    threshold: 2.0,
  });

  const { data: alerts, isLoading } = useQuery({
    queryKey: ["alerts"],
    queryFn: fetchAlerts,
  });

  const createMutation = useMutation({
    mutationFn: createAlert,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["alerts"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteAlert,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["alerts"] }),
  });

  useEffect(() => {
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;
    ws.onmessage = (e) => {
      const data = JSON.parse(e.data);
      setWsMessages((prev) => [
        `[${new Date().toLocaleTimeString()}] ${data.target_name}: ${data.current_value.toFixed(2)}% (임계값 ${data.condition === "above" ? "초과" : "미만"} ${data.threshold}%)`,
        ...prev.slice(0, 19),
      ]);
    };
    return () => ws.close();
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createMutation.mutate(form);
  };

  return (
    <div className="page">
      <h1>알림 설정</h1>

      <form className="alert-form" onSubmit={handleSubmit}>
        <div className="form-row">
          <label>대상 유형</label>
          <select
            value={form.target_type}
            onChange={(e) =>
              setForm({ ...form, target_type: e.target.value, target_id: "ai" })
            }
          >
            <option value="theme">테마</option>
            <option value="stock">종목</option>
          </select>
        </div>

        {form.target_type === "theme" ? (
          <div className="form-row">
            <label>테마 선택</label>
            <select
              value={form.target_id}
              onChange={(e) => setForm({ ...form, target_id: e.target.value })}
            >
              {THEME_OPTIONS.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>
        ) : (
          <div className="form-row">
            <label>종목코드</label>
            <input
              type="text"
              placeholder="예: 005930"
              value={form.target_id}
              onChange={(e) => setForm({ ...form, target_id: e.target.value })}
              maxLength={6}
            />
          </div>
        )}

        <div className="form-row">
          <label>조건</label>
          <select
            value={form.condition}
            onChange={(e) => setForm({ ...form, condition: e.target.value })}
          >
            <option value="above">이상 (초과)</option>
            <option value="below">이하 (미만)</option>
          </select>
        </div>

        <div className="form-row">
          <label>임계값 (%)</label>
          <input
            type="number"
            step="0.1"
            value={form.threshold}
            onChange={(e) =>
              setForm({ ...form, threshold: parseFloat(e.target.value) })
            }
          />
        </div>

        <button type="submit" disabled={createMutation.isPending}>
          {createMutation.isPending ? "저장 중..." : "알림 추가"}
        </button>
      </form>

      <h2>등록된 알림</h2>
      {isLoading && <div className="loading">로딩 중...</div>}
      <div className="alert-list">
        {alerts?.length === 0 && <div className="empty">등록된 알림이 없습니다.</div>}
        {alerts?.map((alert) => (
          <div key={alert.id} className="alert-item">
            <div className="alert-info">
              <span className="alert-target">{alert.target_name}</span>
              <span className="alert-condition">
                {alert.condition === "above" ? "≥" : "≤"} {alert.threshold}%
              </span>
            </div>
            <button
              className="delete-btn"
              onClick={() => deleteMutation.mutate(alert.id)}
            >
              삭제
            </button>
          </div>
        ))}
      </div>

      <h2>실시간 알림 로그</h2>
      <div className="ws-log">
        {wsMessages.length === 0 && (
          <div className="empty">알림 대기 중...</div>
        )}
        {wsMessages.map((msg, i) => (
          <div key={i} className="ws-message">
            {msg}
          </div>
        ))}
      </div>
    </div>
  );
}
