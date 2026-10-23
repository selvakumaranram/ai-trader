import { useEffect, useRef, useState } from "react";
import { CandlestickSeries, createChart, createSeriesMarkers } from "lightweight-charts";
import { chartOptions, num, rupees, shiftDate } from "./format.js";

export default function TradeChart({ trade, onClose }) {
  const ref = useRef(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let chart = null;
    let cancelled = false;
    setError(null);
    const start = shiftDate(trade.signal_date, -90); // about 60 trading days before the signal
    const end = shiftDate(trade.exit_date, 15); // about 10 trading days after the exit
    fetch(`/local/bars/${encodeURIComponent(trade.symbol)}?start=${start}&end=${end}`)
      .then((res) => {
        if (!res.ok) throw new Error(`bars returned ${res.status}`);
        return res.json();
      })
      .then((bars) => {
        if (cancelled || !ref.current) return;
        chart = createChart(ref.current, chartOptions);
        const series = chart.addSeries(CandlestickSeries);
        series.setData(bars.map((b) => ({ time: b.trade_date, open: Number(b.open), high: Number(b.high),
                                          low: Number(b.low), close: Number(b.close) })));
        [["entry", trade.entry_price, "#2563eb"], ["stop", trade.stop, "#dc2626"],
         ["target", trade.target, "#16a34a"]].forEach(([title, price, color]) =>
          series.createPriceLine({ price: Number(price), color, lineWidth: 1, lineStyle: 2, title }));
        const won = Number(trade.pnl) >= 0;
        createSeriesMarkers(series, [
          { time: trade.entry_date, position: "belowBar", color: "#2563eb", shape: "arrowUp",
            text: `Buy ${num(trade.entry_price)}` },
          { time: trade.exit_date, position: "aboveBar", color: won ? "#16a34a" : "#dc2626", shape: "arrowDown",
            text: `Sell ${num(trade.exit_price)} (${trade.exit_reason})` },
        ]);
        chart.timeScale().fitContent();
      })
      .catch((e) => setError(e.message));
    return () => {
      cancelled = true;
      if (chart) chart.remove();
    };
  }, [trade]);

  return (
    <div className="trade-chart">
      <p>
        <strong>{trade.symbol}</strong> — {trade.reason} Result: {rupees(trade.pnl)} ({num(trade.r_multiple)}R).{" "}
        <button type="button" onClick={onClose}>Close chart</button>
      </p>
      {error && <p className="error-text">{error}</p>}
      <div ref={ref} style={{ width: "100%", height: 360 }} />
    </div>
  );
}
