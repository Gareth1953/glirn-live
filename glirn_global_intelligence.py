from datetime import datetime, timezone
import re

from glirn_confidence_engine import confidence_context_for_global_intelligence


SUPPORTED_JURISDICTIONS = (
    "United Kingdom",
    "United Arab Emirates",
    "Singapore",
    "European Union",
    "United States",
)

INTELLIGENCE_CATEGORIES = (
    "hiring_difficulty_indicators",
    "practice_area_demand_indicators",
    "market_competitiveness_observations",
    "jurisdiction_specific_considerations",
    "candidate_scarcity_indicators",
    "talent_mobility_observations",
)


def _rating(value, field_name):
    try:
        rating = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a number from 0 to 100") from exc
    if not 0 <= rating <= 100:
        raise ValueError(f"{field_name} must be from 0 to 100")
    return round(rating, 2)


def _clean_items(values, fallback=None):
    items = []
    for value in values or []:
        item = " ".join(str(value or "").split()).strip()[:500]
        item = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[redacted email]", item)
        item = re.sub(r"(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)", "[redacted phone]", item)
        if item and item not in items:
            items.append(item)
    return items[:12] or list(fallback or [])


def _indicator_level(rating):
    if rating >= 75:
        return "elevated"
    if rating >= 50:
        return "mixed"
    return "limited"


def _observation(category, rating, jurisdiction, practice_area):
    level = _indicator_level(rating)
    labels = {
        "hiring_difficulty_indicators": "hiring difficulty",
        "practice_area_demand_indicators": "practice-area demand",
        "market_competitiveness_observations": "market competitiveness",
        "jurisdiction_specific_considerations": "jurisdiction-specific complexity",
        "candidate_scarcity_indicators": "candidate scarcity",
        "talent_mobility_observations": "talent mobility constraints",
    }
    return {
        "category": category,
        "indicator_rating": rating,
        "indicator_level": level,
        "observation": (
            f"Reviewed inputs indicate {level} {labels[category]} for {practice_area} in {jurisdiction}. "
            "This is a high-level hiring-intelligence observation, not a verified market fact or legal advice."
        ),
        "evidence_based": True,
        "candidate_specific": False,
        "legal_advice": False,
    }


def render_global_intelligence_markdown(validation):
    lines = [
        "## Global Legal Intelligence",
        "",
        f"Jurisdiction: {validation['jurisdiction']}",
        f"Practice area: {validation['practice_area']}",
        f"Confidence score: {validation['confidence_score']}",
        f"Confidence category: {validation['confidence_category']}",
        f"Review timestamp: {validation['review_timestamp']}",
        "",
        f"Intelligence summary: {validation['intelligence_summary']}",
        "",
        "### Structured observations",
        "",
    ]
    for category in INTELLIGENCE_CATEGORIES:
        item = validation["structured_observations"][category]
        lines.append(f"- {item['observation']}")
    sections = (
        ("Evidence transparency summary", validation["evidence_transparency_summary"]),
        ("Known limitations", validation["known_limitations"]),
        ("Information gaps", validation["information_gaps"]),
        ("Alternative interpretations", validation["alternative_interpretations"]),
    )
    for title, values in sections:
        lines.extend(["", f"### {title}", ""])
        lines.extend(f"- {item}" for item in values)
    return "\n".join(lines).strip()


