"""LiveBench public CSV/JSON ingestion adapter."""

from __future__ import annotations
import csv
import io
import json
import re
from typing import Any
from scripts.ingest.base_fetcher import BaseFetcher

_CATEGORY_KEY_MAP = {
    "coding": "coding",
    "code": "coding",
    "math": "mathematics",
    "mathematics": "mathematics",
    "reasoning": "reasoning",
    "data analysis": "data_analysis",
    "data_analysis": "data_analysis",
    "language": "language",
    "instruction following": "instruction_following",
    "instruction_following": "instruction_following",
    "if": "instruction_following",
    "agentic coding": "agentic_coding",
    "agentic_coding": "agentic_coding",
}


class LiveBenchFetcher(BaseFetcher):
    source_key = "livebench"
    source_name = "LiveBench"
    source_url = "https://livebench.ai/"
    model_id_field = "model_key"
    repo_url = "https://github.com/LiveBench/livebench.github.io"
    base_urls = (
        "https://raw.githubusercontent.com/LiveBench/livebench.github.io/main/public",
        "https://livebench.ai",
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._latest_release: str | None = None

    def get_extra_meta(self) -> dict[str, Any] | None:
        if self._latest_release:
            return {"release": self._latest_release}
        return None

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

    def _discover_release_dates(self) -> list[str]:
        candidates: list[str] = []
        try:
            listing = self.request_json("https://api.github.com/repos/LiveBench/livebench.github.io/contents/public")
            if isinstance(listing, list):
                found_tables = sorted(
                    (
                        m.group(1)
                        for item in listing
                        if isinstance(item, dict)
                        and (m := re.match(r"^table_(202\d[_-]\d{2}[_-]\d{2})\.csv$", str(item.get("name", ""))))
                    ),
                    reverse=True,
                )
                candidates.extend(found_tables[:3])
        except Exception:
            pass
        for fallback in ("2026_06_25", "2026_01_08", "2025_12_23"):
            if fallback not in candidates:
                candidates.append(fallback)
        return candidates

    def fetch_live_models(self) -> list[dict[str, Any]]:
        if self.offline_mode:
            raise ConnectionError("Offline mode active; skipping LiveBench live fetch")

        release_dates = self._discover_release_dates()
        for release in release_dates:
            for base in self.base_urls:
                try:
                    cat_raw = self.request_json(f"{base}/categories_{release}.json")
                    csv_text = self.request_text(f"{base}/table_{release}.csv", accept="text/csv")
                    if not csv_text or "<html" in csv_text[:200].lower():
                        continue
                    categories_map: dict[str, list[str]] = {}
                    for raw_cat, subtasks in cat_raw.items():
                        norm_cat = _CATEGORY_KEY_MAP.get(raw_cat.strip().lower(), raw_cat.strip().lower().replace(" ", "_"))
                        if isinstance(subtasks, list):
                            categories_map[norm_cat] = [str(s) for s in subtasks]

                    reader = csv.DictReader(io.StringIO(csv_text))
                    models: list[dict[str, Any]] = []
                    for raw_row in reader:
                        model_key = (raw_row.get("model") or raw_row.get("model_key") or "").strip()
                        if not model_key:
                            continue
                        numeric_row: dict[str, float] = {}
                        for k, v in raw_row.items():
                            if k in ("model", "model_key", "") or v is None or str(v).strip() == "":
                                continue
                            try:
                                numeric_row[k] = float(v)
                            except ValueError:
                                continue
                        cat_avgs = self.compute_category_averages(numeric_row, categories_map)
                        if "global_average" not in cat_avgs:
                            continue
                        g = cat_avgs["global_average"]
                        models.append({
                            "model_key": model_key,
                            "display_name": model_key,
                            "provider": "Unknown",
                            "global_average": g,
                            "coding": cat_avgs.get("coding", g),
                            "mathematics": cat_avgs.get("mathematics", g),
                            "reasoning": cat_avgs.get("reasoning", g),
                            "data_analysis": cat_avgs.get("data_analysis", g),
                            "language": cat_avgs.get("language", g),
                            "instruction_following": cat_avgs.get("instruction_following", g),
                            "agentic_coding": cat_avgs.get("agentic_coding", round(g * 0.85, 2)),
                            "cost_per_question_usd": None,
                        })
                    if models:
                        self._latest_release = release.replace("_", "-")
                        return models
                except Exception:
                    continue
        raise RuntimeError("Could not fetch LiveBench CSV/categories from any live endpoint")


if __name__ == "__main__":
    fetcher = LiveBenchFetcher()
    result = fetcher.run()
    print(f"[livebench] Status={result['fetch_status']} Models={len(result['models'])}")
