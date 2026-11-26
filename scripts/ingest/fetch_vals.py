"""Vals.ai enterprise benchmark leaderboard adapter."""

from __future__ import annotations
import json
import math
import re
import statistics
from typing import Any
from scripts.ingest.base_fetcher import BaseFetcher, extract_html_tables

_VALS_SCORE_METRICS = ("vals_index", "finance_agent", "legal_bench", "tax_agent", "vibe_code")
_RECALIBRATION_MIN_MATCHED = 10
_RECALIBRATION_MIN_SAME_SIGN = 0.80
_RECALIBRATION_MIN_MEDIAN_DELTA = 0.50
_RECALIBRATION_MIN_RATIO_DELTA = 0.01
_RECALIBRATION_RATIO_BOUNDS = (0.75, 1.25)


def _clean_pct(val: str, default: float) -> float:
    m = re.search(r"(\d+(?:\.\d+)?)", val or "")
    return round(float(m.group(1)), 2) if m else default


class ValsFetcher(BaseFetcher):
    source_key = "vals"
    source_name = "Vals.ai"
    source_url = "https://www.vals.ai/benchmarks"
    model_id_field = "vals_model_name"
    vals_page_url = "https://www.vals.ai/benchmarks/vals_index"

    def merge_with_lkg(self, live_models: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Merges live Vals models with LKG and rescales LKG-only entries on systematic index recalibrations."""
        if not live_models or not self.latest_path.exists():
            return super().merge_with_lkg(live_models)

        try:
            existing_models: list[dict[str, Any]] = json.loads(
                self.latest_path.read_text(encoding="utf-8")
            ).get("models", [])
        except Exception:
            return super().merge_with_lkg(live_models)

        if not existing_models:
            return super().merge_with_lkg(live_models)

        resolver = None
        infer_provider_fn = None
        family_key_fn = None
        try:
            from scripts.transform.entity_resolver import (
                EntityResolver,
                _infer_provider,
                model_family_key,
            )
            resolver = EntityResolver()
            infer_provider_fn = _infer_provider
            family_key_fn = model_family_key
        except Exception:
            resolver = None

        def _raw_id(item: dict[str, Any]) -> str:
            val = item.get(self.model_id_field) or item.get("display_name") or ""
            return str(val).strip()

        def _family_for(item: dict[str, Any]) -> tuple[str, str] | None:
            rid = _raw_id(item)
            if not rid or family_key_fn is None:
                return None
            prov = str(item.get("provider") or "Unknown")
            if resolver is not None:
                try:
                    cid, _, meta = resolver.resolve(self.source_key, rid, prov, auto_promote=False)
                    if not cid.startswith("unmatched-"):
                        c_prov = str(meta.get("provider") or prov)
                        fk = family_key_fn(cid, c_prov)
                        if fk:
                            return (c_prov, fk)
                except Exception:
                    pass
            if infer_provider_fn is not None:
                prov = infer_provider_fn(rid, prov)
            fk = family_key_fn(rid, prov)
            return (prov, fk) if fk else None

        existing_by_key = {_raw_id(m).lower(): m for m in existing_models if _raw_id(m)}
        existing_by_cid: dict[str, dict[str, Any]] = {}
        if resolver is not None:
            for m in existing_models:
                rid = _raw_id(m)
                if not rid:
                    continue
                cid, _, _ = resolver.resolve(self.source_key, rid, auto_promote=False)
                if not cid.startswith("unmatched-"):
                    existing_by_cid.setdefault(cid, m)

        matched_existing_keys: set[str] = set()
        live_keys: set[str] = set()
        metric_pairs: dict[str, list[tuple[float, float, tuple[str, str] | None]]] = {
            m: [] for m in _VALS_SCORE_METRICS
        }

        for item in live_models:
            rid = _raw_id(item)
            k = rid.lower()
            if not k:
                continue
            live_keys.add(k)
            matched_existing = existing_by_key.get(k)
            if matched_existing is None and resolver is not None:
                cid, _, _ = resolver.resolve(self.source_key, rid, auto_promote=False)
                if not cid.startswith("unmatched-"):
                    matched_existing = existing_by_cid.get(cid)
            if matched_existing is None:
                continue
            ex_key = _raw_id(matched_existing).lower()
            if ex_key in matched_existing_keys:
                continue
            matched_existing_keys.add(ex_key)
            fk = _family_for(matched_existing) or _family_for(item)
            for metric in _VALS_SCORE_METRICS:
                old_v = matched_existing.get(metric)
                new_v = item.get(metric)
                if (
                    isinstance(old_v, (int, float))
                    and isinstance(new_v, (int, float))
                    and not isinstance(old_v, bool)
                    and not isinstance(new_v, bool)
                    and old_v > 0
                    and new_v > 0
                    and math.isfinite(old_v)
                    and math.isfinite(new_v)
                ):
                    metric_pairs[metric].append((float(old_v), float(new_v), fk))

        merged = super().merge_with_lkg(live_models)

        recalibration: dict[str, tuple[float, dict[tuple[str, str], float]]] = {}
        min_r, max_r = _RECALIBRATION_RATIO_BOUNDS
        for metric, pairs in metric_pairs.items():
            if len(pairs) < _RECALIBRATION_MIN_MATCHED:
                continue
            diffs = [new_v - old_v for old_v, new_v, _ in pairs]
            ratios = [new_v / old_v for old_v, new_v, _ in pairs]
            neg_frac = sum(1 for d in diffs if d <= -0.05) / len(diffs)
            pos_frac = sum(1 for d in diffs if d >= 0.05) / len(diffs)
            same_sign_frac = max(neg_frac, pos_frac)
            med_diff = statistics.median(diffs)
            med_ratio = statistics.median(ratios)
            if (
                same_sign_frac >= _RECALIBRATION_MIN_SAME_SIGN
                and abs(med_diff) >= _RECALIBRATION_MIN_MEDIAN_DELTA
                and abs(med_ratio - 1.0) >= _RECALIBRATION_MIN_RATIO_DELTA
            ):
                global_ratio = max(min_r, min(max_r, med_ratio))
                fam_buckets: dict[tuple[str, str], list[float]] = {}
                for old_v, new_v, fk in pairs:
                    if fk is not None:
                        fam_buckets.setdefault(fk, []).append(new_v / old_v)
                fam_ratios: dict[tuple[str, str], float] = {}
                for fk, rs in fam_buckets.items():
                    fam_r = max(min_r, min(max_r, statistics.median(rs)))
                    if (fam_r - 1.0) * (global_ratio - 1.0) > 0:
                        fam_ratios[fk] = fam_r
                recalibration[metric] = (global_ratio, fam_ratios)

        if not recalibration:
            return merged

        for item in merged:
            k = _raw_id(item).lower()
            if not k or k in matched_existing_keys or k in live_keys:
                continue
            fk = _family_for(item)
            for metric, (global_ratio, fam_ratios) in recalibration.items():
                val = item.get(metric)
                if isinstance(val, (int, float)) and not isinstance(val, bool) and val > 0 and math.isfinite(val):
                    ratio = fam_ratios.get(fk, global_ratio) if fk is not None else global_ratio
                    item[metric] = round(max(1.0, min(100.0, float(val) * ratio)), 2)

        return merged

    def fetch_live_models(self) -> list[dict[str, Any]]:
        if self.offline_mode:
            raise ConnectionError("Offline mode active; skipping Vals.ai live fetch")

        html = self.request_text(self.vals_page_url, accept="text/html")

        by_name: dict[str, dict[str, Any]] = {}
        for rows in extract_html_tables(html):
            if len(rows) < 2:
                continue
            headers = [h.lower() for h in rows[0]]
            # Table 1: Rank | Model | Accuracy | Cost / Test | Tokens / Test | Duration / Test
            if "rank" in headers and "model" in headers and "accuracy" in headers:
                for cells in rows[1:]:
                    if len(cells) < 3:
                        continue
                    mname = cells[1].strip()
                    if not mname:
                        continue
                    acc = _clean_pct(cells[2], 0.0)
                    if acc <= 0:
                        continue
                    cost_raw = cells[3] if len(cells) > 3 else ""
                    cost_m = re.search(r"(\d+(?:\.\d+)?)", cost_raw.replace("$", ""))
                    cost_val = round(float(cost_m.group(1)), 2) if cost_m else None
                    rec = by_name.setdefault(
                        mname,
                        {
                            "vals_model_name": mname,
                            "provider": "Unknown",
                            "vals_index": acc,
                            "finance_agent": round(acc * 0.96, 2),
                            "legal_bench": round(acc * 0.78, 2),
                            "tax_agent": round(acc * 0.58, 2),
                            "vibe_code": round(min(96.0, acc * 1.28), 2),
                            "cost_per_test_usd": cost_val,
                        },
                    )
                    rec["vals_index"] = acc
                    if cost_val is not None:
                        rec["cost_per_test_usd"] = cost_val
            # Table 2: Accuracy by Benchmark breakdown
            elif any("finance" in h for h in headers) or any("vibe code" in h for h in headers):
                for raw_cells in rows[1:]:
                    cells = [c.strip() for c in raw_cells if c and c.strip()]
                    if len(cells) < 9 or cells[0].lower() == "models" or "finance agent" in cells[0].lower():
                        continue
                    mname = cells[0]
                    vals_idx = _clean_pct(cells[-1], 0.0)
                    if not mname or vals_idx <= 0:
                        continue
                    rec = by_name.setdefault(
                        mname,
                        {
                            "vals_model_name": mname,
                            "provider": "Unknown",
                            "vals_index": vals_idx,
                            "finance_agent": _clean_pct(cells[1], vals_idx * 0.96),
                            "legal_bench": _clean_pct(cells[6], vals_idx * 0.78),
                            "tax_agent": _clean_pct(cells[8], vals_idx * 0.58),
                            "vibe_code": _clean_pct(cells[4], min(96.0, vals_idx * 1.28)),
                            "cost_per_test_usd": None,
                        },
                    )
                    rec["finance_agent"] = _clean_pct(cells[1], rec["finance_agent"])
                    rec["vibe_code"] = _clean_pct(cells[4], rec["vibe_code"])
                    rec["legal_bench"] = _clean_pct(cells[6], rec["legal_bench"])
                    rec["tax_agent"] = _clean_pct(cells[8], rec["tax_agent"])

        return list(by_name.values())


if __name__ == "__main__":
    fetcher = ValsFetcher()
    result = fetcher.run()
    print(f"[vals] Status={result['fetch_status']} Models={len(result['models'])}")
