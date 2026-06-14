from collections import Counter
from datetime import datetime, timezone
import re


COMPLETED_REVIEW_OUTCOMES = {
    "approved_for_manual_delivery",
    "changes_required",
    "additional_review_required",
    "declined",
}


def _safe_text(value, limit=300):
    text = " ".join(str(value or "").split()).strip()
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[redacted email]", text)
    text = re.sub(r"(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)", "[redacted phone]", text)
    return text[:limit]


def _confidence_category(score):
    if score >= 90:
        return "Very High"
    if score >= 75:
        return "High"
    if score >= 60:
        return "Moderate"
    return "Low"


def _approved_external_intelligence(external_intelligence, knowledge_updates):
    approved_ids = {
        item.get("external_intelligence_id")
        for item in (knowledge_updates or [])
        if item.get("approved_by") == "Gareth"
        and item.get("knowledge_base_status") == "approved_for_manual_use"
    }
    return [
        item for item in (external_intelligence or [])
        if item.get("external_intelligence_id") in approved_ids
    ]


def _approved_opportunity_pairs(opportunity_intelligence, opportunity_decisions):
    recommendations = {
        item.get("opportunity_intelligence_id"): item
        for item in (opportunity_intelligence or [])
    }
    return [
        (recommendations.get(item.get("opportunity_intelligence_id")), item)
        for item in (opportunity_decisions or [])
        if item.get("decision_by") == "Gareth"
        and recommendations.get(item.get("opportunity_intelligence_id"))
    ]


def generate_governed_learning_snapshot(
    decline_decisions=None,
    human_reviews=None,
    learning_outcomes=None,
    external_intelligence=None,
    knowledge_updates=None,
    opportunity_intelligence=None,
    opportunity_decisions=None,
    generated_at=None,
):
    decisions = [
        item for item in (decline_decisions or [])
        if item.get("decision_by") == "Gareth" and item.get("gareth_approved") is True
    ]
    reviews = [
        item for item in (human_reviews or [])
        if item.get("reviewer") == "Gareth"
        and item.get("outcome") in COMPLETED_REVIEW_OUTCOMES
    ]
    outcomes = [
        item for item in (learning_outcomes or [])
        if item.get("decision_by") == "Gareth"
    ]
    approved_external = _approved_external_intelligence(external_intelligence, knowledge_updates)
    opportunity_pairs = _approved_opportunity_pairs(opportunity_intelligence, opportunity_decisions)

    decision_counts = Counter(item.get("final_decision") for item in decisions)
    correction_counts = Counter(
        f"{item.get('system_recommendation')}->{item.get('final_decision')}"
        for item in decisions
        if item.get("system_recommendation") != item.get("final_decision")
    )
    review_counts = Counter(item.get("outcome") for item in reviews)
    decline_reasons = Counter(
        reason
        for item in outcomes
        for reason in item.get("decline_reason_codes", [])
    )
    remediation_counts = Counter(item.get("remediation_outcome") for item in outcomes)
    external_topics = Counter(item.get("topic") for item in approved_external if item.get("topic"))
    opportunity_categories = Counter(
        category
        for recommendation, _decision in opportunity_pairs
        for category in recommendation.get("categories", [])
    )
    opportunity_decision_counts = Counter(
        decision.get("decision") for _recommendation, decision in opportunity_pairs
    )

    patterns = []
    if correction_counts:
        correction, count = correction_counts.most_common(1)[0]
        patterns.append({
            "pattern_type": "gareth_correction",
            "finding": f"The most frequent recommendation correction was {correction}.",
            "evidence_count": count,
            "advisory_insight": "Review the evidence assumptions associated with this correction pattern.",
        })
    if decline_reasons:
        reason, count = decline_reasons.most_common(1)[0]
        patterns.append({
            "pattern_type": "decline_reason",
            "finding": f"The most frequent coded decline reason was {reason}.",
            "evidence_count": count,
            "advisory_insight": "Surface this factor earlier in future manual review bundles.",
        })
    if remediation_counts:
        outcome, count = remediation_counts.most_common(1)[0]
        patterns.append({
            "pattern_type": "remediation_outcome",
            "finding": f"The most frequent remediation outcome was {outcome}.",
            "evidence_count": count,
            "advisory_insight": "Use this outcome as context when explaining remediation confidence.",
        })
    if review_counts:
        outcome, count = review_counts.most_common(1)[0]
        patterns.append({
            "pattern_type": "completed_review",
            "finding": f"The most frequent completed review outcome was {outcome}.",
            "evidence_count": count,
            "advisory_insight": "Compare future review recommendations against this approved outcome distribution.",
        })
    if external_topics:
        topic, count = external_topics.most_common(1)[0]
        patterns.append({
            "pattern_type": "approved_external_intelligence",
            "finding": f"Approved external intelligence most frequently covered {_safe_text(topic)}.",
            "evidence_count": count,
            "advisory_insight": "Cite approved external intelligence as context, not as legal advice or an automatic rule change.",
        })
    if opportunity_categories:
        category, count = opportunity_categories.most_common(1)[0]
        patterns.append({
            "pattern_type": "opportunity_outcome",
            "finding": f"The most frequent Gareth-reviewed opportunity category was {category}.",
            "evidence_count": count,
            "advisory_insight": "Use the recorded Gareth outcome to calibrate explanations for similar future signals.",
        })
    if not patterns:
        patterns.append({
            "pattern_type": "insufficient_history",
            "finding": "No approved learning pattern has sufficient governed history yet.",
            "evidence_count": 0,
            "advisory_insight": "Continue collecting Gareth-approved outcomes before proposing recommendation changes.",
        })

    source_counts = {
        "gareth_decisions": len(decisions),
        "completed_reviews": len(reviews),
        "learning_outcomes": len(outcomes),
        "approved_external_intelligence": len(approved_external),
        "gareth_opportunity_outcomes": len(opportunity_pairs),
    }
    populated_sources = sum(1 for count in source_counts.values() if count > 0)
    total_records = sum(source_counts.values())
    coverage_score = populated_sources / len(source_counts) * 100
    volume_score = min(100, total_records * 10)
    corroboration_score = min(100, sum(1 for item in patterns if item["evidence_count"] >= 2) * 25)
    confidence_score = round(coverage_score * 0.45 + volume_score * 0.35 + corroboration_score * 0.20, 2)
    confidence_explanation = (
        f"Confidence {confidence_score}/100 reflects {populated_sources} of {len(source_counts)} governed source groups, "
        f"{total_records} approved records, and {corroboration_score}/100 pattern corroboration."
    )
    return {
        "learning_snapshot_id": f"mission-115-snapshot-{total_records}",
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "source_counts": source_counts,
        "decision_counts": dict(decision_counts),
        "gareth_correction_patterns": dict(correction_counts),
        "review_outcome_counts": dict(review_counts),
        "decline_reason_counts": dict(decline_reasons),
        "remediation_outcome_counts": dict(remediation_counts),
        "approved_external_topics": dict(external_topics),
        "opportunity_category_counts": dict(opportunity_categories),
        "opportunity_decision_counts": dict(opportunity_decision_counts),
        "recommendation_patterns": patterns,
        "confidence_score": confidence_score,
        "confidence_category": _confidence_category(confidence_score),
        "confidence_explanation": confidence_explanation,
        "advisory_only": True,
        "approval_status": "awaiting_gareth_approval",
        "gareth_approval_required": True,
        "legal_advice_provided": False,
        "compliance_rules_updated": False,
        "decision_thresholds_changed": False,
        "sensitive_source_content_copied_to_audit": False,
        **_safety_controls(),
    }


