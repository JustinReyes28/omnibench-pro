"""Resilient base fetcher with exponential backoff and Last-Known-Good (LKG) snapshot fallback."""

from __future__ import annotations
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


class BaseFetcher:
    """Abstract base class for upstream benchmark adapters with LKG fallback."""

    source_key: str = "base"
    source_name: str = "Base Source"
    source_url: str = "https://example.com"
    default_timeout: float = 30.0
    max_retries: int = 3
    backoff_schedule: tuple[float, ...] = (1.0, 4.0, 16.0)

    def __init__(self, raw_dir: Path | None = None, offline_mode: bool | None = None) -> None:
        self.raw_dir = (raw_dir or RAW_DATA_DIR) / self.source_key
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.latest_path = self.raw_dir / "latest.json"
        if offline_mode is None:
            offline_mode = os.environ.get("OMNIBENCH_OFFLINE", "1") == "1"
        self.offline_mode = offline_mode

    @property
    def user_agent(self) -> str:
        repo = os.environ.get("GITHUB_REPOSITORY", "omnibench/omnibench")
        return f"OmniBench-Aggregator/1.0 (+https://github.com/{repo})"

    def request_json(self, url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
        """Performs an HTTP GET with exponential backoff (1s, 4s, 16s)."""
        if self.offline_mode:
            raise ConnectionError(f"Offline mode active; skipping live HTTP GET to {url}")

        req_headers = {"User-Agent": self.user_agent, "Accept": "application/json"}
        if headers:
            req_headers.update(headers)

        last_err: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                req = urllib.request.Request(url, headers=req_headers)
                with urllib.request.urlopen(req, timeout=self.default_timeout) as resp:
                    if resp.status in (429, 502, 503, 504):
                        raise urllib.error.HTTPError(url, resp.status, "Transient upstream error", resp.headers, None)
                    payload = resp.read().decode("utf-8")
                    return json.loads(payload)
            except Exception as exc:
                last_err = exc
                wait_sec = self.backoff_schedule[min(attempt, len(self.backoff_schedule) - 1)]
                logger.warning(
                    "[%s] Attempt %d/%d failed (%s). Backing off %.1fs...",
                    self.source_key, attempt + 1, self.max_retries, exc, wait_sec
                )
                if attempt + 1 < self.max_retries and not self.offline_mode:
                    time.sleep(wait_sec)
        raise RuntimeError(f"[{self.source_key}] Exhausted {self.max_retries} retries: {last_err}")

    def load_lkg_snapshot(self) -> dict[str, Any]:
        """Loads the Last-Known-Good snapshot from disk and marks status as cached_fallback."""
        if not self.latest_path.exists():
            raise FileNotFoundError(f"No LKG snapshot found at {self.latest_path}")
        data = json.loads(self.latest_path.read_text(encoding="utf-8"))
        data["fetch_status"] = "cached_fallback"
        data["status"] = "cached_fallback"
        return data

    def save_snapshot(self, models: list[dict[str, Any]], status: str = "live", extra_meta: dict[str, Any] | None = None) -> dict[str, Any]:
        """Validates and writes the snapshot atomically to data/raw/<source>/latest.json."""
        payload: dict[str, Any] = {
            "source_key": self.source_key,
            "source_name": self.source_name,
            "source_url": self.source_url,
            "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": status,
            "fetch_status": status,
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
        """Executes live fetch with automatic Last-Known-Good fallback."""
        try:
            models = self.fetch_live_models()
            if not models:
                raise ValueError("Upstream returned 0 models")
            return self.save_snapshot(models, status="live")
        except Exception as exc:
            logger.warning("[%s] Live fetch unavailable (%s); using Last-Known-Good snapshot.", self.source_key, exc)
            return self.load_lkg_snapshot()
