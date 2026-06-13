import unittest

from glirn_external_learning import (
    SOURCE_WEIGHTS,
    approve_knowledge_update,
    generate_external_intelligence,
    ingest_public_evidence,
)


def evidence(source_type, evidence_id="evidence-113a"):
    return ingest_public_evidence(
        evidence_id,
        source_type,
        "Public legal recruitment guidance",
        "Public body",
        "https://example.org/guidance",
        "2026-06-01",
        "Published guidance relevant to recruitment compliance.",
        "United Kingdom",
    )


class ExternalLearningTests(unittest.TestCase):
    def test_source_weighting_matches_required_categories(self):
        expected = {
            "government_regulatory": ("Very High", 95),
            "professional_body": ("High", 85),
            "major_recruitment_report": ("Medium", 65),
            "industry_forum_discussion": ("Low", 35),
        }
        for source_type, (category, weight) in expected.items():
            with self.subTest(source_type=source_type):
                record = evidence(source_type, f"evidence-{source_type}")
                self.assertEqual(record["confidence_category"], category)
                self.assertEqual(record["evidence_weight"], weight)

    def test_invalid_or_non_public_url_is_rejected(self):
        with self.assertRaises(ValueError):
            ingest_public_evidence(
                "evidence", "government_regulatory", "Title", "Publisher", "file:///private.txt",
                "2026-06-01", "Summary"
            )

    def test_weighted_summary_is_recommendation_only_and_not_legal_advice(self):
        records = [evidence("government_regulatory", "gov"), evidence("professional_body", "body")]
        summary = generate_external_intelligence(records, "Recruitment compliance")
        self.assertEqual(summary["weighted_confidence_score"], 90)
        self.assertEqual(summary["confidence_category"], "Very High")
        self.assertTrue(summary["recommendation_only"])
        self.assertFalse(summary["legal_advice_provided"])
        self.assertEqual(summary["knowledge_base_status"], "awaiting_gareth_approval")

    def test_gareth_approval_is_required_before_knowledge_update(self):
        summary = generate_external_intelligence([evidence("major_recruitment_report")], "Market demand")
        update = approve_knowledge_update(summary, "Approved after manual source review.")
        self.assertEqual(update["approved_by"], "Gareth")
        self.assertEqual(update["knowledge_base_status"], "approved_for_manual_use")
        self.assertFalse(update["automatic_regulatory_change_implemented"])

    def test_no_external_or_autonomous_actions_are_enabled(self):
        record = evidence("industry_forum_discussion")
        for field in (
            "external_retrieval_enabled", "external_organisation_contact_enabled",
            "automatic_regulatory_updates_enabled", "autonomous_decision_making_enabled",
            "automatic_outreach_enabled", "automatic_referral_enabled",
            "automatic_payment_enabled", "automatic_delivery_enabled", "external_commitments_enabled",
        ):
            self.assertFalse(record[field])
        self.assertEqual(set(SOURCE_WEIGHTS), {
            "government_regulatory", "professional_body",
            "major_recruitment_report", "industry_forum_discussion",
        })


if __name__ == "__main__":
    unittest.main()
