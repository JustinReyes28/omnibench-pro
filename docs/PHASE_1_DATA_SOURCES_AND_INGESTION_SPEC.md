# PHASE 1: Data Sources, APIs, Scraping Feasibility & Ingestion Specification

**Document:** `PHASE_1_DATA_SOURCES_AND_INGESTION_SPEC.md`  
**Parent Plan:** `AI_IMPLEMENTATION_PLAN.md`  
**Target Codebase:** `omnibench-pro`  
**Target Agent Role:** Data Engineering & Ingestion Architecture Agent  
**Prerequisite Files:** `AGENTS.md`, `AI_IMPLEMENTATION_PLAN.md`  
**Downstream Handoff Target:** `PHASE_2_SCHEMA_NORMALIZATION_AND_COMPOSITE_INDEX.md`  

---

## Executive Summary & Objective

Build modular, fault-tolerant Python data ingestion adapters for **Artificial Analysis**, **LiveBench**, **Arena.ai (LMSYS)**, and **Vals.ai** that execute inside scheduled GitHub Actions and commit raw, timestamped JSON snapshots to the repository without requiring a paid runtime backend.

---

## 1. Feasibility & Upstream Source Architecture Matrix

Deploying a unified AI benchmark site to [Cloudflare Pages](https://omnibench-pro.pages.dev/) is 100% feasible by strictly decoupling **Data Ingestion** (Scheduled GitHub Actions) from **Presentation** (Static Frontend SPA). 

Browser clients never call authenticated upstream APIs or hit third-party CORS barriers. Instead, scheduled Python fetchers run daily in GitHub Actions, validate upstream payloads, and commit static JSON snapshots into the repository, which Cloudflare Pages automatically serves from the edge.

| Source Provider | Official URL & Docs | Primary Access Method | Key Metrics Extracted | Auth & Rate-Limit Rules |
| :--- | :--- | :--- | :--- | :--- |
| **Artificial Analysis** | [artificialanalysis.ai](https://artificialanalysis.ai/) | Official REST API (`https://artificialanalysis.ai/api/v2`) using `x-api-key` header | Intelligence Index v5.0, Output Speed (tokens/s), TTFT (s), Blended/Input/Output Price ($/1M tokens) | Pass `AA_API_KEY` via GitHub Secrets. Cache responses; fall back to Last-Known-Good (LKG) snapshot if quota reached. |
| **LiveBench** | [livebench.ai](https://livebench.ai/) / [GitHub](https://github.com/LiveBench/new-livebench) | Direct raw CSV/JSON fetch from public GitHub repository & Hugging Face datasets | Contamination-free scores (0–100) across 7 categories (Coding, Math, Reasoning, Data Analysis, Language, IF, Agentic Coding) + $/Q cost | 100% open data (MIT/Apache-2.0); zero API key required. Dynamically resolve latest date release from `src/lib/constants.js`. |
| **Arena.ai (LMSYS)** | [arena.ai](https://arena.ai/leaderboard) / [Hugging Face](https://huggingface.co/spaces/lmarena-ai/arena-leaderboard) | Public Hugging Face Space/Dataset artifacts & daily archival snapshots | Crowd-BT Elo ratings, 95% confidence intervals (+X / -Y), total battle counts across Text, Coding, Vision | Public read access. Pass optional `HF_TOKEN` in GitHub Secrets to avoid anonymous runner IP rate limits. |
| **Vals.ai** | [vals.ai](https://www.vals.ai/benchmarks) | Structured table extraction from public benchmark pages with BenchLM open data fallback | Vals Index score (% weighted by US GDP), Finance Agent accuracy, LegalBench, Tax Agent, Vibe Code Bench, and per-test execution cost ($) | Respect robots.txt, use descriptive custom User-Agent, poll at most once every 24h, and preserve clear attribution. |

---

## 2. Required Phase 1 Output Artifacts

| Output File Path | Purpose | Acceptance & Validation Standard | Status |
| :--- | :--- | :--- | :--- |
| `scripts/ingest/base_fetcher.py` | Abstract base class providing HTTP timeouts, custom User-Agent, exponential backoff, and Last-Known-Good (LKG) snapshot fallback. | Handles HTTP 429 and 5xx responses gracefully without crashing the pipeline. | Completed |
| `scripts/ingest/fetch_artificial_analysis.py` | REST client for `https://artificialanalysis.ai/api/v2` pulling LLM intelligence, speed, latency, and pricing metrics. | Validates `AA_API_KEY` env var or falls back to cached snapshot with structured warning. | Completed |
| `scripts/ingest/fetch_livebench.py` | Fetches latest `table_<date>.csv`, `categories_<date>.json`, and `cost_<date>.csv` from `LiveBench/new-livebench`. | Verifies all subtask columns in CSV map cleanly to categories in JSON. | Completed |
| `scripts/ingest/fetch_arena.py` | Pulls Elo scores and confidence intervals from `lmarena-ai/arena-leaderboard` and archival JSONs. | Extracts Text, Coding, and Vision Elo ratings plus 95% confidence bounds. | Completed |
| `scripts/ingest/fetch_vals.py` | Extracts public enterprise benchmark tables from Vals AI Benchmarks and BenchLM Open Data. | Parses accuracy percentages (0–100) and per-run cost floats cleanly. | Completed |
| `scripts/ingest/run_all.py` | Master orchestrator running all 4 adapters sequentially with summary reporting. | Exits with status code 0; produces structured logs. | Completed |
| `data/raw/<source>/latest.json` | Unmodified raw payload snapshots per provider with `fetched_at` ISO-8601 UTC metadata. | Valid JSON containing >= 15 frontier models per source. | Seeded |

---

## 3. Step-by-Step Implementation Guide

### Step 1.1: Resilient Base Fetcher (`scripts/ingest/base_fetcher.py`)
- Initialize `httpx.Client(timeout=30.0)` with header: `User-Agent: OmnibenchPro-Aggregator/1.0 (+https://omnibench-pro.pages.dev)`.
- Decorate requests with 3-retry exponential backoff (1s, 4s, 16s) on timeouts, HTTP 429, and 502/503/504 errors.
- **Last-Known-Good (LKG) Fallback:** If an upstream source fails or is temporarily unreachable, preserve the existing `data/raw/<source>/latest.json` file, flag `"fetch_status": "cached_fallback"`, and log a warning so downstream builds never fail.

### Step 1.2: Artificial Analysis Adapter (`scripts/ingest/fetch_artificial_analysis.py`)
- Query `https://artificialanalysis.ai/api/v2` passing `headers={"x-api-key": os.environ.get("AA_API_KEY", "")}`.
- Extract model metadata, Intelligence Index v5.0, Coding Index, Math Index, output speed (tokens/s), TTFT (s), and token pricing ($/1M tokens).
- Serialize to `data/raw/artificial_analysis/latest.json`.

### Step 1.3: LiveBench Adapter (`scripts/ingest/fetch_livebench.py`)
- Read `src/lib/constants.js` from `LiveBench/new-livebench` to discover the latest release date string.
- Download `table_<date>.csv`, `categories_<date>.json`, and `cost_<date>.csv`.
- Aggregate subtasks into the 7 core categories (Coding, Math, Reasoning, Data Analysis, Language, IF, Agentic Coding) and write to `data/raw/livebench/latest.json`.

### Step 1.4: Arena.ai Adapter (`scripts/ingest/fetch_arena.py`)
- Query the `lmarena-ai/arena-leaderboard` Hugging Face Space dataset artifacts and mirror archives.
- Extract overall Text Elo, Coding Elo, Vision Elo, 95% confidence intervals, and total battle counts.
- Save structured snapshot to `data/raw/arena/latest.json`.

### Step 1.5: Vals.ai Adapter (`scripts/ingest/fetch_vals.py`)
- Pull benchmark scores for Vals Index, Finance Agent, LegalBench, Tax Agent, and Vibe Code Bench.
- Extract per-test run cost estimates (`cost_usd_per_run`) and write to `data/raw/vals/latest.json`.

---

## 4. Phase 1 Completion Gate & Verification Checklist

- [x] All 4 adapter modules exist in `scripts/ingest/`.
- [x] Master runner `scripts/ingest/run_all.py` coordinates execution with structured error handling.
- [x] Seed snapshots for all 4 sources exist in `data/raw/` containing >= 15 models each.
- [ ] Automated ingestion unit tests verify retry backoff and fallback on mocked HTTP 429/503 responses (`tests/test_ingestion_adapters.py`).
- [ ] Upstream API keys (`AA_API_KEY`, `HF_TOKEN`) populated in GitHub Actions Secrets for live scheduled runs.
