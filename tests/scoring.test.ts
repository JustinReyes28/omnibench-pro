import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { UnifiedDatasetSchema } from "../src/lib/schema";
import {
  WEIGHT_PRESETS,
  computeDynamicCompositeScore,
  recomputeParetoFrontier,
  scoreModelsWithWeights,
} from "../src/lib/scoring";

import { getCapabilityScores, getCapabilityStrengthProfile } from "../src/lib/capabilities";

describe("UnifiedDatasetSchema & scoring invariants", () => {
  const unifiedPath = resolve(process.cwd(), "public/data/models_unified.json");
  const rawPayload = JSON.parse(readFileSync(unifiedPath, "utf8"));

  it("validates public/data/models_unified.json via Zod, enforces >=2 sources, and surfaces Gemini 4 Hydrogen", () => {
    const parsed = UnifiedDatasetSchema.parse(rawPayload);
    expect(parsed.models.length).toBeGreaterThanOrEqual(140);

    for (const m of parsed.models) {
      expect(m.composite.sources_present).toBeGreaterThanOrEqual(2);
      const caps = getCapabilityScores(m);
      const vals = Object.values(caps).filter((v): v is number => typeof v === "number");
      expect(vals.length).toBeGreaterThanOrEqual(1);
      for (const v of vals) {
        expect(v).toBeGreaterThanOrEqual(0);
        expect(v).toBeLessThanOrEqual(100);
      }
      const profile = getCapabilityStrengthProfile(m);
      expect(profile.evaluatedCount).toBeGreaterThanOrEqual(1);
    }

    const hydrogen = parsed.models.filter((m) =>
      m.display_name.toLowerCase().includes("hydrogen")
    );
    expect(hydrogen.length).toBeGreaterThanOrEqual(2);
    const xhigh = hydrogen.find((m) => m.id === "google-gemini-4-hydrogen-xhigh");
    const high = hydrogen.find((m) => m.id === "google-gemini-4-hydrogen-high");
    expect(xhigh).toBeDefined();
    expect(high).toBeDefined();
    expect(xhigh?.composite.sources_present).toBeGreaterThanOrEqual(2);
    expect(xhigh?.release_date).toBe("2026-11-12");
    expect(high?.release_date).toBe("2026-11-12");

    // Ensure 1/4 single-source outliers no longer leak into public/data/models_unified.json
    const ids = new Set(parsed.models.map((m) => m.id));
    for (const singleOutlier of [
      "zai-glm-5-2-max",
      "zai-glm-5-2",
      "xai-grok-4-20-beta-1",
      "deepseek-v4-1-flash-max",
      "meta-muse-spark",
    ]) {
      expect(ids.has(singleOutlier)).toBe(false);
    }
  });

  it("scores partial-source models with downward-only shrinkage and excludes single-source models from Pareto frontier", () => {
    const partialHigh = computeDynamicCompositeScore(
      { aa: 90, lb: null, ar: null, va: 90 },
      WEIGHT_PRESETS.frontier.weights
    );
    // Shrinkage pulls high 2/4 scores below raw mean of 90 toward prior 48
    expect(partialHigh).toBeGreaterThan(80);
    expect(partialHigh).toBeLessThan(90);

    const partialLow = computeDynamicCompositeScore(
      { aa: 6, lb: null, ar: 4, va: null },
      WEIGHT_PRESETS.frontier.weights
    );
    // Downward-only shrinkage must NOT boost low-scoring partial models toward 48
    expect(partialLow).toBeLessThanOrEqual(6);

    const pareto = recomputeParetoFrontier([
      { id: "single-only", score: 99, blendedPrice: 0.1, sourcesPresent: 1 },
      { id: "dual-src", score: 85, blendedPrice: 1.5, sourcesPresent: 2 },
    ]);
    expect(pareto.has("single-only")).toBe(false);
    expect(pareto.has("dual-src")).toBe(true);

    const parsed = UnifiedDatasetSchema.parse(rawPayload);
    const scored = scoreModelsWithWeights(parsed.models, WEIGHT_PRESETS.frontier.weights);
    for (const m of scored) {
      expect(m.composite.sources_present).toBeGreaterThanOrEqual(2);
      if (m.composite.sources_present < 2) {
        expect(m.isDynamicPareto).toBe(false);
      }
    }
  });
});
