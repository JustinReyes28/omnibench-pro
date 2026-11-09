# OmniBench — AI Coding Agent Instructions (AGENTS.md)

1. **Zero Runtime Backend Dependency:** Cloudflare Pages serves static HTML/CSS/JS/JSON files only. Never write frontend code that requires a live backend server at runtime, and never embed secret API keys (`AA_API_KEY`) in client-side code.
2. **Git-Scraped Static JSON Store:** All external API calls and HTML/CSV parsing happen strictly inside Python scripts triggered by GitHub Actions (`.github/workflows/sync-benchmarks.yml`).
3. **Relative Base Path Discipline:** Always fetch static data using `fetch(`${import.meta.env.BASE_URL}data/models_unified.json`)`.
4. **Mandatory Docker Isolation for Local Development:** Execute local builds, data ingestion scripts, tests, and preview servers inside `Dockerfile.dev` / `compose.yaml`.
5. **Statistical Integrity:** Never average raw Arena Elo ratings with 0-100% scores; compute percentile ranks first. Never serialize `NaN` in JSON (`allow_nan=False`).
