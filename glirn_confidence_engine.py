from datetime import datetime, timezone
import re


CONFIDENCE_WEIGHTS = {
    "evidence_sufficiency": 0.20,
    "evidence_quality": 0.15,
    "reviewer_agreement": 0.15,
    "escalation_presence": 0.15,
    "human_review_outcome": 0.10,
    "candidate_consent_completeness": 0.10,
    "data_recency": 0.075,
    "market_information_completeness": 0.075,
}

EVIDENCE_TRANSPARENCY_FIELDS = (
    "key_evidence_considered",
    "supporting_assumptions",
    "known_limitations",
    "areas_requiring_caution",
    "information_gaps_identified",
    "alternative_interpretations",
)


def confidence_category(score):
    normalized = float(score)
    if normalized >= 90:
        return "Very High Confidence"
    if normalized >= 75:
        return "High Confidence"
    if normalized >= 60:
        return "Moderate Confidence"
    return "Low Confidence"


def _rating(value, field_name):
    try:
        rating = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a number from 0 to 100") from exc
    if not 0 <= rating <= 100:
        raise ValueError(f"{field_name} must be from 0 to 100")
    return round(rating, 2)


def _safe_summary(value):
    text = " ".join(str(value or "").split()).strip()
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[redacted email]", text)
    text = re.sub(r"(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)", "[redacted phone]", text)
    return text[:500]


def _safe_list(values, fallback):
    items = []
    for value in values or []:
        item = _safe_summary(value)
        if item and item not in items:
            items.append(item)
    return items[:12] or list(fallback)


def reviewer_agreement(multi_agent_review):
    scores = [
        _rating(item.get("confidence_score", 0), "reviewer confidence score")
        for item in (multi_agent_review.get("reviewer_outputs") or [])
    ]
    if not scores:
        return {"score": 0.0, "level": "Low", "score_spread": 100.0, "significant_disagreement": True}
    spread = max(scores) - min(scores)
    score = round(max(0.0, 100.0 - (spread * 2.0)), 2)
    if score >= 85:
        level = "High"
    elif score >= 70:
        level = "Moderate"
    else:
        level = "Low"
    return {
        "score": score,
        "level": level,
        "score_spread": round(spread, 2),
        "significant_disagreement": score < 70,
    }


def build_evidence_transparency(brief, reviewer_outputs=None, supplied=None):
    supplied = supplied or {}
    outputs = list(reviewer_outputs or [])
    concerns = [concern for output in outputs for concern in output.get("concerns", [])]
    recommendations = [item for output in outputs for item in output.get("recommendations", [])]
    alternatives = [
        concern
        for output in outputs
        if output.get("reviewer_role") == "Devil's Advocate Reviewer"
        for concern in output.get("concerns", [])
    ]
    flags = ((brief.get("human_review_framework") or {}).get("red_flags") or {})
    assumptions = []
    if flags.get("speculative_content"):
        assumptions.append("Some market observations rely on assumptions that require validation.")
    if flags.get("low_ai_confidence"):
        assumptions.append("AI-assisted observations require cautious human interpretation.")
    gaps = []
    if flags.get("insufficient_evidence"):
        gaps.append("Further evidence is required before conclusions can be relied upon.")

    return {
        "key_evidence_considered": _safe_list(
            supplied.get("key_evidence_considered"),
            ["Client context, scoped market observations, and Mission 106 review findings."],
        ),
        "supporting_assumptions": _safe_list(
            supplied.get("supporting_assumptions") or assumptions,
            ["Market conditions may change and observations are limited to the reviewed scope."],
        ),
        "known_limitations": _safe_list(
            supplied.get("known_limitations") or concerns,
            ["The brief is decision support and does not replace independent professional judgement."],
        ),
        "areas_requiring_caution": _safe_list(
            supplied.get("areas_requiring_caution") or recommendations,
            ["Use qualified language and validate material observations before acting."],
        ),
        "information_gaps_identified": _safe_list(
            supplied.get("information_gaps_identified") or gaps,
            ["No material information gap was identified within the reviewed scope."],
        ),
        "alternative_interpretations": _safe_list(
            supplied.get("alternative_interpretations") or alternatives,
            ["Alternative market explanations were considered and no material alternative was identified."],
        ),
        "candidate_data_minimised": True,
        "confidential_source_material_duplicated": False,
    }


def render_evidence_transparency_markdown(assessment):
    transparency = assessment["evidence_transparency"]
    factor_scores = assessment.get("factor_scores") or {}
    evidence_sufficiency = factor_scores.get(
        "evidence_sufficiency",
        assessment.get("evidence_sufficiency_rating", "not assessed"),
    )
    labels = {
        "key_evidence_considered": "Key evidence considered",
        "supporting_assumptions": "Supporting assumptions",
        "known_limitations": "Known limitations",
        "areas_requiring_caution": "Areas requiring caution",
        "information_gaps_identified": "Information gaps identified",
        "alternative_interpretations": "Alternative interpretations identified during Mission 109 review",
    }
    lines = [
        "## Confidence and Evidence Transparency",
        "",
        f"Confidence score: {assessment['confidence_score']}",
        f"Confidence category: {assessment['confidence_category']}",
        f"Evidence sufficiency rating: {evidence_sufficiency}",
        f"Reviewer agreement level: {assessment['reviewer_agreement']['level']}",
        "",
    ]
    for key in EVIDENCE_TRANSPARENCY_FIELDS:
        lines.extend([f"### {labels[key]}", ""])
        lines.extend(f"- {item}" for item in transparency[key])
        lines.append("")
    return "\n".join(lines).strip()


