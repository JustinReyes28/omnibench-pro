# PHASE 4: Static Frontend Architecture, Interactive Leaderboard & Visualization Engine

**Document:** `PHASE_4_FRONTEND_DASHBOARD_AND_VISUALIZATION_ENGINE.md`  
**Parent Plan:** `AI_IMPLEMENTATION_PLAN.md`  
**Target Codebase:** `omnibench-pro`  
**Target Agent Role:** Frontend Product, Data Visualization & UX Engineering Agent  
**Prerequisite Files:** `AGENTS.md`, `AI_IMPLEMENTATION_PLAN.md`, `PHASE_2_SCHEMA_NORMALIZATION_AND_COMPOSITE_INDEX.md`, `PHASE_3_GITHUB_ACTIONS_ETL_AND_STATIC_DATA_STORE.md`  
**Downstream Handoff Target:** `PHASE_5_CLOUDFLARE_PAGES_DEPLOYMENT_AND_MAINTENANCE.md`  

---

## Executive Summary & Objective

Build a fast, zero-backend React 18 + TypeScript + Vite + Tailwind CSS application for Omnibench Pro (`omnibench-pro`) that loads `public/data/models_unified.json` and provides interactive multi-benchmark ranking tables, custom user weight sliders, Pareto frontier cost-vs-intelligence scatter plots, and head-to-head model radar comparisons deployed on [Cloudflare Pages](https://omnibench-pro.pages.dev/).

---

## 1. Product Differentiation & User Experience

Developers currently keep four browser tabs open because each benchmark measures a distinct capability dimension:
- **Artificial Analysis:** Measures API inference speed (tokens/sec), latency (TTFT), token pricing ($/1M), and agentic knowledge work (AA-Briefcase).
- **LiveBench:** Measures contamination-free mathematical, coding, and reasoning capabilities refreshed monthly.
- **Arena.ai (LMSYS):** Measures crowd-sourced human preference across blind pairwise evaluations.
- **Vals.ai:** Measures real-world enterprise domain agent workflows (Finance, Law, Tax, Vibe Coding) weighted by US GDP.

Omnibench Pro aggregates all four sources into a single interactive workbench with instant client-side recalculation and URL-shareable filter states.

---

## 2. Required Phase 4 Engineering Deliverables

| Component / Module | File Path | Core Capabilities & Acceptance Standard | Status |
| :--- | :--- | :--- | :--- |
| **Runtime Zod Data Loader** | `src/lib/dataLoader.ts` | Fetches `data/models_unified.json` using `import.meta.env.BASE_URL` and validates at runtime with Zod. | Completed |
| **Dynamic Scoring Engine** | `src/lib/scoring.ts` | Recalculates weighted composite scores across active sources in < 16ms when sliders move. | Completed |
| **Unified Master Table** | `src/components/LeaderboardTable.tsx` | Built on `@tanstack/react-table`; supports multi-column sorting, search, provider filters, open-weights toggles, and expandable subtask rows. | Completed |
| **Weight Mixer Drawer** | `src/components/WeightMixer.tsx` | Interactive sliders for the 4 sources (AA, LiveBench, Arena, Vals) plus presets (*Calibrated Frontier*, *Coding & Agentic*, *Enterprise Finance/Legal*, *Human Arena Preference*). | Completed |
| **Pareto Scatter Plot** | `src/components/ParetoChart.tsx` | Recharts scatter plot: Log-scale X-axis (Blended $/1M tokens) vs. Y-axis (Unified Quality), highlighting the Pareto efficiency frontier. | Completed |
| **Model Radar Comparison** | `src/components/ModelComparisonModal.tsx` | Side-by-side 8-axis radar comparison of up to 4 models across speed, cost, coding, reasoning, and domain agent skills. | Completed |
| **Attribution & Status Bar** | `src/components/SourceAttributionBar.tsx` | Displays live sync status, upstream last-updated timestamps, and direct attribution backlinks. | Completed |
| **URL State Synchronization** | `src/hooks/useUrlFilterState.ts` | Synchronizes active weights, search queries, and selected models to URL query parameters for 1-click sharing. | Completed |

---

## 3. Dynamic Weighting Formula (`src/lib/scoring.ts`)

When a user drags weight sliders in the frontend:
$$S_m = \frac{\sum_{k \in S_m} w_k \cdot \text{score}_{m,k}}{\sum_{k \in S_m} w_k}$$

Where $S_m$ is the set of benchmark sources present for model $m$, and $w_k$ is the user-defined weight for source $k$. If $\sum w_k = 0$, the composite score gracefully returns `null`.

---

## 4. Cloudflare Pages Routing, Caching & Asset Rules

* **Base Path Discipline:** Always fetch static data using `fetch(`${import.meta.env.BASE_URL}data/models_unified.json`)`.
* **SPA Routing Fallback (`public/_redirects`):**
  ```
  /* /index.html 200
  ```
* **Edge Cache Headers (`public/_headers`):**
  ```
  /data/*.json
    Cache-Control: public, max-age=3600, s-maxage=3600, stale-while-revalidate=86400
    Access-Control-Allow-Origin: *

  /assets/*
    Cache-Control: public, max-age=31536000, immutable
  ```

---

## 5. Phase 4 Completion Gate & Verification Checklist

- [x] All React components authored in `src/components/`.
- [x] Runtime schemas and scoring algorithms authored in `src/lib/`.
- [x] URL state synchronization hook implemented in `src/hooks/`.
- [x] Single-file interactive offline preview generated: `omnibench_pro_preview.html`.
- [ ] Run `npm install` (or `pnpm install`) in `omnibench-pro/`.
- [ ] Run `npm run typecheck` and `npm run build` to verify zero TypeScript errors.
- [ ] Test dev server: `npm run dev` or `.\scripts\start-dev.ps1`.
