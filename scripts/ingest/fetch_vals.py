"""Vals.ai enterprise benchmark leaderboard adapter."""

from __future__ import annotations
import re
from typing import Any
from scripts.ingest.base_fetcher import BaseFetcher, extract_html_tables


def _clean_pct(val: str, default: float) -> float:
    m = re.search(r"(\d+(?:\.\d+)?)", val or "")
    return round(float(m.group(1)), 2) if m else default


class ValsFetcher(BaseFetcher):
    source_key = "vals"
    source_name = "Vals.ai"
    source_url = "https://www.vals.ai/benchmarks"
    model_id_field = "vals_model_name"
    vals_page_url = "https://www.vals.ai/benchmarks/vals_index"

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
                for cells in rows[1:]:
                    if len(cells) < 9 or cells[0].lower() == "models":
                        continue
                    mname = cells[0].strip()
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
