import unittest

from glirn_internal_learning import (
    approve_learning_insight,
    capture_learning_outcome,
    generate_improvement_insights,
)


class InternalLearningTests(unittest.TestCase):
    def test_captures_gareth_decision_and_completed_brief_outcome(self):
        record = capture_learning_outcome(
            "decision-113",
            "brief-113",
            "DECLINE",
            "unsuccessful",
            "declined_after_remediation",
            "Contact person@example.com or +44 7700 900123 for details.",
            ["ethical risk", "client fit"],
            captured_at="2026-06-13T12:00:00+00:00",
        )
        self.assertEqual(record["decision_by"], "Gareth")
        self.assertEqual(record["gareth_decision"], "DECLINE")
        self.assertIn("[redacted email]", record["outcome_summary"])
        self.assertIn("[redacted phone]", record["outcome_summary"])
        self.assertTrue(record["candidate_data_minimised"])

    def test_generates_improvement_insights_from_declines_and_remediation(self):
        records = [
            capture_learning_outcome(
                "decision-1", "brief-1", "DECLINE", "not_completed", "declined_after_remediation",
                "Risk remained unresolved.", ["ethical_risk"]
            ),
            capture_learning_outcome(
                "decision-2", "brief-2", "ACCEPT", "partially_successful", "resolved",
                "Remediation improved the brief.", ["ethical_risk"]
            ),
        ]
        insight = generate_improvement_insights(records, generated_at="2026-06-13T13:00:00+00:00")
        self.assertEqual(insight["outcome_count"], 2)
        self.assertTrue(any("ethical_risk" in item for item in insight["recommendation_improvement_insights"]))
        self.assertEqual(insight["status"], "awaiting_gareth_approval")
        self.assertFalse(insight["knowledge_or_policy_updated"])

    def test_insight_approval_is_manual_consideration_only(self):
        insight = generate_improvement_insights([])
        approval = approve_learning_insight(insight, "Review manually before changing guidance.")
        self.assertEqual(approval["approved_by"], "Gareth")
        self.assertTrue(approval["approved_for_manual_consideration"])
        self.assertFalse(approval["knowledge_or_policy_updated"])
        self.assertFalse(approval["automatic_action_executed"])

    def test_all_autonomous_actions_remain_disabled(self):
        record = capture_learning_outcome(
            "decision-3", "brief-3", "ACCEPT", "successful", "not_required", "Completed successfully."
        )
        for field in (
            "autonomous_decision_making_enabled", "automatic_outreach_enabled",
            "automatic_referral_enabled", "automatic_payment_enabled",
            "automatic_delivery_enabled", "external_commitments_enabled",
        ):
            self.assertFalse(record[field])

    def test_invalid_outcomes_are_rejected(self):
        with self.assertRaises(ValueError):
            capture_learning_outcome("id", "brief", "AUTO", "successful", "not_required", "Summary")
        with self.assertRaises(ValueError):
            capture_learning_outcome("id", "brief", "ACCEPT", "unknown", "not_required", "Summary")


if __name__ == "__main__":
    unittest.main()
