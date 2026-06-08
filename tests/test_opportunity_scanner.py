import unittest

import opportunity_scanner


class OpportunityScannerTests(unittest.TestCase):
    def test_scanner_returns_wasted_money_stub_for_each_supported_category(self):
        results = opportunity_scanner.get_scanner_results()
        categories = {
            opportunity["category"]
            for opportunity in results["opportunities"]
        }

        self.assertEqual(categories, set(opportunity_scanner.OPPORTUNITY_CATEGORIES))
        self.assertEqual(results["analytics"]["opportunities_scanned"], 7)
        self.assertEqual(results["analytics"]["passed_filters"], 7)
        self.assertEqual(results["analytics"]["worth_reviewing"], 7)
        self.assertEqual(results["analytics"]["total_wasted_money_opportunities"], 7)
        self.assertEqual(results["analytics"]["average_estimated_annual_savings"], 9000)
        self.assertEqual(
            results["analytics"]["highest_value_opportunity"]["title"],
            "Excess AI/API Spend"
        )
        self.assertGreater(results["analytics"]["average_gareth_score"], 80)

        for opportunity in results["opportunities"]:
            self.assertIn("estimated_annual_savings", opportunity)
            self.assertIn(opportunity["implementation_difficulty"], {"low", "medium", "high"})
            self.assertGreaterEqual(opportunity["gareth_score"], 0)
            self.assertLessEqual(opportunity["gareth_score"], 100)
            self.assertGreaterEqual(opportunity["confidence"], 0)
            self.assertLessEqual(opportunity["confidence"], 100)

        self.assertFalse(results["capital_execution"])
        self.assertFalse(results["fetching_enabled"])
        self.assertFalse(results["scraping_enabled"])
        self.assertFalse(results["execution_enabled"])


if __name__ == "__main__":
    unittest.main()
