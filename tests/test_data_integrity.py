"""Phase 3 Data Integrity & Pre-Commit Regression Gate Suite."""

import copy
import json
import unittest
from pathlib import Path
from scripts.ci.semantic_diff_check import has_substantive_changes
from scripts.transform.schema import validate_canonical_model_record

ROOT_DIR = Path(__file__).resolve().parents[1]
UNIFIED_PATH = ROOT_DIR / "public" / "data" / "models_unified.json"
TRENDS_PATH = ROOT_DIR / "public" / "data" / "historical_trends.json"
CHANGELOG_PATH = ROOT_DIR / "public" / "data" / "changelog.json"


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

        # Ensure latest Nov 2026 frontier and open-weights releases exist
        for latest_model in (
            "Claude Fable 5.2 (Max)",
            "Claude Fable 5.2 (xHigh)",
            "Claude Fable 5.2 (High)",
            "Inkling 2 Small",
            "Muse Ember (Max)",
            "Tencent Hy4",
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
