from datetime import datetime, timezone
import re


RECOMMENDATIONS = {
    "ACCEPT",
    "DECLINE",
    "MORE_INFORMATION_REQUIRED",
}

DECISION_FACTORS = (
    "client_fit",
    "ethical_risk",
    "commercial_viability",
    "reputation_risk",
    "delivery_confidence",
)

FACTOR_LABELS = {
    "client_fit": "Client Fit",
    "ethical_risk": "Ethical Risk",
    "commercial_viability": "Commercial Viability",
    "reputation_risk": "Reputation Risk",
    "delivery_confidence": "Delivery Confidence",
}


def _score(value, field_name):
    try:
        score = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a number from 0 to 100") from exc
    if not 0 <= score <= 100:
        raise ValueError(f"{field_name} must be from 0 to 100")
    return round(score, 2)


def _safe_text(value):
    text = " ".join(str(value or "").split()).strip()
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[redacted email]", text)
    text = re.sub(r"(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)", "[redacted phone]", text)
    return text[:500]


def _evidence_map(evidence):
    supplied = evidence or {}
    return {
        factor: _safe_text(supplied.get(factor))
        for factor in DECISION_FACTORS
    }


def _factor_reasoning(factor, score, evidence_text):
    if factor in {"ethical_risk", "reputation_risk"}:
        assessment = "high risk" if score >= 70 else "moderate risk" if score >= 40 else "controlled risk"
    else:
        assessment = "strong" if score >= 70 else "borderline" if score >= 50 else "weak"
    evidence_status = "evidence supplied" if evidence_text else "evidence missing"
    return f"{FACTOR_LABELS[factor]} is assessed as {assessment} at {score}/100; {evidence_status}."


def evaluate_decline_decision(
    enquiry_id,
    factor_scores,
    evidence,
    referral_suitable=False,
    referral_type=None,
    referral_reason=None,
    evaluated_at=None,
):
    enquiry_id = str(enquiry_id or "").strip()
    if not enquiry_id:
        raise ValueError("enquiry_id is required")
    scores = {
        factor: _score((factor_scores or {}).get(factor), factor)
        for factor in DECISION_FACTORS
    }
    evidence_summary = _evidence_map(evidence)
    missing_evidence = [factor for factor, value in evidence_summary.items() if not value]

    decline_reasons = []
    if scores["ethical_risk"] >= 70:
        decline_reasons.append("ethical_risk_unacceptably_high")
    if scores["reputation_risk"] >= 75:
        decline_reasons.append("reputation_risk_unacceptably_high")
    if scores["client_fit"] < 35:
        decline_reasons.append("client_fit_materially_insufficient")
    if scores["commercial_viability"] < 30:
        decline_reasons.append("commercial_viability_materially_insufficient")
    if scores["delivery_confidence"] < 40:
        decline_reasons.append("delivery_confidence_materially_insufficient")

    information_reasons = []
    if missing_evidence:
        information_reasons.append("material_evidence_incomplete")
    if 40 <= scores["ethical_risk"] < 70:
        information_reasons.append("ethical_risk_requires_clarification")
    if 40 <= scores["reputation_risk"] < 75:
        information_reasons.append("reputation_risk_requires_clarification")
    if 35 <= scores["client_fit"] < 70:
        information_reasons.append("client_fit_requires_clarification")
    if 30 <= scores["commercial_viability"] < 60:
        information_reasons.append("commercial_viability_requires_clarification")
    if 40 <= scores["delivery_confidence"] < 70:
        information_reasons.append("delivery_confidence_requires_clarification")

    if decline_reasons:
        recommendation = "DECLINE"
        recommendation_reasons = decline_reasons
    elif information_reasons:
        recommendation = "MORE_INFORMATION_REQUIRED"
        recommendation_reasons = information_reasons
    else:
        recommendation = "ACCEPT"
        recommendation_reasons = ["all_decision_thresholds_satisfied"]

    referral_type = _safe_text(referral_type)
    referral_reason = _safe_text(referral_reason)
    referral = {
        "recommended": bool(referral_suitable and recommendation == "DECLINE"),
        "referral_type": referral_type if referral_suitable else "",
        "reason": referral_reason if referral_suitable else "",
        "external_contact_executed": False,
        "gareth_approval_required": True,
    }
    reasoning = [
        _factor_reasoning(factor, scores[factor], evidence_summary[factor])
        for factor in DECISION_FACTORS
    ]
    reasoning.append(
        f"Recommendation: {recommendation}. Trigger(s): {', '.join(recommendation_reasons)}."
    )
    evaluated_at = evaluated_at or datetime.now(timezone.utc).isoformat()
    return {
        "recommendation_id": f"decline-recommendation-{enquiry_id}",
        "enquiry_id": enquiry_id,
        "evaluated_at": evaluated_at,
        "factor_scores": scores,
        "evidence_summary": evidence_summary,
        "missing_evidence": missing_evidence,
        "transparent_reasoning": reasoning,
        "recommendation": recommendation,
        "recommendation_reasons": sorted(set(recommendation_reasons)),
        "referral_recommendation": referral,
        "recommendation_only": True,
        "final_decision_status": "awaiting_gareth_approval",
        "gareth_final_approval_required": True,
        "automatic_acceptance_enabled": False,
        "automatic_decline_enabled": False,
        "automatic_referral_enabled": False,
        "automatic_payment_enabled": False,
        "automatic_candidate_outreach_enabled": False,
        "automatic_search_commitments_enabled": False,
        "automatic_delivery_enabled": False,
        "external_commitments_enabled": False,
        "candidate_data_minimised": True,
        "confidential_source_material_duplicated_in_audit": False,
    }


def apply_gareth_decision(recommendation, final_decision, rationale, decided_at=None):
    if not recommendation or not recommendation.get("recommendation_id"):
        raise ValueError("recommendation record is required")
    final_decision = str(final_decision or "").strip().upper()
    if final_decision not in RECOMMENDATIONS:
        raise ValueError("final_decision must be ACCEPT, DECLINE, or MORE_INFORMATION_REQUIRED")
    rationale = _safe_text(rationale)
    if not rationale:
        raise ValueError("decision rationale is required")
    decided_at = decided_at or datetime.now(timezone.utc).isoformat()
    return {
        "decision_id": f"gareth-decision-{recommendation['enquiry_id']}",
        "recommendation_id": recommendation["recommendation_id"],
        "enquiry_id": recommendation["enquiry_id"],
        "system_recommendation": recommendation["recommendation"],
        "final_decision": final_decision,
        "decision_rationale": rationale,
        "decision_by": "Gareth",
        "decided_at": decided_at,
        "gareth_approved": True,
        "automatic_action_executed": False,
        "automatic_acceptance_enabled": False,
        "automatic_decline_enabled": False,
        "automatic_referral_enabled": False,
        "automatic_payment_enabled": False,
        "automatic_candidate_outreach_enabled": False,
        "automatic_search_commitments_enabled": False,
        "automatic_delivery_enabled": False,
        "external_commitments_enabled": False,
    }
