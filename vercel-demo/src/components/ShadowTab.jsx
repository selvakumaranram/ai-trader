import { useEffect, useState } from "react";
import { count, num, pct, rupees } from "./backtest/format.js";

// Shadow trading: pretend NIFTY option trades on live Kite prices. Nothing here places an order.
const RULE_NAMES = {
  agree2: "2 of 3 index rules agree",
  big_move: "Big move (≥1.5%) closing at the extreme",
  gap_hold: "Gap ≥1% that holds all day",
  sharp_dip: "Sharp dip in an uptrend (or rally in a downtrend)",
  c3_stock: "C3 breakout (stock)",
};
const idea = (s) => (s.side === "BUY" ? `Buy ${s.underlying}` : s.side === "CE" ? "NIFTY up (CE)" : "NIFTY down (PE)");
const muted = { color: "var(--text-muted)" };
const ruleName = (key) => RULE_NAMES[key] ?? key;
const when = (iso) => (iso ? new Date(iso).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }) : "—");

async function getJson(path, options) {
  const res = await fetch(path, options);
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error((data && data.detail) || `HTTP ${res.status}`);
  return data;
}

function ScoreRow({ label, s }) {
  return (
    <tr>
      <td>{label}</td>
      <td>{count(s.signals)}</td>
      <td>{count(s.closed)}</td>
      <td>{count(s.open)}</td>
      <td>{count(s.missed)}</td>
      <td>{pct(s.win_rate)}</td>
      <td>{rupees(s.total_pnl)}</td>
      <td>{rupees(s.avg_pnl)}</td>
    </tr>
  );
}

function ScoreTable({ title, rows }) {
  return (
    <section>
      <h3>{title}</h3>
      <table className="data-table">
        <thead>
          <tr>
            <th></th><th>Signals</th><th>Closed</th><th>Open</th><th>Missed</th><th>Win rate</th>
            <th>Total P&amp;L / lot</th><th>Avg P&amp;L / lot</th>
          </tr>
        </thead>
        <tbody>{rows.map(([label, s]) => <ScoreRow key={label} label={label} s={s} />)}</tbody>
      </table>
    </section>
  );
}

function Replay() {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const load = () => {
    setBusy(true);
    setError(null);
    getJson("/local/shadow/replay").then(setData).catch((e) => setError(e.message)).finally(() => setBusy(false));
  };
  return (
    <section>
      <h3>History check (NIFTY only, not option prices)</h3>
      <p style={muted}>
        Each rule replayed on past NIFTY data: how often NIFTY moved the signal's way within 5 days, and whether it
        reached the target (2 ATR) or the stop (1 ATR) first. With a 2:1 target the target must come first at least
        1 time in 3 just to break even. Past behaviour only — not a promise.
      </p>
      <button onClick={load} disabled={busy}>{busy ? "Replaying…" : data ? "Replay again" : "Run the history check"}</button>
      {error && <p className="error-text">{error}</p>}
      {data && (
        <table className="data-table">
          <thead>
            <tr><th>Rule</th><th>Period</th><th>Signals</th><th>Right way in 5 days</th><th>Avg NIFTY move</th>
              <th>Target first</th><th>Stop first</th></tr>
          </thead>
          <tbody>
            {Object.entries(data.rules).flatMap(([rule, periods]) =>
              ["earlier", "unseen"].map((p) => (
                <tr key={rule + p}>
                  <td>{ruleName(rule)}</td>
                  <td>{p === "earlier" ? `earlier (to ${data.unseen_from})` : "last 2 years"}</td>
                  <td>{count(periods[p].signals)}</td>
                  <td>{pct(periods[p].right_direction)}</td>
                  <td>{pct(periods[p].avg_move)}</td>
                  <td>{pct(periods[p].target_first)}</td>
                  <td>{pct(periods[p].stop_first)}</td>
                </tr>
              )))}
          </tbody>
        </table>
      )}
    </section>
  );
}

