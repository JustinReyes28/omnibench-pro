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

    def test_version_and_effort_signature_prevents_fuzzy_collision(self) -> None:
        # Registered Nov 2026 models resolve to their exact canonical IDs
        cid_fable, _, _ = self.resolver.resolve("artificial_analysis", "Claude Fable 5.2 (Max)")
        cid_fable_xh, _, _ = self.resolver.resolve("livebench", "anthropic-claude-fable-5-2-xhigh")
        cid_inkling2, _, _ = self.resolver.resolve("vals", "Inkling 2 Small")
        self.assertEqual(cid_fable, "anthropic-claude-fable-5-2-max")
        self.assertEqual(cid_fable_xh, "anthropic-claude-fable-5-2-xhigh")
        self.assertEqual(cid_inkling2, "thinking-machines-inkling-2-small")

        # Future unaliased versions/efforts must NOT fuzzy-collide into prior versions
        cid_future_inkling, tier_i3, meta_i3 = self.resolver.resolve("vals", "Inkling 3 Small")
        self.assertEqual(tier_i3, "tier3_quarantine")
        self.assertEqual(cid_future_inkling, "unmatched-inkling-3-small")
        self.assertEqual(meta_i3["provider"], "Thinking Machines")

        cid_future_fable, tier_f53, meta_f53 = self.resolver.resolve("arena", "Claude Fable 5.3 (Max)")
        self.assertEqual(tier_f53, "tier3_quarantine")
        self.assertEqual(cid_future_fable, "unmatched-claude-fable-5-3-max")
        self.assertEqual(meta_f53["provider"], "Anthropic")
        self.assertEqual(meta_f53["thinking_effort"], "max")

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
