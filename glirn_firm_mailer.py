from datetime import datetime, timezone
import ipaddress
import re
from urllib.parse import urlparse


MAX_CAMPAIGN_FIRMS = 25
GENERAL_MAILBOX_PREFIXES = {
    "business",
    "careers",
    "contact",
    "enquiries",
    "enquiry",
    "hello",
    "info",
    "office",
    "recruitment",
}
SUBJECT = "Complimentary Senior Legal Hiring Snapshot from GLIRN"
OPT_OUT_TEXT = (
    "If you would prefer not to receive further introductory emails from GLIRN, "
    "please reply with 'Opt out' and we will add this address to our suppression list."
)
PRINCIPLE = "Human-led. Technology-enhanced. Confidentiality-first."


def _safe_text(value, limit=600):
    text = " ".join(str(value or "").split()).strip()
    text = re.sub(r"[\r\n]+", " ", text)
    return text[:limit]


def _slug(value):
    value = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return value[:60] or "firm-mailer"


def _score(value, field_name):
    try:
        score = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer from 0 to 100") from exc
    if score < 0 or score > 100:
        raise ValueError(f"{field_name} must be an integer from 0 to 100")
    return score


def validate_general_business_email(email):
    email = str(email or "").strip().lower()
    if len(email) > 254 or not re.fullmatch(
        r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+",
        email,
    ):
        raise ValueError("valid publicly listed business email is required")
    local_part = email.split("@", 1)[0]
    if local_part not in GENERAL_MAILBOX_PREFIXES:
        raise ValueError("personal email harvesting is prohibited; use a general business mailbox")
    return email


def _validate_public_source(source_url):
    source_url = str(source_url or "").strip()
    parsed = urlparse(source_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("public_source_url must be a public http or https URL")
    hostname = parsed.hostname or ""
    if parsed.username or parsed.password or hostname == "localhost":
        raise ValueError("public_source_url must reference a public business source")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address and not address.is_global:
        raise ValueError("public_source_url must reference a public business source")
    return source_url[:500]


def score_firm(firm):
    scores = {
        "practice_area_fit": _score(firm.get("practice_area_fit"), "practice_area_fit"),
        "senior_hiring_likelihood": _score(
            firm.get("senior_hiring_likelihood"), "senior_hiring_likelihood"
        ),
        "technology_ai_relevance": _score(
            firm.get("technology_ai_relevance"), "technology_ai_relevance"
        ),
        "jurisdiction_fit": _score(firm.get("jurisdiction_fit"), "jurisdiction_fit"),
        "evidence_quality": _score(firm.get("evidence_quality"), "evidence_quality"),
    }
    weighted = (
        scores["practice_area_fit"] * 0.25
        + scores["senior_hiring_likelihood"] * 0.20
        + scores["technology_ai_relevance"] * 0.25
        + scores["jurisdiction_fit"] * 0.15
        + scores["evidence_quality"] * 0.15
    )
    return round(weighted, 1), scores


def build_introduction_email(firm_name, reason_selected):
    body = "\n".join([
        f"Hello {firm_name} team,",
        "",
        "I am Gareth, founder of GLIRN, the Global Legal Intelligence & Recruitment Network.",
        "",
        "GLIRN helps law firms consider senior legal hiring risks, opportunities and market conditions before committing to an expensive hire.",
        "",
        "I would be pleased to prepare a Complimentary Senior Legal Hiring Snapshot\u2122 for a current or anticipated senior hiring requirement. The snapshot provides an initial role assessment, hiring difficulty indication, preliminary risk indicators, market observations and a high-level recommendation.",
        "",
        "Where a deeper assessment would be useful, GLIRN also offers the Senior Legal Hiring Intelligence Review for a \u00a3500 fixed fee, subject to manual scope review and written acceptance.",
        "",
        f"Why this may be relevant: {reason_selected}",
        "",
        "This introduction is general recruitment intelligence and does not provide legal advice or create any commitment.",
        "",
        OPT_OUT_TEXT,
        "",
        "Gareth",
        "GLIRN | Global Legal Intelligence & Recruitment Network",
        PRINCIPLE,
    ])
    return {"subject": SUBJECT, "body": body}


def build_campaign(campaign_id, firms, suppressed_emails=None, created_at=None):
    firms = list(firms or [])
    if not firms:
        raise ValueError("at least one curated law firm is required")
    if len(firms) > MAX_CAMPAIGN_FIRMS:
        raise ValueError("Growth Phase 1B is capped at 25 curated law firms")
    suppressed = {str(item).strip().lower() for item in (suppressed_emails or [])}
    prepared = []
    seen_emails = set()
    for index, firm in enumerate(firms, start=1):
        firm_name = _safe_text(firm.get("firm_name"), 200)
        jurisdiction = _safe_text(firm.get("jurisdiction"), 120)
        practice_signals = [_safe_text(item, 100) for item in firm.get("practice_signals", [])]
        practice_signals = [item for item in practice_signals if item]
        evidence_summary = _safe_text(firm.get("evidence_summary"), 500)
        if not firm_name or not jurisdiction or not practice_signals or not evidence_summary:
            raise ValueError("firm_name, jurisdiction, practice_signals, and evidence_summary are required")
        email = validate_general_business_email(firm.get("email_address"))
        if email in seen_emails:
            raise ValueError("duplicate firm email addresses are not allowed")
        seen_emails.add(email)
        source_url = _validate_public_source(firm.get("public_source_url"))
        fit_score, scores = score_firm(firm)
        strongest = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:2]
        reason = (
            f"Public business information indicates relevance in {', '.join(practice_signals[:4])}; "
            f"strongest assessed factors are {strongest[0][0].replace('_', ' ')} and "
            f"{strongest[1][0].replace('_', ' ')}."
        )
        risk_flags = []
        if scores["evidence_quality"] < 60:
            risk_flags.append("limited_public_evidence_quality")
        if scores["jurisdiction_fit"] < 60:
            risk_flags.append("jurisdiction_fit_requires_review")
        if email in suppressed:
            risk_flags.append("email_suppressed")
        draft = build_introduction_email(firm_name, reason)
        prepared.append({
            "target_id": f"target-{index:02d}-{_slug(firm_name)}",
            "firm_name": firm_name,
            "email_address": email,
            "jurisdiction": jurisdiction,
            "practice_signals": practice_signals,
            "public_source_url": source_url,
            "evidence_summary": evidence_summary,
            "scores": scores,
            "fit_score": fit_score,
            "reason_selected": reason,
            "draft_email": draft,
            "risk_flags": risk_flags,
            "approval_status": "awaiting_gareth_approval",
            "opt_out_status": "suppressed" if email in suppressed else "not_opted_out",
            "send_status": "blocked_pending_gareth_approval",
        })
    prepared.sort(key=lambda item: (-item["fit_score"], item["firm_name"].lower()))
    for rank, item in enumerate(prepared, start=1):
        item["rank"] = rank
    created_at = created_at or datetime.now(timezone.utc).isoformat()
    return {
        "campaign_id": _slug(campaign_id),
        "created_at": created_at,
        "campaign_status": "draft_pending_gareth_approval",
        "target_count": len(prepared),
        "maximum_target_count": MAX_CAMPAIGN_FIRMS,
        "ranked_targets": prepared,
        "approval_package": {
            "approval_package_id": f"firm-mailer-approval-{_slug(campaign_id)}",
            "approval_status": "awaiting_gareth_approval",
            "gareth_approval_required_for_each_email_or_batch": True,
        },
        "public_business_information_only": True,
        "personal_email_harvesting_enabled": False,
        "automatic_sending_enabled": False,
        "follow_up_automation_enabled": False,
        "linkedin_automation_enabled": False,
        "candidate_outreach_enabled": False,
        "payment_handling_enabled": False,
        "legal_advice_provided": False,
        "external_commitments_enabled": False,
        "network_sending_requires_configuration_and_gareth_approval": True,
    }


