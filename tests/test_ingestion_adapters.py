"""Unit tests for Phase 1 Ingestion Adapters and Last-Known-Good (LKG) fallback."""

import unittest
from scripts.ingest.fetch_artificial_analysis import ArtificialAnalysisFetcher
from scripts.ingest.fetch_livebench import LiveBenchFetcher
from scripts.ingest.fetch_arena import ArenaFetcher
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


if __name__ == "__main__":
    unittest.main()
