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
_WITH_FALLBACK_RE = re.compile(r"\s+with\s+fallback\b", re.IGNORECASE)
_REASONING_TAG_RE = re.compile(
    r"\s*\((?:reasoning|thinking|preview|with fallback)\)\s*",
    re.IGNORECASE,
)
_VENDOR_PREFIX_RE = re.compile(
    r"^(?:openai|anthropic|google|meta|qwen|alibaba|deepseek|mistral|moonshot|xai|zai|xiaomi|minimax|nvidia|thinking-machines|thinking_machines|tencent|cohere|allenai|microsoft|amazon|stepfun|upstage|liquid|ibm)[/-]",
    re.IGNORECASE,
)
_EFFORT_TOKENS = frozenset({"max", "xhigh", "high", "medium", "low", "minimal", "none", "standard"})

_PROVIDER_HINTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("claude", "anthropic"), "Anthropic"),
    (("gpt-", "o1-", "o3-", "o4-", "openai"), "OpenAI"),
    (("gemini", "gemma", "google"), "Google"),
    (("inkling", "thinking-machines", "thinking machines"), "Thinking Machines"),
    (("muse", "llama", "meta"), "Meta"),
    (("hy4", "hunyuan", "tencent"), "Tencent"),
    (("deepseek",), "DeepSeek"),
    (("qwen", "qwq", "alibaba"), "Alibaba"),
    (("glm", "z.ai", "zai"), "Z.AI"),
    (("mimo", "xiaomi"), "Xiaomi"),
    (("minimax",), "MiniMax"),
    (("kimi", "moonshot"), "Moonshot AI"),
    (("grok", "xai"), "xAI"),
    (("mistral", "pixtral", "codestral", "magistral"), "Mistral AI"),
    (("nemotron", "nvidia"), "NVIDIA"),
    (("step-", "step "), "StepFun"),
    (("nova", "amazon"), "Amazon"),
    (("command", "aya", "cohere"), "Cohere"),
    (("phi-", "microsoft"), "Microsoft"),
    (("solar", "upstage"), "Upstage"),
    (("falcon", "tii"), "TII"),
    (("jamba", "ai21"), "AI21 Labs"),
    (("olmo", "allenai"), "AllenAI"),
    (("granite", "ibm"), "IBM"),
    (("lfm", "liquid"), "Liquid AI"),
    (("ernie", "baidu"), "Baidu"),
    (("yi-", "01.ai"), "01.AI"),
    (("doubao", "seed-", "bytedance"), "ByteDance"),
    (("exaone",), "LG AI Research"),
    (("sonar", "r1-1776", "perplexity"), "Perplexity"),
)


def normalize_slug(raw_name: str) -> str:
    """Deterministic Tier 2 slug normalizer stripping date stamps, vendor prefixes, and generic non-effort tags."""
    cleaned = raw_name.strip()
    cleaned = _VENDOR_PREFIX_RE.sub("", cleaned)
    cleaned = _WITH_FALLBACK_RE.sub("", cleaned)
    cleaned = _REASONING_TAG_RE.sub("", cleaned)
    cleaned = _DATE_SUFFIX_RE.sub("", cleaned)
    slug = re.sub(r"[^a-z0-9]+", "-", cleaned.lower()).strip("-")
    return slug


def _slug_signature(slug: str) -> tuple[tuple[str, ...], frozenset[str]]:
    """Extracts numeric version tokens and explicit effort tokens so distinct versions/efforts never fuzzy-collide."""
    parts = slug.split("-")
    nums = tuple(re.findall(r"\d+", slug))
    efforts = frozenset(p for p in parts if p in _EFFORT_TOKENS)
    return nums, efforts


def _infer_provider(raw_name: str, provider: str) -> str:
    if provider and provider != "Unknown":
        return provider
    lowered = raw_name.lower()
    for prefixes, canonical_provider in _PROVIDER_HINTS:
        if any(tok in lowered for tok in prefixes):
            return canonical_provider
    return "Unknown"


def _infer_effort_and_mode(raw_name: str) -> tuple[str, str]:
    lowered = raw_name.lower()
    tokens = set(re.findall(r"[a-z0-9]+", lowered))
    if "xhigh" in tokens:
        return "xhigh", "reasoning"
    if "max" in tokens:
        return "max", "reasoning"
    if "high" in tokens:
        return "high", "reasoning"
    if "medium" in tokens:
        return "medium", "reasoning"
    if "low" in tokens:
        return "low", "hybrid"
    if "minimal" in tokens:
        return "minimal", "hybrid"
    if "none" in tokens:
        return "none", "non_reasoning"
    if "reasoning" in tokens or "thinking" in tokens:
        return "high", "reasoning"
    return "standard", "standard"


