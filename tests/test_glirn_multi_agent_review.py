import unittest

from glirn_brief_template import CLIENT_CONTENT_SECTIONS, REQUIRED_DISCLAIMER
from glirn_multi_agent_review import (
    REVIEWER_ROLES,
    build_consensus_summary,
    run_multi_agent_review,
)


def approved_human_review():
    return {
        "human_review_id": "human-review-brief-109",
        "brief_id": "brief-109",
        "approved_for_manual_delivery": True,
        "delivery_status": "ready_for_manual_delivery",
        "validation_errors": [],
        "incomplete_checks": [],
        "unresolved_red_flags": [],
    }


def review_brief(red_flags=None, **overrides):
    sections = {name: f"Evidence-led content for {name}." for name in CLIENT_CONTENT_SECTIONS}
    sections["Required Disclaimer"] = REQUIRED_DISCLAIMER
    brief = {
        "review_id": "brief-109",
        "sections": sections,
        "human_review_framework": {"red_flags": red_flags or {}},
        "candidate_personal_data_included": False,
        "candidate_personal_data_blocked": False,
    }
    brief.update(overrides)
    return brief


class MultiAgentReviewTests(unittest.TestCase):
    def test_all_four_reviewer_perspectives_execute_with_required_output(self):
        record = run_multi_agent_review(
            review_brief(),
            approved_human_review(),
            reviewed_at="2026-06-11T09:00:00+00:00",
        )

        outputs = record["reviewer_outputs"]
        self.assertEqual(tuple(item["reviewer_role"] for item in outputs), REVIEWER_ROLES)
        for output in outputs:
            self.assertIsInstance(output["findings"], list)
            self.assertIsInstance(output["concerns"], list)
            self.assertIsInstance(output["recommendations"], list)
            self.assertGreaterEqual(output["confidence_score"], 0)
            self.assertLessEqual(output["confidence_score"], 100)
            self.assertIsInstance(output["escalation_required"], bool)
        self.assertTrue(record["review_complete"])
        self.assertFalse(record["escalation_required"])
        self.assertEqual(record["review_status"], "cleared_for_gareth_approval")
        self.assertFalse(record["delivery_eligible"])
        self.assertTrue(record["gareth_final_approval_required"])
        self.assertFalse(record["sensitive_candidate_information_duplicated"])

    def test_confidence_calculation_and_consensus_summary(self):
        outputs = [
            {"reviewer_role": role, "confidence_score": score, "issue_codes": [], "escalation_required": False}
            for role, score in zip(REVIEWER_ROLES, (80, 60, 70, 90))
        ]
        consensus = build_consensus_summary(outputs)

        self.assertEqual(consensus["overall_confidence_score"], 75.0)
        self.assertFalse(consensus["escalation_required"])
        self.assertTrue(consensus["areas_of_agreement"])
        self.assertEqual(consensus["areas_of_disagreement"], [])
        self.assertEqual(consensus["suggested_next_actions"], ["Submit the cleared review to Gareth for final approval."])

    def test_average_confidence_below_70_triggers_escalation(self):
        outputs = [
            {"reviewer_role": role, "confidence_score": 69, "issue_codes": [], "escalation_required": False}
            for role in REVIEWER_ROLES
        ]
        consensus = build_consensus_summary(outputs)

        self.assertTrue(consensus["escalation_required"])
        self.assertIn("average_confidence_below_70", consensus["escalation_requirements"])

    def test_any_reviewer_escalation_request_triggers_escalation(self):
        outputs = [
            {"reviewer_role": role, "confidence_score": 90, "issue_codes": [], "escalation_required": index == 0}
            for index, role in enumerate(REVIEWER_ROLES)
        ]
        consensus = build_consensus_summary(outputs)

        self.assertTrue(consensus["escalation_required"])
        self.assertIn("reviewer_requested_escalation", consensus["escalation_requirements"])

    def test_mandatory_risk_conditions_trigger_delivery_blocking_escalation(self):
        cases = [
            ({"legal_advice_inference_risk": True}, {}, "legal_advice_inference_risk"),
            ({"insufficient_evidence": True}, {}, "evidence_insufficiency"),
            ({}, {"candidate_personal_data_included": True, "candidate_personal_data_blocked": True}, "candidate_consent_concern"),
        ]
        for red_flags, overrides, expected_issue in cases:
            with self.subTest(expected_issue=expected_issue):
                record = run_multi_agent_review(review_brief(red_flags, **overrides), approved_human_review())
                self.assertTrue(record["escalation_required"])
                self.assertEqual(record["review_status"], "escalated_delivery_blocked")
                self.assertIn(expected_issue, record["unresolved_escalations"])
                self.assertFalse(record["automatic_acceptance_enabled"])
                self.assertFalse(record["automatic_payment_enabled"])
                self.assertFalse(record["automatic_candidate_outreach_enabled"])
                self.assertFalse(record["automatic_delivery_enabled"])
                self.assertFalse(record["external_commitments_enabled"])


if __name__ == "__main__":
    unittest.main()
