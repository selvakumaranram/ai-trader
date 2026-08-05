import { useEffect, useState } from "react";
import { apiFetch } from "../lib/api.js";
import AssetCard from "./AssetCard.jsx";

const STYLES = ["intraday", "short_term", "swing"];

export default function PersonalWatchlist() {
  const [items, setItems] = useState(null);
  const [failed, setFailed] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [symbol, setSymbol] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState(null);

  const load = () => {
    setLoading(true);
    apiFetch("/api/watchlist")
      .then((data) => {
        setItems(data.watchlist);
        setFailed(data.failed);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleAdd = async (e) => {
    e.preventDefault();
    if (!symbol.trim()) return;
    setSubmitting(true);
    setFormError(null);
    try {
      await apiFetch("/api/watchlist", {
        method: "POST",
        body: JSON.stringify({ symbol: symbol.trim() }),
      });
      setSymbol("");
      load();
    } catch (err) {
      setFormError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id) => {
    try {
      await apiFetch(`/api/watchlist?id=${id}`, { method: "DELETE" });
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="watchlist-tab">
      <form className="add-form" onSubmit={handleAdd}>
        <input
          type="text"
          placeholder="Symbol to watch (e.g. TATASTEEL.NS)"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          required
        />
        <button type="submit" disabled={submitting}>
          {submitting ? "Adding…" : "Add to watchlist"}
        </button>
      </form>
      {formError && <p className="error-text">{formError}</p>}

      {loading && <p>Loading your watchlist…</p>}
      {error && <p className="error-text">{error}</p>}
      {failed.length > 0 && (
        <p className="warning-text">
          {failed.length} symbol(s) unavailable right now: {failed.map((f) => f.symbol).join(", ")}
        </p>
      )}

      {items && items.length === 0 && (
        <p className="empty-state">Your watchlist is empty — add a symbol above.</p>
      )}
      {items && items.length > 0 && (
        <div className="watchlist-list">
          {items.map((item) => (
            <div key={item.id} className="watchlist-item">
              <div className="watchlist-item-header">
                <span className="watchlist-item-symbol">{item.symbol}</span>
                <button type="button" className="delete-button" onClick={() => handleDelete(item.id)}>
                  Remove
                </button>
              </div>
              <div className="watchlist-item-cards">
                {STYLES.map((style) => (
                  <AssetCard key={style} asset={item} style={style} suggested={undefined} showStyleLabel />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