def generate_global_legal_intelligence(
    brief,
    confidence_assessment,
    jurisdiction,
    practice_area,
    indicator_ratings,
    evidence_basis,
    known_limitations=None,
    information_gaps=None,
    alternative_interpretations=None,
    unsupported_claims_identified=False,
    jurisdiction_expertise_limitations=False,
    evidence_insufficiency_identified=False,
    exceeds_glirn_expertise_boundaries=False,
    reviewed_at=None,
):
    brief_id = str(brief.get("review_id") or "").strip()
    if not brief_id:
        raise ValueError("brief review_id is required")
    jurisdiction = " ".join(str(jurisdiction or "").split()).strip()
    if jurisdiction not in SUPPORTED_JURISDICTIONS:
        raise ValueError("jurisdiction is not supported in Phase 1")
    practice_area = " ".join(str(practice_area or "").split()).strip()
    if not practice_area:
        raise ValueError("practice_area is required")
    confidence = confidence_context_for_global_intelligence(confidence_assessment, brief_id)
    evidence = _clean_items(evidence_basis)
    if not evidence:
        evidence_insufficiency_identified = True

    ratings = {
        category: _rating((indicator_ratings or {}).get(category), category)
        for category in INTELLIGENCE_CATEGORIES
    }
    observations = {
        category: _observation(category, rating, jurisdiction, practice_area)
        for category, rating in ratings.items()
    }
    limitations = _clean_items(
        known_limitations,
        ["Market conditions can change and jurisdiction-specific expertise may require specialist validation."],
    )
    gaps = _clean_items(
        information_gaps,
        ["No material information gap was identified within the supplied evidence scope."],
    )
    alternatives = _clean_items(
        alternative_interpretations,
        confidence["alternative_interpretations"],
    )
    significant_disagreement = confidence["reviewer_disagreement_unresolved"]
    escalation_reasons = []
    if confidence["confidence_score"] < 70:
        escalation_reasons.append("confidence_below_70")
    if jurisdiction_expertise_limitations:
        escalation_reasons.append("jurisdiction_expertise_limitations")
    if evidence_insufficiency_identified or confidence["evidence_sufficiency_rating"] < 70 or not evidence:
        escalation_reasons.append("evidence_insufficiency")
    if significant_disagreement:
        escalation_reasons.append("reviewer_disagreement_unresolved")
    if exceeds_glirn_expertise_boundaries:
        escalation_reasons.append("glirn_expertise_boundary_exceeded")
    if unsupported_claims_identified:
        escalation_reasons.append("unsupported_intelligence_claims")
    if confidence["mission_110_escalation_unresolved"]:
        escalation_reasons.append("mission_110_escalation_unresolved")
    candidate_specific = bool(brief.get("candidate_personal_data_included"))
    candidate_consent_valid = not candidate_specific or not bool(brief.get("candidate_personal_data_blocked", True))
    if not candidate_consent_valid:
        escalation_reasons.append("candidate_consent_incomplete")
    escalation_reasons = sorted(set(escalation_reasons))
    reviewed_at = reviewed_at or datetime.now(timezone.utc).isoformat()
    intelligence_summary = (
        f"High-level jurisdiction-aware hiring intelligence for {practice_area} in {jurisdiction}, "
        "derived from supplied evidence indicators and subject to the stated limitations, gaps, and alternative interpretations."
    )
    return {
        "global_intelligence_id": f"global-intelligence-{brief_id}",
        "brief_id": brief_id,
        "mission_110_confidence_assessment_id": confidence["confidence_assessment_id"],
        "content_fingerprint": confidence["content_fingerprint"],
        "jurisdiction": jurisdiction,
        "practice_area": practice_area,
        "intelligence_summary": intelligence_summary,
        "structured_observations": observations,
        "evidence_transparency_summary": evidence or ["No adequate evidence basis was supplied."],
        "confidence_score": confidence["confidence_score"],
        "confidence_category": confidence["confidence_category"],
        "evidence_sufficiency_rating": confidence["evidence_sufficiency_rating"],
        "known_limitations": limitations,
        "information_gaps": gaps,
        "alternative_interpretations": alternatives,
        "review_timestamp": reviewed_at,
        "validation_complete": True,
        "unsupported_claims_identified": bool(unsupported_claims_identified),
        "jurisdiction_expertise_limitations": bool(jurisdiction_expertise_limitations),
        "evidence_insufficiency_identified": bool(evidence_insufficiency_identified or not evidence),
        "reviewer_disagreement_unresolved": significant_disagreement,
        "exceeds_glirn_expertise_boundaries": bool(exceeds_glirn_expertise_boundaries),
        "candidate_consent_valid": candidate_consent_valid,
        "escalation_required": bool(escalation_reasons),
        "unresolved_escalations": escalation_reasons,
        "validation_status": "escalated_delivery_blocked" if escalation_reasons else "cleared_for_gareth_approval",
        "delivery_eligible": False,
        "gareth_override_allowed": False,
        "high_level_observations_only": True,
        "legal_advice_provided": False,
        "candidate_specific_intelligence_included": False,
        "candidate_data_minimised": True,
        "confidential_source_material_duplicated_in_audit": False,
        "automatic_acceptance_enabled": False,
        "automatic_payment_enabled": False,
        "automatic_candidate_outreach_enabled": False,
        "automatic_search_commitments_enabled": False,
        "automatic_delivery_enabled": False,
        "external_commitments_enabled": False,
    }
