# PHASE 2: Entity Resolution, Schema Normalization & Composite Index Engine

**Document:** `PHASE_2_SCHEMA_NORMALIZATION_AND_COMPOSITE_INDEX.md`  
**Parent Plan:** `AI_IMPLEMENTATION_PLAN.md`  
**Target Codebase:** `omnibench-pro`  
**Target Agent Role:** Data Modeling, Entity Resolution & Statistical Normalization Agent  
**Prerequisite Files:** `AGENTS.md`, `AI_IMPLEMENTATION_PLAN.md`, `PHASE_1_DATA_SOURCES_AND_INGESTION_SPEC.md`  
**Downstream Handoff Target:** `PHASE_3_GITHUB_ACTIONS_ETL_AND_STATIC_DATA_STORE.md`  

---

## Executive Summary & Objective

Reconcile heterogeneous model naming conventions across **Artificial Analysis**, **LiveBench**, **Arena.ai (LMSYS)**, and **Vals.ai** into a canonical model dictionary, validate all records against strict Pydantic v2 / TypeScript Zod schemas, and compute unified percentile ranks and Pareto efficiency frontier flags.

---

## 1. The Core Challenge: Cross-Benchmark Entity Resolution

Every upstream benchmark identifies models differently:
- **Artificial Analysis:** Lists provider-branded names like `Claude 3.7 Sonnet (Reasoning)` or `GPT-5.6 Sol` with provider-level endpoints.
- **Arena.ai (LMSYS):** Uses date-stamped API endpoints such as `claude-3-7-sonnet-20250219-thinking-32k` or `gpt-5.6-sol-max`.
- **LiveBench:** Uses lowercase release slugs like `qwen3.8-27b` in its raw CSV table.
- **Vals.ai:** Appends reasoning effort tags such as `Gemini 4 Argon (High)` or `Kimi K3.1 Pro`.

Naive string comparison leads to row fragmentation (one physical model split across multiple incomplete rows). Phase 2 resolves this with a deterministic 3-tier Entity Resolution Pipeline backed by `data/registry/model_aliases.json`.

---

## 2. Required Phase 2 Output Artifacts

| Output File Path | Purpose | Acceptance & Validation Standard | Status |
| :--- | :--- | :--- | :--- |
| `data/registry/model_aliases.json` | Canonical dictionary mapping `canonical_model_id` to upstream aliases, provider, release date, and open-weights status. | Zero duplicate aliases across different canonical IDs. | Completed |
| `scripts/transform/entity_resolver.py` | 3-stage resolver: Tier 1 Exact Alias -> Tier 2 Deterministic Slug Normalization -> Tier 3 Unmatched Quarantine. | Unmatched models are logged to `unmatched_models.json` without pipeline failure. | Completed |
| `scripts/transform/schema.py` | Strict Pydantic v2 data models defining `CanonicalModelRecord`, per-source metric blocks, and composite indices. | 100% type coverage; rejects NaN, negative prices, or out-of-bounds percentages. | Completed |
| `scripts/transform/normalizer.py` | Statistical engine computing percentile ranks, coverage-weighted composites, and Pareto efficiency flags. | Handles missing benchmark coverage gracefully; never averages raw Elo with 0–100% scores. | Completed |
| `scripts/transform/build_dataset.py` | Master compilation script joining raw snapshots into the unified dataset. | Generates verified, valid `public/data/models_unified.json` (< 500 KB). | Completed |
| `public/data/models_unified.json` | Minified static JSON dataset loaded by the client-side React SPA. | Contains >= 30 frontier models, valid metadata, and zero `NaN` values. | Generated |

---

## 3. Canonical Unified Data Schema (`models_unified.json`)

Every record in `public/data/models_unified.json` must strictly validate against this structure:

