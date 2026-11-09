"""3-Tier Cross-Benchmark Entity Resolution Engine."""

from __future__ import annotations
import difflib
import json
import re
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
ALIASES_PATH = ROOT_DIR / "data" / "registry" / "model_aliases.json"
UNMATCHED_PATH = ROOT_DIR / "data" / "registry" / "unmatched_models.json"

_DATE_SUFFIX_RE = re.compile(r"-(?:202\d{3,5}|\d{4})$")
_REASONING_TAG_RE = re.compile(r"\s*\((?:reasoning|max|high|thinking|xhigh|preview|with fallback|max with fallback|xhigh with fallback|high with fallback)\)\s*", re.IGNORECASE)
_VENDOR_PREFIX_RE = re.compile(r"^(?:openai|anthropic|google|meta|qwen|deepseek|mistral|moonshot|xai|zai|xiaomi|minimax|nvidia)[/-]", re.IGNORECASE)


def normalize_slug(raw_name: str) -> str:
    """Deterministic Tier 2 slug normalizer stripping date stamps, vendor prefixes, and generic effort tags."""
    cleaned = raw_name.strip()
    cleaned = _VENDOR_PREFIX_RE.sub("", cleaned)
    cleaned = _REASONING_TAG_RE.sub("", cleaned)
    cleaned = _DATE_SUFFIX_RE.sub("", cleaned)
    slug = re.sub(r"[^a-z0-9]+", "-", cleaned.lower()).strip("-")
    return slug


class EntityResolver:
    """Resolves heterogeneous source model names into canonical model IDs via a 3-tier pipeline."""

    def __init__(self, aliases_path: Path | None = None) -> None:
        self.aliases_path = aliases_path or ALIASES_PATH
        raw = json.loads(self.aliases_path.read_text(encoding="utf-8"))
        self.canonical_models: dict[str, dict[str, Any]] = {}
        self.exact_lookup: dict[str, dict[str, str]] = {
            "artificial_analysis": {},
            "livebench": {},
            "arena": {},
            "vals": {},
        }
        self.normalized_lookup: dict[str, str] = {}

        for entry in raw.get("models", []):
            cid = entry["canonical_id"]
            if cid in self.canonical_models:
                raise ValueError(f"Duplicate canonical_id in registry: {cid}")
            self.canonical_models[cid] = entry
            self.normalized_lookup.setdefault(normalize_slug(cid), cid)
            self.normalized_lookup.setdefault(normalize_slug(entry["display_name"]), cid)

            for src_key, alias_list in entry.get("aliases", {}).items():
                for alias in alias_list:
                    lowered = alias.strip().lower()
                    if lowered in self.exact_lookup.get(src_key, {}) and self.exact_lookup[src_key][lowered] != cid:
                        raise ValueError(f"Duplicate alias '{alias}' in source '{src_key}'")
                    self.exact_lookup.setdefault(src_key, {})[lowered] = cid
                    self.normalized_lookup.setdefault(normalize_slug(alias), cid)

        self.unmatched_queue: list[dict[str, Any]] = []

    def resolve(self, source_key: str, raw_name: str, provider: str = "Unknown") -> tuple[str, str, dict[str, Any]]:
        """Returns (canonical_id, match_tier, metadata_dict)."""
        lowered = raw_name.strip().lower()

        # Tier 1: Exact Alias Dictionary Lookup
        if lowered in self.exact_lookup.get(source_key, {}):
            cid = self.exact_lookup[source_key][lowered]
            return cid, "tier1_exact", self.canonical_models[cid]

        # Tier 2: Deterministic Slug & Regex Token Normalization
        norm_slug = normalize_slug(raw_name)
        if norm_slug in self.normalized_lookup:
            cid = self.normalized_lookup[norm_slug]
            return cid, "tier2_normalized", self.canonical_models[cid]

        # Tier 3: Fuzzy Similarity Candidate Search + Unmatched Quarantine Queue
        best_cid = None
        best_ratio = 0.0
        for cand_slug, cid in self.normalized_lookup.items():
            ratio = difflib.SequenceMatcher(None, norm_slug, cand_slug).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_cid = cid

        if best_cid and best_ratio >= 0.92:
            return best_cid, "tier2_fuzzy_high_confidence", self.canonical_models[best_cid]

        provisional_id = f"unmatched-{norm_slug}"
        quarantine_entry = {
            "provisional_id": provisional_id,
            "source_key": source_key,
            "raw_name": raw_name,
            "provider": provider,
            "normalized_slug": norm_slug,
            "closest_canonical_candidate": best_cid,
            "similarity_score": round(best_ratio, 3),
        }
        self.unmatched_queue.append(quarantine_entry)

        provisional_meta = {
            "canonical_id": provisional_id,
            "display_name": _REASONING_TAG_RE.sub("", raw_name).strip(),
            "provider": provider,
            "release_date": "2026-10-27",
            "license": "Proprietary",
            "is_open_weights": False,
            "context_window": 128000,
            "reasoning_mode": "reasoning" if "max" in lowered or "reasoning" in lowered else "standard",
            "thinking_effort": "max" if "max" in lowered else ("high" if "high" in lowered else "standard"),
        }
        return provisional_id, "tier3_quarantine", provisional_meta

    def save_unmatched_queue(self, path: Path | None = None) -> Path:
        target = path or UNMATCHED_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "unmatched_count": len(self.unmatched_queue),
            "unmatched_models": self.unmatched_queue,
        }
        target.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        return target
