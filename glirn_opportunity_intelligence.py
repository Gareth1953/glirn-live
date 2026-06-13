from datetime import datetime, timezone
from urllib.parse import urlparse
import re


OPPORTUNITY_CATEGORIES = {
    "law_firm_growth",
    "partner_movement",
    "practice_area_expansion",
    "recruitment_demand",
}

SOURCE_WEIGHTS = {
    "official_firm_announcement": {"confidence": "Very High", "weight": 95},
    "regulatory_filing": {"confidence": "Very High", "weight": 95},
    "professional_association": {"confidence": "High", "weight": 85},
    "major_legal_publication": {"confidence": "High", "weight": 85},
    "recruiter_report": {"confidence": "Medium", "weight": 65},
    "industry_discussion": {"confidence": "Low", "weight": 35},
}


def _safe_text(value, limit=1000):
    text = " ".join(str(value or "").split()).strip()
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[redacted email]", text)
    text = re.sub(r"(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)", "[redacted phone]", text)
    return text[:limit]


def _score(value, name):
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number from 0 to 100") from exc
    if not 0 <= result <= 100:
        raise ValueError(f"{name} must be from 0 to 100")
    return round(result, 2)


def _confidence_category(score):
    if score >= 90:
        return "Very High"
    if score >= 75:
        return "High"
    if score >= 60:
        return "Medium"
    return "Low"


def record_opportunity_signal(
    signal_id,
    category,
    source_type,
    title,
    publisher,
    source_url,
    publication_date,
    signal_summary,
    organisation,
    jurisdiction,
    practice_area=None,
    signal_strength=70,
    recorded_at=None,
):
    signal_id = _safe_text(signal_id, 120)
    category = str(category or "").strip().lower()
    source_type = str(source_type or "").strip().lower()
    if not signal_id:
        raise ValueError("signal_id is required")
    if category not in OPPORTUNITY_CATEGORIES:
        raise ValueError("unsupported opportunity category")
    if source_type not in SOURCE_WEIGHTS:
        raise ValueError("unsupported source_type")
    parsed = urlparse(str(source_url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("source_url must be a public HTTP or HTTPS URL")
    required = {
        "title": _safe_text(title, 250),
        "publisher": _safe_text(publisher, 200),
        "publication_date": _safe_text(publication_date, 40),
        "signal_summary": _safe_text(signal_summary),
        "organisation": _safe_text(organisation, 200),
        "jurisdiction": _safe_text(jurisdiction, 120),
    }
    if not all(required.values()):
        raise ValueError("title, publisher, publication_date, signal_summary, organisation, and jurisdiction are required")
    weighting = SOURCE_WEIGHTS[source_type]
    return {
        "signal_id": signal_id,
        "category": category,
        "source_type": source_type,
        "source_confidence": weighting["confidence"],
        "source_weight": weighting["weight"],
        "signal_strength": _score(signal_strength, "signal_strength"),
        "source_title": required["title"],
        "publisher": required["publisher"],
        "source_url": str(source_url).strip(),
        "publication_date": required["publication_date"],
        "signal_summary": required["signal_summary"],
        "organisation": required["organisation"],
        "jurisdiction": required["jurisdiction"],
        "practice_area": _safe_text(practice_area, 160),
        "recorded_at": recorded_at or datetime.now(timezone.utc).isoformat(),
        "public_source_declared": True,
        "candidate_data_minimised": True,
        **_safety_controls(),
    }


def generate_opportunity_recommendation(signals, generated_at=None):
    records = list(signals or [])
    if not records:
        raise ValueError("at least one opportunity signal is required")
    organisations = {item.get("organisation") for item in records}
    categories = sorted({item.get("category") for item in records})
    if len(organisations) != 1:
        raise ValueError("all signals must relate to the same organisation")
    average_source = sum(float(item.get("source_weight", 0)) for item in records) / len(records)
    average_strength = sum(float(item.get("signal_strength", 0)) for item in records) / len(records)
    corroboration = min(100, 40 + (len(records) - 1) * 20)
    completeness = round(
        100 * sum(
            1 for item in records
            if item.get("jurisdiction") and item.get("publication_date") and item.get("signal_summary")
        ) / len(records),
        2,
    )
    confidence = round(
        average_source * 0.45
        + average_strength * 0.30
        + corroboration * 0.15
        + completeness * 0.10,
        2,
    )
    if confidence >= 75:
        priority = "High"
        action = "Gareth should review whether this organisation merits manual opportunity qualification."
    elif confidence >= 60:
        priority = "Medium"
        action = "Gareth should monitor the signal and seek further public corroboration before qualification."
    else:
        priority = "Low"
        action = "Retain for monitoring only; evidence is insufficient for opportunity qualification."
    organisation = next(iter(organisations))
    return {
        "opportunity_intelligence_id": f"opportunity-intelligence-{records[0]['signal_id']}",
        "organisation": organisation,
        "categories": categories,
        "jurisdictions": sorted({item.get("jurisdiction") for item in records}),
        "practice_areas": sorted({item.get("practice_area") for item in records if item.get("practice_area")}),
        "signal_ids": [item.get("signal_id") for item in records],
        "source_count": len(records),
        "confidence_score": confidence,
        "confidence_category": _confidence_category(confidence),
        "priority": priority,
        "reasoning": {
            "average_source_weight": round(average_source, 2),
            "average_signal_strength": round(average_strength, 2),
            "corroboration_score": corroboration,
            "evidence_completeness": completeness,
        },
        "evidence_summary": [
            {
                "signal_id": item.get("signal_id"),
                "category": item.get("category"),
                "source_type": item.get("source_type"),
                "source_confidence": item.get("source_confidence"),
                "summary": _safe_text(item.get("signal_summary"), 300),
            }
            for item in records
        ],
        "advisory_recommendation": action,
        "recommendation_only": True,
        "approval_status": "awaiting_gareth_approval",
        "gareth_approval_required": True,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        **_safety_controls(),
    }


def apply_gareth_opportunity_decision(recommendation, decision, rationale, decided_at=None):
    if not recommendation or not recommendation.get("opportunity_intelligence_id"):
        raise ValueError("opportunity recommendation is required")
    decision = str(decision or "").strip().upper()
    if decision not in {"APPROVE_FOR_MANUAL_REVIEW", "MONITOR", "REJECT"}:
        raise ValueError("unsupported Gareth decision")
    rationale = _safe_text(rationale, 500)
    if not rationale:
        raise ValueError("decision rationale is required")
    return {
        "opportunity_decision_id": f"gareth-decision-{recommendation['opportunity_intelligence_id']}",
        "opportunity_intelligence_id": recommendation["opportunity_intelligence_id"],
        "organisation": recommendation["organisation"],
        "decision": decision,
        "decision_rationale": rationale,
        "decision_by": "Gareth",
        "decided_at": decided_at or datetime.now(timezone.utc).isoformat(),
        "manual_review_only": True,
        "automatic_action_executed": False,
        **_safety_controls(),
    }


def _safety_controls():
    return {
        "external_retrieval_enabled": False,
        "autonomous_outreach_enabled": False,
        "autonomous_prospecting_enabled": False,
        "automatic_referral_enabled": False,
        "automatic_marketing_enabled": False,
        "automatic_payment_enabled": False,
        "automatic_delivery_enabled": False,
        "external_commitments_enabled": False,
    }
