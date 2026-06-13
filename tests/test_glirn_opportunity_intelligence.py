import unittest

from glirn_opportunity_intelligence import (
    OPPORTUNITY_CATEGORIES,
    SOURCE_WEIGHTS,
    apply_gareth_opportunity_decision,
    generate_opportunity_recommendation,
    record_opportunity_signal,
)


def signal(source_type="official_firm_announcement", signal_id="signal-114", **overrides):
    values = {
        "signal_id": signal_id,
        "category": "law_firm_growth",
        "source_type": source_type,
        "title": "Firm announces office growth",
        "publisher": "Example Law Firm",
        "source_url": "https://example.org/announcement",
        "publication_date": "2026-06-13",
        "signal_summary": "The firm announced expansion in a target market.",
        "organisation": "Example Law Firm",
        "jurisdiction": "United Kingdom",
        "practice_area": "Corporate",
        "signal_strength": 80,
    }
    values.update(overrides)
    return record_opportunity_signal(**values)


class OpportunityIntelligenceTests(unittest.TestCase):
    def test_all_required_categories_are_supported(self):
        self.assertEqual(OPPORTUNITY_CATEGORIES, {
            "law_firm_growth", "partner_movement", "practice_area_expansion", "recruitment_demand"
        })

    def test_source_weighting_matches_mission_requirements(self):
        expected = {
            "official_firm_announcement": ("Very High", 95),
            "regulatory_filing": ("Very High", 95),
            "professional_association": ("High", 85),
            "major_legal_publication": ("High", 85),
            "recruiter_report": ("Medium", 65),
            "industry_discussion": ("Low", 35),
        }
        for source_type, (category, weight) in expected.items():
            with self.subTest(source_type=source_type):
                record = signal(source_type, f"signal-{source_type}")
                self.assertEqual(record["source_confidence"], category)
                self.assertEqual(record["source_weight"], weight)
        self.assertEqual(set(SOURCE_WEIGHTS), set(expected))

    def test_confidence_scoring_rewards_authority_and_corroboration(self):
        single_low = generate_opportunity_recommendation([signal("industry_discussion")])
        corroborated = generate_opportunity_recommendation([
            signal("official_firm_announcement", "official"),
            signal("regulatory_filing", "filing", category="practice_area_expansion"),
            signal("major_legal_publication", "publication", category="recruitment_demand"),
        ])
        self.assertGreater(corroborated["confidence_score"], single_low["confidence_score"])
        self.assertEqual(corroborated["priority"], "High")
        self.assertEqual(corroborated["approval_status"], "awaiting_gareth_approval")

    def test_recommendation_is_transparent_and_advisory_only(self):
        recommendation = generate_opportunity_recommendation([signal()])
        self.assertIn("average_source_weight", recommendation["reasoning"])
        self.assertIn("corroboration_score", recommendation["reasoning"])
        self.assertTrue(recommendation["evidence_summary"])
        self.assertTrue(recommendation["recommendation_only"])
        self.assertTrue(recommendation["gareth_approval_required"])

    def test_gareth_decision_records_manual_review_without_action(self):
        recommendation = generate_opportunity_recommendation([signal()])
        decision = apply_gareth_opportunity_decision(
            recommendation,
            "APPROVE_FOR_MANUAL_REVIEW",
            "Gareth approves manual qualification review only.",
        )
        self.assertEqual(decision["decision_by"], "Gareth")
        self.assertTrue(decision["manual_review_only"])
        self.assertFalse(decision["automatic_action_executed"])

    def test_all_external_actions_remain_disabled(self):
        record = generate_opportunity_recommendation([signal()])
        for field in (
            "external_retrieval_enabled", "autonomous_outreach_enabled",
            "autonomous_prospecting_enabled", "automatic_referral_enabled",
            "automatic_marketing_enabled", "automatic_payment_enabled",
            "automatic_delivery_enabled", "external_commitments_enabled",
        ):
            self.assertFalse(record[field])

    def test_invalid_inputs_and_mixed_organisations_are_rejected(self):
        with self.assertRaises(ValueError):
            signal(source_url="file:///private.txt")
        with self.assertRaises(ValueError):
            signal(category="unknown")
        with self.assertRaises(ValueError):
            generate_opportunity_recommendation([
                signal(signal_id="one"), signal(signal_id="two", organisation="Another Firm")
            ])


if __name__ == "__main__":
    unittest.main()
