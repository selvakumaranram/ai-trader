import { useEffect, useState } from "react";
import EquityChart from "./backtest/EquityChart.jsx";
import TradeChart from "./backtest/TradeChart.jsx";
import { count, num, pct, rupees } from "./backtest/format.js";

const STRATEGIES = [
  { key: "momentum", label: "A — Momentum" },
  { key: "pullback", label: "B — Trend pullback" },
  { key: "breakout", label: "C — Breakout" },
];
const MONEY = [
  { key: "capital", label: "Starting capital (₹)", def: 20000 },
  { key: "risk_per_trade", label: "Risk per trade (₹)", def: 400 },
  { key: "daily_loss_limit", label: "Daily loss stop (₹)", def: 1000 },
  { key: "max_positions", label: "Max open positions", def: 3 },
  { key: "max_position_value", label: "Max per position (₹)", def: 7000 },
];
const METRICS = [
  ["return_pct", "Return", pct],
  ["cagr", "Yearly return (CAGR)", pct],
  ["max_drawdown_pct", "Biggest fall", pct],
  ["max_drawdown_amount", "Biggest fall (₹)", rupees],
  ["worst_month", "Worst month", pct],
  ["trades", "Trades", count],
  ["win_rate", "Win rate", pct],
  ["avg_win", "Average win", rupees],
  ["avg_loss", "Average loss", rupees],
  ["avg_win_r", "Average win (R)", num],
  ["avg_loss_r", "Average loss (R)", num],
  ["expectancy_r", "Expectancy (R per trade, after charges)", num],
  ["profit_factor", "Profit factor", num],
  ["total_charges", "Charges paid", rupees],
  ["charges_pct_of_gross", "Charges ÷ gross P&L", pct],
  ["longest_losing_streak", "Longest losing streak", count],
  ["pct_days_invested", "Days with money invested", pct],
];
const strategyLabel = (key) => STRATEGIES.find((s) => s.key === key)?.label ?? key;
const muted = { color: "var(--text-muted)" };

