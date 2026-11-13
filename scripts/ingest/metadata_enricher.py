"""Free public metadata enricher for newly released or unverified benchmark models.

Queries OpenRouter (/api/v1/models), HuggingFace Hub (/api/models), and
Artificial Analysis SSR model detail pages (/models/<slug>) with strict variant
and header-vs-FAQ release date guards. Never fabricates data and runs strictly
offline/no-op when OMNIBENCH_OFFLINE=1.
"""

from __future__ import annotations

from datetime import datetime, timezone
import html as html_lib
import json
import logging
import os
from pathlib import Path
import re
import urllib.parse
import urllib.request
from typing import Any

from scripts.transform.entity_resolver import (
    ALIASES_PATH,
    EntityResolver,
    _infer_provider,
    format_display_name,
    is_stealth_model,
    normalize_slug,
)

logger = logging.getLogger("omnibench.enricher")
ROOT_DIR = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = ROOT_DIR / "data" / "raw"

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
HF_API_MODELS_URL = "https://huggingface.co/api/models"
AA_MODEL_URL_TMPL = "https://artificialanalysis.ai/models/{slug}"

_VARIANT_QUALIFIERS = frozenset({
    "mini",
    "nano",
    "micro",
    "tiny",
    "small",
    "medium",
    "large",
    "pro",
    "ultra",
    "flash",
    "lite",
    "lightning",
    "air",
    "code",
    "codex",
    "coder",
    "vl",
    "vision",
    "audio",
    "math",
    "reasoner",
    "build",
    "distill",
    "theta",
    "alpha",
    "beta",
    "astra",
    "sol",
    "terra",
    "luna",
    "hydrogen",
    "carbon",
    "argon",
    "wonder",
    "ember",
    "spark",
})

_HARMLESS_HF_QUALIFIERS = frozenset({"instruct", "chat", "it"})

_COMMUNITY_NOISE = frozenset({
    "gguf",
    "awq",
    "gptq",
    "exl2",
    "mlx",
    "fp8",
    "fp4",
    "int4",
    "int8",
    "bf16",
    "nf4",
    "bnb",
    "lora",
    "qlora",
    "abliterated",
    "uncensored",
    "unofficial",
    "pruned",
    "quant",
})

_TRUSTED_UNTRUSTED_AUTHORS = frozenset({
    "bartowski",
    "unsloth",
    "thebloke",
    "lmstudio-community",
    "mlx-community",
    "quanttrio",
    "mradermacher",
    "maziyarpanahi",
    "hugging-quants",
})

_KNOWN_LICENSE_MAP: dict[str, tuple[bool, str]] = {
    "apache-2.0": (True, "Apache-2.0"),
    "apache 2.0": (True, "Apache-2.0"),
    "apache2": (True, "Apache-2.0"),
    "apache2.0": (True, "Apache-2.0"),
    "mit": (True, "MIT"),
    "modified mit": (True, "Modified MIT"),
    "modified-mit": (True, "Modified MIT"),
    "kimi-modified-mit": (True, "Modified MIT"),
    "openmdw-1.1": (True, "OpenMDW-1.1"),
    "openmdw 1.1": (True, "OpenMDW-1.1"),
    "openmdw": (True, "OpenMDW-1.1"),
    "nvidia-open-model": (True, "NVIDIA Open"),
    "nvidia-open-model-license": (True, "NVIDIA Open"),
    "nvidia open model": (True, "NVIDIA Open"),
    "nvidia-open": (True, "NVIDIA Open"),
    "nvidia open": (True, "NVIDIA Open"),
    "gemma": (True, "Gemma"),
    "llama3.1": (True, "Llama-3.1"),
    "llama3.2": (True, "Llama-3.2"),
    "llama3.3": (True, "Llama-3.3"),
    "llama4": (True, "Llama-4"),
    "qwen": (True, "Qwen"),
    "proprietary": (False, "Proprietary"),
    "commercial": (False, "Proprietary"),
    "closed": (False, "Proprietary"),
}


