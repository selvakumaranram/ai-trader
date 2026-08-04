import { useState } from "react";
import WhyPanel, { STYLE_LABELS } from "./WhyPanel.jsx";

const TYPE_LABELS = {
  crypto: "Crypto",
  equity_us: "US Equity",
  equity_in: "Indian Equity",
};

const ACTION_COLORS = {
  "Research LONG": "var(--positive)",
  Watchlist: "var(--text-muted)",
};

export default function AssetCard({ asset, style, suggested, showStyleLabel }) {
  const [expanded, setExpanded] = useState(false);
  const styleData = asset.scores[style];

  return (
    <div className="asset-card">
      <div className="asset-card-row" onClick={() => setExpanded(!expanded)}>
        <div className="asset-card-main">
          <span className="asset-symbol">{asset.symbol}</span>
          {asset.type && <span className="asset-type">{TYPE_LABELS[asset.type] || asset.type}</span>}
          {showStyleLabel && <span className="asset-style-label">{STYLE_LABELS[style]}</span>}
        </div>
        <div className="asset-card-stats">
          <span className="asset-score">{styleData.score.toFixed(3)}</span>
          {suggested !== undefined && (
            <span className="asset-suggested">
              {suggested > 0 ? `₹${suggested.toLocaleString("en-IN")}` : "—"}
            </span>
          )}
          <span
            className="asset-action"
            style={{ color: ACTION_COLORS[styleData.action] || "var(--text-muted)" }}
          >
            {styleData.action}
          </span>
          <span className="asset-expand-icon">{expanded ? "▲" : "▼"}</span>
        </div>
      </div>
      {expanded && <WhyPanel asset={asset} style={style} />}
    </div>
  );
}
