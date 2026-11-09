"""Arena.ai (LMSYS Chatbot Arena) Hugging Face leaderboard adapter."""

from __future__ import annotations
import os
from typing import Any
from scripts.ingest.base_fetcher import BaseFetcher


class ArenaFetcher(BaseFetcher):
    source_key = "arena"
    source_name = "Arena.ai (LMSYS)"
    source_url = "https://arena.ai/leaderboard"
    hf_endpoint = "https://huggingface.co/api/spaces/lmarena-ai/arena-leaderboard"

    def fetch_live_models(self) -> list[dict[str, Any]]:
        headers: dict[str, str] = {}
        hf_token = os.environ.get("HF_TOKEN", "").strip()
        if hf_token:
            headers["Authorization"] = f"Bearer {hf_token}"
        data = self.request_json(self.hf_endpoint, headers=headers)
        return data.get("models", [])


if __name__ == "__main__":
    fetcher = ArenaFetcher()
    result = fetcher.run()
    print(f"[arena] Status={result['fetch_status']} Models={ len(result['models']) }")
