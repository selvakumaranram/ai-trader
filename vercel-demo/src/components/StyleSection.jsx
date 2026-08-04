import AssetCard from "./AssetCard.jsx";
import { sizePositions } from "../lib/positionSizing.js";

export default function StyleSection({ assets, style, capital }) {
  const ranked = [...assets]
    .sort((a, b) => b.scores[style].score - a.scores[style].score)
    .slice(0, 10)
    .map((a) => ({ ...a, score: a.scores[style].score }));

  const sized = sizePositions(ranked, capital);

  return (
    <div className="style-section">
      {sized.map((asset) => (
        <AssetCard key={asset.symbol} asset={asset} style={style} suggested={asset.suggested} />
      ))}
    </div>
  );
}
