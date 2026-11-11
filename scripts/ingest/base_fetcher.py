"""Resilient base fetcher with exponential backoff and Last-Known-Good (LKG) snapshot fallback."""

from __future__ import annotations
from html.parser import HTMLParser
import json
import logging
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("omnibench.ingest")
ROOT_DIR = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = ROOT_DIR / "data" / "raw"


class _SimpleTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._in_table = False
        self._in_row = False
        self._in_cell = False
        self._cur_table: list[list[str]] = []
        self._cur_row: list[str] = []
        self._cur_cell: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        if t == "table":
            self._in_table = True
            self._cur_table = []
        elif t == "tr" and self._in_table:
            self._in_row = True
            self._cur_row = []
        elif t in ("td", "th") and self._in_row:
            self._in_cell = True
            self._cur_cell = []

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in ("td", "th") and self._in_cell:
            self._in_cell = False
            self._cur_row.append(" ".join("".join(self._cur_cell).split()))
        elif t == "tr" and self._in_row:
            self._in_row = False
            if self._cur_row:
                self._cur_table.append(self._cur_row)
        elif t == "table" and self._in_table:
            self._in_table = False
            if self._cur_table:
                self.tables.append(self._cur_table)

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cur_cell.append(data)


def extract_html_tables(html: str) -> list[list[list[str]]]:
    """Parses HTML tables into a list of tables -> rows -> cell strings using stdlib HTMLParser."""
    parser = _SimpleTableParser()
    parser.feed(html)
    return parser.tables


