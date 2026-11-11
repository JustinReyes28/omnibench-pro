"""Arena.ai (LMSYS Chatbot Arena) live leaderboard adapter."""

from __future__ import annotations
import os
from typing import Any
from scripts.ingest.base_fetcher import BaseFetcher


class ArenaFetcher(BaseFetcher):
    source_key = "arena"
    source_name = "Arena.ai (LMSYS)"
    source_url = "https://arena.ai/leaderboard"
    model_id_field = "arena_model_id"
    archive_api_base = "https://api.wulong.dev/arena-ai-leaderboards/v1/leaderboard"
    hf_dataset_url = (
        "https://datasets-server.huggingface.co/rows"
        "?dataset=lmarena-ai%2Fleaderboard-dataset&config=default&split=train&offset=0&length=100"
    )

    def _fetch_from_archive_api(self) -> list[dict[str, Any]]:
        text_data = self.request_json(f"{self.archive_api_base}?name=text")
        code_by_model: dict[str, int] = {}
        vision_by_model: dict[str, int] = {}
        try:
            code_data = self.request_json(f"{self.archive_api_base}?name=code")
            for item in code_data.get("models", []):
                mname = str(item.get("model") or "").strip().lower()
                if mname and item.get("score"):
                    code_by_model[mname] = int(round(float(item["score"])))
        except Exception:
            pass
        try:
            vis_data = self.request_json(f"{self.archive_api_base}?name=vision")
            for item in vis_data.get("models", []):
                mname = str(item.get("model") or "").strip().lower()
                if mname and item.get("score"):
                    vision_by_model[mname] = int(round(float(item["score"])))
        except Exception:
            pass

        models: list[dict[str, Any]] = []
        for item in text_data.get("models", []):
            raw_model = str(item.get("model") or "").strip()
            if not raw_model or not item.get("score"):
                continue
            key_lower = raw_model.lower()
            text_elo = int(round(float(item["score"])))
            ci = int(round(float(item.get("ci") or 6)))
            coding_elo = code_by_model.get(key_lower, text_elo)
            vision_elo = vision_by_model.get(key_lower)
            lic = str(item.get("license") or "Proprietary")
            models.append({
                "arena_model_id": raw_model,
                "display_name": raw_model,
                "organization": str(item.get("vendor") or "Unknown"),
                "license": "Proprietary" if lic.lower() == "proprietary" else lic,
                "text_elo": text_elo,
                "text_ci_lower": text_elo - ci,
                "text_ci_upper": text_elo + ci,
                "coding_elo": coding_elo,
                "vision_elo": vision_elo,
                "votes": int(item.get("votes") or 5000),
            })
        return models

    def _fetch_from_hf_dataset(self) -> list[dict[str, Any]]:
        headers: dict[str, str] = {}
        hf_token = os.environ.get("HF_TOKEN", "").strip()
        if hf_token:
            headers["Authorization"] = f"Bearer {hf_token}"
        data = self.request_json(self.hf_dataset_url, headers=headers)
        rows = data.get("rows") or []
        models: list[dict[str, Any]] = []
        for entry in rows:
            r = entry.get("row") if isinstance(entry, dict) else None
            if not isinstance(r, dict):
                continue
            name = str(r.get("model") or r.get("model_name") or r.get("key") or "").strip()
            rating = r.get("rating") or r.get("elo") or r.get("arena_score")
            if not name or rating is None:
                continue
            elo = int(round(float(rating)))
            models.append({
                "arena_model_id": name,
                "display_name": str(r.get("display_name") or name),
                "organization": str(r.get("organization") or r.get("company") or "Unknown"),
                "license": str(r.get("license") or "Proprietary"),
                "text_elo": elo,
                "text_ci_lower": elo - 6,
                "text_ci_upper": elo + 6,
                "coding_elo": int(round(float(r.get("coding_elo") or elo))),
                "vision_elo": int(round(float(r["vision_elo"]))) if r.get("vision_elo") else None,
                "votes": int(r.get("votes") or r.get("num_battles") or 5000),
            })
        return models

    def fetch_live_models(self) -> list[dict[str, Any]]:
        if self.offline_mode:
            raise ConnectionError("Offline mode active; skipping Arena live fetch")
        try:
            models = self._fetch_from_archive_api()
            if models:
                return models
        except Exception:
            pass
        return self._fetch_from_hf_dataset()


if __name__ == "__main__":
    fetcher = ArenaFetcher()
    result = fetcher.run()
    print(f"[arena] Status={result['fetch_status']} Models={len(result['models'])}")
