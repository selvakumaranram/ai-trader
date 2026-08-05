import { useEffect, useState } from "react";
import MomentumScreenerTab from "./MomentumScreenerTab.jsx";

const SUB_TABS = [
  { key: "screener", label: "Screener" },
  { key: "1d", label: "1 Day Movers" },
  { key: "3d", label: "3 Day Movers" },
  { key: "7d", label: "7 Day Movers" },
  { key: "1m", label: "1 Month Movers" },
];

const RETURN_FIELD = { "1d": "return_1d", "3d": "return_3d", "7d": "return_7d", "1m": "return_1m" };

function MoversTab({ rows, returnField }) {
  if (rows.length === 0) {
    return <p className="empty-state">No data in the latest run.</p>;
  }
  return (
    <div className="momentum-list">
      {rows.map((row, index) => (
        <div key={row.symbol} className="asset-card momentum-card">
          <div className="asset-card-row">
            <div className="asset-card-main">
              <span className="momentum-rank">#{index + 1}</span>
              <span className="asset-symbol">{row.symbol}</span>
              <span className="momentum-sector">{row.sector || "Sector unknown"}</span>
              {row.pe_ratio != null && <span className="momentum-pe">P/E {row.pe_ratio.toFixed(1)}</span>}
            </div>
            <div className="asset-card-stats">
              <span
                className="momentum-return"
                style={{ color: row[returnField] >= 0 ? "var(--positive)" : "var(--negative)" }}
              >
                {row[returnField] != null ? `${(row[returnField] * 100).toFixed(2)}%` : "–"}
              </span>
              <a href={row.screener_url} target="_blank" rel="noreferrer" className="momentum-link">
                Details →
              </a>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function MomentumSection() {
  const [activeSubTab, setActiveSubTab] = useState("screener");
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetch(`/api/momentum?tab=${activeSubTab}`)
      .then((res) => res.json())
      .then((body) => {
        if (body.error) throw new Error(body.error);
        setData(body);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [activeSubTab]);

  return (
    <div className="momentum-section">
      <nav className="tabs momentum-subtabs">
        {SUB_TABS.map((tab) => (
          <button
            key={tab.key}
            className={activeSubTab === tab.key ? "tab active" : "tab"}
            onClick={() => setActiveSubTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {loading && <p>Loading momentum data…</p>}
      {error && <p className="error-text">{error}</p>}

      {data && (
        <>
          <p className="momentum-freshness">
            As of {data.run_date}
            {data.stale && <span className="warning-text"> — data is more than 2 days old</span>}
          </p>
          {activeSubTab === "screener" ? (
            <MomentumScreenerTab rows={data.rows} />
          ) : (
            <MoversTab rows={data.rows} returnField={RETURN_FIELD[activeSubTab]} />
          )}
        </>
      )}
    </div>
  );
}
