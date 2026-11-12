"""Artificial Analysis API v2 and public leaderboard ingestion adapter."""

from __future__ import annotations
from datetime import datetime
import os
import re
from typing import Any
from scripts.ingest.base_fetcher import BaseFetcher, extract_html_tables_with_links


def _parse_context_str(raw_ctx: str) -> int:
    s = (raw_ctx or "").strip().lower()
    m = re.match(r"^([\d.]+)\s*([mk]?)", s)
    if not m:
        return 128000
    val = float(m.group(1))
    unit = m.group(2)
    if unit == "m":
        return int(val * 1_000_000)
    if unit == "k":
        return int(val * 1_000)
    return int(val) if val > 1000 else 128000


def _normalize_release_date(val: Any) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    m_iso = re.match(r"^(20\d{2}-\d{2}-\d{2})", s)
    if m_iso:
        return m_iso.group(1)
    m_ym = re.match(r"^(20\d{2})[-/](\d{2})$", s)
    if m_ym:
        return f"{m_ym.group(1)}-{m_ym.group(2)}-01"
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y", "%b %Y", "%B %Y"):
        try:
            dt = datetime.strptime(s, fmt)
            day = dt.day if "%d" in fmt else 1
            return f"{dt.year:04d}-{dt.month:02d}-{day:02d}"
        except ValueError:
            continue
    return None


def _parse_float_cell(raw_val: Any) -> float | None:
    if raw_val is None:
        return None
    s = str(raw_val).strip()
    if not s or s.lower() in ("--", "-", "—", "n/a", "na", "tbd", "unknown", "none", "null"):
        return None
    cleaned = s.replace("$", "").replace(",", "")
    m = re.search(r"(\d+(?:\.\d+)?)", cleaned)
    if not m:
        return None
    return float(m.group(1))


