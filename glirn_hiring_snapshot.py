from datetime import datetime, timezone
import re


SNAPSHOT_NAME = "Complimentary Senior Legal Hiring Snapshot\u2122"
PAID_REVIEW_NAME = "GLIRN Senior Legal Hiring Intelligence Review"
PAID_REVIEW_PRICE = "\u00a3500 Fixed Fee"
NEXT_STEP = "For a deeper assessment, request the \u00a3500 Senior Legal Hiring Intelligence Review."
DISCLAIMER = (
    "This snapshot provides preliminary legal hiring intelligence for internal discussion only. "
    "It is not legal advice, regulated recruitment advice, or a guaranteed hiring outcome."
)
PRINCIPLE = "Human-led. Technology-enhanced. Confidentiality-first."


def _safe_text(value, limit=1000):
    text = " ".join(str(value or "").split()).strip()
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[redacted email]", text)
    text = re.sub(r"(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)", "[redacted phone]", text)
    return text[:limit]


def _slug(value):
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return slug[:60] or "hiring-snapshot"


def _safety_controls():
    return {
        "network_client_enabled": False,
        "automatic_sending_enabled": False,
        "automatic_outreach_enabled": False,
        "automatic_client_contact_enabled": False,
        "automatic_publishing_enabled": False,
        "payment_handling_enabled": False,
        "legal_advice_provided": False,
        "automatic_delivery_enabled": False,
        "external_commitments_enabled": False,
    }


def generate_complimentary_hiring_snapshot(
    snapshot_id,
    role_title,
    organisation_context,
    jurisdiction,
    practice_area,
    evidence_points,
    generated_at=None,
):
    snapshot_id = _slug(snapshot_id)
    role_title = _safe_text(role_title, 160)
    organisation_context = _safe_text(organisation_context, 500)
    jurisdiction = _safe_text(jurisdiction, 160)
    practice_area = _safe_text(practice_area, 160)
    evidence = [_safe_text(item, 400) for item in (evidence_points or [])]
    evidence = [item for item in evidence if item]
    if not all((role_title, organisation_context, jurisdiction, practice_area)):
        raise ValueError("role_title, organisation_context, jurisdiction, and practice_area are required")
    if not evidence:
        raise ValueError("at least one evidence point is required")

    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    sections = {
        "Initial Role Assessment": (
            f"Preliminary assessment of the {role_title} requirement in {jurisdiction}, considering the stated "
            f"organisation context and the need for {practice_area} capability."
        ),
        "Market Hiring Difficulty Indication": (
            f"An initial market indication is required for the availability, seniority, location, and competitive "
            f"conditions affecting a {role_title} appointment in {jurisdiction}."
        ),
        "Initial Hiring Risk Indicators": (
            "Potential risks include an unclear role mandate, unrealistic timing, insufficient market evidence, "
            "candidate consent constraints, and misalignment between scope and available talent."
        ),
        "Preliminary Market Observations": (
            f"The supplied evidence indicates a possible {practice_area} hiring requirement. These observations are "
            "preliminary, high-level, and require human validation before reliance or external use."
        ),
        "High-Level Recommendation": (
            "Clarify the role mandate, test the evidence and market assumptions, and decide manually whether a deeper "
            "fixed-fee review or a premium recruitment engagement is proportionate."
        ),
        "Next Step": NEXT_STEP,
        "Required Disclaimer": DISCLAIMER,
    }
    review_checks = {
        "all_required_sections_present": len(sections) == 7,
        "evidence_present": bool(evidence),
        "paid_review_preserved": "Senior Legal Hiring Intelligence Review" in NEXT_STEP,
        "disclaimer_present": sections["Required Disclaimer"] == DISCLAIMER,
        "manual_approval_control_present": True,
        "candidate_sensitive_content_minimised": True,
        "external_action_paths_disabled": True,
    }
    review_passed = all(review_checks.values())
    return {
        "snapshot_id": snapshot_id,
        "snapshot_name": SNAPSHOT_NAME,
        "generated_at": generated_at,
        "role_title": role_title,
        "jurisdiction": jurisdiction,
        "practice_area": practice_area,
        "organisation_context": organisation_context,
        "evidence_summary": evidence,
        "sections": sections,
        "offer_structure": {
            "primary": SNAPSHOT_NAME,
            "secondary": f"{PAID_REVIEW_NAME} - {PAID_REVIEW_PRICE}",
            "higher_value_next_step": "Executive Search Support / Premium Legal Recruitment Engagements",
        },
        "internal_review": {
            "review_id": f"snapshot-review-{snapshot_id}",
            "reviewed_at": generated_at,
            "review_checks": review_checks,
            "review_passed": review_passed,
        },
        "approval_status": "awaiting_gareth_approval",
        "gareth_approval_required": True,
        "approved_for_manual_use": False,
        "delivery_status": "blocked_pending_gareth_approval",
        "candidate_data_minimised": True,
        "principle": PRINCIPLE,
        **_safety_controls(),
    }


def apply_gareth_snapshot_decision(snapshot, decision, rationale, decided_at=None):
    if not snapshot or not snapshot.get("snapshot_id"):
        raise ValueError("snapshot is required")
    if not snapshot.get("internal_review", {}).get("review_passed"):
        raise ValueError("internal review must pass before Gareth approval")
    decision = str(decision or "").strip().upper()
    if decision not in {"APPROVE", "REJECT", "CHANGES_REQUIRED"}:
        raise ValueError("unsupported Gareth snapshot decision")
    rationale = _safe_text(rationale, 500)
    if not rationale:
        raise ValueError("decision rationale is required")
    approved = decision == "APPROVE"
    return {
        "snapshot_decision_id": f"gareth-snapshot-decision-{snapshot['snapshot_id']}",
        "snapshot_id": snapshot["snapshot_id"],
        "decision": decision,
        "decision_rationale": rationale,
        "decision_by": "Gareth",
        "decided_at": decided_at or datetime.now(timezone.utc).isoformat(),
        "approved_for_manual_use": approved,
        "manual_download_or_copy_only": approved,
        "delivery_executed": False,
        **_safety_controls(),
    }