export default function ShadowTab() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const load = () => getJson("/local/shadow").then(setData).catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, []);

  const setView = (id, view) =>
    getJson(`/local/shadow/signals/${id}/view`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ view }),
    }).then(load).catch((e) => setError(e.message));

  if (error) return <p className="error-text">{error}</p>;
  if (!data) return <p>Loading…</p>;
  const sb = data.scoreboard;
  const open = data.trades.filter((t) => t.status === "open");
  const closed = data.trades.filter((t) => t.status === "closed");

  return (
    <div className="shadow-tab">
      <p style={muted}>
        <strong>Shadow trading — pretend trades only, no real orders.</strong> After each close the system checks NIFTY
        against 4 candidate "strong day" rules, and the stocks against strategy C3 (pretend ₹1,00,000 account, 1% risk
        per trade, ₹25,000 per stock, 5 open at most, 3-ATR trailing stop updated after each close). Next morning (about 9:20) it pretends to buy one lot of the
        at-the-money CE (up) or PE (down) at the live Kite price, and before the close (3:25) it checks the stop, the
        target, 5 days held, or expiry. Log in to Kite every morning before 9:15, or that day's entries are missed.
        P&amp;L per lot is after approximate charges.
      </p>

      <ScoreTable title="Scoreboard by rule" rows={Object.entries(sb.rules).map(([k, s]) => [ruleName(k), s])} />
      <ScoreTable title="Your calls" rows={[["You agreed", sb.views.agree], ["You disagreed", sb.views.disagree],
        ["No view given", sb.views.no_view]]} />

      <section>
        <h3>Signals</h3>
        {data.signals.length === 0 ? <p style={muted}>No signals yet. The first scan runs after today's close (4:40 PM).</p> : (
          <table className="data-table">
            <thead><tr><th>Date</th><th>Rule</th><th>Idea</th><th>Close</th><th>Stop / target</th><th>Why</th>
              <th>Status</th><th>Your view</th></tr></thead>
            <tbody>
              {data.signals.map((s) => (
                <tr key={s.id}>
                  <td>{s.signal_date}</td>
                  <td>{ruleName(s.rule)}</td>
                  <td>{idea(s)}</td>
                  <td>{num(s.close, 2)}</td>
                  <td>{num(s.stop, 2)} / {s.target == null ? "trailing" : num(s.target, 0)}</td>
                  <td>{s.reason}</td>
                  <td>{s.status}{s.note ? ` — ${s.note}` : ""}</td>
                  <td>
                    <button className={s.user_view === "agree" ? "tab active" : "tab"} onClick={() => setView(s.id, s.user_view === "agree" ? null : "agree")}>I agree</button>{" "}
                    <button className={s.user_view === "disagree" ? "tab active" : "tab"} onClick={() => setView(s.id, s.user_view === "disagree" ? null : "disagree")}>I don't</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {[["Open pretend trades", open], ["Closed pretend trades", closed]].map(([title, rows]) => (
        <section key={title}>
          <h3>{title}</h3>
          {rows.length === 0 ? <p style={muted}>None yet.</p> : (
            <table className="data-table">
              <thead><tr><th>Rule</th><th>Stock / option</th><th>Shares / lot</th><th>Entry</th><th>Entry price</th>
                <th>{title.startsWith("Open") ? "Latest mark" : "Exit price"}</th><th>Underlying entry → now/exit</th><th>Stop</th>
                <th>Exit</th><th>P&amp;L</th><th>R</th><th>Note</th></tr></thead>
              <tbody>
                {rows.map((t) => (
                  <tr key={t.id}>
                    <td>{ruleName(t.rule)}</td>
                    <td>{t.tradingsymbol}</td>
                    <td>{t.lot_size}</td>
                    <td>{when(t.entry_at)}</td>
                    <td>{num(t.entry_price)}</td>
                    <td>{num(t.exit_price ?? t.mark_price)}</td>
                    <td>{num(t.underlying_entry, 0)} → {num(t.underlying_exit ?? t.underlying_mark, 0)}</td>
                    <td>{num(t.stop, 2)}{t.kind === "stock" && t.initial_stop != null && Number(t.stop) > Number(t.initial_stop) ? " (trailed up)" : ""}</td>
                    <td>{t.exit_reason ?? "—"}</td>
                    <td>{t.pnl_per_lot == null ? (t.mark_price == null ? "—" : `≈ ${rupees((t.mark_price - t.entry_price) * t.lot_size)} (open)`) : rupees(t.pnl_per_lot)}</td>
                    <td>{t.r_multiple == null ? "—" : num(t.r_multiple)}</td>
                    <td>{t.note || ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      ))}

      <Replay />
    </div>
  );
}
