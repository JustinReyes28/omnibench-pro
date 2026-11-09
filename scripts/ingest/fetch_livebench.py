"""LiveBench public GitHub CSV/JSON ingestion adapter."""

from __future__ import annotations
from typing import Any
from scripts.ingest.base_fetcher import BaseFetcher


class LiveBenchFetcher(BaseFetcher):
    source_key = "livebench"
    source_name = "LiveBench"
    source_url = "https://livebench.ai/"
    repo_url = "https://github.com/LiveBench/new-livebench"

    @staticmethod
    def compute_category_averages(
        row: dict[str, float], categories_map: dict[str, list[str]]
    ) -> dict[str, float]:
        """Computes per-category averages across mapped subtask columns and global unweighted average."""
        cat_scores: dict[str, float] = {}
        for cat_name, subtasks in categories_map.items():
            vals = [float(row[sub]) for sub in subtasks if sub in row and row[sub] is not None]
            if vals:
                cat_scores[cat_name] = round(sum(vals) / len(vals), 2)
        if cat_scores:
            cat_scores["global_average"] = round(sum(cat_scores.values()) / len(cat_scores), 2)
        return cat_scores

    def fetch_live_models(self) -> list[dict[str, Any]]:
        data = self.request_json("https://raw.githubusercontent.com/LiveBench/new-livebench/main/public/latest.json")
        return data.get("models", [])


if __name__ == "__main__":
    fetcher = LiveBenchFetcher()
    result = fetcher.run()
    print(f"[livebench] Status={result['fetch_status']} Models={ len(result['models']) }")
