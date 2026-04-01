import { useCallback, useEffect, useMemo, useState } from "react";
import { Button, Card, CardBody, CardHeader, Input } from "@nextui-org/react";

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";
const LS_ACCESS = "taskun_access";
const LS_REFRESH = "taskun_refresh";

export default function App() {
  const [health, setHealth] = useState(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [me, setMe] = useState(null);
  const [authError, setAuthError] = useState("");
  const [loading, setLoading] = useState(false);

  const healthUrl = useMemo(() => `${API_BASE}/api/health/`, []);
  const tokenUrl = useMemo(() => `${API_BASE}/api/token/`, []);
  const meUrl = useMemo(() => `${API_BASE}/api/me/`, []);

  useEffect(() => {
    fetch(healthUrl)
      .then((r) => r.json())
      .then(setHealth)
      .catch(() => setHealth({ ok: false }));
  }, [healthUrl]);

  const loadMe = useCallback(
    async (access) => {
      const r = await fetch(meUrl, {
        headers: { Authorization: `Bearer ${access}` },
      });
      if (!r.ok) {
        setMe(null);
        return;
      }
      setMe(await r.json());
    },
    [meUrl],
  );

  useEffect(() => {
    const access = localStorage.getItem(LS_ACCESS);
    if (!access) return;
    loadMe(access);
  }, [loadMe]);

  const onLogin = async () => {
    setAuthError("");
    setLoading(true);
    try {
      const r = await fetch(tokenUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: username.trim(), password }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) {
        setAuthError(data.detail || data.non_field_errors?.[0] || `Ошибка ${r.status}`);
        setMe(null);
        return;
      }
      localStorage.setItem(LS_ACCESS, data.access);
      localStorage.setItem(LS_REFRESH, data.refresh);
      setMe(data.user || null);
      if (data.access) await loadMe(data.access);
    } catch {
      setAuthError("Сеть недоступна");
      setMe(null);
    } finally {
      setLoading(false);
    }
  };

  const onLogout = () => {
    localStorage.removeItem(LS_ACCESS);
    localStorage.removeItem(LS_REFRESH);
    setMe(null);
    setPassword("");
  };

  return (
    <div style={{ maxWidth: 760, margin: "28px auto", padding: 16 }}>
      <Card>
        <CardHeader style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
          <div>
            <div style={{ fontWeight: 700, fontSize: 18 }}>Po_Taskun</div>
            <div style={{ color: "#666", fontSize: 13 }}>
              Django + JWT + React (NextUI). Health:{" "}
              <span style={{ fontFamily: "monospace" }}>{healthUrl}</span>
            </div>
          </div>
          <div style={{ color: health?.ok ? "green" : "#b00020", fontWeight: 700 }}>
            {health == null ? "API: ..." : health?.ok ? "API: OK" : "API: OFF"}
          </div>
        </CardHeader>
        <CardBody style={{ display: "grid", gap: 12 }}>
          {me ? (
            <>
              <div style={{ fontSize: 14 }}>
                <strong>Вошли как:</strong> {me.short_name}
                {me.full_name ? ` — ${me.full_name}` : ""}
                {me.worker_role ? ` (${me.worker_role})` : ""}
              </div>
              <Button color="danger" variant="flat" onPress={onLogout}>
                Выйти
              </Button>
            </>
          ) : (
            <>
              <Input
                label="Логин (short_name)"
                placeholder="Иванов"
                value={username}
                onValueChange={setUsername}
                autoComplete="username"
              />
              <Input
                label="Пароль"
                placeholder="Пароль"
                type="password"
                value={password}
                onValueChange={setPassword}
                autoComplete="current-password"
              />
              {authError ? (
                <div style={{ color: "#b00020", fontSize: 13 }}>{authError}</div>
              ) : null}
              <Button color="primary" isLoading={loading} onPress={onLogin}>
                Войти
              </Button>
            </>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