```json
{
  "schema_version": "1.0.0",
  "generated_at": "2026-10-28T12:00:00Z",
  "sources_metadata": {
    "artificial_analysis": {
      "last_updated": "2026-10-28T06:00:00Z",
      "status": "live",
      "url": "https://artificialanalysis.ai/"
    },
    "livebench": {
      "last_updated": "2026-10-28T06:00:00Z",
      "release": "2026-10-15",
      "status": "live",
      "url": "https://livebench.ai/"
    },
    "arena": {
      "last_updated": "2026-10-28T06:00:00Z",
      "status": "live",
      "url": "https://arena.ai/leaderboard"
    },
    "vals": {
      "last_updated": "2026-10-28T06:00:00Z",
      "status": "live",
      "url": "https://www.vals.ai/benchmarks"
    }
  },
  "models": [
    {
      "id": "anthropic-claude-opus-5-5",
      "display_name": "Claude Opus 5.5",
      "provider": "Anthropic",
      "release_date": "2026-09-15",
      "license": "Proprietary",
      "is_open_weights": false,
      "context_window": 1000000,
      "reasoning_mode": "reasoning",
      "pricing": {
        "input_per_1m_usd": 15.0,
        "output_per_1m_usd": 75.0,
        "blended_per_1m_usd": 30.0
      },
      "performance": {
        "output_tokens_per_sec": 68.4,
        "ttft_seconds": 1.12
      },
      "benchmarks": {
        "artificial_analysis": {
          "intelligence_index": 57.6,
          "coding_index": 64.2,
          "math_index": 71.0
        },
        "livebench": {
          "global_average": 74.8,
          "coding": 79.1,
          "mathematics": 76.4,
          "reasoning": 81.2,
          "data_analysis": 70.5,
          "language": 68.9,
          "instruction_following": 78.0,
          "agentic_coding": 72.3,
          "cost_per_question_usd": 0.042
        },
        "arena": {
          "text_elo": 1412,
          "text_ci_lower": 1406,
          "text_ci_upper": 1418,
          "coding_elo": 1435,
          "vision_elo": 1360,
          "votes": 48200
        },
        "vals": {
          "vals_index": 70.18,
          "finance_agent": 68.4,
          "legal_bench": 74.2,
          "tax_agent": 71.5,
          "vibe_code": 86.1,
          "cost_per_test_usd": 8.20
        }
      },
      "composite": {
        "sources_present": 4,
        "coverage_ratio": 1.0,
        "unified_quality_score": 94.6,
        "coding_composite_score": 96.1,
        "enterprise_agent_score": 92.8,
        "value_efficiency_score": 61.4,
        "is_pareto_optimal": true
      }
    }
  ]
}
```

---

## 4. Step-by-Step Implementation Guide

### Step 2.1: 3-Tier Entity Resolver (`scripts/transform/entity_resolver.py`)
* **Tier 1 (Exact Alias Dictionary):** Match the raw name directly against `data/registry/model_aliases.json`.
* **Tier 2 (Slug Normalization):** Strip timestamp suffixes (`-20261015`), vendor prefixes (`openai/`, `anthropic/`), and reasoning tags (`(Thinking)`, `(High)`).
* **Tier 3 (Quarantine Queue):** Any unrecognized model is assigned a provisional slug and written to `data/registry/unmatched_models.json` for maintainer review via pull request.

### Step 2.2: Cross-Scale Statistical Normalization (`scripts/transform/normalizer.py`)
* **Percentile Ranks:** Because Arena Elo (~1000–1450+) and percentage benchmarks (0–100%) have different bounds, compute percentile ranks across the active model fleet before computing composite scores.
* **Unified Quality Score:** Default weighting:
  $$\text{Score} = 0.25 \cdot AA + 0.25 \cdot LiveBench + 0.25 \cdot Arena + 0.25 \cdot Vals$$
  Re-normalized over the set of sources present for each model.
* **Pareto Frontier (`is_pareto_optimal`):** A model is on the Pareto frontier if no other model simultaneously achieves a strictly higher `unified_quality_score` AND a lower or equal `blended_per_1m_usd` price.

---

## 5. Phase 2 Completion Gate & Verification Checklist

- [x] Pydantic models in `scripts/transform/schema.py` define all canonical types.
- [x] 3-tier resolver in `scripts/transform/entity_resolver.py` resolves known model variants.
- [x] Normalization engine in `scripts/transform/normalizer.py` calculates percentile ranks and Pareto frontier flags.
- [x] `public/data/models_unified.json` generated and verified (< 500 KB, zero `NaN` values).
- [ ] Run automated pytest test suite: `pytest tests/test_entity_resolver.py`.
