import { useState } from "react";
import AssetCard from "./AssetCard.jsx";

const STYLES = ["intraday", "short_term", "swing"];

export default function SearchBox() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch(`/api/search?symbol=${encodeURIComponent(query.trim())}`);
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="search-box">
      <form onSubmit={handleSearch}>
        <input
          type="text"
          placeholder="Search any symbol (e.g. AAPL, RELIANCE.NS, BTC-USD)"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button type="submit" disabled={loading}>
          {loading ? "Searching…" : "Search"}
        </button>
      </form>
      {error && <p className="error-text">{error}</p>}
      {result && result.warning && <p className="warning-text">{result.warning}</p>}
      {result && (
        <div className="search-results">
          {STYLES.map((style) => (
            <AssetCard key={style} asset={result} style={style} suggested={undefined} showStyleLabel />
          ))}
        </div>
      )}
    </div>
  );
}
