import { useState } from "react";
import WhyPanel from "./WhyPanel.jsx";

const SELL_SIGNAL_COLORS = {
  "Consider selling": "var(--negative)",
  "Short-term weakness": "var(--warning)",
  "Long-term weakness": "var(--warning)",
  Hold: "var(--positive)",
};

export default function HoldingCard({ holding, onDelete }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="asset-card holding-card">
      <div className="asset-card-row" onClick={() => setExpanded(!expanded)}>
        <div className="asset-card-main">
          <span className="asset-symbol">{holding.symbol}</span>
          <span className="holding-qty">
            {holding.quantity} @ ₹{holding.buy_price}
          </span>
        </div>
        <div className="asset-card-stats">
          <span
            className="holding-pnl"
            style={{ color: holding.unrealized_pnl >= 0 ? "var(--positive)" : "var(--negative)" }}
          >
            {holding.unrealized_pnl >= 0 ? "+" : ""}
            ₹{holding.unrealized_pnl.toLocaleString("en-IN")} ({holding.unrealized_pnl_pct.toFixed(1)}%)
          </span>
          <span
            className="asset-action"
            style={{ color: SELL_SIGNAL_COLORS[holding.sell_signal.action] || "var(--text-muted)" }}
          >
            {holding.sell_signal.action}
          </span>
          <span className="asset-expand-icon">{expanded ? "▲" : "▼"}</span>
        </div>
      </div>
      <div className="holding-meta">
        <span>{holding.days_held} days held</span>
        {holding.ltcg_applicable ? (
          <span>
            {holding.ltcg_eligible ? "Long-term eligible" : `${holding.days_to_ltcg} days to long-term`}
          </span>
        ) : (
          <span>N/A — India LTCG applies to .NS/.BO equity only</span>
        )}
        <button
          type="button"
          className="delete-button"
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
        >
          Remove
        </button>
      </div>
      {expanded && (
        <div className="holding-why">
          <p className="why-sell-reason">{holding.sell_signal.reason}</p>
          <WhyPanel asset={holding} style="short_term" />
          <WhyPanel asset={holding} style="swing" />
        </div>
      )}
    </div>
  );
}