async function getJson(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path} returned ${res.status}`);
  return res.json();
}

function errorText(body, status) {
  if (body && typeof body.detail === "string") return body.detail;
  if (body && body.detail) return JSON.stringify(body.detail);
  return `request failed (${status})`;
}

function RunsTable({ runs, onOpen }) {
  if (runs.length === 0) return <p style={muted}>No backtests yet.</p>;
  return (
    <table>
      <thead>
        <tr>
          <th>#</th><th>Strategy</th><th>Period</th><th>Status</th><th>Return</th><th>Biggest fall</th>
          <th>Checklist</th><th />
        </tr>
      </thead>
      <tbody>
        {runs.map((r) => {
          const whole = r.summary?.whole;
          const passed = (r.summary?.checklist || []).filter((c) => c.passed).length;
          return (
            <tr key={r.id}>
              <td>{r.id}</td>
              <td>{strategyLabel(r.strategy)}</td>
              <td>{r.start_date ?? "—"} → {r.end_date ?? "—"}</td>
              <td>{r.status}</td>
              <td>{pct(whole?.return_pct)}</td>
              <td>{pct(whole?.max_drawdown_pct)}</td>
              <td>{r.summary ? `${passed}/4` : "—"}</td>
              <td><button type="button" onClick={() => onOpen(r.id)}>Open</button></td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function RunView({ run }) {
  const [trade, setTrade] = useState(null);
  const s = run.summary;
  const title = `Run #${run.id} — ${strategyLabel(run.strategy)}`;
  if (run.status !== "ok" || !s) {
    return (
      <section>
        <h3>{title}</h3>
        <p className={run.status === "failed" ? "error-text" : ""}>
          Status: {run.status}{run.message ? ` — ${run.message}` : ""}
        </p>
      </section>
    );
  }
  const bench = s.benchmark || {};
  const skips = Object.entries(s.skips || {});
  return (
    <section>
      <h3>{title} ({run.start_date} → {run.end_date})</h3>
      {s.warnings.map((w) => <p key={w} className="warning-text">{w}</p>)}

      <h4>Minimum-evidence checklist (not a promise of profit)</h4>
      <ul>{s.checklist.map((c) => <li key={c.key}>{c.passed ? "✓" : "✗"} {c.label}</li>)}</ul>

      <h4>Results</h4>
      <table>
        <thead>
          <tr><th /><th>Earlier years</th><th>Unseen years (from {run.unseen_from})</th><th>Whole run</th></tr>
        </thead>
        <tbody>
          {METRICS.map(([key, label, fmt]) => (
            <tr key={key}>
              <td>{label}</td>
              <td>{fmt(s.earlier?.[key])}</td>
              <td>{fmt(s.unseen?.[key])}</td>
              <td>{fmt(s.whole?.[key])}</td>
            </tr>
          ))}
          <tr>
            <td>NIFTY 50 buy &amp; hold — return</td><td />
            <td>{pct(bench.unseen?.return_pct)}</td><td>{pct(bench.whole?.return_pct)}</td>
          </tr>
          <tr>
            <td>NIFTY 50 buy &amp; hold — biggest fall</td><td />
            <td>{pct(bench.unseen?.max_drawdown_pct)}</td><td>{pct(bench.whole?.max_drawdown_pct)}</td>
          </tr>
        </tbody>
      </table>

      <h4>Account value vs NIFTY 50</h4>
      <EquityChart equity={run.equity} unseenFrom={run.unseen_from} />

      <h4>By year</h4>
      <table>
        <thead><tr><th>Year</th><th>Return</th><th>Biggest fall</th><th>Trades</th></tr></thead>
        <tbody>
          {s.years.map((y) => (
            <tr key={y.year}>
              <td>{y.year}</td><td>{pct(y.return_pct)}</td><td>{pct(y.max_drawdown_pct)}</td><td>{y.trades}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h4>Skipped signals</h4>
      {skips.length === 0 ? <p style={muted}>None.</p> : (
        <ul>{skips.map(([reason, n]) => <li key={reason}>{reason.replaceAll("_", " ")}: {n}</li>)}</ul>
      )}

      {s.index_signals.length > 0 && (
        <>
          <h4>NIFTY / BANKNIFTY signals — index signal quality in R, not option profit</h4>
          <table>
            <thead><tr><th>Index</th><th>Idea</th><th>Period</th><th>Signals</th><th>Win rate</th><th>Avg R</th></tr></thead>
            <tbody>
              {s.index_signals.map((r) => (
                <tr key={`${r.symbol}-${r.direction}-${r.period}`}>
                  <td>{r.symbol}</td><td>{r.direction === "long" ? "Bullish (CE)" : "Bearish (PE)"}</td>
                  <td>{r.period}</td><td>{r.signals}</td><td>{pct(r.win_rate)}</td><td>{num(r.avg_r)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      <h4>Trades ({run.trades.length}) — click a row to see its chart</h4>
      {trade && <TradeChart trade={trade} onClose={() => setTrade(null)} />}
      <table>
        <thead>
          <tr>
            <th>Symbol</th><th>Entry</th><th>Exit</th><th>Buy</th><th>Stop</th><th>Target</th><th>Sell</th>
            <th>Why it ended</th><th>Result</th><th>R</th><th>Why it was taken</th>
          </tr>
        </thead>
        <tbody>
          {run.trades.map((t) => (
            <tr key={t.id} onClick={() => setTrade(t)} style={{ cursor: "pointer" }}>
              <td>{t.symbol}</td><td>{t.entry_date}</td><td>{t.exit_date}</td><td>{num(t.entry_price)}</td>
              <td>{num(t.stop)}</td><td>{num(t.target)}</td><td>{num(t.exit_price)}</td>
              <td>{t.exit_reason.replaceAll("_", " ")}</td><td>{rupees(t.pnl)}</td><td>{num(t.r_multiple)}</td>
              <td>{t.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

export default function BacktestTab() {
  const [form, setForm] = useState({
    strategy: "pullback", start: "", end: "", ...Object.fromEntries(MONEY.map((m) => [m.key, m.def])),
  });
  const [runs, setRuns] = useState([]);
  const [run, setRun] = useState(null);
  const [runningId, setRunningId] = useState(null);
  const [error, setError] = useState(null);

  const loadRuns = () => getJson("/local/backtests?limit=50").then(setRuns).catch((e) => setError(e.message));
  const openRun = (id) => getJson(`/local/backtests/${id}`).then(setRun).catch((e) => setError(e.message));
  const set = (key) => (event) => setForm({ ...form, [key]: event.target.value });

  useEffect(() => {
    loadRuns();
  }, []);

  // Re-attach to a run that is still going (e.g. after switching tabs, which unmounts this component).
  useEffect(() => {
    const live = runs.find((r) => r.status === "running");
    if (live && runningId === null) setRunningId(live.id);
  }, [runs]);

  useEffect(() => {
    if (runningId === null) return undefined;
    let failures = 0;
    const timer = setInterval(() => {
      getJson(`/local/backtests/${runningId}`)
        .then((r) => {
          failures = 0;
          if (r.status !== "running") {
            setRunningId(null);
            setRun(r);
            loadRuns();
          }
        })
        .catch((e) => {
          failures += 1;
          if (failures >= 5) {  // keep polling through brief hiccups; give up only when the service is gone
            setRunningId(null);
            setError(e.message);
          }
        });
    }, 2000);
    return () => clearInterval(timer);
  }, [runningId]);

  const submit = async (event) => {
    event.preventDefault();
    setError(null);
    const body = { strategy: form.strategy, start: form.start || null, end: form.end || null };
    MONEY.forEach((m) => {
      body[m.key] = Number(form[m.key]);
    });
    try {
      const res = await fetch("/local/backtests", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(errorText(data, res.status));
      setRun(null);
      setRunningId(data.id);
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div className="backtest-tab">
      <form onSubmit={submit} style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem", alignItems: "end" }}>
        <label>
          Strategy{" "}
          <select value={form.strategy} onChange={set("strategy")}>
            {STRATEGIES.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
          </select>
        </label>
        <label>From <input type="date" value={form.start} onChange={set("start")} /></label>
        <label>To <input type="date" value={form.end} onChange={set("end")} /></label>
        {MONEY.map((m) => (
          <label key={m.key}>
            {m.label} <input type="number" min="1" value={form[m.key]} onChange={set(m.key)} style={{ width: "7rem" }} />
          </label>
        ))}
        <button type="submit" disabled={runningId !== null}>{runningId !== null ? "Running…" : "Run backtest"}</button>
      </form>
      <p style={muted}>
        Leave the dates empty to use all loaded history. Results show past behaviour only — not a promise of profit.
      </p>
      {error && <p className="error-text">{error}</p>}
      {runningId !== null && <p>Backtest #{runningId} is running…</p>}
      {run && <RunView run={run} />}
      <h3>Past runs</h3>
      <RunsTable runs={runs} onOpen={openRun} />
    </div>
  );
}
