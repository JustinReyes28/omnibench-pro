"""Arena.ai (LMSYS Chatbot Arena) live leaderboard adapter."""

from __future__ import annotations
import json
import os
import re
import time
import urllib.parse
from typing import Any
from scripts.ingest.base_fetcher import BaseFetcher

_MAX_UNSEEN_ARENA_MODELS = 20
_MIN_UNSEEN_ARENA_ELO = 1470
_MAX_UNSEEN_ARENA_RANK = 50
_ARENA_FRONTIER_BAND = 60

_PRE_2026_CHECKPOINT_RE = re.compile(
    r"(?:^|[^0-9])202[345](?:[-_/]?\d{2}(?:[-_/]?\d{2})?|(?=$|[^a-z0-9]))",
    re.IGNORECASE,
)


def _is_valid_elo(val: Any) -> bool:
    try:
        num = float(val)
    except (TypeError, ValueError):
        return False
    return 500.0 <= num <= 2500.0


def _is_pre_2026_checkpoint(raw_id: str) -> bool:
    return bool(_PRE_2026_CHECKPOINT_RE.search(raw_id or ""))


class ArenaFetcher(BaseFetcher):
    source_key = "arena"
    source_name = "Arena.ai (LMSYS)"
    source_url = "https://arena.ai/leaderboard"
    model_id_field = "arena_model_id"
    archive_api_base = "https://api.wulong.dev/arena-ai-leaderboards/v1/leaderboard"
    github_archive_raw_base = "https://raw.githubusercontent.com/oolong-tea-2026/arena-ai-leaderboards/main/data"
    github_archive_api_url = "https://api.github.com/repos/oolong-tea-2026/arena-ai-leaderboards/contents/data"
    hf_rows_base = "https://datasets-server.huggingface.co/rows"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._excluded_historical: set[str] = self._load_excluded_historical_ids()

    def _load_excluded_historical_ids(self) -> set[str]:
        if not self.latest_path.exists():
            return set()
        try:
            old = json.loads(self.latest_path.read_text(encoding="utf-8"))
            raw_list = old.get("excluded_historical_ids") or []
            return {str(x).strip().lower() for x in raw_list if str(x).strip()}
        except Exception:
            return set()

    def _filter_live_models(
        self,
        models: list[dict[str, Any]],
        explicit_ranks: dict[str, int] | None = None,
    ) -> list[dict[str, Any]]:
        """Preserves all tracked/curated models while preventing historical 2023-2025 Arena backlog dumps."""
        if not models:
            return []

        existing_excluded = self._load_excluded_historical_ids()
        self._excluded_historical = set(existing_excluded)

        existing_by_key: dict[str, dict[str, Any]] = {}
        if self.latest_path.exists():
            try:
                old = json.loads(self.latest_path.read_text(encoding="utf-8"))
                for m in old.get("models", []):
                    for fk in ("arena_model_id", "display_name"):
                        val = str(m.get(fk) or "").strip().lower()
                        if val:
                            existing_by_key.setdefault(val, m)
            except Exception:
                pass

        resolver = None
        is_stealth_fn = None
        try:
            from scripts.transform.entity_resolver import EntityResolver, is_stealth_model
            resolver = EntityResolver()
            is_stealth_fn = is_stealth_model
        except Exception:
            resolver = None

        ranked = sorted(
            models,
            key=lambda m: (
                -int(m["text_elo"]),
                -int(m.get("votes") or 0),
                str(m["arena_model_id"]).lower(),
            ),
        )
        top_elo = int(ranked[0]["text_elo"]) if ranked else _MIN_UNSEEN_ARENA_ELO
        frontier_floor = max(_MIN_UNSEEN_ARENA_ELO, top_elo - _ARENA_FRONTIER_BAND)

        known_models: list[dict[str, Any]] = []
        unseen_models: list[dict[str, Any]] = []

        for global_rank, m in enumerate(ranked, start=1):
            raw_id = str(m.get("arena_model_id") or "").strip()
            key_lower = raw_id.lower()
            org = str(m.get("organization") or "Unknown")
            elo = int(m["text_elo"])

            is_known = False
            if resolver is not None:
                try:
                    _, tier, _ = resolver.resolve("arena", raw_id, org, auto_promote=False)
                    if tier != "tier3_quarantine":
                        is_known = True
                except Exception:
                    pass

            if not is_known:
                if key_lower in existing_excluded:
                    self._excluded_historical.add(key_lower)
                    continue
                if key_lower in existing_by_key:
                    old_entry = existing_by_key[key_lower]
                    old_rd = str(old_entry.get("release_date") or "")[:10]
                    if old_rd and old_rd < "2026-01-01":
                        self._excluded_historical.add(key_lower)
                        continue
                    if _is_pre_2026_checkpoint(raw_id):
                        continue
                    is_known = True

            if is_known:
                known_models.append(m)
                continue

            if is_stealth_fn is not None and is_stealth_fn(org, raw_id):
                continue

            if _is_pre_2026_checkpoint(raw_id):
                continue

            eff_rank = (explicit_ranks or {}).get(key_lower, global_rank)
            is_2026_plus = bool(re.search(r"202[6-9]", raw_id))
            if (eff_rank <= _MAX_UNSEEN_ARENA_RANK and elo >= frontier_floor) or (
                is_2026_plus and eff_rank <= 100 and elo >= 1400
            ):
                unseen_models.append(m)

        return known_models + unseen_models[:_MAX_UNSEEN_ARENA_MODELS]

    def merge_with_lkg(self, live_models: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Merges live Arena models with LKG while permanently evicting confirmed pre-2026 historical entries."""
        merged = super().merge_with_lkg(live_models)
        excluded = getattr(self, "_excluded_historical", set())
        resolver = None
        try:
            from scripts.transform.entity_resolver import EntityResolver
            resolver = EntityResolver()
        except Exception:
            resolver = None

        cleaned: list[dict[str, Any]] = []
        for item in merged:
            raw_id = str(item.get("arena_model_id") or item.get("display_name") or "").strip()
            key_lower = raw_id.lower()
            org = str(item.get("organization") or "Unknown")

            is_curated = False
            if resolver is not None and raw_id:
                try:
                    _, tier, meta = resolver.resolve("arena", raw_id, org, auto_promote=False)
                    if tier != "tier3_quarantine" and not meta.get("auto_promoted", False):
                        is_curated = True
                except Exception:
                    pass

            if not is_curated:
                rd = str(item.get("release_date") or "")[:10]
                if key_lower in excluded or _is_pre_2026_checkpoint(raw_id):
                    continue
                if rd and rd < "2026-01-01":
                    self._excluded_historical.add(key_lower)
                    continue
            cleaned.append(item)
        return cleaned

    def get_extra_meta(self) -> dict[str, Any] | None:
        excluded = getattr(self, "_excluded_historical", None)
        if excluded:
            return {"excluded_historical_ids": sorted(excluded)}
        return None

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
        return self._filter_live_models(models)

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
                    if offset > 0 and not self.offline_mode:
                        time.sleep(0.15)
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
        explicit_ranks: dict[str, int] = {}
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
            raw_rank = r.get("rank")
            if isinstance(raw_rank, (int, float)) and not isinstance(raw_rank, bool) and int(raw_rank) > 0:
                explicit_ranks[key_lower] = int(raw_rank)
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
        return self._filter_live_models(models, explicit_ranks=explicit_ranks)

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
