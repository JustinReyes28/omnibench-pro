"""Vals.ai enterprise benchmark leaderboard adapter."""

from __future__ import annotations
from typing import Any
from scripts.ingest.base_fetcher import BaseFetcher


class ValsFetcher(BaseFetcher):
    source_key = "vals"
    source_name = "Vals.ai"
    source_url = "https://www.vals.ai/benchmarks"
    vals_endpoint = "https://www.vals.ai/api/benchmarks/vals_index"

    def fetch_live_models(self) -> list[dict[str, Any]]:
        data = self.request_json(self.vals_endpoint)
        return data.get("models", [])


if __name__ == "__main__":
    fetcher = ValsFetcher()
    result = fetcher.run()
    print(f"[vals] Status={result['fetch_status']} Models={ len(result['models']) }")
