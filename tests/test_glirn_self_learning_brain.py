import unittest

from glirn_self_learning_brain import (
    apply_gareth_learning_decision,
    generate_governed_learning_snapshot,
)


class SelfLearningBrainTests(unittest.TestCase):
    def _snapshot(self):
        return generate_governed_learning_snapshot(
            decline_decisions=[{
                "decision_id": "decision-1",
                "system_recommendation": "ACCEPT",
                "final_decision": "MORE_INFORMATION_REQUIRED",
                "decision_by": "Gareth",
                "gareth_approved": True,
            }],
            human_reviews=[{
                "human_review_id": "review-1",
                "reviewer": "Gareth",
                "outcome": "changes_required",
            }],
            learning_outcomes=[{
                "learning_outcome_id": "outcome-1",
                "decision_by": "Gareth",
                "decline_reason_codes": ["evidence_insufficient"],
                "remediation_outcome": "resolved",
            }],
            external_intelligence=[{
                "external_intelligence_id": "external-1",
                "topic": "Professional conduct guidance",
            }],
            knowledge_updates=[{
                "external_intelligence_id": "external-1",
                "approved_by": "Gareth",
                "knowledge_base_status": "approved_for_manual_use",
            }],
            opportunity_intelligence=[{
                "opportunity_intelligence_id": "opportunity-1",
                "categories": ["law_firm_growth"],
            }],
            opportunity_decisions=[{
                "opportunity_intelligence_id": "opportunity-1",
                "decision": "MONITOR",
                "decision_by": "Gareth",
            }],
            generated_at="2026-06-14T10:00:00+00:00",
        )

    def test_learns_from_all_governed_source_groups(self):
        snapshot = self._snapshot()
        self.assertEqual(snapshot["source_counts"], {
            "gareth_decisions": 1,
            "completed_reviews": 1,
            "learning_outcomes": 1,
            "approved_external_intelligence": 1,
            "gareth_opportunity_outcomes": 1,
        })
        pattern_types = {item["pattern_type"] for item in snapshot["recommendation_patterns"]}
        self.assertIn("gareth_correction", pattern_types)
        self.assertIn("decline_reason", pattern_types)
        self.assertIn("remediation_outcome", pattern_types)
        self.assertIn("approved_external_intelligence", pattern_types)
        self.assertIn("opportunity_outcome", pattern_types)

    def test_unapproved_or_non_gareth_records_are_excluded(self):
        snapshot = generate_governed_learning_snapshot(
            decline_decisions=[{
                "decision_by": "System", "gareth_approved": False, "final_decision": "ACCEPT"
            }],
            human_reviews=[{"reviewer": "Other", "outcome": "declined"}],
            external_intelligence=[{"external_intelligence_id": "unapproved", "topic": "Topic"}],
            knowledge_updates=[],
            opportunity_intelligence=[{"opportunity_intelligence_id": "opp", "categories": ["partner_movement"]}],
            opportunity_decisions=[{"opportunity_intelligence_id": "opp", "decision_by": "System"}],
        )
        self.assertEqual(sum(snapshot["source_counts"].values()), 0)
        self.assertEqual(snapshot["recommendation_patterns"][0]["pattern_type"], "insufficient_history")

    def test_confidence_is_explained_and_advisory_only(self):
        snapshot = self._snapshot()
        self.assertGreater(snapshot["confidence_score"], 0)
        self.assertIn("governed source groups", snapshot["confidence_explanation"])
        self.assertTrue(snapshot["advisory_only"])
        self.assertEqual(snapshot["approval_status"], "awaiting_gareth_approval")
        self.assertTrue(snapshot["gareth_approval_required"])
        self.assertFalse(snapshot["legal_advice_provided"])
        self.assertFalse(snapshot["compliance_rules_updated"])
        self.assertFalse(snapshot["decision_thresholds_changed"])

    def test_gareth_decision_is_manual_consideration_only(self):
        decision = apply_gareth_learning_decision(
            self._snapshot(),
            "APPROVE_FOR_MANUAL_CONSIDERATION",
            "Gareth approves these patterns for manual review only.",
        )
        self.assertEqual(decision["decision_by"], "Gareth")
        self.assertTrue(decision["manual_consideration_only"])
        self.assertFalse(decision["automatic_action_executed"])
        self.assertFalse(decision["compliance_rules_updated"])
        self.assertFalse(decision["decision_thresholds_changed"])

    def test_all_external_and_autonomous_actions_are_disabled(self):
        snapshot = self._snapshot()
        for field in (
            "network_client_enabled", "autonomous_decision_making_enabled",
            "automatic_client_contact_enabled", "automatic_candidate_contact_enabled",
            "automatic_firm_contact_enabled", "automatic_recruiter_contact_enabled",
            "automatic_association_contact_enabled", "automatic_outreach_enabled",
            "automatic_referral_enabled", "automatic_marketing_enabled",
            "automatic_payment_enabled", "automatic_delivery_enabled", "external_commitments_enabled",
        ):
            self.assertFalse(snapshot[field])

    def test_invalid_gareth_decision_is_rejected(self):
        with self.assertRaises(ValueError):
            apply_gareth_learning_decision(self._snapshot(), "AUTO_APPLY", "Invalid action.")


if __name__ == "__main__":
    unittest.main()
