import json
import os
import tempfile
import unittest
from unittest.mock import patch

from opportunities.evaluator import evaluate_opportunity
from opportunities.models import Opportunity, OpportunityApproval
from opportunities import scanner, store


class OpportunityTests(unittest.TestCase):
    def test_opportunity_model_round_trips_dict(self):
        opportunity = Opportunity.create(
            source="unit",
            category="ai_infrastructure",
            title="Inference capacity review",
            description="Requires human approval before any action.",
            confidence=0.8,
            estimated_value=100.0,
            risk_level="low"
        )

        data = opportunity.to_dict()
        restored = Opportunity.from_dict(data)

        self.assertEqual(restored.to_dict(), data)
        self.assertEqual(data["status"], "pending_review")
        self.assertEqual(set(data.keys()), {
            "id",
            "source",
            "category",
            "title",
            "description",
            "confidence",
            "estimated_value",
            "risk_level",
            "status",
            "created_at",
            "confidence_reason",
            "estimated_cost",
            "estimated_benefit",
            "risk_notes",
            "recommended_action"
        })
        self.assertEqual(data["recommended_action"], "review")

    def test_opportunity_rejects_invalid_recommended_action(self):
        with self.assertRaises(ValueError):
            Opportunity.create(
                source="unit",
                category="ai_infrastructure",
                title="Invalid action",
                description="Review only.",
                confidence=0.8,
                estimated_value=100.0,
                risk_level="low",
                recommended_action="execute"
            )

    def test_evaluator_adds_review_fields_without_execution(self):
        opportunity = Opportunity.create(
            source="unit",
            category="ai_infrastructure",
            title="Inference capacity review",
            description="Requires human approval before any action.",
            confidence=0.8,
            estimated_value=1000.0,
            risk_level="low"
        )

        evaluated = evaluate_opportunity(opportunity)

        self.assertEqual(evaluated.recommended_action, "review")
        self.assertGreater(evaluated.estimated_benefit, 0)
        self.assertGreater(evaluated.estimated_cost, 0)
        self.assertIn("confidence=0.8", evaluated.confidence_reason)
        self.assertIn("no capital execution", evaluated.risk_notes.lower())

    def test_evaluator_can_recommend_monitor_or_reject(self):
        monitor = Opportunity.create(
            source="unit",
            category="ai_infrastructure",
            title="Monitor item",
            description="Review only.",
            confidence=0.6,
            estimated_value=1000.0,
            risk_level="low"
        )
        reject = Opportunity.create(
            source="unit",
            category="ai_infrastructure",
            title="Reject item",
            description="Review only.",
            confidence=0.8,
            estimated_value=1000.0,
            risk_level="high"
        )

        self.assertEqual(evaluate_opportunity(monitor).recommended_action, "monitor")
        self.assertEqual(evaluate_opportunity(reject).recommended_action, "reject")

    def test_approval_model_round_trips_dict_without_capital_execution(self):
        approval = OpportunityApproval.create(
            opportunity_id="opp-1",
            action="approve",
            status="approved_human_review",
            reviewer_note="Approved for follow-up."
        )

        data = approval.to_dict()
        restored = OpportunityApproval.from_dict(data)

        self.assertEqual(restored.to_dict(), data)
        self.assertFalse(data["capital_execution"])
        self.assertEqual(data["action"], "approve")
        self.assertEqual(data["reviewer_note"], "Approved for follow-up.")
        self.assertIsNone(data["realized_value"])

    def test_approval_model_loads_legacy_dict_without_optional_fields(self):
        approval = OpportunityApproval.from_dict({
            "id": "approval-1",
            "opportunity_id": "opp-1",
            "action": "approve",
            "status": "approved_human_review",
            "capital_execution": False,
            "created_at": "2026-05-28T00:00:00+00:00"
        })

        self.assertEqual(approval.reviewer_note, "")
        self.assertIsNone(approval.realized_value)

    def test_store_persists_jsonl_and_lists_recent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_file = store.OPPORTUNITIES_FILE
            store.OPPORTUNITIES_FILE = os.path.join(temp_dir, "opportunities.jsonl")

            try:
                first = Opportunity.create(
                    source="unit",
                    category="ai_infrastructure",
                    title="First review",
                    description="Review only.",
                    confidence=0.5,
                    estimated_value=10.0,
                    risk_level="low"
                )
                second = Opportunity.create(
                    source="unit",
                    category="ai_infrastructure",
                    title="Second review",
                    description="Review only.",
                    confidence=0.6,
                    estimated_value=20.0,
                    risk_level="medium"
                )

                store.append_opportunities([first, second])
                listed = store.list_opportunities(limit=1)

                self.assertEqual(len(listed), 1)
                self.assertEqual(listed[0].title, "Second review")

                with open(store.OPPORTUNITIES_FILE, "r", encoding="utf-8") as file:
                    rows = [json.loads(line) for line in file]

                self.assertEqual(len(rows), 2)
                self.assertEqual(rows[0]["status"], "pending_review")
            finally:
                store.OPPORTUNITIES_FILE = original_file

    def test_record_opportunity_approval_updates_status_and_writes_ledger(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_opportunities_file = store.OPPORTUNITIES_FILE
            original_approvals_file = store.APPROVALS_FILE
            store.OPPORTUNITIES_FILE = os.path.join(temp_dir, "opportunities.jsonl")
            store.APPROVALS_FILE = os.path.join(temp_dir, "opportunity_approvals.jsonl")

            try:
                opportunity = Opportunity.create(
                    source="unit",
                    category="ai_infrastructure",
                    title="Review item",
                    description="Review only.",
                    confidence=0.7,
                    estimated_value=50.0,
                    risk_level="low"
                )
                store.append_opportunity(opportunity)

                updated, approval = store.record_opportunity_approval(
                    opportunity.id,
                    "approve",
                    reviewer_note="Approved for follow-up."
                )

                self.assertEqual(updated.status, "approved_human_review")
                self.assertEqual(approval.opportunity_id, opportunity.id)
                self.assertEqual(approval.action, "approve")
                self.assertEqual(approval.status, "approved_human_review")
                self.assertEqual(approval.reviewer_note, "Approved for follow-up.")
                self.assertFalse(approval.capital_execution)

                listed = store.list_opportunities(limit=1)
                approvals = store.list_approvals(limit=1)

                self.assertEqual(listed[0].status, "approved_human_review")
                self.assertEqual(approvals[0].status, "approved_human_review")
                self.assertEqual(approvals[0].reviewer_note, "Approved for follow-up.")
            finally:
                store.OPPORTUNITIES_FILE = original_opportunities_file
                store.APPROVALS_FILE = original_approvals_file

    def test_record_opportunity_rejection_updates_status(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_opportunities_file = store.OPPORTUNITIES_FILE
            original_approvals_file = store.APPROVALS_FILE
            store.OPPORTUNITIES_FILE = os.path.join(temp_dir, "opportunities.jsonl")
            store.APPROVALS_FILE = os.path.join(temp_dir, "opportunity_approvals.jsonl")

            try:
                opportunity = Opportunity.create(
                    source="unit",
                    category="ai_infrastructure",
                    title="Review item",
                    description="Review only.",
                    confidence=0.7,
                    estimated_value=50.0,
                    risk_level="low"
                )
                store.append_opportunity(opportunity)

                updated, approval = store.record_opportunity_approval(opportunity.id, "reject")

                self.assertEqual(updated.status, "rejected_human_review")
                self.assertEqual(approval.action, "reject")
                self.assertEqual(approval.status, "rejected_human_review")
            finally:
                store.OPPORTUNITIES_FILE = original_opportunities_file
                store.APPROVALS_FILE = original_approvals_file

    def test_record_opportunity_approval_returns_none_for_missing_id(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_opportunities_file = store.OPPORTUNITIES_FILE
            original_approvals_file = store.APPROVALS_FILE
            store.OPPORTUNITIES_FILE = os.path.join(temp_dir, "opportunities.jsonl")
            store.APPROVALS_FILE = os.path.join(temp_dir, "opportunity_approvals.jsonl")

            try:
                updated, approval = store.record_opportunity_approval("missing", "approve")

                self.assertIsNone(updated)
                self.assertIsNone(approval)
                self.assertFalse(os.path.exists(store.APPROVALS_FILE))
            finally:
                store.OPPORTUNITIES_FILE = original_opportunities_file
                store.APPROVALS_FILE = original_approvals_file

    def test_record_opportunity_outcome_updates_status_and_writes_ledger(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_opportunities_file = store.OPPORTUNITIES_FILE
            original_approvals_file = store.APPROVALS_FILE
            store.OPPORTUNITIES_FILE = os.path.join(temp_dir, "opportunities.jsonl")
            store.APPROVALS_FILE = os.path.join(temp_dir, "opportunity_approvals.jsonl")

            try:
                opportunity = Opportunity.create(
                    source="unit",
                    category="ai_infrastructure",
                    title="Review item",
                    description="Review only.",
                    confidence=0.7,
                    estimated_value=50.0,
                    risk_level="low"
                )
                store.append_opportunity(opportunity)

                updated, approval = store.record_opportunity_outcome(
                    opportunity.id,
                    "monitored",
                    reviewer_note="Watch for changes.",
                    realized_value=12.5
                )

                self.assertEqual(updated.status, "monitored")
                self.assertEqual(approval.action, "outcome")
                self.assertEqual(approval.status, "monitored")
                self.assertEqual(approval.reviewer_note, "Watch for changes.")
                self.assertEqual(approval.realized_value, 12.5)
                self.assertFalse(approval.capital_execution)

                listed = store.list_opportunities(limit=1)
                approvals = store.list_approvals(limit=1)

                self.assertEqual(listed[0].status, "monitored")
                self.assertEqual(approvals[0].status, "monitored")
                self.assertEqual(approvals[0].realized_value, 12.5)
            finally:
                store.OPPORTUNITIES_FILE = original_opportunities_file
                store.APPROVALS_FILE = original_approvals_file

    def test_record_opportunity_outcome_rejects_invalid_status(self):
        with self.assertRaises(ValueError):
            store.record_opportunity_outcome("opp-1", "executed")

    def test_get_opportunity_analytics_summarizes_opportunities_and_outcomes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_opportunities_file = store.OPPORTUNITIES_FILE
            original_approvals_file = store.APPROVALS_FILE
            store.OPPORTUNITIES_FILE = os.path.join(temp_dir, "opportunities.jsonl")
            store.APPROVALS_FILE = os.path.join(temp_dir, "opportunity_approvals.jsonl")

            try:
                first = Opportunity.create(
                    source="unit",
                    category="ai_infrastructure",
                    title="First review",
                    description="Review only.",
                    confidence=0.8,
                    estimated_value=1000.0,
                    risk_level="low",
                    estimated_benefit=750.0,
                    recommended_action="review"
                )
                second = Opportunity.create(
                    source="unit",
                    category="ai_infrastructure",
                    title="Second review",
                    description="Review only.",
                    confidence=0.6,
                    estimated_value=500.0,
                    risk_level="medium",
                    estimated_benefit=300.0,
                    recommended_action="monitor"
                )
                store.append_opportunities([first, second])
                store.record_opportunity_approval(first.id, "approve")
                store.record_opportunity_approval(second.id, "reject")
                store.record_opportunity_outcome(first.id, "monitored", realized_value=125.25)

                analytics = store.get_opportunity_analytics()

                self.assertEqual(analytics["total_opportunities"], 2)
                self.assertEqual(analytics["count_by_status"], {
                    "monitored": 1,
                    "rejected_human_review": 1
                })
                self.assertEqual(analytics["count_by_recommended_action"], {
                    "review": 1,
                    "monitor": 1
                })
                self.assertEqual(analytics["average_confidence"], 0.7)
                self.assertEqual(analytics["total_estimated_value"], 1500.0)
                self.assertEqual(analytics["total_estimated_benefit"], 1050.0)
                self.assertEqual(analytics["total_realized_value"], 125.25)
                self.assertEqual(analytics["approval_counts"], {
                    "approved": 1,
                    "rejected": 1,
                    "monitored": 1
                })
                self.assertFalse(analytics["capital_execution"])
            finally:
                store.OPPORTUNITIES_FILE = original_opportunities_file
                store.APPROVALS_FILE = original_approvals_file

    def test_stub_scanner_creates_ai_infrastructure_review_items(self):
        with patch("opportunities.scanner.append_opportunities", side_effect=lambda items: items) as append:
            results = scanner.scan_opportunities()

        self.assertEqual(len(results), 2)
        self.assertTrue(all(item.category == "ai_infrastructure" for item in results))
        self.assertTrue(all(item.status == "pending_review" for item in results))
        self.assertTrue(all("human approval" in item.description.lower() for item in results))
        self.assertTrue(all(item.recommended_action in {"review", "monitor", "reject"} for item in results))
        self.assertTrue(all(item.confidence_reason for item in results))
        self.assertTrue(all(item.risk_notes for item in results))
        append.assert_called_once()


if __name__ == "__main__":
    unittest.main()
