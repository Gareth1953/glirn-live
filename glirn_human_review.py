from datetime import datetime, timezone


HUMAN_REVIEW_CHECKLIST = {
    "scope_within_glirn_boundaries": "Scope is within GLIRN's stated service boundaries.",
    "evidence_identified_and_sufficient": "Sources and evidence are identified and sufficient.",
    "facts_separated_from_speculation": "Facts are separated from assumptions or speculation.",
    "ai_content_human_reviewed": "AI-assisted content has been reviewed by a named person.",
    "confidence_limitations_stated": "Confidence limitations are clearly stated.",
    "no_advice_inference": "No legal or regulated recruitment advice is implied.",
    "candidate_consent_verified": "Candidate-specific information has valid consent or is not included.",
    "confidentiality_and_minimisation_checked": "Confidentiality and data-minimisation requirements are met.",
    "no_guarantee_or_commitment": "Commercial wording creates no guarantee or commitment.",
    "final_wording_quality_checked": "Final wording is accurate, balanced, and suitable for delivery.",
}

RED_FLAG_RULES = {
    "low_ai_confidence": "AI confidence is below the acceptable review threshold.",
    "speculative_content": "The brief contains assumptions, predictions, or speculative content.",
    "candidate_specific_intelligence": "Candidate-specific intelligence requires enhanced review and active consent.",
    "legal_advice_inference_risk": "Wording could be interpreted as legal or regulated recruitment advice.",
    "insufficient_evidence": "Available evidence is insufficient to support responsible delivery.",
}

DECLINE_CRITERIA = {
    "legal_advice_requested": "The request requires legal advice or legal interpretation.",
    "regulated_recruitment_advice_requested": "The request requires regulated recruitment advice.",
    "insufficient_evidence": "Evidence cannot support a responsible intelligence brief.",
    "candidate_consent_unavailable": "Candidate-specific information lacks valid consent.",
    "outside_glirn_expertise": "The request requires expertise GLIRN does not hold.",
    "guarantee_or_improper_influence_requested": "The request seeks guarantees, improper influence, or misleading claims.",
    "confidentiality_or_ethics_cannot_be_maintained": "Confidentiality, lawful handling, or ethical handling cannot be maintained.",
    "specialist_adviser_better_placed": "Another specialist adviser would better serve the client's needs.",
}

ALLOWED_OUTCOMES = {
    "approved_for_manual_delivery",
    "changes_required",
    "additional_review_required",
    "declined",
    "awaiting_human_review",
}

ALLOWED_DELIVERY_STATUSES = {
    "not_ready",
    "blocked",
    "ready_for_manual_delivery",
    "manually_delivered",
}


def build_initial_human_review_framework(brief, ai_confidence=100, speculative_content=False, evidence_sufficient=True):
    candidate_specific = bool(brief.get("candidate_personal_data_included", False))
    red_flags = {
        "low_ai_confidence": float(ai_confidence or 0) < 60,
        "speculative_content": bool(speculative_content),
        "candidate_specific_intelligence": candidate_specific,
        "legal_advice_inference_risk": False,
        "insufficient_evidence": not bool(evidence_sufficient),
    }
    active_flags = [name for name, active in red_flags.items() if active]
    return {
        "framework_version": "mission-106-v1",
        "checklist": [
            {"check_id": check_id, "label": label, "required": True}
            for check_id, label in HUMAN_REVIEW_CHECKLIST.items()
        ],
        "red_flag_rules": RED_FLAG_RULES,
        "red_flags": red_flags,
        "active_red_flags": active_flags,
        "decline_criteria": DECLINE_CRITERIA,
        "qa_status": "additional_review_required" if active_flags else "awaiting_human_review",
        "human_review_required": True,
        "quality_assurance_required": True,
        "client_delivery_allowed": False,
        "external_delivery_enabled": False,
    }


