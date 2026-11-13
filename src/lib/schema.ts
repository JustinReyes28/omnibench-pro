import { z } from "zod";

export const PricingSchema = z.object({
  input_per_1m_usd: z.number().nullable(),
  output_per_1m_usd: z.number().nullable(),
  blended_per_1m_usd: z.number().nullable(),
});

export const PerformanceSchema = z.object({
  output_tokens_per_sec: z.number().nullable(),
  ttft_seconds: z.number().nullable(),
});

export const ArtificialAnalysisBenchSchema = z.object({
  intelligence_index: z.number(),
  coding_index: z.number(),
  math_index: z.number(),
});

export const LiveBenchSchema = z.object({
  global_average: z.number(),
  coding: z.number(),
  mathematics: z.number(),
  reasoning: z.number(),
  data_analysis: z.number(),
  language: z.number(),
  instruction_following: z.number(),
  agentic_coding: z.number(),
  cost_per_question_usd: z.number().nullable(),
});

export const ArenaSchema = z.object({
  text_elo: z.number(),
  text_ci_lower: z.number(),
  text_ci_upper: z.number(),
  coding_elo: z.number(),
  vision_elo: z.number().nullable(),
  votes: z.number(),
});

export const ValsSchema = z.object({
  vals_index: z.number(),
  finance_agent: z.number(),
  legal_bench: z.number(),
  tax_agent: z.number(),
  vibe_code: z.number(),
  cost_per_test_usd: z.number().nullable(),
});

export const CapabilitiesSchema = z.object({
  coding: z.number().nullable(),
  reasoning: z.number().nullable(),
  agentic: z.number().nullable(),
  enterprise: z.number().nullable(),
  chat: z.number().nullable(),
});
export type ModelCapabilities = z.infer<typeof CapabilitiesSchema>;

export const CompositeSchema = z.object({
  sources_present: z.number(),
  coverage_ratio: z.number(),
  provisional_ranking: z.boolean().optional(),
  unified_quality_score: z.number(),
  coding_composite_score: z.number(),
  enterprise_agent_score: z.number(),
  value_efficiency_score: z.number(),
  is_pareto_optimal: z.boolean(),
});

export const CanonicalModelSchema = z.object({
  id: z.string(),
  display_name: z.string(),
  provider: z.string(),
  release_date: z.string(),
  license: z.string(),
  is_open_weights: z.boolean(),
  context_window: z.number(),
  reasoning_mode: z.string(),
  thinking_effort: z.string().optional(),
  pricing: PricingSchema,
  performance: PerformanceSchema,
  benchmarks: z.object({
    artificial_analysis: ArtificialAnalysisBenchSchema.nullable(),
    livebench: LiveBenchSchema.nullable(),
    arena: ArenaSchema.nullable(),
    vals: ValsSchema.nullable(),
  }),
  normalized_pillars: z
    .object({
      aa: z.number().nullable().optional(),
      lb: z.number().nullable().optional(),
      ar: z.number().nullable().optional(),
      va: z.number().nullable().optional(),
    })
    .optional(),
  capabilities: CapabilitiesSchema.optional(),
  composite: CompositeSchema,
});

export const SourceMetadataItemSchema = z.object({
  last_updated: z.string(),
  status: z.string(),
  url: z.string(),
  release: z.string().optional(),
  methodology_url: z.string().optional(),
});
export type SourceMetadataItem = z.infer<typeof SourceMetadataItemSchema>;

export const SourcesMetadataSchema = z.object({
  artificial_analysis: SourceMetadataItemSchema,
  livebench: SourceMetadataItemSchema,
  arena: SourceMetadataItemSchema,
  vals: SourceMetadataItemSchema,
}).catchall(SourceMetadataItemSchema);

export type SourcesMetadataMap = z.infer<typeof SourcesMetadataSchema>;

export const UnifiedDatasetSchema = z.object({
  schema_version: z.string(),
  generated_at: z.string(),
  sources_metadata: SourcesMetadataSchema,
  models: z.array(CanonicalModelSchema),
});

export type CanonicalModel = z.infer<typeof CanonicalModelSchema>;
export type ModelEntry = CanonicalModel;
export type UnifiedDataset = z.infer<typeof UnifiedDatasetSchema>;
export type UnifiedBenchmarkPayload = UnifiedDataset;
