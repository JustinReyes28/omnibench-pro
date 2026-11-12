"""Statistical normalization, percentile ranking, Winsorized Z-scores, and Pareto frontier engine."""

from __future__ import annotations
import math
import statistics
from typing import Any


def compute_winsorized_zscores(values_by_id: dict[str, float], clip_sd: float = 3.0) -> dict[str, float]:
    """Computes Z-scores clipped to +/- clip_sd standard deviations."""
    if len(values_by_id) < 2:
        return {k: 0.0 for k in values_by_id}
    vals = list(values_by_id.values())
    mean = statistics.fmean(vals)
    stdev = statistics.stdev(vals)
    if stdev == 0:
        return {k: 0.0 for k in values_by_id}
    return {
        mid: round(max(-clip_sd, min(clip_sd, (v - mean) / stdev)), 3)
        for mid, v in values_by_id.items()
    }


def compute_percentile_ranks(values_by_id: dict[str, float]) -> dict[str, float]:
    """Computes frontier-calibrated 0-100 scores across the active model pool.

    Combines cardinal min-max scaling mapped onto [5.0, 100.0] (65%), empirical
    rank percentile (25%), and Winsorized Z-score tail calibration (10%) so that:
    - True frontier models preserve their cardinal lead at the top of the scale.
    - Legacy and smaller models are graded accurately without artificial floor compression.
    """
    if not values_by_id:
        return {}
    vals = list(values_by_id.values())
    if len(vals) == 1:
        return {k: 100.0 for k in values_by_id}

    min_v = min(vals)
    max_v = max(vals)
    span = max_v - min_v
    sorted_vals = sorted(vals)
    n = len(sorted_vals)
    z_map = compute_winsorized_zscores(values_by_id, clip_sd=2.8)

    out: dict[str, float] = {}
    for mid, v in values_by_id.items():
        less_count = sum(1 for x in sorted_vals if x < v)
        equal_count = sum(1 for x in sorted_vals if x == v)
        empirical_pct = ((less_count + 0.5 * (equal_count - 1)) / max(1, n - 1)) * 100.0
        scaled_linear = 5.0 + ((v - min_v) / span) * 95.0 if span > 0 else 100.0
        z_norm = ((z_map.get(mid, 0.0) + 2.8) / 5.6) * 100.0
        blended = 0.65 * scaled_linear + 0.25 * empirical_pct + 0.10 * z_norm
        out[mid] = round(max(1.0, min(100.0, blended)), 2)
    return out


def compute_weighted_composite(
    pillar_scores: dict[str, float | None],
    weights: dict[str, float] | None = None,
    shrinkage_prior: float = 48.0,
) -> float:
    """Computes coverage-calibrated composite score across available benchmark pillars.

    Default frontier weights emphasize objective, contamination-resistant, and
    real-world agentic benchmarks:
    - Artificial Analysis Intelligence v5.0: 30%
    - LiveBench 2.0 Contamination-Free Suite: 30%
    - Vals.ai Enterprise Index v2.2: 25%
    - Arena.ai Human + Coding Elo: 15%

    Applies a Bayesian missing-source shrinkage prior when a model is missing
    active pillars so single-benchmark outliers cannot leapfrog full-coverage
    frontier models.
    """
    if weights is None:
        weights = {"aa": 30.0, "lb": 30.0, "ar": 15.0, "va": 25.0}
    weighted_sum = 0.0
    active_w = 0.0
    requested_w = sum(w for w in weights.values() if w > 0)
    for k, w in weights.items():
        val = pillar_scores.get(k)
        if val is not None and not math.isnan(val) and w > 0:
            weighted_sum += val * w
            active_w += w
    if active_w == 0:
        return 0.0
    raw_mean = weighted_sum / active_w
    if requested_w > 0 and active_w < requested_w:
        missing_frac = (requested_w - active_w) / requested_w
        prior_weight = 0.18 * missing_frac
        adjusted = (1.0 - prior_weight) * raw_mean + prior_weight * shrinkage_prior
        return round(adjusted, 2)
    return round(raw_mean, 2)


def mark_pareto_frontier(models: list[dict[str, Any]], min_sources_for_pareto: int = 2) -> None:
    """Marks is_pareto_optimal=True for multi-source corroborated models where no cheaper model has equal/higher quality."""
    candidates = []
    for m in models:
        comp = m.get("composite") or {}
        price = (m.get("pricing") or {}).get("blended_per_1m_usd")
        qual = comp.get("unified_quality_score")
        sources_present = comp.get("sources_present")
        corroborated = sources_present is None or int(sources_present) >= min_sources_for_pareto
        if price is not None and price > 0 and qual is not None and not comp.get("provisional_ranking") and corroborated:
            candidates.append((m["id"], float(price), float(qual)))

    pareto_ids: set[str] = set()
    for mid, price, qual in candidates:
        dominated = False
        for other_id, other_price, other_qual in candidates:
            if other_id == mid:
                continue
            if other_price <= price and other_qual >= qual and (other_price < price or other_qual > qual):
                dominated = True
                break
        if not dominated:
            pareto_ids.add(mid)

    for m in models:
        m["composite"]["is_pareto_optimal"] = m["id"] in pareto_ids
