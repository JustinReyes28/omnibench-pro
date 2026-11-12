"""3-Tier Cross-Benchmark Entity Resolution Engine."""

from __future__ import annotations
from datetime import datetime, timezone
import difflib
import json
import re
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
ALIASES_PATH = ROOT_DIR / "data" / "registry" / "model_aliases.json"
UNMATCHED_PATH = ROOT_DIR / "data" / "registry" / "unmatched_models.json"

_DATE_SUFFIX_RE = re.compile(r"-(?:202\d{3,5}|\d{4})$")
_YYYYMMDD_SUFFIX_RE = re.compile(r"-202\d{3,5}$")
_INLINE_DATE_RE = re.compile(r"-(?:202\d-\d{2}-\d{2}|202\d{5})(?=-|$)")
_EFFORT_NOISE_RE = re.compile(
    r"-(?:thinking-auto|thinking-\d+k|effort|preview)(?=-|$)",
    re.IGNORECASE,
)
_WITH_FALLBACK_RE = re.compile(r"\s+with\s+fallback\b", re.IGNORECASE)
_REASONING_TAG_RE = re.compile(
    r"\s*\((?:reasoning|thinking|preview|with fallback)\)\s*",
    re.IGNORECASE,
)
_VENDOR_PREFIX_RE = re.compile(
    r"^(?:openai|anthropic|google|meta|qwen|alibaba|deepseek|mistral|moonshot|xai|zai|xiaomi|minimax|nvidia|thinking-machines|thinking_machines|tencent|cohere|allenai|microsoft|amazon|stepfun|upstage|liquid|ibm)[/-]",
    re.IGNORECASE,
)
_ORG_SLUG_PREFIX_RE = re.compile(
    r"^(?:openai|anthropic|google|meta|deepseek|xai|zai|z-ai|xiaomi|minimax|nvidia|thinking-machines|thinking_machines|tencent|cohere|allenai|microsoft|amazon|stepfun|upstage|liquid-ai|liquid|ibm|alibaba|mistral-ai|moonshot-ai|moonshot|reflection-ai|reflection|sapiens-ai|china-mobile|lg-ai-research|ai21-labs|ai21)-",
    re.IGNORECASE,
)
_EFFORT_SUFFIX_RE = re.compile(
    r"-(?:max|xhigh|high|medium|low|minimal|none|non-reasoning|standard)$"
)
_EFFORT_TOKENS = frozenset({"max", "xhigh", "high", "medium", "low", "minimal", "none", "standard"})
_STEALTH_PROVIDERS = frozenset({"stealth lab", "stealth", "anonymous", "unknown", ""})

_PROVIDER_HINTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("claude", "anthropic"), "Anthropic"),
    (("gpt-", "gpt-oss", "o1-", "o3-", "o4-", "openai", "codex"), "OpenAI"),
    (("gemini", "gemma", "google"), "Google"),
    (("inkling", "thinking-machines", "thinking machines"), "Thinking Machines"),
    (("muse", "llama", "meta", "wonder"), "Meta"),
    (("hy4", "hy3", "hunyuan", "tencent"), "Tencent"),
    (("deepseek",), "DeepSeek"),
    (("qwen", "qwq", "alibaba"), "Alibaba"),
    (("glm", "z.ai", "zai"), "Z.AI"),
    (("mimo", "xiaomi"), "Xiaomi"),
    (("minimax",), "MiniMax"),
    (("kimi", "moonshot"), "Moonshot AI"),
    (("grok", "xai"), "xAI"),
    (("mistral", "pixtral", "codestral", "magistral"), "Mistral AI"),
    (("nemotron", "nvidia"), "NVIDIA"),
    (("mercury", "inception"), "Inception"),
    (("step-", "step "), "StepFun"),
    (("nova", "amazon"), "Amazon"),
    (("command", "aya", "north ", "cohere"), "Cohere"),
    (("phi-", "microsoft"), "Microsoft"),
    (("solar", "upstage"), "Upstage"),
    (("agnes", "sapiens"), "Sapiens AI"),
    (("nanbeige",), "Nanbeige"),
    (("apodex",), "Apodex"),
    (("jt-", "china mobile"), "China Mobile"),
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

