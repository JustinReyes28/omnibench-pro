# PHASE 3: Zero-Cost Automated GitHub Actions ETL Pipeline & Static Data Store

**Document:** `PHASE_3_GITHUB_ACTIONS_ETL_AND_STATIC_DATA_STORE.md`  
**Parent Plan:** `AI_IMPLEMENTATION_PLAN.md`  
**Target Codebase:** `omnibench-pro`  
**Target Agent Role:** DevOps, CI/CD Automation & Static Data Engineering Agent  
**Prerequisite Files:** `AGENTS.md`, `AI_IMPLEMENTATION_PLAN.md`, `PHASE_1_DATA_SOURCES_AND_INGESTION_SPEC.md`, `PHASE_2_SCHEMA_NORMALIZATION_AND_COMPOSITE_INDEX.md`  
**Downstream Handoff Target:** `PHASE_4_FRONTEND_DASHBOARD_AND_VISUALIZATION_ENGINE.md`  

---

## Executive Summary & Objective

Implement a zero-cost, serverless ETL pipeline using GitHub Actions that runs on a daily cron schedule (`0 6 * * *`), executes Phase 1 ingestion and Phase 2 normalization, compacts historical score deltas, and commits to `main` only when substantive benchmark scores or prices change.

---

## 1. Serverless GitHub-Native ETL Architecture

Instead of paying for managed databases or always-on cloud servers, the Git repository acts as an auditable flat-file data warehouse (Git Scraping pattern):

```
[Daily Cron: 06:00 UTC / Manual workflow_dispatch]
        │
        ▼
[GitHub Actions Runner: ubuntu-latest (Python 3.12)]
        ├─► Step 1: Run Phase 1 Fetchers (AA, LiveBench, Arena, Vals)
        ├─► Step 2: Run Phase 2 Entity Resolver & Normalizer
        ├─► Step 3: Run Data Integrity & Regression Gate (pytest)
        ├─► Step 4: Semantic Diff Check (Did any score or price change?)
        │      ├── No Changes ──► Exit cleanly (0 commits, 0 noisy rebuilds)
        │      └── Changes Detected ──►
        │             ├── Step 5: Archive snapshot to historical_trends.json
        │             ├── Step 6: Commit updated data/ to main
        │             └── Step 7: Triggers Cloudflare Pages deployment
```

---

## 2. Required Phase 3 Output Artifacts

| Output File Path | Purpose | Acceptance & Validation Standard | Status |
| :--- | :--- | :--- | :--- |
| `.github/workflows/sync-benchmarks.yml` | Scheduled daily GitHub Actions workflow (`cron: '0 6 * * *'`) with manual `workflow_dispatch`. | Uses minimal `contents: write` permissions and concurrency lock. | Completed |
| `scripts/ci/semantic_diff_check.py` | Compares newly built `models_unified.json` against the committed version, ignoring timestamps. | Returns exit code 0 (changes found) or non-zero (no substantive changes). | Completed |
| `scripts/ci/archive_snapshot.py` | Appends score points to `public/data/historical_trends.json` and updates `changelog.json`. | Keeps `historical_trends.json` compact (< 300 KB) via bucketed sampling. | Completed |
| `tests/test_data_integrity.py` | Pre-commit automated sanity suite checking model count drops, schema compliance, and score bounds. | Blocks commit if active model fleet drops by > 10% compared to prior snapshot. | Completed |
| `public/data/historical_trends.json` | Longitudinal score & price time series for charting trends over time. | Valid JSON containing timestamped records per model ID. | Generated |
| `public/data/changelog.json` | Human-readable log of new model releases, score shifts, and price reductions. | Valid JSON feed of score deltas. | Generated |

---

## 3. Step-by-Step Implementation Guide

### Step 3.1: Semantic Diff Check (`scripts/ci/semantic_diff_check.py`)
- Load the previous `public/data/models_unified.json` from Git HEAD and the freshly built file on disk.
- Strip volatile timestamp fields (`generated_at`, `last_updated`) from both payloads in memory.
- Compare model arrays, scores, speeds, and prices. Only when a model is added/removed or a score/price shifts by >= 0.01 does the script signal GitHub Actions to commit and push.

### Step 3.2: Automated History & Changelog Archiver (`scripts/ci/archive_snapshot.py`)
- When substantive changes are found, generate an entry in `public/data/changelog.json` (e.g., *"Updated Claude Opus 5.5 Arena Text Elo (+4 to 1412); added Kimi K3.1 Pro"*).
- Append compact summary records (`date`, `model_id`, `unified_quality_score`, `blended_per_1m_usd`) to `public/data/historical_trends.json`.

### Step 3.3: Pre-Commit Regression Gate (`tests/test_data_integrity.py`)
Before committing changes to `main`, `pytest tests/test_data_integrity.py` validates:
1. **Fleet Size Sanity:** Active model count in `models_unified.json` must be >= 30 and must not decrease by > 10% relative to the prior commit.
2. **Zero NaN/Infinity Leakage:** No `NaN`, `Infinity`, or `null` values in required numeric fields.
3. **Attribution Links:** All entries in `sources_metadata` have valid, clickable URLs.

---

## 4. Phase 3 Completion Gate & Verification Checklist

- [x] `.github/workflows/sync-benchmarks.yml` configured and valid YAML.
- [x] Semantic diff comparator implemented in `scripts/ci/semantic_diff_check.py`.
- [x] Historical snapshot compactor implemented in `scripts/ci/archive_snapshot.py`.
- [x] Data integrity test assertions created in `tests/test_data_integrity.py`.
- [ ] Push repository to GitHub and enable "Read and write permissions" under **Settings -> Actions -> General -> Workflow permissions**.
- [ ] Trigger manual workflow execution (`workflow_dispatch`) to verify clean end-to-end run.
