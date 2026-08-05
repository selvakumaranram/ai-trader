import { sizePositions } from "../lib/positionSizing.js";

const GATE_LABELS = {
  market_cap: "Market cap > ₹5,000 Cr",
  avg_daily_traded_value: "Avg daily traded value > ₹10 Cr",
  asm: "Not on ASM list",
  gsm: "Not on GSM list",
  fo_ban: "Not in F&O ban",
  promoter_holding: "Promoter holding > 40%",
  debt_to_equity: "Debt-to-equity < 1.0",
  earnings_growth: "Stable/positive earnings growth",
};

const VOLUME_BADGE = {
  full: { label: "Volume confirmed", color: "var(--positive)" },
  partial: { label: "Partial volume signal", color: "var(--warning)" },
  none: { label: "No volume confirmation", color: "var(--text-muted)" },
};

function GateBreakdown({ detail }) {
  return (
    <ul className="momentum-gate-list">
      {Object.entries(detail).map(([key, value]) => (
        <li key={key} className={`momentum-gate momentum-gate-${value}`}>
          <span>{GATE_LABELS[key] || key}</span>
          <span className="momentum-gate-status">{value}</span>
        </li>
      ))}
    </ul>
  );
}

export default function MomentumScreenerTab({ rows, capital }) {
  if (rows.length === 0) {
    return <p className="empty-state">No symbols passed every quality gate in the latest run.</p>;
  }
  const sized = sizePositions(
    rows.map((r) => ({ ...r, score: r.momentum_score ?? 0 })),
    capital
  );
  return (
    <div className="momentum-list">
      {sized.map((row, index) => {
        const badge = VOLUME_BADGE[row.volume_confirmation] || VOLUME_BADGE.none;
        return (
          <div key={row.symbol} className="asset-card momentum-card">
            <div className="asset-card-row">
              <div className="asset-card-main">
                <span className="momentum-rank">#{index + 1}</span>
                <span className="asset-symbol">{row.symbol}</span>
                <span className="momentum-sector">{row.sector || "Sector unknown"}</span>
                {row.pe_ratio != null && <span className="momentum-pe">P/E {row.pe_ratio.toFixed(1)}</span>}
              </div>
              <div className="asset-card-stats">
                <span className="momentum-score">Score {row.momentum_score?.toFixed(3) ?? "–"}</span>
                <span style={{ color: badge.color }}>{badge.label}</span>
                <a href={row.screener_url} target="_blank" rel="noreferrer" className="momentum-link">
                  Details →
                </a>
              </div>
            </div>
            <div className="momentum-risk">
              <span>Entry ₹{row.current_price.toLocaleString("en-IN")}</span>
              <span>Stop-loss ₹{row.stop_loss?.toLocaleString("en-IN")}</span>
              <span>
                Target ₹{row.target_low?.toLocaleString("en-IN")}–{row.target_high?.toLocaleString("en-IN")}
              </span>
              {row.suggested > 0 && <span>Suggested ₹{row.suggested.toLocaleString("en-IN")}</span>}
            </div>
            <GateBreakdown detail={row.quality_gate_detail} />
          </div>
        );
      })}
    </div>
  );
}
