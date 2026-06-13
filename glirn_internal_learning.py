from collections import Counter
from datetime import datetime, timezone
import re


DECISIONS = {"ACCEPT", "DECLINE", "MORE_INFORMATION_REQUIRED"}
BRIEF_OUTCOMES = {"successful", "partially_successful", "unsuccessful", "not_completed"}
REMEDIATION_OUTCOMES = {"not_required", "resolved", "unresolved", "declined_after_remediation"}


def _safe_text(value, limit=500):
    text = " ".join(str(value or "").split()).strip()
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[redacted email]", text)
    text = re.sub(r"(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)", "[redacted phone]", text)
    return text[:limit]


def capture_learning_outcome(
    record_id,
    brief_id,
    gareth_decision,
    brief_outcome,
    remediation_outcome,
    outcome_summary,
    decline_reason_codes=None,
    captured_at=None,
):
    record_id = _safe_text(record_id, 120)
    brief_id = _safe_text(brief_id, 120)
    if not record_id or not brief_id:
        raise ValueError("record_id and brief_id are required")
    gareth_decision = str(gareth_decision or "").strip().upper()
    if gareth_decision not in DECISIONS:
        raise ValueError("gareth_decision must be ACCEPT, DECLINE, or MORE_INFORMATION_REQUIRED")
    brief_outcome = str(brief_outcome or "").strip().lower()
    if brief_outcome not in BRIEF_OUTCOMES:
        raise ValueError("unsupported brief_outcome")
    remediation_outcome = str(remediation_outcome or "").strip().lower()
    if remediation_outcome not in REMEDIATION_OUTCOMES:
        raise ValueError("unsupported remediation_outcome")
    outcome_summary = _safe_text(outcome_summary)
    if not outcome_summary:
        raise ValueError("outcome_summary is required")
    reason_codes = sorted({
        _safe_text(item, 80).lower().replace(" ", "_")
        for item in (decline_reason_codes or [])
        if _safe_text(item, 80)
    })
    return {
        "learning_outcome_id": f"learning-outcome-{record_id}",
        "source_record_id": record_id,
        "brief_id": brief_id,
        "gareth_decision": gareth_decision,
        "decision_by": "Gareth",
        "brief_outcome": brief_outcome,
        "remediation_outcome": remediation_outcome,
        "outcome_summary": outcome_summary,
        "decline_reason_codes": reason_codes,
        "captured_at": captured_at or datetime.now(timezone.utc).isoformat(),
        "candidate_data_minimised": True,
        "gareth_approval_mandatory": True,
        "automatic_action_executed": False,
        **_safety_controls(),
    }


def generate_improvement_insights(outcomes, generated_at=None):
    records = list(outcomes or [])
    decisions = Counter(item.get("gareth_decision") for item in records)
    brief_outcomes = Counter(item.get("brief_outcome") for item in records)
    remediation = Counter(item.get("remediation_outcome") for item in records)
    decline_reasons = Counter(
        reason
        for item in records
        for reason in item.get("decline_reason_codes", [])
    )
    recommendations = []
    evidence = []
    if decline_reasons:
        reason, count = decline_reasons.most_common(1)[0]
        recommendations.append(f"Review intake guidance for recurring decline factor: {reason}.")
        evidence.append(f"{count} recorded outcome(s) referenced {reason}.")
    if remediation.get("resolved", 0):
        recommendations.append("Retain effective remediation checks and require the same human review sequence.")
        evidence.append(f"{remediation['resolved']} remediation outcome(s) were resolved.")
    if brief_outcomes.get("unsuccessful", 0) or brief_outcomes.get("partially_successful", 0):
        recommendations.append("Review evidence sufficiency and delivery-confidence assumptions for future briefs.")
        evidence.append(
            f"{brief_outcomes.get('unsuccessful', 0)} unsuccessful and "
            f"{brief_outcomes.get('partially_successful', 0)} partially successful brief outcome(s) were recorded."
        )
    if not recommendations:
        recommendations.append("Continue collecting outcomes before changing recommendation guidance.")
        evidence.append(f"{len(records)} completed learning outcome(s) are currently available.")
    return {
        "insight_id": f"learning-insight-{len(records)}",
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "outcome_count": len(records),
        "decision_counts": dict(decisions),
        "brief_outcome_counts": dict(brief_outcomes),
        "remediation_counts": dict(remediation),
        "recommendation_improvement_insights": recommendations,
        "evidence_summary": evidence,
        "recommendation_only": True,
        "status": "awaiting_gareth_approval",
        "gareth_approval_mandatory": True,
        "knowledge_or_policy_updated": False,
        "automatic_action_executed": False,
        **_safety_controls(),
    }


def approve_learning_insight(insight, rationale, approved_at=None):
    if not insight or not insight.get("insight_id"):
        raise ValueError("learning insight is required")
    rationale = _safe_text(rationale)
    if not rationale:
        raise ValueError("approval rationale is required")
    return {
        "learning_approval_id": f"gareth-approval-{insight['insight_id']}",
        "insight_id": insight["insight_id"],
        "approved_by": "Gareth",
        "approval_rationale": rationale,
        "approved_at": approved_at or datetime.now(timezone.utc).isoformat(),
        "approved_for_manual_consideration": True,
        "knowledge_or_policy_updated": False,
        "automatic_action_executed": False,
        **_safety_controls(),
    }


def _safety_controls():
    return {
        "autonomous_decision_making_enabled": False,
        "automatic_outreach_enabled": False,
        "automatic_referral_enabled": False,
        "automatic_payment_enabled": False,
        "automatic_delivery_enabled": False,
        "external_commitments_enabled": False,
    }
