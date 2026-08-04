const MAX_DEPLOY_PCT = 0.6;
const MAX_ALLOC_PER_IDEA = 0.2;

export function sizePositions(scoredAssets, capital) {
  const minTicket = capital * 0.02;
  const positive = scoredAssets.filter((a) => a.score > 0).map((a) => a.score);
  const totalPositive = positive.length ? positive.reduce((a, b) => a + b, 0) : 1.0;
  const deployable = capital * MAX_DEPLOY_PCT;
  const maxPerIdea = capital * MAX_ALLOC_PER_IDEA;

  return scoredAssets.map((a) => {
    let allocation = 0;
    if (a.score > 0) {
      const raw = deployable * (a.score / totalPositive);
      allocation = Math.min(maxPerIdea, raw);
      if (allocation < minTicket) allocation = 0;
    }
    return { ...a, suggested: Math.round(allocation) };
  });
}
