import csv
import os
import tempfile
import unittest

import audit_logger


class AuditLoggerTests(unittest.TestCase):
    def test_route_decision_log_is_created_and_appended(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_log_file = audit_logger.LOG_FILE
            logs_dir = os.path.join(temp_dir, "logs")
            os.makedirs(logs_dir, exist_ok=True)
            audit_logger.LOG_FILE = os.path.join(logs_dir, "route_decisions.csv")

            try:
                audit_logger.log_route_decision(
                    task="unit task",
                    task_type="general",
                    provider="UnitProvider",
                    latency=0.25,
                    estimated_cost=0.001,
                    status="verified_live_response"
                )

                with open(audit_logger.LOG_FILE, "r", encoding="utf-8") as file:
                    rows = list(csv.DictReader(file))

                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["task"], "unit task")
                self.assertEqual(rows[0]["provider"], "UnitProvider")
            finally:
                audit_logger.LOG_FILE = original_log_file


if __name__ == "__main__":
    unittest.main()
