import type { CanonicalModel } from "./schema";

export interface PillarWeights {
  aa: number;
  lb: number;
  ar: number;
  va: number;
}

export const WEIGHT_PRESETS: Record<string, { label: string; description: string; weights: PillarWeights }> = {
  frontier: {
    label: "Default Balance (30/30/15/25)",
    description: "Default balanced weights: 30% AA v5.0, 30% LiveBench 2.0, 25% Vals v2.2, 15% Arena Elo.",
    weights: { aa: 30, lb: 30, ar: 15, va: 25 },
  },
  balanced: {
    label: "Equal Weights (25/25/25/25)",
    description: "Equal weight across Artificial Analysis, LiveBench, Arena.ai, and Vals.ai.",
    weights: { aa: 25, lb: 25, ar: 25, va: 25 },
  },
  coding: {
    label: "Coding & Agents",
    description: "Emphasizes LiveBench and Artificial Analysis coding benchmarks.",
    weights: { aa: 35, lb: 40, ar: 10, va: 15 },
  },
  enterprise: {
    label: "Enterprise Tasks",
    description: "Prioritizes Vals.ai enterprise benchmarks and AA Briefcase.",
    weights: { aa: 25, lb: 20, ar: 5, va: 50 },
  },
  human_chat: {
    label: "Human Preference",
    description: "Prioritizes human evaluation on Arena.ai alongside LiveBench.",
    weights: { aa: 15, lb: 25, ar: 50, va: 10 },
  },
};

export function computeDynamicCompositeScore(
  normalizedScores: { aa?: number | null; lb?: number | null; ar?: number | null; va?: number | null } | undefined,
  weights: PillarWeights,
  shrinkagePrior = 48.0
): number {
  if (!normalizedScores) return 0;
  let weightedSum = 0;
  let activeWeightTotal = 0;
  const requestedWeightTotal = Math.max(0, weights.aa) + Math.max(0, weights.lb) + Math.max(0, weights.ar) + Math.max(0, weights.va);

  for (const key of ["aa", "lb", "ar", "va"] as const) {
    const score = normalizedScores[key];
    const weight = weights[key];
    if (typeof score === "number" && !Number.isNaN(score) && weight > 0) {
      weightedSum += score * weight;
      activeWeightTotal += weight;
    }
  }

  if (activeWeightTotal === 0) return 0;
  const rawMean = weightedSum / activeWeightTotal;
  if (requestedWeightTotal > 0 && activeWeightTotal < requestedWeightTotal) {
    const missingFrac = (requestedWeightTotal - activeWeightTotal) / requestedWeightTotal;
    const priorWeight = 0.18 * missingFrac;
    return Number(((1 - priorWeight) * rawMean + priorWeight * shrinkagePrior).toFixed(2));
  }
  return Number(rawMean.toFixed(2));
}

export const computeDynamicScore = computeDynamicCompositeScore;

export function recomputeParetoFrontier(
  models: Array<{ id: string; dynamicScore?: number; score?: number; blendedPrice: number | null; provisional?: boolean }>
): Set<string> {
  const valid = models.filter(
    (m): m is { id: string; dynamicScore?: number; score?: number; blendedPrice: number; provisional?: boolean } =>
      typeof m.blendedPrice === "number" && m.blendedPrice > 0 && !m.provisional
  );
  const pareto = new Set<string>();
  for (const cand of valid) {
    const candScore = cand.dynamicScore ?? cand.score ?? 0;
    const dominated = valid.some((other) => {
      if (other.id === cand.id) return false;
      const otherScore = other.dynamicScore ?? other.score ?? 0;
      return (
        other.blendedPrice <= cand.blendedPrice &&
        otherScore >= candScore &&
        (other.blendedPrice < cand.blendedPrice || otherScore > candScore)
      );
    });
    if (!dominated) pareto.add(cand.id);
  }
  return pareto;
}

export function recomputeParetoFlags(
  models: Array<{ id: string; score: number; blendedPrice: number | null; provisional?: boolean }>
): Record<string, boolean> {
  const set = recomputeParetoFrontier(models);
  const out: Record<string, boolean> = {};
  for (const m of models) {
    out[m.id] = set.has(m.id);
  }
  return out;
}

export function scoreModelsWithWeights(models: CanonicalModel[], weights: PillarWeights) {
  const scored = models.map((m) => {
    const dynamicScore =
      computeDynamicCompositeScore(m.normalized_pillars ?? {}, weights) ||
      m.composite.unified_quality_score;
    return {
      ...m,
      dynamicScore,
    };
  });
  const paretoIds = recomputeParetoFrontier(
    scored.map((m) => ({
      id: m.id,
      dynamicScore: m.dynamicScore,
      blendedPrice: m.pricing.blended_per_1m_usd,
      provisional: Boolean(m.composite.provisional_ranking),
    }))
  );
  return scored
    .map((m) => ({
      ...m,
      isDynamicPareto: paretoIds.has(m.id),
    }))
    .sort((a, b) => {
      const provA = Boolean(a.composite.provisional_ranking);
      const provB = Boolean(b.composite.provisional_ranking);
      if (provA !== provB) return provA ? 1 : -1;
      return b.dynamicScore - a.dynamicScore;
    });
}
