import { useEffect, useMemo, useState } from "react";
import { Button, Card, CardBody, CardHeader, Input } from "@nextui-org/react";

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

export default function App() {
  const [health, setHealth] = useState(null);
  const [password, setPassword] = useState("");

  const healthUrl = useMemo(() => `${API_BASE}/api/health/`, []);

  useEffect(() => {
    fetch(healthUrl)
      .then((r) => r.json())
      .then(setHealth)
      .catch(() => setHealth({ ok: false }));
  }, [healthUrl]);

  return (
    <div style={{ maxWidth: 760, margin: "28px auto", padding: 16 }}>
      <Card>
        <CardHeader style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
          <div>
            <div style={{ fontWeight: 700, fontSize: 18 }}>Po_Taskun</div>
            <div style={{ color: "#666", fontSize: 13 }}>
              Django backend + React (NextUI). Тест API:{" "}
              <span style={{ fontFamily: "monospace" }}>{healthUrl}</span>
            </div>
          </div>
          <div style={{ color: health?.ok ? "green" : "#b00020", fontWeight: 700 }}>
            {health == null ? "API: ..." : health?.ok ? "API: OK" : "API: OFF"}
          </div>
        </CardHeader>
        <CardBody style={{ display: "grid", gap: 12 }}>
          <Input
            label="Пароль (демо UI)"
            placeholder="Введите пароль"
            type="password"
            value={password}
            onValueChange={setPassword}
          />
          <Button color="primary" onPress={() => alert("Дальше подключим авторизацию к API")}>
            Войти
          </Button>
        </CardBody>
      </Card>
    </div>
  );
}
