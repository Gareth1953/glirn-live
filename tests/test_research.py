import json
import os
import tempfile
import unittest
from unittest.mock import patch

from research import converter
from research import intake, store
from research.models import ResearchItem
from research import sources


class ResearchTests(unittest.TestCase):
    def test_research_item_round_trips_dict(self):
        item = ResearchItem.create(
            source="unit",
            title="Provider pricing monitor",
            url="internal://research/provider-pricing",
            summary="Review only.",
            category="provider_pricing_changes",
            relevance_score=0.8
        )

        data = item.to_dict()
        restored = ResearchItem.from_dict(data)

        self.assertEqual(restored.to_dict(), data)
        self.assertEqual(set(data.keys()), {
            "id",
            "source",
            "title",
            "url",
            "summary",
            "category",
            "relevance_score",
            "created_at"
        })

    def test_store_persists_jsonl_and_lists_recent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_file = store.RESEARCH_FILE
            store.RESEARCH_FILE = os.path.join(temp_dir, "research_items.jsonl")

            try:
                first = ResearchItem.create(
                    source="unit",
                    title="First",
                    url="internal://first",
                    summary="First summary.",
                    category="ai_infrastructure_arbitrage",
                    relevance_score=0.6
                )
                second = ResearchItem.create(
                    source="unit",
                    title="Second",
                    url="internal://second",
                    summary="Second summary.",
                    category="latency_optimisation",
                    relevance_score=0.7
                )

                store.append_research_items([first, second])
                listed = store.list_research_items(limit=1)

                self.assertEqual(len(listed), 1)
                self.assertEqual(listed[0].title, "Second")

                with open(store.RESEARCH_FILE, "r", encoding="utf-8") as file:
                    rows = [json.loads(line) for line in file]

                self.assertEqual(len(rows), 2)
            finally:
                store.RESEARCH_FILE = original_file

    def test_stub_intake_creates_non_crypto_research_items(self):
        with patch("research.intake.append_research_items", side_effect=lambda items: items) as append:
            items = intake.intake_research_items()

        categories = {item.category for item in items}
        summaries = " ".join(item.summary.lower() for item in items)

        self.assertEqual(len(items), 4)
        self.assertIn("ai_infrastructure_arbitrage", categories)
        self.assertIn("provider_pricing_changes", categories)
        self.assertIn("enterprise_ai_orchestration", categories)
        self.assertIn("latency_optimisation", categories)
        self.assertIn("non-crypto", summaries)
        self.assertTrue(all("crypto" not in item.category for item in items))
        append.assert_called_once()

    def test_converter_creates_opportunities_for_high_relevance_research_only(self):
        high = ResearchItem.create(
            source="unit",
            title="AI infrastructure arbitrage watchlist",
            url="internal://high",
            summary="Review capacity arbitrage.",
            category="ai_infrastructure_arbitrage",
            relevance_score=0.91
        )
        low = ResearchItem.create(
            source="unit",
            title="Low relevance item",
            url="internal://low",
            summary="Ignore this.",
            category="latency_optimisation",
            relevance_score=0.5
        )

        with patch("research.converter.list_research_items", return_value=[high, low]), \
                patch("research.converter.append_opportunities", side_effect=lambda items: items) as append:
            opportunities = converter.convert_research_to_opportunities(limit=20)

        self.assertEqual(len(opportunities), 1)
        self.assertEqual(opportunities[0].source, f"research:{high.id}")
        self.assertEqual(opportunities[0].category, "ai_infrastructure")
        self.assertEqual(opportunities[0].status, "pending_review")
        self.assertEqual(opportunities[0].recommended_action, "review")
        self.assertNotIn("crypto", opportunities[0].category)
        append.assert_called_once()

    def test_converter_can_return_no_opportunities(self):
        low = ResearchItem.create(
            source="unit",
            title="Low relevance item",
            url="internal://low",
            summary="Ignore this.",
            category="latency_optimisation",
            relevance_score=0.5
        )

        with patch("research.converter.list_research_items", return_value=[low]), \
                patch("research.converter.append_opportunities", side_effect=lambda items: items):
            opportunities = converter.convert_research_to_opportunities(limit=20)

        self.assertEqual(opportunities, [])

    def test_research_sources_load_and_toggle_local_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "research_sources.json")
            source_config = {
                "sources": [
                    {
                        "name": "AI Infrastructure News",
                        "category": "ai_infrastructure_news",
                        "url": "https://example.com/ai",
                        "enabled": False,
                        "refresh_cadence": "daily",
                        "notes": "No scraping."
                    }
                ]
            }

            with open(path, "w", encoding="utf-8") as file:
                json.dump(source_config, file)

            loaded = sources.load_research_sources(path)
            toggled = sources.toggle_research_source("AI Infrastructure News", path)
            reloaded = sources.load_research_sources(path)

        self.assertEqual(loaded[0]["name"], "AI Infrastructure News")
        self.assertTrue(toggled["enabled"])
        self.assertTrue(reloaded[0]["enabled"])

    def test_research_source_toggle_returns_none_for_unknown_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "research_sources.json")

            with open(path, "w", encoding="utf-8") as file:
                json.dump({"sources": []}, file)

            result = sources.toggle_research_source("Missing Source", path)

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
