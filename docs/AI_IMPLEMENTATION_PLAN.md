# Omnibench Pro — Master AI Implementation Plan (AI_IMPLEMENTATION_PLAN.md)

**Project Identity:** Official project name is **Omnibench Pro**; GitHub repository and Cloudflare Pages identifier is `omnibench-pro` (`omnibench-pro/`).  
**Purpose:** Master execution contract, repository file map, and phase-by-phase verification blueprint for building and deploying the Omnibench Pro AI Benchmark Aggregator to [Cloudflare Pages](https://omnibench-pro.pages.dev/).

---

## 1. End-to-End Repository Directory Structure

```
omnibench-pro/
├── .github/
│   └── workflows/
│       ├── sync-benchmarks.yml            # Daily 06:00 UTC ETL cron + semantic git commit
│       └── deploy-cloudflare-pages.yml    # Vite build + Cloudflare Pages deployment
├── data/
│   ├── raw/                               # Last-Known-Good raw upstream snapshots
│   │   ├── artificial_analysis/latest.json
│   │   ├── livebench/latest.json
│   │   ├── arena/latest.json
│   │   └── vals/latest.json
│   └── registry/
│       ├── model_aliases.json             # Canonical model ID <-> upstream alias dictionary
│       └── unmatched_models.json          # Auto-populated queue for new frontier models
├── public/
│   ├── data/
│   │   ├── models_unified.json            # Primary normalized dataset loaded by React SPA
│   │   ├── historical_trends.json         # Longitudinal score & price series
│   │   └── changelog.json                 # Automated feed of score/model updates
│   ├── _redirects                         # Cloudflare Pages SPA routing fallback (/* /index.html 200)
│   └── _headers                           # Cloudflare Pages edge cache-control rules
├── scripts/
│   ├── ingest/
│   │   ├── base_fetcher.py
│   │   ├── fetch_artificial_analysis.py
│   │   ├── fetch_livebench.py
│   │   ├── fetch_arena.py
│   │   ├── fetch_vals.py
│   │   └── run_all.py
│   ├── transform/
│   │   ├── schema.py                      # Pydantic v2 models
│   │   ├── entity_resolver.py             # 3-tier alias resolution
│   │   ├── normalizer.py                  # Calibrated frontier, composite & Pareto math
│   │   └── build_dataset.py
│   └── ci/
│       ├── semantic_diff_check.py         # Prevents empty timestamp-only commits
│       └── archive_snapshot.py
├── src/
│   ├── components/
│   │   ├── LeaderboardTable.tsx           # Master multi-source table
│   │   ├── WeightMixer.tsx                # Interactive pillar weight sliders
│   │   ├── ParetoChart.tsx                # Cost vs. Quality scatter + Pareto curve
│   │   ├── ModelComparisonModal.tsx       # 4-model radar comparison
│   │   └── SourceAttributionBar.tsx       # Live sync status + upstream links
│   ├── hooks/
│   │   └── useUrlFilterState.ts           # Syncs weights & filters to URL params
│   ├── lib/
│   │   ├── schema.ts                      # Runtime Zod schema matching Pydantic
│   │   ├── scoring.ts                     # Client-side real-time weight recalculation
│   │   └── dataLoader.ts
│   ├── App.tsx
│   └── main.tsx
├── tests/
│   ├── test_ingestion_adapters.py
│   ├── test_entity_resolver.py
│   └── test_data_integrity.py
├── .dockerignore                          # Ignores host node_modules, .venv, and build caches
├── compose.yaml                           # One-command Docker compose configuration
├── Dockerfile.dev                         # Dual-stack Python 3.12 + Node 20 development container
├── index.html
├── package.json
├── requirements.txt
├── tsconfig.json
├── vite.config.ts
└── README.md
```

---

## 2. Five-Phase Execution Roadmap & Acceptance Gates

| Phase | Specification File | Core Scope | Exit Gate Criteria |
| :--- | :--- | :--- | :--- |
| **Phase 1** | `PHASE_1_DATA_SOURCES_AND_INGESTION_SPEC.md` | Python adapters for Artificial Analysis API v2, LiveBench CSV/JSON, Arena.ai HF Space, and Vals.ai. | `python -m scripts.ingest.run_all` populates all 4 `data/raw/<source>/latest.json` files with LKG fallback. |
| **Phase 2** | `PHASE_2_SCHEMA_NORMALIZATION_AND_COMPOSITE_INDEX.md` | Alias reconciliation (`model_aliases.json`), Pydantic v2 schemas, calibrated normalization, and Pareto frontier calculation. | `python -m scripts.transform.build_dataset` outputs valid `public/data/models_unified.json` with zero NaN tokens. |
| **Phase 3** | `PHASE_3_GITHUB_ACTIONS_ETL_AND_STATIC_DATA_STORE.md` | Daily cron workflow (`sync-benchmarks.yml`), semantic diff check, changelog generation, and data regression tests. | pytest passes; unchanged runs create zero noisy commits; 10%+ model drop aborts commit. |
| **Phase 4** | `PHASE_4_FRONTEND_DASHBOARD_AND_VISUALIZATION_ENGINE.md` | React 18 + TypeScript + Vite SPA with Master Leaderboard, Weight Mixer, Pareto Scatter Plot, and Radar Comparison. | `npm run build` succeeds; `dist/_redirects` and `dist/_headers` are present; weight sliders recalculate in < 16ms. |
| **Phase 5** | `PHASE_5_CLOUDFLARE_PAGES_DEPLOYMENT_AND_MAINTENANCE.md` | Cloudflare Pages CI/CD deployment (`deploy-cloudflare-pages.yml` or Native Git Integration), upstream attribution badges, and automated drift alerts. | Live Cloudflare Pages URL (`https://omnibench-pro.pages.dev/`) renders all 4 benchmark sources with verified links and automated daily updates. |

---

## 3. Client-Side Dynamic Weighting Formula (`src/lib/scoring.ts`)

When a user drags the weight sliders in the frontend (e.g., setting Artificial Analysis = $w_{aa}$, LiveBench = $w_{lb}$, Arena.ai = $w_{ar}$, Vals.ai = $w_{va}$), compute each model's dynamic composite score over the set of sources $S_m$ present for model $m$:

```typescript
export function computeDynamicCompositeScore(
  normalizedScores: { aa?: number; lb?: number; ar?: number; va?: number },
  weights: { aa: number; lb: number; ar: number; va: number }
): number | null {
  let weightedSum = 0;
  let activeWeightTotal = 0;

  for (const key of ["aa", "lb", "ar", "va"] as const) {
    const score = normalizedScores[key];
    const weight = weights[key];
    if (typeof score === "number" && !Number.isNaN(score) && weight > 0) {
      weightedSum += score * weight;
      activeWeightTotal += weight;
    }
  }

  if (activeWeightTotal === 0) return null;
  return Number((weightedSum / activeWeightTotal).toFixed(2));
}
```
