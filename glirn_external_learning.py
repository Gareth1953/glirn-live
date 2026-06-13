from datetime import datetime, timezone
from urllib.parse import urlparse
import re


SOURCE_WEIGHTS = {
    "government_regulatory": {"confidence": "Very High", "weight": 95},
    "professional_body": {"confidence": "High", "weight": 85},
    "major_recruitment_report": {"confidence": "Medium", "weight": 65},
    "industry_forum_discussion": {"confidence": "Low", "weight": 35},
}


def _safe_text(value, limit=1000):
    text = " ".join(str(value or "").split()).strip()
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[redacted email]", text)
    text = re.sub(r"(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)", "[redacted phone]", text)
    return text[:limit]


def ingest_public_evidence(
    evidence_id,
    source_type,
    title,
    publisher,
    source_url,
    publication_date,
    evidence_summary,
    jurisdiction=None,
    ingested_at=None,
):
    evidence_id = _safe_text(evidence_id, 120)
    source_type = str(source_type or "").strip().lower()
    if not evidence_id:
        raise ValueError("evidence_id is required")
    if source_type not in SOURCE_WEIGHTS:
        raise ValueError("unsupported source_type")
    parsed = urlparse(str(source_url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("source_url must be a public HTTP or HTTPS URL")
    title = _safe_text(title, 250)
    publisher = _safe_text(publisher, 200)
    publication_date = _safe_text(publication_date, 40)
    evidence_summary = _safe_text(evidence_summary)
    if not all((title, publisher, publication_date, evidence_summary)):
        raise ValueError("title, publisher, publication_date, and evidence_summary are required")
    weighting = SOURCE_WEIGHTS[source_type]
    return {
        "evidence_id": evidence_id,
        "source_type": source_type,
        "source_title": title,
        "publisher": publisher,
        "source_url": str(source_url).strip(),
        "publication_date": publication_date,
        "jurisdiction": _safe_text(jurisdiction, 120),
        "evidence_summary": evidence_summary,
        "confidence_category": weighting["confidence"],
        "evidence_weight": weighting["weight"],
        "ingested_at": ingested_at or datetime.now(timezone.utc).isoformat(),
        "public_source_declared": True,
        "legal_advice_provided": False,
        "knowledge_base_status": "not_proposed",
        "gareth_approval_required_for_knowledge_update": True,
        "candidate_data_minimised": True,
        **_safety_controls(),
    }


def generate_external_intelligence(evidence_records, topic, generated_at=None):
    records = list(evidence_records or [])
    topic = _safe_text(topic, 250)
    if not topic:
        raise ValueError("topic is required")
    if not records:
        raise ValueError("at least one evidence record is required")
    total_weight = sum(float(item.get("evidence_weight", 0)) for item in records)
    weighted_confidence = round(total_weight / len(records), 2)
    if weighted_confidence >= 90:
        category = "Very High"
    elif weighted_confidence >= 75:
        category = "High"
    elif weighted_confidence >= 50:
        category = "Medium"
    else:
        category = "Low"
    summaries = [_safe_text(item.get("evidence_summary"), 300) for item in records]
    return {
        "external_intelligence_id": f"external-intelligence-{len(records)}-{topic.lower().replace(' ', '-')[:40]}",
        "topic": topic,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "evidence_ids": [item.get("evidence_id") for item in records],
        "source_count": len(records),
        "weighted_confidence_score": weighted_confidence,
        "confidence_category": category,
        "intelligence_summary": summaries,
        "recommendations": [
            "Gareth should review the cited public evidence before any GLIRN guidance or process change.",
            "Treat lower-confidence discussion sources as directional context, not authoritative requirements.",
        ],
        "legal_advice_provided": False,
        "recommendation_only": True,
        "knowledge_base_status": "awaiting_gareth_approval",
        "gareth_approval_required": True,
        **_safety_controls(),
    }


def approve_knowledge_update(intelligence, rationale, approved_at=None):
    if not intelligence or not intelligence.get("external_intelligence_id"):
        raise ValueError("external intelligence record is required")
    rationale = _safe_text(rationale, 500)
    if not rationale:
        raise ValueError("approval rationale is required")
    return {
        "knowledge_update_id": f"knowledge-update-{intelligence['external_intelligence_id']}",
        "external_intelligence_id": intelligence["external_intelligence_id"],
        "topic": intelligence["topic"],
        "evidence_ids": list(intelligence.get("evidence_ids", [])),
        "approved_by": "Gareth",
        "approval_rationale": rationale,
        "approved_at": approved_at or datetime.now(timezone.utc).isoformat(),
        "knowledge_base_status": "approved_for_manual_use",
        "automatic_regulatory_change_implemented": False,
        "legal_advice_provided": False,
        **_safety_controls(),
    }


def _safety_controls():
    return {
        "external_retrieval_enabled": False,
        "external_organisation_contact_enabled": False,
        "automatic_regulatory_updates_enabled": False,
        "autonomous_decision_making_enabled": False,
        "automatic_outreach_enabled": False,
        "automatic_referral_enabled": False,
        "automatic_payment_enabled": False,
        "automatic_delivery_enabled": False,
        "external_commitments_enabled": False,
    }
