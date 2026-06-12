import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

os.environ.setdefault(
    "GLIRN_DB_PATH",
    os.path.join(tempfile.gettempdir(), f"glirn-brief-tests-{os.getpid()}.db"),
)

import app
from glirn_multi_agent_review import brief_content_fingerprint
from glirn_brief_template import (
    CLIENT_CONTENT_SECTIONS,
    GLIRN_PRINCIPLE,
    REQUIRED_DISCLAIMER,
    REQUIRED_SECTIONS,
    IntelligenceBriefValidationError,
    build_intelligence_brief_package,
)


def approved_review(brief_id="brief-107"):
    return {
        "human_review_id": f"human-review-{brief_id}",
        "brief_id": brief_id,
        "reviewed_at": "2026-06-10T09:30:00+00:00",
        "reviewer": "Gareth",
        "outcome": "approved_for_manual_delivery",
        "approval_rationale": "Evidence, limitations, wording, and delivery controls checked.",
        "delivery_status": "ready_for_manual_delivery",
        "approved_for_manual_delivery": True,
        "validation_errors": [],
        "incomplete_checks": [],
        "unresolved_red_flags": [],
    }


def complete_sections():
    return {name: f"Approved content for {name}." for name in CLIENT_CONTENT_SECTIONS}


def cleared_multi_agent_review(brief_id="brief-107"):
    return {
        "review_id": f"multi-agent-review-{brief_id}",
        "brief_id": brief_id,
        "review_complete": True,
        "content_fingerprint": brief_content_fingerprint(complete_sections()),
        "escalation_required": False,
        "unresolved_escalations": [],
        "review_status": "cleared_for_gareth_approval",
    }


def cleared_confidence_assessment(brief_id="brief-107"):
    return {
        "confidence_assessment_id": f"confidence-assessment-{brief_id}",
        "brief_id": brief_id,
        "mission_109_review_id": f"multi-agent-review-{brief_id}",
        "content_fingerprint": brief_content_fingerprint(complete_sections()),
        "assessment_complete": True,
        "confidence_score": 88,
        "confidence_category": "High Confidence",
        "evidence_sufficiency_rating": 90,
        "reviewer_agreement": {"level": "High"},
        "outstanding_limitations": ["Market information remains time-sensitive."],
        "evidence_transparency": {
            "key_evidence_considered": ["Reviewed market observations."],
            "supporting_assumptions": ["Market conditions remain comparable."],
            "known_limitations": ["Market information remains time-sensitive."],
            "areas_requiring_caution": ["Validate observations before action."],
            "information_gaps_identified": ["No material gaps identified."],
            "alternative_interpretations": ["Alternative demand conditions were considered."],
            "candidate_data_minimised": True,
            "confidential_source_material_duplicated": False,
        },
        "escalation_required": False,
        "unresolved_escalations": [],
        "assessment_status": "cleared_for_gareth_approval",
    }


class IntelligenceBriefTemplateTests(unittest.TestCase):
    def test_package_contains_every_required_section_and_review_identity(self):
        package = build_intelligence_brief_package(
            {"review_id": "brief-107"},
            approved_review(),
            complete_sections(),
            audit_record_id="audit-107",
            generated_at="2026-06-10T10:00:00+00:00",
        )

        self.assertEqual(tuple(package["sections"]), REQUIRED_SECTIONS)
        self.assertEqual(package["review_record_id"], "human-review-brief-107")
        self.assertEqual(package["audit_record_id"], "audit-107")
        self.assertEqual(package["reviewer_identity"], "Gareth")
        self.assertEqual(package["review_date"], "2026-06-10T09:30:00+00:00")
        self.assertIn("Reviewed by Gareth", package["sections"]["Human Review Summary"])

    def test_package_cannot_bypass_mission_106_review(self):
        review = approved_review()
        review["approved_for_manual_delivery"] = False

        with self.assertRaisesRegex(IntelligenceBriefValidationError, "has not approved"):
            build_intelligence_brief_package(
                {"review_id": "brief-107"},
                review,
                complete_sections(),
            )

    def test_required_disclaimer_and_principle_are_always_included(self):
        sections = complete_sections()
        sections["Required Disclaimer"] = "Remove the disclaimer."
        package = build_intelligence_brief_package(
            {"review_id": "brief-107"},
            approved_review(),
            sections,
        )

        self.assertEqual(package["sections"]["Required Disclaimer"], REQUIRED_DISCLAIMER)
        self.assertEqual(package["principle"], GLIRN_PRINCIPLE)
        self.assertIn(REQUIRED_DISCLAIMER, package["markdown"])
        self.assertIn(GLIRN_PRINCIPLE, package["markdown"])

    def test_delivery_controls_remain_manual_only(self):
        package = build_intelligence_brief_package(
            {"review_id": "brief-107"},
            approved_review(),
            complete_sections(),
        )

        self.assertTrue(package["manual_delivery_only"])
        self.assertTrue(package["local_file_only"])
        self.assertFalse(package["automatic_delivery_enabled"])
        self.assertFalse(package["external_delivery_enabled"])
        self.assertFalse(package["email_sending_enabled"])
        self.assertFalse(package["external_upload_enabled"])
        self.assertFalse(package["external_integrations_enabled"])


class IntelligenceBriefPackageApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app.app)
        self.brief = {"review_id": "brief-107"}
        self.glirn_data = {
            "intelligence_review_engine": {"generated_reviews": [self.brief]}
        }

    def test_endpoint_refuses_package_without_mission_106_record(self):
        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.get_glirn_dashboard_data", return_value=self.glirn_data), \
                patch.object(app, "PERSISTED_HUMAN_REVIEWS", []):
            response = self.client.post(
                "/glirn/intelligence-briefs/package",
                json={"brief_id": "brief-107", "sections": complete_sections()},
            )

        self.assertEqual(response.status_code, 403)
        self.assertIn("Mission 106 human review is required", response.json()["detail"])

    def test_endpoint_generates_linked_local_manual_delivery_package(self):
        stored = []

        def store_record(category, record_id, payload):
            stored.append((category, record_id, dict(payload)))

        with tempfile.TemporaryDirectory() as temp_dir, \
                patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.get_glirn_dashboard_data", return_value=self.glirn_data), \
                patch.object(app, "PERSISTED_HUMAN_REVIEWS", [approved_review()]), \
                patch.object(app, "PERSISTED_MULTI_AGENT_REVIEWS", [cleared_multi_agent_review()]), \
                patch.object(app, "PERSISTED_CONFIDENCE_ASSESSMENTS", [cleared_confidence_assessment()]), \
                patch.object(app, "PERSISTED_INTELLIGENCE_BRIEFS", []), \
                patch.dict(app.FINAL_APPROVAL_LOCAL_STATUS, {
                    "intelligence-brief-final-approval-brief-107": "approved_by_gareth",
                }, clear=True), \
                patch("app.GLIRN_INTELLIGENCE_BRIEFS_DIR", temp_dir), \
                patch("app.upsert_record", side_effect=store_record), \
                patch("app.list_records", return_value=[]), \
                patch("app.persist_safe_action") as persist_action, \
                patch("app.record_approval_event") as approval_event:
            response = self.client.post(
                "/glirn/intelligence-briefs/package",
                json={"brief_id": "brief-107", "sections": complete_sections()},
            )

            self.assertEqual(response.status_code, 200)
            data = response.json()
            package = data["intelligence_brief_package"]
            self.assertTrue(os.path.isfile(package["local_file_path"]))
            with open(package["local_file_path"], encoding="utf-8") as brief_file:
                content = brief_file.read()

        self.assertEqual(package["review_record_id"], "human-review-brief-107")
        self.assertEqual(package["multi_agent_review_id"], "multi-agent-review-brief-107")
        self.assertEqual(package["confidence_assessment_id"], "confidence-assessment-brief-107")
        self.assertEqual(package["confidence_category"], "High Confidence")
        self.assertEqual(package["final_approval_status"], "approved_by_gareth")
        self.assertEqual(package["audit_record_id"], "intelligence-brief-audit-brief-107")
        self.assertIn(REQUIRED_DISCLAIMER, content)
        self.assertIn("Confidence and Evidence Transparency", content)
        self.assertIn("Alternative interpretations identified during Mission 109 review", content)
        self.assertTrue(data["manual_delivery_only"])
        self.assertFalse(data["automatic_delivery_enabled"])
        self.assertFalse(data["external_delivery_enabled"])
        self.assertFalse(data["external_integrations_enabled"])
        self.assertEqual(
            {item[0] for item in stored},
            {"intelligence_brief_record", "intelligence_brief_audit_record"},
        )
        persist_action.assert_called_once()
        approval_event.assert_called_once()


if __name__ == "__main__":
    unittest.main()
