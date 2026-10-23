import { useEffect, useRef } from "react";
import { LineSeries, createChart, createSeriesMarkers } from "lightweight-charts";
import { chartOptions } from "./format.js";

export default function EquityChart({ equity, unseenFrom }) {
  const ref = useRef(null);

  useEffect(() => {
    if (!ref.current || equity.length === 0) return undefined;
    const chart = createChart(ref.current, chartOptions);
    const strategy = chart.addSeries(LineSeries, { color: "#2563eb", lineWidth: 2, title: "Strategy" });
    strategy.setData(equity.map((p) => ({ time: p.trade_date, value: Number(p.equity) })));
    const bench = chart.addSeries(LineSeries, { color: "#9ca3af", lineWidth: 1, title: "NIFTY 50" });
    bench.setData(equity.map((p) => ({ time: p.trade_date, value: Number(p.benchmark_equity) })));
    const boundary = equity.find((p) => p.trade_date >= unseenFrom);
    if (boundary && boundary.trade_date > equity[0].trade_date) {
      createSeriesMarkers(strategy, [
        { time: boundary.trade_date, position: "aboveBar", color: "#f59e0b", shape: "arrowDown",
          text: "unseen period starts" },
      ]);
    }
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [equity, unseenFrom]);

  return <div ref={ref} style={{ width: "100%", height: 300 }} />;
}