_PROVIDER_ALIASES: dict[str, str] = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google": "Google",
    "meta": "Meta",
    "deepseek": "DeepSeek",
    "alibaba": "Alibaba",
    "alibaba cloud": "Alibaba",
    "xiaomi": "Xiaomi",
    "minimax": "MiniMax",
    "tencent": "Tencent",
    "nvidia": "NVIDIA",
    "cohere": "Cohere",
    "upstage": "Upstage",
    "ibm": "IBM",
    "stepfun": "StepFun",
    "thinky": "Thinking Machines",
    "sapiens ai": "Sapiens AI",
    "china mobile": "China Mobile",
    "lg ai research": "LG AI Research",
    "nanbeige": "Nanbeige",
    "apodex": "Apodex",
    "mistral": "Mistral AI",
    "mistral ai": "Mistral AI",
    "moonshot": "Moonshot AI",
    "moonshot ai": "Moonshot AI",
    "z.ai": "Z.AI",
    "zai": "Z.AI",
    "zhipu": "Z.AI",
    "x.ai": "xAI",
    "xai": "xAI",
    "thinking machines": "Thinking Machines",
    "thinking-machines": "Thinking Machines",
    "reflection": "Reflection AI",
    "reflection ai": "Reflection AI",
    "inception": "Inception",
    "mercury": "Inception",
    "wonder": "Meta",
}

_PROVIDER_CANONICAL_PREFIX: dict[str, str] = {
    "Mistral AI": "mistral",
    "Moonshot AI": "moonshot",
    "Z.AI": "zai",
    "Thinking Machines": "thinking-machines",
    "Reflection AI": "reflection",
    "Sapiens AI": "sapiens-ai",
    "China Mobile": "china-mobile",
    "LG AI Research": "lg-ai-research",
    "Liquid AI": "liquid",
    "AI21 Labs": "ai21",
    "Alibaba": "alibaba",
}


def canonical_provider_prefix(provider: str) -> str:
    if provider in _PROVIDER_CANONICAL_PREFIX:
        return _PROVIDER_CANONICAL_PREFIX[provider]
    return re.sub(r"[^a-z0-9]+", "-", provider.lower()).strip("-")


def is_stealth_model(provider: str, raw_name: str = "") -> bool:
    prov_norm = (provider or "").strip().lower()
    if prov_norm in _STEALTH_PROVIDERS:
        return True
    lowered_name = (raw_name or "").strip().lower()
    return lowered_name.startswith(("stealth-", "stealth ", "anonymous-", "anonymous "))


