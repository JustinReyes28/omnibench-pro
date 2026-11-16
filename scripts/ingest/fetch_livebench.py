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
    "long agentic": "long_agentic",
    "long_agentic": "long_agentic",
    "browser": "browser",
    "research": "research",
    "design": "design",
}


def _normalize_release_iso(release: str) -> str:
    s = (release or "").strip().replace("_", "-")
    if re.match(r"^202\d{5}$", s):
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s


class LiveBenchFetcher(BaseFetcher):
    source_key = "livebench"
    source_name = "LiveBench"
    source_url = "https://livebench.ai/"
    model_id_field = "model_key"
    repo_url = "https://github.com/LiveBench/livebench.github.io"
    base_urls = (
        "https://livebench.ai",
        "https://raw.githubusercontent.com/LiveBench/livebench.github.io/main/public",
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._latest_release: str | None = None
        self._js_model_meta: dict[str, dict[str, Any]] = {}

    def get_extra_meta(self) -> dict[str, Any] | None:
        if self._latest_release:
            return {"release": self._latest_release}
        return None

    @staticmethod
    def compute_category_averages(
        row: dict[str, float],
        categories_map: dict[str, list[str]],
        weights: dict[str, float] | None = None,
    ) -> dict[str, float]:
        """Computes per-category averages across mapped subtask columns and global (weighted or unweighted) average."""
        cat_scores: dict[str, float] = {}
        for cat_name, subtasks in categories_map.items():
            vals = [float(row[sub]) for sub in subtasks if sub in row and row[sub] is not None]
            if vals:
                cat_scores[cat_name] = round(sum(vals) / len(vals), 2)
        if cat_scores:
            if weights:
                w_sum = 0.0
                w_tot = 0.0
                for cat_name, score in cat_scores.items():
                    w = float(weights.get(cat_name, 1.0))
                    if w > 0:
                        w_sum += score * w
                        w_tot += w
                if w_tot > 0:
                    cat_scores["global_average"] = round(w_sum / w_tot, 1)
                else:
                    cat_scores["global_average"] = round(sum(cat_scores.values()) / len(cat_scores), 2)
            else:
                cat_scores["global_average"] = round(sum(cat_scores.values()) / len(cat_scores), 2)
        return cat_scores

    @staticmethod
    def _parse_js_model_metadata(js_text: str) -> dict[str, dict[str, Any]]:
        meta: dict[str, dict[str, Any]] = {}
        for m in re.finditer(r'"([a-z0-9._-]+)"\s*:\s*\{([^{}]*displayName\s*:[^{}]*)\}', js_text, re.IGNORECASE):
            mkey = m.group(1).strip()
            body = m.group(2)
            info: dict[str, Any] = {}
            disp_m = re.search(r'displayName\s*:\s*"([^"]+)"', body)
            if disp_m:
                info["display_name"] = disp_m.group(1).strip()
            org_m = re.search(r'organization\s*:\s*"([^"]+)"', body)
            if org_m:
                info["provider"] = org_m.group(1).strip()
            eff_m = re.search(r'effort\s*:\s*"([^"]+)"', body)
            if eff_m:
                info["effort"] = eff_m.group(1).strip().lower()
            if re.search(r"openweight\s*:\s*(!0|true)\b", body):
                info["open_weights"] = True
            ver_m = re.search(r'version\s*:\s*"(\d{4})"', body)
            if ver_m:
                info["version"] = ver_m.group(1)
            meta[mkey.lower()] = info
        return meta

    def _discover_release_dates(self) -> list[str]:
        candidates: list[str] = []
        try:
            html = self.request_text("https://livebench.ai/", accept="text/html")
            js_paths = re.findall(r'static/js/main\.[^"\'\s>]+\.js', html or "")
            for js_rel in js_paths[:1]:
                js_url = f"https://livebench.ai/{js_rel.lstrip('/')}"
                js_text = self.request_text(js_url)
                if js_text:
                    self._js_model_meta.update(self._parse_js_model_metadata(js_text))
                    found_v2 = sorted(
                        set(re.findall(r'"(202\d(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01]))"', js_text)),
                        reverse=True,
                    )
                    for dt in found_v2[:3]:
                        if dt not in candidates:
                            candidates.append(dt)
        except Exception:
            pass
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
                for dt in found_tables[:3]:
                    if dt not in candidates:
                        candidates.append(dt)
        except Exception:
            pass
        for fallback in ("20261106", "20261025", "2026_06_25", "2026_01_08", "2025_12_23"):
            if fallback not in candidates:
                candidates.append(fallback)
        candidates.sort(key=_normalize_release_iso, reverse=True)
        return candidates

    @staticmethod
    def _parse_cost_map(cost_csv_text: str | None, subtasks: list[str]) -> dict[str, float]:
        if not cost_csv_text or "<html" in cost_csv_text[:200].lower():
            return {}
        costs: dict[str, float] = {}
        try:
            for row in csv.DictReader(io.StringIO(cost_csv_text)):
                mkey = (row.get("model") or row.get("model_key") or "").strip().lower()
                if not mkey:
                    continue
                total_cost = 0.0
                total_nq = 0.0
                for sub in subtasks:
                    c_raw = row.get(sub)
                    nq_raw = row.get(f"nq_{sub}")
                    if c_raw in (None, "", "-") or nq_raw in (None, "", "-"):
                        continue
                    try:
                        c_val = float(c_raw)
                        nq_val = float(nq_raw)
                    except ValueError:
                        continue
                    if nq_val > 0 and c_val >= 0:
                        total_cost += c_val
                        total_nq += nq_val
                if total_nq > 0:
                    costs[mkey] = round(total_cost / total_nq, 4)
        except Exception:
            return {}
        return costs

    def fetch_live_models(self) -> list[dict[str, Any]]:
        if self.offline_mode:
            raise ConnectionError("Offline mode active; skipping LiveBench live fetch")

        release_dates = self._discover_release_dates()
        for release in release_dates:
            url_pairs: list[tuple[str, str, str | None]] = []
            if re.match(r"^202\d{5}$", release):
                url_pairs.append((
                    f"https://livebench.ai/data/{release}/categories.json",
                    f"https://livebench.ai/data/{release}/table.csv",
                    f"https://livebench.ai/data/{release}/cost.csv",
                ))
            for base in self.base_urls:
                url_pairs.append((
                    f"{base}/categories_{release}.json",
                    f"{base}/table_{release}.csv",
                    None,
                ))

            for cat_url, csv_url, cost_url in url_pairs:
                try:
                    cat_raw = self.request_json(cat_url)
                    csv_text = self.request_text(csv_url, accept="text/csv")
                    if not csv_text or "<html" in csv_text[:200].lower() or not isinstance(cat_raw, dict):
                        continue
                    categories_map: dict[str, list[str]] = {}
                    weights_map: dict[str, float] = {}
                    raw_weights = cat_raw.get("_overall_weights")
                    for raw_cat, subtasks in cat_raw.items():
                        if str(raw_cat).startswith("_"):
                            continue
                        norm_cat = _CATEGORY_KEY_MAP.get(raw_cat.strip().lower(), raw_cat.strip().lower().replace(" ", "_"))
                        if isinstance(subtasks, list):
                            categories_map[norm_cat] = [str(s) for s in subtasks]
                            if isinstance(raw_weights, dict) and raw_cat in raw_weights:
                                try:
                                    weights_map[norm_cat] = float(raw_weights[raw_cat])
                                except (TypeError, ValueError):
                                    pass

                    all_subtasks = [s for sl in categories_map.values() for s in sl]
                    cost_by_key: dict[str, float] = {}
                    if cost_url:
                        try:
                            cost_text = self.request_text(cost_url, accept="text/csv")
                            cost_by_key = self._parse_cost_map(cost_text, all_subtasks)
                        except Exception:
                            cost_by_key = {}

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
                        cat_avgs = self.compute_category_averages(
                            numeric_row,
                            categories_map,
                            weights=weights_map if weights_map else None,
                        )
                        if "global_average" not in cat_avgs:
                            continue
                        g = cat_avgs["global_average"]
                        js_info = self._js_model_meta.get(model_key.lower(), {})
                        rec: dict[str, Any] = {
                            "model_key": model_key,
                            "display_name": js_info.get("display_name") or model_key,
                            "provider": js_info.get("provider") or "Unknown",
                            "global_average": g,
                            "coding": cat_avgs.get("coding", g),
                            "mathematics": cat_avgs.get("mathematics", cat_avgs.get("browser", g)),
                            "reasoning": cat_avgs.get("reasoning", g),
                            "data_analysis": cat_avgs.get("data_analysis", g),
                            "language": cat_avgs.get("language", cat_avgs.get("research", g)),
                            "instruction_following": cat_avgs.get("instruction_following", cat_avgs.get("design", g)),
                            "agentic_coding": cat_avgs.get("agentic_coding", cat_avgs.get("long_agentic", round(g * 0.85, 2))),
                            "cost_per_question_usd": cost_by_key.get(model_key.lower()),
                        }
                        if js_info.get("open_weights") is True:
                            rec["open_weights"] = True
                        models.append(rec)
                    if models:
                        self._latest_release = _normalize_release_iso(release)
                        return models
                except Exception:
                    continue
        raise RuntimeError("Could not fetch LiveBench CSV/categories from any live endpoint")


if __name__ == "__main__":
    fetcher = LiveBenchFetcher()
    result = fetcher.run()
    print(f"[livebench] Status={result['fetch_status']} Models={len(result['models'])}")
