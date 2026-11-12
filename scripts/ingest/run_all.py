"""Runs all 4 Phase 1 ingestion adapters with Last-Known-Good fallback and metadata enrichment."""

from __future__ import annotations
import sys
from scripts.ingest.fetch_artificial_analysis import ArtificialAnalysisFetcher
from scripts.ingest.fetch_livebench import LiveBenchFetcher
from scripts.ingest.fetch_arena import ArenaFetcher
from scripts.ingest.fetch_vals import ValsFetcher
from scripts.ingest.metadata_enricher import enrich_snapshots


def run_all(offline_mode: bool | None = None) -> dict[str, dict]:
    adapters = [
        ArtificialAnalysisFetcher(offline_mode=offline_mode),
        LiveBenchFetcher(offline_mode=offline_mode),
        ArenaFetcher(offline_mode=offline_mode),
        ValsFetcher(offline_mode=offline_mode),
    ]
    results = {}
    for adapter in adapters:
        snap = adapter.run()
        results[adapter.source_key] = snap
        print(
            f"[ingest] {adapter.source_name:<22} | status={snap['fetch_status']:<15} | models={len(snap['models'])}"
        )
    enrich_res = enrich_snapshots(offline_mode=offline_mode)
    if not enrich_res.get("skipped"):
        print(f"[ingest] Metadata Enricher      | newly_enriched={enrich_res.get('enriched_count', 0)}")
    return results


if __name__ == "__main__":
    summary = run_all()
    if any(len(v.get("models", [])) < 15 for v in summary.values()):
        sys.exit(1)