class BaseFetcher:
    """Abstract base class for upstream benchmark adapters with LKG fallback and incremental merge."""

    source_key: str = "base"
    source_name: str = "Base Source"
    source_url: str = "https://example.com"
    model_id_field: str = "model_name"
    default_timeout: float = 30.0
    max_retries: int = 3
    backoff_schedule: tuple[float, ...] = (1.0, 4.0, 16.0)

    def __init__(
        self,
        raw_dir: Path | None = None,
        offline_mode: bool | None = None,
        min_refresh_interval_hours: float | None = None,
    ) -> None:
        self.raw_dir = (raw_dir or RAW_DATA_DIR) / self.source_key
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.latest_path = self.raw_dir / "latest.json"
        if offline_mode is None:
            offline_mode = os.environ.get("OMNIBENCH_OFFLINE", "1") == "1"
        self.offline_mode = offline_mode
        if min_refresh_interval_hours is None:
            min_refresh_interval_hours = float(os.environ.get("OMNIBENCH_MIN_REFRESH_HOURS", "0"))
        self.min_refresh_interval_hours = min_refresh_interval_hours

    @property
    def user_agent(self) -> str:
        repo = os.environ.get("GITHUB_REPOSITORY", "omnibench/omnibench")
        return f"OmniBench-Aggregator/1.0 (+https://github.com/{repo})"

    def is_snapshot_fresh(self) -> bool:
        """Returns True if the local LKG snapshot was fetched within min_refresh_interval_hours."""
        if self.min_refresh_interval_hours <= 0 or os.environ.get("OMNIBENCH_FORCE_REFRESH", "0") == "1":
            return False
        if not self.latest_path.exists():
            return False
        try:
            data = json.loads(self.latest_path.read_text(encoding="utf-8"))
            fetched_at = data.get("fetched_at")
            if not fetched_at:
                return False
            fetched_dt = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
            age_hours = (datetime.now(timezone.utc) - fetched_dt).total_seconds() / 3600.0
            return 0.0 <= age_hours < self.min_refresh_interval_hours
        except Exception:
            return False

    def request_text(self, url: str, headers: dict[str, str] | None = None, accept: str = "*/*") -> str:
        """Performs an HTTP GET returning decoded UTF-8 text with exponential backoff."""
        if self.offline_mode:
            raise ConnectionError(f"Offline mode active; skipping live HTTP GET to {url}")

        req_headers = {"User-Agent": self.user_agent, "Accept": accept}
        if headers:
            req_headers.update(headers)

        last_err: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                req = urllib.request.Request(url, headers=req_headers)
                with urllib.request.urlopen(req, timeout=self.default_timeout) as resp:
                    if resp.status in (429, 502, 503, 504):
                        raise urllib.error.HTTPError(url, resp.status, "Transient upstream error", resp.headers, None)
                    return resp.read().decode("utf-8", errors="replace")
            except urllib.error.HTTPError as exc:
                last_err = exc
                # Do not retry deterministic 400/401/403/404/410 client errors
                if exc.code in (400, 401, 403, 404, 410):
                    break
                wait_sec = self.backoff_schedule[min(attempt, len(self.backoff_schedule) - 1)]
                logger.warning(
                    "[%s] Attempt %d/%d failed (%s). Backing off %.1fs...",
                    self.source_key, attempt + 1, self.max_retries, exc, wait_sec
                )
                if attempt + 1 < self.max_retries and not self.offline_mode:
                    time.sleep(wait_sec)
            except Exception as exc:
                last_err = exc
                if "Name or service not known" in str(exc):
                    break
                wait_sec = self.backoff_schedule[min(attempt, len(self.backoff_schedule) - 1)]
                logger.warning(
                    "[%s] Attempt %d/%d failed (%s). Backing off %.1fs...",
                    self.source_key, attempt + 1, self.max_retries, exc, wait_sec
                )
                if attempt + 1 < self.max_retries and not self.offline_mode:
                    time.sleep(wait_sec)
        raise RuntimeError(f"[{self.source_key}] HTTP GET failed for {url}: {last_err}")

    def request_json(self, url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
        """Performs an HTTP GET and parses JSON response."""
        payload = self.request_text(url, headers=headers, accept="application/json")
        return json.loads(payload)

    def load_lkg_snapshot(self) -> dict[str, Any]:
        """Loads the Last-Known-Good snapshot from disk and marks status as cached_fallback."""
        if not self.latest_path.exists():
            raise FileNotFoundError(f"No LKG snapshot found at {self.latest_path}")
        data = json.loads(self.latest_path.read_text(encoding="utf-8"))
        data["fetch_status"] = "cached_fallback"
        data["status"] = "cached_fallback"
        return data

    def merge_with_lkg(self, live_models: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Merges newly fetched models with the existing LKG snapshot so partial upstream responses never drop existing models."""
        if not self.latest_path.exists():
            cleaned: list[dict[str, Any]] = []
            for m in live_models:
                c = dict(m)
                c.pop("_scraped_summary", None)
                cleaned.append(c)
            return cleaned
        try:
            existing_data = json.loads(self.latest_path.read_text(encoding="utf-8"))
            existing_models: list[dict[str, Any]] = existing_data.get("models", [])
        except Exception:
            return live_models

        def _raw_id(item: dict[str, Any]) -> str:
            val = (
                item.get(self.model_id_field)
                or item.get("model_name")
                or item.get("model_key")
                or item.get("arena_model_id")
                or item.get("vals_model_name")
                or item.get("display_name")
                or ""
            )
            return str(val).strip()

        def _key_for(item: dict[str, Any]) -> str:
            return _raw_id(item).lower()

        resolver = None
        if self.source_key in ("artificial_analysis", "livebench", "arena", "vals"):
            try:
                from scripts.transform.entity_resolver import EntityResolver
                resolver = EntityResolver()
            except Exception:
                resolver = None

        existing_by_key = {_key_for(m): m for m in existing_models if _key_for(m)}
        existing_by_cid: dict[str, dict[str, Any]] = {}
        if resolver is not None:
            for m in existing_models:
                rid = _raw_id(m)
                if not rid:
                    continue
                cid, _, _ = resolver.resolve(self.source_key, rid, auto_promote=False)
                if not cid.startswith("unmatched-"):
                    existing_by_cid.setdefault(cid, m)

        seen_existing_keys: set[str] = set()
        seen_live_keys: set[str] = set()
        merged: list[dict[str, Any]] = []

        for item in live_models:
            rid = _raw_id(item)
            k = rid.lower()
            if not k:
                continue
            is_scraped_summary = bool(item.get("_scraped_summary"))
            clean_item = dict(item)
            clean_item.pop("_scraped_summary", None)

            matched_existing: dict[str, Any] | None = existing_by_key.get(k)
            if matched_existing is None and resolver is not None:
                cid, _, _ = resolver.resolve(self.source_key, rid, auto_promote=False)
                if not cid.startswith("unmatched-"):
                    matched_existing = existing_by_cid.get(cid)

            if matched_existing is not None:
                ex_key = _key_for(matched_existing)
                if ex_key in seen_existing_keys:
                    continue
                seen_existing_keys.add(ex_key)
                combined = dict(matched_existing)
                if is_scraped_summary:
                    for field in ("intelligence_index", "context_window"):
                        if field in clean_item and clean_item[field] is not None:
                            combined[field] = clean_item[field]
                else:
                    combined.update(clean_item)
                    if k != ex_key:
                        for id_f in (self.model_id_field, "model_name", "model_key", "arena_model_id", "vals_model_name", "display_name", "provider", "organization"):
                            if id_f in matched_existing:
                                combined[id_f] = matched_existing[id_f]
                merged.append(combined)
            else:
                if k in seen_live_keys:
                    continue
                seen_live_keys.add(k)
                merged.append(clean_item)

        for item in existing_models:
            k = _key_for(item)
            if k and k not in seen_existing_keys:
                merged.append(item)

        return merged

    def save_snapshot(self, models: list[dict[str, Any]], status: str = "live", extra_meta: dict[str, Any] | None = None) -> dict[str, Any]:
        """Validates and writes the snapshot atomically to data/raw/<source>/latest.json."""
        preserved_meta: dict[str, Any] = {}
        if self.latest_path.exists():
            try:
                old = json.loads(self.latest_path.read_text(encoding="utf-8"))
                for k in ("methodology_version", "release"):
                    if k in old:
                        preserved_meta[k] = old[k]
            except Exception:
                pass

        payload: dict[str, Any] = {
            "source_key": self.source_key,
            "source_name": self.source_name,
            "source_url": self.source_url,
            "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": status,
            "fetch_status": status,
            **preserved_meta,
            "model_count": len(models),
            "models": models,
        }
        if extra_meta:
            payload.update(extra_meta)
        serialized = json.dumps(payload, indent=2, allow_nan=False)
        self.latest_path.write_text(serialized + "\n", encoding="utf-8")
        return payload

    def fetch_live_models(self) -> list[dict[str, Any]]:
        """Implemented by concrete source adapters."""
        raise NotImplementedError

    def run(self) -> dict[str, Any]:
        """Executes live fetch with cooldown check, incremental LKG merge, and automatic LKG fallback."""
        if not self.offline_mode and self.is_snapshot_fresh():
            logger.info("[%s] Snapshot is within %.1fh cooldown window; reusing LKG snapshot.", self.source_key, self.min_refresh_interval_hours)
            return self.load_lkg_snapshot()
        try:
            live_models = self.fetch_live_models()
            if not live_models:
                raise ValueError("Upstream returned 0 models")
            merged_models = self.merge_with_lkg(live_models)
            return self.save_snapshot(merged_models, status="live")
        except Exception as exc:
            logger.warning("[%s] Live fetch unavailable (%s); using Last-Known-Good snapshot.", self.source_key, exc)
            return self.load_lkg_snapshot()
