import unittest

from glirn_hiring_snapshot import (
    DISCLAIMER,
    NEXT_STEP,
    PAID_REVIEW_NAME,
    PAID_REVIEW_PRICE,
    SNAPSHOT_NAME,
    apply_gareth_snapshot_decision,
    generate_complimentary_hiring_snapshot,
)


def snapshot():
    return generate_complimentary_hiring_snapshot(
        "snapshot-001",
        "Technology Partner",
        "International law firm assessing a senior growth hire",
        "United Kingdom",
        "AI and Technology Law",
        ["Public market evidence indicates demand for specialist senior capability."],
        generated_at="2026-06-14T12:00:00+00:00",
    )


class ComplimentaryHiringSnapshotTests(unittest.TestCase):
    def test_generates_all_required_snapshot_sections(self):
        result = snapshot()
        for section in (
            "Initial Role Assessment",
            "Market Hiring Difficulty Indication",
            "Initial Hiring Risk Indicators",
            "Preliminary Market Observations",
            "High-Level Recommendation",
            "Next Step",
            "Required Disclaimer",
        ):
            self.assertIn(section, result["sections"])
        self.assertEqual(result["sections"]["Next Step"], NEXT_STEP)
        self.assertEqual(result["sections"]["Required Disclaimer"], DISCLAIMER)

    def test_offer_structure_preserves_paid_review_and_premium_next_step(self):
        offers = snapshot()["offer_structure"]
        self.assertEqual(offers["primary"], SNAPSHOT_NAME)
        self.assertIn(PAID_REVIEW_NAME, offers["secondary"])
        self.assertIn(PAID_REVIEW_PRICE, offers["secondary"])
        self.assertEqual(
            offers["higher_value_next_step"],
            "Executive Search Support / Premium Legal Recruitment Engagements",
        )

    def test_gareth_approval_is_mandatory_and_does_not_send(self):
        result = snapshot()
        self.assertEqual(result["approval_status"], "awaiting_gareth_approval")
        self.assertFalse(result["approved_for_manual_use"])
        decision = apply_gareth_snapshot_decision(result, "APPROVE", "Approved for manual client preparation.")
        self.assertEqual(decision["decision_by"], "Gareth")
        self.assertTrue(decision["approved_for_manual_use"])
        self.assertTrue(decision["manual_download_or_copy_only"])
        self.assertFalse(decision["delivery_executed"])
        self.assertFalse(decision["automatic_sending_enabled"])

    def test_missing_evidence_is_rejected(self):
        with self.assertRaises(ValueError):
            generate_complimentary_hiring_snapshot(
                "snapshot-002", "Partner", "Firm", "United Kingdom", "Corporate", []
            )

    def test_all_external_action_paths_are_disabled(self):
        result = snapshot()
        for field in (
            "network_client_enabled",
            "automatic_sending_enabled",
            "automatic_outreach_enabled",
            "automatic_client_contact_enabled",
            "automatic_publishing_enabled",
            "payment_handling_enabled",
            "legal_advice_provided",
            "automatic_delivery_enabled",
            "external_commitments_enabled",
        ):
            self.assertFalse(result[field])


if __name__ == "__main__":
    unittest.main()
