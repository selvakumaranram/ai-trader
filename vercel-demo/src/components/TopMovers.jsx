export default function TopMovers({ assets }) {
  const gainers = [...assets].sort((a, b) => b.day_change_pct - a.day_change_pct).slice(0, 10);
  const losers = [...assets].sort((a, b) => a.day_change_pct - b.day_change_pct).slice(0, 10);

  return (
    <div className="top-movers">
      <div className="movers-column">
        <h3>Top Gainers</h3>
        {gainers.map((a) => (
          <div key={a.symbol} className="mover-row">
            <span className="asset-symbol">{a.symbol}</span>
            <span className="mover-pct positive">+{a.day_change_pct.toFixed(2)}%</span>
          </div>
        ))}
      </div>
      <div className="movers-column">
        <h3>Top Losers</h3>
        {losers.map((a) => (
          <div key={a.symbol} className="mover-row">
            <span className="asset-symbol">{a.symbol}</span>
            <span className="mover-pct negative">{a.day_change_pct.toFixed(2)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}
