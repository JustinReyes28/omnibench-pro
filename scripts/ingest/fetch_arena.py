"""Arena.ai (LMSYS Chatbot Arena) live leaderboard adapter."""

from __future__ import annotations
import os
import re
import urllib.parse
from typing import Any
from scripts.ingest.base_fetcher import BaseFetcher


def _is_valid_elo(val: Any) -> bool:
    try:
        num = float(val)
    except (TypeError, ValueError):
        return False
    return 500.0 <= num <= 2500.0


class ArenaFetcher(BaseFetcher):
    source_key = "arena"
    source_name = "Arena.ai (LMSYS)"
    source_url = "https://arena.ai/leaderboard"
    model_id_field = "arena_model_id"
    archive_api_base = "https://api.wulong.dev/arena-ai-leaderboards/v1/leaderboard"
    github_archive_raw_base = "https://raw.githubusercontent.com/oolong-tea-2026/arena-ai-leaderboards/main/data"
    github_archive_api_url = "https://api.github.com/repos/oolong-tea-2026/arena-ai-leaderboards/contents/data"
    hf_rows_base = "https://datasets-server.huggingface.co/rows"

    def _parse_archive_models(
        self,
        text_data: dict[str, Any],
        code_by_model: dict[str, int],
        vision_by_model: dict[str, int],
    ) -> list[dict[str, Any]]:
        models: list[dict[str, Any]] = []
        for item in text_data.get("models", []):
            raw_model = str(item.get("model") or "").strip()
            score = item.get("score")
            if not raw_model or not _is_valid_elo(score):
                continue
            key_lower = raw_model.lower()
            text_elo = int(round(float(score)))
            ci = int(round(float(item.get("ci") or 6)))
            coding_elo = code_by_model.get(key_lower, text_elo)
            vision_elo = vision_by_model.get(key_lower)
            lic = str(item.get("license") or "Proprietary").strip() or "Proprietary"
            models.append({
                "arena_model_id": raw_model,
                "display_name": raw_model,
                "organization": str(item.get("vendor") or "Unknown"),
                "license": "Proprietary" if lic.lower() == "proprietary" else lic,
                "text_elo": text_elo,
                "text_ci_lower": max(500, text_elo - ci),
                "text_ci_upper": min(2500, text_elo + ci),
                "coding_elo": coding_elo,
                "vision_elo": vision_elo,
                "votes": int(item.get("votes") or 5000),
            })
        return models

    def _fetch_from_archive_api(self) -> list[dict[str, Any]]:
        text_data = self.request_json(f"{self.archive_api_base}?name=text")
        code_by_model: dict[str, int] = {}
        vision_by_model: dict[str, int] = {}
        try:
            code_data = self.request_json(f"{self.archive_api_base}?name=code")
            for item in code_data.get("models", []):
                mname = str(item.get("model") or "").strip().lower()
                if mname and _is_valid_elo(item.get("score")):
                    code_by_model[mname] = int(round(float(item["score"])))
        except Exception:
            pass
        try:
            vis_data = self.request_json(f"{self.archive_api_base}?name=vision")
            for item in vis_data.get("models", []):
                mname = str(item.get("model") or "").strip().lower()
                if mname and _is_valid_elo(item.get("score")):
                    vision_by_model[mname] = int(round(float(item["score"])))
        except Exception:
            pass
        return self._parse_archive_models(text_data, code_by_model, vision_by_model)

    def _discover_github_archive_dates(self) -> list[str]:
        candidates: list[str] = []
        try:
            latest_meta = self.request_json(f"{self.github_archive_raw_base}/latest.json")
            if isinstance(latest_meta, dict):
                for key in ("date", "latest", "snapshot_date", "latest_date"):
                    val = str(latest_meta.get(key) or "").strip()
                    if re.match(r"^202\d-\d{2}-\d{2}$", val) and val not in candidates:
                        candidates.append(val)
        except Exception:
            pass
        try:
            listing = self.request_json(self.github_archive_api_url)
            if isinstance(listing, list):
                dirs = sorted(
                    (
                        str(entry.get("name", "")).strip()
                        for entry in listing
                        if isinstance(entry, dict)
                        and entry.get("type") == "dir"
                        and re.match(r"^202\d-\d{2}-\d{2}$", str(entry.get("name", "")).strip())
                    ),
                    reverse=True,
                )
                for d in dirs[:3]:
                    if d not in candidates:
                        candidates.append(d)
        except Exception:
            pass
        return candidates

    def _fetch_from_github_archive(self) -> list[dict[str, Any]]:
        for snap_date in self._discover_github_archive_dates():
            try:
                text_data = self.request_json(f"{self.github_archive_raw_base}/{snap_date}/text.json")
            except Exception:
                continue
            code_by_model: dict[str, int] = {}
            vision_by_model: dict[str, int] = {}
            try:
                code_data = self.request_json(f"{self.github_archive_raw_base}/{snap_date}/code.json")
                for item in code_data.get("models", []):
                    mname = str(item.get("model") or "").strip().lower()
                    if mname and _is_valid_elo(item.get("score")):
                        code_by_model[mname] = int(round(float(item["score"])))
            except Exception:
                pass
            try:
                vis_data = self.request_json(f"{self.github_archive_raw_base}/{snap_date}/vision.json")
                for item in vis_data.get("models", []):
                    mname = str(item.get("model") or "").strip().lower()
                    if mname and _is_valid_elo(item.get("score")):
                        vision_by_model[mname] = int(round(float(item["score"])))
            except Exception:
                pass
            models = self._parse_archive_models(text_data, code_by_model, vision_by_model)
            if models:
                return models
        return []

    def _fetch_hf_config_rows(self, configs: tuple[str, ...], headers: dict[str, str]) -> list[dict[str, Any]]:
        dataset_enc = urllib.parse.quote("lmarena-ai/leaderboard-dataset", safe="")
        for cfg in configs:
            all_rows: list[dict[str, Any]] = []
            offset = 0
            page_size = 100
            total_rows: int | None = None
            try:
                while offset < 1000:
                    url = (
                        f"{self.hf_rows_base}?dataset={dataset_enc}"
                        f"&config={urllib.parse.quote(cfg, safe='')}&split=latest&offset={offset}&length={page_size}"
                    )
                    data = self.request_json(url, headers=headers)
                    batch = data.get("rows") or []
                    if not isinstance(batch, list) or not batch:
                        break
                    for entry in batch:
                        r = entry.get("row") if isinstance(entry, dict) else None
                        if isinstance(r, dict):
                            all_rows.append(r)
                    if total_rows is None and isinstance(data.get("num_rows_total"), int):
                        total_rows = data["num_rows_total"]
                    offset += len(batch)
                    if len(batch) < page_size or (total_rows is not None and offset >= total_rows):
                        break
                if all_rows:
                    return all_rows
            except Exception:
                continue
        return []

    def _fetch_from_hf_dataset(self) -> list[dict[str, Any]]:
        headers: dict[str, str] = {}
        hf_token = os.environ.get("HF_TOKEN", "").strip()
        if hf_token:
            headers["Authorization"] = f"Bearer {hf_token}"

        text_rows = self._fetch_hf_config_rows(("text", "text_style_control"), headers)
        if not text_rows:
            return []
        vision_rows = self._fetch_hf_config_rows(("vision", "vision_style_control"), headers)

        coding_by_model: dict[str, int] = {}
        vision_by_model: dict[str, int] = {}
        for r in text_rows:
            cat = str(r.get("category") or "").strip().lower()
            name = str(r.get("model_name") or r.get("model") or r.get("key") or "").strip().lower()
            rating = r.get("rating") if r.get("rating") is not None else r.get("elo")
            if cat == "coding" and name and _is_valid_elo(rating):
                coding_by_model[name] = int(round(float(rating)))
        for r in vision_rows:
            cat = str(r.get("category") or "overall").strip().lower()
            name = str(r.get("model_name") or r.get("model") or r.get("key") or "").strip().lower()
            rating = r.get("rating") if r.get("rating") is not None else r.get("elo")
            if cat == "overall" and name and _is_valid_elo(rating):
                vision_by_model[name] = int(round(float(rating)))

        models: list[dict[str, Any]] = []
        seen_names: set[str] = set()
        for r in text_rows:
            cat = str(r.get("category") or "overall").strip().lower()
            if cat != "overall":
                continue
            name = str(r.get("model_name") or r.get("model") or r.get("key") or "").strip()
            rating = r.get("rating") if r.get("rating") is not None else (r.get("elo") if r.get("elo") is not None else r.get("arena_score"))
            if not name or not _is_valid_elo(rating):
                continue
            key_lower = name.lower()
            if key_lower in seen_names:
                continue
            seen_names.add(key_lower)
            elo = int(round(float(rating)))
            ci_lo_raw = r.get("rating_lower")
            ci_hi_raw = r.get("rating_upper")
            ci_lo = int(round(float(ci_lo_raw))) if _is_valid_elo(ci_lo_raw) else max(500, elo - 6)
            ci_hi = int(round(float(ci_hi_raw))) if _is_valid_elo(ci_hi_raw) else min(2500, elo + 6)
            lic = str(r.get("license") or "Proprietary").strip() or "Proprietary"
            votes_raw = r.get("vote_count") if r.get("vote_count") is not None else (r.get("votes") if r.get("votes") is not None else r.get("num_battles"))
            models.append({
                "arena_model_id": name,
                "display_name": str(r.get("display_name") or name),
                "organization": str(r.get("organization") or r.get("company") or "Unknown"),
                "license": "Proprietary" if lic.lower() == "proprietary" else lic,
                "text_elo": elo,
                "text_ci_lower": min(ci_lo, elo),
                "text_ci_upper": max(ci_hi, elo),
                "coding_elo": coding_by_model.get(key_lower, int(round(float(r["coding_elo"]))) if _is_valid_elo(r.get("coding_elo")) else elo),
                "vision_elo": vision_by_model.get(key_lower, int(round(float(r["vision_elo"]))) if _is_valid_elo(r.get("vision_elo")) else None),
                "votes": int(votes_raw or 5000),
            })
        return models

    def fetch_live_models(self) -> list[dict[str, Any]]:
        if self.offline_mode:
            raise ConnectionError("Offline mode active; skipping Arena live fetch")
        for fetcher in (
            self._fetch_from_archive_api,
            self._fetch_from_github_archive,
            self._fetch_from_hf_dataset,
        ):
            try:
                models = fetcher()
                if models:
                    return models
            except Exception:
                continue
        raise RuntimeError("Could not fetch Arena.ai leaderboard from any live endpoint")


if __name__ == "__main__":
    fetcher = ArenaFetcher()
    result = fetcher.run()
    print(f"[arena] Status={result['fetch_status']} Models={len(result['models'])}")
