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

describe("UnifiedDatasetSchema & scoring invariants", () => {
  const unifiedPath = resolve(process.cwd(), "public/data/models_unified.json");
  const rawPayload = JSON.parse(readFileSync(unifiedPath, "utf8"));

  it("validates public/data/models_unified.json via Zod and surfaces Gemini 4 Hydrogen", () => {
    const parsed = UnifiedDatasetSchema.parse(rawPayload);
    expect(parsed.models.length).toBeGreaterThanOrEqual(140);

    const hydrogen = parsed.models.filter((m) =>
      m.display_name.toLowerCase().includes("hydrogen")
    );
    expect(hydrogen.length).toBe(4);
    const xhigh = hydrogen.find((m) => m.id === "google-gemini-4-hydrogen-xhigh");
    expect(xhigh).toBeDefined();
    expect(xhigh?.composite.sources_present).toBeGreaterThanOrEqual(2);
    expect(xhigh?.release_date).toBe("2026-11-12");
  });

  it("scores partial-source models with shrinkage and excludes single-source models from Pareto frontier", () => {
    const partialScore = computeDynamicCompositeScore(
      { aa: 90, lb: null, ar: null, va: 90 },
      WEIGHT_PRESETS.frontier.weights
    );
    // Shrinkage pulls 2/4 coverage slightly below raw mean of 90 toward prior 48
    expect(partialScore).toBeGreaterThan(80);
    expect(partialScore).toBeLessThan(90);

    const pareto = recomputeParetoFrontier([
      { id: "single-only", score: 99, blendedPrice: 0.1, sourcesPresent: 1 },
      { id: "dual-src", score: 85, blendedPrice: 1.5, sourcesPresent: 2 },
    ]);
    expect(pareto.has("single-only")).toBe(false);
    expect(pareto.has("dual-src")).toBe(true);

    const parsed = UnifiedDatasetSchema.parse(rawPayload);
    const scored = scoreModelsWithWeights(parsed.models, WEIGHT_PRESETS.frontier.weights);
    for (const m of scored) {
      if (m.composite.sources_present < 2) {
        expect(m.isDynamicPareto).toBe(false);
      }
    }
  });
});
