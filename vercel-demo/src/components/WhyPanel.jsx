const STYLE_LABELS = {
  intraday: "Day Trading",
  short_term: "Short-Term",
  swing: "Swing / Long-Term",
};

export default function WhyPanel({ asset, style }) {
  const styleData = asset.scores[style];

  return (
    <div className="why-panel">
      <div className="why-row">
        <span className="why-label">Momentum</span>
        <span className="why-value">{(asset.momentum * 100).toFixed(1)}%</span>
        <span className="why-detail">
          10-day return {(asset.momentum_detail.return_10d * 100).toFixed(1)}%, vs 50-day
          average {(asset.momentum_detail.trend_vs_sma50 * 100).toFixed(1)}%
        </span>
      </div>
      <div className="why-row">
        <span className="why-label">Sentiment</span>
        <span className="why-value">{asset.sentiment.toFixed(3)}</span>
        <span className="why-detail">
          {asset.matched_headlines.length > 0
            ? `From ${asset.matched_headlines.length} matched headline${asset.matched_headlines.length === 1 ? "" : "s"}`
            : "No matching headlines this run — neutral by default, not an error"}
        </span>
      </div>
      {asset.matched_headlines.length > 0 && (
        <ul className="why-headlines">
          {asset.matched_headlines.slice(0, 5).map((h, i) => (
            <li key={i}>{h.title}</li>
          ))}
        </ul>
      )}
      <div className="why-row">
        <span className="why-label">{STYLE_LABELS[style]} score</span>
        <span className="why-value">{styleData.score.toFixed(3)}</span>
        <span className="why-detail">
          Momentum × style weight + sentiment × style weight, threshold 0.15 for "Research LONG"
        </span>
      </div>
    </div>
  );
}
