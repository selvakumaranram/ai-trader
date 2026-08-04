import { useEffect, useState } from "react";
import { apiFetch } from "../lib/api.js";
import HoldingCard from "./HoldingCard.jsx";

export default function Holdings() {
  const [holdings, setHoldings] = useState(null);
  const [failed, setFailed] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ symbol: "", buy_price: "", quantity: "", buy_date: "" });
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState(null);

  const load = () => {
    setLoading(true);
    apiFetch("/api/holdings")
      .then((data) => {
        setHoldings(data.holdings);
        setFailed(data.failed);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleAdd = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setFormError(null);
    try {
      await apiFetch("/api/holdings", {
        method: "POST",
        body: JSON.stringify({
          symbol: form.symbol.trim(),
          buy_price: Number(form.buy_price),
          quantity: Number(form.quantity),
          buy_date: form.buy_date,
        }),
      });
      setForm({ symbol: "", buy_price: "", quantity: "", buy_date: "" });
      load();
    } catch (err) {
      setFormError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id) => {
    try {
      await apiFetch(`/api/holdings?id=${id}`, { method: "DELETE" });
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="holdings-tab">
      <form className="add-form" onSubmit={handleAdd}>
        <input
          type="text"
          placeholder="Symbol (e.g. RELIANCE.NS)"
          value={form.symbol}
          onChange={(e) => setForm({ ...form, symbol: e.target.value })}
          required
        />
        <input
          type="number"
          step="0.01"
          placeholder="Buy price"
          value={form.buy_price}
          onChange={(e) => setForm({ ...form, buy_price: e.target.value })}
          required
        />
        <input
          type="number"
          step="1"
          placeholder="Quantity"
          value={form.quantity}
          onChange={(e) => setForm({ ...form, quantity: e.target.value })}
          required
        />
        <input
          type="date"
          value={form.buy_date}
          onChange={(e) => setForm({ ...form, buy_date: e.target.value })}
          required
        />
        <button type="submit" disabled={submitting}>
          {submitting ? "Adding…" : "Add holding"}
        </button>
      </form>
      {formError && <p className="error-text">{formError}</p>}

      {loading && <p>Loading your holdings…</p>}
      {error && <p className="error-text">{error}</p>}
      {failed.length > 0 && (
        <p className="warning-text">
          {failed.length} holding(s) unavailable right now: {failed.map((f) => f.symbol).join(", ")}
        </p>
      )}

      {holdings && holdings.length === 0 && <p className="empty-state">No holdings yet — add one above.</p>}
      {holdings && holdings.length > 0 && (
        <div className="holdings-list">
          {holdings.map((h) => (
            <HoldingCard key={h.id} holding={h} onDelete={() => handleDelete(h.id)} />
          ))}
        </div>
      )}
    </div>
  );
}
