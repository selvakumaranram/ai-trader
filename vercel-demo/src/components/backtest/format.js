const isNum = (v) => v !== null && v !== undefined && v !== "" && !Number.isNaN(Number(v));

export const rupees = (v) =>
  isNum(v) ? `₹${Number(v).toLocaleString("en-IN", { maximumFractionDigits: 0 })}` : "—";
export const pct = (v) => (isNum(v) ? `${(Number(v) * 100).toFixed(1)}%` : "—");
export const num = (v, digits = 2) => (isNum(v) ? Number(v).toFixed(digits) : "—");
export const count = (v) => (isNum(v) ? String(v) : "—");

export function shiftDate(iso, days) {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

export const chartOptions = {
  autoSize: true,
  layout: { background: { color: "transparent" }, textColor: "#8a8f98" },
  grid: { vertLines: { color: "rgba(128,128,128,0.15)" }, horzLines: { color: "rgba(128,128,128,0.15)" } },
  rightPriceScale: { borderVisible: false },
  timeScale: { borderVisible: false },
};