class EntityResolver:
    """Resolves heterogeneous source model names into canonical model IDs via a 3-tier pipeline."""

    def __init__(self, aliases_path: Path | None = None) -> None:
        self.aliases_path = aliases_path or ALIASES_PATH
        raw = json.loads(self.aliases_path.read_text(encoding="utf-8"))
        self.registry_version: str = raw.get("registry_version", "1.1.0")
        self.registry_updated_at: str = raw.get("updated_at", "2026-11-10T18:00:00Z")
        self.canonical_models: dict[str, dict[str, Any]] = {}
        self.exact_lookup: dict[str, dict[str, str]] = {
            "artificial_analysis": {},
            "livebench": {},
            "arena": {},
            "vals": {},
        }
        self.normalized_lookup: dict[str, str] = {}
        self.auto_promoted_ids: set[str] = set()

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

    def _record_alias(self, cid: str, source_key: str, raw_name: str) -> None:
        entry = self.canonical_models.get(cid)
        if not entry:
            return
        aliases = entry.setdefault(
            "aliases",
            {"artificial_analysis": [], "livebench": [], "arena": [], "vals": []},
        )
        src_list = aliases.setdefault(source_key, [])
        if raw_name not in src_list:
            src_list.append(raw_name)

    def resolve(
        self,
        source_key: str,
        raw_name: str,
        provider: str = "Unknown",
        auto_promote: bool = False,
    ) -> tuple[str, str, dict[str, Any]]:
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
            if cid in self.auto_promoted_ids:
                self._record_alias(cid, source_key, raw_name)
            return cid, "tier2_normalized", self.canonical_models[cid]

        # Tier 3: Fuzzy Similarity Candidate Search (guarded by numeric version & effort signature)
        norm_sig = _slug_signature(norm_slug)
        best_cid = None
        best_ratio = 0.0
        for cand_slug, cid in self.normalized_lookup.items():
            if _slug_signature(cand_slug) != norm_sig:
                continue
            ratio = difflib.SequenceMatcher(None, norm_slug, cand_slug).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_cid = cid

        if best_cid and best_ratio >= 0.92:
            if best_cid in self.auto_promoted_ids:
                self._record_alias(best_cid, source_key, raw_name)
            return best_cid, "tier2_fuzzy_high_confidence", self.canonical_models[best_cid]

        inferred_provider = _infer_provider(raw_name, provider)
        effort, reasoning_mode = _infer_effort_and_mode(raw_name)
        clean_display = _REASONING_TAG_RE.sub("", _WITH_FALLBACK_RE.sub("", raw_name)).strip()

        if auto_promote:
            effective_provider = inferred_provider
            if effective_provider == "Unknown":
                first_word = re.sub(r"[^A-Za-z0-9]+", "", (clean_display.split() or ["Independent"])[0])
                effective_provider = first_word.capitalize() if first_word else "Independent"
            prov_slug = re.sub(r"[^a-z0-9]+", "-", effective_provider.lower()).strip("-")
            auto_cid = norm_slug if norm_slug.startswith(prov_slug) else f"{prov_slug}-{norm_slug}"
            auto_meta: dict[str, Any] = {
                "canonical_id": auto_cid,
                "display_name": clean_display,
                "provider": effective_provider,
                "release_date": "2026-11-10",
                "license": "Proprietary",
                "is_open_weights": False,
                "context_window": 128000,
                "reasoning_mode": reasoning_mode,
                "thinking_effort": effort,
                "aliases": {
                    "artificial_analysis": [],
                    "livebench": [],
                    "arena": [],
                    "vals": [],
                },
            }
            auto_meta["aliases"].setdefault(source_key, []).append(raw_name)
            self.canonical_models[auto_cid] = auto_meta
            self.auto_promoted_ids.add(auto_cid)
            self.normalized_lookup.setdefault(norm_slug, auto_cid)
            self.normalized_lookup.setdefault(normalize_slug(auto_cid), auto_cid)
            self.exact_lookup.setdefault(source_key, {})[lowered] = auto_cid
            return auto_cid, "tier2_auto_promoted", auto_meta

        provisional_id = f"unmatched-{norm_slug}"
        quarantine_entry = {
            "provisional_id": provisional_id,
            "source_key": source_key,
            "raw_name": raw_name,
            "provider": inferred_provider,
            "normalized_slug": norm_slug,
            "closest_canonical_candidate": best_cid,
            "similarity_score": round(best_ratio, 3),
        }
        self.unmatched_queue.append(quarantine_entry)

        provisional_meta = {
            "canonical_id": provisional_id,
            "display_name": clean_display,
            "provider": inferred_provider,
            "release_date": "2026-11-09",
            "license": "Proprietary",
            "is_open_weights": False,
            "context_window": 128000,
            "reasoning_mode": reasoning_mode,
            "thinking_effort": effort,
        }
        return provisional_id, "tier3_quarantine", provisional_meta

    def save_registry(self, path: Path | None = None) -> bool:
        """Persists newly auto-promoted canonical models back to model_aliases.json."""
        if not self.auto_promoted_ids:
            return False
        target = path or self.aliases_path
        payload = {
            "registry_version": self.registry_version,
            "updated_at": self.registry_updated_at,
            "models": list(self.canonical_models.values()),
        }
        target.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        return True

    def save_unmatched_queue(self, path: Path | None = None) -> Path:
        target = path or UNMATCHED_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "unmatched_count": len(self.unmatched_queue),
            "unmatched_models": self.unmatched_queue,
        }
        target.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        return target
