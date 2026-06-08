import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import approval_ledger


class ApprovalLedgerTests(unittest.TestCase):
    def test_list_approval_events_returns_recent_entries(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger_file = Path(temp_dir) / "logs" / "approval_ledger.jsonl"

            with patch.object(approval_ledger, "LEDGER_FILE", ledger_file):
                approval_ledger.record_approval_event({
                    "event_type": "agent_safety_evaluated",
                    "decision": "ALLOW",
                })
                approval_ledger.record_approval_event({
                    "event_type": "agent_safety_blocked",
                    "decision": "BLOCK",
                })

                events = approval_ledger.list_approval_events(limit=1)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "agent_safety_blocked")
        self.assertEqual(events[0]["decision"], "BLOCK")
        self.assertFalse(events[0]["capital_execution"])


if __name__ == "__main__":
    unittest.main()
