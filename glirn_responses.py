import os
import smtplib
from email.message import EmailMessage


EMPLOYER_ACKNOWLEDGEMENT = {
    "subject": "GLIRN Enquiry Received",
    "body": """Thank you for contacting GLIRN.

Your enquiry has been received and will be reviewed confidentially.

A member of GLIRN will consider your enquiry and next steps.

Human-led. Technology-enhanced. Confidentiality-first.

GLIRN""",
}

CANDIDATE_ACKNOWLEDGEMENT = {
    "subject": "GLIRN Confidential Career Enquiry Received",
    "body": """Thank you for contacting GLIRN.

Your confidential career enquiry has been received.

No candidate information is shared without consent.

A member of GLIRN will review your enquiry.

Human-led. Technology-enhanced. Confidentiality-first.

GLIRN""",
}

FAQ_TEMPLATES = {
    "intelligence_review": {
        "topic": "What is the GBP 500 Intelligence Review?",
        "subject": "GLIRN Senior Legal Hiring Intelligence Review",
        "body": (
            "The GBP 500 Senior Legal Hiring Intelligence Review is a confidential, fixed-scope first step "
            "that may consider role priority, market difficulty, talent availability, search viability, and suggested next steps. "
            "It does not commit either party to an executive search process."
        ),
    },
    "services": {
        "topic": "What services does GLIRN provide?",
        "subject": "GLIRN Services",
        "body": (
            "GLIRN provides senior legal hiring intelligence reviews, confidential executive and partner search support, "
            "legal market intelligence, and confidential career discussions for established and future legal leaders."
        ),
    },
    "confidentiality": {
        "topic": "Are enquiries confidential?",
        "subject": "GLIRN Confidentiality",
        "body": (
            "GLIRN follows a confidentiality-first approach. Enquiries are reviewed carefully, and candidate information "
            "is not shared without consent."
        ),
    },
    "candidates": {
        "topic": "Does GLIRN support candidates?",
        "subject": "GLIRN Support for Legal Professionals",
        "body": (
            "Yes. GLIRN welcomes confidential career discussions with established legal leaders, specialist lawyers, "
            "associates, and other legal professionals. No candidate information is shared without consent."
        ),
    },
    "future_legal_leaders": {
        "topic": "Does GLIRN support future legal leaders?",
        "subject": "GLIRN Support for Future Legal Leaders",
        "body": (
            "Yes. GLIRN welcomes confidential conversations with newly qualified solicitors, associates, rising legal talent, "
            "and future legal leaders building long-term specialist careers."
        ),
    },
    "international": {
        "topic": "Does GLIRN work internationally?",
        "subject": "GLIRN International Support",
        "body": (
            "GLIRN supports legal organisations and legal professionals with international hiring awareness. "
            "The suitability and scope of any specific cross-border requirement is reviewed by a person before commitment."
        ),
    },
}


def is_candidate_lead(lead_record):
    return lead_record.get("lead_type") in {
        "candidate_lead",
        "senior_legal_candidate_lead",
        "future_legal_leader_candidate_lead",
    }


def build_acknowledgement(lead_record):
    template = CANDIDATE_ACKNOWLEDGEMENT if is_candidate_lead(lead_record) else EMPLOYER_ACKNOWLEDGEMENT
    return {
        "acknowledgement_id": f"glirn-acknowledgement-{lead_record.get('lead_id', 'unknown')}",
        "lead_id": lead_record.get("lead_id"),
        "recipient_email": lead_record.get("email"),
        "recipient_type": "candidate" if is_candidate_lead(lead_record) else "employer",
        "subject": template["subject"],
        "body": template["body"],
        "acknowledgement_status": "pending_transport",
        "automatic_acknowledgement_allowed": True,
        "substantive_response_sent": False,
    }


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


def deliver_template_email(recipient, subject, body):
    settings = smtp_settings()
    if not settings["configured"]:
        return {"status": "queued_local_only", "email_sent": False, "smtp_configured": False}

    try:
        message = EmailMessage()
        message["From"] = settings["from_email"]
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)
        with smtplib.SMTP(settings["host"], int(settings["port"]), timeout=10) as transport:
            transport.starttls()
            transport.login(settings["username"], settings["password"])
            transport.send_message(message)
        return {"status": "sent", "email_sent": True, "smtp_configured": True}
    except Exception:
        return {"status": "queued_local_only", "email_sent": False, "smtp_configured": True}


