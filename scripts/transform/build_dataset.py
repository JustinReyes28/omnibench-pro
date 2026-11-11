"""Executes Phase 2 Entity Resolution & Normalization to build public/data/models_unified.json."""

from __future__ import annotations
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.transform.entity_resolver import EntityResolver
from scripts.transform.normalizer import (
    compute_percentile_ranks,
    compute_weighted_composite,
    mark_pareto_frontier,
)
from scripts.transform.schema import validate_canonical_model_record

ROOT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT_DIR / "data" / "raw"
PUBLIC_DATA_DIR = ROOT_DIR / "public" / "data"


def build_unified_dataset() -> dict[str, Any]:
    resolver = EntityResolver()

    aa_raw = json.loads((RAW_DIR / "artificial_analysis" / "latest.json").read_text(encoding="utf-8"))
    lb_raw = json.loads((RAW_DIR / "livebench" / "latest.json").read_text(encoding="utf-8"))
    ar_raw = json.loads((RAW_DIR / "arena" / "latest.json").read_text(encoding="utf-8"))
    va_raw = json.loads((RAW_DIR / "vals" / "latest.json").read_text(encoding="utf-8"))

    merged: dict[str, dict[str, Any]] = {}

    def ensure_record(cid: str, meta: dict[str, Any]) -> dict[str, Any]:
        if cid not in merged:
            merged[cid] = {
                "id": cid,
                "display_name": meta["display_name"],
                "provider": meta["provider"],
                "release_date": meta["release_date"],
                "license": meta["license"],
                "is_open_weights": bool(meta["is_open_weights"]),
                "context_window": int(meta["context_window"]),
                "reasoning_mode": meta["reasoning_mode"],
                "thinking_effort": meta.get("thinking_effort", "standard"),
                "pricing": {
                    "input_per_1m_usd": None,
                    "output_per_1m_usd": None,
                    "blended_per_1m_usd": None,
                },
                "performance": {
                    "output_tokens_per_sec": None,
                    "ttft_seconds": None,
                },
                "benchmarks": {
                    "artificial_analysis": None,
                    "livebench": None,
                    "arena": None,
                    "vals": None,
                },
            }
        return merged[cid]

    # 1. Artificial Analysis
    for item in aa_raw.get("models", []):
        cid, tier, meta = resolver.resolve(
            "artificial_analysis", item["model_name"], item.get("provider", "Unknown"), auto_promote=True
        )
        rec = ensure_record(cid, meta)
        if tier in ("tier2_auto_promoted", "tier3_quarantine"):
            if item.get("release_date"):
                rec["release_date"] = item["release_date"]
                meta["release_date"] = item["release_date"]
            if item.get("license"):
                rec["license"] = item["license"]
                meta["license"] = item["license"]
            if "open_weights" in item:
                rec["is_open_weights"] = bool(item["open_weights"])
                meta["is_open_weights"] = bool(item["open_weights"])
            if item.get("context_window"):
                rec["context_window"] = int(item["context_window"])
                meta["context_window"] = int(item["context_window"])
        rec["pricing"] = {
            "input_per_1m_usd": round(float(item["input_price_per_1m"]), 3),
            "output_per_1m_usd": round(float(item["output_price_per_1m"]), 3),
            "blended_per_1m_usd": round(float(item["blended_price_per_1m"]), 3),
        }
        rec["performance"] = {
            "output_tokens_per_sec": round(float(item["output_tokens_per_second"]), 1),
            "ttft_seconds": round(float(item["ttft_seconds"]), 2),
        }
        rec["benchmarks"]["artificial_analysis"] = {
            "intelligence_index": round(float(item["intelligence_index"]), 2),
            "coding_index": round(float(item["coding_index"]), 2),
            "math_index": round(float(item["math_index"]), 2),
        }

    # 2. LiveBench
    for item in lb_raw.get("models", []):
        cid, tier, meta = resolver.resolve(
            "livebench", item.get("model_key") or item["display_name"], item.get("provider", "Unknown"), auto_promote=True
        )
        rec = ensure_record(cid, meta)
        if tier in ("tier2_auto_promoted", "tier3_quarantine") and item.get("display_name"):
            rec["display_name"] = item["display_name"]
            meta["display_name"] = item["display_name"]
        rec["benchmarks"]["livebench"] = {
            "global_average": round(float(item["global_average"]), 2),
            "coding": round(float(item["coding"]), 2),
            "mathematics": round(float(item["mathematics"]), 2),
            "reasoning": round(float(item["reasoning"]), 2),
            "data_analysis": round(float(item["data_analysis"]), 2),
            "language": round(float(item["language"]), 2),
            "instruction_following": round(float(item["instruction_following"]), 2),
            "agentic_coding": round(float(item["agentic_coding"]), 2),
            "cost_per_question_usd": round(float(item["cost_per_question_usd"]), 4) if item.get("cost_per_question_usd") is not None else None,
        }

    # 3. Arena.ai
    for item in ar_raw.get("models", []):
        cid, tier, meta = resolver.resolve(
            "arena", item.get("arena_model_id") or item["display_name"], item.get("organization", "Unknown"), auto_promote=True
        )
        rec = ensure_record(cid, meta)
        if tier in ("tier2_auto_promoted", "tier3_quarantine") and item.get("display_name"):
            rec["display_name"] = item["display_name"]
            meta["display_name"] = item["display_name"]
        if tier in ("tier2_auto_promoted", "tier3_quarantine") and item.get("license"):
            rec["license"] = item["license"]
            rec["is_open_weights"] = item["license"].lower() not in ("proprietary", "commercial")
            meta["license"] = rec["license"]
            meta["is_open_weights"] = rec["is_open_weights"]
        rec["benchmarks"]["arena"] = {
            "text_elo": int(item["text_elo"]),
            "text_ci_lower": int(item["text_ci_lower"]),
            "text_ci_upper": int(item["text_ci_upper"]),
            "coding_elo": int(item["coding_elo"]),
            "vision_elo": int(item["vision_elo"]) if item.get("vision_elo") is not None else None,
            "votes": int(item["votes"]),
        }

    # 4. Vals.ai
    for item in va_raw.get("models", []):
        cid, _, meta = resolver.resolve(
            "vals", item["vals_model_name"], item.get("provider", "Unknown"), auto_promote=True
        )
        rec = ensure_record(cid, meta)
        rec["benchmarks"]["vals"] = {
            "vals_index": round(float(item["vals_index"]), 2),
            "finance_agent": round(float(item["finance_agent"]), 2),
            "legal_bench": round(float(item["legal_bench"]), 2),
            "tax_agent": round(float(item["tax_agent"]), 2),
            "vibe_code": round(float(item["vibe_code"]), 2),
            "cost_per_test_usd": round(float(item["cost_per_test_usd"]), 2) if item.get("cost_per_test_usd") is not None else None,
        }

    resolver.save_registry()
    resolver.save_unmatched_queue()

    # Compute calibrated normalized scores across all 4 sources
    aa_map = {
        cid: r["benchmarks"]["artificial_analysis"]["intelligence_index"]
        for cid, r in merged.items()
        if r["benchmarks"]["artificial_analysis"]
    }
    lb_map = {
        cid: r["benchmarks"]["livebench"]["global_average"]
        for cid, r in merged.items()
        if r["benchmarks"]["livebench"]
    }
    ar_map = {
        cid: (
            0.55 * float(r["benchmarks"]["arena"]["text_elo"])
            + 0.45 * float(r["benchmarks"]["arena"]["coding_elo"])
        )
        for cid, r in merged.items()
        if r["benchmarks"]["arena"]
    }
    va_map = {
        cid: r["benchmarks"]["vals"]["vals_index"]
        for cid, r in merged.items()
        if r["benchmarks"]["vals"]
    }

    aa_norm = compute_percentile_ranks(aa_map)
    lb_norm = compute_percentile_ranks(lb_map)
    ar_norm = compute_percentile_ranks(ar_map)
    va_norm = compute_percentile_ranks(va_map)

    aa_code_norm = compute_percentile_ranks({cid: r["benchmarks"]["artificial_analysis"]["coding_index"] for cid, r in merged.items() if r["benchmarks"]["artificial_analysis"]})
    lb_code_norm = compute_percentile_ranks({cid: r["benchmarks"]["livebench"]["coding"] for cid, r in merged.items() if r["benchmarks"]["livebench"]})
    ar_code_norm = compute_percentile_ranks({cid: float(r["benchmarks"]["arena"]["coding_elo"]) for cid, r in merged.items() if r["benchmarks"]["arena"]})
    va_code_norm = compute_percentile_ranks({cid: r["benchmarks"]["vals"]["vibe_code"] for cid, r in merged.items() if r["benchmarks"]["vals"]})

    models_list: list[dict[str, Any]] = []
    for cid, rec in merged.items():
        b = rec["benchmarks"]
        sources_present = sum(1 for k in ("artificial_analysis", "livebench", "arena", "vals") if b.get(k) is not None)
        coverage_ratio = round(sources_present / 4.0, 2)

        pillars = {
            "aa": aa_norm.get(cid),
            "lb": lb_norm.get(cid),
            "ar": ar_norm.get(cid),
            "va": va_norm.get(cid),
        }
        unified_q = compute_weighted_composite(pillars, {"aa": 30.0, "lb": 30.0, "ar": 15.0, "va": 25.0})

        code_pillars = {
            "aa": aa_code_norm.get(cid),
            "lb": lb_code_norm.get(cid),
            "ar": ar_code_norm.get(cid),
            "va": va_code_norm.get(cid),
        }
        coding_comp = compute_weighted_composite(code_pillars, {"aa": 35.0, "lb": 40.0, "ar": 10.0, "va": 15.0})

        ent_pillars = {
            "aa": aa_norm.get(cid),
            "lb": lb_norm.get(cid),
            "ar": ar_norm.get(cid),
            "va": va_norm.get(cid),
        }
        enterprise_comp = compute_weighted_composite(ent_pillars, {"aa": 25.0, "lb": 20.0, "ar": 5.0, "va": 50.0})

        blended_price = rec["pricing"]["blended_per_1m_usd"]
        if blended_price is not None and blended_price > 0:
            raw_eff = unified_q / (1.0 + math.log10(max(0.05, blended_price) * 12.0))
            value_eff = round(max(10.0, min(99.5, raw_eff * 1.40)), 2)
        else:
            value_eff = round(unified_q * 0.75, 2)

        rec["normalized_pillars"] = {
            "aa": pillars["aa"],
            "lb": pillars["lb"],
            "ar": pillars["ar"],
            "va": pillars["va"],
        }
        rec["composite"] = {
            "sources_present": sources_present,
            "coverage_ratio": coverage_ratio,
            "provisional_ranking": cid.startswith("unmatched-"),
            "unified_quality_score": unified_q,
            "coding_composite_score": coding_comp,
            "enterprise_agent_score": enterprise_comp,
            "value_efficiency_score": value_eff,
            "is_pareto_optimal": False,
        }
        models_list.append(rec)

    mark_pareto_frontier(models_list)

    models_list.sort(
        key=lambda x: (
            not x["composite"]["provisional_ranking"],
            x["composite"]["unified_quality_score"],
        ),
        reverse=True,
    )

    for m in models_list:
        validate_canonical_model_record(m)

    payload = {
        "schema_version": "1.1.0",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources_metadata": {
            "artificial_analysis": {
                "last_updated": aa_raw.get("fetched_at", "2026-10-28T06:00:00Z"),
                "status": aa_raw.get("fetch_status", "live"),
                "url": "https://artificialanalysis.ai/",
                "methodology_url": "https://artificialanalysis.ai/methodology/intelligence-benchmarking",
            },
            "livebench": {
                "last_updated": lb_raw.get("fetched_at", "2026-10-28T06:00:00Z"),
                "release": lb_raw.get("release", "2026-10-25"),
                "status": lb_raw.get("fetch_status", "live"),
                "url": "https://livebench.ai/",
                "repo_url": "https://github.com/LiveBench/new-livebench",
            },
            "arena": {
                "last_updated": ar_raw.get("fetched_at", "2026-10-28T06:00:00Z"),
                "status": ar_raw.get("fetch_status", "live"),
                "url": "https://arena.ai/leaderboard",
                "hf_url": "https://huggingface.co/spaces/lmarena-ai/arena-leaderboard",
            },
            "vals": {
                "last_updated": va_raw.get("fetched_at", "2026-10-28T06:00:00Z"),
                "status": va_raw.get("fetch_status", "live"),
                "url": "https://www.vals.ai/benchmarks",
                "methodology_url": "https://www.vals.ai/methodology",
            },
        },
        "models": models_list,
    }

    PUBLIC_DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PUBLIC_DATA_DIR / "models_unified.json"
    serialized = json.dumps(payload, indent=2, allow_nan=False)
    out_path.write_text(serialized + "\n", encoding="utf-8")
    size_kb = out_path.stat().st_size / 1024.0
    print(
        f"[build_dataset] Built {len(models_list)} canonical models ({size_kb:.1f} KB) | "
        f"Pareto optimal={sum(1 for m in models_list if m['composite']['is_pareto_optimal'])} | "
        f"Unmatched quarantined={len(resolver.unmatched_queue)}"
    )
    return payload


if __name__ == "__main__":
    build_unified_dataset()
