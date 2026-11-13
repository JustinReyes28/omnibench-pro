"""Unit tests for Phase 1 Ingestion Adapters and Last-Known-Good (LKG) fallback."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.ingest.fetch_artificial_analysis import ArtificialAnalysisFetcher
from scripts.ingest.fetch_arena import ArenaFetcher
from scripts.ingest.fetch_livebench import LiveBenchFetcher
from scripts.ingest.fetch_vals import ValsFetcher
from scripts.ingest.metadata_enricher import (
    enrich_snapshots,
    is_compatible_variant_match,
    parse_aa_model_page,
    reconcile_enriched_metadata,
)
from scripts.transform.entity_resolver import ALIASES_PATH


class TestIngestionAdapters(unittest.TestCase):
    def test_offline_lkg_fallback_for_all_sources(self) -> None:
        adapters = [
            ArtificialAnalysisFetcher(offline_mode=True),
            LiveBenchFetcher(offline_mode=True),
            ArenaFetcher(offline_mode=True),
            ValsFetcher(offline_mode=True),
        ]
        for adapter in adapters:
            snap = adapter.run()
            self.assertEqual(snap["fetch_status"], "cached_fallback")
            self.assertGreaterEqual(len(snap["models"]), 30)
            self.assertIn("source_url", snap)
            self.assertIn("fetched_at", snap)

    def test_livebench_category_averaging_helper(self) -> None:
        sample_row = {"lcb_gen": 80.0, "code_comp": 70.0, "aime": 90.0, "amc": 82.0}
        cat_map = {"coding": ["lcb_gen", "code_comp"], "mathematics": ["aime", "amc"]}
        res = LiveBenchFetcher.compute_category_averages(sample_row, cat_map)
        self.assertEqual(res["coding"], 75.0)
        self.assertEqual(res["mathematics"], 86.0)
        self.assertEqual(res["global_average"], 80.5)

    def test_incremental_merge_preserves_existing_models(self) -> None:
        adapter = ValsFetcher(offline_mode=True)
        merged = adapter.merge_with_lkg([
            {
                "vals_model_name": "Claude Fable 5.2 (Max)",
                "provider": "Anthropic",
                "vals_index": 71.85,
                "finance_agent": 70.1,
                "legal_bench": 54.2,
                "tax_agent": 47.5,
                "vibe_code": 94.2,
                "cost_per_test_usd": 24.5,
            }
        ])
        self.assertGreaterEqual(len(merged), 139)
        self.assertEqual(merged[0]["vals_model_name"], "Claude Fable 5.2 (Max)")

    def test_arena_hf_dataset_pagination_category_filter_and_bounds(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = ArenaFetcher(raw_dir=Path(tmpdir), offline_mode=False)

            def fake_json(url: str, headers: dict | None = None):
                if "api.wulong.dev" in url or "oolong-tea-2026" in url:
                    raise RuntimeError("Upstream mirror down")
                if "config=text" in url and "offset=0" in url:
                    return {
                        "num_rows_total": 102,
                        "rows": [
                            {"row": {"model_name": "gemini-4-hydrogen", "organization": "google", "license": "Proprietary", "category": "overall", "rating": 1495.4, "rating_lower": 1488.0, "rating_upper": 1502.0, "vote_count": 12450}}
                            for _ in range(100)
                        ],
                    }
                if "config=text" in url and "offset=100" in url:
                    return {
                        "num_rows_total": 102,
                        "rows": [
                            {"row": {"model_name": "gemini-4-hydrogen", "organization": "google", "category": "coding", "rating": 1520.2, "vote_count": 4200}},
                            {"row": {"model_name": "non-elo-ips-row", "organization": "openai", "category": "overall", "rating": 0.42, "vote_count": 300}},
                        ],
                    }
                if "config=vision" in url:
                    return {
                        "num_rows_total": 1,
                        "rows": [
                            {"row": {"model_name": "gemini-4-hydrogen", "organization": "google", "category": "overall", "rating": 1475.1, "vote_count": 3100}},
                        ],
                    }
                raise AssertionError(f"Unexpected URL {url}")

            with patch.object(adapter, "request_json", side_effect=fake_json):
                models = adapter.fetch_live_models()

            self.assertEqual(len(models), 1)
            m = models[0]
            self.assertEqual(m["arena_model_id"], "gemini-4-hydrogen")
            self.assertEqual(m["text_elo"], 1495)
            self.assertEqual(m["text_ci_lower"], 1488)
            self.assertEqual(m["text_ci_upper"], 1502)
            self.assertEqual(m["coding_elo"], 1520)
            self.assertEqual(m["vision_elo"], 1475)
            self.assertEqual(m["votes"], 12450)

    def test_arena_github_archive_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = ArenaFetcher(raw_dir=Path(tmpdir), offline_mode=False)

            def fake_json(url: str, headers: dict | None = None):
                if "api.wulong.dev" in url:
                    raise RuntimeError("Down")
                if url.endswith("/latest.json"):
                    return {"date": "2026-11-12"}
                if url.endswith("/2026-11-12/text.json"):
                    return {"models": [{"model": "claude-fable-5-2", "vendor": "anthropic", "license": "Proprietary", "score": 1510.0, "ci": 5, "votes": 9000}]}
                if url.endswith("/2026-11-12/code.json"):
                    return {"models": [{"model": "claude-fable-5-2", "score": 1545.0}]}
                if url.endswith("/2026-11-12/vision.json"):
                    return {"models": [{"model": "claude-fable-5-2", "score": 1480.0}]}
                raise RuntimeError("404")

            with patch.object(adapter, "request_json", side_effect=fake_json):
                models = adapter.fetch_live_models()

            self.assertEqual(len(models), 1)
            self.assertEqual(models[0]["coding_elo"], 1545)
            self.assertEqual(models[0]["vision_elo"], 1480)

    def test_livebench_updates_release_extra_meta(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = LiveBenchFetcher(raw_dir=Path(tmpdir), offline_mode=False)

            def fake_json(url: str, headers: dict | None = None):
                if "contents/public" in url:
                    return [{"name": "table_2026_11_06.csv"}]
                return {"coding": ["lcb"], "math": ["aime"]}

            def fake_text(url: str, headers: dict | None = None, accept: str = "*/*"):
                return "model,lcb,aime\nfuture-model-x,82.0,90.0\n"

            with patch.object(adapter, "request_json", side_effect=fake_json), patch.object(
                adapter, "request_text", side_effect=fake_text
            ):
                snap = adapter.run()

            self.assertEqual(snap["fetch_status"], "live")
            self.assertEqual(snap["release"], "2026-11-06")
            self.assertEqual(snap["models"][0]["model_key"], "future-model-x")

    def test_aa_scrape_handles_missing_cost_and_speed_without_fabrication(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = ArtificialAnalysisFetcher(raw_dir=Path(tmpdir), offline_mode=False)
            sample_html = """
            <table>
              <tr><th>Model</th><th>Context Window</th><th>Creator</th><th>Artificial Analysis Intelligence Index</th><th>Price</th></tr>
              <tr><td><a href="/models/nanbeige4-3-33b">Nanbeige4.3-33B</a></td><td>524k</td><td>Nanbeige</td><td>34.0%</td><td>--</td></tr>
              <tr><td><a href="/models/solar-pro4">Solar Pro 4</a></td><td>512k</td><td>Upstage</td><td>31.2%</td><td>$0.96</td></tr>
            </table>
            """
            with patch.object(adapter, "request_text", return_value=sample_html):
                parsed = adapter._scrape_public_leaderboard()

            self.assertEqual(len(parsed), 2)
            unpriced = parsed[0]
            self.assertEqual(unpriced["model_name"], "Nanbeige4.3-33B")
            self.assertEqual(unpriced["aa_slug"], "nanbeige4-3-33b")
            self.assertEqual(unpriced["context_window"], 524000)
            self.assertIsNone(unpriced["blended_price_per_1m"])
            self.assertIsNone(unpriced["input_price_per_1m"])
            self.assertIsNone(unpriced["output_price_per_1m"])
            self.assertIsNone(unpriced["output_tokens_per_second"])
            self.assertIsNone(unpriced["ttft_seconds"])

            priced = parsed[1]
            self.assertEqual(priced["aa_slug"], "solar-pro4")
            self.assertAlmostEqual(priced["blended_price_per_1m"], 0.576, places=3)
            self.assertIsNone(priced["output_tokens_per_second"])

    def test_merge_with_lkg_preserves_first_seen_and_enriched_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = LiveBenchFetcher(raw_dir=Path(tmpdir), offline_mode=False)
            adapter.latest_path.write_text(
                json.dumps({
                    "fetched_at": "2026-12-01T00:00:00Z",
                    "models": [
                        {
                            "model_key": "glm-5.2",
                            "display_name": "GLM-5.2",
                            "provider": "Z.AI",
                            "first_seen": "2026-11-28",
                            "release_date": "2026-06-16",
                            "open_weights": True,
                            "license": "MIT",
                            "context_window": 1000000,
                            "global_average": 65.0,
                        }
                    ],
                }),
                encoding="utf-8",
            )
            merged = adapter.merge_with_lkg([
                {
                    "model_key": "glm-5.2",
                    "display_name": "glm-5.2",
                    "provider": "Unknown",
                    "global_average": 66.0,
                },
                {
                    "model_key": "brand-new-model",
                    "display_name": "brand-new-model",
                    "provider": "Unknown",
                    "global_average": 70.0,
                },
            ])
            by_key = {m["model_key"]: m for m in merged}
            self.assertEqual(by_key["glm-5.2"]["first_seen"], "2026-11-28")
            self.assertEqual(by_key["glm-5.2"]["release_date"], "2026-06-16")
            self.assertTrue(by_key["glm-5.2"]["open_weights"])
            self.assertEqual(by_key["glm-5.2"]["license"], "MIT")
            self.assertEqual(by_key["glm-5.2"]["context_window"], 1000000)
            self.assertEqual(by_key["glm-5.2"]["display_name"], "GLM-5.2")
            self.assertEqual(by_key["glm-5.2"]["provider"], "Z.AI")
            self.assertIn("first_seen", by_key["brand-new-model"])

    def test_metadata_enricher_header_vs_faq_variant_guard_and_live_run(self) -> None:
        # 1. Strict variant matching blocks Mini/8B/GGUF collisions
        self.assertFalse(is_compatible_variant_match("Apodex 1.1", "apodex/Apodex-1.1-Mini"))
        self.assertFalse(is_compatible_variant_match("Granite 4.2 3B", "ibm-granite/granite-4.2-8b"))
        self.assertFalse(is_compatible_variant_match("Qwen3.6-27B", "Qwen/Qwen3.6-27B-GGUF"))
        self.assertFalse(is_compatible_variant_match("Kimi K2.7 Code", "moonshotai/Kimi-K2.7"))
        self.assertTrue(is_compatible_variant_match("Qwen3.6-27B", "Qwen/Qwen3.6-27B"))
        self.assertTrue(is_compatible_variant_match("Nemotron 3.5 Lightning", "nvidia/NVIDIA-Nemotron-3.5-Lightning"))

        # 2. AA header month supersedes later FAQ benchmark addition date
        jt_html = """
        <div>JT-4.1 Flash 236B A21B · Released July 2026 · Proprietary model</div>
        <p>JT-4.1 Flash 236B A21B was released on Nov 11, 2026 with a 262k context window.</p>
        """
        aa_parsed = parse_aa_model_page(jt_html)
        self.assertEqual(aa_parsed["header_ym"], "2026-07")
        self.assertTrue(aa_parsed["faq_superseded"])
        self.assertEqual(aa_parsed["release_date"], "2026-07-01")
        self.assertFalse(aa_parsed["open_weights"])
        rec = reconcile_enriched_metadata("JT-4.1 Flash 236B A21B", aa_meta=aa_parsed, or_meta={"release_date": "2026-07-09"})
        self.assertEqual(rec["release_date"], "2026-07-09")

        # 3. End-to-end mocked enrich_snapshots updates new/unverified entries while skipping curated ones
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            raw_dir = tmp / "raw"
            aliases_copy = tmp / "model_aliases.json"
            shutil.copy2(ALIASES_PATH, aliases_copy)
            for src in ("artificial_analysis", "livebench", "arena", "vals"):
                (raw_dir / src).mkdir(parents=True, exist_ok=True)
                (raw_dir / src / "latest.json").write_text(json.dumps({"fetched_at": "2026-12-01T00:00:00Z", "models": []}))

            (raw_dir / "artificial_analysis" / "latest.json").write_text(json.dumps({
                "fetched_at": "2026-12-01T00:00:00Z",
                "models": [
                    {
                        "model_name": "FutureOpen 7B",
                        "provider": "Upstage",
                        "aa_slug": "futureopen-7b",
                        "context_window": 128000,
                        "open_weights": False,
                        "intelligence_index": 40.0,
                    }
                ],
            }))

            def fake_json(url: str, headers: dict | None = None, timeout: float = 10.0):
                if "openrouter.ai" in url:
                    return {
                        "data": [
                            {
                                "id": "upstage/futureopen-7b",
                                "name": "FutureOpen 7B",
                                "created": 1785456000,
                                "context_length": 262144,
                                "hugging_face_id": "upstage/FutureOpen-7B",
                            }
                        ]
                    }
                if "huggingface.co/api/models/upstage" in url:
                    return {
                        "id": "upstage/FutureOpen-7B",
                        "createdAt": "2026-07-31T08:00:00.000Z",
                        "tags": ["license:apache-2.0"],
                    }
                return []

            def fake_text(url: str, headers: dict | None = None, timeout: float = 10.0):
                return "<p>FutureOpen 7B Released July 2026. Open weights model released under the Apache 2.0 license.</p>"

            with patch("scripts.ingest.metadata_enricher._http_get_json", side_effect=fake_json), patch(
                "scripts.ingest.metadata_enricher._http_get_text", side_effect=fake_text
            ):
                res = enrich_snapshots(raw_dir=raw_dir, aliases_path=aliases_copy, offline_mode=False)

            self.assertEqual(res["enriched_count"], 1)
            updated = json.loads((raw_dir / "artificial_analysis" / "latest.json").read_text())["models"][0]
            self.assertEqual(updated["release_date"], "2026-07-31")
            self.assertTrue(updated["open_weights"])
            self.assertEqual(updated["license"], "Apache-2.0")
            self.assertEqual(updated["context_window"], 262144)

    def test_aa_scrape_handles_two_row_group_headers_and_doubled_creators(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = ArtificialAnalysisFetcher(raw_dir=Path(tmpdir), offline_mode=False)
            aa_two_row_html = """
            <table>
              <thead>
                <tr><th>Features</th><th>Intelligence</th><th>Price</th><th>Speed</th><th>Latency</th></tr>
                <tr>
                  <th>Model</th><th>Context Window</th><th>Creator</th>
                  <th>Artificial Analysis Intelligence Index</th><th>Cost per TaskUSD</th>
                  <th>Time per TaskMinutes</th><th>First AnswerToken (s)</th><th>Further Analysis</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Claude Fable 5.2 (max)</td><td>1M</td><td>Anthropic Anthropic</td>
                  <td>65</td><td>$26.54</td><td>46.8</td><td>267.23</td>
                  <td><a href="/models/claude-fable-5-2-max">Model</a> · <a href="/models/claude-fable-5-2-max/providers">Providers</a></td>
                </tr>
                <tr>
                  <td>Grok 4.7 (xhigh)</td><td>500k</td><td>SpaceXAI SpaceXAI</td>
                  <td>35</td><td>$7.77</td><td>27.0</td><td>58.37</td>
                  <td><a href="/models/grok-4-7-xhigh">Model</a></td>
                </tr>
                <tr>
                  <td>GLM-5.3 (max)</td><td>1M</td><td>Z AI Z AI</td>
                  <td>32</td><td>$5.01</td><td>27.7</td><td>63.55</td>
                  <td><a href="/models/glm-5-3-max">Model</a></td>
                </tr>
                <tr>
                  <td>K2 Horizon 375B A23B</td><td>524k</td><td>Institute of Foundation Models Institute of Foundation Models</td>
                  <td>18</td><td>$0.00</td><td>4.8</td><td>15.96</td>
                  <td><a href="/models/k2-horizon-375b-a23b">Model</a></td>
                </tr>
                <tr>
                  <td>Muse Wonder Full (max)</td><td>1M</td><td>Meta Meta</td>
                  <td>50</td><td>--</td><td>--</td><td>--</td>
                  <td><a href="/models/muse-wonder-full-max">Model</a></td>
                </tr>
                <tr>
                  <td>JT-35B-Flash</td><td>256k</td><td>China Mobile China Mobile</td>
                  <td>--</td><td>--</td><td>--</td><td>--</td>
                  <td><a href="/models/jt-35b-flash">Model</a></td>
                </tr>
              </tbody>
            </table>
            """
            with patch.object(adapter, "request_text", return_value=aa_two_row_html):
                parsed = adapter._scrape_public_leaderboard()

            self.assertEqual(len(parsed), 5)
            by_name = {m["model_name"]: m for m in parsed}

            fable = by_name["Claude Fable 5.2 (max)"]
            self.assertEqual(fable["provider"], "Anthropic")
            self.assertEqual(fable["context_window"], 1_000_000)
            self.assertEqual(fable["intelligence_index"], 65.0)
            self.assertEqual(fable["aa_slug"], "claude-fable-5-2-max")
            # Time per TaskMinutes (46.8) must NEVER be misread as output_tokens_per_second
            self.assertIsNone(fable["output_tokens_per_second"])
            self.assertEqual(fable["ttft_seconds"], 267.23)

            grok = by_name["Grok 4.7 (xhigh)"]
            self.assertEqual(grok["provider"], "SpaceXAI")
            self.assertEqual(grok["context_window"], 500_000)

            glm = by_name["GLM-5.3 (max)"]
            self.assertEqual(glm["provider"], "Z AI")

            k2 = by_name["K2 Horizon 375B A23B"]
            self.assertEqual(k2["provider"], "Institute of Foundation Models")
            self.assertEqual(k2["context_window"], 524_000)
            self.assertEqual(k2["blended_price_per_1m"], 0.05)

            muse = by_name["Muse Wonder Full (max)"]
            self.assertIsNone(muse["blended_price_per_1m"])
            self.assertIsNone(muse["ttft_seconds"])

    def test_scraped_aa_summary_never_overwrites_existing_api_telemetry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = ArtificialAnalysisFetcher(raw_dir=Path(tmpdir), offline_mode=False)
            adapter.latest_path.write_text(
                json.dumps({
                    "fetched_at": "2026-11-12T00:00:00Z",
                    "models": [
                        {
                            "model_name": "GPT-6 Astra (Max)",
                            "provider": "OpenAI",
                            "context_window": 1000000,
                            "intelligence_index": 57.0,
                            "coding_index": 61.0,
                            "math_index": 70.0,
                            "input_price_per_1m": 15.0,
                            "output_price_per_1m": 42.5,
                            "blended_price_per_1m": 21.88,
                            "output_tokens_per_second": 76.0,
                            "ttft_seconds": 1.45,
                            "release_date": "2026-10-08",
                        },
                        {
                            "model_name": "Gemini 4 Hydrogen (xhigh)",
                            "provider": "Google",
                            "context_window": 1000000,
                            "intelligence_index": 54.0,
                            "coding_index": 60.48,
                            "math_index": 66.96,
                            "input_price_per_1m": 0.948,
                            "output_price_per_1m": 4.74,
                            "blended_price_per_1m": 1.896,
                            "output_tokens_per_second": None,
                            "ttft_seconds": None,
                            "release_date": "2026-11-12",
                        },
                    ],
                }),
                encoding="utf-8",
            )
            merged = adapter.merge_with_lkg([
                {
                    "model_name": "GPT-6 Astra (max)",
                    "provider": "OpenAI",
                    "context_window": 1000000,
                    "intelligence_index": 57.0,
                    "input_price_per_1m": 1.872,
                    "output_price_per_1m": 9.36,
                    "blended_price_per_1m": 3.744,
                    "output_tokens_per_second": None,
                    "ttft_seconds": 228.86,
                    "aa_slug": "gpt-6-astra-max",
                    "_scraped_summary": True,
                },
                {
                    "model_name": "Gemini 4 Hydrogen (xhigh)",
                    "provider": "Google",
                    "context_window": 1000000,
                    "intelligence_index": 54.0,
                    "input_price_per_1m": 0.948,
                    "output_price_per_1m": 4.74,
                    "blended_price_per_1m": 1.896,
                    "output_tokens_per_second": None,
                    "ttft_seconds": 40.55,
                    "aa_slug": "gemini-4-hydrogen-xhigh",
                    "_scraped_summary": True,
                },
            ])
            by_name = {m["model_name"]: m for m in merged}
            astra = by_name["GPT-6 Astra (Max)"]
            self.assertEqual(astra["blended_price_per_1m"], 21.88)
            self.assertEqual(astra["output_tokens_per_second"], 76.0)
            self.assertEqual(astra["ttft_seconds"], 1.45)
            self.assertEqual(astra["aa_slug"], "gpt-6-astra-max")

            hydrogen = by_name["Gemini 4 Hydrogen (xhigh)"]
            self.assertEqual(hydrogen["blended_price_per_1m"], 1.896)
            self.assertIsNone(hydrogen["output_tokens_per_second"])
            self.assertEqual(hydrogen["ttft_seconds"], 40.55)

    def test_arena_hf_dataset_filters_historical_backlog_and_keeps_tracked_models(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = ArenaFetcher(raw_dir=Path(tmpdir), offline_mode=False)
            adapter.latest_path.write_text(
                json.dumps({
                    "fetched_at": "2026-11-12T00:00:00Z",
                    "models": [{"arena_model_id": "meta-llama-3-1-405b-instruct-202610", "display_name": "Llama 3.1 405B", "text_elo": 1284}],
                }),
                encoding="utf-8",
            )

            rows: list[dict] = [
                # Curated/tracked lower-Elo model must always be preserved
                {"row": {"model_name": "llama-3.1-405b-instruct", "organization": "Meta", "category": "overall", "rating": 1284.0, "rank": 210}},
                # Stealth row should be excluded
                {"row": {"model_name": "anonymous-mystery-bot", "organization": "Stealth", "category": "overall", "rating": 1510.0, "rank": 1}},
                # Historical 2023/2024 models should be filtered even with higher votes
                {"row": {"model_name": "gpt-4-turbo-2024-04-09", "organization": "OpenAI", "category": "overall", "rating": 1355.0, "rank": 140}},
            ]
            # 8 recent high-Elo top-160 challengers
            for i in range(8):
                rows.append({"row": {"model_name": f"challenger-2026-{i}", "organization": "Cohere", "category": "overall", "rating": 1450.0 - i, "rank": i + 10}})
            # 220 low-Elo historical backlog rows (rank > 160 & elo < 1350)
            for i in range(220):
                rows.append({"row": {"model_name": f"old-chatbot-{i}", "organization": "LMSYS", "category": "overall", "rating": 1250.0 - (i * 0.5), "rank": 170 + i}})

            all_rows = rows
            def fake_paginated_json(url: str, headers: dict | None = None):
                if "api.wulong.dev" in url or "oolong-tea-2026" in url:
                    raise RuntimeError("Mirror down")
                if "config=text" in url:
                    if "offset=0" in url:
                        return {"num_rows_total": len(all_rows), "rows": all_rows[:100]}
                    if "offset=100" in url:
                        return {"num_rows_total": len(all_rows), "rows": all_rows[100:200]}
                    if "offset=200" in url:
                        return {"num_rows_total": len(all_rows), "rows": all_rows[200:]}
                return {"num_rows_total": 0, "rows": []}

            with patch.object(adapter, "request_json", side_effect=fake_paginated_json):
                models = adapter.fetch_live_models()

            ids = {m["arena_model_id"] for m in models}
            self.assertIn("llama-3.1-405b-instruct", ids)
            for i in range(8):
                self.assertIn(f"challenger-2026-{i}", ids)
            self.assertNotIn("gpt-4-turbo-2024-04-09", ids)
            self.assertNotIn("anonymous-mystery-bot", ids)
            self.assertEqual(len(ids), 9)

    def test_metadata_enricher_blocks_closed_lab_unlinked_hf_and_low_download_spam(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            raw_dir = tmp / "raw"
            aliases_copy = tmp / "model_aliases.json"
            shutil.copy2(ALIASES_PATH, aliases_copy)
            for src in ("artificial_analysis", "livebench", "arena", "vals"):
                (raw_dir / src).mkdir(parents=True, exist_ok=True)
                (raw_dir / src / "latest.json").write_text(json.dumps({"fetched_at": "2026-12-01T00:00:00Z", "models": []}))

            (raw_dir / "arena" / "latest.json").write_text(json.dumps({
                "fetched_at": "2026-12-01T00:00:00Z",
                "models": [
                    {"arena_model_id": "claude-future-9", "display_name": "Claude Future 9", "organization": "Anthropic"},
                    {"arena_model_id": "spam-open-7b", "display_name": "Spam Open 7B", "organization": "Upstage"},
                ],
            }))

            def fake_json(url: str, headers: dict | None = None, timeout: float = 10.0):
                if "openrouter.ai" in url:
                    return {"data": []}
                if "huggingface.co/api/models?search=" in url:
                    if "claude" in url.lower():
                        return [{"id": "fake/Claude-Future-9", "downloads": 5000, "createdAt": "2026-12-01T00:00:00Z", "tags": ["license:mit"]}]
                    if "spam" in url.lower():
                        return [{"id": "fake/Spam-Open-7B", "downloads": 3, "createdAt": "2026-12-01T00:00:00Z", "tags": ["license:apache-2.0"]}]
                return []

            with patch("scripts.ingest.metadata_enricher._http_get_json", side_effect=fake_json):
                res = enrich_snapshots(raw_dir=raw_dir, aliases_path=aliases_copy, offline_mode=False)

            self.assertEqual(res["enriched_count"], 0)
            arena_models = json.loads((raw_dir / "arena" / "latest.json").read_text())["models"]
            self.assertFalse(arena_models[0].get("open_weights", False))
            self.assertIsNone(arena_models[0].get("license"))
            self.assertFalse(arena_models[1].get("open_weights", False))
            self.assertIsNone(arena_models[1].get("license"))


if __name__ == "__main__":
    unittest.main()
