"""Phase 3 Data Integrity & Pre-Commit Regression Gate Suite."""

import copy
import json
import unittest
from pathlib import Path
from scripts.ci.semantic_diff_check import has_substantive_changes
from scripts.transform.entity_resolver import EntityResolver
from scripts.transform.schema import validate_canonical_model_record

ROOT_DIR = Path(__file__).resolve().parents[1]
UNIFIED_PATH = ROOT_DIR / "public" / "data" / "models_unified.json"
TRENDS_PATH = ROOT_DIR / "public" / "data" / "historical_trends.json"
CHANGELOG_PATH = ROOT_DIR / "public" / "data" / "changelog.json"
RAW_AA_PATH = ROOT_DIR / "data" / "raw" / "artificial_analysis" / "latest.json"


class TestDataIntegrity(unittest.TestCase):
    def setUp(self) -> None:
        self.raw_text = UNIFIED_PATH.read_text(encoding="utf-8")
        self.data = json.loads(self.raw_text)

    def test_payload_size_and_minimum_fleet_count(self) -> None:
        size_kb = UNIFIED_PATH.stat().st_size / 1024.0
        self.assertLess(size_kb, 500.0, "models_unified.json must stay under 500 KB")
        models = self.data.get("models", [])
        self.assertGreaterEqual(len(models), 100, "Minimum fleet threshold is 100 models")

    def test_zero_nan_or_infinity_tokens(self) -> None:
        for forbidden in ("NaN", "Infinity", "-Infinity", "undefined"):
            self.assertNotIn(forbidden, self.raw_text)

    def test_frontier_grading_and_verified_model_names(self) -> None:
        models = self.data.get("models", [])
        names = {m["display_name"] for m in models}
        # Ensure fictitious model names do not exist
        for fake in ("GPT-5.6 Mini", "GPT-5.6 Nano", "Qwen 3.8 Coder 32B", "DeepSeek R2", "Llama 4.1 405B"):
            self.assertNotIn(fake, names)

        # Ensure multiple thinking effort variants exist
        efforts = {m.get("thinking_effort") for m in models}
        for req_effort in ("max", "xhigh", "high", "medium", "low", "standard"):
            self.assertIn(req_effort, efforts)

        # Ensure latest Nov 2026 frontier, flagship, and open-weights releases exist
        for latest_model in (
            "Claude Fable 5.2 (Max)",
            "Claude Fable 5.2 (xHigh)",
            "Claude Fable 5.2 (High)",
            "Inkling 2 Small",
            "Muse Ember (Max)",
            "Tencent Hy4",
            "Gemini 4 Hydrogen (xhigh)",
            "Gemini 4 Hydrogen (high)",
            "Gemini 4 Hydrogen (medium)",
            "Gemini 4 Hydrogen (low)",
        ):
            self.assertIn(latest_model, names)

        # Ensure frontier leaders outrank prior generations without blocking future #1 releases
        by_id = {m["id"]: m["composite"]["unified_quality_score"] for m in models}
        self.assertGreaterEqual(models[0]["composite"]["unified_quality_score"], 90.0)
        self.assertGreater(by_id["anthropic-claude-fable-5-2-max"], by_id["anthropic-claude-fable-5-1-max"])
        self.assertGreater(by_id["thinking-machines-inkling-2-small"], by_id["thinking-machines-inkling-small"])
        self.assertGreater(by_id["anthropic-claude-opus-5-5"], by_id["openai-gpt-5-6-sol"] + 15.0)
        self.assertGreater(by_id["openai-gpt-6-astra-max"], by_id["openai-gpt-5-6-sol"] + 10.0)
        self.assertGreater(by_id["deepseek-v4-1-flash-1017"], by_id["deepseek-r1-0528"] + 20.0)
        self.assertGreater(by_id["meta-muse-wonder-full-max"], by_id["meta-llama-3-1-405b-instruct"] + 45.0)

    def test_all_models_pass_schema_and_attribution_urls(self) -> None:
        sources_meta = self.data.get("sources_metadata", {})
        for key in ("artificial_analysis", "livebench", "arena", "vals"):
            self.assertIn(key, sources_meta)
            self.assertTrue(sources_meta[key].get("url", "").startswith("https://"))

        for model in self.data.get("models", []):
            validate_canonical_model_record(model)

    def test_all_models_have_complete_four_source_benchmarks_and_pricing(self) -> None:
        models = self.data.get("models", [])
        resolver = EntityResolver()
        raw_aa = json.loads(RAW_AA_PATH.read_text(encoding="utf-8"))
        raw_aa_by_cid: dict[str, dict] = {}
        for item in raw_aa.get("models", []):
            cid, tier, _ = resolver.resolve(
                "artificial_analysis",
                item["model_name"],
                item.get("provider", "Unknown"),
                auto_promote=False,
            )
            if tier != "tier3_quarantine":
                raw_aa_by_cid[cid] = item

        forbidden_providers = {
            "Wonder",
            "Mercury",
            "Mistral",
            "Stealth Lab",
            "Agnes",
            "Anonymous",
            "Unknown",
            "SpaceXAI",
            "Z AI",
            "Kimi",
            "Reflection",
            "Institute of Foundation Models",
        }
        source_pillar_pairs = (
            ("artificial_analysis", "aa"),
            ("livebench", "lb"),
            ("arena", "ar"),
            ("vals", "va"),
        )
        full_telemetry_4_count = 0
        for m in models:
            mid = m["id"]
            self.assertNotIn(m["provider"], forbidden_providers, f"Invalid provider on {mid}: {m['provider']}")
            self.assertNotEqual(
                m["provider"],
                m["provider"].lower(),
                f"Unnormalized lowercase provider on {mid}: {m['provider']}",
            )
            sources_present = m["composite"]["sources_present"]
            self.assertGreaterEqual(sources_present, 1, f"Model {mid} has 0 benchmark sources")
            self.assertLessEqual(sources_present, 4, f"Model {mid} has invalid source count")
            self.assertEqual(
                m["composite"]["coverage_ratio"],
                round(sources_present / 4.0, 2),
                f"Mismatched coverage_ratio on {mid}",
            )
            self.assertFalse(m["composite"]["provisional_ranking"], f"Unexpected provisional model in unified dataset: {mid}")

            actual_sources = sum(1 for src, _ in source_pillar_pairs if m["benchmarks"].get(src) is not None)
            self.assertEqual(actual_sources, sources_present, f"Mismatched sources_present on {mid}")

            for src, pillar in source_pillar_pairs:
                val = m["normalized_pillars"].get(pillar)
                if m["benchmarks"].get(src) is not None:
                    self.assertIsNotNone(val, f"Missing normalized pillar {pillar} on {mid}")
                    self.assertGreater(val, 0.0, f"Zero normalized pillar {pillar} on {mid}")
                else:
                    self.assertIsNone(val, f"Unexpected non-null pillar {pillar} without {src} on {mid}")

            if m["pricing"].get("blended_per_1m_usd") is not None:
                self.assertGreater(m["pricing"]["blended_per_1m_usd"], 0.0, f"Non-positive pricing on {mid}")
            else:
                self.assertFalse(
                    m["composite"]["is_pareto_optimal"],
                    f"Unpriced model {mid} must not claim Pareto frontier",
                )
            if m["performance"].get("output_tokens_per_sec") is not None:
                self.assertGreater(m["performance"]["output_tokens_per_sec"], 0.0, f"Non-positive speed on {mid}")

            if sources_present == 4 and m["pricing"].get("blended_per_1m_usd") is not None and m["performance"].get("output_tokens_per_sec") is not None:
                full_telemetry_4_count += 1

            raw_item = raw_aa_by_cid.get(mid)
            if raw_item is not None:
                if raw_item.get("blended_price_per_1m") is None:
                    self.assertIsNone(m["pricing"].get("blended_per_1m_usd"), f"Fabricated pricing on {mid}")
                else:
                    self.assertAlmostEqual(
                        m["pricing"].get("blended_per_1m_usd"),
                        round(float(raw_item["blended_price_per_1m"]), 3),
                        places=3,
                        msg=f"Pricing mismatch against raw AA on {mid}",
                    )
                if raw_item.get("output_tokens_per_second") is None:
                    self.assertIsNone(m["performance"].get("output_tokens_per_sec"), f"Fabricated speed on {mid}")
                else:
                    self.assertAlmostEqual(
                        m["performance"].get("output_tokens_per_sec"),
                        round(float(raw_item["output_tokens_per_second"]), 1),
                        places=1,
                        msg=f"Speed mismatch against raw AA on {mid}",
                    )

            if sources_present < 2:
                self.assertFalse(
                    m["composite"]["is_pareto_optimal"],
                    f"Single-source model {mid} must not claim Pareto frontier",
                )
                if m["benchmarks"].get("arena") is not None and resolver.canonical_models.get(mid, {}).get("auto_promoted"):
                    self.assertGreaterEqual(
                        m["release_date"],
                        "2026-01-01",
                        f"Pre-2026 single-source Arena historical model leaked into unified dataset: {mid}",
                    )

            if "non-reasoning" in m["display_name"].lower():
                self.assertEqual(m.get("thinking_effort"), "standard", f"Invalid effort on {mid}")

        self.assertGreaterEqual(full_telemetry_4_count, 135, "Expected >= 135 4/4 models with complete pricing and speed telemetry")

        by_id = {m["id"]: m for m in models}
        # API-verified pricing is preserved and never overwritten by HTML Cost-per-Task summary estimates
        self.assertGreater(by_id["openai-gpt-6-astra-max"]["pricing"]["blended_per_1m_usd"], 15.0)
        self.assertGreater(by_id["meta-muse-wonder-full-max"]["pricing"]["blended_per_1m_usd"], 8.0)

        # Gemini 4 Hydrogen flagship coalesces Vals + AA without orphan duplicate
        self.assertNotIn("google-gemini-4-hydrogen", by_id)
        h_xhigh = by_id["google-gemini-4-hydrogen-xhigh"]
        self.assertEqual(h_xhigh["provider"], "Google")
        self.assertEqual(h_xhigh["release_date"], "2026-11-12")
        self.assertEqual(h_xhigh["thinking_effort"], "xhigh")
        self.assertGreaterEqual(h_xhigh["composite"]["sources_present"], 2)
        self.assertIsNotNone(h_xhigh["benchmarks"]["artificial_analysis"])
        self.assertIsNotNone(h_xhigh["benchmarks"]["vals"])

        # Series names containing effort words must not misclassify as reasoning effort
        self.assertEqual(by_id["mistral-medium-3-5"]["thinking_effort"], "standard")
        self.assertNotIn("unmatched-stealth-nebula-v1", by_id)

        # LiveBench-only models retain real release dates (never CSV filename date), formatted names, and open-weights metadata
        expected_lb = {
            "openai-gpt-5-2-codex": ("GPT-5.2-Codex", "2025-12-18", False, "Proprietary", 400000),
            "zai-glm-5-2": ("GLM-5.2", "2026-06-16", True, "MIT", 1000000),
            "moonshot-kimi-k2-7-code": ("Kimi K2.7 Code", "2026-06-12", True, "Modified MIT", 262000),
            "xai-grok-build-0-1": ("Grok Build 0.1", "2026-05-20", False, "Proprietary", 256000),
            "alibaba-qwen3-6-27b": ("Qwen3.6-27B", "2026-04-21", True, "Apache-2.0", 262000),
            "xai-grok-4-3": ("Grok 4.3", "2026-04-30", False, "Proprietary", 1000000),
            "openai-gpt-5-5": ("GPT-5.5", "2026-03-10", False, "Proprietary", 1050000),
            "openai-gpt-5-5-high": ("GPT-5.5 (High)", "2026-03-10", False, "Proprietary", 1050000),
        }
        for mid, (disp, rd, ow, lic, ctx) in expected_lb.items():
            rec = by_id[mid]
            self.assertEqual(rec["display_name"], disp)
            self.assertEqual(rec["release_date"], rd)
            self.assertEqual(rec["is_open_weights"], ow)
            self.assertEqual(rec["license"], lic)
            self.assertEqual(rec["context_window"], ctx)

        # Unpriced "--" AA models never fabricate $0.90/1M or 85.0 t/s, and carry verified release dates + licenses
        unpriced_aa = {
            "nanbeige4-3-33b": ("2026-10-24", True, "Apache-2.0"),
            "china-mobile-jt-4-1-flash-236b-a21b": ("2026-07-09", False, "Proprietary"),
            "lg-ai-research-k-exaone-2-0": ("2026-07-31", True, "Apache-2.0"),
            "ibm-granite-4-2-3b": ("2026-08-25", True, "Apache-2.0"),
            "nvidia-nemotron-3-nano-4b": ("2026-03-16", True, "NVIDIA Open"),
        }
        for mid, (rd, ow, lic) in unpriced_aa.items():
            rec = by_id[mid]
            self.assertEqual(rec["release_date"], rd)
            self.assertEqual(rec["is_open_weights"], ow)
            self.assertEqual(rec["license"], lic)
            if raw_aa_by_cid.get(mid, {}).get("blended_price_per_1m") is None:
                self.assertIsNone(rec["pricing"]["blended_per_1m_usd"])
            if raw_aa_by_cid.get(mid, {}).get("output_tokens_per_second") is None:
                self.assertIsNone(rec["performance"]["output_tokens_per_sec"])

        # AA-scraped priced models carry verified dates, licenses, and never fabricate 85.0 t/s
        aa_verified = {
            "sapiens-ai-agnes-2-5-pro-theta": ("Sapiens AI", "2026-11-07", False, "Proprietary"),
            "upstage-solar-pro-4": ("Upstage", "2026-08-06", False, "Proprietary"),
            "apodex-1-1": ("Apodex", "2026-08-30", False, "Proprietary"),
            "nvidia-nemotron-3-5-lightning": ("NVIDIA", "2026-08-11", True, "OpenMDW-1.1"),
            "ibm-granite-4-2-8b": ("IBM", "2026-08-25", True, "Apache-2.0"),
            "mistral-medium-3-5": ("Mistral AI", "2026-04-28", True, "Modified MIT"),
            "mistral-small-4": ("Mistral AI", "2026-03-16", True, "Apache-2.0"),
            "openai-gpt-oss-120b-high": ("OpenAI", "2025-08-05", True, "Apache-2.0"),
            "cohere-north-mini-code": ("Cohere", "2026-06-09", True, "Apache-2.0"),
        }
        for mid, (prov, rd, ow, lic) in aa_verified.items():
            rec = by_id[mid]
            self.assertEqual(rec["provider"], prov)
            self.assertEqual(rec["release_date"], rd)
            self.assertEqual(rec["is_open_weights"], ow)
            self.assertEqual(rec["license"], lic)
            if raw_aa_by_cid.get(mid, {}).get("output_tokens_per_second") is None:
                self.assertIsNone(rec["performance"]["output_tokens_per_sec"])

        # Open-weights sibling consistency
        for ow_mid, exp_lic in (
            ("alibaba-qwen3-8-27b-medium", "Apache-2.0"),
            ("alibaba-qwen3-8-27b-low", "Apache-2.0"),
            ("alibaba-qwen3-8-27b-non-reasoning", "Apache-2.0"),
            ("deepseek-v4-1-flash-1017-high", "MIT"),
            ("deepseek-v4-1-flash-1017-non-reasoning", "MIT"),
            ("deepseek-v4-pro-0813-non-reasoning", "MIT"),
        ):
            self.assertTrue(by_id[ow_mid]["is_open_weights"])
            self.assertEqual(by_id[ow_mid]["license"], exp_lic)


    def test_semantic_diff_ignores_volatile_timestamps(self) -> None:
        clone = copy.deepcopy(self.data)
        clone["generated_at"] = "2099-01-01T00:00:00Z"
        clone["sources_metadata"]["artificial_analysis"]["last_updated"] = "2099-01-01T00:00:00Z"
        self.assertFalse(has_substantive_changes(self.data, clone))

        clone["models"][0]["composite"]["unified_quality_score"] -= 1.5
        self.assertTrue(has_substantive_changes(self.data, clone))

    def test_historical_trends_and_changelog_exist(self) -> None:
        self.assertTrue(TRENDS_PATH.exists())
        self.assertTrue(CHANGELOG_PATH.exists())
        trends = json.loads(TRENDS_PATH.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(trends.get("timeline", [])), 4)

    def test_frontend_features_and_loading_text(self) -> None:
        app_tsx = (ROOT_DIR / "src" / "App.tsx").read_text(encoding="utf-8")
        pareto_tsx = (ROOT_DIR / "src" / "components" / "ParetoChart.tsx").read_text(encoding="utf-8")
        timeline_tsx_path = ROOT_DIR / "src" / "components" / "ReleaseTimelinePage.tsx"

        # 1. Loading screen is simple and does not hardcode "132 models"
        self.assertNotIn("132 models", app_tsx)
        self.assertIn("Loading benchmarks...", app_tsx)

        # 2. Pareto chart supports Log and Linear scale toggle
        self.assertIn("pareto-scale-log", pareto_tsx)
        self.assertIn("pareto-scale-linear", pareto_tsx)
        self.assertIn("LINEAR_X_TICKS", pareto_tsx)

        # 3. Separate Release Timeline page exists and is wired into App navigation
        self.assertTrue(timeline_tsx_path.exists())
        timeline_tsx = timeline_tsx_path.read_text(encoding="utf-8")
        self.assertIn("Model Release Timeline", timeline_tsx)
        self.assertIn("ReleaseTimelinePage", app_tsx)
        self.assertIn("nav-release-timeline", app_tsx)


if __name__ == "__main__":
    unittest.main()
