import unittest

from glirn_confidence_engine import (
    CONFIDENCE_WEIGHTS,
    assess_confidence,
    confidence_category,
    confidence_context_for_global_intelligence,
    render_evidence_transparency_markdown,
    reviewer_agreement,
)


def approved_human_review():
    return {
        "human_review_id": "human-review-brief-110",
        "brief_id": "brief-110",
        "approved_for_manual_delivery": True,
        "delivery_status": "ready_for_manual_delivery",
        "validation_errors": [],
        "incomplete_checks": [],
        "unresolved_red_flags": [],
    }


def multi_agent_review(scores=(90, 90, 90, 90), escalation=False):
    roles = (
        "Intelligence Analyst",
        "Risk Reviewer",
        "Devil's Advocate Reviewer",
        "Quality Assurance Reviewer",
    )
    return {
        "review_id": "multi-agent-review-brief-110",
        "brief_id": "brief-110",
        "review_complete": True,
        "content_fingerprint": "fingerprint-110",
        "reviewer_outputs": [
            {
                "reviewer_role": role,
                "confidence_score": score,
                "findings": ["Reviewed."],
                "concerns": ["Alternative market interpretation."] if role == "Devil's Advocate Reviewer" else [],
                "recommendations": ["Validate material observations."],
            }
            for role, score in zip(roles, scores)
        ],
        "escalation_required": escalation,
        "unresolved_escalations": ["mission_109_issue"] if escalation else [],
    }


def brief(**overrides):
    value = {
        "review_id": "brief-110",
        "human_review_framework": {"red_flags": {}},
        "candidate_personal_data_included": False,
        "candidate_personal_data_blocked": False,
    }
    value.update(overrides)
    return value


class ConfidenceEngineTests(unittest.TestCase):
    def test_confidence_categories_assign_boundary_values(self):
        cases = {
            100: "Very High Confidence",
            90: "Very High Confidence",
            89: "High Confidence",
            75: "High Confidence",
            74: "Moderate Confidence",
            60: "Moderate Confidence",
            59: "Low Confidence",
            0: "Low Confidence",
        }
        for score, expected in cases.items():
            with self.subTest(score=score):
                self.assertEqual(confidence_category(score), expected)

    def test_weighted_confidence_calculation_uses_all_required_factors(self):
        assessment = assess_confidence(
            brief(),
            approved_human_review(),
            multi_agent_review(),
            100,
            100,
            100,
            100,
            assessed_at="2026-06-12T09:00:00+00:00",
        )

        self.assertAlmostEqual(sum(CONFIDENCE_WEIGHTS.values()), 1.0)
        self.assertEqual(set(assessment["factor_scores"]), set(CONFIDENCE_WEIGHTS))
        self.assertEqual(assessment["confidence_score"], 100.0)
        self.assertEqual(assessment["confidence_category"], "Very High Confidence")
        self.assertFalse(assessment["escalation_required"])
        self.assertEqual(assessment["assessment_status"], "cleared_for_gareth_approval")

    def test_reviewer_agreement_detects_significant_score_dispersion(self):
        agreement = reviewer_agreement(multi_agent_review((100, 80, 70, 60)))

        self.assertEqual(agreement["score_spread"], 40.0)
        self.assertEqual(agreement["level"], "Low")
        self.assertTrue(agreement["significant_disagreement"])

    def test_low_confidence_requires_remediation_and_reassessment(self):
        assessment = assess_confidence(
            brief(),
            approved_human_review(),
            multi_agent_review(),
            20,
            20,
            20,
            20,
        )

        self.assertLess(assessment["confidence_score"], 70)
        self.assertTrue(assessment["escalation_required"])
        self.assertIn("confidence_below_70", assessment["unresolved_escalations"])
        self.assertIn("evidence_sufficiency_inadequate", assessment["unresolved_escalations"])
        self.assertTrue(assessment["remediation_and_mission_109_110_reassessment_required"])
        self.assertFalse(assessment["gareth_override_allowed"])
        self.assertFalse(assessment["delivery_eligible"])

    def test_each_mandatory_escalation_condition_triggers(self):
        cases = [
            ({"evidence_sufficiency": 69}, "evidence_sufficiency_inadequate"),
            ({"review": multi_agent_review((100, 80, 70, 60))}, "significant_reviewer_disagreement"),
            ({"material_limitations": True}, "material_limitations_undermine_conclusions"),
        ]
        for options, expected in cases:
            with self.subTest(expected=expected):
                assessment = assess_confidence(
                    brief(),
                    approved_human_review(),
                    options.get("review", multi_agent_review()),
                    options.get("evidence_sufficiency", 95),
                    95,
                    95,
                    95,
                    material_limitations_undermine_conclusions=options.get("material_limitations", False),
                )
                self.assertTrue(assessment["escalation_required"])
                self.assertIn(expected, assessment["unresolved_escalations"])

    def test_evidence_transparency_is_generated_and_candidate_data_is_minimised(self):
        assessment = assess_confidence(
            brief(),
            approved_human_review(),
            multi_agent_review(),
            95,
            95,
            95,
            95,
            evidence_transparency={
                "key_evidence_considered": ["Source contact person@example.com and +44 7700 900123."],
                "supporting_assumptions": ["Demand remains stable."],
                "known_limitations": ["Limited sample."],
                "areas_requiring_caution": ["Validate before action."],
                "information_gaps_identified": ["Compensation detail unavailable."],
            },
        )
        transparency = assessment["evidence_transparency"]
        markdown = render_evidence_transparency_markdown(assessment)

        self.assertIn("[redacted email]", transparency["key_evidence_considered"][0])
        self.assertIn("[redacted phone]", transparency["key_evidence_considered"][0])
        self.assertIn("Alternative market interpretation.", transparency["alternative_interpretations"])
        self.assertTrue(transparency["candidate_data_minimised"])
        self.assertFalse(transparency["confidential_source_material_duplicated"])
        self.assertIn("## Confidence and Evidence Transparency", markdown)
        self.assertIn("### Known limitations", markdown)
        self.assertFalse(assessment["confidential_source_material_duplicated_in_audit"])
        self.assertFalse(assessment["automatic_acceptance_enabled"])
        self.assertFalse(assessment["automatic_payment_enabled"])
        self.assertFalse(assessment["automatic_candidate_outreach_enabled"])
        self.assertFalse(assessment["automatic_search_activity_enabled"])
        self.assertFalse(assessment["automatic_delivery_enabled"])
        self.assertFalse(assessment["external_commitments_enabled"])

    def test_global_intelligence_context_inherits_authoritative_confidence(self):
        assessment = assess_confidence(
            brief(), approved_human_review(), multi_agent_review(), 85, 80, 75, 70,
        )
        context = confidence_context_for_global_intelligence(assessment, "brief-110")

        self.assertEqual(context["confidence_assessment_id"], assessment["confidence_assessment_id"])
        self.assertEqual(context["confidence_score"], assessment["confidence_score"])
        self.assertEqual(context["confidence_category"], assessment["confidence_category"])
        self.assertEqual(context["evidence_sufficiency_rating"], 85.0)
        self.assertFalse(context["reviewer_disagreement_unresolved"])

    def test_global_intelligence_context_rejects_mismatched_brief(self):
        with self.assertRaisesRegex(ValueError, "matching Mission 110"):
            confidence_context_for_global_intelligence(confidence_assessment := {
                "brief_id": "other-brief",
                "assessment_complete": True,
            }, "brief-110")


if __name__ == "__main__":
    unittest.main()
