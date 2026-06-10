from datetime import datetime, timezone
import re


GLIRN_PRINCIPLE = "Human-led. Technology-enhanced. Confidentiality-first."

REQUIRED_DISCLAIMER = (
    "GLIRN does not provide legal advice, regulated recruitment advice, or guaranteed hiring outcomes. "
    "This Intelligence Brief is intended to support internal discussion and must be reviewed alongside "
    "independent professional judgement."
)

REQUIRED_SECTIONS = (
    "Client Context",
    "Scope of Brief",
    "Hiring Priority Assessment",
    "Market Observations",
    "Risks and Considerations",
    "Indicative Next Steps",
    "Human Review Summary",
    "Required Disclaimer",
)

CLIENT_CONTENT_SECTIONS = REQUIRED_SECTIONS[:6]


class IntelligenceBriefValidationError(ValueError):
    pass


def _required_text(value, field_name):
    text = str(value or "").strip()
    if not text:
        raise IntelligenceBriefValidationError(f"{field_name} is required")
    return text


def _validate_mission_106_review(source_brief, human_review):
    brief_id = _required_text(source_brief.get("review_id"), "source brief review_id")
    review_brief_id = _required_text(human_review.get("brief_id"), "human review brief_id")
    if review_brief_id != brief_id:
        raise IntelligenceBriefValidationError("Mission 106 review does not match the intelligence brief")
    if human_review.get("outcome") != "approved_for_manual_delivery":
        raise IntelligenceBriefValidationError("Mission 106 approval is required before package generation")
    if human_review.get("approved_for_manual_delivery") is not True:
        raise IntelligenceBriefValidationError("Mission 106 review has not approved manual delivery")
    if human_review.get("delivery_status") != "ready_for_manual_delivery":
        raise IntelligenceBriefValidationError("Mission 106 review is not ready for manual delivery")
    if human_review.get("validation_errors"):
        raise IntelligenceBriefValidationError("Mission 106 review contains validation errors")
    if human_review.get("incomplete_checks"):
        raise IntelligenceBriefValidationError("Mission 106 checklist is incomplete")
    if human_review.get("unresolved_red_flags"):
        raise IntelligenceBriefValidationError("Mission 106 red flags remain unresolved")
    reviewer = _required_text(human_review.get("reviewer"), "reviewer identity")
    reviewed_at = _required_text(human_review.get("reviewed_at"), "review date")
    review_id = _required_text(human_review.get("human_review_id"), "human review record id")
    return brief_id, review_id, reviewer, reviewed_at


def render_intelligence_brief_markdown(package):
    lines = [
        "# GLIRN Intelligence Brief",
        "",
        GLIRN_PRINCIPLE,
        "",
        f"Brief ID: {package['brief_record_id']}",
        f"Mission 106 review record: {package['review_record_id']}",
        f"Audit record: {package['audit_record_id']}",
        f"Reviewer: {package['reviewer_identity']}",
        f"Review date: {package['review_date']}",
        "",
    ]
    for section_name in REQUIRED_SECTIONS:
        lines.extend([f"## {section_name}", "", package["sections"][section_name], ""])
    lines.extend([
        "Delivery status: Ready for manual delivery only.",
        "Automatic delivery: Disabled.",
        "External delivery integrations: Disabled.",
    ])
    return "\n".join(lines).strip() + "\n"


def build_intelligence_brief_package(
    source_brief,
    human_review,
    sections,
    audit_record_id=None,
    generated_at=None,
):
    brief_id, review_id, reviewer, reviewed_at = _validate_mission_106_review(
        source_brief,
        human_review,
    )
    supplied_sections = sections or {}
    final_sections = {
        name: _required_text(supplied_sections.get(name), name)
        for name in CLIENT_CONTENT_SECTIONS
    }
    rationale = _required_text(human_review.get("approval_rationale"), "approval rationale")
    final_sections["Human Review Summary"] = (
        f"Reviewed by {reviewer} on {reviewed_at}. "
        f"Mission 106 outcome: approved for manual delivery. Rationale: {rationale}"
    )
    final_sections["Required Disclaimer"] = REQUIRED_DISCLAIMER

    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    brief_record_id = f"intelligence-brief-{brief_id}"
    package_id = f"delivery-package-{brief_id}"
    audit_record_id = audit_record_id or f"intelligence-brief-audit-{brief_id}"
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", brief_record_id).strip("-")
    package = {
        "package_id": package_id,
        "brief_record_id": brief_record_id,
        "source_brief_id": brief_id,
        "review_record_id": review_id,
        "audit_record_id": audit_record_id,
        "generated_at": generated_at,
        "reviewer_identity": reviewer,
        "review_date": reviewed_at,
        "principle": GLIRN_PRINCIPLE,
        "sections": final_sections,
        "required_sections": list(REQUIRED_SECTIONS),
        "delivery_status": "ready_for_manual_delivery",
        "manual_delivery_only": True,
        "automatic_delivery_enabled": False,
        "external_delivery_enabled": False,
        "email_sending_enabled": False,
        "external_upload_enabled": False,
        "external_integrations_enabled": False,
        "local_file_only": True,
        "suggested_filename": f"{safe_name}.md",
    }
    package["markdown"] = render_intelligence_brief_markdown(package)
    return package
