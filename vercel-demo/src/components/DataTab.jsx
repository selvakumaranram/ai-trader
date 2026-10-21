import { useEffect, useState } from "react";

const JOBS = [
  { key: "backfill_history", label: "Load history (5y)" },
  { key: "ingest_daily_bars", label: "Load today's bars" },
  { key: "run_quality_checks", label: "Run quality checks" },
  { key: "sync_instruments", label: "Sync Kite instruments" },
  { key: "snapshot_options", label: "Snapshot options" },
];

async function getJson(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path} returned ${res.status}`);
  return res.json();
}

function KiteBox({ kite }) {
  if (!kite.configured) {
    return <p className="warning-text">Kite is not configured. Add your Kite keys to ai-trader-core's .env.</p>;
  }
  if (kite.connected) {
    return (
      <p>
        Kite: <strong>connected</strong> as {kite.kite_user_id} until{" "}
        {new Date(kite.expires_at).toLocaleString("en-IN")}
      </p>
    );
  }
  return (
    <p>
      Kite: <strong>not connected</strong> — <a href="/local/kite/login">Log in to Kite</a> (needed each trading
      day before 15:35 for the option snapshot)
    </p>
  );
}

export default function DataTab() {
  const [status, setStatus] = useState(null);
  const [runs, setRuns] = useState([]);
  const [issues, setIssues] = useState([]);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState("");

  const load = () =>
    Promise.all([getJson("/local/status"), getJson("/local/runs?limit=20"), getJson("/local/issues?limit=50")])
      .then(([s, r, i]) => {
        setStatus(s);
        setRuns(r);
        setIssues(i);
        setError(null);
      })
      .catch((e) => setError(e.message));

  useEffect(() => {
    load();
  }, []);

  const runJob = async (job) => {
    setBusy(job);
    try {
      const res = await fetch(`/local/jobs/${job}/run`, { method: "POST" });
      if (!res.ok) throw new Error(`${job} returned ${res.status}`);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy("");
      setTimeout(load, 2000);
    }
  };

  if (error && !status) return <p className="error-text">Local data service unavailable: {error}</p>;
  if (!status) return <p>Loading data status…</p>;

  const bars = status.coverage.bars;
  return (
    <div className="data-tab">
      {error && <p className="error-text">{error}</p>}
      <KiteBox kite={status.kite} />

      <h3>Coverage</h3>
      <ul>
        {Object.entries(bars).map(([kind, c]) => (
          <li key={kind}>
            {kind}: {c.instruments} instruments, {c.first_date} → {c.last_date}
          </li>
        ))}
        <li>option snapshots: {status.coverage.option_snapshots.rows} rows</li>
      </ul>

      <h3>Actions</h3>
      <div className="data-actions">
        {JOBS.map((j) => (
          <button key={j.key} type="button" disabled={busy !== ""} onClick={() => runJob(j.key)}>
            {busy === j.key ? "Starting…" : j.label}
          </button>
        ))}
      </div>

      <h3>Recent runs</h3>
      <table>
        <tbody>
          {runs.map((r) => (
            <tr key={r.id}>
              <td>{r.job}</td>
              <td>{r.run_date}</td>
              <td>{r.status}</td>
              <td>{JSON.stringify(r.counts)}</td>
              <td>{r.message}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>Quality issues ({Object.entries(status.issue_counts).map(([k, v]) => `${k}: ${v}`).join(", ") || "none"})</h3>
      <table>
        <tbody>
          {issues.map((i) => (
            <tr key={i.id}>
              <td>{i.severity}</td>
              <td>{i.trade_date}</td>
              <td>{i.symbol || i.tradingsymbol || "—"}</td>
              <td>{i.check_name}</td>
              <td>{i.detail}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