def evaluate_human_review(brief, submission):
    reviewer = str(submission.get("reviewer", "")).strip()
    rationale = str(submission.get("approval_rationale", "")).strip()
    outcome = str(submission.get("outcome", "")).strip()
    requested_delivery_status = str(submission.get("delivery_status", "not_ready")).strip()
    checklist_results = submission.get("checklist_results") or {}
    submitted_red_flags = submission.get("red_flags") or {}
    red_flag_resolutions = submission.get("red_flag_resolutions") or {}
    decline_reason = str(submission.get("decline_reason") or "").strip()
    decline_criterion = str(submission.get("decline_criterion") or "").strip()

    errors = []
    if not reviewer:
        errors.append("reviewer is required")
    if not rationale:
        errors.append("approval_rationale is required")
    if outcome not in ALLOWED_OUTCOMES:
        errors.append("unsupported outcome")
    if requested_delivery_status not in ALLOWED_DELIVERY_STATUSES:
        errors.append("unsupported delivery_status")
    if decline_criterion and decline_criterion not in DECLINE_CRITERIA:
        errors.append("unsupported decline_criterion")

    incomplete_checks = [
        check_id for check_id in HUMAN_REVIEW_CHECKLIST
        if checklist_results.get(check_id) is not True
    ]
    initial_framework = brief.get("human_review_framework") or build_initial_human_review_framework(brief)
    effective_red_flags = {
        name: bool((initial_framework.get("red_flags") or {}).get(name, False) or submitted_red_flags.get(name, False))
        for name in RED_FLAG_RULES
    }
    unresolved_red_flags = [
        name for name, active in effective_red_flags.items()
        if active and red_flag_resolutions.get(name) is not True
    ]

    candidate_consent_valid = not effective_red_flags["candidate_specific_intelligence"] or (
        brief.get("candidate_personal_data_included", False)
        and not brief.get("candidate_personal_data_blocked", True)
        and checklist_results.get("candidate_consent_verified") is True
    )
    if effective_red_flags["candidate_specific_intelligence"] and not candidate_consent_valid:
        if "candidate_specific_intelligence" not in unresolved_red_flags:
            unresolved_red_flags.append("candidate_specific_intelligence")

    approval_requested = outcome == "approved_for_manual_delivery"
    if approval_requested and incomplete_checks:
        errors.append("all mandatory checklist items must pass before approval")
    if approval_requested and unresolved_red_flags:
        errors.append("all red flags must be resolved before approval")
    if approval_requested and not candidate_consent_valid:
        errors.append("active candidate consent is required before approval")

    if outcome == "declined" and not (decline_reason or decline_criterion):
        errors.append("decline_reason or decline_criterion is required when declining")

    approved = approval_requested and not errors
    if outcome == "declined":
        delivery_status = "blocked"
    elif approved:
        delivery_status = "ready_for_manual_delivery"
    else:
        delivery_status = "blocked" if incomplete_checks or unresolved_red_flags else "not_ready"

    now = datetime.now(timezone.utc).isoformat()
    record = {
        "human_review_id": f"human-review-{brief.get('review_id', 'unknown')}",
        "brief_id": brief.get("review_id"),
        "enquiry_date": submission.get("enquiry_date") or now,
        "reviewed_at": now,
        "reviewer": reviewer,
        "outcome": outcome,
        "approval_rationale": rationale,
        "checklist_results": {key: checklist_results.get(key) is True for key in HUMAN_REVIEW_CHECKLIST},
        "incomplete_checks": incomplete_checks,
        "red_flags": effective_red_flags,
        "unresolved_red_flags": unresolved_red_flags,
        "red_flags_resolved": not unresolved_red_flags,
        "decline_criterion": decline_criterion or None,
        "decline_reason": decline_reason or DECLINE_CRITERIA.get(decline_criterion),
        "delivery_status": delivery_status,
        "requested_delivery_status": requested_delivery_status,
        "approved_for_manual_delivery": approved,
        "client_delivery_allowed": approved,
        "manual_delivery_only": True,
        "external_delivery_enabled": False,
        "automatic_delivery_enabled": False,
        "candidate_consent_valid": candidate_consent_valid,
        "validation_errors": errors,
    }
    return record
