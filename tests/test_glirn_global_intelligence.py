import unittest

from glirn_global_intelligence import (
    INTELLIGENCE_CATEGORIES,
    SUPPORTED_JURISDICTIONS,
    generate_global_legal_intelligence,
    render_global_intelligence_markdown,
)


def confidence_assessment(score=88, evidence=90, disagreement=False, escalation=False):
    return {
        "confidence_assessment_id": "confidence-assessment-brief-111",
        "brief_id": "brief-111",
        "content_fingerprint": "fingerprint-111",
        "assessment_complete": True,
        "confidence_score": score,
        "confidence_category": "High Confidence" if score >= 75 else "Moderate Confidence",
        "evidence_sufficiency_rating": evidence,
        "reviewer_agreement": {
            "level": "Low" if disagreement else "High",
            "significant_disagreement": disagreement,
        },
        "evidence_transparency": {
            "alternative_interpretations": ["Demand may reflect short-term replacement activity."],
        },
        "escalation_required": escalation,
        "unresolved_escalations": ["mission_110_issue"] if escalation else [],
    }


def indicator_ratings(value=80):
    return {category: value for category in INTELLIGENCE_CATEGORIES}


def brief(**overrides):
    value = {
        "review_id": "brief-111",
        "candidate_personal_data_included": False,
        "candidate_personal_data_blocked": False,
    }
    value.update(overrides)
    return value


class GlobalLegalIntelligenceTests(unittest.TestCase):
    def test_all_phase_one_jurisdictions_generate_required_intelligence(self):
        for jurisdiction in SUPPORTED_JURISDICTIONS:
            with self.subTest(jurisdiction=jurisdiction):
                record = generate_global_legal_intelligence(
                    brief(),
                    confidence_assessment(),
                    jurisdiction,
                    "Technology & AI Law",
                    indicator_ratings(),
                    ["Reviewed high-level market source summary."],
                    reviewed_at="2026-06-13T09:00:00+00:00",
                )

                self.assertEqual(record["jurisdiction"], jurisdiction)
                self.assertEqual(record["practice_area"], "Technology & AI Law")
                self.assertEqual(set(record["structured_observations"]), set(INTELLIGENCE_CATEGORIES))
                self.assertEqual(record["confidence_score"], 88.0)
                self.assertEqual(record["confidence_category"], "High Confidence")
                self.assertTrue(record["intelligence_summary"])
                self.assertTrue(record["evidence_transparency_summary"])
                self.assertTrue(record["known_limitations"])
                self.assertTrue(record["information_gaps"])
                self.assertTrue(record["alternative_interpretations"])
                self.assertEqual(record["review_timestamp"], "2026-06-13T09:00:00+00:00")
                self.assertFalse(record["escalation_required"])

    def test_observations_are_high_level_non_advisory_and_non_candidate_specific(self):
        record = generate_global_legal_intelligence(
            brief(), confidence_assessment(), "United Kingdom", "Corporate & M&A",
            indicator_ratings(), ["Reviewed evidence summary."],
        )

        for observation in record["structured_observations"].values():
            self.assertTrue(observation["evidence_based"])
            self.assertFalse(observation["candidate_specific"])
            self.assertFalse(observation["legal_advice"])
            self.assertIn("not a verified market fact or legal advice", observation["observation"])
        self.assertTrue(record["high_level_observations_only"])
        self.assertFalse(record["legal_advice_provided"])
        self.assertFalse(record["candidate_specific_intelligence_included"])

    def test_unsupported_jurisdiction_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "not supported"):
            generate_global_legal_intelligence(
                brief(), confidence_assessment(), "Canada", "Employment Law",
                indicator_ratings(), ["Reviewed evidence summary."],
            )

    def test_all_mandatory_escalation_conditions_block_delivery(self):
        cases = [
            ({"assessment": confidence_assessment(score=69)}, "confidence_below_70"),
            ({"jurisdiction_expertise_limitations": True}, "jurisdiction_expertise_limitations"),
            ({"evidence_insufficiency_identified": True}, "evidence_insufficiency"),
            ({"assessment": confidence_assessment(disagreement=True)}, "reviewer_disagreement_unresolved"),
            ({"exceeds_glirn_expertise_boundaries": True}, "glirn_expertise_boundary_exceeded"),
            ({"unsupported_claims_identified": True}, "unsupported_intelligence_claims"),
        ]
        for options, expected in cases:
            with self.subTest(expected=expected):
                record = generate_global_legal_intelligence(
                    brief(),
                    options.get("assessment", confidence_assessment()),
                    "Singapore",
                    "Financial Services Regulation",
                    indicator_ratings(),
                    ["Reviewed evidence summary."],
                    unsupported_claims_identified=options.get("unsupported_claims_identified", False),
                    jurisdiction_expertise_limitations=options.get("jurisdiction_expertise_limitations", False),
                    evidence_insufficiency_identified=options.get("evidence_insufficiency_identified", False),
                    exceeds_glirn_expertise_boundaries=options.get("exceeds_glirn_expertise_boundaries", False),
                )
                self.assertTrue(record["escalation_required"])
                self.assertIn(expected, record["unresolved_escalations"])
                self.assertEqual(record["validation_status"], "escalated_delivery_blocked")
                self.assertFalse(record["delivery_eligible"])
                self.assertFalse(record["gareth_override_allowed"])

    def test_missing_evidence_and_candidate_consent_block_intelligence(self):
        record = generate_global_legal_intelligence(
            brief(candidate_personal_data_included=True, candidate_personal_data_blocked=True),
            confidence_assessment(),
            "United Arab Emirates",
            "Private Equity",
            indicator_ratings(),
            [],
        )

        self.assertIn("evidence_insufficiency", record["unresolved_escalations"])
        self.assertIn("candidate_consent_incomplete", record["unresolved_escalations"])
        self.assertFalse(record["candidate_consent_valid"])
        self.assertTrue(record["candidate_data_minimised"])
        self.assertFalse(record["confidential_source_material_duplicated_in_audit"])

    def test_evidence_summary_redacts_contact_details(self):
        record = generate_global_legal_intelligence(
            brief(), confidence_assessment(), "United States", "Antitrust",
            indicator_ratings(), ["Source person@example.com and +1 212 555 0199."],
        )

        self.assertIn("[redacted email]", record["evidence_transparency_summary"][0])
        self.assertIn("[redacted phone]", record["evidence_transparency_summary"][0])

    def test_markdown_contains_required_transparency_fields(self):
        record = generate_global_legal_intelligence(
            brief(), confidence_assessment(), "European Union", "Competition Law",
            indicator_ratings(), ["Reviewed evidence summary."],
        )
        markdown = render_global_intelligence_markdown(record)

        self.assertIn("## Global Legal Intelligence", markdown)
        self.assertIn("Jurisdiction: European Union", markdown)
        self.assertIn("Practice area: Competition Law", markdown)
        self.assertIn("Evidence transparency summary", markdown)
        self.assertIn("Known limitations", markdown)
        self.assertIn("Information gaps", markdown)
        self.assertIn("Alternative interpretations", markdown)
        self.assertFalse(record["automatic_acceptance_enabled"])
        self.assertFalse(record["automatic_payment_enabled"])
        self.assertFalse(record["automatic_candidate_outreach_enabled"])
        self.assertFalse(record["automatic_search_commitments_enabled"])
        self.assertFalse(record["automatic_delivery_enabled"])
        self.assertFalse(record["external_commitments_enabled"])


if __name__ == "__main__":
    unittest.main()
