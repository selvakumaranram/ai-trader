export default function CapitalInput({ capital, onChange }) {
  return (
    <div className="capital-input">
      <label htmlFor="capital">Capital to deploy (₹)</label>
      <input
        id="capital"
        type="number"
        min="0"
        step="100"
        value={capital}
        onChange={(e) => onChange(Number(e.target.value) || 0)}
      />
    </div>
  );
}
