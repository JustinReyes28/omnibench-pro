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

        # Ensure single-source outliers never invert lab flagships in models_unified.json
        for single_outlier in (
            "zai-glm-5-2-max",
            "zai-glm-5-2",
            "xai-grok-4-20-beta-1",
            "deepseek-v4-1-flash-max",
            "meta-muse-spark",
            "google-gemini-3-1-pro",
            "anthropic-claude-fable-5-high",
        ):
            self.assertNotIn(single_outlier, by_id)

        by_lab_top: dict[str, str] = {}
        for m in models:
            by_lab_top.setdefault(m["provider"], m["id"])
        self.assertEqual(by_lab_top["Z.AI"], "zai-glm-5-3-max")
        self.assertEqual(by_lab_top["xAI"], "xai-grok-4-7-xhigh")
        self.assertEqual(by_lab_top["DeepSeek"], "deepseek-v4-1-flash-1017")
        self.assertEqual(by_lab_top["Meta"], "meta-muse-wonder-full-max")
        self.assertEqual(by_lab_top["Google"], "google-gemini-4-carbon-high")

        # Ensure shrinkage directionality avoids lifting older/low partial models above newer flagships
        self.assertGreater(by_id["openai-gpt-6-sol-max"], by_id["openai-gpt-5-5-high"])
        self.assertGreater(by_id["openai-gpt-5-5-high"], by_id["openai-gpt-5-5"])
        self.assertLess(by_id["ibm-granite-4-2-8b"], 20.0)

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
            self.assertGreaterEqual(sources_present, 2, f"Model {mid} has fewer than 2 benchmark sources")
            self.assertLessEqual(sources_present, 4, f"Model {mid} has invalid source count")
            self.assertEqual(
                m["composite"]["coverage_ratio"],
                round(sources_present / 4.0, 2),
                f"Mismatched coverage_ratio on {mid}",
            )
            self.assertFalse(m["composite"]["provisional_ranking"], f"Unexpected provisional model in unified dataset: {mid}")

            caps = m.get("capabilities")
            self.assertIsInstance(caps, dict, f"Missing 5-axis capabilities dict on {mid}")
            cap_vals = [caps.get(ax) for ax in ("coding", "reasoning", "agentic", "enterprise", "chat") if caps.get(ax) is not None]
            self.assertGreaterEqual(len(cap_vals), 1, f"Model {mid} has 0 evaluated capabilities")
            for cv in cap_vals:
                self.assertGreaterEqual(cv, 0.0, f"Negative capability score on {mid}")
                self.assertLessEqual(cv, 100.0, f"Out-of-range capability score on {mid}")

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

            if "non-reasoning" in m["display_name"].lower():
                self.assertEqual(m.get("thinking_effort"), "standard", f"Invalid effort on {mid}")

        self.assertGreaterEqual(full_telemetry_4_count, 135, "Expected >= 135 4/4 models with complete pricing and speed telemetry")

        by_id = {m["id"]: m for m in models}
        # API-verified pricing is preserved and never overwritten by HTML Cost-per-Task summary estimates
        self.assertGreater(by_id["openai-gpt-6-astra-max"]["pricing"]["blended_per_1m_usd"], 15.0)
        self.assertGreater(by_id["meta-muse-wonder-full-max"]["pricing"]["blended_per_1m_usd"], 8.0)

        # Gemini 4 Hydrogen flagship coalesces Vals + AA without orphan duplicate; (high) & (xhigh) pass >=2 gate
        self.assertNotIn("google-gemini-4-hydrogen", by_id)
        h_xhigh = by_id["google-gemini-4-hydrogen-xhigh"]
        self.assertEqual(h_xhigh["provider"], "Google")
        self.assertEqual(h_xhigh["release_date"], "2026-11-12")
        self.assertEqual(h_xhigh["thinking_effort"], "xhigh")
        self.assertGreaterEqual(h_xhigh["composite"]["sources_present"], 2)
        self.assertIsNotNone(h_xhigh["benchmarks"]["artificial_analysis"])
        self.assertIsNotNone(h_xhigh["benchmarks"]["vals"])

        h_high = by_id["google-gemini-4-hydrogen-high"]
        self.assertEqual(h_high["provider"], "Google")
        self.assertEqual(h_high["release_date"], "2026-11-12")
        self.assertGreaterEqual(h_high["composite"]["sources_present"], 2)

        # 1/4 Hydrogen effort siblings remain excluded from public leaderboard while preserved in registry
        for h_single in ("google-gemini-4-hydrogen-medium", "google-gemini-4-hydrogen-low"):
            self.assertNotIn(h_single, by_id)
            self.assertEqual(resolver.canonical_models[h_single]["release_date"], "2026-11-12")

        # Series names containing effort words must not misclassify as reasoning effort
        self.assertEqual(by_id["mistral-medium-3-5"]["thinking_effort"], "standard")
        self.assertNotIn("unmatched-stealth-nebula-v1", by_id)

        # Corroborated (>=2 source) models in published unified dataset keep exact release dates, names, and licenses
        verified_multi = {
            "xai-grok-4-3": ("Grok 4.3", "xAI", "2026-04-30", False, "Proprietary", 1000000),
            "openai-gpt-5-5": ("GPT-5.5", "OpenAI", "2026-03-10", False, "Proprietary", 1050000),
            "openai-gpt-5-5-high": ("GPT-5.5 (High)", "OpenAI", "2026-03-10", False, "Proprietary", 1050000),
            "ibm-granite-4-2-3b": ("Granite 4.2 3B", "IBM", "2026-08-25", True, "Apache-2.0", 131000),
            "ibm-granite-4-2-8b": ("Granite 4.2 8B", "IBM", "2026-08-25", True, "Apache-2.0", 131000),
            "upstage-solar-pro-4": ("Solar Pro 4", "Upstage", "2026-08-06", False, "Proprietary", 512000),
            "mistral-medium-3-5": ("Mistral Medium 3.5", "Mistral AI", "2026-04-28", True, "Modified MIT", 256000),
        }
        for mid, (disp, prov, rd, ow, lic, ctx) in verified_multi.items():
            rec = by_id[mid]
            self.assertEqual(rec["display_name"], disp)
            self.assertEqual(rec["provider"], prov)
            self.assertEqual(rec["release_date"], rd)
            self.assertEqual(rec["is_open_weights"], ow)
            self.assertEqual(rec["license"], lic)
            self.assertEqual(rec["context_window"], ctx)

        # Gated 1/4 models are excluded from models_unified.json yet keep verified metadata in EntityResolver registry
        gated_registry_checks = {
            "openai-gpt-5-2-codex": ("GPT-5.2-Codex", "OpenAI", "2025-12-18", False, "Proprietary", 400000),
            "zai-glm-5-2": ("GLM-5.2", "Z.AI", "2026-06-16", True, "MIT", 1000000),
            "moonshot-kimi-k2-7-code": ("Kimi K2.7 Code", "Moonshot AI", "2026-06-12", True, "Modified MIT", 262000),
            "xai-grok-build-0-1": ("Grok Build 0.1", "xAI", "2026-05-20", False, "Proprietary", 256000),
            "alibaba-qwen3-6-27b": ("Qwen3.6-27B", "Alibaba", "2026-04-21", True, "Apache-2.0", 262000),
            "nanbeige4-3-33b": ("Nanbeige4.3-33B", "Nanbeige", "2026-10-24", True, "Apache-2.0", 524000),
            "china-mobile-jt-4-1-flash-236b-a21b": ("JT-4.1 Flash 236B A21B", "China Mobile", "2026-07-09", False, "Proprietary", 262000),
            "lg-ai-research-k-exaone-2-0": ("K-EXAONE 2.0", "LG AI Research", "2026-07-31", True, "Apache-2.0", 262000),
            "nvidia-nemotron-3-nano-4b": ("Nemotron 3 Nano 4B", "NVIDIA", "2026-03-16", True, "NVIDIA Open", 262000),
            "sapiens-ai-agnes-2-5-pro-theta": ("Agnes 2.5 Pro Theta", "Sapiens AI", "2026-11-07", False, "Proprietary", 1000000),
            "apodex-1-1": ("Apodex 1.1", "Apodex", "2026-08-30", False, "Proprietary", 256000),
            "nvidia-nemotron-3-5-lightning": ("Nemotron 3.5 Lightning", "NVIDIA", "2026-08-11", True, "OpenMDW-1.1", 1000000),
            "mistral-small-4": ("Mistral Small 4", "Mistral AI", "2026-03-16", True, "Apache-2.0", 256000),
            "openai-gpt-oss-120b-high": ("gpt-oss-120b (high)", "OpenAI", "2025-08-05", True, "Apache-2.0", 131000),
            "cohere-north-mini-code": ("North Mini Code", "Cohere", "2026-06-09", True, "Apache-2.0", 256000),
        }
        for mid, (disp, prov, rd, ow, lic, ctx) in gated_registry_checks.items():
            self.assertNotIn(mid, by_id, f"Single-source model {mid} must be gated from models_unified.json")
            canon = resolver.canonical_models[mid]
            self.assertEqual(canon["display_name"], disp)
            self.assertEqual(canon["provider"], prov)
            self.assertEqual(canon["release_date"], rd)
            self.assertEqual(canon["is_open_weights"], ow)
            self.assertEqual(canon["license"], lic)
            self.assertEqual(canon["context_window"], ctx)

        # Open-weights sibling consistency in registry (gated 1/4 variants retain verified open-weights licenses)
        for ow_mid, exp_lic in (
            ("alibaba-qwen3-8-27b-medium", "Apache-2.0"),
            ("alibaba-qwen3-8-27b-low", "Apache-2.0"),
            ("alibaba-qwen3-8-27b-non-reasoning", "Apache-2.0"),
            ("deepseek-v4-1-flash-1017-high", "MIT"),
            ("deepseek-v4-1-flash-1017-non-reasoning", "MIT"),
            ("deepseek-v4-pro-0813-non-reasoning", "MIT"),
        ):
            self.assertNotIn(ow_mid, by_id)
            canon = resolver.canonical_models[ow_mid]
            self.assertTrue(canon["is_open_weights"])
            self.assertEqual(canon["license"], exp_lic)

        # Step 5b metadata consistency remains intact for gated Arena-only siblings so graduation is accurate
        self.assertNotIn("google-gemini-3-pro", by_id)
        for mid, exp_rd in (
            ("xai-grok-4-20-beta-1", "2026-03-09"),
            ("meta-muse-spark", "2026-04-08"),
            ("anthropic-claude-opus-4-6", "2026-02-04"),
            ("anthropic-claude-fable-5-high", "2026-06-09"),
            ("meta-muse-spark-1-2-xhigh", "2026-08-05"),
            ("google-gemini-3-1-pro", "2026-02-19"),
            ("openai-gpt-5-2-chat", "2026-02-10"),
            ("deepseek-v4-pro-high", "2026-08-13"),
            ("deepseek-v4-1-flash-max", "2026-09-10"),
        ):
            self.assertNotIn(mid, by_id)
            if mid in resolver.canonical_models:
                self.assertEqual(resolver.canonical_models[mid]["release_date"], exp_rd)

        unmatched_path = ROOT_DIR / "data" / "registry" / "unmatched_models.json"
        if unmatched_path.exists():
            unmatched_payload = json.loads(unmatched_path.read_text(encoding="utf-8"))
            self.assertLessEqual(
                int(unmatched_payload.get("unmatched_count", 0)),
                2,
                "Expected unmatched queue to stay clean (stealth baseline only)",
            )


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
