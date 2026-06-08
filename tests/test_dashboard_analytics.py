import csv
import os
import tempfile
import unittest

import dashboard


class DashboardAnalyticsTests(unittest.TestCase):
    def test_routing_history_aggregates_route_decisions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_route_log = dashboard.ROUTE_DECISIONS_LOG_FILE
            dashboard.ROUTE_DECISIONS_LOG_FILE = os.path.join(temp_dir, "route_decisions.csv")

            try:
                with open(dashboard.ROUTE_DECISIONS_LOG_FILE, "w", newline="", encoding="utf-8") as file:
                    writer = csv.DictWriter(file, fieldnames=[
                        "timestamp",
                        "task",
                        "task_type",
                        "provider",
                        "latency",
                        "estimated_cost",
                        "status"
                    ])
                    writer.writeheader()
                    writer.writerow({
                        "timestamp": "2026-05-27T00:00:00+00:00",
                        "task": "one",
                        "task_type": "general",
                        "provider": "OpenAI_Test",
                        "latency": "0.2",
                        "estimated_cost": "0.001",
                        "status": "verified_live_response"
                    })
                    writer.writerow({
                        "timestamp": "2026-05-27T00:01:00+00:00",
                        "task": "two",
                        "task_type": "general",
                        "provider": "OpenAI_Test",
                        "latency": "0.4",
                        "estimated_cost": "0.003",
                        "status": "verified_live_response"
                    })
                    writer.writerow({
                        "timestamp": "2026-05-27T00:02:00+00:00",
                        "task": "three",
                        "task_type": "general",
                        "provider": "Anthropic_Test",
                        "latency": "1.0",
                        "estimated_cost": "0.006",
                        "status": "verified_live_response"
                    })

                result = dashboard.get_routing_history_data(limit=2)

                self.assertEqual(result["total_route_count"], 3)
                self.assertEqual(result["provider_win_counts"], {
                    "OpenAI_Test": 2,
                    "Anthropic_Test": 1
                })
                self.assertAlmostEqual(result["average_latency_per_provider"]["OpenAI_Test"], 0.3)
                self.assertAlmostEqual(result["average_cost_per_provider"]["OpenAI_Test"], 0.002)
                self.assertEqual(len(result["recent_routing_history"]), 2)
                self.assertEqual(result["recent_routing_history"][0]["task"], "two")
            finally:
                dashboard.ROUTE_DECISIONS_LOG_FILE = original_route_log


if __name__ == "__main__":
    unittest.main()
