import os
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage


GLIRN_BUSINESS_EMAIL = "legalintelligencerecruitment@outlook.com"
NOTIFICATION_SUBJECT = "[GLIRN] New Enquiry Received – Manual Review Required"
MANUAL_REVIEW_NOTICE = (
    "Human review is required before any response, acceptance of work, payment discussion, "
    "intelligence brief preparation, or search activity."
)


def smtp_settings():
    values = {
        "host": os.getenv("GLIRN_SMTP_HOST", "").strip(),
        "port": os.getenv("GLIRN_SMTP_PORT", "").strip(),
        "username": os.getenv("GLIRN_SMTP_USERNAME", "").strip(),
        "password": os.getenv("GLIRN_SMTP_PASSWORD", ""),
        "from_email": os.getenv("GLIRN_FROM_EMAIL", "").strip(),
    }
    values["configured"] = all(values.values())
    return values


def build_enquiry_notification_email(enquiry):
    enquiry_id = str(enquiry.get("lead_id") or "unknown")
    submitted_at = str(enquiry.get("received_at") or "not recorded")
    fields = [
        ("Enquiry ID", enquiry_id),
        ("Submission timestamp", submitted_at),
        ("Enquiry type", enquiry.get("inquiry_type")),
        ("Name", enquiry.get("name")),
        ("Organisation", enquiry.get("organisation")),
        ("Country", enquiry.get("country")),
        ("Practice area", enquiry.get("practice_area") or enquiry.get("legal_sector")),
        ("Jurisdiction", enquiry.get("jurisdiction")),
        ("Seniority", enquiry.get("seniority_level")),
        ("Timescale", enquiry.get("timescale")),
    ]
    body_lines = ["A new GLIRN website enquiry has been received.", ""]
    body_lines.extend(f"{label}: {str(value or 'Not provided')}" for label, value in fields)
    body_lines.extend([
        "",
        "Full enquiry message:",
        str(enquiry.get("message") or "Not provided"),
        "",
        MANUAL_REVIEW_NOTICE,
        "",
        "This notification is informational only.",
        "Human-led. Technology-enhanced. Confidentiality-first.",
    ])
    return {
        "notification_id": f"glirn-enquiry-notification-{enquiry_id}",
        "enquiry_id": enquiry_id,
        "recipient_address": GLIRN_BUSINESS_EMAIL,
        "subject": NOTIFICATION_SUBJECT,
        "body": "\n".join(body_lines),
    }


def deliver_enquiry_notification(enquiry, previous_record=None):
    email = build_enquiry_notification_email(enquiry)
    previous_record = previous_record or {}
    now = datetime.now(timezone.utc).isoformat()
    retry_attempts = int(previous_record.get("retry_attempts", 0) or 0)
    attempt_number = int(previous_record.get("attempt_count", 0) or 0) + 1
    settings = smtp_settings()
    delivery_status = "delivery_failed"
    failure_reason = "smtp_not_configured"

    if settings["configured"]:
        try:
            message = EmailMessage()
            message["From"] = settings["from_email"]
            message["To"] = email["recipient_address"]
            message["Subject"] = email["subject"]
            message.set_content(email["body"])
            with smtplib.SMTP(settings["host"], int(settings["port"]), timeout=10) as transport:
                transport.starttls()
                transport.login(settings["username"], settings["password"])
                transport.send_message(message)
            delivery_status = "sent"
            failure_reason = None
        except Exception:
            failure_reason = "smtp_delivery_failed"

    if previous_record:
        retry_attempts += 1

    return {
        "notification_id": email["notification_id"],
        "related_enquiry_id": email["enquiry_id"],
        "recipient_address": email["recipient_address"],
        "delivery_status": delivery_status,
        "created_at": previous_record.get("created_at") or now,
        "last_attempt_at": now,
        "delivered_at": now if delivery_status == "sent" else previous_record.get("delivered_at"),
        "attempt_count": attempt_number,
        "retry_attempts": retry_attempts,
        "failure_reason": failure_reason,
        "manual_resend_available": delivery_status != "sent",
        "informational_only": True,
        "business_email_notification_only": True,
        "automatic_acceptance_enabled": False,
        "automatic_payment_enabled": False,
        "automatic_brief_generation_enabled": False,
        "automatic_candidate_outreach_enabled": False,
        "automatic_search_activity_enabled": False,
        "automatic_delivery_enabled": False,
        "external_integrations_enabled": False,
    }
