import unittest
from unittest.mock import patch

from glirn_firm_mailer import (
    MAX_CAMPAIGN_FIRMS,
    OPT_OUT_TEXT,
    apply_campaign_approval,
    build_campaign,
    build_suppression_record,
    validate_general_business_email,
)
from introduction_mailer_service import send_approved_introduction


def firm(index=1, email=None):
    return {
        "firm_name": f"Example Legal {index}",
        "email_address": email or f"info@example{index}.com",
        "jurisdiction": "United Kingdom",
        "practice_signals": ["Technology law", "AI law", "Data protection"],
        "public_source_url": f"https://example{index}.com/services/technology",
        "evidence_summary": "The firm's public website describes technology and data capability.",
        "practice_area_fit": 85,
        "senior_hiring_likelihood": 75,
        "technology_ai_relevance": 90,
        "jurisdiction_fit": 90,
        "evidence_quality": 80,
    }


def campaign(count=1, suppressed=None):
    return build_campaign(
        "pilot-25",
        [firm(index) for index in range(1, count + 1)],
        suppressed_emails=suppressed,
        created_at="2026-06-14T14:00:00+00:00",
    )


class ControlledFirmMailerTests(unittest.TestCase):
    def test_campaign_is_capped_at_25_firms(self):
        result = campaign(MAX_CAMPAIGN_FIRMS)
        self.assertEqual(result["target_count"], 25)
        self.assertEqual(len(result["ranked_targets"]), 25)
        with self.assertRaises(ValueError):
            campaign(MAX_CAMPAIGN_FIRMS + 1)

    def test_ranked_targets_include_required_scores_and_minimal_evidence(self):
        result = campaign(2)
        target = result["ranked_targets"][0]
        self.assertEqual(target["rank"], 1)
        self.assertIn("practice_area_fit", target["scores"])
        self.assertIn("senior_hiring_likelihood", target["scores"])
        self.assertIn("technology_ai_relevance", target["scores"])
        self.assertIn("jurisdiction_fit", target["scores"])
        self.assertIn("evidence_quality", target["scores"])
        self.assertLessEqual(len(target["evidence_summary"]), 500)

    def test_personal_email_harvesting_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "personal email harvesting is prohibited"):
            validate_general_business_email("jane.smith@example.com")
        self.assertEqual(validate_general_business_email("enquiries@example.com"), "enquiries@example.com")

    def test_private_or_restricted_source_urls_are_rejected(self):
        private_firm = firm()
        private_firm["public_source_url"] = "http://192.168.1.10/private-directory"
        with self.assertRaisesRegex(ValueError, "public business source"):
            build_campaign("private-source", [private_firm])

    def test_email_content_is_compliant_and_preserves_paid_review(self):
        draft = campaign()["ranked_targets"][0]["draft_email"]
        self.assertIn("Complimentary Senior Legal Hiring Snapshot\u2122", draft["body"])
        self.assertIn("Senior Legal Hiring Intelligence Review for a \u00a3500 fixed fee", draft["body"])
        self.assertIn("Global Legal Intelligence & Recruitment Network", draft["body"])
        self.assertIn(OPT_OUT_TEXT, draft["body"])
        self.assertIn("does not provide legal advice", draft["body"])
        self.assertNotIn("guarantee", draft["body"].lower())

    def test_approval_is_required_and_never_triggers_send(self):
        result = campaign()
        target_id = result["ranked_targets"][0]["target_id"]
        approval = apply_campaign_approval(result, [target_id], "APPROVE", "Approved by Gareth.")
        self.assertEqual(approval["decision_by"], "Gareth")
        self.assertTrue(approval["send_authorised"])
        self.assertFalse(approval["automatic_send_triggered"])

    def test_opt_out_suppression_blocks_approval_and_send(self):
        result = campaign(suppressed=["info@example1.com"])
        target = result["ranked_targets"][0]
        approval = apply_campaign_approval(result, [target["target_id"]], "APPROVE", "Review target.")
        self.assertEqual(target["opt_out_status"], "suppressed")
        self.assertFalse(approval["send_authorised"])
        send_result = send_approved_introduction(target, approval, [target["email_address"]])
        self.assertEqual(send_result["send_status"], "blocked")
        self.assertEqual(send_result["failure_reason"], "recipient_suppressed")

    def test_no_autonomous_send_when_mailer_is_not_explicitly_enabled(self):
        result = campaign()
        target = result["ranked_targets"][0]
        approval = apply_campaign_approval(result, [target["target_id"]], "APPROVE", "Approved by Gareth.")
        with patch.dict("os.environ", {}, clear=True):
            send_result = send_approved_introduction(target, approval)
        self.assertEqual(send_result["send_status"], "blocked")
        self.assertEqual(send_result["failure_reason"], "introduction_mailer_not_enabled")
        self.assertFalse(send_result["automatic_send"])
        self.assertFalse(send_result["follow_up_scheduled"])

    def test_configured_transport_sends_only_an_approved_target(self):
        result = campaign()
        target = result["ranked_targets"][0]
        approval = apply_campaign_approval(result, [target["target_id"]], "APPROVE", "Approved by Gareth.")
        environment = {
            "GLIRN_INTRO_MAILER_ENABLED": "true",
            "GLIRN_SMTP_HOST": "smtp.example.com",
            "GLIRN_SMTP_PORT": "587",
            "GLIRN_SMTP_USERNAME": "mailer-user",
            "GLIRN_SMTP_PASSWORD": "mailer-password",
            "GLIRN_FROM_EMAIL": "legalintelligencerecruitment@outlook.com",
        }
        with patch.dict("os.environ", environment, clear=True), \
                patch("introduction_mailer_service.smtplib.SMTP") as smtp:
            send_result = send_approved_introduction(target, approval)
        self.assertEqual(send_result["send_status"], "sent")
        self.assertFalse(send_result["automatic_send"])
        transport = smtp.return_value.__enter__.return_value
        transport.starttls.assert_called_once_with()
        transport.login.assert_called_once_with("mailer-user", "mailer-password")
        transport.send_message.assert_called_once()

    def test_suppression_record_blocks_future_sends(self):
        record = build_suppression_record("recruitment@example.com", "opt_out_requested")
        self.assertEqual(record["opt_out_status"], "suppressed")
        self.assertTrue(record["future_sends_blocked"])


if __name__ == "__main__":
    unittest.main()