def assess_confidence(
    brief,
    human_review,
    multi_agent_review,
    evidence_sufficiency,
    evidence_quality,
    data_recency,
    market_information_completeness,
    evidence_transparency=None,
    material_limitations_undermine_conclusions=False,
    assessed_at=None,
):
    brief_id = str(brief.get("review_id") or "").strip()
    if not brief_id:
        raise ValueError("brief review_id is required")
    if not human_review or human_review.get("brief_id") != brief_id:
        raise ValueError("matching Mission 106 review is required")
    if not multi_agent_review or multi_agent_review.get("brief_id") != brief_id:
        raise ValueError("matching Mission 109 review is required")
    if not multi_agent_review.get("review_complete"):
        raise ValueError("Mission 109 review must be complete")

    agreement = reviewer_agreement(multi_agent_review)
    human_approved = bool(
        human_review.get("approved_for_manual_delivery") is True
        and human_review.get("delivery_status") == "ready_for_manual_delivery"
        and not human_review.get("validation_errors")
        and not human_review.get("incomplete_checks")
        and not human_review.get("unresolved_red_flags")
    )
    candidate_specific = bool(brief.get("candidate_personal_data_included"))
    consent_complete = not candidate_specific or not bool(brief.get("candidate_personal_data_blocked", True))
    mission_109_escalation = bool(
        multi_agent_review.get("escalation_required")
        or multi_agent_review.get("unresolved_escalations")
    )
    factor_scores = {
        "evidence_sufficiency": _rating(evidence_sufficiency, "evidence_sufficiency"),
        "evidence_quality": _rating(evidence_quality, "evidence_quality"),
        "reviewer_agreement": agreement["score"],
        "escalation_presence": 0.0 if mission_109_escalation else 100.0,
        "human_review_outcome": 100.0 if human_approved else 0.0,
        "candidate_consent_completeness": 100.0 if consent_complete else 0.0,
        "data_recency": _rating(data_recency, "data_recency"),
        "market_information_completeness": _rating(
            market_information_completeness,
            "market_information_completeness",
        ),
    }
    weighted_components = {
        name: round(factor_scores[name] * weight, 2)
        for name, weight in CONFIDENCE_WEIGHTS.items()
    }
    score = round(sum(weighted_components.values()), 2)
    escalation_reasons = []
    if score < 70:
        escalation_reasons.append("confidence_below_70")
    if factor_scores["evidence_sufficiency"] < 70:
        escalation_reasons.append("evidence_sufficiency_inadequate")
    if agreement["significant_disagreement"]:
        escalation_reasons.append("significant_reviewer_disagreement")
    if material_limitations_undermine_conclusions:
        escalation_reasons.append("material_limitations_undermine_conclusions")
    if mission_109_escalation:
        escalation_reasons.append("mission_109_escalation_unresolved")
    if not human_approved:
        escalation_reasons.append("mission_106_approval_invalid")
    if not consent_complete:
        escalation_reasons.append("candidate_consent_incomplete")
    escalation_reasons = sorted(set(escalation_reasons))
    transparency = build_evidence_transparency(
        brief,
        multi_agent_review.get("reviewer_outputs") or [],
        evidence_transparency,
    )
    assessed_at = assessed_at or datetime.now(timezone.utc).isoformat()
    return {
        "confidence_assessment_id": f"confidence-assessment-{brief_id}",
        "brief_id": brief_id,
        "mission_106_review_id": human_review.get("human_review_id"),
        "mission_109_review_id": multi_agent_review.get("review_id"),
        "content_fingerprint": multi_agent_review.get("content_fingerprint"),
        "assessed_at": assessed_at,
        "assessment_complete": True,
        "confidence_score": score,
        "confidence_category": confidence_category(score),
        "factor_scores": factor_scores,
        "weighted_components": weighted_components,
        "confidence_weights": dict(CONFIDENCE_WEIGHTS),
        "reviewer_agreement": agreement,
        "evidence_sufficiency_rating": factor_scores["evidence_sufficiency"],
        "outstanding_limitations": transparency["known_limitations"],
        "evidence_transparency": transparency,
        "material_limitations_undermine_conclusions": bool(material_limitations_undermine_conclusions),
        "escalation_required": bool(escalation_reasons),
        "unresolved_escalations": escalation_reasons,
        "assessment_status": "escalated_remediation_required" if escalation_reasons else "cleared_for_gareth_approval",
        "remediation_and_mission_109_110_reassessment_required": bool(escalation_reasons),
        "gareth_override_allowed": False,
        "delivery_eligible": False,
        "candidate_data_minimised": True,
        "confidential_source_material_duplicated_in_audit": False,
        "automatic_acceptance_enabled": False,
        "automatic_payment_enabled": False,
        "automatic_candidate_outreach_enabled": False,
        "automatic_search_activity_enabled": False,
        "automatic_delivery_enabled": False,
        "external_commitments_enabled": False,
    }
