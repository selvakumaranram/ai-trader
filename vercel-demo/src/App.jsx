import { useEffect, useState } from "react";
import CapitalInput from "./components/CapitalInput.jsx";

export default function App() {
  const [dashboard, setDashboard] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [capital, setCapital] = useState(25000);

  useEffect(() => {
    fetch("/api/dashboard")
      .then((res) => res.json())
      .then((data) => {
        if (data.error) throw new Error(data.error);
        setDashboard(data);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <header style={{ marginBottom: "2rem" }}>
        <h1 style={{ marginBottom: "0.25rem" }}>QuantDesk</h1>
        <p style={{ color: "var(--text-muted)", margin: 0 }}>
          Research &amp; recommendation dashboard — live prices, live sentiment.
        </p>
      </header>
      <CapitalInput capital={capital} onChange={setCapital} />
      {loading && <p>Loading live market data…</p>}
      {error && <p className="error-text">Error: {error}</p>}
      {dashboard && (
        <p style={{ color: "var(--text-muted)" }}>
          Loaded {dashboard.assets.length} assets
          {dashboard.failed.length > 0 && `, ${dashboard.failed.length} unavailable`}.
        </p>
      )}
    </div>
  );
}
