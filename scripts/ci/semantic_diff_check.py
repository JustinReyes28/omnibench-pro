"""Compares newly generated models_unified.json against a reference copy, ignoring volatile timestamps."""

from __future__ import annotations
import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_TARGET = ROOT_DIR / "public" / "data" / "models_unified.json"


def strip_volatile_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """Removes generated_at and last_updated timestamps so only substantive score/price diffs remain."""
    cleaned = copy.deepcopy(payload)
    cleaned.pop("generated_at", None)
    sources = cleaned.get("sources_metadata") or {}
    for src_meta in sources.values():
        if isinstance(src_meta, dict):
            src_meta.pop("last_updated", None)
    return cleaned


def has_substantive_changes(old_payload: dict[str, Any], new_payload: dict[str, Any], tolerance: float = 0.01) -> bool:
    """Returns True if models were added/removed or any numeric metric changed by >= tolerance."""
    old_clean = strip_volatile_fields(old_payload)
    new_clean = strip_volatile_fields(new_payload)

    old_models = {m["id"]: m for m in old_clean.get("models", [])}
    new_models = {m["id"]: m for m in new_clean.get("models", [])}

    if set(old_models.keys()) != set(new_models.keys()):
        return True

    def _diff_values(a: Any, b: Any) -> bool:
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
            return abs(float(a) - float(b)) >= tolerance
        if isinstance(a, dict) and isinstance(b, dict):
            if set(a.keys()) != set(b.keys()):
                return True
            return any(_diff_values(a[k], b[k]) for k in a)
        if isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                return True
            return any(_diff_values(x, y) for x, y in zip(a, b))
        return a != b

    return _diff_values(old_models, new_models)


def load_git_head_baseline() -> dict[str, Any] | None:
    """Loads the committed HEAD version of public/data/models_unified.json from Git."""
    try:
        raw = subprocess.check_output(
            ["git", "show", "HEAD:public/data/models_unified.json"],
            cwd=str(ROOT_DIR),
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return json.loads(raw)
    except Exception:
        return None


if __name__ == "__main__":
    if not DEFAULT_TARGET.exists():
        print("models_unified.json missing; signaling change required.")
        sys.exit(0)
    current = json.loads(DEFAULT_TARGET.read_text(encoding="utf-8"))
    if len(sys.argv) > 1:
        baseline = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    else:
        baseline = load_git_head_baseline()
        if baseline is None:
            print("[semantic_diff_check] No Git HEAD baseline found; signaling change required.")
            sys.exit(0)
    changed = has_substantive_changes(baseline, current)
    print(f"[semantic_diff_check] substantive_changes={changed}")
    sys.exit(0 if changed else 2)
