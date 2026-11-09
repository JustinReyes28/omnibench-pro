"""Artificial Analysis API v2 ingestion adapter."""

from __future__ import annotations
import os
from typing import Any
from scripts.ingest.base_fetcher import BaseFetcher


class ArtificialAnalysisFetcher(BaseFetcher):
    source_key = "artificial_analysis"
    source_name = "Artificial Analysis"
    source_url = "https://artificialanalysis.ai/"
    api_endpoint = "https://artificialanalysis.ai/api/v2/models"

    def fetch_live_models(self) -> list[dict[str, Any]]:
        api_key = os.environ.get("AA_API_KEY", "").strip()
        if not api_key:
            raise PermissionError("AA_API_KEY environment variable is not set; falling back to LKG snapshot")
        raw = self.request_json(self.api_endpoint, headers={"x-api-key": api_key})
        items = raw.get("data") or raw.get("models") or []
        normalized: list[dict[str, Any]] = []
        for item in items:
            normalized.append({
                "model_name": item.get("name") or item.get("model_name"),
                "provider": item.get("creator") or item.get("provider"),
                "context_window": int(item.get("context_window", 128000)),
                "open_weights": bool(item.get("open_weights", False)),
                "intelligence_index": float(item["intelligence_index"]),
                "coding_index": float(item.get("coding_index", item["intelligence_index"])),
                "math_index": float(item.get("math_index", item["intelligence_index"])),
                "output_tokens_per_second": float(item.get("median_output_tokens_per_second", 50.0)),
                "ttft_seconds": float(item.get("median_time_to_first_token_seconds", 1.0)),
                "input_price_per_1m": float(item.get("price_1m_input_tokens", 1.0)),
                "output_price_per_1m": float(item.get("price_1m_output_tokens", 3.0)),
                "blended_price_per_1m": float(item.get("price_1m_blended_3_to_1", 1.5)),
            })
        return normalized


if __name__ == "__main__":
    fetcher = ArtificialAnalysisFetcher()
    result = fetcher.run()
    print(f"[artificial_analysis] Status={result['fetch_status']} Models={ len(result['models']) }")
