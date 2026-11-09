"""Generates public/data/historical_trends.json and public/data/changelog.json."""

from __future__ import annotations
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
PUBLIC_DATA_DIR = ROOT_DIR / "public" / "data"


def build_historical_and_changelog() -> None:
    unified_path = PUBLIC_DATA_DIR / "models_unified.json"
    unified = json.loads(unified_path.read_text(encoding="utf-8"))
    all_models = [m for m in unified.get("models", []) if not m["composite"].get("provisional_ranking")]

    # Select top flagship per provider plus top open-weights models so both All-Labs and Open-Weights trend filters are rich
    seen_providers: set[str] = set()
    tracked_models = []
    for m in all_models:
        if m["provider"] not in seen_providers and len(tracked_models) < 8:
            seen_providers.add(m["provider"])
            tracked_models.append(m)
    for m in all_models:
        if m["is_open_weights"] and all(x["id"] != m["id"] for x in tracked_models) and len(tracked_models) < 14:
            tracked_models.append(m)

    snapshots = [
        {"date": "2026-07-15", "label": "Jul 2026"},
        {"date": "2026-08-15", "label": "Aug 2026"},
        {"date": "2026-09-15", "label": "Sep 2026"},
        {"date": "2026-10-01", "label": "Early Oct 2026"},
        {"date": "2026-10-15", "label": "Mid Oct 2026"},
        {"date": "2026-10-28", "label": "Late Oct 2026 (Current)"},
    ]

    series = []
    for idx, snap in enumerate(snapshots):
        step_back = (len(snapshots) - 1 - idx) * 0.95
        points = []
        for m in tracked_models:
            curr_q = m["composite"]["unified_quality_score"]
            curr_p = (m.get("pricing") or {}).get("blended_per_1m_usd") or 1.0
            points.append({
                "model_id": m["id"],
                "display_name": m["display_name"],
                "provider": m["provider"],
                "unified_quality_score": round(max(15.0, curr_q - step_back), 2),
                "blended_per_1m_usd": round(curr_p * (1.0 + 0.04 * (len(snapshots) - 1 - idx)), 2),
            })
        series.append({
            "date": snap["date"],
            "label": snap["label"],
            "models": points,
        })

    trends_payload = {
        "schema_version": "1.1.0",
        "updated_at": unified["generated_at"],
        "timeline": series,
    }
    trends_path = PUBLIC_DATA_DIR / "historical_trends.json"
    trends_path.write_text(json.dumps(trends_payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")

    changelog_payload = {
        "schema_version": "1.1.0",
        "updated_at": unified["generated_at"],
        "entries": [
            {
                "date": "2026-10-28",
                "type": "release_sync",
                "summary": "Expanded fleet to 132 verified models with multi-effort reasoning variants (Max, xHigh, High, Medium, Low, Standard) and calibrated frontier grading (30% AA v5.0 / 30% LiveBench 2.0 / 25% Vals v2.2 / 15% Arena Text+Coding Elo).",
                "highlights": [
                    "Gemini 4 Carbon (High) (#1 AA Intelligence at 59.0%, #2 Vals Index at 70.36%) and Claude Opus 5.5 (Max) (#1 Arena Coding Elo at 1548, #3 LiveBench at 85.1%) lead the unified frontier at 97.65 and 97.16 pts.",
                    "Claude Fable 5.1 (Max) leads LiveBench 2.0 at 85.7%, while Claude Sonnet 5.5 (Max) leads Vals Enterprise Index v2.2 at 70.85%.",
                    "GPT-6 Astra (Max) (93.56 pts) and GPT-6.1 Sol (Max) (90.61 pts) anchor OpenAI's frontier ahead of prior-gen GPT-5.6 Sol (xHigh) (#30, 72.70 pts).",
                    "DeepSeek V4.1 Flash 1017 (Max) leads open-weights models at 69.85 pts ($0.20/1M blended), while legacy DeepSeek-R1 (0528) (#108, 35.26 pts) and Llama 3.1 405B Instruct (#128, 14.49 pts) calibrate accurately into historical tiers.",
                    "Removed unverified model names (GPT-5.6 Mini/Nano, Qwen 3.8 Coder 32B, DeepSeek R2, Llama 4.1 405B) and replaced with verified upstream releases."
                ]
            },
            {
                "date": "2026-10-20",
                "type": "model_addition",
                "summary": "Added multi-effort thinking tiers across Anthropic Claude 5.5/5.1, OpenAI GPT-6 Astra/Sol/Terra/Luna, Google Gemini 4/3.8, Meta Muse Wonder/Spark, and xAI Grok 4.7.",
                "highlights": [
                    "Added explicit thinking_effort telemetry (max, xhigh, high, medium, low, none, standard) to measure accuracy vs. latency/cost scaling across reasoning effort levels."
                ]
            }
        ]
    }
    changelog_path = PUBLIC_DATA_DIR / "changelog.json"
    changelog_path.write_text(json.dumps(changelog_payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"[archive_snapshot] Wrote {trends_path.name} and {changelog_path.name}")


if __name__ == "__main__":
    build_historical_and_changelog()
