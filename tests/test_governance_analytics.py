import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import governance_analytics


class GovernanceAnalyticsTests(unittest.TestCase):
    def write_jsonl(self, path, rows):
        path.parent.mkdir(exist_ok=True)

        with path.open("w", encoding="utf-8") as file:
            for row in rows:
                file.write(json.dumps(row) + "\n")

    def test_get_governance_analytics_summarizes_approval_activity(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            queue_file = Path(temp_dir) / "approvals" / "approval_queue.jsonl"
            ledger_file = Path(temp_dir) / "logs" / "approval_ledger.jsonl"

            self.write_jsonl(queue_file, [
                {
                    "approval_id": "pending-1",
                    "created_at": "2026-05-29T06:00:00+00:00",
                    "status": "pending_user_approval",
                    "route_result": {
                        "provider": "OpenAI_Test",
                        "task_type": "general"
                    },
                    "decision": None,
                    "decided_at": None,
                    "capital_execution": False
                },
                {
                    "approval_id": "approved-1",
                    "created_at": "2026-05-29T01:00:00+00:00",
                    "status": "user_approved",
                    "route_result": {
                        "provider": "OpenAI_Test",
                        "task_type": "general"
                    },
                    "decision": "approved",
                    "decided_at": "2026-05-29T03:00:00+00:00",
                    "capital_execution": False
                },
                {
                    "approval_id": "rejected-1",
                    "created_at": "2026-05-29T02:00:00+00:00",
                    "status": "user_rejected",
                    "route_result": {
                        "provider_name": "Anthropic_Test",
                        "task_type": "research"
                    },
                    "decision": "rejected",
                    "decided_at": "2026-05-29T05:00:00+00:00",
                    "capital_execution": False
                }
            ])
            self.write_jsonl(ledger_file, [
                {
                    "timestamp": "2026-05-29T03:00:00+00:00",
                    "event_type": "approval_decision",
                    "approval_id": "approved-1",
                    "decision": "approved",
                    "provider": "OpenAI_Test",
                    "task_type": "general",
                    "capital_execution": False
                },
                {
                    "timestamp": "2026-05-29T05:00:00+00:00",
                    "event_type": "approval_decision",
                    "approval_id": "rejected-1",
                    "decision": "rejected",
                    "provider": "Anthropic_Test",
                    "task_type": "research",
                    "capital_execution": False
                }
            ])

            with patch.object(governance_analytics, "QUEUE_FILE", queue_file), \
                    patch.object(governance_analytics, "LEDGER_FILE", ledger_file):
                analytics = governance_analytics.get_governance_analytics(
                    now=datetime(2026, 5, 29, 8, 0, tzinfo=timezone.utc)
                )

        self.assertEqual(analytics["pending_count"], 1)
        self.assertEqual(analytics["approved_count"], 1)
        self.assertEqual(analytics["rejected_count"], 1)
        self.assertEqual(analytics["approval_rate"], 50)
        self.assertEqual(analytics["average_approval_hours"], 2)
        self.assertEqual(analytics["average_rejection_hours"], 3)
        self.assertEqual(analytics["oldest_pending_hours"], 2)
        self.assertEqual(analytics["approvals_by_provider"], {"OpenAI_Test": 1})
        self.assertEqual(analytics["rejections_by_provider"], {"Anthropic_Test": 1})
        self.assertEqual(analytics["approvals_by_task_type"], {"general": 1})
        self.assertEqual(analytics["rejections_by_task_type"], {"research": 1})
        self.assertFalse(analytics["capital_execution"])


if __name__ == "__main__":
    unittest.main()
