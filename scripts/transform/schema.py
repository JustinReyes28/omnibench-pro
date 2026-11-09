"""Schema validation for CanonicalModelRecord, per-source metric blocks, and unified dataset."""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Any

VALID_EFFORT_LEVELS = {"max", "xhigh", "high", "medium", "low", "minimal", "none", "standard"}


def _check_finite_number(val: Any, field_name: str, allow_none: bool = True, min_val: float | None = None, max_val: float | None = None) -> float | None:
    if val is None:
        if allow_none:
            return None
        raise ValueError(f"Field '{field_name}' cannot be None")
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        raise TypeError(f"Field '{field_name}' must be numeric, got {type(val).__name__}")
    fval = float(val)
    if math.isnan(fval) or math.isinf(fval):
        raise ValueError(f"Field '{field_name}' contains NaN or Infinity")
    if min_val is not None and fval < min_val:
        raise ValueError(f"Field '{field_name}'={fval} is below minimum {min_val}")
    if max_val is not None and fval > max_val:
        raise ValueError(f"Field '{field_name}'={fval} exceeds maximum {max_val}")
    return fval


@dataclass
class PricingBlock:
    input_per_1m_usd: float | None
    output_per_1m_usd: float | None
    blended_per_1m_usd: float | None

    def validate(self) -> None:
        _check_finite_number(self.input_per_1m_usd, "pricing.input_per_1m_usd", min_val=0.0)
        _check_finite_number(self.output_per_1m_usd, "pricing.output_per_1m_usd", min_val=0.0)
        _check_finite_number(self.blended_per_1m_usd, "pricing.blended_per_1m_usd", min_val=0.0)


@dataclass
class PerformanceBlock:
    output_tokens_per_sec: float | None
    ttft_seconds: float | None

    def validate(self) -> None:
        _check_finite_number(self.output_tokens_per_sec, "performance.output_tokens_per_sec", min_val=0.0)
        _check_finite_number(self.ttft_seconds, "performance.ttft_seconds", min_val=0.0)


def validate_canonical_model_record(record: dict[str, Any]) -> dict[str, Any]:
    """Validates a canonical model dictionary against strict schema bounds and zero-NaN rules."""
    required_str = ("id", "display_name", "provider", "release_date", "license", "reasoning_mode")
    for key in required_str:
        if not isinstance(record.get(key), str) or not record[key].strip():
            raise ValueError(f"Missing or invalid string field '{key}' in record {record.get('id')}")

    effort = record.get("thinking_effort")
    if effort is not None and effort not in VALID_EFFORT_LEVELS:
        raise ValueError(f"Invalid thinking_effort='{effort}' in record {record.get('id')}")

    if not isinstance(record.get("is_open_weights"), bool):
        raise TypeError(f"Field 'is_open_weights' must be bool in {record['id']}")

    ctx = record.get("context_window")
    if not isinstance(ctx, int) or ctx <= 0:
        raise ValueError(f"Invalid context_window={ctx} in {record['id']}")

    pricing = record.get("pricing") or {}
    PricingBlock(
        input_per_1m_usd=pricing.get("input_per_1m_usd"),
        output_per_1m_usd=pricing.get("output_per_1m_usd"),
        blended_per_1m_usd=pricing.get("blended_per_1m_usd"),
    ).validate()

    perf = record.get("performance") or {}
    PerformanceBlock(
        output_tokens_per_sec=perf.get("output_tokens_per_sec"),
        ttft_seconds=perf.get("ttft_seconds"),
    ).validate()

    benchmarks = record.get("benchmarks") or {}
    aa = benchmarks.get("artificial_analysis")
    if aa is not None:
        for k in ("intelligence_index", "coding_index", "math_index"):
            _check_finite_number(aa.get(k), f"aa.{k}", allow_none=False, min_val=0.0, max_val=100.0)

    lb = benchmarks.get("livebench")
    if lb is not None:
        for k in ("global_average", "coding", "mathematics", "reasoning", "data_analysis", "language", "instruction_following", "agentic_coding"):
            _check_finite_number(lb.get(k), f"livebench.{k}", allow_none=False, min_val=0.0, max_val=100.0)
        _check_finite_number(lb.get("cost_per_question_usd"), "livebench.cost_per_question_usd", allow_none=True, min_val=0.0)

    ar = benchmarks.get("arena")
    if ar is not None:
        for k in ("text_elo", "text_ci_lower", "text_ci_upper", "coding_elo", "vision_elo"):
            _check_finite_number(ar.get(k), f"arena.{k}", allow_none=True, min_val=500.0, max_val=2500.0)
        _check_finite_number(ar.get("votes"), "arena.votes", allow_none=True, min_val=0.0)

    va = benchmarks.get("vals")
    if va is not None:
        for k in ("vals_index", "finance_agent", "legal_bench", "tax_agent", "vibe_code"):
            _check_finite_number(va.get(k), f"vals.{k}", allow_none=False, min_val=0.0, max_val=100.0)
        _check_finite_number(va.get("cost_per_test_usd"), "vals.cost_per_test_usd", allow_none=True, min_val=0.0)

    comp = record.get("composite") or {}
    _check_finite_number(comp.get("unified_quality_score"), "composite.unified_quality_score", allow_none=False, min_val=0.0, max_val=100.0)
    _check_finite_number(comp.get("coding_composite_score"), "composite.coding_composite_score", allow_none=False, min_val=0.0, max_val=100.0)
    _check_finite_number(comp.get("enterprise_agent_score"), "composite.enterprise_agent_score", allow_none=False, min_val=0.0, max_val=100.0)
    _check_finite_number(comp.get("value_efficiency_score"), "composite.value_efficiency_score", allow_none=False, min_val=0.0, max_val=100.0)
    if not isinstance(comp.get("is_pareto_optimal"), bool):
        raise TypeError("composite.is_pareto_optimal must be boolean")

    return record
