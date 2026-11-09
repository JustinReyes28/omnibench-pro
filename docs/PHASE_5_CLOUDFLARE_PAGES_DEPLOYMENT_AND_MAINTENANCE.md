# PHASE 5: Cloudflare Pages CI/CD Deployment, Licensing, Attribution & Maintenance

**Document:** `PHASE_5_CLOUDFLARE_PAGES_DEPLOYMENT_AND_MAINTENANCE.md`  
**Parent Plan:** `AI_IMPLEMENTATION_PLAN.md`  
**Target Codebase:** `omnibench-pro`  
**Target Agent Role:** Release Engineering, Open-Source Compliance & Site Reliability Agent  
**Prerequisite Files:** `AGENTS.md`, `AI_IMPLEMENTATION_PLAN.md`, Phases 1–4 Specifications, and `CLOUDFLARE_PAGES_WORKFLOWS_AND_CONFIGS.md`  

---

## Executive Summary & Objective

Deploy the static benchmark dashboard to **Cloudflare Pages** (`https://omnibench-pro.pages.dev/`), establish the Git repository and automated CI/CD pipeline, enforce upstream benchmark data attribution, configure scraper health monitoring, and launch production operations.

---

## 1. Cloudflare Pages Deployment Architecture

Because Omnibench Pro is a static Vite application with zero runtime backend dependencies, it can be deployed via either of two clean methods:

### Method A: Cloudflare Pages Native Git Integration (Recommended)
1. In the **Cloudflare Dashboard**, navigate to **Compute (Workers & Pages)** -> **Create application** -> **Pages** -> **Connect to Git**.
2. Select the GitHub repository `omnibench-pro`.
3. Set build configuration:
   * **Framework preset:** `Vite`
   * **Build command:** `npm run build`
   * **Build output directory:** `dist`
   * **Environment variable:** `NODE_VERSION=20`
4. On every push to `main` (including automated daily data commits from `sync-benchmarks.yml`), Cloudflare automatically builds and deploys to the edge globally within seconds. Zero GitHub Actions deployment secrets needed!

### Method B: GitHub Actions Wrangler Deployment
Uses [`.github/workflows/deploy-cloudflare-pages.yml`](file:///C:/Users/Administrator/Documents/Projects/Web%20Dev%20Projects/Omnibench%20Pro%20AI%20Benchmark%20Aggregator%20Project/omnibench-pro/.github/workflows/deploy-cloudflare-pages.yml) with `cloudflare/wrangler-action@v3` to build in GitHub Actions and publish the `dist/` directory using `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`.

---

## 2. Upstream Data Attribution & Terms Compliance Matrix

Aggregating benchmark data publicly requires transparent credit and strict adherence to upstream terms:

| Upstream Source | Attribution & Backlink Requirement | Permitted Usage | Prohibited Actions |
| :--- | :--- | :--- | :--- |
| **Artificial Analysis** | Link to [artificialanalysis.ai](https://artificialanalysis.ai/) and [Intelligence Methodology](https://artificialanalysis.ai/methodology/intelligence-benchmarking) on speed, price, and intelligence views. | Display summary scores, latency, throughput, and token pricing with source credit. | Never expose private `AA_API_KEY` in frontend bundles or claim AA metrics as proprietary evaluations. |
| **LiveBench** | Cite the [LiveBench Paper](https://arxiv.org/html/2406.19314v2) and link to [livebench.ai](https://livebench.ai/) and GitHub repository. | Full open-source reuse of leaderboard CSV/JSON scores under Apache-2.0 / MIT. | Do not publish unhashed private test answers that could contaminate LLM training sets. |
| **Arena.ai (LMSYS)** | Link to [arena.ai](https://arena.ai/leaderboard) and the LMSYS Hugging Face Space. | Display Crowd-BT Elo ratings, confidence intervals, and battle counts. | Do not alter confidence bounds or mix incompatible Elo pools without clear disclosure. |
| **Vals.ai** | Link to [vals.ai/benchmarks](https://www.vals.ai/benchmarks) and [Vals AI Methodology](https://www.vals.ai/). | Display headline scores (Vals Index, Finance, Legal, Tax, Vibe Code) with deep links to full reports. | Do not bulk-mirror proprietary evaluation narratives or bypass scraping limits. |

---

## 3. Step-by-Step Production Launch Runbook

### Step 5.1: Initialize Git Repository
In `omnibench-pro/`:
```bash
git init
git add .
git commit -m "feat: initial commit of Omnibench Pro platform"
git branch -M main
git remote add origin https://github.com/<your-username>/omnibench-pro.git
git push -u origin main
```

### Step 5.2: Configure GitHub Actions Workflow Permissions
In your GitHub repository:
1. Navigate to **Settings -> Actions -> General**.
2. Under **Workflow permissions**, select **"Read and write permissions"**.
3. Check **"Allow GitHub Actions to create and approve pull requests"**.
4. Click **Save**.

### Step 5.3: Add GitHub Secrets (Settings -> Secrets and variables -> Actions)
* `AA_API_KEY` *(Optional)*: Artificial Analysis API key for daily ETL refresh.
* `HF_TOKEN` *(Optional)*: Hugging Face read token to avoid runner IP rate limits.
* `CLOUDFLARE_API_TOKEN` *(Only if using Method B)*: Cloudflare Pages deploy token.
* `CLOUDFLARE_ACCOUNT_ID` *(Only if using Method B)*: Cloudflare account ID.

### Step 5.4: Deploy to Cloudflare Pages
Connect repository in Cloudflare Pages dashboard (Method A) or trigger the deployment workflow (Method B). Verify edge deployment at `https://omnibench-pro.pages.dev/`.

### Step 5.5: Verify Edge Headers & Routing
1. Test SPA client routing: Navigating directly to subpaths returns HTTP 200 via `public/_redirects`.
2. Inspect cache headers on `https://omnibench-pro.pages.dev/data/models_unified.json`:
   * `cache-control: public, max-age=3600, s-maxage=3600, stale-while-revalidate=86400`
   * `access-control-allow-origin: *`

---

## 4. Phase 5 Completion Gate & Production Checklist

- [x] Cloudflare Pages workflow configured in `.github/workflows/deploy-cloudflare-pages.yml`.
- [x] `public/_headers` and `public/_redirects` configured for edge routing and caching.
- [x] Single-click Windows 11 runner ready: `scripts/start-dev.ps1`.
- [ ] Initialize Git repository and push to GitHub `main` branch.
- [ ] Enable GitHub Actions "Read and write permissions".
- [ ] Link repository in Cloudflare Pages dashboard.
- [ ] Verify live deployment at `https://omnibench-pro.pages.dev/`.