def apply_campaign_approval(campaign, target_ids, decision, rationale, decided_at=None):
    if not campaign or not campaign.get("campaign_id"):
        raise ValueError("campaign is required")
    target_ids = list(dict.fromkeys(target_ids or []))
    if not target_ids:
        raise ValueError("at least one target_id is required")
    known = {item["target_id"]: item for item in campaign.get("ranked_targets", [])}
    if any(target_id not in known for target_id in target_ids):
        raise ValueError("approval contains an unknown campaign target")
    decision = str(decision or "").strip().upper()
    if decision not in {"APPROVE", "REJECT", "CHANGES_REQUIRED"}:
        raise ValueError("unsupported Gareth campaign decision")
    rationale = _safe_text(rationale, 500)
    if not rationale:
        raise ValueError("decision rationale is required")
    approved_ids = [
        target_id for target_id in target_ids
        if decision == "APPROVE" and known[target_id].get("opt_out_status") != "suppressed"
    ]
    return {
        "campaign_approval_id": f"gareth-mailer-approval-{campaign['campaign_id']}-{len(target_ids)}",
        "campaign_id": campaign["campaign_id"],
        "target_ids": target_ids,
        "approved_target_ids": approved_ids,
        "decision": decision,
        "decision_rationale": rationale,
        "decision_by": "Gareth",
        "decided_at": decided_at or datetime.now(timezone.utc).isoformat(),
        "send_authorised": decision == "APPROVE" and len(approved_ids) == len(target_ids),
        "automatic_send_triggered": False,
        "external_commitment_created": False,
    }


def build_suppression_record(email_address, reason, recorded_at=None):
    email = validate_general_business_email(email_address)
    reason = _safe_text(reason, 250)
    if not reason:
        raise ValueError("suppression reason is required")
    return {
        "suppression_id": f"suppression-{_slug(email)}",
        "email_address": email,
        "opt_out_status": "suppressed",
        "reason_code": reason,
        "recorded_at": recorded_at or datetime.now(timezone.utc).isoformat(),
        "future_sends_blocked": True,
    }