def match_safe_faq(lead):
    text = " ".join([
        str(lead.get("message", "")),
        str(lead.get("hiring_need", "")),
        str(lead.get("confidential_career_interest", "")),
    ]).lower()
    patterns = [
        ("intelligence_review", ["what is the £500", "what is the gbp 500", "500 intelligence review", "senior legal hiring intelligence review"]),
        ("services", ["what services", "services does glirn", "which services"]),
        ("confidentiality", ["are enquiries confidential", "is my enquiry confidential", "is this confidential"]),
        ("future_legal_leaders", ["support future legal leaders", "support newly qualified", "newly qualified solicitors"]),
        ("candidates", ["support candidates", "support legal professionals", "candidate support"]),
        ("international", ["work internationally", "international support", "support internationally", "cross-border"]),
    ]
    for topic, phrases in patterns:
        if any(phrase in text for phrase in phrases):
            return topic
    return None


def build_enquiry_response_package(lead, lead_record, revenue_package):
    acknowledgement = build_acknowledgement(lead_record)
    acknowledgement_delivery = deliver_template_email(
        acknowledgement["recipient_email"], acknowledgement["subject"], acknowledgement["body"]
    )
    acknowledgement["acknowledgement_status"] = acknowledgement_delivery["status"]
    acknowledgement.update({
        "email_sent": acknowledgement_delivery["email_sent"],
        "smtp_configured": acknowledgement_delivery["smtp_configured"],
    })

    faq_topic = match_safe_faq(lead)
    faq_response = None
    if faq_topic:
        template = FAQ_TEMPLATES[faq_topic]
        delivery = deliver_template_email(lead_record.get("email"), template["subject"], template["body"])
        faq_response = {
            "faq_response_id": f"glirn-faq-{lead_record.get('lead_id')}-{faq_topic}",
            "lead_id": lead_record.get("lead_id"),
            "topic": faq_topic,
            "approved_topic": template["topic"],
            "subject": template["subject"],
            "body": template["body"],
            "faq_response_status": delivery["status"],
            "email_sent": delivery["email_sent"],
            "predefined_template_only": True,
            "freeform_ai_response_enabled": False,
        }

    candidate = is_candidate_lead(lead_record)
    draft = {
        "draft_response_id": f"glirn-draft-response-{lead_record.get('lead_id', 'unknown')}",
        "lead_id": lead_record.get("lead_id"),
        "enquiry_summary": str(lead.get("message", ""))[:500],
        "recommended_response": (
            "Review the confidential career enquiry and prepare a personalised response without sharing candidate information."
            if candidate
            else "Review the organisation's requirement and prepare a personalised response without making a search or pricing commitment."
        ),
        "suggested_priority": (
            "High" if revenue_package.get("urgency_score", 0) >= 75
            else "Medium" if revenue_package.get("urgency_score", 0) >= 50
            else "Low"
        ),
        "lead_classification": lead_record.get("lead_type"),
        "revenue_opportunity_classification": revenue_package.get("opportunity_type"),
        "response_status": "safe_faq_template_handled" if faq_response else "awaiting_gareth_approval",
        "substantive_response_sent": False,
        "gareth_approval_required": not bool(faq_response),
        "automatic_sending_enabled": False,
    }

    return {
        "response_package_id": f"glirn-response-package-{lead_record.get('lead_id', 'unknown')}",
        "lead_id": lead_record.get("lead_id"),
        "lead_type": lead_record.get("lead_type"),
        "enquiry_party": "candidate" if candidate else "employer",
        "acknowledgement": acknowledgement,
        "faq_response": faq_response,
        "draft_response": draft,
        "suggested_response": faq_response["body"] if faq_response else draft["recommended_response"],
        "opportunity_classification": revenue_package.get("opportunity_type"),
        "available_actions": ["Approve & Send", "Edit Before Sending", "Reject", "Request More Information"],
        "actions_local_only": True,
        "automatic_executive_search_commitment": False,
        "automatic_candidate_introductions": False,
        "automatic_candidate_sharing": False,
        "automatic_linkedin_messaging": False,
        "automatic_pricing_negotiation": False,
        "automatic_invoice_sending": False,
        "automatic_payment_requests": False,
        "money_movement_enabled": False,
    }