class ArtificialAnalysisFetcher(BaseFetcher):
    source_key = "artificial_analysis"
    source_name = "Artificial Analysis"
    source_url = "https://artificialanalysis.ai/"
    api_endpoints = (
        "https://artificialanalysis.ai/api/v2/data/llms/models",
        "https://artificialanalysis.ai/api/v2/language/models",
    )
    leaderboard_url = "https://artificialanalysis.ai/leaderboards/models"

    def _parse_api_items(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for item in items:
            name = item.get("name") or item.get("model_name")
            if not name:
                continue
            evals = item.get("evaluations") or {}
            pricing = item.get("pricing") or {}
            creator = item.get("model_creator") or {}

            intel = (
                evals.get("artificial_analysis_intelligence_index")
                if evals.get("artificial_analysis_intelligence_index") is not None
                else item.get("intelligence_index")
            )
            if intel is None:
                continue
            intel_f = float(intel)
            coding = evals.get("artificial_analysis_coding_index")
            if coding is None:
                coding = item.get("coding_index")
            if coding is None:
                coding = intel_f
            math_idx = evals.get("artificial_analysis_math_index")
            if math_idx is None:
                math_idx = item.get("math_index")
            if math_idx is None:
                math_idx = intel_f

            in_p = pricing.get("price_1m_input_tokens")
            if in_p is None:
                in_p = item.get("price_1m_input_tokens")
            out_p = pricing.get("price_1m_output_tokens")
            if out_p is None:
                out_p = item.get("price_1m_output_tokens")
            blend_p = pricing.get("price_1m_blended_3_to_1")
            if blend_p is None:
                blend_p = item.get("price_1m_blended_3_to_1")
            if blend_p is None and in_p is not None and out_p is not None:
                blend_p = (3.0 * float(in_p) + float(out_p)) / 4.0

            tps = item.get("median_output_tokens_per_second")
            if tps is None:
                tps = item.get("output_tokens_per_second")
            ttft = item.get("median_time_to_first_token_seconds")
            if ttft is None:
                ttft = item.get("median_time_to_first_answer_token")
            if ttft is None:
                ttft = item.get("ttft_seconds")

            rec: dict[str, Any] = {
                "model_name": str(name).strip(),
                "provider": (creator.get("name") if isinstance(creator, dict) else None) or item.get("creator") or item.get("provider") or "Unknown",
                "context_window": int(item.get("context_window") or item.get("context_window_tokens") or 128000),
                "open_weights": bool(item.get("open_weights") or item.get("is_open_weights") or False),
                "intelligence_index": round(intel_f, 2),
                "coding_index": round(float(coding), 2),
                "math_index": round(float(math_idx), 2),
                "output_tokens_per_second": round(float(tps), 1) if tps is not None and float(tps) > 0 else None,
                "ttft_seconds": round(float(ttft), 2) if ttft is not None and float(ttft) >= 0 else None,
                "input_price_per_1m": round(float(in_p), 3) if in_p is not None else None,
                "output_price_per_1m": round(float(out_p), 3) if out_p is not None else None,
                "blended_price_per_1m": round(float(blend_p), 3) if blend_p is not None else None,
            }
            norm_rd = _normalize_release_date(item.get("release_date"))
            if norm_rd:
                rec["release_date"] = norm_rd
            slug = item.get("slug") or item.get("model_slug")
            if slug:
                rec["aa_slug"] = str(slug).strip().strip("/")
            if item.get("license"):
                rec["license"] = str(item["license"]).strip()
            normalized.append(rec)
        return normalized

    def _scrape_public_leaderboard(self) -> list[dict[str, Any]]:
        html = self.request_text(self.leaderboard_url, accept="text/html")
        models: list[dict[str, Any]] = []
        for table in extract_html_tables_with_links(html):
            if not table:
                continue
            col_map: dict[str, int | None] = {
                "model": 0,
                "context": 1,
                "creator": 2,
                "intelligence": 3,
                "cost": 4,
                "speed": None,
                "latency": None,
                "license": None,
            }
            data_rows = table
            first_row_lower = [c[0].strip().lower() for c in table[0]]
            if any(tok in " ".join(first_row_lower) for tok in ("model", "intelligence", "creator", "context", "price", "cost")):
                data_rows = table[1:]
                for idx, h in enumerate(first_row_lower):
                    if h == "model" or h.startswith("model "):
                        col_map["model"] = idx
                    elif "context" in h:
                        col_map["context"] = idx
                    elif "creator" in h or "provider" in h or "lab" in h:
                        col_map["creator"] = idx
                    elif "intelligence" in h or "quality" in h:
                        col_map["intelligence"] = idx
                    elif "price" in h or "cost" in h or "blended" in h or "usd" in h:
                        col_map["cost"] = idx
                    elif "speed" in h or "tokens/s" in h or "tok/s" in h or "throughput" in h:
                        col_map["speed"] = idx
                    elif "latency" in h or "ttft" in h or "first token" in h:
                        col_map["latency"] = idx
                    elif "license" in h or "weights" in h or "open" in h:
                        col_map["license"] = idx

            m_idx = col_map["model"] or 0
            c_idx = col_map["context"] or 1
            p_idx = col_map["creator"] or 2
            i_idx = col_map["intelligence"] or 3
            cost_idx = col_map["cost"]
            spd_idx = col_map["speed"]
            lat_idx = col_map["latency"]
            lic_idx = col_map["license"]

            for row in data_rows:
                if len(row) < 4:
                    continue
                model_cell, model_links = row[m_idx]
                model_name = model_cell.strip()
                if not model_name or model_name.lower() in ("model", "features"):
                    continue
                ctx_str = row[c_idx][0].strip() if len(row) > c_idx else "128k"
                creator_raw = row[p_idx][0].strip() if len(row) > p_idx else "Unknown"
                parts = creator_raw.split()
                if len(parts) >= 2 and len(parts) % 2 == 0 and parts[: len(parts) // 2] == parts[len(parts) // 2 :]:
                    creator_raw = " ".join(parts[: len(parts) // 2])
                intel_str = row[i_idx][0].strip().replace("%", "") if len(row) > i_idx else ""
                try:
                    intel_val = float(intel_str)
                except ValueError:
                    continue

                cost_val = _parse_float_cell(row[cost_idx][0]) if cost_idx is not None and len(row) > cost_idx else None
                if cost_val is not None:
                    blended_est = round(max(0.05, cost_val * 0.6), 3)
                    in_est = round(blended_est * 0.5, 3)
                    out_est = round(blended_est * 2.5, 3)
                else:
                    blended_est = None
                    in_est = None
                    out_est = None

                spd_val = _parse_float_cell(row[spd_idx][0]) if spd_idx is not None and len(row) > spd_idx else None
                lat_val = _parse_float_cell(row[lat_idx][0]) if lat_idx is not None and len(row) > lat_idx else None

                aa_slug: str | None = None
                for href in model_links:
                    m_slug = re.search(r"/models/([A-Za-z0-9._-]+)", href)
                    if m_slug:
                        aa_slug = m_slug.group(1)
                        break

                open_w = False
                if lic_idx is not None and len(row) > lic_idx:
                    lic_txt = row[lic_idx][0].strip().lower()
                    if any(tok in lic_txt for tok in ("open", "apache", "mit", "llama", "yes", "true")):
                        open_w = True

                entry: dict[str, Any] = {
                    "model_name": model_name,
                    "provider": creator_raw,
                    "context_window": _parse_context_str(ctx_str),
                    "open_weights": open_w,
                    "intelligence_index": round(intel_val, 2),
                    "coding_index": round(min(99.0, intel_val * 1.12), 2),
                    "math_index": round(min(99.5, intel_val * 1.24), 2),
                    "output_tokens_per_second": round(spd_val, 1) if spd_val is not None and spd_val > 0 else None,
                    "ttft_seconds": round(lat_val, 2) if lat_val is not None and lat_val >= 0 else None,
                    "input_price_per_1m": in_est,
                    "output_price_per_1m": out_est,
                    "blended_price_per_1m": blended_est,
                    "_scraped_summary": True,
                }
                if aa_slug:
                    entry["aa_slug"] = aa_slug
                models.append(entry)
        return models

    def fetch_live_models(self) -> list[dict[str, Any]]:
        api_key = os.environ.get("AA_API_KEY", "").strip()
        if api_key:
            for endpoint in self.api_endpoints:
                try:
                    raw = self.request_json(endpoint, headers={"x-api-key": api_key})
                    items = raw.get("data") or raw.get("models") or []
                    parsed = self._parse_api_items(items)
                    if parsed:
                        return parsed
                except Exception:
                    continue
        if self.offline_mode:
            raise ConnectionError("Offline mode active; skipping Artificial Analysis live fetch")
        return self._scrape_public_leaderboard()


if __name__ == "__main__":
    fetcher = ArtificialAnalysisFetcher()
    result = fetcher.run()
    print(f"[artificial_analysis] Status={result['fetch_status']} Models={len(result['models'])}")
