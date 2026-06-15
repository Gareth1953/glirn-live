import unittest

from glirn_visibility_engine import (
    DISCLAIMER,
    LINKEDIN_THEMES,
    SUPPORTED_MARKETS,
    WEBSITE_ASSET_TYPES,
    apply_gareth_visibility_decision,
    generate_visibility_package,
)


def package(markets=None):
    return generate_visibility_package(
        "growth-phase-1",
        "Cross-border legal hiring demand",
        "AI and Technology Law",
        markets or list(SUPPORTED_MARKETS),
        ["Public market reporting indicates continued demand for specialist legal capability."],
        generated_at="2026-06-14T10:00:00+00:00",
    )


class VisibilityPreparationEngineTests(unittest.TestCase):
    def test_generates_all_linkedin_content_themes(self):
        result = package(["United Kingdom"])
        self.assertEqual({item["theme"] for item in result["linkedin_posts"]}, set(LINKEDIN_THEMES))
        self.assertTrue(all(item["publication_status"] == "blocked_pending_gareth_approval" for item in result["linkedin_posts"]))

    def test_generates_reports_for_all_supported_markets(self):
        result = package()
        self.assertEqual({item["market"] for item in result["intelligence_reports"]}, set(SUPPORTED_MARKETS))
        for report in result["intelligence_reports"]:
            self.assertIn(DISCLAIMER, report["markdown"])
            self.assertTrue(report["suggested_filename"].endswith(".md"))
            self.assertEqual(report["download_status"], "blocked_pending_gareth_approval")

    def test_generates_all_website_asset_types(self):
        result = package(["Singapore"])
        self.assertEqual({item["asset_type"] for item in result["website_assets"]}, set(WEBSITE_ASSET_TYPES))

    def test_generates_linkedin_report_and_website_schedules(self):
        calendar = package(["Europe", "United States"])["content_calendar"]
        self.assertEqual(len(calendar["weekly_linkedin_schedule"]), 4)
        self.assertEqual(len(calendar["monthly_intelligence_report_schedule"]), 2)
        self.assertEqual(len(calendar["website_publication_schedule"]), 4)
        self.assertFalse(calendar["automatic_scheduling_enabled"])

    def test_internal_review_and_approval_package_are_mandatory(self):
        result = package(["United Arab Emirates"])
        self.assertTrue(result["internal_review"]["review_passed"])
        self.assertTrue(result["approval_package"]["internal_review_passed"])
        self.assertEqual(result["approval_package"]["approval_status"], "awaiting_gareth_approval")
        self.assertFalse(result["automatic_publishing_enabled"])

    def test_gareth_approval_enables_local_download_not_publication(self):
        decision = apply_gareth_visibility_decision(
            package(["United Kingdom"]),
            "APPROVE",
            "Approved for manual publication preparation after final human review.",
        )
        self.assertEqual(decision["decision_by"], "Gareth")
        self.assertTrue(decision["approved_for_manual_publication"])
        self.assertTrue(decision["report_download_enabled"])
        self.assertFalse(decision["publication_executed"])
        self.assertFalse(decision["linkedin_posting_enabled"])
        self.assertFalse(decision["website_publishing_enabled"])

    def test_missing_evidence_and_unsupported_markets_are_rejected(self):
        with self.assertRaises(ValueError):
            generate_visibility_package("id", "Topic", "Corporate", ["United Kingdom"], [])
        with self.assertRaises(ValueError):
            generate_visibility_package("id", "Topic", "Corporate", ["Mars"], ["Evidence"])

    def test_all_network_publication_and_contact_paths_are_disabled(self):
        result = package(["United States"])
        for field in (
            "network_client_enabled", "automatic_publishing_enabled", "linkedin_posting_enabled",
            "website_publishing_enabled", "automatic_scheduling_enabled", "outreach_enabled",
            "contact_functionality_enabled", "external_commitments_enabled",
        ):
            self.assertFalse(result[field])


if __name__ == "__main__":
    unittest.main()