def apply_gareth_learning_decision(snapshot, decision, rationale, decided_at=None):
    if not snapshot or not snapshot.get("learning_snapshot_id"):
        raise ValueError("learning snapshot is required")
    decision = str(decision or "").strip().upper()
    if decision not in {"APPROVE_FOR_MANUAL_CONSIDERATION", "REJECT", "MORE_INFORMATION_REQUIRED"}:
        raise ValueError("unsupported Gareth learning decision")
    rationale = _safe_text(rationale, 500)
    if not rationale:
        raise ValueError("decision rationale is required")
    return {
        "learning_decision_id": f"gareth-decision-{snapshot['learning_snapshot_id']}",
        "learning_snapshot_id": snapshot["learning_snapshot_id"],
        "decision": decision,
        "decision_rationale": rationale,
        "decision_by": "Gareth",
        "decided_at": decided_at or datetime.now(timezone.utc).isoformat(),
        "manual_consideration_only": True,
        "compliance_rules_updated": False,
        "decision_thresholds_changed": False,
        "automatic_action_executed": False,
        **_safety_controls(),
    }


def _safety_controls():
    return {
        "network_client_enabled": False,
        "autonomous_decision_making_enabled": False,
        "automatic_client_contact_enabled": False,
        "automatic_candidate_contact_enabled": False,
        "automatic_firm_contact_enabled": False,
        "automatic_recruiter_contact_enabled": False,
        "automatic_association_contact_enabled": False,
        "automatic_outreach_enabled": False,
        "automatic_referral_enabled": False,
        "automatic_marketing_enabled": False,
        "automatic_payment_enabled": False,
        "automatic_delivery_enabled": False,
        "external_commitments_enabled": False,
    }
