import unittest

from glirn_decline_decision import (
    DECISION_FACTORS,
    apply_gareth_decision,
    evaluate_decline_decision,
)


def scores(**overrides):
    values = {
        "client_fit": 80,
        "ethical_risk": 20,
        "commercial_viability": 75,
        "reputation_risk": 20,
        "delivery_confidence": 85,
    }
    values.update(overrides)
    return values


def evidence(**overrides):
    values = {factor: f"Reviewed evidence for {factor}." for factor in DECISION_FACTORS}
    values.update(overrides)
    return values


class DeclineDecisionEngineTests(unittest.TestCase):
    def test_strong_low_risk_enquiry_recommends_accept(self):
        record = evaluate_decline_decision(
            "enquiry-112", scores(), evidence(), evaluated_at="2026-06-13T10:00:00+00:00"
        )

        self.assertEqual(record["recommendation"], "ACCEPT")
        self.assertEqual(record["recommendation_reasons"], ["all_decision_thresholds_satisfied"])
        self.assertEqual(set(record["factor_scores"]), set(DECISION_FACTORS))
        self.assertEqual(len(record["transparent_reasoning"]), 6)
        self.assertEqual(record["final_decision_status"], "awaiting_gareth_approval")
        self.assertTrue(record["recommendation_only"])
        self.assertTrue(record["gareth_final_approval_required"])

    def test_each_material_failure_can_recommend_decline(self):
        cases = [
            ({"ethical_risk": 70}, "ethical_risk_unacceptably_high"),
            ({"reputation_risk": 75}, "reputation_risk_unacceptably_high"),
            ({"client_fit": 34}, "client_fit_materially_insufficient"),
            ({"commercial_viability": 29}, "commercial_viability_materially_insufficient"),
            ({"delivery_confidence": 39}, "delivery_confidence_materially_insufficient"),
        ]
        for score_override, expected_reason in cases:
            with self.subTest(expected_reason=expected_reason):
                record = evaluate_decline_decision(
                    "enquiry-112", scores(**score_override), evidence()
                )
                self.assertEqual(record["recommendation"], "DECLINE")
                self.assertIn(expected_reason, record["recommendation_reasons"])

    def test_borderline_scores_require_more_information(self):
        cases = [
            {"client_fit": 69},
            {"ethical_risk": 40},
            {"commercial_viability": 59},
            {"reputation_risk": 40},
            {"delivery_confidence": 69},
        ]
        for score_override in cases:
            with self.subTest(score_override=score_override):
                record = evaluate_decline_decision(
                    "enquiry-112", scores(**score_override), evidence()
                )
                self.assertEqual(record["recommendation"], "MORE_INFORMATION_REQUIRED")

    def test_missing_evidence_requires_more_information(self):
        record = evaluate_decline_decision(
            "enquiry-112", scores(), evidence(client_fit="")
        )

        self.assertEqual(record["recommendation"], "MORE_INFORMATION_REQUIRED")
        self.assertIn("client_fit", record["missing_evidence"])
        self.assertIn("material_evidence_incomplete", record["recommendation_reasons"])

    def test_optional_referral_is_only_recommended_for_decline(self):
        decline = evaluate_decline_decision(
            "enquiry-112",
            scores(ethical_risk=80),
            evidence(),
            referral_suitable=True,
            referral_type="Independent specialist adviser",
            referral_reason="Request falls outside GLIRN's appropriate risk tolerance.",
        )
        accept = evaluate_decline_decision(
            "enquiry-113", scores(), evidence(), referral_suitable=True,
            referral_type="Specialist", referral_reason="Optional.",
        )

        self.assertTrue(decline["referral_recommendation"]["recommended"])
        self.assertEqual(decline["referral_recommendation"]["referral_type"], "Independent specialist adviser")
        self.assertFalse(decline["referral_recommendation"]["external_contact_executed"])
        self.assertTrue(decline["referral_recommendation"]["gareth_approval_required"])
        self.assertFalse(accept["referral_recommendation"]["recommended"])

    def test_evidence_is_redacted_and_safety_controls_remain_disabled(self):
        record = evaluate_decline_decision(
            "enquiry-112",
            scores(),
            evidence(client_fit="Contact person@example.com or +44 7700 900123."),
        )

        self.assertIn("[redacted email]", record["evidence_summary"]["client_fit"])
        self.assertIn("[redacted phone]", record["evidence_summary"]["client_fit"])
        self.assertTrue(record["candidate_data_minimised"])
        self.assertFalse(record["confidential_source_material_duplicated_in_audit"])
        self.assertFalse(record["automatic_acceptance_enabled"])
        self.assertFalse(record["automatic_decline_enabled"])
        self.assertFalse(record["automatic_referral_enabled"])
        self.assertFalse(record["automatic_payment_enabled"])
        self.assertFalse(record["automatic_candidate_outreach_enabled"])
        self.assertFalse(record["automatic_search_commitments_enabled"])
        self.assertFalse(record["automatic_delivery_enabled"])
        self.assertFalse(record["external_commitments_enabled"])

    def test_invalid_scores_are_rejected(self):
        for invalid in (-1, 101, "unknown"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    evaluate_decline_decision(
                        "enquiry-112", scores(client_fit=invalid), evidence()
                    )

    def test_gareth_can_record_any_final_decision_with_rationale(self):
        recommendation = evaluate_decline_decision(
            "enquiry-112", scores(ethical_risk=80), evidence()
        )
        for final_decision in ("ACCEPT", "DECLINE", "MORE_INFORMATION_REQUIRED"):
            with self.subTest(final_decision=final_decision):
                decision = apply_gareth_decision(
                    recommendation,
                    final_decision,
                    "Gareth reviewed the evidence and records the final decision.",
                    decided_at="2026-06-13T11:00:00+00:00",
                )
                self.assertEqual(decision["final_decision"], final_decision)
                self.assertEqual(decision["decision_by"], "Gareth")
                self.assertTrue(decision["gareth_approved"])
                self.assertFalse(decision["automatic_action_executed"])


if __name__ == "__main__":
    unittest.main()
