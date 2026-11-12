"""Unit tests for Phase 1 Ingestion Adapters and Last-Known-Good (LKG) fallback."""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.ingest.fetch_artificial_analysis import ArtificialAnalysisFetcher
from scripts.ingest.fetch_arena import ArenaFetcher
from scripts.ingest.fetch_livebench import LiveBenchFetcher
from scripts.ingest.fetch_vals import ValsFetcher


class TestIngestionAdapters(unittest.TestCase):
    def test_offline_lkg_fallback_for_all_sources(self) -> None:
        adapters = [
            ArtificialAnalysisFetcher(offline_mode=True),
            LiveBenchFetcher(offline_mode=True),
            ArenaFetcher(offline_mode=True),
            ValsFetcher(offline_mode=True),
        ]
        for adapter in adapters:
            snap = adapter.run()
            self.assertEqual(snap["fetch_status"], "cached_fallback")
            self.assertGreaterEqual(len(snap["models"]), 30)
            self.assertIn("source_url", snap)
            self.assertIn("fetched_at", snap)

    def test_livebench_category_averaging_helper(self) -> None:
        sample_row = {"lcb_gen": 80.0, "code_comp": 70.0, "aime": 90.0, "amc": 82.0}
        cat_map = {"coding": ["lcb_gen", "code_comp"], "mathematics": ["aime", "amc"]}
        res = LiveBenchFetcher.compute_category_averages(sample_row, cat_map)
        self.assertEqual(res["coding"], 75.0)
        self.assertEqual(res["mathematics"], 86.0)
        self.assertEqual(res["global_average"], 80.5)

    def test_incremental_merge_preserves_existing_models(self) -> None:
        adapter = ValsFetcher(offline_mode=True)
        merged = adapter.merge_with_lkg([
            {
                "vals_model_name": "Claude Fable 5.2 (Max)",
                "provider": "Anthropic",
                "vals_index": 71.85,
                "finance_agent": 70.1,
                "legal_bench": 54.2,
                "tax_agent": 47.5,
                "vibe_code": 94.2,
                "cost_per_test_usd": 24.5,
            }
        ])
        self.assertGreaterEqual(len(merged), 139)
        self.assertEqual(merged[0]["vals_model_name"], "Claude Fable 5.2 (Max)")

    def test_arena_hf_dataset_pagination_category_filter_and_bounds(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = ArenaFetcher(raw_dir=Path(tmpdir), offline_mode=False)

            def fake_json(url: str, headers: dict | None = None):
                if "api.wulong.dev" in url or "oolong-tea-2026" in url:
                    raise RuntimeError("Upstream mirror down")
                if "config=text" in url and "offset=0" in url:
                    return {
                        "num_rows_total": 102,
                        "rows": [
                            {"row": {"model_name": "gemini-4-hydrogen", "organization": "google", "license": "Proprietary", "category": "overall", "rating": 1495.4, "rating_lower": 1488.0, "rating_upper": 1502.0, "vote_count": 12450}}
                            for _ in range(100)
                        ],
                    }
                if "config=text" in url and "offset=100" in url:
                    return {
                        "num_rows_total": 102,
                        "rows": [
                            {"row": {"model_name": "gemini-4-hydrogen", "organization": "google", "category": "coding", "rating": 1520.2, "vote_count": 4200}},
                            {"row": {"model_name": "non-elo-ips-row", "organization": "openai", "category": "overall", "rating": 0.42, "vote_count": 300}},
                        ],
                    }
                if "config=vision" in url:
                    return {
                        "num_rows_total": 1,
                        "rows": [
                            {"row": {"model_name": "gemini-4-hydrogen", "organization": "google", "category": "overall", "rating": 1475.1, "vote_count": 3100}},
                        ],
                    }
                raise AssertionError(f"Unexpected URL {url}")

            with patch.object(adapter, "request_json", side_effect=fake_json):
                models = adapter.fetch_live_models()

            self.assertEqual(len(models), 1)
            m = models[0]
            self.assertEqual(m["arena_model_id"], "gemini-4-hydrogen")
            self.assertEqual(m["text_elo"], 1495)
            self.assertEqual(m["text_ci_lower"], 1488)
            self.assertEqual(m["text_ci_upper"], 1502)
            self.assertEqual(m["coding_elo"], 1520)
            self.assertEqual(m["vision_elo"], 1475)
            self.assertEqual(m["votes"], 12450)

    def test_arena_github_archive_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = ArenaFetcher(raw_dir=Path(tmpdir), offline_mode=False)

            def fake_json(url: str, headers: dict | None = None):
                if "api.wulong.dev" in url:
                    raise RuntimeError("Down")
                if url.endswith("/latest.json"):
                    return {"date": "2026-11-12"}
                if url.endswith("/2026-11-12/text.json"):
                    return {"models": [{"model": "claude-fable-5-2", "vendor": "anthropic", "license": "Proprietary", "score": 1510.0, "ci": 5, "votes": 9000}]}
                if url.endswith("/2026-11-12/code.json"):
                    return {"models": [{"model": "claude-fable-5-2", "score": 1545.0}]}
                if url.endswith("/2026-11-12/vision.json"):
                    return {"models": [{"model": "claude-fable-5-2", "score": 1480.0}]}
                raise RuntimeError("404")

            with patch.object(adapter, "request_json", side_effect=fake_json):
                models = adapter.fetch_live_models()

            self.assertEqual(len(models), 1)
            self.assertEqual(models[0]["coding_elo"], 1545)
            self.assertEqual(models[0]["vision_elo"], 1480)

    def test_livebench_updates_release_extra_meta(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = LiveBenchFetcher(raw_dir=Path(tmpdir), offline_mode=False)

            def fake_json(url: str, headers: dict | None = None):
                if "contents/public" in url:
                    return [{"name": "table_2026_11_06.csv"}]
                return {"coding": ["lcb"], "math": ["aime"]}

            def fake_text(url: str, headers: dict | None = None, accept: str = "*/*"):
                return "model,lcb,aime\nfuture-model-x,82.0,90.0\n"

            with patch.object(adapter, "request_json", side_effect=fake_json), patch.object(
                adapter, "request_text", side_effect=fake_text
            ):
                snap = adapter.run()

            self.assertEqual(snap["fetch_status"], "live")
            self.assertEqual(snap["release"], "2026-11-06")
            self.assertEqual(snap["models"][0]["model_key"], "future-model-x")


if __name__ == "__main__":
    unittest.main()