def normalize_license_name(raw_lic: str | None) -> tuple[bool, str] | None:
    """Normalizes SPDX/HuggingFace/AA license strings into (is_open_weights, clean_license)."""
    if not raw_lic:
        return None
    cleaned = re.sub(r"^license:\s*", "", raw_lic.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"^(?:the\s+)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+license$", "", cleaned, flags=re.IGNORECASE).strip()
    if not cleaned:
        return None
    lowered = cleaned.lower()
    if lowered == "other":
        return (True, "other")
    if lowered in _KNOWN_LICENSE_MAP:
        return _KNOWN_LICENSE_MAP[lowered]
    for pat, mapped in _KNOWN_LICENSE_MAP.items():
        if pat in lowered and pat != "mit":
            return mapped
    if re.search(r"\bmit\b", lowered):
        if "modified" in lowered:
            return (True, "Modified MIT")
        return (True, "MIT")
    return (True, cleaned)


def _strip_effort_and_dates(name: str) -> str:
    s = (name or "").strip().lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"^[a-z0-9._-]+/", "", s)
    s = re.sub(r"\b202\d-\d{2}-\d{2}\b", " ", s)
    s = re.sub(r"\b202\d{3,5}\b", " ", s)
    s = re.sub(r"(?:^|[-_\s])(?:max|xhigh|high|low|minimal|none|non-reasoning|standard|thinking|reasoning|preview)(?=$|[-_\s])", " ", s)
    # Strip trailing -medium only if not part of mistral medium
    if "mistral" not in s:
        s = re.sub(r"(?:^|[-_\s])medium(?=$|[-_\s])", " ", s)
    return re.sub(r"[^a-z0-9.]+", " ", s).strip()


def _extract_signature(
    name: str,
) -> tuple[tuple[str, ...], frozenset[str], frozenset[str], frozenset[str], frozenset[str]]:
    cleaned = _strip_effort_and_dates(name)
    tokens = [t for t in cleaned.split() if t]
    # Split concatenated model+version tokens like qwen3.6 or nanbeige4.3 cleanly
    expanded: list[str] = []
    for t in tokens:
        expanded.extend(p for p in re.split(r"(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])", t) if re.match(r"^[a-z]+$|^\d+(?:\.\d+)?$", p))
        if t not in expanded:
            expanded.append(t)

    nums = tuple(re.findall(r"\d+(?:\.\d+)?", cleaned))
    tok_set = set(tokens) | set(expanded)
    size_tokens = frozenset(t for t in tok_set if re.match(r"^a?\d+(?:\.\d+)?[bkm]$", t))
    qualifiers = frozenset(t for t in tok_set if t in _VARIANT_QUALIFIERS)
    noise = frozenset(t for t in tok_set if t in _COMMUNITY_NOISE)
    anchors = frozenset(
        t
        for t in tok_set
        if len(t) >= 2
        and not re.match(r"^\d+(?:\.\d+)?$", t)
        and t not in _VARIANT_QUALIFIERS
        and t not in _HARMLESS_HF_QUALIFIERS
        and t not in _COMMUNITY_NOISE
        and t not in size_tokens
        and t not in {"ai", "research", "china", "mobile", "open", "weights"}
    )
    return nums, size_tokens, qualifiers, noise, anchors


def is_compatible_variant_match(query_name: str, candidate_name: str, allow_harmless_instruct: bool = True) -> bool:
    """Strictly validates that a candidate entry matches the query without cross-variant pollution (e.g. Apodex 1.1 != Apodex 1.1 Mini)."""
    cand_lower = (candidate_name or "").strip().lower()
    author = cand_lower.split("/", 1)[0] if "/" in cand_lower else ""
    if author in _TRUSTED_UNTRUSTED_AUTHORS:
        return False

    q_nums, q_sizes, q_quals, _, q_anchors = _extract_signature(query_name)
    c_nums, c_sizes, c_quals, c_noise, c_anchors = _extract_signature(candidate_name)

    if c_noise:
        return False
    if q_nums != c_nums:
        return False
    if q_sizes != c_sizes:
        return False
    if q_quals != c_quals:
        return False
    if q_anchors and c_anchors and not (q_anchors & c_anchors):
        return False
    if not allow_harmless_instruct:
        cand_clean = set(_strip_effort_and_dates(candidate_name).split())
        q_clean = set(_strip_effort_and_dates(query_name).split())
        if (cand_clean & _HARMLESS_HF_QUALIFIERS) != (q_clean & _HARMLESS_HF_QUALIFIERS):
            return False
    return True


