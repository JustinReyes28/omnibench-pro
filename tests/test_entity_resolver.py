"""Unit tests for Phase 2 3-Tier Entity Resolution and Pareto / Percentile math."""

import unittest
from scripts.transform.entity_resolver import EntityResolver, normalize_slug
from scripts.transform.normalizer import compute_percentile_ranks, mark_pareto_frontier


class TestEntityResolverAndNormalizer(unittest.TestCase):
    def setUp(self) -> None:
        self.resolver = EntityResolver()

    def test_tier1_exact_alias_resolution(self) -> None:
        cid1, tier1, _ = self.resolver.resolve("artificial_analysis", "Claude Opus 5.5 (Reasoning)")
        cid2, tier2, _ = self.resolver.resolve("arena", "anthropic-claude-opus-5-5-202610")
        cid3, tier3, _ = self.resolver.resolve("vals", "Claude Opus 5.5 (Max)")
        cid_high, tier_high, meta_high = self.resolver.resolve("vals", "Claude Opus 5.5 (High)")
        self.assertEqual(cid1, "anthropic-claude-opus-5-5")
        self.assertEqual(cid2, "anthropic-claude-opus-5-5")
        self.assertEqual(cid3, "anthropic-claude-opus-5-5")
        self.assertEqual(cid_high, "anthropic-claude-opus-5-5-high")
        self.assertEqual(meta_high["thinking_effort"], "high")
        self.assertEqual(tier1, "tier1_exact")

    def test_tier2_normalized_slug_resolution(self) -> None:
        slug = normalize_slug("openai/GPT-5.6-Sol (Thinking)-20261015")
        self.assertEqual(slug, "gpt-5-6-sol")
        cid, tier, _ = self.resolver.resolve("arena", "openai/GPT-5.6-Sol (Thinking)-20261015")
        self.assertEqual(cid, "openai-gpt-5-6-sol")
        self.assertIn("tier2", tier)

    def test_tier3_unmatched_quarantine(self) -> None:
        cid, tier, _ = self.resolver.resolve("arena", "mystery-omega-99b-20261028", "MysteryOrg")
        self.assertEqual(tier, "tier3_quarantine")
        self.assertTrue(cid.startswith("unmatched-"))
        self.assertEqual(len(self.resolver.unmatched_queue), 1)

    def test_pareto_frontier_calculation(self) -> None:
        sample_models = [
            {"id": "cheap-good", "pricing": {"blended_per_1m_usd": 0.50}, "composite": {"unified_quality_score": 80.0}},
            {"id": "expensive-worse", "pricing": {"blended_per_1m_usd": 5.00}, "composite": {"unified_quality_score": 75.0}},
            {"id": "flagship-best", "pricing": {"blended_per_1m_usd": 15.00}, "composite": {"unified_quality_score": 96.0}},
        ]
        mark_pareto_frontier(sample_models)
        by_id = {m["id"]: m["composite"]["is_pareto_optimal"] for m in sample_models}
        self.assertTrue(by_id["cheap-good"])
        self.assertFalse(by_id["expensive-worse"])
        self.assertTrue(by_id["flagship-best"])


if __name__ == "__main__":
    unittest.main()
