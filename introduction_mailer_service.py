import os
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage

from notification_service import smtp_settings


def introduction_mailer_enabled():
    return os.getenv("GLIRN_INTRO_MAILER_ENABLED", "").strip().lower() == "true"


def send_approved_introduction(target, approval, suppression_emails=None):
    now = datetime.now(timezone.utc).isoformat()
    email_address = str(target.get("email_address") or "").strip().lower()
    suppressed = {str(item).strip().lower() for item in (suppression_emails or [])}
    result = {
        "send_id": f"firm-mailer-send-{target.get('target_id', 'unknown')}",
        "campaign_id": approval.get("campaign_id"),
        "target_id": target.get("target_id"),
        "recipient_address": email_address,
        "approval_id": approval.get("campaign_approval_id"),
        "approval_status": approval.get("decision"),
        "opt_out_status": "suppressed" if email_address in suppressed else target.get("opt_out_status"),
        "send_status": "blocked",
        "attempted_at": now,
        "sent_at": None,
        "failure_reason": None,
        "automatic_send": False,
        "follow_up_scheduled": False,
        "external_commitment_created": False,
    }
    if email_address in suppressed or target.get("opt_out_status") == "suppressed":
        result["failure_reason"] = "recipient_suppressed"
        return result
    if not approval.get("send_authorised") or target.get("target_id") not in approval.get("approved_target_ids", []):
        result["failure_reason"] = "gareth_approval_required"
        return result
    if not introduction_mailer_enabled():
        result["failure_reason"] = "introduction_mailer_not_enabled"
        return result
    settings = smtp_settings()
    if not settings["configured"]:
        result["failure_reason"] = "smtp_not_configured"
        return result
    try:
        message = EmailMessage()
        message["From"] = settings["from_email"]
        message["To"] = email_address
        message["Subject"] = target["draft_email"]["subject"]
        message.set_content(target["draft_email"]["body"])
        with smtplib.SMTP(settings["host"], int(settings["port"]), timeout=10) as transport:
            transport.starttls()
            transport.login(settings["username"], settings["password"])
            transport.send_message(message)
        result["send_status"] = "sent"
        result["sent_at"] = now
    except Exception:
        result["send_status"] = "delivery_failed"
        result["failure_reason"] = "smtp_delivery_failed"
    return result