def _normalize_date_str(raw: str | None) -> str | None:
    if not raw:
        return None
    s = raw.strip()
    m_iso = re.match(r"^(20\d{2}-\d{2}-\d{2})", s)
    if m_iso:
        return m_iso.group(1)
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _normalize_ym_str(raw: str | None) -> str | None:
    if not raw:
        return None
    s = raw.strip()
    for fmt in ("%b %Y", "%B %Y"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m")
        except ValueError:
            continue
    m = re.match(r"^(20\d{2})[-/](\d{2})$", s)
    return f"{m.group(1)}-{m.group(2)}" if m else None


def parse_aa_model_page(html_text: str) -> dict[str, Any]:
    """Parses Artificial Analysis /models/<slug> SSR page with header-vs-FAQ date validation."""
    text = html_lib.unescape(re.sub(r"<[^>]+>", " ", html_text))
    text = re.sub(r"\s+", " ", text)

    faq_date: str | None = None
    m_faq = re.search(
        r"(?:was\s+)?released\s+on\s+([A-Z][a-z]+\s+\d{1,2},\s+20\d{2})",
        text,
        re.IGNORECASE,
    )
    if m_faq:
        faq_date = _normalize_date_str(m_faq.group(1))

    header_ym: str | None = None
    m_hdr = re.search(r"\bReleased\s+([A-Z][a-z]+\s+20\d{2})\b", text, re.IGNORECASE)
    if m_hdr:
        header_ym = _normalize_ym_str(m_hdr.group(1))

    aa_release_date: str | None = None
    faq_superseded = False
    if header_ym and faq_date:
        if header_ym < faq_date[:7]:
            # Header month precedes AA's FAQ date (e.g. Released July 2026 vs AA added Nov 11, 2026)
            faq_superseded = True
            aa_release_date = f"{header_ym}-01"
        else:
            aa_release_date = faq_date
    elif faq_date:
        aa_release_date = faq_date
    elif header_ym:
        aa_release_date = f"{header_ym}-01"

    open_weights: bool | None = None
    license_name: str | None = None
    if re.search(r"\bopen\s+weights\s+model\b", text, re.IGNORECASE):
        open_weights = True
    elif re.search(r"\bproprietary\s+model\b", text, re.IGNORECASE):
        open_weights = False

    m_lic = re.search(
        r"released\s+under\s+(?:the\s+)?([A-Za-z0-9.\s_-]{2,40}?)\s+license\b",
        text,
        re.IGNORECASE,
    )
    if m_lic:
        parsed_lic = normalize_license_name(m_lic.group(1))
        if parsed_lic:
            open_weights = parsed_lic[0] if open_weights is None else open_weights
            if parsed_lic[1] != "other":
                license_name = parsed_lic[1]

    context_window: int | None = None
    m_ctx = re.search(r"(?:context\s+(?:window|length)[^0-9]{0,20}|^|\s)(\d+(?:\.\d+)?)\s*([mk])\s+context\b", text, re.IGNORECASE)
    if m_ctx:
        val = float(m_ctx.group(1))
        unit = m_ctx.group(2).lower()
        context_window = int(val * (1_000_000 if unit == "m" else 1_000))

    hf_id: str | None = None
    m_hf = re.search(r"https?://huggingface\.co/([A-Za-z0-9._-]+/[A-Za-z0-9._-]+)", html_text)
    if m_hf:
        cand_hf = m_hf.group(1).strip().rstrip("/")
        if not cand_hf.lower().startswith(("spaces/", "datasets/")):
            hf_id = cand_hf

    return {
        "release_date": aa_release_date,
        "header_ym": header_ym,
        "faq_date": faq_date,
        "faq_superseded": faq_superseded,
        "open_weights": open_weights,
        "license": license_name,
        "context_window": context_window,
        "hugging_face_id": hf_id,
    }


def match_openrouter_model(raw_name: str, or_models: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Finds strict variant-compatible entry in OpenRouter /api/v1/models catalog."""
    best: dict[str, Any] | None = None
    for entry in or_models:
        or_id = str(entry.get("id") or "").strip()
        or_name = str(entry.get("name") or "").strip()
        if not or_id:
            continue
        if is_compatible_variant_match(raw_name, or_id) or (or_name and is_compatible_variant_match(raw_name, or_name)):
            created_ts = entry.get("created")
            created_date: str | None = None
            if isinstance(created_ts, (int, float)) and created_ts > 1_600_000_000:
                created_date = datetime.fromtimestamp(float(created_ts), tz=timezone.utc).strftime("%Y-%m-%d")
            ctx = entry.get("context_length")
            hf_id = entry.get("hugging_face_id")
            cand = {
                "openrouter_id": or_id,
                "release_date": created_date,
                "context_window": int(ctx) if isinstance(ctx, (int, float)) and int(ctx) > 1000 else None,
                "hugging_face_id": str(hf_id).strip() if hf_id else None,
            }
            # Prefer matches that link directly to a HuggingFace repo or carry context_length
            if best is None or (cand["hugging_face_id"] and not best.get("hugging_face_id")):
                best = cand
                if cand["hugging_face_id"]:
                    break
    return best


def parse_hf_model_metadata(query_name: str, hf_obj: dict[str, Any]) -> dict[str, Any] | None:
    """Parses HuggingFace Hub API model object with strict variant guard."""
    repo_id = str(hf_obj.get("id") or hf_obj.get("modelId") or "").strip()
    if not repo_id or not is_compatible_variant_match(query_name, repo_id):
        return None

    created_raw = hf_obj.get("createdAt")
    release_date = _normalize_date_str(str(created_raw)) if created_raw else None

    license_name: str | None = None
    open_weights = True
    tags = [str(t) for t in (hf_obj.get("tags") or []) if t]
    for t in tags:
        if t.lower().startswith("license:"):
            parsed = normalize_license_name(t)
            if parsed and parsed[1] != "other":
                open_weights, license_name = parsed
                break
    if not license_name and isinstance(hf_obj.get("cardData"), dict):
        card_lic = hf_obj["cardData"].get("license")
        if isinstance(card_lic, list) and card_lic:
            card_lic = card_lic[0]
        parsed = normalize_license_name(str(card_lic) if card_lic else None)
        if parsed and parsed[1] != "other":
            open_weights, license_name = parsed

    ctx: int | None = None
    cfg = hf_obj.get("config")
    if isinstance(cfg, dict):
        mpe = cfg.get("max_position_embeddings")
        if isinstance(mpe, (int, float)) and int(mpe) > 1000:
            ctx = int(mpe)

    return {
        "hugging_face_id": repo_id,
        "release_date": release_date,
        "open_weights": open_weights,
        "license": license_name,
        "context_window": ctx,
    }


def reconcile_enriched_metadata(
    raw_name: str,
    *,
    aa_meta: dict[str, Any] | None = None,
    or_meta: dict[str, Any] | None = None,
    hf_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Combines AA SSR page, OpenRouter, and HuggingFace metadata using accuracy priority rules."""
    aa_meta = aa_meta or {}
    or_meta = or_meta or {}
    hf_meta = hf_meta or {}

    header_ym: str | None = aa_meta.get("header_ym")
    hf_date: str | None = hf_meta.get("release_date")
    or_date: str | None = or_meta.get("release_date")
    aa_date: str | None = aa_meta.get("release_date")
    aa_faq_superseded = bool(aa_meta.get("faq_superseded"))

    # Collect day-precision dates excluding post-header AA FAQ upload dates
    day_candidates: list[str] = []
    if hf_date:
        day_candidates.append(hf_date)
    if or_date:
        day_candidates.append(or_date)
    if aa_date and not aa_faq_superseded and not (header_ym and aa_date == f"{header_ym}-01" and aa_meta.get("faq_date") is None):
        day_candidates.append(aa_date)

    release_date: str | None = None
    if header_ym:
        in_hdr_month = [d for d in day_candidates if d[:7] == header_ym]
        if in_hdr_month:
            release_date = min(in_hdr_month)
        elif hf_date and hf_date[:7] <= header_ym:
            release_date = hf_date
        elif aa_date:
            release_date = aa_date
        elif day_candidates:
            release_date = min(day_candidates)
    elif hf_date:
        if aa_date and aa_date < hf_date and aa_date[:7] == hf_date[:7]:
            release_date = aa_date
        else:
            release_date = hf_date
    elif day_candidates:
        release_date = min(day_candidates)
    elif aa_date:
        release_date = aa_date

    # Open weights / license
    open_weights: bool | None = None
    if hf_meta.get("open_weights"):
        open_weights = True
    elif aa_meta.get("open_weights") is not None:
        open_weights = bool(aa_meta["open_weights"])

    license_name: str | None = None
    for cand_lic in (aa_meta.get("license"), hf_meta.get("license")):
        if cand_lic and cand_lic.lower() not in ("proprietary", "commercial", "other"):
            license_name = cand_lic
            open_weights = True
            break
    if open_weights is False and not license_name:
        license_name = "Proprietary"

    # Context window
    ctx_cands = [
        c for c in (or_meta.get("context_window"), hf_meta.get("context_window"), aa_meta.get("context_window"))
        if isinstance(c, int) and c > 128000
    ]
    context_window = max(ctx_cands) if ctx_cands else None

    return {
        "release_date": release_date,
        "open_weights": open_weights,
        "license": license_name,
        "context_window": context_window,
    }


def _http_get_text(url: str, headers: dict[str, str] | None = None, timeout: float = 10.0) -> str:
    req_headers = {"User-Agent": "OmniBench-Aggregator/1.0"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _http_get_json(url: str, headers: dict[str, str] | None = None, timeout: float = 10.0) -> Any:
    return json.loads(_http_get_text(url, headers=headers, timeout=timeout))


def enrich_snapshots(
    raw_dir: Path | None = None,
    aliases_path: Path | None = None,
    offline_mode: bool | None = None,
) -> dict[str, Any]:
    """Enriches newly discovered or unverified models across raw snapshots using free public endpoints."""
    if offline_mode is None:
        offline_mode = os.environ.get("OMNIBENCH_OFFLINE", "1") == "1"
    if offline_mode:
        return {"enriched_count": 0, "skipped": True}

    src_root = raw_dir or RAW_DATA_DIR
    resolver = EntityResolver(aliases_path=aliases_path or ALIASES_PATH)

    or_models: list[dict[str, Any]] = []
    try:
        or_payload = _http_get_json(OPENROUTER_MODELS_URL)
        if isinstance(or_payload, dict) and isinstance(or_payload.get("data"), list):
            or_models = or_payload["data"]
    except Exception as exc:
        logger.debug("OpenRouter catalog fetch skipped: %s", exc)

    hf_headers: dict[str, str] = {}
    hf_token = os.environ.get("HF_TOKEN", "").strip()
    if hf_token:
        hf_headers["Authorization"] = f"Bearer {hf_token}"

    cache: dict[str, dict[str, Any]] = {}
    enriched_count = 0

    def _raw_id_for(source_key: str, item: dict[str, Any]) -> str:
        return str(
            item.get("model_name")
            or item.get("model_key")
            or item.get("arena_model_id")
            or item.get("vals_model_name")
            or item.get("display_name")
            or ""
        ).strip()

    for source_key in ("artificial_analysis", "livebench", "arena", "vals"):
        snap_path = src_root / source_key / "latest.json"
        if not snap_path.exists():
            continue
        try:
            snap = json.loads(snap_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        snap_dirty = False
        for item in snap.get("models", []):
            raw_name = _raw_id_for(source_key, item)
            if not raw_name:
                continue
            raw_prov = str(item.get("provider") or item.get("organization") or "Unknown")
            inferred_prov = _infer_provider(raw_name, raw_prov)
            if is_stealth_model(inferred_prov, raw_name):
                continue

            cid, tier, meta = resolver.resolve(source_key, raw_name, raw_prov, auto_promote=False)
            is_curated = (
                tier != "tier3_quarantine"
                and not meta.get("auto_promoted", False)
                and bool(meta.get("release_date"))
            )
            if is_curated:
                continue

            # Format raw lowercase slugs cleanly when display_name mirrors raw_id
            cur_disp = str(item.get("display_name") or "")
            if cur_disp and cur_disp == raw_name:
                formatted_disp = format_display_name(raw_name, inferred_prov)
                if formatted_disp and formatted_disp != cur_disp:
                    item["display_name"] = formatted_disp
                    snap_dirty = True

            # Skip live remote lookups if item already has verified date and >128k context
            if item.get("release_date") and item.get("metadata_verified") and (item.get("context_window") or 128000) > 128000:
                continue

            cache_key = normalize_slug(raw_name)
            if cache_key not in cache:
                aa_meta: dict[str, Any] = {}
                or_meta = match_openrouter_model(raw_name, or_models) if or_models else None
                hf_meta: dict[str, Any] | None = None

                aa_slug = item.get("aa_slug")
                if aa_slug:
                    try:
                        aa_html = _http_get_text(AA_MODEL_URL_TMPL.format(slug=urllib.parse.quote(str(aa_slug), safe="")))
                        aa_meta = parse_aa_model_page(aa_html)
                    except Exception as exc:
                        logger.debug("AA model page lookup failed for %s: %s", aa_slug, exc)

                hf_repo_cand = (or_meta or {}).get("hugging_face_id") or aa_meta.get("hugging_face_id")
                lower_raw = raw_name.lower()
                closed_lab = (
                    inferred_prov in ("Anthropic", "xAI")
                    or (inferred_prov == "OpenAI" and "gpt-oss" not in lower_raw)
                    or (inferred_prov == "Google" and "gemma" not in lower_raw)
                )
                allow_unlinked_hf = aa_meta.get("open_weights") is True or (
                    aa_meta.get("open_weights") is not False
                    and not closed_lab
                    and not aa_meta.get("release_date")
                )
                if hf_repo_cand:
                    try:
                        hf_obj = _http_get_json(f"{HF_API_MODELS_URL}/{urllib.parse.quote(hf_repo_cand, safe='/')}", headers=hf_headers)
                        if isinstance(hf_obj, dict):
                            hf_meta = parse_hf_model_metadata(raw_name, hf_obj)
                    except Exception as exc:
                        logger.debug("HF repo lookup failed for %s: %s", hf_repo_cand, exc)
                elif allow_unlinked_hf:
                    search_q = urllib.parse.quote(re.sub(r"\([^)]*\)", "", raw_name).strip())
                    try:
                        hf_list = _http_get_json(
                            f"{HF_API_MODELS_URL}?search={search_q}&sort=downloads&direction=-1&limit=8",
                            headers=hf_headers,
                        )
                        if isinstance(hf_list, list):
                            for cand in hf_list:
                                if not isinstance(cand, dict):
                                    continue
                                if int(cand.get("downloads") or 0) < 50:
                                    continue
                                parsed_hf = parse_hf_model_metadata(raw_name, cand)
                                if parsed_hf:
                                    # Fetch full detail endpoint for createdAt + card/config metadata
                                    try:
                                        full_hf = _http_get_json(
                                            f"{HF_API_MODELS_URL}/{urllib.parse.quote(parsed_hf['hugging_face_id'], safe='/')}",
                                            headers=hf_headers,
                                        )
                                        if isinstance(full_hf, dict):
                                            parsed_hf = parse_hf_model_metadata(raw_name, full_hf) or parsed_hf
                                    except Exception:
                                        pass
                                    hf_meta = parsed_hf
                                    break
                    except Exception as exc:
                        logger.debug("HF search failed for %s: %s", raw_name, exc)

                cache[cache_key] = reconcile_enriched_metadata(
                    raw_name, aa_meta=aa_meta, or_meta=or_meta, hf_meta=hf_meta
                )

            rec = cache[cache_key]
            if rec.get("release_date") and not item.get("release_date"):
                item["release_date"] = rec["release_date"]
                item["metadata_verified"] = True
                snap_dirty = True
                enriched_count += 1
            if rec.get("open_weights") is True and not item.get("open_weights"):
                item["open_weights"] = True
                snap_dirty = True
            if rec.get("license") and (not item.get("license") or item.get("license") == "Proprietary"):
                item["license"] = rec["license"]
                if rec["license"].lower() not in ("proprietary", "commercial"):
                    item["open_weights"] = True
                snap_dirty = True
            if rec.get("context_window") and (item.get("context_window") or 128000) == 128000:
                item["context_window"] = rec["context_window"]
                snap_dirty = True

        if snap_dirty:
            snap_path.write_text(json.dumps(snap, indent=2, allow_nan=False) + "\n", encoding="utf-8")

    return {"enriched_count": enriched_count, "skipped": False}
