import { useEffect, useState } from "react";
import CapitalInput from "./components/CapitalInput.jsx";
import SearchBox from "./components/SearchBox.jsx";
import StyleSection from "./components/StyleSection.jsx";
import TopMovers from "./components/TopMovers.jsx";
import Holdings from "./components/Holdings.jsx";
import PersonalWatchlist from "./components/PersonalWatchlist.jsx";
import MomentumSection from "./components/MomentumSection.jsx";

const TABS = [
  { key: "intraday", label: "Day Trading" },
  { key: "short_term", label: "Short-Term" },
  { key: "swing", label: "Swing / Long-Term" },
  { key: "movers", label: "Top Movers" },
  { key: "holdings", label: "My Holdings" },
  { key: "watchlist", label: "My Watchlist" },
  { key: "momentum", label: "Momentum" },
];

export default function App() {
  const [dashboard, setDashboard] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [capital, setCapital] = useState(25000);
  const [activeTab, setActiveTab] = useState("intraday");

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
      <header className="app-header">
        <h1>QuantDesk</h1>
        <p style={{ color: "var(--text-muted)", margin: 0 }}>
          Research &amp; recommendation dashboard — live prices, live sentiment.
        </p>
      </header>

      <SearchBox />

      <CapitalInput capital={capital} onChange={setCapital} />

      <nav className="tabs">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            className={activeTab === tab.key ? "tab active" : "tab"}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {activeTab === "holdings" ? (
        <Holdings />
      ) : activeTab === "watchlist" ? (
        <PersonalWatchlist />
      ) : activeTab === "momentum" ? (
        <MomentumSection capital={capital} />
      ) : (
        <>
          {loading && <p>Loading live market data…</p>}
          {error && <p className="error-text">Error: {error}</p>}

          {dashboard && dashboard.warning && <p className="warning-text">{dashboard.warning}</p>}
          {dashboard && dashboard.failed.length > 0 && (
            <p className="warning-text">
              {dashboard.failed.length} asset(s) unavailable this run:{" "}
              {dashboard.failed.map((f) => f.symbol).join(", ")}
            </p>
          )}

          {dashboard &&
            (activeTab === "movers" ? (
              <TopMovers assets={dashboard.assets} />
            ) : (
              <StyleSection assets={dashboard.assets} style={activeTab} capital={capital} />
            ))}
        </>
      )}
    </div>
  );
}
