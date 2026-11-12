"""Unit tests for Phase 2 3-Tier Entity Resolution and Pareto / Percentile math."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from scripts.transform.build_dataset import build_unified_dataset
from scripts.transform.entity_resolver import (
    ALIASES_PATH,
    EntityResolver,
    _infer_effort_and_mode,
    normalize_slug,
)
from scripts.transform.normalizer import mark_pareto_frontier


class TestEntityResolverAndNormalizer(unittest.TestCase):
    def setUp(self) -> None:
        self.resolver = EntityResolver()

    def test_tier1_exact_alias_resolution(self) -> None:
        cid1, tier1, _ = self.resolver.resolve("artificial_analysis", "Claude Opus 5.5 (Reasoning)")
        cid2, tier2, _ = self.resolver.resolve("arena", "anthropic-claude-opus-5-5-202610")
        cid3, tier3, _ = self.resolver.resolve("vals", "Claude Opus 5.5 (Max)")
        cid_high, tier_high, meta_high = self.resolver.resolve("vals", "Claude Opus 5.5 (High)")
        self.assertEqual(cid1, "anthropic-claude-opus-5-5")
        self.assertEqual(cid2, "anthropic-claude-opus-5-5")
        self.assertEqual(cid3, "anthropic-claude-opus-5-5")
        self.assertEqual(cid_high, "anthropic-claude-opus-5-5-high")
        self.assertEqual(meta_high["thinking_effort"], "high")
        self.assertEqual(tier1, "tier1_exact")

    def test_tier2_normalized_slug_resolution(self) -> None:
        slug = normalize_slug("openai/GPT-5.6-Sol (Thinking)-20261015")
        self.assertEqual(slug, "gpt-5-6-sol")
        cid, tier, _ = self.resolver.resolve("arena", "openai/GPT-5.6-Sol (Thinking)-20261015")
        self.assertEqual(cid, "openai-gpt-5-6-sol")
        self.assertIn("tier2", tier)

    def test_tier3_unmatched_quarantine(self) -> None:
        cid, tier, _ = self.resolver.resolve("arena", "mystery-omega-99b-20261028", "MysteryOrg")
        self.assertEqual(tier, "tier3_quarantine")
        self.assertTrue(cid.startswith("unmatched-"))
        self.assertEqual(len(self.resolver.unmatched_queue), 1)

    def test_version_and_effort_signature_prevents_fuzzy_collision(self) -> None:
        cid_fable, _, _ = self.resolver.resolve("artificial_analysis", "Claude Fable 5.2 (Max)")
        cid_fable_xh, _, _ = self.resolver.resolve("livebench", "anthropic-claude-fable-5-2-xhigh")
        cid_inkling2, _, _ = self.resolver.resolve("vals", "Inkling 2 Small")
        self.assertEqual(cid_fable, "anthropic-claude-fable-5-2-max")
        self.assertEqual(cid_fable_xh, "anthropic-claude-fable-5-2-xhigh")
        self.assertEqual(cid_inkling2, "thinking-machines-inkling-2-small")

        cid_future_inkling, tier_i3, meta_i3 = self.resolver.resolve("vals", "Inkling 3 Small")
        self.assertEqual(tier_i3, "tier3_quarantine")
        self.assertEqual(cid_future_inkling, "unmatched-inkling-3-small")
        self.assertEqual(meta_i3["provider"], "Thinking Machines")

        cid_future_fable, tier_f53, meta_f53 = self.resolver.resolve("arena", "Claude Fable 5.3 (Max)")
        self.assertEqual(tier_f53, "tier3_quarantine")
        self.assertEqual(cid_future_fable, "unmatched-claude-fable-5-3-max")
        self.assertEqual(meta_f53["provider"], "Anthropic")
        self.assertEqual(meta_f53["thinking_effort"], "max")

        auto_cid_1, auto_tier_1, _ = self.resolver.resolve(
            "artificial_analysis", "Claude Fable 5.4 (Max)", "Anthropic", auto_promote=True
        )
        auto_cid_2, auto_tier_2, _ = self.resolver.resolve(
            "vals", "Claude Fable 5.4 (Max)", "Unknown", auto_promote=True
        )
        self.assertEqual(auto_cid_1, "anthropic-claude-fable-5-4-max")
        self.assertEqual(auto_tier_1, "tier2_auto_promoted")
        self.assertEqual(auto_cid_2, "anthropic-claude-fable-5-4-max")
        self.assertEqual(auto_tier_2, "tier2_normalized")

    def test_non_reasoning_and_series_name_effort_inference(self) -> None:
        self.assertEqual(_infer_effort_and_mode("DeepSeek V4.1 Flash 1017 (non-reasoning)"), ("standard", "non_reasoning"))
        self.assertEqual(_infer_effort_and_mode("Mistral Medium 3.5"), ("standard", "standard"))
        self.assertEqual(_infer_effort_and_mode("Mistral Medium 3.5 (high)"), ("high", "reasoning"))
        self.assertEqual(_infer_effort_and_mode("Gemini 4 Hydrogen (xhigh)"), ("xhigh", "reasoning"))

    def test_dynamic_release_date_sibling_and_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            aliases_copy = Path(tmpdir) / "model_aliases.json"
            shutil.copy2(ALIASES_PATH, aliases_copy)
            res = EntityResolver(aliases_path=aliases_copy)

            _, _, meta_m = res.resolve(
                "artificial_analysis", "Mistral Large 4 (medium)", "Mistral", auto_promote=True, default_release_date="2026-12-01"
            )
            self.assertEqual(meta_m["provider"], "Mistral AI")
            self.assertEqual(meta_m["release_date"], "2026-10-02")

            _, _, meta_new = res.resolve(
                "artificial_analysis", "FutureModel Omega 9", "OpenAI", auto_promote=True, default_release_date="2026-12-01"
            )
            self.assertEqual(meta_new["release_date"], "2026-12-01")

    def test_stealth_model_never_auto_promoted(self) -> None:
        cid, tier, _ = self.resolver.resolve(
            "arena", "stealth-nebula-v1-preview-20261027", "Stealth Lab", auto_promote=True
        )
        self.assertEqual(tier, "tier3_quarantine")
        self.assertTrue(cid.startswith("unmatched-"))

    def test_pareto_frontier_calculation_and_single_source_guard(self) -> None:
        sample_models = [
            {"id": "cheap-good", "pricing": {"blended_per_1m_usd": 0.50}, "composite": {"unified_quality_score": 80.0}},
            {"id": "expensive-worse", "pricing": {"blended_per_1m_usd": 5.00}, "composite": {"unified_quality_score": 75.0}},
            {"id": "flagship-best", "pricing": {"blended_per_1m_usd": 15.00}, "composite": {"unified_quality_score": 96.0}},
        ]
        mark_pareto_frontier(sample_models)
        by_id = {m["id"]: m["composite"]["is_pareto_optimal"] for m in sample_models}
        self.assertTrue(by_id["cheap-good"])
        self.assertFalse(by_id["expensive-worse"])
        self.assertTrue(by_id["flagship-best"])

        guarded = [
            {"id": "single-src", "pricing": {"blended_per_1m_usd": 0.25}, "composite": {"sources_present": 1, "unified_quality_score": 99.0}},
            {"id": "dual-src", "pricing": {"blended_per_1m_usd": 0.50}, "composite": {"sources_present": 2, "unified_quality_score": 85.0}},
        ]
        mark_pareto_frontier(guarded)
        self.assertFalse(guarded[0]["composite"]["is_pareto_optimal"])
        self.assertTrue(guarded[1]["composite"]["is_pareto_optimal"])

    def test_end_to_end_bidirectional_coalescing_and_multi_row_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            raw_dir = tmp / "raw"
            pub_dir = tmp / "public_data"
            aliases_copy = tmp / "model_aliases.json"
            unmatched_copy = tmp / "unmatched_models.json"
            shutil.copy2(ALIASES_PATH, aliases_copy)

            for src in ("artificial_analysis", "livebench", "arena", "vals"):
                (raw_dir / src).mkdir(parents=True, exist_ok=True)
                (raw_dir / src / "latest.json").write_text(
                    json.dumps({"fetched_at": "2026-12-01T00:00:00Z", "release": "2026-12-01", "models": []}),
                    encoding="utf-8",
                )

            # Day 0: Vals releases "Gemini 5 Nova" BEFORE AA splits effort tiers; LB has multi-row gpt-5.5
            (raw_dir / "vals" / "latest.json").write_text(json.dumps({
                "fetched_at": "2026-12-01T00:00:00Z",
                "models": [
                    {
                        "vals_model_name": "Gemini 5 Nova",
                        "provider": "Unknown",
                        "vals_index": 70.0,
                        "finance_agent": 68.0,
                        "legal_bench": 72.0,
                        "tax_agent": 60.0,
                        "vibe_code": 65.0,
                        "cost_per_test_usd": 8.0,
                    }
                ],
            }), encoding="utf-8")
            (raw_dir / "livebench" / "latest.json").write_text(json.dumps({
                "fetched_at": "2026-12-01T00:00:00Z",
                "release": "2026-12-01",
                "models": [
                    {"model_key": "gpt-5.5", "display_name": "gpt-5.5", "provider": "OpenAI", "global_average": 71.0, "coding": 71.0, "mathematics": 71.0, "reasoning": 71.0, "data_analysis": 71.0, "language": 71.0, "instruction_following": 71.0, "agentic_coding": 71.0},
                    {"model_key": "gpt-5.5-high", "display_name": "gpt-5.5-high", "provider": "OpenAI", "global_average": 73.0, "coding": 73.0, "mathematics": 73.0, "reasoning": 73.0, "data_analysis": 73.0, "language": 73.0, "instruction_following": 73.0, "agentic_coding": 73.0},
                ],
            }), encoding="utf-8")

            day0 = build_unified_dataset(
                aliases_path=aliases_copy,
                raw_dir=raw_dir,
                public_data_dir=pub_dir,
                unmatched_path=unmatched_copy,
            )
            day0_ids = {m["id"] for m in day0["models"]}
            self.assertIn("google-gemini-5-nova", day0_ids)

            # Day 1: AA arrives with "Gemini 5 Nova (xhigh)", "Gemini 5 Nova (high)", and "GPT-5.5 (xHigh)"
            (raw_dir / "artificial_analysis" / "latest.json").write_text(json.dumps({
                "fetched_at": "2026-12-02T00:00:00Z",
                "models": [
                    {"model_name": "Gemini 5 Nova (xhigh)", "provider": "Google", "context_window": 1000000, "open_weights": False, "intelligence_index": 62.0, "coding_index": 70.0, "math_index": 74.0, "output_tokens_per_second": 90.0, "ttft_seconds": 1.0, "input_price_per_1m": 1.0, "output_price_per_1m": 4.0, "blended_price_per_1m": 1.75},
                    {"model_name": "Gemini 5 Nova (high)", "provider": "Google", "context_window": 1000000, "open_weights": False, "intelligence_index": 58.0, "coding_index": 65.0, "math_index": 70.0, "output_tokens_per_second": 90.0, "ttft_seconds": 1.0, "input_price_per_1m": 0.5, "output_price_per_1m": 2.0, "blended_price_per_1m": 0.875},
                    {"model_name": "GPT-5.5 (xHigh)", "provider": "OpenAI", "context_window": 400000, "open_weights": False, "intelligence_index": 55.0, "coding_index": 60.0, "math_index": 65.0, "output_tokens_per_second": 80.0, "ttft_seconds": 1.2, "input_price_per_1m": 1.5, "output_price_per_1m": 6.0, "blended_price_per_1m": 2.625},
                ],
            }), encoding="utf-8")

            day1 = build_unified_dataset(
                aliases_path=aliases_copy,
                raw_dir=raw_dir,
                public_data_dir=pub_dir,
                unmatched_path=unmatched_copy,
            )
            by_id = {m["id"]: m for m in day1["models"]}
            # Vals standard entry was retroactively coalesced into xhigh flagship and retired
            self.assertNotIn("google-gemini-5-nova", by_id)
            nova_xh = by_id["google-gemini-5-nova-xhigh"]
            self.assertEqual(nova_xh["composite"]["sources_present"], 2)
            self.assertIsNotNone(nova_xh["benchmarks"]["artificial_analysis"])
            self.assertIsNotNone(nova_xh["benchmarks"]["vals"])
            self.assertIn("google-gemini-5-nova-high", by_id)
            # Multi-row LB family ("gpt-5.5" + "gpt-5.5-high") did NOT wrongly collapse into AA's "GPT-5.5 (xHigh)"
            self.assertIn("openai-gpt-5-5", by_id)
            self.assertIn("openai-gpt-5-5-high", by_id)
            self.assertIn("openai-gpt-5-5-xhigh", by_id)


if __name__ == "__main__":
    unittest.main()
