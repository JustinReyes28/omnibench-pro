# OmniBench — Unified AI Benchmark Aggregator

**A zero-backend, auto-updating AI model leaderboard deployed on [Cloudflare Pages](https://omnibench-pro.pages.dev/) that aggregates [Artificial Analysis](https://artificialanalysis.ai/), [LiveBench](https://livebench.ai/), [Arena.ai (LMSYS)](https://arena.ai/leaderboard), and [Vals.ai](https://www.vals.ai/benchmarks) into a single interactive workbench.**

## 1. Why OmniBench Exists

Evaluating frontier LLMs requires checking four separate websites that measure completely different dimensions of performance:

| Upstream Source | Primary Strength | What It Misses Alone |
| :--- | :--- | :--- |
| **[Artificial Analysis](https://artificialanalysis.ai/)** | API throughput (tokens/s), latency (TTFT), token pricing ($/1M), and [Intelligence Index v5.0](https://artificialanalysis.ai/methodology/intelligence-benchmarking). | Does not include blind human preference battles or vertical legal/tax agent evaluations. |
| **[LiveBench](https://github.com/LiveBench/new-livebench)** | Contamination-free, verifiable monthly tasks across Coding, Math, Reasoning, Data Analysis, and IF ([LiveBench Paper](https://arxiv.org/html/2406.19314v2)). | Does not measure real-time inference provider latency or human conversational preference. |
| **[Arena.ai (LMSYS)](https://arena.ai/leaderboard)** | Millions of blind human pairwise votes ([LMArena Leaderboard](https://huggingface.co/spaces/lmarena-ai/arena-leaderboard)) across Text, Coding, and Vision. | Susceptible to formatting/style bias; does not track API pricing or deterministic agent pass rates. |
| **[Vals.ai](https://www.vals.ai/benchmarks)** | Real-world enterprise agent benchmarks ([Vals Index](https://www.vals.ai/benchmarks/vals_index), [Finance Agent](https://www.vals.ai/benchmarks/finance_agent), [LegalBench](https://www.vals.ai/benchmarks/legal_bench), [Vibe Code Bench](https://www.vals.ai/benchmarks/vibe-code)). | Evaluates a curated subset of frontier models rather than the full open-weights ecosystem. |

## 2. 60-Second Local Quickstart (Isolated via Docker)

To prevent cluttering your local development environment with Node.js, Python, virtual environments, and heavy `node_modules`, all local ingestion and dashboard development run inside an isolated Docker container:

```bash
# 1. Build and start the isolated dual-stack container (Python 3.12 + Node.js 20 LTS)
docker compose up -d
docker exec -it omnibench-dev bash

# 2. Inside the container: install dependencies, refresh data, and run dev server
pip install -r requirements.txt
npm install
python -m scripts.ingest.run_all
python -m scripts.transform.build_dataset
pytest
npm run dev -- --host 0.0.0.0
```

## 3. Data Attribution & License

Application source code is licensed under the [MIT License](https://opensource.org/license/mit). All benchmark scores and model evaluations remain the intellectual property of their respective creators: [Artificial Analysis](https://artificialanalysis.ai/), [LiveBench](https://livebench.ai/), [Arena.ai (LMSYS)](https://arena.ai/), and [Vals.ai](https://www.vals.ai/home).
