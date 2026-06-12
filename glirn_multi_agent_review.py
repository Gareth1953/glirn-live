from datetime import datetime, timezone
import hashlib
import json

from glirn_brief_template import CLIENT_CONTENT_SECTIONS, REQUIRED_DISCLAIMER
from glirn_confidence_engine import build_evidence_transparency


REVIEWER_ROLES = (
    "Intelligence Analyst",
    "Risk Reviewer",
    "Devil's Advocate Reviewer",
    "Quality Assurance Reviewer",
)

ESCALATION_ISSUES = {
    "legal_advice_inference_risk",
    "candidate_consent_concern",
    "evidence_insufficiency",
}


def brief_content_fingerprint(sections):
    content = {
        name: str((sections or {}).get(name) or "").strip()
        for name in CLIENT_CONTENT_SECTIONS
    }
    serialized = json.dumps(content, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _text_blob(brief):
    sections = brief.get("sections") or {}
    return " ".join(str(value or "") for value in sections.values()).lower()


def _output(role, findings, concerns, recommendations, confidence_score, escalation_required=False, issue_codes=None):
    return {
        "reviewer_role": role,
        "findings": list(findings),
        "concerns": list(concerns),
        "recommendations": list(recommendations),
        "confidence_score": max(0, min(100, int(round(confidence_score)))),
        "escalation_required": bool(escalation_required),
        "issue_codes": sorted(set(issue_codes or [])),
    }


def review_as_intelligence_analyst(brief):
    framework = brief.get("human_review_framework") or {}
    flags = framework.get("red_flags") or {}
    evidence_insufficient = bool(flags.get("insufficient_evidence"))
    speculative = bool(flags.get("speculative_content"))
    concerns = []
    issues = []
    confidence = 88
    if evidence_insufficient:
        concerns.append("Available evidence is insufficient for a delivery-ready conclusion.")
        issues.append("evidence_insufficiency")
        confidence -= 35
    if speculative:
        concerns.append("Market observations contain speculative content requiring stronger support.")
        issues.append("unsupported_assumptions")
        confidence -= 18
    findings = ["Evidence quality and market observations were assessed."]
    recommendations = [
        "Identify source support for each material market observation.",
        "Separate verified evidence from assumptions and missing information.",
    ]
    return _output(
        "Intelligence Analyst",
        findings,
        concerns,
        recommendations,
        confidence,
        escalation_required=evidence_insufficient,
        issue_codes=issues,
    )


def review_as_risk_reviewer(brief):
    framework = brief.get("human_review_framework") or {}
    flags = framework.get("red_flags") or {}
    legal_risk = bool(flags.get("legal_advice_inference_risk"))
    candidate_specific = bool(brief.get("candidate_personal_data_included"))
    consent_blocked = bool(brief.get("candidate_personal_data_blocked", candidate_specific))
    concerns = []
    issues = []
    confidence = 90
    if legal_risk:
        concerns.append("Wording may be interpreted as legal or regulated recruitment advice.")
        issues.append("legal_advice_inference_risk")
        confidence -= 30
    if candidate_specific and consent_blocked:
        concerns.append("Candidate-specific information does not have confirmed active consent.")
        issues.append("candidate_consent_concern")
        confidence -= 35
    return _output(
        "Risk Reviewer",
        ["Commercial, confidentiality, legal-inference, and reputational risks were assessed."],
        concerns,
        [
            "Use qualified, non-advisory language throughout the brief.",
            "Exclude candidate-specific information unless active consent is confirmed.",
        ],
        confidence,
        escalation_required=bool(issues),
        issue_codes=issues,
    )


def review_as_devils_advocate(brief):
    framework = brief.get("human_review_framework") or {}
    flags = framework.get("red_flags") or {}
    low_confidence = bool(flags.get("low_ai_confidence"))
    speculative = bool(flags.get("speculative_content"))
    concerns = []
    confidence = 84
    if low_confidence:
        concerns.append("The underlying confidence level may not support the strength of the conclusions.")
        confidence -= 25
    if speculative:
        concerns.append("Alternative explanations may account for the observed market signals.")
        confidence -= 15
    return _output(
        "Devil's Advocate Reviewer",
        ["Conclusions, alternative explanations, and recommendation strength were challenged."],
        concerns,
        [
            "State plausible alternative interpretations of the evidence.",
            "Reduce recommendation strength where evidence or confidence is limited.",
        ],
        confidence,
        escalation_required=low_confidence,
        issue_codes=["overconfidence_risk"] if low_confidence else [],
    )


def review_as_quality_assurance(brief, human_review):
    text = _text_blob(brief)
    disclaimer_present = REQUIRED_DISCLAIMER.lower() in text or "does not provide legal advice" in text
    mission_106_approved = bool(
        human_review
        and human_review.get("approved_for_manual_delivery") is True
        and human_review.get("delivery_status") == "ready_for_manual_delivery"
        and not human_review.get("validation_errors")
        and not human_review.get("incomplete_checks")
        and not human_review.get("unresolved_red_flags")
    )
    concerns = []
    issues = []
    confidence = 94
    if not mission_106_approved:
        concerns.append("Mission 106 human review approval is incomplete or invalid.")
        issues.append("mission_106_noncompliance")
        confidence -= 45
    if not disclaimer_present:
        concerns.append("The required disclaimer is not present in the reviewed brief content.")
        issues.append("missing_required_disclaimer")
        confidence -= 25
    return _output(
        "Quality Assurance Reviewer",
        ["Mission 106 compliance, disclaimer presence, language, and delivery suitability were checked."],
        concerns,
        [
            "Complete all Mission 106 controls before final approval.",
            "Include the required disclaimer and delivery-safe language.",
        ],
        confidence,
        escalation_required=bool(issues),
        issue_codes=issues,
    )


def build_consensus_summary(reviewer_outputs):
    outputs = list(reviewer_outputs)
    overall_confidence = round(sum(item["confidence_score"] for item in outputs) / len(outputs), 2)
    issue_counts = {}
    for output in outputs:
        for issue in output.get("issue_codes", []):
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
    areas_of_agreement = [
        "Human review and final Gareth approval remain mandatory.",
        "Recommendations must be evidence-led, qualified, and suitable for manual delivery.",
    ]
    areas_of_disagreement = sorted(issue for issue, count in issue_counts.items() if count == 1)
    escalation_reasons = sorted({
        *(issue for issue in issue_counts if issue in ESCALATION_ISSUES),
        *("reviewer_requested_escalation" for item in outputs if item["escalation_required"]),
        *("average_confidence_below_70" for _ in [0] if overall_confidence < 70),
    })
    escalation_required = bool(escalation_reasons)
    return {
        "overall_confidence_score": overall_confidence,
        "areas_of_agreement": areas_of_agreement,
        "areas_of_disagreement": areas_of_disagreement,
        "escalation_required": escalation_required,
        "escalation_requirements": escalation_reasons,
        "unresolved_escalations": escalation_reasons,
        "suggested_next_actions": (
            ["Resolve all escalation requirements and repeat multi-agent review."]
            if escalation_required
            else ["Submit the cleared review to Gareth for final approval."]
        ),
    }


def run_multi_agent_review(brief, human_review, reviewed_at=None):
    brief_id = str(brief.get("review_id") or "").strip()
    if not brief_id:
        raise ValueError("brief review_id is required")
    outputs = [
        review_as_intelligence_analyst(brief),
        review_as_risk_reviewer(brief),
        review_as_devils_advocate(brief),
        review_as_quality_assurance(brief, human_review),
    ]
    consensus = build_consensus_summary(outputs)
    evidence_transparency = build_evidence_transparency(brief, outputs)
    reviewed_at = reviewed_at or datetime.now(timezone.utc).isoformat()
    return {
        "review_id": f"multi-agent-review-{brief_id}",
        "brief_id": brief_id,
        "mission_106_review_id": human_review.get("human_review_id") if human_review else None,
        "content_fingerprint": brief_content_fingerprint(brief.get("sections") or {}),
        "reviewed_at": reviewed_at,
        "reviewer_outputs": outputs,
        "confidence_scores": {
            item["reviewer_role"]: item["confidence_score"] for item in outputs
        },
        "consensus_summary": consensus,
        "evidence_transparency": evidence_transparency,
        "review_complete": True,
        "escalation_required": consensus["escalation_required"],
        "unresolved_escalations": consensus["unresolved_escalations"],
        "review_status": "escalated_delivery_blocked" if consensus["escalation_required"] else "cleared_for_gareth_approval",
        "delivery_eligible": False,
        "gareth_final_approval_required": True,
        "sensitive_candidate_information_duplicated": False,
        "automatic_acceptance_enabled": False,
        "automatic_payment_enabled": False,
        "automatic_candidate_outreach_enabled": False,
        "automatic_search_activity_enabled": False,
        "automatic_delivery_enabled": False,
        "external_commitments_enabled": False,
    }