def normalize_slug(raw_name: str) -> str:
    """Deterministic Tier 2 slug normalizer stripping date stamps, vendor prefixes, and generic non-effort tags."""
    cleaned = raw_name.strip()
    cleaned = _VENDOR_PREFIX_RE.sub("", cleaned)
    cleaned = _WITH_FALLBACK_RE.sub("", cleaned)
    cleaned = _REASONING_TAG_RE.sub("", cleaned)
    slug = re.sub(r"[^a-z0-9]+", "-", cleaned.lower()).strip("-")
    slug = _INLINE_DATE_RE.sub("", slug)
    slug = _EFFORT_NOISE_RE.sub("", slug)
    slug = _DATE_SUFFIX_RE.sub("", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


def model_family_key(name_or_slug: str, provider: str = "") -> str:
    """Returns a compact alphanumeric base-family key stripping provider prefixes, dates, and trailing effort tiers."""
    cleaned = _VENDOR_PREFIX_RE.sub("", (name_or_slug or "").strip())
    cleaned = _WITH_FALLBACK_RE.sub("", cleaned)
    cleaned = _REASONING_TAG_RE.sub("", cleaned)
    slug = re.sub(r"[^a-z0-9]+", "-", cleaned.lower()).strip("-")
    slug = _INLINE_DATE_RE.sub("", slug)
    slug = _EFFORT_NOISE_RE.sub("", slug)
    slug = _YYYYMMDD_SUFFIX_RE.sub("", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    slug = _EFFORT_SUFFIX_RE.sub("", slug)

    prefixes: list[str] = []
    if provider:
        prefixes.append(canonical_provider_prefix(provider))
        raw_p = re.sub(r"[^a-z0-9]+", "-", provider.lower()).strip("-")
        if raw_p not in prefixes:
            prefixes.append(raw_p)
    for pfx in prefixes:
        if pfx and slug.startswith(pfx + "-") and len(slug) > len(pfx) + 1:
            slug = slug[len(pfx) + 1 :]
            break
    else:
        stripped = _ORG_SLUG_PREFIX_RE.sub("", slug)
        if stripped:
            slug = stripped

    return re.sub(r"[^a-z0-9]", "", slug)


def _slug_signature(slug: str) -> tuple[tuple[str, ...], frozenset[str]]:
    """Extracts numeric version tokens and explicit effort tokens so distinct versions/efforts never fuzzy-collide."""
    parts = slug.split("-")
    nums = tuple(re.findall(r"\d+", slug))
    efforts = frozenset(p for p in parts if p in _EFFORT_TOKENS)
    return nums, efforts


def _infer_provider(raw_name: str, provider: str) -> str:
    if provider and provider != "Unknown":
        return _PROVIDER_ALIASES.get(provider.strip().lower(), provider.strip())
    lowered = raw_name.lower()
    for prefixes, canonical_provider in _PROVIDER_HINTS:
        if any(tok in lowered for tok in prefixes):
            return canonical_provider
    return "Unknown"


def _infer_effort_and_mode(raw_name: str) -> tuple[str, str]:
    lowered = raw_name.lower().strip()
    if re.search(r"\bnon[-_\s]?reasoning\b", lowered):
        return "standard", "non_reasoning"

    paren_tokens: set[str] = set()
    for group in re.findall(r"\(([^)]+)\)", lowered):
        paren_tokens.update(re.findall(r"[a-z0-9]+", group))

    stripped = _REASONING_TAG_RE.sub("", _WITH_FALLBACK_RE.sub("", lowered))
    stripped = re.sub(r"\([^)]*\)", "", stripped).strip()
    stripped = re.sub(r"[-_\s]+(?:202\d{3,5}|\d{4}|preview|effort|\d+k)$", "", stripped).strip()
    tail_match = re.search(r"(?:^|[-_\s])([a-z0-9]+)$", stripped)
    tail_tokens: set[str] = {tail_match.group(1)} if tail_match else set()
    if tail_tokens == {"medium"} and re.search(r"\bmistral\s+medium$", stripped):
        tail_tokens = set()

    tokens = paren_tokens | tail_tokens
    if "none" in tokens:
        return "standard", "non_reasoning"
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
    if "reasoning" in tokens or "thinking" in tokens:
        return "high", "reasoning"
    return "standard", "standard"


class EntityResolver:
    """Resolves heterogeneous source model names into canonical model IDs via a 3-tier pipeline."""

    def __init__(self, aliases_path: Path | None = None) -> None:
        self.aliases_path = aliases_path or ALIASES_PATH
        raw = json.loads(self.aliases_path.read_text(encoding="utf-8"))
        self.registry_version: str = raw.get("registry_version") or raw.get("schema_version") or "1.1.0"
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
        self.registry_dirty: bool = False

        for entry in raw.get("models", []):
            cid = entry["canonical_id"]
            if cid in self.canonical_models:
                raise ValueError(f"Duplicate canonical_id in registry: {cid}")
            self.canonical_models[cid] = entry
            self.normalized_lookup.setdefault(cid, cid)
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
        if not entry or not raw_name:
            return
        aliases = entry.setdefault(
            "aliases",
            {"artificial_analysis": [], "livebench": [], "arena": [], "vals": []},
        )
        src_list = aliases.setdefault(source_key, [])
        if raw_name not in src_list:
            src_list.append(raw_name)
            self.registry_dirty = True
        lowered = raw_name.strip().lower()
        src_exact = self.exact_lookup.setdefault(source_key, {})
        if lowered not in src_exact:
            src_exact[lowered] = cid
        self.normalized_lookup.setdefault(normalize_slug(raw_name), cid)

    def merge_and_retire_canonical(self, source_cid: str, target_cid: str) -> None:
        """Transfers aliases and lookup bindings from an untagged temporary entry to its flagship sibling."""
        src_entry = self.canonical_models.get(source_cid)
        tgt_entry = self.canonical_models.get(target_cid)
        if not src_entry or not tgt_entry or source_cid == target_cid:
            return

        for src_key, alias_list in (src_entry.get("aliases") or {}).items():
            for alias in alias_list:
                lowered = alias.strip().lower()
                if self.exact_lookup.get(src_key, {}).get(lowered) == source_cid:
                    self.exact_lookup[src_key][lowered] = target_cid
                self._record_alias(target_cid, src_key, alias)

        for src_dict in self.exact_lookup.values():
            for k, v in list(src_dict.items()):
                if v == source_cid:
                    src_dict[k] = target_cid

        for k, v in list(self.normalized_lookup.items()):
            if v == source_cid:
                self.normalized_lookup[k] = target_cid

        if src_entry.get("is_open_weights") and not tgt_entry.get("is_open_weights"):
            tgt_entry["is_open_weights"] = True
            if src_entry.get("license") and src_entry["license"] != "Proprietary":
                tgt_entry["license"] = src_entry["license"]

        self.canonical_models.pop(source_cid, None)
        self.auto_promoted_ids.discard(source_cid)
        self.registry_dirty = True

    def _infer_release_date(
        self,
        auto_cid: str,
        raw_name: str,
        provider: str = "",
        default_date: str | None = None,
    ) -> str:
        m_iso = re.search(r"(202\d-\d{2}-\d{2})", raw_name)
        if m_iso:
            return m_iso.group(1)
        m_8 = re.search(r"(202\d)(\d{2})(\d{2})", raw_name)
        if m_8:
            return f"{m_8.group(1)}-{m_8.group(2)}-{m_8.group(3)}"
        target_keys = {model_family_key(raw_name, provider), model_family_key(auto_cid, provider)} - {""}
        for cid, entry in self.canonical_models.items():
            if not entry.get("release_date"):
                continue
            if provider and entry.get("provider") and entry["provider"] != provider:
                continue
            cand_keys = {
                model_family_key(cid, entry.get("provider", "")),
                model_family_key(entry.get("display_name", ""), entry.get("provider", "")),
            }
            if target_keys & cand_keys:
                return str(entry["release_date"])
        return default_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def resolve(
        self,
        source_key: str,
        raw_name: str,
        provider: str = "Unknown",
        auto_promote: bool = False,
        default_release_date: str | None = None,
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
            if auto_promote or cid in self.auto_promoted_ids:
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
            if auto_promote or best_cid in self.auto_promoted_ids:
                self._record_alias(best_cid, source_key, raw_name)
            return best_cid, "tier2_fuzzy_high_confidence", self.canonical_models[best_cid]

        inferred_provider = _infer_provider(raw_name, provider)
        effort, reasoning_mode = _infer_effort_and_mode(raw_name)
        clean_display = _REASONING_TAG_RE.sub("", _WITH_FALLBACK_RE.sub("", raw_name)).strip()

        if auto_promote and not is_stealth_model(inferred_provider, raw_name):
            effective_provider = inferred_provider
            prov_slug = canonical_provider_prefix(effective_provider)
            auto_cid = norm_slug if norm_slug.startswith(prov_slug) else f"{prov_slug}-{norm_slug}"
            if auto_cid in self.canonical_models:
                self._record_alias(auto_cid, source_key, raw_name)
                return auto_cid, "tier2_normalized", self.canonical_models[auto_cid]
            inferred_release = self._infer_release_date(
                auto_cid,
                raw_name,
                provider=effective_provider,
                default_date=default_release_date,
            )
            auto_meta: dict[str, Any] = {
                "canonical_id": auto_cid,
                "display_name": clean_display,
                "provider": effective_provider,
                "release_date": inferred_release,
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
            self.registry_dirty = True
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
            "release_date": default_release_date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "license": "Proprietary",
            "is_open_weights": False,
            "context_window": 128000,
            "reasoning_mode": reasoning_mode,
            "thinking_effort": effort,
        }
        return provisional_id, "tier3_quarantine", provisional_meta

    def save_registry(self, path: Path | None = None) -> bool:
        """Persists newly auto-promoted canonical models and alias updates back to model_aliases.json."""
        if not self.auto_promoted_ids and not self.registry_dirty:
            return False
        target = path or self.aliases_path
        payload = {
            "registry_version": self.registry_version,
            "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
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
