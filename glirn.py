from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import re

from glirn_human_review import build_initial_human_review_framework


LEGAL_SECTORS = [
    "Corporate & M&A",
    "Private Equity",
    "Banking & Finance",
    "Commercial Law",
    "Technology & AI Law",
    "Energy & Infrastructure",
    "Construction Law",
    "Litigation & Dispute Resolution",
    "Employment Law",
    "Intellectual Property",
    "In-House Counsel",
    "Partner & Executive Search",
]


EXECUTIVE_SEARCH_WORKFLOWS = [
    "Partner Search",
    "General Counsel",
    "Chief Legal Officer",
    "Senior Associate / Legal Director",
]


REVENUE_TYPES = [
    "contingency placement fee",
    "retained search fee",
    "executive search fee",
    "intelligence report fee",
    "subscription intelligence fee",
]


TARGET_CLIENT_TYPES = [
    "Law firms",
    "Boutique legal practices",
    "In-house legal departments",
    "Legal tech companies",
    "Private equity-backed companies",
    "Infrastructure / energy companies with legal teams",
]


TARGET_CANDIDATE_TYPES = [
    "Equity Partners",
    "Salaried Partners",
    "General Counsel",
    "Chief Legal Officers",
    "Legal Directors",
    "Senior Associates",
    "Commercial Lawyers",
    "Corporate / M&A Lawyers",
    "Banking & Finance Lawyers",
    "Technology & AI Lawyers",
    "Energy & Infrastructure Lawyers",
    "Construction Lawyers",
]


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def iso_to_datetime(value):
    if not value:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def sector_code(name):
    return (
        name.lower()
        .replace("&", "and")
        .replace("/", " ")
        .replace("-", " ")
        .replace("  ", " ")
        .strip()
        .replace(" ", "_")
    )


@dataclass
class LegalPracticeArea:
    code: str
    name: str
    capital_execution: bool = False

    def to_dict(self):
        return asdict(self)


@dataclass
class Jurisdiction:
    code: str
    name: str
    region: str = "global"
    capital_execution: bool = False

    def to_dict(self):
        return asdict(self)


@dataclass
class Candidate:
    candidate_id: str
    full_name: str
    practice_area: str
    jurisdiction: str
    seniority: str
    consent_status: str = "not_contacted"
    quality_score: float = 0
    capital_execution: bool = False

    def to_dict(self):
        return asdict(self)


@dataclass
class ClientFirm:
    firm_id: str
    name: str
    jurisdiction: str
    practice_areas: list[str]
    client_quality: float = 0
    capital_execution: bool = False

    def to_dict(self):
        return asdict(self)


@dataclass
class CandidateConsentRecord:
    consent_id: str
    candidate_id: str
    consent_status: str
    consent_source: str = "human_review"
    recorded_at: str = field(default_factory=utc_now)
    capital_execution: bool = False

    def to_dict(self):
        return asdict(self)


@dataclass
class ClientFeeAgreement:
    agreement_id: str
    firm_id: str
    fee_percentage: float
    payment_terms: str
    signed: bool = False
    capital_execution: bool = False

    def to_dict(self):
        return asdict(self)


@dataclass
class HumanApprovalDecision:
    decision_id: str
    subject_id: str
    subject_type: str
    decision: str
    reviewer_note: str = ""
    created_at: str = field(default_factory=utc_now)
    capital_execution: bool = False

    def to_dict(self):
        return asdict(self)


@dataclass
class ComplianceAlert:
    alert_id: str
    subject_id: str
    subject_type: str
    alert_type: str
    severity: str
    message: str
    outbound_action_blocked: bool = True
    created_at: str = field(default_factory=utc_now)
    capital_execution: bool = False

    def to_dict(self):
        return asdict(self)


@dataclass
class RecruitmentOpportunity:
    opportunity_id: str
    title: str
    candidate: Candidate
    client_firm: ClientFirm
    practice_area: str
    jurisdiction: str
    expected_fee_value: float
    placement_probability: float
    client_quality: float
    candidate_quality: float
    compliance_readiness: float
    urgency_score: float
    time_to_revenue: float
    status: str = "pending_human_approval"
    overall_glirn_score: float = 0
    capital_execution: bool = False

    def __post_init__(self):
        if not self.overall_glirn_score:
            self.overall_glirn_score = calculate_glirn_score(
                expected_fee_value=self.expected_fee_value,
                placement_probability=self.placement_probability,
                client_quality=self.client_quality,
                candidate_quality=self.candidate_quality,
                compliance_readiness=self.compliance_readiness,
                urgency_score=self.urgency_score,
                time_to_revenue=self.time_to_revenue,
            )

    def to_dict(self):
        data = asdict(self)
        data["candidate"] = self.candidate.to_dict()
        data["client_firm"] = self.client_firm.to_dict()
        data["capital_execution"] = False
        return data


def clamp_score(value):
    return max(0, min(float(value), 100))


def calculate_glirn_score(
    expected_fee_value,
    placement_probability,
    client_quality,
    candidate_quality,
    compliance_readiness,
    urgency_score,
    time_to_revenue,
):
    fee_score = clamp_score((float(expected_fee_value) / 100000) * 100)
    probability_score = clamp_score(float(placement_probability) * 100)
    time_score = clamp_score(100 - float(time_to_revenue))

    return round(
        fee_score * 0.20
        + probability_score * 0.20
        + clamp_score(client_quality) * 0.15
        + clamp_score(candidate_quality) * 0.15
        + clamp_score(compliance_readiness) * 0.15
        + clamp_score(urgency_score) * 0.10
        + time_score * 0.05,
        2,
    )


def estimate_fee_value(annual_compensation, fee_percentage=25, placement_probability=1.0):
    gross_fee = float(annual_compensation) * (float(fee_percentage) / 100)
    expected_fee = gross_fee * float(placement_probability)

    return {
        "annual_compensation": float(annual_compensation),
        "fee_percentage": float(fee_percentage),
        "gross_fee_value": round(gross_fee, 2),
        "placement_probability": float(placement_probability),
        "expected_fee_value": round(expected_fee, 2),
        "capital_execution": False,
    }


def calculate_radar_priority(opportunity):
    fee_score = clamp_score((float(opportunity.get("expected_fee_value", 0)) / 100000) * 100)
    placement_score = clamp_score(float(opportunity.get("placement_probability", 0)) * 100)
    glirn_score = clamp_score(opportunity.get("overall_glirn_score", 0))
    compliance_score = clamp_score(opportunity.get("compliance_readiness", 0))
    urgency_score = clamp_score(opportunity.get("urgency_score", 0))

    return round(
        fee_score * 0.35
        + placement_score * 0.20
        + glirn_score * 0.20
        + compliance_score * 0.15
        + urgency_score * 0.10,
        2,
    )


def radar_recommendation(opportunity):
    compliance = clamp_score(opportunity.get("compliance_readiness", 0))
    priority = clamp_score(opportunity.get("radar_priority_score", 0))

    if compliance < 70:
        return "Request evidence before any outreach."
    if priority >= 75:
        return "Review first: high expected fee value with strong candidate and client quality."
    if priority >= 60:
        return "Monitor and prepare human-approved outreach."
    return "Defer until higher-value signals appear."


def build_legal_opportunity_radar(opportunities):
    ranked = []

    for opportunity in opportunities:
        candidate = opportunity.get("candidate", {}) or {}
        client_firm = opportunity.get("client_firm", {}) or {}
        radar_item = {
            **opportunity,
            "fee_estimate": {
                "expected_fee_value": float(opportunity.get("expected_fee_value", 0)),
                "placement_probability": float(opportunity.get("placement_probability", 0)),
                "capital_execution": False,
            },
            "radar_priority_score": calculate_radar_priority(opportunity),
            "approval_required": True,
            "outbound_action_allowed": False,
            "capital_execution": False,
            "candidate_view": {
                "candidate_id": candidate.get("candidate_id"),
                "full_name": candidate.get("full_name"),
                "practice_area": candidate.get("practice_area"),
                "jurisdiction": candidate.get("jurisdiction"),
                "seniority": candidate.get("seniority"),
                "candidate_quality": opportunity.get("candidate_quality", candidate.get("quality_score", 0)),
                "expected_fee_value": float(opportunity.get("expected_fee_value", 0)),
                "approval_required": True,
                "capital_execution": False,
            },
            "client_firm_view": {
                "firm_id": client_firm.get("firm_id"),
                "name": client_firm.get("name"),
                "jurisdiction": client_firm.get("jurisdiction"),
                "practice_areas": client_firm.get("practice_areas", []),
                "client_quality": opportunity.get("client_quality", client_firm.get("client_quality", 0)),
                "expected_fee_value": float(opportunity.get("expected_fee_value", 0)),
                "approval_required": True,
                "capital_execution": False,
            },
        }
        radar_item["dave_recommendation"] = radar_recommendation(radar_item)
        ranked.append(radar_item)

    ranked = sorted(
        ranked,
        key=lambda item: (
            item.get("radar_priority_score", 0),
            item.get("expected_fee_value", 0),
        ),
        reverse=True,
    )

    for index, item in enumerate(ranked, start=1):
        item["priority_rank"] = index

    highest_value_candidate = None
    highest_value_client_firm = None

    if ranked:
        highest_value_candidate = max(
            (item["candidate_view"] for item in ranked),
            key=lambda item: item.get("expected_fee_value", 0),
        )
        highest_value_client_firm = max(
            (item["client_firm_view"] for item in ranked),
            key=lambda item: item.get("expected_fee_value", 0),
        )

    return {
        "engine": "legal_opportunity_radar",
        "opportunities_ranked": ranked,
        "top_opportunity": ranked[0] if ranked else None,
        "highest_value_candidate": highest_value_candidate,
        "highest_value_client_firm": highest_value_client_firm,
        "dave_recommends_first": ranked[0] if ranked else None,
        "approval_required_for_outbound_action": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def build_glirn_approval_centre(opportunities, pending_approvals=None):
    pending_approvals = pending_approvals or []
    glirn_approvals = [
        approval
        for approval in pending_approvals
        if (approval.get("route_result", {}) or {}).get("source") == "glirn"
    ]

    pending_opportunities = [
        opportunity
        for opportunity in opportunities
        if opportunity.get("status") == "pending_human_approval"
    ]
    queue_items = []

    for opportunity in pending_opportunities:
        matching_approval = next(
            (
                approval
                for approval in glirn_approvals
                if (approval.get("route_result", {}) or {}).get("opportunity_id")
                == opportunity.get("opportunity_id")
            ),
            None,
        )
        queue_items.append({
            "approval_id": matching_approval.get("approval_id") if matching_approval else None,
            "opportunity_id": opportunity.get("opportunity_id"),
            "title": opportunity.get("title"),
            "practice_area": opportunity.get("practice_area"),
            "expected_fee_value": opportunity.get("expected_fee_value"),
            "overall_glirn_score": opportunity.get("overall_glirn_score"),
            "status": "waiting_for_gareth_approval",
            "allowed_actions": ["approve", "reject", "monitor"],
            "approval_reason_required": True,
            "outbound_action_locked": True,
            "candidate_introduction_locked": True,
            "client_engagement_locked": True,
            "fee_negotiation_locked": True,
            "capital_execution": False,
        })

    return {
        "status": "Waiting for Gareth Approval",
        "pending_count": len(queue_items),
        "queue": queue_items,
        "locks": {
            "outbound_action_locked": True,
            "candidate_introduction_locked": True,
            "client_engagement_locked": True,
            "fee_negotiation_locked": True,
        },
        "rules": [
            "No candidate introduction without approval.",
            "No client engagement without approval.",
            "No fee proposal without approval.",
            "No outbound action without approval.",
        ],
        "capital_execution": False,
        "autonomous_execution": False,
    }


def build_candidate_consent_ledger(opportunities):
    consent_profiles = {
        "candidate-stub-001": {
            "consent_status": "active",
            "expires_at": "2026-12-31T23:59:59+00:00",
            "consent_scope": "candidate_introduction",
        },
        "candidate-stub-002": {
            "consent_status": "missing",
            "expires_at": None,
            "consent_scope": "none",
        },
        "candidate-stub-003": {
            "consent_status": "expired",
            "expires_at": "2026-01-01T00:00:00+00:00",
            "consent_scope": "candidate_introduction",
        },
        "candidate-stub-004": {
            "consent_status": "active",
            "expires_at": "2026-11-30T23:59:59+00:00",
            "consent_scope": "candidate_introduction",
        },
        "candidate-stub-005": {
            "consent_status": "active",
            "expires_at": "2026-12-31T23:59:59+00:00",
            "consent_scope": "candidate_introduction",
        },
    }
    records = []

    for opportunity in opportunities:
        candidate = opportunity.get("candidate", {}) or {}
        candidate_id = candidate.get("candidate_id")
        profile = consent_profiles.get(candidate_id, {
            "consent_status": "missing",
            "expires_at": None,
            "consent_scope": "none",
        })
        records.append({
            "consent_id": f"consent-{candidate_id}",
            "candidate_id": candidate_id,
            "candidate_name": candidate.get("full_name"),
            "consent_status": profile["consent_status"],
            "consent_scope": profile["consent_scope"],
            "expires_at": profile["expires_at"],
            "candidate_introduction_allowed": profile["consent_status"] == "active",
            "outbound_action_blocked": profile["consent_status"] != "active",
            "capital_execution": False,
        })

    return records


def build_client_terms_status(opportunities):
    terms_profiles = {
        "client-stub-001": "recorded",
        "client-stub-002": "missing",
        "client-stub-003": "recorded",
        "client-stub-004": "missing",
        "client-stub-005": "recorded",
    }
    records = []

    for opportunity in opportunities:
        client = opportunity.get("client_firm", {}) or {}
        firm_id = client.get("firm_id")
        terms_status = terms_profiles.get(firm_id, "missing")
        records.append({
            "firm_id": firm_id,
            "client_name": client.get("name"),
            "terms_status": terms_status,
            "candidate_details_allowed": terms_status == "recorded",
            "client_engagement_blocked": terms_status != "recorded",
            "capital_execution": False,
        })

    return records


def build_jurisdiction_compliance_profiles():
    return [
        {
            "jurisdiction": "England & Wales",
            "code": "GB-ENG",
            "profile": "UK GDPR and recruitment consent controls required.",
            "candidate_consent_required": True,
            "client_terms_required": True,
            "data_retention_days": 365,
            "capital_execution": False,
        },
        {
            "jurisdiction": "United Arab Emirates",
            "code": "AE",
            "profile": "Consent and cross-border data caution required.",
            "candidate_consent_required": True,
            "client_terms_required": True,
            "data_retention_days": 365,
            "capital_execution": False,
        },
        {
            "jurisdiction": "Singapore",
            "code": "SG",
            "profile": "PDPA-style consent and retention controls required.",
            "candidate_consent_required": True,
            "client_terms_required": True,
            "data_retention_days": 365,
            "capital_execution": False,
        },
    ]


def build_data_retention_status(consent_ledger, deletion_requests=None):
    deletion_requests = deletion_requests or []
    requested_ids = {request.get("candidate_id") for request in deletion_requests}

    records = []
    for consent in consent_ledger:
        candidate_id = consent.get("candidate_id")
        records.append({
            "candidate_id": candidate_id,
            "retention_status": "deletion_requested" if candidate_id in requested_ids else "within_retention_window",
            "deletion_requested": candidate_id in requested_ids,
            "data_retention_days": 365,
            "outbound_action_blocked": candidate_id in requested_ids,
            "capital_execution": False,
        })

    return records


def flag_deletion_request(candidate_id, reason):
    return {
        "request_id": f"delete-{candidate_id}",
        "candidate_id": candidate_id,
        "reason": reason,
        "status": "deletion_review_required",
        "record_flagged": True,
        "outbound_action_blocked": True,
        "created_at": utc_now(),
        "capital_execution": False,
    }


def create_compliance_alerts(consent_ledger, client_terms_status, data_retention_status):
    alerts = []

    for consent in consent_ledger:
        status = consent.get("consent_status")
        if status == "missing":
            alerts.append(ComplianceAlert(
                alert_id=f"missing-consent-{consent.get('candidate_id')}",
                subject_id=consent.get("candidate_id"),
                subject_type="candidate",
                alert_type="missing_consent",
                severity="high",
                message="Candidate consent is missing. Candidate introduction and outbound action are blocked.",
            ).to_dict())
        elif status == "expired":
            alerts.append(ComplianceAlert(
                alert_id=f"expired-consent-{consent.get('candidate_id')}",
                subject_id=consent.get("candidate_id"),
                subject_type="candidate",
                alert_type="expired_consent",
                severity="critical",
                message="Candidate consent has expired. Outbound action is blocked.",
            ).to_dict())

    for client in client_terms_status:
        if client.get("terms_status") != "recorded":
            alerts.append(ComplianceAlert(
                alert_id=f"missing-client-terms-{client.get('firm_id')}",
                subject_id=client.get("firm_id"),
                subject_type="client_firm",
                alert_type="missing_client_terms",
                severity="high",
                message="Client terms status is missing. Candidate details cannot be sent.",
            ).to_dict())

    for retention in data_retention_status:
        if retention.get("deletion_requested"):
            alerts.append(ComplianceAlert(
                alert_id=f"deletion-request-{retention.get('candidate_id')}",
                subject_id=retention.get("candidate_id"),
                subject_type="candidate",
                alert_type="deletion_request",
                severity="critical",
                message="Deletion request is flagged. Outbound action is blocked pending review.",
            ).to_dict())

    return alerts


def evaluate_compliance_readiness(candidate_consent, client_terms, retention_status=None):
    retention_status = retention_status or {}
    consent_active = candidate_consent.get("consent_status") == "active"
    terms_recorded = client_terms.get("terms_status") == "recorded"
    deletion_requested = retention_status.get("deletion_requested", False)
    outbound_allowed = consent_active and terms_recorded and not deletion_requested

    score = 100
    if not consent_active:
        score -= 45
    if candidate_consent.get("consent_status") == "expired":
        score -= 20
    if not terms_recorded:
        score -= 30
    if deletion_requested:
        score -= 50

    return {
        "candidate_introduction_allowed": outbound_allowed,
        "client_candidate_details_allowed": terms_recorded and consent_active,
        "outbound_action_allowed": outbound_allowed,
        "outbound_action_blocked": not outbound_allowed,
        "compliance_readiness_score": clamp_score(score),
        "capital_execution": False,
    }


def build_glirn_compliance_core(opportunities, deletion_requests=None):
    deletion_requests = deletion_requests or []
    consent_ledger = build_candidate_consent_ledger(opportunities)
    client_terms_status = build_client_terms_status(opportunities)
    jurisdiction_profiles = build_jurisdiction_compliance_profiles()
    retention_status = build_data_retention_status(consent_ledger, deletion_requests)
    alerts = create_compliance_alerts(consent_ledger, client_terms_status, retention_status)

    readiness_records = []
    for opportunity in opportunities:
        candidate_id = (opportunity.get("candidate", {}) or {}).get("candidate_id")
        firm_id = (opportunity.get("client_firm", {}) or {}).get("firm_id")
        candidate_consent = next(item for item in consent_ledger if item.get("candidate_id") == candidate_id)
        client_terms = next(item for item in client_terms_status if item.get("firm_id") == firm_id)
        retention = next(item for item in retention_status if item.get("candidate_id") == candidate_id)
        readiness = evaluate_compliance_readiness(candidate_consent, client_terms, retention)
        readiness_records.append({
            "opportunity_id": opportunity.get("opportunity_id"),
            "title": opportunity.get("title"),
            **readiness,
        })

    missing_consent_alerts = [
        alert for alert in alerts if alert.get("alert_type") == "missing_consent"
    ]
    consent_expiry_alerts = [
        alert for alert in alerts if alert.get("alert_type") == "expired_consent"
    ]
    restricted_actions = [
        record for record in readiness_records if record.get("outbound_action_blocked")
    ]
    average_readiness = (
        sum(record["compliance_readiness_score"] for record in readiness_records) / len(readiness_records)
        if readiness_records else 0
    )

    return {
        "status": "Compliance-First Controls Active",
        "candidate_consent_ledger": consent_ledger,
        "client_consent_terms_status": client_terms_status,
        "jurisdiction_compliance_profile": jurisdiction_profiles,
        "data_retention_status": retention_status,
        "deletion_request_workflow": deletion_requests,
        "consent_expiry_alerts": consent_expiry_alerts,
        "missing_consent_alerts": missing_consent_alerts,
        "compliance_alerts": alerts,
        "restricted_outbound_actions": restricted_actions,
        "compliance_readiness_score": round(average_readiness, 2),
        "rules": [
            "Candidate cannot be introduced without active consent.",
            "Client cannot receive candidate details without terms status recorded.",
            "Any missing consent creates a compliance alert.",
            "Any expired consent blocks outbound action.",
        ],
        "capital_execution": False,
        "autonomous_execution": False,
    }


def classify_candidate_seniority(opportunity):
    title = str(opportunity.get("title", "")).lower()
    seniority = str((opportunity.get("candidate", {}) or {}).get("seniority", "")).lower()
    combined = f"{title} {seniority}"

    if "chief legal officer" in combined or "clo" in combined:
        return "Chief Legal Officer"
    if "general counsel" in combined:
        return "General Counsel"
    if "partner" in combined:
        return "Partner"
    if "legal director" in combined or "senior associate" in combined or "senior legal counsel" in combined:
        return "Senior Associate / Legal Director"
    return "Executive Legal Talent"


def executive_workflow_for_seniority(seniority_classification):
    if seniority_classification in {"Partner", "General Counsel", "Chief Legal Officer"}:
        return f"{seniority_classification} workflow" if seniority_classification != "Partner" else "Partner Search workflow"
    if seniority_classification == "Senior Associate / Legal Director":
        return "Senior Associate / Legal Director workflow"
    return "Executive Legal Talent workflow"


def estimate_executive_placement_fee(annual_compensation, fee_percentage=30):
    return {
        "annual_compensation": float(annual_compensation),
        "fee_percentage": float(fee_percentage),
        "estimated_placement_fee": round(float(annual_compensation) * (float(fee_percentage) / 100), 2),
        "capital_execution": False,
    }


def estimate_retained_search_fee(estimated_placement_fee, retainer_percentage=33.33):
    return {
        "estimated_placement_fee": float(estimated_placement_fee),
        "retainer_percentage": float(retainer_percentage),
        "estimated_retainer_fee": round(float(estimated_placement_fee) * (float(retainer_percentage) / 100), 2),
        "gareth_approval_required": True,
        "capital_execution": False,
    }


def is_premium_executive_opportunity(seniority_classification):
    return seniority_classification in {"Partner", "General Counsel", "Chief Legal Officer"}


def calculate_high_fee_priority_score(opportunity, compliance_readiness):
    fee_score = clamp_score((float(opportunity.get("expected_fee_value", 0)) / 150000) * 100)
    probability_score = clamp_score(float(opportunity.get("placement_probability", 0)) * 100)
    client_score = clamp_score(opportunity.get("client_quality", 0))
    candidate_score = clamp_score(opportunity.get("candidate_quality", 0))
    compliance_score = clamp_score(compliance_readiness.get("compliance_readiness_score", 0))
    premium_bonus = 15 if is_premium_executive_opportunity(classify_candidate_seniority(opportunity)) else 0

    return round(
        fee_score * 0.35
        + probability_score * 0.15
        + client_score * 0.15
        + candidate_score * 0.15
        + compliance_score * 0.15
        + premium_bonus,
        2,
    )


def build_executive_search_engine(opportunities, compliance_core=None):
    compliance_core = compliance_core or build_glirn_compliance_core(opportunities)
    readiness_by_opportunity = {
        item.get("opportunity_id"): item
        for item in compliance_core.get("restricted_outbound_actions", [])
    }
    all_readiness = {}
    consent_ledger = compliance_core.get("candidate_consent_ledger", [])
    client_terms = compliance_core.get("client_consent_terms_status", [])
    retention = compliance_core.get("data_retention_status", [])

    for opportunity in opportunities:
        candidate_id = (opportunity.get("candidate", {}) or {}).get("candidate_id")
        firm_id = (opportunity.get("client_firm", {}) or {}).get("firm_id")
        candidate_consent = next(item for item in consent_ledger if item.get("candidate_id") == candidate_id)
        firm_terms = next(item for item in client_terms if item.get("firm_id") == firm_id)
        retention_status = next(item for item in retention if item.get("candidate_id") == candidate_id)
        all_readiness[opportunity.get("opportunity_id")] = evaluate_compliance_readiness(
            candidate_consent,
            firm_terms,
            retention_status,
        )

    executive_items = []
    for opportunity in opportunities:
        seniority = classify_candidate_seniority(opportunity)
        placement_fee = estimate_executive_placement_fee(
            annual_compensation=float(opportunity.get("expected_fee_value", 0)) / 0.30,
            fee_percentage=30,
        )
        retainer_fee = estimate_retained_search_fee(placement_fee["estimated_placement_fee"])
        readiness = all_readiness.get(opportunity.get("opportunity_id")) or readiness_by_opportunity.get(opportunity.get("opportunity_id"), {})
        missing_consent_blocks = not readiness.get("candidate_introduction_allowed", False)
        missing_client_terms_blocks = not readiness.get("client_candidate_details_allowed", False)
        high_fee_score = calculate_high_fee_priority_score(opportunity, readiness)

        executive_items.append({
            "opportunity_id": opportunity.get("opportunity_id"),
            "title": opportunity.get("title"),
            "workflow": executive_workflow_for_seniority(seniority),
            "candidate_seniority_classification": seniority,
            "candidate_name": (opportunity.get("candidate", {}) or {}).get("full_name"),
            "client_firm": (opportunity.get("client_firm", {}) or {}).get("name"),
            "estimated_placement_fee": placement_fee["estimated_placement_fee"],
            "estimated_retainer_fee": retainer_fee["estimated_retainer_fee"],
            "premium_opportunity": is_premium_executive_opportunity(seniority),
            "high_fee_priority_score": high_fee_score,
            "executive_candidate_outreach_allowed": not missing_consent_blocks,
            "client_engagement_allowed": not missing_client_terms_blocks,
            "retained_search_proposal_requires_gareth_approval": True,
            "outbound_action_blocked": missing_consent_blocks or missing_client_terms_blocks,
            "blocked_reasons": [
                reason
                for reason, blocked in [
                    ("missing_or_inactive_candidate_consent", missing_consent_blocks),
                    ("missing_client_terms_status", missing_client_terms_blocks),
                ]
                if blocked
            ],
            "dave_recommendation": "Review first for retained executive search." if high_fee_score >= 70 else "Monitor until compliance and commercial signals improve.",
            "capital_execution": False,
            "autonomous_execution": False,
        })

    executive_items = sorted(
        executive_items,
        key=lambda item: (
            item.get("premium_opportunity", False),
            item.get("high_fee_priority_score", 0),
            item.get("estimated_placement_fee", 0),
        ),
        reverse=True,
    )

    return {
        "status": "Executive Search Engine Active",
        "workflows": EXECUTIVE_SEARCH_WORKFLOWS,
        "top_executive_opportunities": executive_items,
        "dave_recommends_first": executive_items[0] if executive_items else None,
        "retained_search_proposal_requires_gareth_approval": True,
        "rules": [
            "Executive candidate outreach requires active consent.",
            "Client engagement requires client terms status.",
            "Retained search proposal requires Gareth approval.",
            "Partner, General Counsel, and Chief Legal Officer placements are premium.",
        ],
        "capital_execution": False,
        "autonomous_execution": False,
    }


def generate_salary_intelligence(opportunities):
    signals = []

    for opportunity in opportunities:
        estimated_fee = float(opportunity.get("expected_fee_value", 0))
        seniority = classify_candidate_seniority(opportunity)
        fee_percentage = 30 if is_premium_executive_opportunity(seniority) else 25
        estimated_salary = round(estimated_fee / (fee_percentage / 100), 2) if fee_percentage else 0
        signals.append({
            "practice_area": opportunity.get("practice_area"),
            "jurisdiction": opportunity.get("jurisdiction"),
            "seniority": seniority,
            "estimated_salary": estimated_salary,
            "estimated_fee_value": estimated_fee,
            "signal_strength": clamp_score((estimated_fee / 120000) * 100),
            "candidate_personal_data_included": False,
            "capital_execution": False,
        })

    return sorted(
        signals,
        key=lambda item: (item.get("estimated_salary", 0), item.get("signal_strength", 0)),
        reverse=True,
    )


def generate_market_intelligence(opportunities):
    total_expected_fee = sum(float(item.get("expected_fee_value", 0)) for item in opportunities)
    average_probability = (
        sum(float(item.get("placement_probability", 0)) for item in opportunities) / len(opportunities)
        if opportunities else 0
    )
    premium_count = len([
        item for item in opportunities
        if is_premium_executive_opportunity(classify_candidate_seniority(item))
    ])

    return {
        "market_summary": "High-fee legal hiring demand is strongest where executive seniority, cross-border jurisdiction, and premium practice areas overlap.",
        "total_expected_fee_value": round(total_expected_fee, 2),
        "average_placement_probability": round(average_probability, 2),
        "premium_opportunity_count": premium_count,
        "client_intelligence_hook": "Use salary, jurisdiction, and practice-area signals to open a client conversation before recruitment placement.",
        "candidate_personal_data_included": False,
        "capital_execution": False,
    }


def generate_hiring_trend_intelligence(opportunities):
    alerts = []

    for opportunity in opportunities:
        urgency = clamp_score(opportunity.get("urgency_score", 0))
        if urgency >= 80:
            alerts.append({
                "alert_type": "hiring_trend",
                "title": f"Rising demand for {opportunity.get('practice_area')}",
                "practice_area": opportunity.get("practice_area"),
                "jurisdiction": opportunity.get("jurisdiction"),
                "urgency_score": urgency,
                "message": "High urgency score suggests client-facing intelligence hook.",
                "candidate_personal_data_included": False,
                "capital_execution": False,
            })

    return sorted(alerts, key=lambda item: item.get("urgency_score", 0), reverse=True)


def rank_hot_practice_areas(opportunities):
    area_scores = {}

    for opportunity in opportunities:
        area = opportunity.get("practice_area", "unknown")
        area_scores.setdefault(area, {
            "practice_area": area,
            "opportunity_count": 0,
            "total_expected_fee_value": 0,
            "average_urgency_score": 0,
            "growth_score": 0,
            "capital_execution": False,
        })
        area_scores[area]["opportunity_count"] += 1
        area_scores[area]["total_expected_fee_value"] += float(opportunity.get("expected_fee_value", 0))
        area_scores[area]["average_urgency_score"] += float(opportunity.get("urgency_score", 0))

    ranked = []
    for item in area_scores.values():
        item["average_urgency_score"] = round(item["average_urgency_score"] / item["opportunity_count"], 2)
        fee_score = clamp_score((item["total_expected_fee_value"] / 150000) * 100)
        item["growth_score"] = round(fee_score * 0.65 + item["average_urgency_score"] * 0.35, 2)
        ranked.append(item)

    return sorted(ranked, key=lambda item: item.get("growth_score", 0), reverse=True)


def rank_jurisdiction_demand(opportunities):
    jurisdiction_scores = {}

    for opportunity in opportunities:
        jurisdiction = opportunity.get("jurisdiction", "unknown")
        jurisdiction_scores.setdefault(jurisdiction, {
            "jurisdiction": jurisdiction,
            "opportunity_count": 0,
            "total_expected_fee_value": 0,
            "average_client_quality": 0,
            "demand_score": 0,
            "capital_execution": False,
        })
        jurisdiction_scores[jurisdiction]["opportunity_count"] += 1
        jurisdiction_scores[jurisdiction]["total_expected_fee_value"] += float(opportunity.get("expected_fee_value", 0))
        jurisdiction_scores[jurisdiction]["average_client_quality"] += float(opportunity.get("client_quality", 0))

    ranked = []
    for item in jurisdiction_scores.values():
        item["average_client_quality"] = round(item["average_client_quality"] / item["opportunity_count"], 2)
        fee_score = clamp_score((item["total_expected_fee_value"] / 150000) * 100)
        item["demand_score"] = round(fee_score * 0.70 + item["average_client_quality"] * 0.30, 2)
        ranked.append(item)

    return sorted(ranked, key=lambda item: item.get("demand_score", 0), reverse=True)


def generate_competitor_hiring_signals(opportunities):
    signals = []

    for opportunity in opportunities:
        if float(opportunity.get("client_quality", 0)) >= 85:
            signals.append({
                "signal_type": "competitor_hiring_signal",
                "practice_area": opportunity.get("practice_area"),
                "jurisdiction": opportunity.get("jurisdiction"),
                "seniority": classify_candidate_seniority(opportunity),
                "signal_strength": opportunity.get("client_quality", 0),
                "message": "High-quality client signal suggests competitor demand in this hiring segment.",
                "candidate_personal_data_included": False,
                "capital_execution": False,
            })

    return sorted(signals, key=lambda item: item.get("signal_strength", 0), reverse=True)


def build_candidate_specific_report(opportunity, consent_record):
    consent_active = consent_record.get("consent_status") == "active"

    if not consent_active:
        return {
            "candidate_personal_data_included": False,
            "blocked": True,
            "blocked_reason": "candidate_personal_data_blocked_without_active_consent",
            "capital_execution": False,
        }

    candidate = opportunity.get("candidate", {}) or {}
    return {
        "candidate_personal_data_included": True,
        "blocked": False,
        "candidate_name": candidate.get("full_name"),
        "candidate_id": candidate.get("candidate_id"),
        "seniority": candidate.get("seniority"),
        "practice_area": candidate.get("practice_area"),
        "capital_execution": False,
    }


def build_legal_intelligence_network(opportunities, compliance_core=None):
    compliance_core = compliance_core or build_glirn_compliance_core(opportunities)
    salary_signals = generate_salary_intelligence(opportunities)
    hot_practice_areas = rank_hot_practice_areas(opportunities)
    growing_jurisdictions = rank_jurisdiction_demand(opportunities)
    hiring_trends = generate_hiring_trend_intelligence(opportunities)
    competitor_signals = generate_competitor_hiring_signals(opportunities)
    market_intelligence = generate_market_intelligence(opportunities)
    dave_first = None

    if hot_practice_areas and growing_jurisdictions:
        dave_first = {
            "recommendation": "Lead with intelligence, then qualify recruitment demand.",
            "practice_area": hot_practice_areas[0].get("practice_area"),
            "jurisdiction": growing_jurisdictions[0].get("jurisdiction"),
            "reason": "Highest combined practice-area growth and jurisdiction demand.",
            "gareth_approval_required": True,
            "capital_execution": False,
        }

    return {
        "status": "Legal Intelligence Network Active",
        "salary_intelligence": salary_signals,
        "market_intelligence": market_intelligence,
        "hiring_trend_intelligence": hiring_trends,
        "practice_area_growth_intelligence": hot_practice_areas,
        "jurisdiction_demand_intelligence": growing_jurisdictions,
        "competitor_hiring_signal_data": competitor_signals,
        "top_salary_signals": salary_signals[:3],
        "hot_practice_areas": hot_practice_areas[:3],
        "growing_jurisdictions": growing_jurisdictions[:3],
        "hiring_trend_alerts": hiring_trends[:3],
        "client_intelligence_hook": market_intelligence.get("client_intelligence_hook"),
        "dave_recommends_first": dave_first,
        "client_facing_report_generation_requires_gareth_approval": True,
        "candidate_specific_reports_require_active_consent": True,
        "candidate_personal_data_exposed_without_consent": False,
        "rules": [
            "Intelligence reports must not expose candidate personal data without consent.",
            "Candidate-specific reports require active consent.",
            "Client-facing report generation requires Gareth approval.",
            "Every report-generation request is audit logged.",
        ],
        "capital_execution": False,
        "autonomous_execution": False,
    }


def calculate_placement_fee(annual_compensation, fee_percentage=25):
    return {
        "fee_type": "contingency placement fee",
        "annual_compensation": float(annual_compensation),
        "fee_percentage": float(fee_percentage),
        "calculated_fee": round(float(annual_compensation) * (float(fee_percentage) / 100), 2),
        "capital_execution": False,
    }


def calculate_retained_search_commercial_fee(annual_compensation, fee_percentage=30, retainer_percentage=33.33):
    placement = calculate_placement_fee(annual_compensation, fee_percentage=fee_percentage)
    retainer = estimate_retained_search_fee(placement["calculated_fee"], retainer_percentage=retainer_percentage)

    return {
        "fee_type": "retained search fee",
        "estimated_placement_fee": placement["calculated_fee"],
        "estimated_retainer_fee": retainer["estimated_retainer_fee"],
        "gareth_approval_required": True,
        "capital_execution": False,
    }


def calculate_intelligence_report_fee(report_type="market_intelligence"):
    fee_map = {
        "market_intelligence": 750,
        "salary_intelligence": 500,
        "hiring_trend_intelligence": 650,
        "subscription_intelligence": 250,
    }
    fee_type = "subscription intelligence fee" if report_type == "subscription_intelligence" else "intelligence report fee"

    return {
        "fee_type": fee_type,
        "report_type": report_type,
        "calculated_fee": fee_map.get(report_type, 500),
        "gareth_approval_required": True,
        "capital_execution": False,
    }


def determine_commercial_fee_type(opportunity):
    seniority = classify_candidate_seniority(opportunity)
    if is_premium_executive_opportunity(seniority):
        return "executive search fee"
    if seniority == "Senior Associate / Legal Director":
        return "contingency placement fee"
    return "contingency placement fee"


def fee_negotiation_recommendation(item):
    if item.get("invoice_readiness") != "ready":
        return "Do not propose fees until terms and consent checks are complete."
    if item.get("estimated_revenue", 0) >= 80000:
        return "Request Gareth approval for premium fee negotiation."
    return "Prepare Gareth-approved standard fee proposal."


def build_commercial_revenue_engine(opportunities, compliance_core=None, intelligence_network=None, executive_search=None):
    compliance_core = compliance_core or build_glirn_compliance_core(opportunities)
    intelligence_network = intelligence_network or build_legal_intelligence_network(opportunities, compliance_core=compliance_core)
    executive_search = executive_search or build_executive_search_engine(opportunities, compliance_core=compliance_core)

    consent_by_candidate = {
        item.get("candidate_id"): item
        for item in compliance_core.get("candidate_consent_ledger", [])
    }
    terms_by_client = {
        item.get("firm_id"): item
        for item in compliance_core.get("client_consent_terms_status", [])
    }
    executive_by_opportunity = {
        item.get("opportunity_id"): item
        for item in executive_search.get("top_executive_opportunities", [])
    }
    pipeline = []

    for opportunity in opportunities:
        candidate_id = (opportunity.get("candidate", {}) or {}).get("candidate_id")
        firm_id = (opportunity.get("client_firm", {}) or {}).get("firm_id")
        consent = consent_by_candidate.get(candidate_id, {})
        terms = terms_by_client.get(firm_id, {})
        consent_active = consent.get("consent_status") == "active"
        terms_recorded = terms.get("terms_status") == "recorded"
        fee_type = determine_commercial_fee_type(opportunity)
        executive_item = executive_by_opportunity.get(opportunity.get("opportunity_id"), {})
        estimated_revenue = (
            executive_item.get("estimated_placement_fee")
            if fee_type == "executive search fee"
            else opportunity.get("expected_fee_value", 0)
        )
        invoice_ready = terms_recorded and consent_active

        pipeline_item = {
            "opportunity_id": opportunity.get("opportunity_id"),
            "title": opportunity.get("title"),
            "client_firm": (opportunity.get("client_firm", {}) or {}).get("name"),
            "fee_type": fee_type,
            "estimated_revenue": round(float(estimated_revenue or 0), 2),
            "success_fee_status": "unearned_pending_placement",
            "invoice_readiness": "ready" if invoice_ready else "blocked",
            "client_terms_readiness": "recorded" if terms_recorded else "missing",
            "candidate_submission_allowed": consent_active,
            "fee_proposal_requires_gareth_approval": True,
            "human_approval_required": True,
            "awaiting_gareth_approval": True,
            "blocked_reasons": [
                reason
                for reason, blocked in [
                    ("missing_client_terms", not terms_recorded),
                    ("missing_or_inactive_candidate_consent", not consent_active),
                ]
                if blocked
            ],
            "capital_execution": False,
            "autonomous_execution": False,
        }
        pipeline_item["fee_negotiation_recommendation"] = fee_negotiation_recommendation(pipeline_item)
        pipeline.append(pipeline_item)

    intelligence_report_fee = calculate_intelligence_report_fee("market_intelligence")
    subscription_fee = calculate_intelligence_report_fee("subscription_intelligence")
    pipeline.append({
        "opportunity_id": "glirn-intelligence-report-fee",
        "title": "Client Intelligence Report",
        "client_firm": "prospective client",
        "fee_type": intelligence_report_fee["fee_type"],
        "estimated_revenue": intelligence_report_fee["calculated_fee"],
        "success_fee_status": "report_fee_pending_approval",
        "invoice_readiness": "blocked",
        "client_terms_readiness": "missing",
        "candidate_submission_allowed": False,
        "fee_proposal_requires_gareth_approval": True,
        "human_approval_required": True,
        "awaiting_gareth_approval": True,
        "blocked_reasons": ["missing_client_terms"],
        "fee_negotiation_recommendation": "Use intelligence as the hook, then request Gareth approval before any fee proposal.",
        "capital_execution": False,
        "autonomous_execution": False,
    })
    pipeline.append({
        "opportunity_id": "glirn-subscription-intelligence-fee",
        "title": "Subscription Intelligence Fee",
        "client_firm": "prospective client",
        "fee_type": subscription_fee["fee_type"],
        "estimated_revenue": subscription_fee["calculated_fee"],
        "success_fee_status": "subscription_fee_pending_approval",
        "invoice_readiness": "blocked",
        "client_terms_readiness": "missing",
        "candidate_submission_allowed": False,
        "fee_proposal_requires_gareth_approval": True,
        "human_approval_required": True,
        "awaiting_gareth_approval": True,
        "blocked_reasons": ["missing_client_terms"],
        "fee_negotiation_recommendation": "Subscription intelligence requires Gareth-approved commercial terms.",
        "capital_execution": False,
        "autonomous_execution": False,
    })

    pipeline = sorted(pipeline, key=lambda item: item.get("estimated_revenue", 0), reverse=True)
    highest = pipeline[0] if pipeline else None
    estimated_total = sum(float(item.get("estimated_revenue", 0)) for item in pipeline)

    return {
        "status": "Commercial Revenue Controls Active",
        "revenue_types": REVENUE_TYPES,
        "estimated_revenue_pipeline": round(estimated_total, 2),
        "commercial_pipeline": pipeline,
        "highest_fee_opportunity": highest,
        "dave_recommends_first": {
            "recommendation": highest.get("fee_negotiation_recommendation") if highest else "No commercial recommendation available.",
            "opportunity_id": highest.get("opportunity_id") if highest else None,
            "fee_type": highest.get("fee_type") if highest else None,
            "awaiting_gareth_approval": True,
            "capital_execution": False,
        },
        "awaiting_gareth_approval": True,
        "rules": [
            "No invoice readiness unless client terms are recorded.",
            "No fee proposal without Gareth approval.",
            "No candidate submission without active consent.",
            "Every commercial action is audit logged.",
            "Human approval remains mandatory.",
        ],
        "capital_execution": False,
        "autonomous_execution": False,
    }


def classify_target_client_type(opportunity):
    practice_areas = (opportunity.get("client_firm", {}) or {}).get("practice_areas", [])
    practice_area = opportunity.get("practice_area", "")
    seniority = classify_candidate_seniority(opportunity)

    if "Partner & Executive Search" in practice_areas:
        return "Law firms"
    if practice_area == "Private Equity":
        return "Private equity-backed companies"
    if practice_area == "Technology & AI Law":
        return "Legal tech companies"
    if practice_area == "In-House Counsel" or seniority in {"General Counsel", "Chief Legal Officer"}:
        return "In-house legal departments"
    if practice_area in {"Energy & Infrastructure", "Construction Law"}:
        return "Infrastructure / energy companies with legal teams"
    return "Boutique legal practices"


def calculate_hiring_likelihood_score(opportunity):
    urgency = clamp_score(opportunity.get("urgency_score", 0))
    probability = clamp_score(float(opportunity.get("placement_probability", 0)) * 100)
    client_quality = clamp_score(opportunity.get("client_quality", 0))

    return round(urgency * 0.45 + probability * 0.35 + client_quality * 0.20, 2)


def estimate_client_fee_potential(opportunity, executive_search=None):
    executive_search = executive_search or {}
    executive_items = {
        item.get("opportunity_id"): item
        for item in executive_search.get("top_executive_opportunities", [])
    }
    executive_item = executive_items.get(opportunity.get("opportunity_id"), {})

    return round(float(
        executive_item.get("estimated_placement_fee")
        or opportunity.get("expected_fee_value", 0)
    ), 2)


def calculate_client_opportunity_score(opportunity, readiness_status, executive_search=None):
    fee_score = clamp_score((estimate_client_fee_potential(opportunity, executive_search) / 150000) * 100)
    hiring_score = calculate_hiring_likelihood_score(opportunity)
    practice_match = clamp_score(opportunity.get("candidate_quality", 0))
    readiness_score = 100 if readiness_status == "ready" else 35
    client_quality = clamp_score(opportunity.get("client_quality", 0))

    return round(
        fee_score * 0.30
        + hiring_score * 0.25
        + practice_match * 0.20
        + client_quality * 0.15
        + readiness_score * 0.10,
        2,
    )


def build_target_client_profiles(opportunities, compliance_core=None, executive_search=None):
    compliance_core = compliance_core or build_glirn_compliance_core(opportunities)
    executive_search = executive_search or build_executive_search_engine(opportunities, compliance_core=compliance_core)
    terms_by_client = {
        item.get("firm_id"): item
        for item in compliance_core.get("client_consent_terms_status", [])
    }
    consent_by_candidate = {
        item.get("candidate_id"): item
        for item in compliance_core.get("candidate_consent_ledger", [])
    }
    profiles = []

    for opportunity in opportunities:
        client = opportunity.get("client_firm", {}) or {}
        candidate = opportunity.get("candidate", {}) or {}
        terms = terms_by_client.get(client.get("firm_id"), {})
        consent = consent_by_candidate.get(candidate.get("candidate_id"), {})
        terms_recorded = terms.get("terms_status") == "recorded"
        consent_active = consent.get("consent_status") == "active"
        readiness_status = "ready" if terms_recorded else "terms_missing"
        fee_potential = estimate_client_fee_potential(opportunity, executive_search)
        hiring_likelihood = calculate_hiring_likelihood_score(opportunity)
        client_score = calculate_client_opportunity_score(opportunity, readiness_status, executive_search)

        profiles.append({
            "client_id": client.get("firm_id"),
            "client_name": client.get("name"),
            "target_client_type": classify_target_client_type(opportunity),
            "opportunity_id": opportunity.get("opportunity_id"),
            "hiring_likelihood_score": hiring_likelihood,
            "estimated_fee_potential": fee_potential,
            "preferred_practice_area_match": opportunity.get("practice_area"),
            "client_readiness_status": readiness_status,
            "client_terms_recorded": terms_recorded,
            "candidate_consent_active": consent_active,
            "outreach_approval_required": True,
            "outreach_blocked_without_approval": True,
            "fee_discussion_allowed": terms_recorded,
            "candidate_details_allowed": terms_recorded and consent_active,
            "client_opportunity_score": client_score,
            "awaiting_gareth_approval": True,
            "capital_execution": False,
            "autonomous_execution": False,
        })

    return profiles


def build_client_acquisition_engine(opportunities, compliance_core=None, executive_search=None):
    compliance_core = compliance_core or build_glirn_compliance_core(opportunities)
    executive_search = executive_search or build_executive_search_engine(opportunities, compliance_core=compliance_core)
    profiles = build_target_client_profiles(
        opportunities,
        compliance_core=compliance_core,
        executive_search=executive_search,
    )
    ranked = sorted(
        profiles,
        key=lambda item: (
            item.get("client_opportunity_score", 0),
            item.get("estimated_fee_potential", 0),
        ),
        reverse=True,
    )
    highest_fee_client = max(
        ranked,
        key=lambda item: item.get("estimated_fee_potential", 0),
    ) if ranked else None
    top = ranked[0] if ranked else None

    return {
        "status": "Client Acquisition Controls Active",
        "target_client_types": TARGET_CLIENT_TYPES,
        "target_client_profiles": ranked,
        "top_target_clients": ranked[:5],
        "highest_fee_potential_client": highest_fee_client,
        "outreach_approval_queue": [
            {
                "client_id": item.get("client_id"),
                "client_name": item.get("client_name"),
                "opportunity_id": item.get("opportunity_id"),
                "status": "awaiting_gareth_approval",
                "outreach_approval_required": True,
                "capital_execution": False,
            }
            for item in ranked
        ],
        "dave_recommends_first": {
            "recommendation": "Review top target client before any outreach.",
            "client_name": top.get("client_name") if top else None,
            "recommended_practice_area": top.get("preferred_practice_area_match") if top else None,
            "hiring_likelihood_score": top.get("hiring_likelihood_score") if top else 0,
            "estimated_fee_potential": top.get("estimated_fee_potential") if top else 0,
            "awaiting_gareth_approval": True,
            "capital_execution": False,
        },
        "awaiting_gareth_approval": True,
        "rules": [
            "No outreach without Gareth approval.",
            "No fee discussion without recorded client terms status.",
            "No candidate details shared without active candidate consent.",
            "Every client acquisition action is audit logged.",
            "Human approval remains mandatory.",
        ],
        "capital_execution": False,
        "autonomous_execution": False,
    }


def calculate_candidate_seniority_score(opportunity):
    seniority = classify_candidate_seniority(opportunity)
    scores = {
        "Chief Legal Officer": 100,
        "General Counsel": 94,
        "Partner": 92,
        "Senior Associate / Legal Director": 76,
        "Executive Legal Talent": 65,
    }
    return scores.get(seniority, 60)


def calculate_practice_area_match_score(opportunity):
    premium_areas = {
        "Partner & Executive Search": 100,
        "Private Equity": 94,
        "Corporate & M&A": 90,
        "Technology & AI Law": 86,
        "Banking & Finance": 84,
        "Energy & Infrastructure": 82,
        "Construction Law": 78,
        "Commercial Law": 74,
        "In-House Counsel": 80,
    }
    return premium_areas.get(opportunity.get("practice_area"), clamp_score(opportunity.get("candidate_quality", 0)))


def calculate_jurisdiction_match_score(opportunity):
    jurisdiction_scores = {
        "England & Wales": 94,
        "New York": 92,
        "United Arab Emirates": 88,
        "Singapore": 86,
    }
    return jurisdiction_scores.get(opportunity.get("jurisdiction"), 70)


def relocation_openness_flag(opportunity):
    jurisdiction = opportunity.get("jurisdiction")
    seniority = classify_candidate_seniority(opportunity)
    return jurisdiction in {"United Arab Emirates", "Singapore", "New York"} or seniority in {"General Counsel", "Chief Legal Officer"}


def estimate_candidate_placement_value(opportunity, executive_search=None):
    executive_search = executive_search or {}
    executive_items = {
        item.get("opportunity_id"): item
        for item in executive_search.get("top_executive_opportunities", [])
    }
    executive_item = executive_items.get(opportunity.get("opportunity_id"), {})

    return round(float(
        executive_item.get("estimated_placement_fee")
        or opportunity.get("expected_fee_value", 0)
    ), 2)


def calculate_candidate_priority_score(opportunity, consent_status="missing", executive_search=None):
    seniority_score = calculate_candidate_seniority_score(opportunity)
    practice_score = calculate_practice_area_match_score(opportunity)
    jurisdiction_score = calculate_jurisdiction_match_score(opportunity)
    value_score = clamp_score((estimate_candidate_placement_value(opportunity, executive_search) / 150000) * 100)
    consent_score = 100 if consent_status == "active" else 20
    relocation_bonus = 5 if relocation_openness_flag(opportunity) else 0

    return round(
        seniority_score * 0.25
        + practice_score * 0.20
        + jurisdiction_score * 0.15
        + value_score * 0.25
        + consent_score * 0.10
        + relocation_bonus,
        2,
    )


def build_candidate_discovery_engine(opportunities, compliance_core=None, executive_search=None):
    compliance_core = compliance_core or build_glirn_compliance_core(opportunities)
    executive_search = executive_search or build_executive_search_engine(opportunities, compliance_core=compliance_core)
    consent_by_candidate = {
        item.get("candidate_id"): item
        for item in compliance_core.get("candidate_consent_ledger", [])
    }
    candidate_items = []

    for opportunity in opportunities:
        candidate = opportunity.get("candidate", {}) or {}
        consent = consent_by_candidate.get(candidate.get("candidate_id"), {})
        consent_status = consent.get("consent_status", "missing")
        consent_active = consent_status == "active"
        seniority = classify_candidate_seniority(opportunity)
        estimated_value = estimate_candidate_placement_value(opportunity, executive_search)
        candidate_items.append({
            "candidate_id": candidate.get("candidate_id"),
            "candidate_name": candidate.get("full_name"),
            "opportunity_id": opportunity.get("opportunity_id"),
            "candidate_seniority_classification": seniority,
            "candidate_seniority_score": calculate_candidate_seniority_score(opportunity),
            "practice_area_match_score": calculate_practice_area_match_score(opportunity),
            "jurisdiction_match_score": calculate_jurisdiction_match_score(opportunity),
            "relocation_openness": relocation_openness_flag(opportunity),
            "consent_readiness_status": "active" if consent_active else consent_status,
            "profile_activation_allowed": consent_active,
            "candidate_details_allowed": consent_active,
            "executive_candidate": is_premium_executive_opportunity(seniority),
            "estimated_placement_value": estimated_value,
            "candidate_priority_score": calculate_candidate_priority_score(
                opportunity,
                consent_status=consent_status,
                executive_search=executive_search,
            ),
            "outreach_approval_required": True,
            "outreach_blocked_without_approval": True,
            "candidate_specific_intelligence_allowed": consent_active,
            "awaiting_gareth_approval": True,
            "capital_execution": False,
            "autonomous_execution": False,
        })

    ranked = sorted(
        candidate_items,
        key=lambda item: (
            item.get("candidate_priority_score", 0),
            item.get("estimated_placement_value", 0),
        ),
        reverse=True,
    )
    highest_value = max(
        ranked,
        key=lambda item: item.get("estimated_placement_value", 0),
    ) if ranked else None
    top = ranked[0] if ranked else None

    return {
        "status": "Candidate Discovery Controls Active",
        "target_candidate_types": TARGET_CANDIDATE_TYPES,
        "candidate_profiles": ranked,
        "top_candidate_opportunities": ranked[:5],
        "highest_estimated_placement_value": highest_value,
        "dave_recommends_first": {
            "recommendation": "Review top candidate before any outreach or profile activation.",
            "candidate_id": top.get("candidate_id") if top else None,
            "candidate_name": top.get("candidate_name") if top else None,
            "practice_area_match_score": top.get("practice_area_match_score") if top else 0,
            "awaiting_gareth_approval": True,
            "capital_execution": False,
        },
        "awaiting_gareth_approval": True,
        "rules": [
            "No candidate outreach without Gareth approval.",
            "No candidate profile activation without consent.",
            "No candidate details shared without active consent.",
            "Candidate-specific intelligence requires active consent.",
            "Every candidate discovery action is audit logged.",
            "Human approval remains mandatory.",
        ],
        "capital_execution": False,
        "autonomous_execution": False,
    }


def calculate_practice_area_compatibility(candidate_profile, client_profile):
    return 100 if (
        candidate_profile.get("opportunity_id") == client_profile.get("opportunity_id")
        or candidate_profile.get("practice_area_match_score", 0) >= 90
        and client_profile.get("preferred_practice_area_match")
    ) else clamp_score(candidate_profile.get("practice_area_match_score", 0))


def calculate_jurisdiction_compatibility(candidate_profile, client_profile):
    base_score = clamp_score(candidate_profile.get("jurisdiction_match_score", 0))
    relocation_bonus = 10 if candidate_profile.get("relocation_openness") else 0
    same_opportunity_bonus = 10 if candidate_profile.get("opportunity_id") == client_profile.get("opportunity_id") else 0
    return clamp_score(base_score + relocation_bonus + same_opportunity_bonus)


def calculate_seniority_compatibility(candidate_profile, client_profile):
    seniority_score = clamp_score(candidate_profile.get("candidate_seniority_score", 0))
    fee_score = clamp_score((float(client_profile.get("estimated_fee_potential", 0)) / 150000) * 100)
    return round(seniority_score * 0.65 + fee_score * 0.35, 2)


def calculate_salary_fee_compatibility(candidate_profile, client_profile):
    candidate_value = float(candidate_profile.get("estimated_placement_value", 0))
    client_potential = float(client_profile.get("estimated_fee_potential", 0))
    if not candidate_value or not client_potential:
        return 0
    ratio = min(candidate_value, client_potential) / max(candidate_value, client_potential)
    return round(clamp_score(ratio * 100), 2)


def calculate_relocation_compatibility(candidate_profile, client_profile):
    if candidate_profile.get("opportunity_id") == client_profile.get("opportunity_id"):
        return 100
    return 85 if candidate_profile.get("relocation_openness") else 60


def calculate_match_revenue_score(match):
    return round(
        clamp_score((float(match.get("estimated_fee_potential", 0)) / 150000) * 100) * 0.55
        + clamp_score(match.get("overall_compatibility_score", 0)) * 0.45,
        2,
    )


def calculate_placement_probability_score(match):
    gate_score = 100 if match.get("consent_and_terms_gate") == "passed" else 25
    return round(
        clamp_score(match.get("overall_compatibility_score", 0)) * 0.55
        + gate_score * 0.25
        + clamp_score(match.get("hiring_likelihood_score", 0)) * 0.20,
        2,
    )


def build_matching_engine(candidate_discovery_engine, client_acquisition_engine):
    candidate_profiles = candidate_discovery_engine.get("candidate_profiles", [])
    client_profiles = client_acquisition_engine.get("target_client_profiles", [])
    matches = []

    for candidate in candidate_profiles:
        for client in client_profiles:
            if candidate.get("opportunity_id") != client.get("opportunity_id"):
                continue

            practice_score = calculate_practice_area_compatibility(candidate, client)
            jurisdiction_score = calculate_jurisdiction_compatibility(candidate, client)
            seniority_score = calculate_seniority_compatibility(candidate, client)
            salary_score = calculate_salary_fee_compatibility(candidate, client)
            relocation_score = calculate_relocation_compatibility(candidate, client)
            consent_active = candidate.get("consent_readiness_status") == "active"
            terms_recorded = client.get("client_terms_recorded", False)
            gate_passed = consent_active and terms_recorded
            overall = round(
                practice_score * 0.25
                + jurisdiction_score * 0.15
                + seniority_score * 0.20
                + salary_score * 0.25
                + relocation_score * 0.15,
                2,
            )
            match = {
                "match_id": f"match-{candidate.get('candidate_id')}-{client.get('client_id')}",
                "candidate_id": candidate.get("candidate_id"),
                "candidate_name": candidate.get("candidate_name"),
                "client_id": client.get("client_id"),
                "client_name": client.get("client_name"),
                "opportunity_id": candidate.get("opportunity_id"),
                "practice_area_compatibility_score": practice_score,
                "jurisdiction_compatibility_score": jurisdiction_score,
                "seniority_compatibility_score": seniority_score,
                "salary_fee_compatibility_score": salary_score,
                "relocation_compatibility_score": relocation_score,
                "overall_compatibility_score": overall,
                "candidate_consent_status": candidate.get("consent_readiness_status"),
                "client_terms_status": "recorded" if terms_recorded else "missing",
                "consent_and_terms_gate": "passed" if gate_passed else "blocked",
                "match_active_allowed": gate_passed,
                "client_facing_allowed": terms_recorded,
                "candidate_details_share_allowed": False,
                "placement_action_requires_gareth_approval": True,
                "human_approval_required": True,
                "awaiting_gareth_approval": True,
                "estimated_fee_potential": client.get("estimated_fee_potential", 0),
                "hiring_likelihood_score": client.get("hiring_likelihood_score", 0),
                "blocked_reasons": [
                    reason
                    for reason, blocked in [
                        ("missing_or_inactive_candidate_consent", not consent_active),
                        ("missing_client_terms", not terms_recorded),
                    ]
                    if blocked
                ],
                "capital_execution": False,
                "autonomous_execution": False,
            }
            match["match_revenue_score"] = calculate_match_revenue_score(match)
            match["placement_probability_score"] = calculate_placement_probability_score(match)
            matches.append(match)

    ranked = sorted(
        matches,
        key=lambda item: (
            item.get("match_revenue_score", 0),
            item.get("placement_probability_score", 0),
        ),
        reverse=True,
    )
    highest_revenue = ranked[0] if ranked else None

    return {
        "status": "Matching & Placement Controls Active",
        "ranked_placement_matches": ranked,
        "top_ranked_placement_matches": ranked[:5],
        "highest_match_revenue_score": highest_revenue,
        "dave_recommends_first": {
            "recommendation": "Review the top ranked placement match before any client-facing action.",
            "match_id": highest_revenue.get("match_id") if highest_revenue else None,
            "placement_probability_score": highest_revenue.get("placement_probability_score") if highest_revenue else 0,
            "awaiting_gareth_approval": True,
            "capital_execution": False,
        },
        "awaiting_gareth_approval": True,
        "rules": [
            "No match can become active without active candidate consent.",
            "No match can be client-facing unless client terms are recorded.",
            "No candidate details can be shared without Gareth approval.",
            "No placement action can proceed without Gareth approval.",
            "Every match action is audit logged.",
            "Human approval remains mandatory.",
        ],
        "capital_execution": False,
        "autonomous_execution": False,
    }


def build_executive_autopilot(
    legal_opportunity_radar,
    executive_search,
    client_acquisition_engine,
    candidate_discovery_engine,
    matching_engine,
    commercial_revenue_engine,
    compliance_core,
):
    top_opportunity = (
        legal_opportunity_radar.get("top_opportunity")
        or legal_opportunity_radar.get("highest_value_opportunity")
        or {}
    )
    top_candidate = (
        (candidate_discovery_engine.get("top_candidate_opportunities") or [{}])[0]
        if candidate_discovery_engine.get("top_candidate_opportunities")
        else {}
    )
    top_client = (
        (client_acquisition_engine.get("top_target_clients") or [{}])[0]
        if client_acquisition_engine.get("top_target_clients")
        else {}
    )
    top_match = (
        (matching_engine.get("top_ranked_placement_matches") or [{}])[0]
        if matching_engine.get("top_ranked_placement_matches")
        else {}
    )
    highest_fee = commercial_revenue_engine.get("highest_fee_opportunity") or {}
    compliance_alerts = compliance_core.get("compliance_alerts", []) or []
    approval_queue = []

    if top_opportunity:
        approval_queue.append({
            "queue_type": "Opportunity Review",
            "target_id": top_opportunity.get("opportunity_id"),
            "title": top_opportunity.get("title"),
            "reason": "Top legal opportunity requires Gareth approval before outbound action.",
            "approval_required": True,
        })
    if top_candidate:
        approval_queue.append({
            "queue_type": "Candidate Review",
            "target_id": top_candidate.get("candidate_id"),
            "title": top_candidate.get("candidate_name"),
            "reason": "Top candidate requires Gareth approval before outreach or profile activation.",
            "approval_required": True,
        })
    if top_client:
        approval_queue.append({
            "queue_type": "Client Review",
            "target_id": top_client.get("client_id"),
            "title": top_client.get("client_name"),
            "reason": "Top client requires Gareth approval before outreach or engagement.",
            "approval_required": True,
        })
    if top_match:
        approval_queue.append({
            "queue_type": "Placement Match Review",
            "target_id": top_match.get("match_id"),
            "title": f"{top_match.get('candidate_name', 'Candidate')} to {top_match.get('client_name', 'Client')}",
            "reason": "Top placement match requires Gareth approval before any client-facing action.",
            "approval_required": True,
        })

    compliance_gate_clear = not compliance_alerts
    top_match_consent = top_match.get("candidate_consent_status") == "active"
    top_match_terms = top_match.get("client_terms_status") == "recorded"
    top_match_gate_clear = bool(top_match) and top_match_consent and top_match_terms

    highest_estimated_fee = max(
        float(top_opportunity.get("expected_fee_value", 0) or 0),
        float(highest_fee.get("estimated_revenue", 0) or 0),
        float(top_match.get("estimated_fee_potential", 0) or 0),
    )
    highest_placement_probability = max(
        float(top_opportunity.get("placement_probability", 0) or 0) * 100,
        float(top_match.get("placement_probability_score", 0) or 0),
    )

    ranking_inputs = [
        {
            "recommendation_type": "Top Opportunity",
            "title": top_opportunity.get("title", "No opportunity available"),
            "score": float(top_opportunity.get("radar_priority_score", top_opportunity.get("overall_glirn_score", 0)) or 0),
            "estimated_fee": float(top_opportunity.get("expected_fee_value", 0) or 0),
            "approval_required": True,
        },
        {
            "recommendation_type": "Top Candidate",
            "title": top_candidate.get("candidate_name", "No candidate available"),
            "score": float(top_candidate.get("candidate_priority_score", 0) or 0),
            "estimated_fee": float(top_candidate.get("estimated_placement_value", 0) or 0),
            "approval_required": True,
        },
        {
            "recommendation_type": "Top Client",
            "title": top_client.get("client_name", "No client available"),
            "score": float(top_client.get("client_opportunity_score", top_client.get("hiring_likelihood_score", 0)) or 0),
            "estimated_fee": float(top_client.get("estimated_fee_potential", 0) or 0),
            "approval_required": True,
        },
        {
            "recommendation_type": "Top Placement Match",
            "title": f"{top_match.get('candidate_name', 'Candidate')} to {top_match.get('client_name', 'Client')}",
            "score": float(top_match.get("match_revenue_score", 0) or 0),
            "estimated_fee": float(top_match.get("estimated_fee_potential", 0) or 0),
            "approval_required": True,
        },
    ]
    ranked_recommendations = sorted(
        ranking_inputs,
        key=lambda item: (
            item.get("score", 0),
            item.get("estimated_fee", 0),
        ),
        reverse=True,
    )
    dave_first = ranked_recommendations[0] if ranked_recommendations else {}

    if not top_match_gate_clear:
        dave_recommendation = "Resolve consent and client terms gates before any placement action."
    elif not compliance_gate_clear:
        dave_recommendation = "Review compliance alerts before approving any GLIRN action."
    else:
        dave_recommendation = "Review the highest-ranked GLIRN placement route and approve only if evidence is complete."

    return {
        "engine": "executive_autopilot",
        "status": "Executive Autopilot Waiting for Gareth Approval",
        "top_opportunity": top_opportunity,
        "top_candidate": top_candidate,
        "top_client": top_client,
        "top_placement_match": top_match,
        "highest_estimated_fee": highest_estimated_fee,
        "highest_placement_probability": round(highest_placement_probability, 2),
        "compliance_alerts": compliance_alerts,
        "compliance_gate_clear": compliance_gate_clear,
        "top_match_gate_clear": top_match_gate_clear,
        "gareth_approval_queue": approval_queue,
        "approval_queue_count": len(approval_queue),
        "ranked_recommendations": ranked_recommendations,
        "dave_recommends_first": {
            "recommendation": dave_recommendation,
            "recommended_focus": dave_first.get("recommendation_type", "Review"),
            "title": dave_first.get("title", "No recommendation available"),
            "approval_required": True,
        },
        "no_autonomous_outreach": True,
        "no_autonomous_candidate_introduction": True,
        "no_autonomous_client_engagement": True,
        "no_autonomous_fee_proposal": True,
        "human_approval_mandatory": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def get_live_data_source_registry():
    return [
        {
            "source_id": "source-candidate-csv-import",
            "source_name": "Human-approved candidate CSV import",
            "source_type": "manual_csv",
            "jurisdiction": "England & Wales",
            "contains_personal_data": True,
            "requires_candidate_consent": True,
            "requires_client_terms": False,
            "lawful_basis_required": True,
            "lawful_basis_status": "clear",
            "human_approval_required": True,
            "status": "proposed",
            "risk_level": "medium",
            "notes": "Future manual import only. No live ingestion is enabled.",
        },
        {
            "source_id": "source-client-terms-register",
            "source_name": "Client terms readiness register",
            "source_type": "manual_register",
            "jurisdiction": "Global",
            "contains_personal_data": False,
            "requires_candidate_consent": False,
            "requires_client_terms": True,
            "lawful_basis_required": False,
            "lawful_basis_status": "not_required",
            "human_approval_required": True,
            "status": "approved",
            "risk_level": "low",
            "notes": "Manual client terms status only. No external service connection.",
        },
        {
            "source_id": "source-public-law-firm-directory",
            "source_name": "Public law firm directory reference",
            "source_type": "manual_reference",
            "jurisdiction": "Global",
            "contains_personal_data": False,
            "requires_candidate_consent": False,
            "requires_client_terms": False,
            "lawful_basis_required": True,
            "lawful_basis_status": "unclear",
            "human_approval_required": True,
            "status": "proposed",
            "risk_level": "medium",
            "notes": "Future human-reviewed reference source. Lawful basis must be clarified before use.",
        },
        {
            "source_id": "source-scraped-candidate-profiles",
            "source_name": "Scraped candidate profile feed",
            "source_type": "scraped_feed",
            "jurisdiction": "Global",
            "contains_personal_data": True,
            "requires_candidate_consent": True,
            "requires_client_terms": False,
            "lawful_basis_required": True,
            "lawful_basis_status": "unclear",
            "human_approval_required": True,
            "status": "blocked",
            "risk_level": "high",
            "notes": "Blocked by default. GLIRN does not scrape or ingest candidate data.",
        },
    ]


def calculate_source_readiness(source):
    risk_level = source.get("risk_level", "medium")
    status = source.get("status", "proposed")
    lawful_basis_status = source.get("lawful_basis_status", "unclear")
    contains_personal_data = source.get("contains_personal_data", False)
    requires_candidate_consent = source.get("requires_candidate_consent", False)
    requires_client_terms = source.get("requires_client_terms", False)

    consent_ready = not contains_personal_data or requires_candidate_consent
    terms_ready = not requires_client_terms or status == "approved"
    approval_ready = status == "approved"
    lawful_basis_ready = not source.get("lawful_basis_required", False) or lawful_basis_status in {"clear", "not_required"}

    score = 100
    if risk_level == "high":
        score -= 70
    elif risk_level == "medium":
        score -= 20
    if not consent_ready:
        score -= 45
    if not terms_ready:
        score -= 20
    if not approval_ready:
        score -= 25
    if not lawful_basis_ready:
        score -= 50
    if status in {"blocked", "inactive"}:
        score = 0

    if risk_level == "high":
        readiness_status = "blocked_high_risk_default"
    elif status == "blocked":
        readiness_status = "blocked"
    elif status == "inactive":
        readiness_status = "inactive"
    elif not lawful_basis_ready:
        readiness_status = "not_ready_lawful_basis_unclear"
    elif not consent_ready:
        readiness_status = "not_ready_consent_controls_required"
    elif not approval_ready:
        readiness_status = "pending_gareth_approval"
    elif score >= 80:
        readiness_status = "ready_for_human_approved_integration"
    else:
        readiness_status = "not_ready"

    return {
        **source,
        "compliance_readiness_score": clamp_score(score),
        "consent_readiness": "ready" if consent_ready else "not_ready",
        "terms_readiness": "ready" if terms_ready else "not_ready",
        "approval_readiness": "approved" if approval_ready else "requires_gareth_approval",
        "lawful_basis_readiness": "ready" if lawful_basis_ready else "unclear",
        "ingestion_readiness_status": readiness_status,
        "blocked_by_default": risk_level == "high",
        "external_connection_enabled": False,
        "scraping_enabled": False,
        "live_fetching_enabled": False,
        "ingestion_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def build_live_data_readiness(source_registry=None):
    raw_sources = source_registry or get_live_data_source_registry()
    sources = [calculate_source_readiness(source) for source in raw_sources]
    blocked_sources = [
        source for source in sources
        if source.get("risk_level") == "high"
        or source.get("status") == "blocked"
        or str(source.get("ingestion_readiness_status", "")).startswith("blocked")
    ]
    approved_sources = [
        source for source in sources
        if source.get("status") == "approved"
    ]
    pending_sources = [
        source for source in sources
        if source.get("status") == "proposed"
    ]
    not_ready_sources = [
        source for source in sources
        if "not_ready" in source.get("ingestion_readiness_status", "")
        or source.get("approval_readiness") == "requires_gareth_approval"
    ]

    if blocked_sources:
        recommendation = "Keep high-risk or unclear sources blocked until Gareth reviews compliance evidence."
    elif pending_sources:
        recommendation = "Review proposed sources before approving any future data integration."
    else:
        recommendation = "Maintain human approval and audit controls before any source is used."

    return {
        "engine": "live_data_readiness",
        "status": "Live Data Readiness Controls Active",
        "source_registry": sources,
        "source_readiness_summary": {
            "total_sources": len(sources),
            "approved_sources": len(approved_sources),
            "pending_sources": len(pending_sources),
            "blocked_sources": len(blocked_sources),
            "not_ready_sources": len(not_ready_sources),
            "external_connections_enabled": False,
            "scraping_enabled": False,
            "live_fetching_enabled": False,
            "ingestion_enabled": False,
        },
        "blocked_sources": blocked_sources,
        "approved_sources": approved_sources,
        "pending_sources": pending_sources,
        "dave_recommends_first": {
            "recommendation": recommendation,
            "human_approval_required": True,
            "capital_execution": False,
        },
        "rules": [
            "No source can become active without Gareth approval.",
            "High-risk sources are blocked by default.",
            "Sources containing candidate personal data must require consent controls.",
            "Sources with unclear lawful basis are not ready.",
            "Every source decision is audit logged.",
            "No scraping, live fetching, or candidate data ingestion is enabled.",
        ],
        "human_approval_required": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def get_integration_registry():
    return [
        {
            "integration_id": "integration-manual-csv-upload",
            "integration_name": "Manual CSV Upload",
            "integration_type": "manual_import",
            "jurisdiction": "England & Wales",
            "risk_level": "medium",
            "contains_personal_data": True,
            "requires_candidate_consent": True,
            "requires_client_terms": False,
            "lawful_basis_required": True,
            "lawful_basis_status": "clear",
            "human_approval_required": True,
            "status": "pending",
        },
        {
            "integration_id": "integration-client-terms-register",
            "integration_name": "Client Terms Register",
            "integration_type": "manual_register",
            "jurisdiction": "Global",
            "risk_level": "low",
            "contains_personal_data": False,
            "requires_candidate_consent": False,
            "requires_client_terms": True,
            "lawful_basis_required": False,
            "lawful_basis_status": "not_required",
            "human_approval_required": True,
            "status": "approved",
        },
        {
            "integration_id": "integration-email-outbound",
            "integration_name": "Outbound Email Connector",
            "integration_type": "email_connector",
            "jurisdiction": "Global",
            "risk_level": "high",
            "contains_personal_data": True,
            "requires_candidate_consent": True,
            "requires_client_terms": True,
            "lawful_basis_required": True,
            "lawful_basis_status": "unclear",
            "human_approval_required": True,
            "status": "blocked",
        },
    ]


def calculate_integration_governance(integration):
    risk_level = integration.get("risk_level", "medium")
    status = integration.get("status", "pending")
    lawful_basis_required = integration.get("lawful_basis_required", False)
    lawful_basis_status = integration.get("lawful_basis_status", "unclear")
    contains_personal_data = integration.get("contains_personal_data", False)
    requires_candidate_consent = integration.get("requires_candidate_consent", False)
    requires_client_terms = integration.get("requires_client_terms", False)

    lawful_basis_ready = not lawful_basis_required or lawful_basis_status in {"clear", "not_required"}
    consent_controls_ready = not contains_personal_data or requires_candidate_consent
    terms_controls_ready = not requires_client_terms or status == "approved"
    approval_ready = status == "approved"

    compliance_score = 100
    if not lawful_basis_ready:
        compliance_score -= 45
    if not consent_controls_ready:
        compliance_score -= 35
    if not terms_controls_ready:
        compliance_score -= 20

    approval_score = 100 if approval_ready else 35
    risk_score = {"low": 85, "medium": 55, "high": 10}.get(risk_level, 40)
    readiness_score = round(
        clamp_score(compliance_score) * 0.45
        + approval_score * 0.25
        + risk_score * 0.30,
        2,
    )

    if risk_level == "high":
        governance_status = "blocked_high_risk_default"
        readiness_score = min(readiness_score, 25)
    elif status == "blocked":
        governance_status = "blocked"
        readiness_score = 0
    elif status == "suspended":
        governance_status = "suspended"
        readiness_score = 0
    elif not lawful_basis_ready:
        governance_status = "not_ready_lawful_basis_unclear"
    elif not consent_controls_ready:
        governance_status = "not_ready_consent_controls_required"
    elif not approval_ready:
        governance_status = "pending_gareth_approval"
    else:
        governance_status = "approved_for_human_controlled_future_use"

    return {
        **integration,
        "compliance_score": clamp_score(compliance_score),
        "approval_score": approval_score,
        "readiness_score": clamp_score(readiness_score),
        "risk_score": risk_score,
        "governance_status": governance_status,
        "blocked_by_default": risk_level == "high",
        "external_connection_enabled": False,
        "scraping_enabled": False,
        "outbound_connection_enabled": False,
        "autonomous_activation_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def build_integration_governance(integration_registry=None):
    raw_integrations = integration_registry or get_integration_registry()
    integrations = [
        calculate_integration_governance(integration)
        for integration in raw_integrations
    ]
    approved = [
        integration for integration in integrations
        if integration.get("status") == "approved"
    ]
    blocked = [
        integration for integration in integrations
        if integration.get("risk_level") == "high"
        or integration.get("status") in {"blocked", "suspended"}
        or str(integration.get("governance_status", "")).startswith("blocked")
    ]
    pending = [
        integration for integration in integrations
        if integration.get("status") == "pending"
    ]
    alerts = []
    for integration in integrations:
        if integration.get("blocked_by_default"):
            alerts.append({
                "integration_id": integration.get("integration_id"),
                "alert_type": "high_risk_blocked_by_default",
                "message": "High-risk integration is blocked unless Gareth reviews and explicitly approves future governance.",
            })
        if integration.get("contains_personal_data") and not integration.get("requires_candidate_consent"):
            alerts.append({
                "integration_id": integration.get("integration_id"),
                "alert_type": "missing_candidate_consent_controls",
                "message": "Personal-data integration must require candidate consent controls.",
            })

    return {
        "engine": "integration_governance",
        "status": "Integration Governance Controls Active",
        "integration_registry": integrations,
        "approved_integrations": approved,
        "blocked_integrations": blocked,
        "pending_integrations": pending,
        "governance_alerts": alerts,
        "dave_recommends_first": {
            "recommendation": "Keep all future integrations inactive until Gareth approves governance, consent, terms, and lawful basis.",
            "human_approval_required": True,
            "capital_execution": False,
        },
        "human_approval_required": True,
        "external_connections_enabled": False,
        "scraping_enabled": False,
        "outbound_connections_enabled": False,
        "autonomous_activation_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def grade_readiness(percentage):
    if percentage >= 90:
        return "A"
    if percentage >= 75:
        return "B"
    if percentage >= 60:
        return "C"
    if percentage >= 40:
        return "D"
    return "F"


def build_deployment_readiness(
    compliance_core,
    approval_centre,
    commercial_revenue_engine,
    live_data_readiness,
    integration_governance,
    executive_autopilot,
):
    compliance_summary = live_data_readiness.get("source_readiness_summary", {}) or {}
    integration_alerts = integration_governance.get("governance_alerts", []) or []
    compliance_alerts = compliance_core.get("compliance_alerts", []) or []
    blocked_sources = live_data_readiness.get("blocked_sources", []) or []
    blocked_integrations = integration_governance.get("blocked_integrations", []) or []

    technical_readiness = 90
    compliance_readiness = clamp_score(float(compliance_core.get("compliance_readiness_score", 0)))
    if compliance_alerts:
        compliance_readiness = clamp_score(compliance_readiness - 20)
    commercial_readiness = 75 if commercial_revenue_engine.get("highest_fee_opportunity") else 45
    operational_readiness = 80 if approval_centre.get("locks", {}).get("outbound_action_locked", True) else 40
    documentation_readiness = 85
    integration_readiness = 70
    if blocked_sources:
        integration_readiness -= 15
    if blocked_integrations:
        integration_readiness -= 15
    if integration_alerts:
        integration_readiness -= 10
    integration_readiness = clamp_score(integration_readiness)

    readiness_percentage = round(
        technical_readiness * 0.18
        + compliance_readiness * 0.22
        + commercial_readiness * 0.16
        + operational_readiness * 0.16
        + documentation_readiness * 0.12
        + integration_readiness * 0.16,
        2,
    )
    critical_gaps = []
    if compliance_alerts:
        critical_gaps.append("Resolve compliance alerts before real-world operation.")
    if blocked_sources:
        critical_gaps.append("Keep blocked live data sources inactive until Gareth approves evidence.")
    if blocked_integrations:
        critical_gaps.append("Keep high-risk integrations blocked before launch.")
    if approval_centre.get("pending_count", 0) > 0:
        critical_gaps.append("Review Gareth approval queue before operational use.")
    if not integration_governance.get("external_connections_enabled") is False:
        critical_gaps.append("Confirm external connections remain disabled.")

    if not critical_gaps:
        critical_gaps.append("Complete final human approval review before any real-world deployment.")

    recommended_actions = [
        "Review all compliance, source, and integration gates.",
        "Confirm backups and documentation are current.",
        "Run smoke tests before any deployment decision.",
        "Keep all deployment actions manual and Gareth-approved.",
    ]

    launch_checklist = [
        {
            "item": "platform status",
            "status": "ready",
            "detail": "Core GLIRN dashboard and engines are available.",
        },
        {
            "item": "documentation status",
            "status": "ready",
            "detail": "Release and architecture documentation exists.",
        },
        {
            "item": "backup status",
            "status": "manual_review_required",
            "detail": "Backups must be confirmed before any real-world operation.",
        },
        {
            "item": "compliance status",
            "status": "review_required" if compliance_alerts else "controlled",
            "detail": "Consent, terms, retention, and lawful-basis controls must remain active.",
        },
        {
            "item": "approval workflows",
            "status": "active",
            "detail": "Gareth approval remains mandatory.",
        },
        {
            "item": "audit status",
            "status": "active",
            "detail": "Approval and governance actions are audit logged.",
        },
    ]

    return {
        "engine": "deployment_readiness",
        "status": "Deployment Readiness Assessment Active",
        "technical_readiness": technical_readiness,
        "compliance_readiness": compliance_readiness,
        "commercial_readiness": commercial_readiness,
        "operational_readiness": operational_readiness,
        "documentation_readiness": documentation_readiness,
        "integration_readiness": integration_readiness,
        "readiness_percentage": readiness_percentage,
        "readiness_score": readiness_percentage,
        "readiness_grade": grade_readiness(readiness_percentage),
        "critical_gaps": critical_gaps,
        "recommended_actions": recommended_actions,
        "launch_checklist": launch_checklist,
        "dave_recommends_first": {
            "recommendation": "Do not deploy externally until Gareth reviews critical gaps, backups, compliance evidence, and integration governance.",
            "human_approval_required": True,
            "capital_execution": False,
        },
        "deployment_actions_enabled": False,
        "external_connections_enabled": False,
        "assessment_only": True,
        "human_approval_mandatory": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def build_operations_command_centre(
    executive_autopilot,
    legal_opportunity_radar,
    client_acquisition_engine,
    candidate_discovery_engine,
    matching_engine,
    commercial_revenue_engine,
    compliance_core,
    deployment_readiness,
    approval_centre,
):
    opportunities = legal_opportunity_radar.get("opportunities_ranked", []) or []
    candidates = candidate_discovery_engine.get("candidate_profiles", []) or []
    clients = client_acquisition_engine.get("target_client_profiles", []) or []
    matches = matching_engine.get("ranked_placement_matches", []) or []
    compliance_alerts = compliance_core.get("compliance_alerts", []) or []
    pending_approvals = (
        approval_centre.get("pending_count", 0)
        + executive_autopilot.get("approval_queue_count", 0)
    )
    estimated_revenue_pipeline = commercial_revenue_engine.get("estimated_revenue_pipeline", 0)
    readiness_score = deployment_readiness.get("readiness_score", 0)

    key_metrics = {
        "total_opportunities": len(opportunities),
        "total_candidates": len(candidates),
        "total_clients": len(clients),
        "total_matches": len(matches),
        "estimated_revenue_pipeline": estimated_revenue_pipeline,
        "compliance_alerts": len(compliance_alerts),
        "pending_gareth_approvals": pending_approvals,
        "readiness_score": readiness_score,
    }
    platform_health = {
        "executive_autopilot": executive_autopilot.get("status"),
        "opportunity_radar": legal_opportunity_radar.get("status", "Legal Opportunity Radar Active"),
        "client_acquisition": client_acquisition_engine.get("status"),
        "candidate_discovery": candidate_discovery_engine.get("status"),
        "matching_engine": matching_engine.get("status"),
        "commercial_revenue_engine": commercial_revenue_engine.get("status"),
        "compliance_core": compliance_core.get("status"),
        "deployment_readiness": deployment_readiness.get("status"),
        "read_only": True,
        "external_connections_enabled": False,
        "automation_changes_enabled": False,
        "outreach_enabled": False,
        "deployment_actions_enabled": False,
    }
    executive_summary = {
        "top_opportunity": executive_autopilot.get("top_opportunity"),
        "top_candidate": executive_autopilot.get("top_candidate"),
        "top_client": executive_autopilot.get("top_client"),
        "top_placement_match": executive_autopilot.get("top_placement_match"),
        "highest_estimated_fee": executive_autopilot.get("highest_estimated_fee", 0),
        "highest_placement_probability": executive_autopilot.get("highest_placement_probability", 0),
    }

    if compliance_alerts:
        recommendation = "Review compliance alerts before any operational action."
    elif pending_approvals:
        recommendation = "Work through Gareth approval queue before client or candidate action."
    else:
        recommendation = "Monitor GLIRN readiness and keep all operational activity human-approved."

    return {
        "engine": "operations_command_centre",
        "status": "Operations Command Centre Active",
        "executive_summary": executive_summary,
        "key_metrics": key_metrics,
        "platform_health": platform_health,
        "dave_recommends_first": {
            "recommendation": recommendation,
            "human_approval_required": True,
            "capital_execution": False,
        },
        "read_only": True,
        "automation_changes_enabled": False,
        "external_connections_enabled": False,
        "outreach_enabled": False,
        "deployment_actions_enabled": False,
        "human_approval_mandatory": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def build_daily_executive_briefing(
    operations_command_centre,
    legal_opportunity_radar,
    commercial_revenue_engine,
    compliance_core,
    deployment_readiness,
    executive_autopilot,
):
    top_opportunities = (legal_opportunity_radar.get("opportunities_ranked", []) or [])[:3]
    compliance_warnings = compliance_core.get("compliance_alerts", []) or []
    deployment_gaps = deployment_readiness.get("critical_gaps", []) or []
    top_risks = []
    for warning in compliance_warnings[:3]:
        top_risks.append({
            "risk_type": warning.get("alert_type", "compliance_warning"),
            "description": warning.get("message", "Compliance warning requires review."),
        })
    for gap in deployment_gaps:
        if len(top_risks) >= 3:
            break
        top_risks.append({
            "risk_type": "deployment_readiness_gap",
            "description": gap,
        })
    if not top_risks:
        top_risks.append({
            "risk_type": "human_approval_required",
            "description": "Maintain Gareth approval before any client, candidate, fee, or deployment action.",
        })

    pipeline = commercial_revenue_engine.get("commercial_pipeline", []) or []
    top_revenue_actions = [
        {
            "opportunity_id": item.get("opportunity_id"),
            "title": item.get("title"),
            "fee_type": item.get("fee_type"),
            "estimated_revenue": item.get("estimated_revenue", 0),
            "recommended_action": "Review fee opportunity with Gareth approval.",
        }
        for item in pipeline[:3]
    ]
    if not top_revenue_actions and commercial_revenue_engine.get("highest_fee_opportunity"):
        highest = commercial_revenue_engine.get("highest_fee_opportunity") or {}
        top_revenue_actions.append({
            "opportunity_id": highest.get("opportunity_id"),
            "title": highest.get("title"),
            "fee_type": highest.get("fee_type"),
            "estimated_revenue": highest.get("estimated_revenue", 0),
            "recommended_action": "Review highest fee opportunity.",
        })

    pending_approvals = executive_autopilot.get("gareth_approval_queue", []) or []
    if top_risks and top_risks[0].get("risk_type") != "human_approval_required":
        recommendation = "Review today's risks before any revenue or placement action."
    elif pending_approvals:
        recommendation = "Clear the highest-priority Gareth approval items before client or candidate action."
    else:
        recommendation = "Review top opportunities and keep all activity human-approved."

    return {
        "engine": "daily_executive_briefing",
        "status": "Daily Executive Briefing Ready",
        "top_3_opportunities": top_opportunities,
        "top_3_risks": top_risks[:3],
        "top_3_revenue_actions": top_revenue_actions[:3],
        "pending_gareth_approvals": pending_approvals,
        "compliance_warnings": compliance_warnings,
        "dave_recommends_today": {
            "recommendation": recommendation,
            "human_approval_required": True,
            "capital_execution": False,
        },
        "operations_snapshot": operations_command_centre.get("key_metrics", {}),
        "read_only": True,
        "automation_changes_enabled": False,
        "external_connections_enabled": False,
        "outreach_enabled": False,
        "deployment_actions_enabled": False,
        "human_approval_mandatory": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def build_intelligence_review_engine(
    intelligence_network,
    client_acquisition_engine,
    candidate_discovery_engine,
    matching_engine,
    commercial_revenue_engine,
    compliance_core,
    executive_autopilot,
):
    top_client = (
        (client_acquisition_engine.get("top_target_clients") or [{}])[0]
        if client_acquisition_engine.get("top_target_clients")
        else {}
    )
    top_candidate = (
        (candidate_discovery_engine.get("top_candidate_opportunities") or [{}])[0]
        if candidate_discovery_engine.get("top_candidate_opportunities")
        else {}
    )
    top_match = (
        (matching_engine.get("top_ranked_placement_matches") or [{}])[0]
        if matching_engine.get("top_ranked_placement_matches")
        else {}
    )
    highest_fee = commercial_revenue_engine.get("highest_fee_opportunity") or {}
    hot_area = (
        (intelligence_network.get("hot_practice_areas") or [{}])[0]
        if intelligence_network.get("hot_practice_areas")
        else {}
    )
    jurisdiction_signal = (
        (intelligence_network.get("growing_jurisdictions") or [{}])[0]
        if intelligence_network.get("growing_jurisdictions")
        else {}
    )
    compliance_alerts = compliance_core.get("compliance_alerts", []) or []
    consent_active = top_candidate.get("consent_readiness_status") == "active"
    candidate_profile_specification = {
        "seniority": top_candidate.get("candidate_seniority_classification", "Senior legal candidate"),
        "practice_area": hot_area.get("practice_area") or top_client.get("preferred_practice_area_match", "Legal practice area"),
        "jurisdiction": jurisdiction_signal.get("jurisdiction", "England & Wales"),
        "candidate_personal_data_included": consent_active,
        "candidate_name": top_candidate.get("candidate_name") if consent_active else None,
        "candidate_personal_data_status": "included_with_active_consent" if consent_active else "blocked_without_active_consent",
    }
    recommended_action = "start search" if (
        top_match.get("consent_and_terms_gate") == "passed"
        and not compliance_alerts
    ) else "monitor"
    if compliance_alerts:
        recommended_action = "defer"
    if not top_client:
        recommended_action = "reject"

    review = {
        "review_id": "glirn-review-001",
        "title": f"GLIRN Senior Legal Hiring Intelligence Review - {top_client.get('client_name', 'Target Client')}",
        "target_client_profile": top_client.get("client_name", "Target client profile"),
        "practice_area": hot_area.get("practice_area") or top_client.get("preferred_practice_area_match", "Technology & AI Law"),
        "jurisdiction": jurisdiction_signal.get("jurisdiction", "England & Wales"),
        "approval_status": "pending_gareth_approval",
        "client_ready": False,
        "client_delivery_allowed": False,
        "compliance_status": "review_required" if compliance_alerts else "controlled",
        "candidate_personal_data_included": consent_active,
        "candidate_personal_data_blocked": not consent_active,
        "recommended_action": recommended_action,
        "sections": {
            "Executive Summary": "GLIRN has generated a draft senior legal hiring intelligence review for human approval.",
            "Client Context": f"Target client profile: {top_client.get('client_name', 'Target client profile')}. Client type: {top_client.get('target_client_type', 'legal employer')}.",
            "Practice Area Focus": f"Primary practice area focus: {hot_area.get('practice_area') or top_client.get('preferred_practice_area_match', 'Technology & AI Law')}.",
            "Jurisdiction Focus": f"Primary jurisdiction focus: {jurisdiction_signal.get('jurisdiction', 'England & Wales')}.",
            "Market Signal Summary": intelligence_network.get("client_intelligence_hook", "Use legal intelligence as the client hook before recruitment placement."),
            "Hiring Difficulty Assessment": f"Placement probability score: {top_match.get('placement_probability_score', 0)}. Hiring likelihood: {top_client.get('hiring_likelihood_score', 0)}.",
            "Recommended Priority Role": executive_autopilot.get("top_opportunity", {}).get("title", "Senior legal hiring priority"),
            "Candidate Profile Specification": candidate_profile_specification,
            "Indicative Fee Model": f"Estimated fee or revenue opportunity: GBP {highest_fee.get('estimated_revenue', highest_fee.get('expected_fee_value', 0))}. Fee type: {highest_fee.get('fee_type', 'placement or retained search fee')}.",
            "Compliance Summary": "Candidate details require active consent. Client-facing delivery and fee proposals require Gareth approval.",
        },
        "source_modules": [
            "Legal Intelligence Network",
            "Client Acquisition Engine",
            "Candidate Discovery Engine",
            "Matching Engine",
            "Commercial Revenue Engine",
            "Compliance Core",
            "Executive Autopilot",
        ],
        "approval_required_before_client_ready": True,
        "human_approval_mandatory": True,
        "external_delivery_enabled": False,
        "automation_changes_enabled": False,
        "outreach_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    }
    review["human_review_framework"] = build_initial_human_review_framework(
        review,
        ai_confidence=top_match.get("placement_probability_score", 0),
        speculative_content=False,
        evidence_sufficient=bool(review["source_modules"] and top_client),
    )

    return {
        "engine": "intelligence_review_engine",
        "status": "Automated Intelligence Review Draft Ready",
        "review_generation_status": "generated_pending_gareth_approval",
        "generated_reviews": [review],
        "pending_review_approvals": [
            {
                "review_id": review["review_id"],
                "title": review["title"],
                "approval_status": review["approval_status"],
                "recommended_action": review["recommended_action"],
                "approval_required": True,
            }
        ],
        "latest_generated_review": review,
        "dave_recommends_first": {
            "recommendation": "Review the generated intelligence draft before any client-facing use.",
            "review_id": review["review_id"],
            "human_approval_required": True,
            "capital_execution": False,
        },
        "client_delivery_enabled": False,
        "human_approval_mandatory": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def build_client_deliverable_factory(
    executive_autopilot,
    intelligence_review_engine,
    client_acquisition_engine,
    candidate_discovery_engine,
    matching_engine,
    commercial_revenue_engine,
    compliance_core,
):
    top_client = (
        (client_acquisition_engine.get("top_target_clients") or [{}])[0]
        if client_acquisition_engine.get("top_target_clients")
        else {}
    )
    top_candidate = (
        (candidate_discovery_engine.get("top_candidate_opportunities") or [{}])[0]
        if candidate_discovery_engine.get("top_candidate_opportunities")
        else {}
    )
    top_match = (
        (matching_engine.get("top_ranked_placement_matches") or [{}])[0]
        if matching_engine.get("top_ranked_placement_matches")
        else {}
    )
    highest_fee = commercial_revenue_engine.get("highest_fee_opportunity") or {}
    latest_review = intelligence_review_engine.get("latest_generated_review") or {}
    compliance_alerts = compliance_core.get("compliance_alerts", []) or []
    consent_active = top_candidate.get("consent_readiness_status") == "active"
    compliance_status = "review_required" if compliance_alerts else "controlled"
    target_client = top_client.get("client_name", latest_review.get("target_client_profile", "Target Client"))
    practice_area = latest_review.get("practice_area") or top_client.get("preferred_practice_area_match", "Technology & AI Law")
    jurisdiction = latest_review.get("jurisdiction", "England & Wales")
    estimated_fee = highest_fee.get("estimated_revenue", top_match.get("estimated_fee_potential", 0))

    anonymised_candidate = {
        "profile_id": top_candidate.get("candidate_id", "candidate-profile").replace("candidate", "profile"),
        "seniority": top_candidate.get("candidate_seniority_classification", "Senior legal candidate"),
        "practice_area": practice_area,
        "jurisdiction": jurisdiction,
        "candidate_personal_data_included": False,
        "candidate_personal_data_status": "anonymised_only",
    }
    if consent_active:
        anonymised_candidate["consent_status"] = "active"
    else:
        anonymised_candidate["consent_status"] = "missing_or_inactive"

    deliverables = [
        {
            "deliverable_id": "glirn-deliverable-search-mandate-001",
            "deliverable_type": "Search Mandate Proposal",
            "title": f"Search Mandate Proposal - {target_client}",
            "target_client_profile": target_client,
            "approval_status": "pending_gareth_approval",
            "client_ready": False,
            "client_delivery_allowed": False,
            "compliance_status": compliance_status,
            "recommended_action": "review",
            "sections": {
                "client_context": latest_review.get("sections", {}).get("Client Context", f"Target client: {target_client}."),
                "hiring_objective": f"Assess whether {target_client} should begin a senior legal search in {practice_area}.",
                "role_summary": executive_autopilot.get("top_opportunity", {}).get("title", "Senior legal role"),
                "jurisdiction": jurisdiction,
                "proposed_search_approach": "Human-led, consent-aware senior legal search with Gareth approval before client-facing action.",
                "fee_model": f"Indicative fee model based on estimated value GBP {estimated_fee}.",
                "recommended_next_steps": "Gareth to approve whether this search mandate proposal can be discussed with the client.",
            },
        },
        {
            "deliverable_id": "glirn-deliverable-executive-search-001",
            "deliverable_type": "Executive Search Proposal",
            "title": f"Executive Search Proposal - {target_client}",
            "target_client_profile": target_client,
            "approval_status": "pending_gareth_approval",
            "client_ready": False,
            "client_delivery_allowed": False,
            "compliance_status": compliance_status,
            "recommended_action": "review",
            "sections": {
                "executive_role_summary": executive_autopilot.get("top_opportunity", {}).get("title", "Executive legal role"),
                "search_rationale": "Senior legal leadership may create commercial and operational value for the target client.",
                "market_challenge_assessment": latest_review.get("sections", {}).get("Hiring Difficulty Assessment", "Hiring difficulty requires human review."),
                "proposed_retained_search_model": "Staged retained search model subject to Gareth approval and recorded client terms.",
                "estimated_timeline": "Indicative timeline: 6 to 12 weeks depending on seniority, market availability, and approval readiness.",
            },
        },
        {
            "deliverable_id": "glirn-deliverable-fee-proposal-001",
            "deliverable_type": "Fee Proposal",
            "title": f"Fee Proposal - {target_client}",
            "target_client_profile": target_client,
            "approval_status": "pending_gareth_approval",
            "client_ready": False,
            "client_delivery_allowed": False,
            "compliance_status": compliance_status,
            "recommended_action": "review",
            "sections": {
                "fee_structure": highest_fee.get("fee_type", "placement or retained search fee"),
                "estimated_fee_value": estimated_fee,
                "payment_stages": "Contingency on placement or retained stages subject to Gareth approval.",
                "approval_requirements": "No fee proposal can become client-ready without Gareth approval.",
            },
        },
        {
            "deliverable_id": "glirn-deliverable-candidate-shortlist-001",
            "deliverable_type": "Candidate Shortlist Report",
            "title": f"Candidate Shortlist Report - {target_client}",
            "target_client_profile": target_client,
            "approval_status": "pending_gareth_approval",
            "client_ready": False,
            "client_delivery_allowed": False,
            "compliance_status": compliance_status,
            "recommended_action": "review",
            "sections": {
                "anonymised_candidate_profiles": [anonymised_candidate],
                "role_fit_assessment": f"Match score: {top_match.get('match_revenue_score', 0)}. Placement probability: {top_match.get('placement_probability_score', 0)}.",
                "hiring_recommendation": latest_review.get("recommended_action", "monitor"),
                "compliance_status": compliance_status,
            },
        },
        {
            "deliverable_id": "glirn-deliverable-market-intelligence-001",
            "deliverable_type": "Market Intelligence Report",
            "title": f"Market Intelligence Report - {practice_area}",
            "target_client_profile": target_client,
            "approval_status": "pending_gareth_approval",
            "client_ready": False,
            "client_delivery_allowed": False,
            "compliance_status": compliance_status,
            "recommended_action": "review",
            "sections": {
                "market_demand_indicators": latest_review.get("sections", {}).get("Market Signal Summary", "Market signals require review."),
                "hiring_pressure_assessment": f"Hiring likelihood score: {top_client.get('hiring_likelihood_score', 0)}.",
                "role_scarcity_assessment": latest_review.get("sections", {}).get("Hiring Difficulty Assessment", "Role scarcity requires review."),
                "practice_area_observations": practice_area,
            },
        },
        {
            "deliverable_id": "glirn-deliverable-client-meeting-brief-001",
            "deliverable_type": "Client Meeting Brief",
            "title": f"Client Meeting Brief - {target_client}",
            "target_client_profile": target_client,
            "approval_status": "pending_gareth_approval",
            "client_ready": False,
            "client_delivery_allowed": False,
            "compliance_status": compliance_status,
            "recommended_action": "review",
            "sections": {
                "meeting_objective": "Determine whether the client has a real senior legal hiring need.",
                "opportunity_summary": executive_autopilot.get("top_opportunity", {}).get("title", "Senior legal opportunity"),
                "key_discussion_points": [
                    "Practice area demand",
                    "Jurisdiction focus",
                    "Role priority",
                    "Fee model",
                    "Consent and client terms readiness",
                ],
                "recommended_outcome": "Agree whether to monitor, defer, or move toward a Gareth-approved search mandate.",
            },
        },
    ]

    for item in deliverables:
        item.update({
            "candidate_personal_data_included": False,
            "candidate_personal_data_blocked": True,
            "human_approval_mandatory": True,
            "external_delivery_enabled": False,
            "outreach_enabled": False,
            "capital_execution": False,
            "autonomous_execution": False,
        })

    latest = deliverables[0] if deliverables else None

    return {
        "engine": "deliverable_factory",
        "status": "Client Deliverable Drafts Ready",
        "deliverable_generation_status": "generated_pending_gareth_approval",
        "generated_deliverables": deliverables,
        "pending_deliverable_approvals": [
            {
                "deliverable_id": item.get("deliverable_id"),
                "title": item.get("title"),
                "deliverable_type": item.get("deliverable_type"),
                "approval_status": item.get("approval_status"),
                "approval_required": True,
            }
            for item in deliverables
        ],
        "latest_deliverable": latest,
        "deliverable_status": latest.get("approval_status") if latest else "none",
        "dave_recommends_first": {
            "recommendation": "Review generated client deliverables before any client-facing use.",
            "deliverable_id": latest.get("deliverable_id") if latest else None,
            "human_approval_required": True,
            "capital_execution": False,
        },
        "client_delivery_enabled": False,
        "human_approval_mandatory": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def build_approval_to_action_workflow(intelligence_review_engine, deliverable_factory):
    review_items = [
        {
            "item_id": review.get("review_id"),
            "item_type": "intelligence_review",
            "title": review.get("title"),
            "draft_status": "generated_draft",
            "approval_status": review.get("approval_status", "pending_gareth_approval"),
            "client_ready_status": "not_client_ready",
            "action_readiness_status": "awaiting_gareth_approval",
            "source": "intelligence_review_engine",
            "client_ready": False,
            "human_use_ready": False,
        }
        for review in intelligence_review_engine.get("generated_reviews", []) or []
    ]
    deliverable_items = [
        {
            "item_id": deliverable.get("deliverable_id"),
            "item_type": "client_deliverable",
            "title": deliverable.get("title"),
            "deliverable_type": deliverable.get("deliverable_type"),
            "draft_status": "generated_draft",
            "approval_status": deliverable.get("approval_status", "pending_gareth_approval"),
            "client_ready_status": "not_client_ready",
            "action_readiness_status": "awaiting_gareth_approval",
            "source": "deliverable_factory",
            "client_ready": False,
            "human_use_ready": False,
        }
        for deliverable in deliverable_factory.get("generated_deliverables", []) or []
    ]
    pending_items = review_items + deliverable_items

    return {
        "engine": "approval_to_action_workflow",
        "status": "Approval-to-Action Controls Active",
        "draft_status": "generated_drafts_pending_review",
        "approval_status": "pending_gareth_approval",
        "client_ready_status": "not_client_ready_without_gareth_approval",
        "action_readiness_status": "human_review_required",
        "pending_gareth_approval": pending_items,
        "approved_for_human_use": [],
        "approved_deliverable_queue": [],
        "rejected_items": [],
        "rejected_deliverable_queue": [],
        "monitored_items": [],
        "monitored_deliverable_queue": [],
        "dave_recommends_first": {
            "recommendation": "Review generated drafts and approve only those ready for human-controlled use.",
            "human_approval_required": True,
            "capital_execution": False,
        },
        "automatic_delivery_enabled": False,
        "outreach_enabled": False,
        "external_connections_enabled": False,
        "fee_proposal_autonomous": False,
        "contracts_autonomous": False,
        "human_approval_mandatory": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def apply_approval_to_action_decision(item, action):
    base = {
        **item,
        "decision": action,
        "automatic_delivery_enabled": False,
        "outreach_enabled": False,
        "external_connections_enabled": False,
        "fee_proposal_autonomous": False,
        "contracts_autonomous": False,
        "capital_execution": False,
        "autonomous_execution": False,
    }
    if action == "approve":
        return {
            **base,
            "approval_status": "approved_by_gareth",
            "client_ready_status": "ready_for_human_use",
            "action_readiness_status": "approved_for_human_controlled_use",
            "client_ready": True,
            "human_use_ready": True,
        }
    if action == "reject":
        return {
            **base,
            "approval_status": "rejected_by_gareth",
            "client_ready_status": "blocked_not_client_ready",
            "action_readiness_status": "rejected",
            "client_ready": False,
            "human_use_ready": False,
        }
    if action == "monitor":
        return {
            **base,
            "approval_status": "monitoring",
            "client_ready_status": "not_client_ready",
            "action_readiness_status": "monitoring_pending_future_review",
            "client_ready": False,
            "human_use_ready": False,
        }
    return {
        **base,
        "approval_status": "pending_gareth_approval",
        "client_ready_status": "not_client_ready",
        "action_readiness_status": "reset_to_draft",
        "client_ready": False,
        "human_use_ready": False,
    }


def build_revenue_command_centre(
    legal_opportunity_radar,
    executive_autopilot,
    matching_engine,
    commercial_revenue_engine,
    deliverable_factory,
    approval_to_action_workflow,
    daily_executive_briefing,
):
    pipeline = commercial_revenue_engine.get("commercial_pipeline", []) or []
    matches = matching_engine.get("ranked_placement_matches", []) or []
    deliverables = deliverable_factory.get("generated_deliverables", []) or []
    approved_items = approval_to_action_workflow.get("approved_for_human_use", []) or []
    pending_items = approval_to_action_workflow.get("pending_gareth_approval", []) or []
    radar_opportunities = legal_opportunity_radar.get("opportunities_ranked", []) or []

    total_revenue_pipeline = round(
        float(commercial_revenue_engine.get("estimated_revenue_pipeline", 0) or 0),
        2,
    )
    estimated_placement_fee_pipeline = round(
        sum(
            float(item.get("estimated_revenue", 0) or 0)
            for item in pipeline
            if "placement" in str(item.get("fee_type", "")).lower()
            or "search" in str(item.get("fee_type", "")).lower()
        ),
        2,
    )
    estimated_intelligence_review_revenue = round(
        sum(
            float(item.get("estimated_revenue", 0) or 0)
            for item in pipeline
            if "intelligence" in str(item.get("fee_type", "")).lower()
        ),
        2,
    )
    approved_opportunities_count = len([
        item for item in approved_items
        if item.get("item_type") in {"opportunity", "intelligence_review"}
    ])
    approved_deliverables_count = len([
        item for item in approved_items
        if item.get("item_type") == "client_deliverable"
    ])

    highest_fee_opportunity = (
        commercial_revenue_engine.get("highest_fee_opportunity")
        or (pipeline[0] if pipeline else {})
    )
    fastest_revenue_opportunity = sorted(
        pipeline,
        key=lambda item: (
            0 if item.get("invoice_readiness") == "ready" else 1,
            len(item.get("blocked_reasons", []) or []),
            -float(item.get("estimated_revenue", 0) or 0),
        ),
    )[0] if pipeline else {}

    match_by_opportunity = {item.get("opportunity_id"): item for item in matches}
    prioritised = []
    for item in pipeline:
        opportunity_id = item.get("opportunity_id")
        match = match_by_opportunity.get(opportunity_id, {})
        fee_score = clamp_score((float(item.get("estimated_revenue", 0) or 0) / 150000) * 100)
        probability_score = clamp_score(match.get("placement_probability_score", 50))
        compliance_score = 100 if not item.get("blocked_reasons") else 35
        approval_score = 80 if item.get("human_approval_required") else 100
        client_score = 100 if item.get("client_terms_readiness") == "recorded" else 35
        revenue_priority_score = round(
            fee_score * 0.35
            + probability_score * 0.25
            + compliance_score * 0.20
            + approval_score * 0.10
            + client_score * 0.10,
            2,
        )
        prioritised.append({
            "opportunity_id": opportunity_id,
            "title": item.get("title"),
            "fee_type": item.get("fee_type"),
            "estimated_revenue": item.get("estimated_revenue", 0),
            "placement_probability_score": probability_score,
            "compliance_readiness": compliance_score,
            "approval_readiness": approval_score,
            "client_readiness": client_score,
            "revenue_priority_score": revenue_priority_score,
            "readiness_status": "invoice_ready" if item.get("invoice_readiness") == "ready" else "requires_gareth_review",
            "human_approval_required": True,
            "capital_execution": False,
            "autonomous_execution": False,
        })

    top_revenue_opportunities = sorted(
        prioritised,
        key=lambda item: (
            item.get("revenue_priority_score", 0),
            item.get("estimated_revenue", 0),
        ),
        reverse=True,
    )[:5]
    top_quick_win_opportunities = sorted(
        prioritised,
        key=lambda item: (
            item.get("client_readiness", 0),
            item.get("compliance_readiness", 0),
            item.get("placement_probability_score", 0),
            item.get("estimated_revenue", 0),
        ),
        reverse=True,
    )[:3]
    highest_probability_revenue = sorted(
        prioritised,
        key=lambda item: item.get("placement_probability_score", 0),
        reverse=True,
    )[0] if prioritised else {}

    revenue_funnel = [
        {
            "stage": "Opportunity",
            "item_count": len(radar_opportunities),
            "estimated_value": round(sum(float(item.get("expected_fee_value", 0) or 0) for item in radar_opportunities), 2),
            "readiness_status": "ranked_pending_gareth_review",
        },
        {
            "stage": "Intelligence Review",
            "item_count": len(daily_executive_briefing.get("top_3_revenue_actions", []) or []),
            "estimated_value": estimated_intelligence_review_revenue,
            "readiness_status": "draft_or_review_required",
        },
        {
            "stage": "Search Mandate",
            "item_count": len([
                item for item in deliverables
                if item.get("deliverable_type") == "Search Mandate Proposal"
            ]),
            "estimated_value": estimated_intelligence_review_revenue,
            "readiness_status": "pending_gareth_approval",
        },
        {
            "stage": "Candidate Match",
            "item_count": len(matches),
            "estimated_value": round(sum(float(item.get("estimated_fee_potential", 0) or 0) for item in matches), 2),
            "readiness_status": "consent_and_terms_gate_required",
        },
        {
            "stage": "Placement",
            "item_count": len([
                item for item in pipeline
                if item.get("fee_type") in {"contingency placement fee", "executive search fee"}
            ]),
            "estimated_value": estimated_placement_fee_pipeline,
            "readiness_status": "human_approved_placement_required",
        },
        {
            "stage": "Invoice Ready",
            "item_count": len([
                item for item in pipeline
                if item.get("invoice_readiness") == "ready"
            ]),
            "estimated_value": round(sum(
                float(item.get("estimated_revenue", 0) or 0)
                for item in pipeline
                if item.get("invoice_readiness") == "ready"
            ), 2),
            "readiness_status": "client_terms_and_consent_required",
        },
    ]

    readiness_components = [
        100 if highest_fee_opportunity else 0,
        100 if top_revenue_opportunities else 0,
        100 if deliverables else 0,
        100 if pending_items else 50,
        max((item.get("compliance_readiness", 0) for item in prioritised), default=0),
    ]
    revenue_readiness_score = round(sum(readiness_components) / len(readiness_components), 2)
    recommendation_target = top_revenue_opportunities[0] if top_revenue_opportunities else {}
    recommendation = (
        f"Review {recommendation_target.get('title')} first; it has the strongest revenue priority score."
        if recommendation_target
        else "Monitor the revenue pipeline until a reviewed opportunity is available."
    )

    return {
        "engine": "revenue_command_centre",
        "status": "Revenue Command Centre Active",
        "revenue_pipeline": pipeline,
        "total_revenue_pipeline": total_revenue_pipeline,
        "estimated_placement_fee_pipeline": estimated_placement_fee_pipeline,
        "estimated_intelligence_review_revenue": estimated_intelligence_review_revenue,
        "approved_opportunities_count": approved_opportunities_count,
        "approved_deliverables_count": approved_deliverables_count,
        "highest_fee_opportunity": highest_fee_opportunity,
        "fastest_revenue_opportunity": fastest_revenue_opportunity,
        "revenue_readiness_score": revenue_readiness_score,
        "revenue_funnel": revenue_funnel,
        "top_revenue_opportunities": top_revenue_opportunities,
        "top_quick_win_opportunities": top_quick_win_opportunities,
        "highest_probability_revenue": highest_probability_revenue,
        "dave_recommends_first": {
            "recommendation": recommendation,
            "opportunity_id": recommendation_target.get("opportunity_id"),
            "human_approval_required": True,
            "capital_execution": False,
        },
        "read_only": True,
        "outreach_enabled": False,
        "client_delivery_enabled": False,
        "fee_proposals_enabled": False,
        "contracts_enabled": False,
        "invoicing_enabled": False,
        "external_integrations_enabled": False,
        "scraping_enabled": False,
        "live_data_fetching_enabled": False,
        "human_approval_mandatory": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def build_first_client_readiness_gate(
    legal_opportunity_radar,
    intelligence_review_engine,
    deliverable_factory,
    approval_to_action_workflow,
    commercial_revenue_engine,
    compliance_core,
    revenue_command_centre,
):
    opportunities = legal_opportunity_radar.get("opportunities_ranked", []) or []
    reviews = intelligence_review_engine.get("generated_reviews", []) or []
    deliverables = deliverable_factory.get("generated_deliverables", []) or []
    pending_approval_items = approval_to_action_workflow.get("pending_gareth_approval", []) or []
    pipeline = commercial_revenue_engine.get("commercial_pipeline", []) or []
    compliance_alerts = compliance_core.get("compliance_alerts", []) or []
    has_review = bool(reviews)
    has_deliverable = bool(deliverables)
    has_fee_model = bool(pipeline)
    has_payment_process = any(item.get("invoice_readiness") == "ready" for item in pipeline)
    manual_delivery_process_ready = has_deliverable and bool(pending_approval_items)
    human_review_checklist_complete = bool(pending_approval_items)
    first_client_items = []

    for opportunity in opportunities:
        matching_pipeline = next(
            (
                item for item in pipeline
                if item.get("opportunity_id") == opportunity.get("opportunity_id")
            ),
            {},
        )
        candidate_consent_ready = not (
            "missing_or_inactive_candidate_consent" in (matching_pipeline.get("blocked_reasons", []) or [])
        )
        client_terms_ready = matching_pipeline.get("client_terms_readiness") == "recorded"
        compliance_ready = not compliance_alerts and opportunity.get("compliance_readiness", 0) >= 75
        fee_model_ready = bool(matching_pipeline.get("fee_type")) and has_fee_model
        checks = {
            "client_profile_confirmed": bool((opportunity.get("client_firm", {}) or {}).get("name")),
            "target_sector_confirmed": bool(opportunity.get("practice_area")),
            "jurisdiction_confirmed": bool(opportunity.get("jurisdiction")),
            "offer_confirmed": True,
            "deliverable_generated": has_deliverable,
            "human_review_checklist_complete": human_review_checklist_complete,
            "candidate_consent_ready": candidate_consent_ready,
            "client_terms_ready": client_terms_ready,
            "compliance_ready": compliance_ready,
            "fee_model_ready": fee_model_ready,
            "payment_process_ready": has_payment_process,
            "manual_delivery_process_ready": manual_delivery_process_ready,
            "gareth_approval_required": True,
        }
        client_readiness_score = round(
            (
                (100 if checks["client_profile_confirmed"] else 0)
                + (100 if checks["target_sector_confirmed"] else 0)
                + (100 if checks["jurisdiction_confirmed"] else 0)
                + (100 if checks["offer_confirmed"] else 0)
                + (100 if checks["client_terms_ready"] else 0)
            ) / 5,
            2,
        )
        compliance_readiness_score = round(
            (
                (100 if checks["candidate_consent_ready"] else 0)
                + (100 if checks["compliance_ready"] else 0)
            ) / 2,
            2,
        )
        commercial_readiness_score = round(
            (
                (100 if checks["fee_model_ready"] else 0)
                + (100 if checks["payment_process_ready"] else 0)
            ) / 2,
            2,
        )
        deliverable_readiness_score = round(
            (
                (100 if checks["deliverable_generated"] else 0)
                + (100 if checks["human_review_checklist_complete"] else 0)
                + (100 if checks["manual_delivery_process_ready"] else 0)
            ) / 3,
            2,
        )
        approval_readiness_score = 75 if checks["gareth_approval_required"] else 100
        overall_score = round(
            client_readiness_score * 0.20
            + compliance_readiness_score * 0.30
            + commercial_readiness_score * 0.15
            + deliverable_readiness_score * 0.20
            + approval_readiness_score * 0.15,
            2,
        )

        if not checks["candidate_consent_ready"]:
            recommendation = "blocked_missing_consent"
        elif not checks["client_terms_ready"]:
            recommendation = "blocked_missing_terms"
        elif not checks["compliance_ready"]:
            recommendation = "blocked_missing_compliance"
        elif not checks["fee_model_ready"]:
            recommendation = "blocked_missing_fee_model"
        elif not checks["deliverable_generated"]:
            recommendation = "blocked_missing_deliverable"
        elif overall_score >= 85:
            recommendation = "approve_for_human_action"
        elif overall_score >= 60:
            recommendation = "monitor"
        else:
            recommendation = "reject"

        missing_checks = [
            check_name for check_name, passed in checks.items()
            if check_name != "gareth_approval_required" and not passed
        ]
        item = {
            "item_id": f"first-client-{opportunity.get('opportunity_id')}",
            "opportunity_id": opportunity.get("opportunity_id"),
            "title": opportunity.get("title"),
            "client_name": (opportunity.get("client_firm", {}) or {}).get("name"),
            "practice_area": opportunity.get("practice_area"),
            "jurisdiction": opportunity.get("jurisdiction"),
            "readiness_checks": checks,
            "missing_checks": missing_checks,
            "client_readiness_score": client_readiness_score,
            "compliance_readiness_score": compliance_readiness_score,
            "commercial_readiness_score": commercial_readiness_score,
            "deliverable_readiness_score": deliverable_readiness_score,
            "approval_readiness_score": approval_readiness_score,
            "overall_first_client_readiness_score": overall_score,
            "readiness_recommendation": recommendation,
            "gareth_approval_status": "required",
            "human_action_ready": False,
            "human_approval_required": True,
            "client_contact_enabled": False,
            "candidate_contact_enabled": False,
            "client_delivery_enabled": False,
            "fee_proposal_enabled": False,
            "invoicing_enabled": False,
            "capital_execution": False,
            "autonomous_execution": False,
        }
        first_client_items.append(item)

    ready_items = [
        item for item in first_client_items
        if item.get("readiness_recommendation") == "approve_for_human_action"
    ]
    blocked_items = [
        item for item in first_client_items
        if str(item.get("readiness_recommendation", "")).startswith("blocked_")
        or item.get("readiness_recommendation") == "reject"
    ]
    monitored_items = [
        item for item in first_client_items
        if item.get("readiness_recommendation") == "monitor"
    ]
    best_item = sorted(
        first_client_items,
        key=lambda item: (
            item.get("overall_first_client_readiness_score", 0),
            revenue_command_centre.get("total_revenue_pipeline", 0),
        ),
        reverse=True,
    )[0] if first_client_items else {}
    overall_gate_score = round(
        sum(item.get("overall_first_client_readiness_score", 0) for item in first_client_items) / len(first_client_items),
        2,
    ) if first_client_items else 0
    readiness_recommendation = (
        best_item.get("readiness_recommendation")
        if best_item
        else "monitor"
    )

    return {
        "engine": "first_client_readiness_gate",
        "status": "First Client Readiness Gate Active",
        "readiness_checks": first_client_items,
        "first_client_ready_items": ready_items,
        "blocked_first_client_items": blocked_items,
        "monitored_first_client_items": monitored_items,
        "readiness_recommendation": readiness_recommendation,
        "overall_first_client_readiness_score": overall_gate_score,
        "dave_recommends_first": {
            "recommendation": (
                f"Review {best_item.get('title')} first; current readiness is {readiness_recommendation}."
                if best_item
                else "Monitor first-client readiness until GLIRN has a decision-ready item."
            ),
            "item_id": best_item.get("item_id"),
            "human_approval_required": True,
            "capital_execution": False,
        },
        "client_contact_enabled": False,
        "candidate_contact_enabled": False,
        "client_delivery_enabled": False,
        "fee_proposal_enabled": False,
        "contract_acceptance_enabled": False,
        "invoicing_enabled": False,
        "external_integrations_enabled": False,
        "scraping_enabled": False,
        "live_data_fetching_enabled": False,
        "human_approval_mandatory": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def apply_first_client_readiness_decision(item, action):
    base = {
        **item,
        "decision": action,
        "client_contact_enabled": False,
        "candidate_contact_enabled": False,
        "client_delivery_enabled": False,
        "fee_proposal_enabled": False,
        "contract_acceptance_enabled": False,
        "invoicing_enabled": False,
        "external_integrations_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    }
    if action == "approve":
        return {
            **base,
            "gareth_approval_status": "approved_by_gareth",
            "readiness_recommendation": "approve_for_human_action",
            "human_action_ready": True,
        }
    if action == "reject":
        return {
            **base,
            "gareth_approval_status": "rejected_by_gareth",
            "readiness_recommendation": "reject",
            "human_action_ready": False,
        }
    if action == "monitor":
        return {
            **base,
            "gareth_approval_status": "monitoring",
            "readiness_recommendation": "monitor",
            "human_action_ready": False,
        }
    return {
        **base,
        "gareth_approval_status": "review_required",
        "readiness_recommendation": "monitor",
        "human_action_ready": False,
    }


def build_launch_readiness_command_centre(
    deployment_readiness,
    first_client_readiness_gate,
    revenue_command_centre,
    intelligence_review_engine,
    deliverable_factory,
    approval_to_action_workflow,
    launch_assets=None,
):
    launch_assets = launch_assets or {}
    website_ready = launch_assets.get("website_asset_ready", True)
    linkedin_ready = launch_assets.get("linkedin_asset_ready", True)
    first_offer_ready = launch_assets.get("first_offer_confirmed", True)
    target_clients_ready = launch_assets.get("target_client_list_ready", True)
    payment_process_ready = launch_assets.get("payment_process_ready", False)
    client_terms_process_ready = launch_assets.get("client_terms_process_ready", False)
    manual_delivery_ready = launch_assets.get("manual_delivery_process_ready", False)
    gareth_approval_ready = launch_assets.get("gareth_approval_ready", False)

    sample_review_ready = bool(intelligence_review_engine.get("latest_generated_review"))
    deliverable_ready = bool(deliverable_factory.get("generated_deliverables"))
    approval_ready = bool(approval_to_action_workflow.get("pending_gareth_approval"))
    first_client_score = first_client_readiness_gate.get("overall_first_client_readiness_score", 0)
    revenue_score = revenue_command_centre.get("revenue_readiness_score", 0)
    compliance_ready = first_client_score >= 60 and not first_client_readiness_gate.get("blocked_first_client_items") == []
    # Keep compliance conservative: score can be positive while launch remains blocked by consent or terms.
    compliance_ready = first_client_score >= 60

    categories = {
        "brand_readiness": True,
        "website_readiness": website_ready,
        "LinkedIn_readiness": linkedin_ready,
        "first_offer_readiness": first_offer_ready,
        "sample_review_readiness": sample_review_ready,
        "client_targeting_readiness": target_clients_ready,
        "compliance_readiness": compliance_ready,
        "consent_process_readiness": first_client_score >= 60,
        "client_terms_readiness": client_terms_process_ready,
        "payment_process_readiness": payment_process_ready,
        "first_client_readiness": first_client_score >= 70,
        "revenue_system_readiness": revenue_score >= 70,
        "approval_workflow_readiness": approval_ready,
        "deliverable_readiness": deliverable_ready,
    }

    gap_map = {
        "website_readiness": "missing website asset",
        "LinkedIn_readiness": "missing LinkedIn profile asset",
        "first_offer_readiness": "missing first offer confirmation",
        "sample_review_readiness": "missing sample intelligence review",
        "client_targeting_readiness": "missing target client list",
        "client_terms_readiness": "missing client terms process",
        "payment_process_readiness": "missing payment process",
        "manual_delivery_process_ready": "missing manual delivery process",
        "gareth_approval_ready": "missing Gareth approval",
    }
    extra_checks = {
        "manual_delivery_process_ready": manual_delivery_ready,
        "gareth_approval_ready": gareth_approval_ready,
    }
    launch_missing_items = [
        {"gap_code": key, "description": description}
        for key, description in gap_map.items()
        if not categories.get(key, extra_checks.get(key, False))
    ]

    launch_ready_items = [
        {"category": key, "status": "ready"}
        for key, ready in categories.items()
        if ready
    ]
    launch_blocked_items = [
        {"category": item["gap_code"], "reason": item["description"]}
        for item in launch_missing_items
    ]

    brand_score = round((
        (100 if categories["brand_readiness"] else 0)
        + (100 if categories["website_readiness"] else 0)
        + (100 if categories["LinkedIn_readiness"] else 0)
    ) / 3, 2)
    commercial_score = round((
        (100 if categories["first_offer_readiness"] else 0)
        + (100 if categories["client_targeting_readiness"] else 0)
        + (100 if categories["client_terms_readiness"] else 0)
        + (100 if categories["payment_process_readiness"] else 0)
    ) / 4, 2)
    compliance_score = round((
        (100 if categories["compliance_readiness"] else 0)
        + (100 if categories["consent_process_readiness"] else 0)
        + (100 if categories["approval_workflow_readiness"] else 0)
    ) / 3, 2)
    revenue_score_value = round((
        revenue_score
        + (100 if categories["revenue_system_readiness"] else 0)
        + (100 if categories["deliverable_readiness"] else 0)
    ) / 3, 2)
    operational_score = round((
        (100 if categories["sample_review_readiness"] else 0)
        + (100 if categories["first_client_readiness"] else 0)
        + (100 if extra_checks["manual_delivery_process_ready"] else 0)
        + (100 if extra_checks["gareth_approval_ready"] else 0)
        + float(deployment_readiness.get("readiness_score", 0) or 0)
    ) / 5, 2)
    overall_score = round(
        brand_score * 0.15
        + commercial_score * 0.25
        + compliance_score * 0.25
        + revenue_score_value * 0.20
        + operational_score * 0.15,
        2,
    )

    critical_gaps = {item["gap_code"] for item in launch_missing_items}
    if {"client_terms_readiness", "payment_process_readiness", "gareth_approval_ready"} & critical_gaps:
        grade = "blocked"
    elif overall_score >= 85 and not launch_missing_items:
        grade = "launch_ready"
    elif overall_score >= 65:
        grade = "nearly_ready"
    else:
        grade = "not_ready"

    if not sample_review_ready:
        next_action = "create_sample_review"
    elif not website_ready:
        next_action = "publish_website_copy"
    elif not linkedin_ready:
        next_action = "complete_linkedin_profile"
    elif not first_offer_ready:
        next_action = "confirm_first_offer"
    elif not client_terms_process_ready:
        next_action = "confirm_client_terms_process"
    elif not payment_process_ready:
        next_action = "confirm_payment_process"
    elif not gareth_approval_ready:
        next_action = "approve_first_client_action"
    else:
        next_action = "monitor"

    return {
        "engine": "launch_readiness_command_centre",
        "status": "Launch Readiness Command Centre Active",
        "launch_readiness_score": overall_score,
        "launch_readiness_grade": grade,
        "overall_launch_readiness_score": overall_score,
        "brand_score": brand_score,
        "commercial_score": commercial_score,
        "compliance_score": compliance_score,
        "revenue_score": revenue_score_value,
        "operational_score": operational_score,
        "launch_readiness_categories": categories,
        "launch_ready_items": launch_ready_items,
        "launch_blocked_items": launch_blocked_items,
        "launch_missing_items": launch_missing_items,
        "launch_recommended_next_action": next_action,
        "gareth_approval_status": "required",
        "dave_recommends_first": {
            "recommendation": f"Next launch action: {next_action}. Gareth approval remains required before any real-world activity.",
            "human_approval_required": True,
            "capital_execution": False,
        },
        "autonomous_launch_enabled": False,
        "website_publishing_enabled": False,
        "linkedin_posting_enabled": False,
        "outreach_enabled": False,
        "client_delivery_enabled": False,
        "fee_proposal_enabled": False,
        "invoicing_enabled": False,
        "external_integrations_enabled": False,
        "scraping_enabled": False,
        "live_data_fetching_enabled": False,
        "human_approval_mandatory": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def apply_launch_readiness_decision(item, action):
    base = {
        **item,
        "decision": action,
        "autonomous_launch_enabled": False,
        "website_publishing_enabled": False,
        "linkedin_posting_enabled": False,
        "outreach_enabled": False,
        "client_delivery_enabled": False,
        "fee_proposal_enabled": False,
        "invoicing_enabled": False,
        "external_integrations_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    }
    if action == "approve":
        return {
            **base,
            "gareth_approval_status": "approved_by_gareth",
            "launch_action_status": "approved_for_human_planning",
        }
    if action == "reject":
        return {
            **base,
            "gareth_approval_status": "rejected_by_gareth",
            "launch_action_status": "blocked",
        }
    if action == "monitor":
        return {
            **base,
            "gareth_approval_status": "monitoring",
            "launch_action_status": "monitoring",
        }
    return {
        **base,
        "gareth_approval_status": "planning_required",
        "launch_action_status": "reset_to_planning",
    }


def build_invoice_drafting_engine(commercial_revenue_engine, first_client_readiness_gate, revenue_command_centre):
    pipeline = commercial_revenue_engine.get("commercial_pipeline", []) or []
    readiness_items = first_client_readiness_gate.get("readiness_checks", []) or []
    readiness_by_opportunity = {
        item.get("opportunity_id"): item
        for item in readiness_items
    }
    invoice_drafts = []

    for index, item in enumerate(pipeline, start=1):
        amount = round(float(item.get("estimated_revenue", 0) or 0), 2)
        if amount <= 0:
            continue

        fee_type = item.get("fee_type", "intelligence report fee")
        opportunity_id = item.get("opportunity_id")
        readiness = readiness_by_opportunity.get(opportunity_id, {})
        service_description = item.get("title") or "GLIRN senior legal hiring service"
        client_terms_ready = item.get("client_terms_readiness") == "recorded"
        fee_model_ready = bool(fee_type)
        service_description_ready = bool(service_description)
        gareth_approval_ready = False
        invoice_ready = (
            client_terms_ready
            and fee_model_ready
            and service_description_ready
            and gareth_approval_ready
        )

        draft = {
            "invoice_number": f"GLIRN-INV-{index:03d}",
            "invoice_date": datetime.now(timezone.utc).date().isoformat(),
            "supply_date": datetime.now(timezone.utc).date().isoformat(),
            "seller_name": "David Sanson",
            "seller_business_name": "Global Legal Intelligence & Recruitment Network",
            "seller_contact_details": "To be confirmed by Gareth Price before manual sending.",
            "customer_name": item.get("client_firm", "Prospective Client"),
            "customer_address": "To be confirmed manually before sending.",
            "service_description": service_description,
            "fee_type": fee_type,
            "amount": amount,
            "VAT_status": "VAT not applied - confirm VAT position with Gareth Price before sending.",
            "VAT_amount_if_applicable": 0,
            "total_amount_due": amount,
            "payment_method_options": [
                "PayPal Business",
                "Revolut UK Bank Transfer",
            ],
            "payment_due_date": "To be confirmed manually before sending.",
            "payment_reference": f"GLIRN-{index:03d}",
            "notes": "Draft only. Gareth must approve, send, and confirm payment manually.",
            "invoice_type": (
                "GBP 500 GLIRN Senior Legal Hiring Intelligence Review"
                if amount == 500 or "intelligence" in str(fee_type).lower()
                else fee_type
            ),
            "opportunity_id": opportunity_id,
            "invoice_readiness_checks": {
                "client_terms_status": "recorded" if client_terms_ready else "missing",
                "fee_model_ready": fee_model_ready,
                "service_description_ready": service_description_ready,
                "gareth_approval_required": True,
                "gareth_approval_status": "required",
                "first_client_readiness": readiness.get("readiness_recommendation", "monitor"),
            },
            "invoice_readiness_status": "ready_for_gareth_approval" if invoice_ready else "draft_pending_gareth_approval",
            "approval_status": "pending_gareth_approval",
            "manual_sent_status": "not_sent",
            "manual_payment_status": "not_paid",
            "automatic_sending_enabled": False,
            "automatic_payment_collection_enabled": False,
            "automatic_payment_confirmation_enabled": False,
            "external_payment_integration_enabled": False,
            "paypal_api_enabled": False,
            "revolut_api_enabled": False,
            "bank_integration_enabled": False,
            "human_approval_required": True,
            "capital_execution": False,
            "autonomous_execution": False,
        }
        invoice_drafts.append(draft)

    pending = [
        {
            "invoice_number": draft.get("invoice_number"),
            "customer_name": draft.get("customer_name"),
            "amount": draft.get("amount"),
            "approval_status": draft.get("approval_status"),
            "approval_required": True,
        }
        for draft in invoice_drafts
    ]

    return {
        "engine": "invoice_drafting_engine",
        "status": "Invoice Drafting Engine Active",
        "invoice_drafts": invoice_drafts,
        "invoice_readiness_status": "drafts_pending_gareth_approval" if invoice_drafts else "no_invoice_drafts",
        "pending_invoice_approvals": pending,
        "approved_invoice_drafts": [],
        "supported_payment_methods": [
            "PayPal Business",
            "Revolut UK Bank Transfer",
        ],
        "supported_invoice_types": [
            "GBP 500 GLIRN Senior Legal Hiring Intelligence Review",
            "retained search payment",
            "contingency placement fee",
            "executive search fee",
            "intelligence report fee",
        ],
        "dave_recommends_first": {
            "recommendation": "Review invoice drafts manually before any invoice is sent.",
            "invoice_number": invoice_drafts[0].get("invoice_number") if invoice_drafts else None,
            "human_approval_required": True,
            "capital_execution": False,
        },
        "automatic_sending_enabled": False,
        "automatic_payment_collection_enabled": False,
        "automatic_payment_confirmation_enabled": False,
        "external_payment_integration_enabled": False,
        "paypal_api_enabled": False,
        "revolut_api_enabled": False,
        "bank_integration_enabled": False,
        "human_approval_mandatory": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def apply_invoice_draft_action(invoice, action):
    base = {
        **invoice,
        "action": action,
        "automatic_sending_enabled": False,
        "automatic_payment_collection_enabled": False,
        "automatic_payment_confirmation_enabled": False,
        "external_payment_integration_enabled": False,
        "paypal_api_enabled": False,
        "revolut_api_enabled": False,
        "bank_integration_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    }
    if action == "approve":
        return {
            **base,
            "approval_status": "approved_by_gareth",
            "invoice_readiness_status": "ready_for_manual_sending",
        }
    if action == "reject":
        return {
            **base,
            "approval_status": "rejected_by_gareth",
            "invoice_readiness_status": "blocked_rejected",
        }
    if action == "monitor":
        return {
            **base,
            "approval_status": "monitoring",
            "invoice_readiness_status": "monitoring",
        }
    if action == "mark-manually-sent":
        return {
            **base,
            "manual_sent_status": "sent_manually_by_gareth",
            "invoice_readiness_status": "manually_sent",
        }
    if action == "mark-manually-paid":
        return {
            **base,
            "manual_payment_status": "paid_manually_confirmed_by_gareth",
            "invoice_readiness_status": "manual_payment_recorded",
        }
    return {
        **base,
        "invoice_readiness_status": "draft_generated",
        "approval_status": "pending_gareth_approval",
    }


def build_client_terms_drafting_engine(commercial_revenue_engine):
    pipeline = commercial_revenue_engine.get("commercial_pipeline", []) or []
    draft_specs = [
        {
            "terms_id": "GLIRN-TERMS-REVIEW-001",
            "terms_type": "GBP 500 GLIRN Senior Legal Hiring Intelligence Review",
            "service_description": "Fixed-scope GLIRN Senior Legal Hiring Intelligence Review.",
            "fee_structure": "GBP 500 fixed review fee, subject to Gareth approval and manual agreement.",
            "payment_timing": "Payment timing to be confirmed manually before use.",
        },
        {
            "terms_id": "GLIRN-TERMS-CONTINGENCY-001",
            "terms_type": "contingency search mandate",
            "service_description": "Contingency senior legal recruitment search mandate.",
            "fee_structure": "Contingency placement fee payable only on agreed placement event.",
            "payment_timing": "Payment timing to be confirmed in manually agreed client terms.",
        },
        {
            "terms_id": "GLIRN-TERMS-RETAINED-001",
            "terms_type": "retained search mandate",
            "service_description": "Retained senior legal recruitment search mandate.",
            "fee_structure": "Retained search fee payable in manually agreed stages.",
            "payment_timing": "Retainer stages to be confirmed manually before use.",
        },
        {
            "terms_id": "GLIRN-TERMS-EXECUTIVE-001",
            "terms_type": "executive search mandate",
            "service_description": "Executive legal search mandate for Partner, General Counsel, CLO, or equivalent senior role.",
            "fee_structure": "Executive search fee subject to Gareth-approved client terms.",
            "payment_timing": "Payment milestones to be confirmed manually before use.",
        },
        {
            "terms_id": "GLIRN-TERMS-INTELLIGENCE-001",
            "terms_type": "intelligence report engagement",
            "service_description": "Legal hiring market intelligence report engagement.",
            "fee_structure": "Intelligence report fee subject to Gareth approval.",
            "payment_timing": "Payment timing to be confirmed manually before use.",
        },
    ]
    customer_hint = (
        (pipeline[0].get("client_firm") if pipeline else None)
        or "Client name to be inserted manually"
    )
    drafts = []

    for spec in draft_specs:
        draft = {
            "terms_id": spec["terms_id"],
            "terms_type": spec["terms_type"],
            "client_name_placeholder": customer_hint,
            "service_description": spec["service_description"],
            "scope_of_work": "Scope to be reviewed by Gareth and confirmed manually before client-facing use.",
            "fee_structure": spec["fee_structure"],
            "payment_method_options": [
                "PayPal Business",
                "Revolut UK Bank Transfer",
            ],
            "payment_timing": spec["payment_timing"],
            "no_guarantee_of_placement_wording": "GLIRN does not guarantee candidate availability, candidate acceptance, interview outcome, placement, or revenue outcome.",
            "confidentiality_wording": "Information exchanged should be treated as confidential unless Gareth manually agrees otherwise.",
            "candidate_consent_requirement": "Candidate-specific details require active candidate consent before any client-facing use.",
            "client_terms_requirement_before_candidate_details": "Client terms must be recorded before candidate details are shared.",
            "human_approval_statement": "Gareth approval is required before these terms are used externally.",
            "data_protection_note": "Candidate personal data must not be included or shared without active consent and compliance review.",
            "cancellation_note": "Cancellation position to be reviewed and completed manually before use.",
            "governing_jurisdiction_placeholder": "Governing jurisdiction to be confirmed manually before use.",
            "gareth_approval_status": "required",
            "terms_readiness_status": "draft_pending_gareth_approval",
            "manual_sent_status": "not_sent",
            "manual_agreed_status": "not_agreed",
            "automatic_sending_enabled": False,
            "automatic_agreement_enabled": False,
            "automatic_contract_acceptance_enabled": False,
            "esignature_integration_enabled": False,
            "external_integrations_enabled": False,
            "solicitor_approved_claim": False,
            "legally_binding_auto_created": False,
            "human_approval_required": True,
            "capital_execution": False,
            "autonomous_execution": False,
        }
        drafts.append(draft)

    return {
        "engine": "client_terms_drafting_engine",
        "status": "Client Terms Drafting Engine Active",
        "client_terms_drafts": drafts,
        "pending_terms_approvals": [
            {
                "terms_id": draft.get("terms_id"),
                "terms_type": draft.get("terms_type"),
                "gareth_approval_status": draft.get("gareth_approval_status"),
                "approval_required": True,
            }
            for draft in drafts
        ],
        "approved_terms_drafts": [],
        "terms_readiness_status": "drafts_pending_gareth_approval",
        "dave_recommends_first": {
            "recommendation": "Review client terms drafts manually before any client-facing use.",
            "terms_id": drafts[0].get("terms_id") if drafts else None,
            "human_approval_required": True,
            "capital_execution": False,
        },
        "automatic_sending_enabled": False,
        "automatic_agreement_enabled": False,
        "automatic_contract_acceptance_enabled": False,
        "esignature_integration_enabled": False,
        "external_integrations_enabled": False,
        "solicitor_approved_claim": False,
        "human_approval_mandatory": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def apply_client_terms_action(terms, action):
    base = {
        **terms,
        "action": action,
        "automatic_sending_enabled": False,
        "automatic_agreement_enabled": False,
        "automatic_contract_acceptance_enabled": False,
        "esignature_integration_enabled": False,
        "external_integrations_enabled": False,
        "solicitor_approved_claim": False,
        "legally_binding_auto_created": False,
        "capital_execution": False,
        "autonomous_execution": False,
    }
    if action == "approve":
        return {
            **base,
            "gareth_approval_status": "approved_by_gareth",
            "terms_readiness_status": "ready_for_manual_use",
        }
    if action == "reject":
        return {
            **base,
            "gareth_approval_status": "rejected_by_gareth",
            "terms_readiness_status": "blocked_rejected",
        }
    if action == "monitor":
        return {
            **base,
            "gareth_approval_status": "monitoring",
            "terms_readiness_status": "monitoring",
        }
    if action == "mark-manually-sent":
        return {
            **base,
            "manual_sent_status": "sent_manually_by_gareth",
            "terms_readiness_status": "manually_sent",
        }
    if action == "mark-manually-agreed":
        return {
            **base,
            "manual_agreed_status": "agreed_manually_by_gareth",
            "terms_readiness_status": "manual_agreement_recorded",
        }
    return {
        **base,
        "gareth_approval_status": "required",
        "terms_readiness_status": "draft_generated",
    }


def build_candidate_consent_management_engine(compliance_core):
    ledger = compliance_core.get("candidate_consent_ledger", []) or []
    records = []
    expiry_alerts = []

    for item in ledger:
        status = item.get("consent_status", "missing")
        consent_status = status if status in {"active", "expired", "withdrawn", "blocked"} else "draft"
        if status == "missing":
            consent_status = "draft"
        expiry = item.get("expires_at")
        if status == "active" and expiry:
            try:
                expiry_date = datetime.fromisoformat(expiry).date()
                days_until_expiry = (expiry_date - datetime.now(timezone.utc).date()).days
            except ValueError:
                days_until_expiry = None
            if days_until_expiry is not None and days_until_expiry <= 45:
                expiry_alerts.append({
                    "candidate_id": item.get("candidate_id"),
                    "alert_type": "consent_expiry_warning",
                    "days_until_expiry": days_until_expiry,
                })
        record = {
            "candidate_id": item.get("candidate_id"),
            "candidate_name_placeholder": item.get("candidate_name", "Candidate name withheld"),
            "jurisdiction": "jurisdiction to be confirmed manually",
            "consent_status": consent_status,
            "consent_date": "to be confirmed manually" if consent_status != "active" else "recorded in consent ledger",
            "consent_expiry_date": expiry,
            "consent_scope": item.get("consent_scope", "none"),
            "permitted_use": "candidate introduction" if consent_status == "active" else "none until manually confirmed",
            "approval_status": "pending_gareth_approval" if consent_status in {"draft", "pending"} else "recorded",
            "audit_reference": item.get("consent_id"),
            "candidate_contact_enabled": False,
            "automated_consent_collection_enabled": False,
            "automated_consent_activation_enabled": False,
            "external_integrations_enabled": False,
            "scraping_enabled": False,
            "live_data_fetching_enabled": False,
            "human_approval_required": True,
            "capital_execution": False,
            "autonomous_execution": False,
        }
        records.append(record)

    pending = [item for item in records if item.get("consent_status") in {"draft", "pending"}]
    active = [item for item in records if item.get("consent_status") == "active"]
    expired = [item for item in records if item.get("consent_status") == "expired"]
    blocked = [item for item in records if item.get("consent_status") in {"withdrawn", "blocked"}]
    candidate_consent_readiness = round(
        (len(active) / len(records)) * 100,
        2,
    ) if records else 0
    if expired or blocked:
        compliance_status = "blocked"
    elif pending:
        compliance_status = "pending_manual_consent"
    else:
        compliance_status = "ready"

    return {
        "engine": "candidate_consent_management_engine",
        "status": "Candidate Consent Management Engine Active",
        "candidate_consent_records": records,
        "pending_candidate_consents": pending,
        "active_candidate_consents": active,
        "expired_candidate_consents": expired,
        "withdrawn_candidate_consents": [item for item in records if item.get("consent_status") == "withdrawn"],
        "blocked_candidate_consents": blocked,
        "consent_readiness_status": compliance_status,
        "candidate_consent_readiness": candidate_consent_readiness,
        "consent_expiry_alerts": expiry_alerts,
        "consent_compliance_status": compliance_status,
        "dave_recommends_first": {
            "recommendation": "Review pending or expired consent records before any candidate-specific activity.",
            "human_approval_required": True,
            "capital_execution": False,
        },
        "candidate_contact_enabled": False,
        "automated_consent_collection_enabled": False,
        "automated_consent_activation_enabled": False,
        "external_integrations_enabled": False,
        "scraping_enabled": False,
        "live_data_fetching_enabled": False,
        "human_approval_mandatory": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def apply_candidate_consent_action(consent, action):
    base = {
        **consent,
        "action": action,
        "candidate_contact_enabled": False,
        "automated_consent_collection_enabled": False,
        "automated_consent_activation_enabled": False,
        "external_integrations_enabled": False,
        "scraping_enabled": False,
        "live_data_fetching_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    }
    if action == "approve":
        return {**base, "approval_status": "approved_by_gareth", "consent_status": "pending"}
    if action == "reject":
        return {**base, "approval_status": "rejected_by_gareth", "consent_status": "blocked"}
    if action == "monitor":
        return {**base, "approval_status": "monitoring", "consent_status": "pending"}
    if action == "mark-manually-sent":
        return {**base, "manual_sent_status": "sent_manually_by_gareth", "consent_status": "pending"}
    if action == "mark-manually-received":
        return {**base, "manual_received_status": "received_manually_by_gareth", "consent_status": "active"}
    if action == "mark-manually-withdrawn":
        return {**base, "manual_withdrawn_status": "withdrawn_manually_recorded_by_gareth", "consent_status": "withdrawn"}
    return {**base, "approval_status": "pending_gareth_approval", "consent_status": "draft"}


def build_manual_delivery_control_engine(
    approval_to_action_workflow,
    client_terms_drafting_engine,
    invoice_drafting_engine,
    candidate_consent_management_engine,
    compliance_core,
):
    approved_items = approval_to_action_workflow.get("approved_for_human_use", []) or []
    pending_items = approval_to_action_workflow.get("pending_gareth_approval", []) or []
    terms_drafts = client_terms_drafting_engine.get("client_terms_drafts", []) or []
    invoice_drafts = invoice_drafting_engine.get("invoice_drafts", []) or []
    active_consents = candidate_consent_management_engine.get("active_candidate_consents", []) or []
    active_consent_available = bool(active_consents)
    compliance_alerts = compliance_core.get("compliance_alerts", []) or []
    compliance_ready = not compliance_alerts
    terms_ready = any(
        item.get("gareth_approval_status") == "approved_by_gareth"
        or item.get("terms_readiness_status") == "ready_for_manual_use"
        for item in terms_drafts
    )
    invoice_ready = any(
        item.get("approval_status") == "approved_by_gareth"
        or item.get("invoice_readiness_status") == "ready_for_manual_sending"
        for item in invoice_drafts
    )
    delivery_items = []

    source_items = approved_items or pending_items
    if not source_items and terms_drafts:
        source_items = [
            {
                "item_id": terms_drafts[0].get("terms_id"),
                "item_type": "client_terms",
                "title": terms_drafts[0].get("terms_type"),
                "approval_status": terms_drafts[0].get("gareth_approval_status", "required"),
                "client_ready": False,
            }
        ]

    for item in source_items:
        candidate_data_included = bool(item.get("candidate_personal_data_included", False))
        gareth_approved = (
            item.get("approval_status") == "approved_by_gareth"
            or item.get("client_ready") is True
            or item.get("human_use_ready") is True
        )
        consent_ready = active_consent_available if candidate_data_included else True
        checklist = {
            "gareth_approval": gareth_approved,
            "client_terms_readiness": terms_ready,
            "payment_readiness": invoice_ready,
            "compliance_readiness": compliance_ready,
            "consent_readiness": consent_ready,
            "deliverable_approved_status": gareth_approved,
            "no_candidate_personal_data_unless_consent_active": consent_ready,
        }
        missing = [
            key for key, passed in checklist.items()
            if not passed
        ]
        delivery_pack = {
            "delivery_id": f"delivery-{item.get('item_id', 'item')}",
            "source_item_id": item.get("item_id"),
            "source_item_type": item.get("item_type", "delivery_item"),
            "title": item.get("title", "Manual delivery item"),
            "delivery_checklist": checklist,
            "missing_checks": missing,
            "manual_delivery_status": "ready_for_manual_delivery" if not missing else "blocked",
            "gareth_approval_required": True,
            "client_email_enabled": False,
            "external_upload_enabled": False,
            "candidate_contact_enabled": False,
            "automatic_sending_enabled": False,
            "human_delivery_only": True,
            "capital_execution": False,
            "autonomous_execution": False,
        }
        delivery_items.append(delivery_pack)

    delivery_ready_items = [
        item for item in delivery_items
        if item.get("manual_delivery_status") == "ready_for_manual_delivery"
    ]
    blocked_delivery_items = [
        item for item in delivery_items
        if item.get("manual_delivery_status") == "blocked"
    ]

    return {
        "engine": "manual_delivery_control_engine",
        "status": "Manual Delivery Control Engine Active",
        "delivery_ready_items": delivery_ready_items,
        "blocked_delivery_items": blocked_delivery_items,
        "delivery_checklist": delivery_items[0].get("delivery_checklist", {}) if delivery_items else {},
        "manual_delivery_status": "ready_for_manual_delivery" if delivery_ready_items else "blocked_pending_manual_checks",
        "pending_delivery_approvals": blocked_delivery_items,
        "dave_recommends_first": {
            "recommendation": "Review blocked delivery checks before Gareth manually sends anything.",
            "human_approval_required": True,
            "capital_execution": False,
        },
        "client_email_enabled": False,
        "external_upload_enabled": False,
        "candidate_contact_enabled": False,
        "automatic_sending_enabled": False,
        "human_delivery_only": True,
        "human_approval_mandatory": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def apply_manual_delivery_action(item, action):
    base = {
        **item,
        "action": action,
        "client_email_enabled": False,
        "external_upload_enabled": False,
        "candidate_contact_enabled": False,
        "automatic_sending_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    }
    if action == "approve":
        return {**base, "manual_delivery_status": "approved_for_manual_delivery"}
    if action == "reject":
        return {**base, "manual_delivery_status": "rejected"}
    if action == "monitor":
        return {**base, "manual_delivery_status": "monitoring"}
    if action == "mark-manually-delivered":
        return {**base, "manual_delivery_status": "delivered_manually_by_gareth"}
    return {**base, "manual_delivery_status": "prepared_pending_gareth_review"}


def build_launch_compliance_validation_engine(
    manual_delivery_control_engine,
    client_terms_drafting_engine,
    invoice_drafting_engine,
    candidate_consent_management_engine,
    compliance_core,
):
    delivery_ready = manual_delivery_control_engine.get("delivery_ready_items", []) or []
    delivery_blocked = manual_delivery_control_engine.get("blocked_delivery_items", []) or []
    delivery_items = delivery_ready + delivery_blocked
    terms_drafts = client_terms_drafting_engine.get("client_terms_drafts", []) or []
    invoice_drafts = invoice_drafting_engine.get("invoice_drafts", []) or []
    active_consents = candidate_consent_management_engine.get("active_candidate_consents", []) or []
    expired_consents = candidate_consent_management_engine.get("expired_candidate_consents", []) or []
    compliance_alerts = compliance_core.get("compliance_alerts", []) or []

    terms_ready = any(
        item.get("gareth_approval_status") == "approved_by_gareth"
        or item.get("terms_readiness_status") == "ready_for_manual_use"
        for item in terms_drafts
    )
    invoice_ready = any(
        item.get("approval_status") == "approved_by_gareth"
        or item.get("invoice_readiness_status") == "ready_for_manual_sending"
        for item in invoice_drafts
    )
    audit_trail_present = bool(
        delivery_items or terms_drafts or invoice_drafts or compliance_alerts
    )
    compliance_profile_assigned = bool(
        compliance_core.get("jurisdiction_compliance_profile")
        or compliance_core.get("jurisdiction_profiles")
    )
    active_consent_available = bool(active_consents)
    expired_consent_present = bool(expired_consents)

    if not delivery_items:
        delivery_items = [
            {
                "delivery_id": "delivery-validation-placeholder",
                "source_item_id": "launch-compliance-placeholder",
                "source_item_type": "launch_compliance_item",
                "title": "Launch compliance validation item",
                "manual_delivery_status": "blocked",
                "gareth_approval_required": True,
                "candidate_personal_data_included": False,
            }
        ]

    validations = []
    for item in delivery_items:
        candidate_data_exposed = bool(item.get("candidate_personal_data_included", False))
        consent_ready = active_consent_available if candidate_data_exposed else True
        manual_delivery_ready = item.get("manual_delivery_status") in {
            "ready_for_manual_delivery",
            "approved_for_manual_delivery",
            "delivered_manually_by_gareth",
        }
        gareth_approval_present = bool(item.get("gareth_approval_required", True))
        approval_ready = item.get("manual_delivery_status") in {
            "ready_for_manual_delivery",
            "approved_for_manual_delivery",
            "delivered_manually_by_gareth",
        }
        jurisdiction_assigned = bool(
            item.get("jurisdiction")
            or item.get("jurisdiction_focus")
            or compliance_profile_assigned
        )
        checks = {
            "candidate_consent_status": consent_ready,
            "candidate_consent_expiry_status": not expired_consent_present,
            "client_terms_status": terms_ready,
            "deliverable_approval_status": approval_ready,
            "invoice_approval_status": invoice_ready,
            "manual_delivery_readiness": manual_delivery_ready,
            "jurisdiction_assigned": jurisdiction_assigned,
            "compliance_profile_assigned": compliance_profile_assigned,
            "audit_trail_present": audit_trail_present,
            "gareth_approval_requirement_present": gareth_approval_present,
            "no_candidate_personal_data_exposed_without_active_consent": consent_ready,
            "no_autonomous_outreach": True,
            "no_autonomous_delivery": True,
            "no_autonomous_fee_proposal": True,
            "no_autonomous_invoicing": True,
            "no_external_integrations_active": True,
        }
        missing = [key for key, passed in checks.items() if not passed]
        if "candidate_consent_status" in missing:
            recommendation = "blocked_missing_consent"
        elif "audit_trail_present" in missing:
            recommendation = "blocked_missing_audit"
        elif "jurisdiction_assigned" in missing:
            recommendation = "blocked_missing_jurisdiction"
        elif "gareth_approval_requirement_present" in missing or "deliverable_approval_status" in missing:
            recommendation = "blocked_missing_approval"
        elif "client_terms_status" in missing:
            recommendation = "blocked_missing_terms"
        elif missing:
            recommendation = "blocked_high_risk"
        else:
            recommendation = "approve_for_human_use"

        risk_level = "low_risk"
        if recommendation.startswith("blocked"):
            risk_level = "blocked"
        elif len(missing) >= 3:
            risk_level = "high_risk"
        elif missing:
            risk_level = "moderate_risk"

        validations.append({
            "validation_id": f"compliance-{item.get('delivery_id', item.get('source_item_id', 'item'))}",
            "source_item_id": item.get("source_item_id"),
            "source_item_type": item.get("source_item_type", "delivery_item"),
            "title": item.get("title", "Launch compliance item"),
            "compliance_validation_checks": checks,
            "missing_compliance_checks": missing,
            "compliance_validation_status": "ready_for_gareth_review" if not missing else "blocked",
            "compliance_recommendation": recommendation,
            "compliance_risk_level": risk_level,
            "gareth_approval_required": True,
            "legal_advice_provided": False,
            "legal_certification_claimed": False,
            "global_legal_compliance_declared": False,
            "external_integrations_enabled": False,
            "capital_execution": False,
            "autonomous_execution": False,
        })

    ready_items = [
        item for item in validations
        if item.get("compliance_validation_status") == "ready_for_gareth_review"
    ]
    blocked_items = [
        item for item in validations
        if item.get("compliance_validation_status") == "blocked"
    ]
    top_item = ready_items[0] if ready_items else (blocked_items[0] if blocked_items else {})

    consent_score = 100 if active_consent_available or not any(
        bool(item.get("candidate_personal_data_included", False)) for item in delivery_items
    ) else 0
    if expired_consent_present:
        consent_score = min(consent_score, 50)
    commercial_score = round(((1 if terms_ready else 0) + (1 if invoice_ready else 0)) / 2 * 100)
    operational_score = 100 if any(
        item.get("manual_delivery_status") in {"ready_for_manual_delivery", "approved_for_manual_delivery"}
        for item in delivery_items
    ) else 40
    governance_score = round(((1 if audit_trail_present else 0) + (1 if compliance_profile_assigned else 0)) / 2 * 100)
    overall_score = round((consent_score + commercial_score + operational_score + governance_score) / 4)

    return {
        "engine": "launch_compliance_validation_engine",
        "status": "Launch Compliance Validation Engine Active",
        "compliance_validation_checks": validations,
        "compliance_ready_items": ready_items,
        "compliance_blocked_items": blocked_items,
        "compliance_validation_status": "ready_for_gareth_review" if ready_items else "blocked_pending_compliance_checks",
        "compliance_recommendation": top_item.get("compliance_recommendation", "monitor"),
        "compliance_risk_level": top_item.get("compliance_risk_level", "blocked"),
        "consent_compliance_score": consent_score,
        "commercial_compliance_score": commercial_score,
        "operational_compliance_score": operational_score,
        "governance_compliance_score": governance_score,
        "overall_compliance_readiness_score": overall_score,
        "dave_recommends_first": {
            "recommendation": "Review compliance validation before any first-client activity.",
            "human_approval_required": True,
            "capital_execution": False,
        },
        "legal_advice_provided": False,
        "legal_certification_claimed": False,
        "global_legal_compliance_declared": False,
        "external_integrations_enabled": False,
        "human_approval_mandatory": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def apply_launch_compliance_action(item, action):
    base = {
        **item,
        "action": action,
        "legal_advice_provided": False,
        "legal_certification_claimed": False,
        "global_legal_compliance_declared": False,
        "external_integrations_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    }
    if action == "approve":
        return {**base, "compliance_validation_status": "approved_for_gareth_consideration"}
    if action == "reject":
        return {**base, "compliance_validation_status": "rejected"}
    if action == "monitor":
        return {**base, "compliance_validation_status": "monitoring"}
    if action == "reset-to-review":
        return {**base, "compliance_validation_status": "pending_review"}
    return {**base, "compliance_validation_status": "validated_pending_gareth_review"}


FIRST_PROSPECT_CATEGORIES = [
    {
        "category": "Boutique Technology & AI Law Firms",
        "sector_focus": "Technology & AI Law",
        "jurisdiction": "England & Wales",
        "revenue_potential_score": 78,
        "ease_of_acquisition_score": 86,
        "launch_readiness_score": 88,
        "market_demand_score": 91,
        "compliance_complexity_score": 76,
        "reason": "High relevance to legal intelligence, clear hiring pain, and easier access than larger firms.",
    },
    {
        "category": "Corporate & M&A Firms",
        "sector_focus": "Corporate & M&A",
        "jurisdiction": "England & Wales",
        "revenue_potential_score": 92,
        "ease_of_acquisition_score": 58,
        "launch_readiness_score": 72,
        "market_demand_score": 82,
        "compliance_complexity_score": 68,
        "reason": "High fee potential, but slower access and stronger incumbent competition.",
    },
    {
        "category": "Commercial Law Firms",
        "sector_focus": "Commercial Law",
        "jurisdiction": "England & Wales",
        "revenue_potential_score": 68,
        "ease_of_acquisition_score": 79,
        "launch_readiness_score": 82,
        "market_demand_score": 74,
        "compliance_complexity_score": 78,
        "reason": "Practical first-client profile with moderate fees and broad hiring needs.",
    },
    {
        "category": "Data Privacy Law Firms",
        "sector_focus": "Data Privacy",
        "jurisdiction": "England & Wales",
        "revenue_potential_score": 74,
        "ease_of_acquisition_score": 80,
        "launch_readiness_score": 84,
        "market_demand_score": 88,
        "compliance_complexity_score": 62,
        "reason": "Strong demand, but privacy-sensitive positioning requires careful consent and compliance handling.",
    },
    {
        "category": "Intellectual Property Firms",
        "sector_focus": "Intellectual Property",
        "jurisdiction": "England & Wales",
        "revenue_potential_score": 72,
        "ease_of_acquisition_score": 72,
        "launch_readiness_score": 78,
        "market_demand_score": 79,
        "compliance_complexity_score": 74,
        "reason": "Specialist hiring demand with manageable first-review positioning.",
    },
    {
        "category": "Legal Technology Companies",
        "sector_focus": "Legal Technology",
        "jurisdiction": "United Kingdom",
        "revenue_potential_score": 64,
        "ease_of_acquisition_score": 82,
        "launch_readiness_score": 86,
        "market_demand_score": 84,
        "compliance_complexity_score": 80,
        "reason": "Good fit for a technology-enhanced message, though placement fee potential may be lower than law firms.",
    },
    {
        "category": "In-House Legal Teams",
        "sector_focus": "In-House Counsel",
        "jurisdiction": "United Kingdom",
        "revenue_potential_score": 70,
        "ease_of_acquisition_score": 55,
        "launch_readiness_score": 66,
        "market_demand_score": 76,
        "compliance_complexity_score": 65,
        "reason": "Relevant demand, but harder access and more internal procurement friction.",
    },
    {
        "category": "Alternative Legal Service Providers",
        "sector_focus": "Alternative Legal Services",
        "jurisdiction": "United Kingdom",
        "revenue_potential_score": 58,
        "ease_of_acquisition_score": 76,
        "launch_readiness_score": 78,
        "market_demand_score": 70,
        "compliance_complexity_score": 82,
        "reason": "Lower fee ceiling, but easier experimentation and lower trust barrier for intelligence-led conversations.",
    },
]


def calculate_first_prospect_score(profile):
    revenue = profile.get("revenue_potential_score", 0)
    acquisition = profile.get("ease_of_acquisition_score", 0)
    readiness = profile.get("launch_readiness_score", 0)
    demand = profile.get("market_demand_score", 0)
    compliance = profile.get("compliance_complexity_score", 0)
    return round(
        revenue * 0.24
        + acquisition * 0.24
        + readiness * 0.22
        + demand * 0.20
        + compliance * 0.10,
        2,
    )


def build_first_prospect_selection_engine(launch_readiness_command_centre, launch_compliance_validation_engine):
    launch_score = launch_readiness_command_centre.get("launch_readiness_score", 0)
    compliance_score = launch_compliance_validation_engine.get("overall_compliance_readiness_score", 0)
    launch_adjustment = round((launch_score + compliance_score) / 20, 2)
    prospect_profiles = []

    for index, profile in enumerate(FIRST_PROSPECT_CATEGORIES, start=1):
        base_score = calculate_first_prospect_score(profile)
        adjusted_score = min(100, round(base_score + launch_adjustment, 2))
        prospect_profiles.append({
            "prospect_id": f"first-prospect-{index:03d}",
            "category": profile["category"],
            "sector_focus": profile["sector_focus"],
            "jurisdiction": profile["jurisdiction"],
            "revenue_potential_score": profile["revenue_potential_score"],
            "ease_of_acquisition_score": profile["ease_of_acquisition_score"],
            "launch_readiness_score": profile["launch_readiness_score"],
            "market_demand_score": profile["market_demand_score"],
            "compliance_complexity_score": profile["compliance_complexity_score"],
            "overall_prospect_score": adjusted_score,
            "launch_priority_score": adjusted_score,
            "reason": profile["reason"],
            "prospect_contact_enabled": False,
            "outreach_enabled": False,
            "candidate_contact_enabled": False,
            "client_contact_enabled": False,
            "external_integrations_enabled": False,
            "scraping_enabled": False,
            "live_data_fetching_enabled": False,
            "human_approval_required": True,
            "capital_execution": False,
            "autonomous_execution": False,
        })

    prospect_rankings = sorted(
        prospect_profiles,
        key=lambda item: item.get("overall_prospect_score", 0),
        reverse=True,
    )
    highest_revenue = max(
        prospect_profiles,
        key=lambda item: item.get("revenue_potential_score", 0),
    )
    fastest_revenue = max(
        prospect_profiles,
        key=lambda item: (
            item.get("ease_of_acquisition_score", 0)
            + item.get("launch_readiness_score", 0)
        ),
    )
    highest_probability = max(
        prospect_profiles,
        key=lambda item: (
            item.get("ease_of_acquisition_score", 0)
            + item.get("market_demand_score", 0)
            + item.get("compliance_complexity_score", 0)
        ),
    )
    recommended = prospect_rankings[0]

    return {
        "engine": "first_prospect_selection_engine",
        "status": "First Prospect Selection Engine Active",
        "prospect_profiles": prospect_profiles,
        "prospect_rankings": prospect_rankings,
        "prospect_recommendations": {
            "highest_revenue_prospect": highest_revenue,
            "fastest_revenue_prospect": fastest_revenue,
            "highest_probability_prospect": highest_probability,
            "recommended_first_prospect": recommended,
        },
        "launch_priority_score": recommended.get("launch_priority_score", 0),
        "highest_revenue_prospect": highest_revenue,
        "fastest_revenue_prospect": fastest_revenue,
        "highest_probability_prospect": highest_probability,
        "recommended_first_prospect": recommended,
        "dave_recommends_first": {
            "recommendation": f"Start launch preparation with {recommended.get('category')}.",
            "reason": recommended.get("reason"),
            "human_approval_required": True,
            "capital_execution": False,
        },
        "prospect_contact_enabled": False,
        "outreach_enabled": False,
        "candidate_contact_enabled": False,
        "client_contact_enabled": False,
        "external_integrations_enabled": False,
        "scraping_enabled": False,
        "live_data_fetching_enabled": False,
        "human_approval_mandatory": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def build_first_client_dry_run(
    first_prospect_selection_engine,
    intelligence_review_engine,
    deliverable_factory,
    client_terms_drafting_engine,
    invoice_drafting_engine,
    candidate_consent_management_engine,
    manual_delivery_control_engine,
    launch_compliance_validation_engine,
):
    selected_prospect = first_prospect_selection_engine.get("recommended_first_prospect") or {}
    latest_review = intelligence_review_engine.get("latest_generated_review") or {}
    latest_deliverable = deliverable_factory.get("latest_deliverable") or {}
    terms_drafts = client_terms_drafting_engine.get("client_terms_drafts", []) or []
    invoice_drafts = invoice_drafting_engine.get("invoice_drafts", []) or []
    consent_records = candidate_consent_management_engine.get("candidate_consent_records", []) or []
    delivery_ready = manual_delivery_control_engine.get("delivery_ready_items", []) or []
    delivery_blocked = manual_delivery_control_engine.get("blocked_delivery_items", []) or []
    compliance_ready = launch_compliance_validation_engine.get("compliance_ready_items", []) or []
    compliance_blocked = launch_compliance_validation_engine.get("compliance_blocked_items", []) or []

    terms_draft = terms_drafts[0] if terms_drafts else {}
    invoice_draft = invoice_drafts[0] if invoice_drafts else {}
    consent_record = consent_records[0] if consent_records else {}
    delivery_pack = delivery_ready[0] if delivery_ready else (delivery_blocked[0] if delivery_blocked else {})
    compliance_validation = compliance_ready[0] if compliance_ready else (compliance_blocked[0] if compliance_blocked else {})

    dry_run_artifacts = {
        "selected_prospect": selected_prospect,
        "intelligence_review": {
            "artifact_id": latest_review.get("review_id"),
            "title": latest_review.get("title"),
            "status": intelligence_review_engine.get("review_generation_status", "not_generated"),
            "generated": bool(latest_review),
        },
        "client_deliverable": {
            "artifact_id": latest_deliverable.get("deliverable_id"),
            "title": latest_deliverable.get("title"),
            "status": deliverable_factory.get("deliverable_status", "not_generated"),
            "generated": bool(latest_deliverable),
        },
        "client_terms_draft": {
            "artifact_id": terms_draft.get("terms_id"),
            "title": terms_draft.get("terms_type"),
            "status": client_terms_drafting_engine.get("terms_readiness_status", "not_generated"),
            "generated": bool(terms_draft),
        },
        "invoice_draft": {
            "artifact_id": invoice_draft.get("invoice_number"),
            "title": invoice_draft.get("service_description"),
            "status": invoice_drafting_engine.get("invoice_readiness_status", "not_generated"),
            "generated": bool(invoice_draft),
        },
        "candidate_consent_validation": {
            "artifact_id": consent_record.get("candidate_id"),
            "status": candidate_consent_management_engine.get("consent_readiness_status", "not_checked"),
            "executed": bool(consent_records),
        },
        "manual_delivery_pack": {
            "artifact_id": delivery_pack.get("delivery_id"),
            "status": manual_delivery_control_engine.get("manual_delivery_status", "not_prepared"),
            "generated": bool(delivery_pack),
        },
        "launch_compliance_validation": {
            "artifact_id": compliance_validation.get("validation_id"),
            "status": launch_compliance_validation_engine.get("compliance_validation_status", "not_validated"),
            "executed": bool(compliance_validation),
        },
    }

    step_checks = {
        "recommended_first_prospect_selected": bool(selected_prospect),
        "intelligence_review_generated": bool(latest_review),
        "client_deliverable_generated": bool(latest_deliverable),
        "client_terms_draft_generated": bool(terms_draft),
        "invoice_draft_generated": bool(invoice_draft),
        "candidate_consent_validation_executed": bool(consent_records),
        "manual_delivery_pack_prepared": bool(delivery_pack),
        "launch_compliance_validation_executed": bool(compliance_validation),
        "gareth_approval_package_created": True,
        "final_dry_run_report_generated": True,
    }

    blockers = []
    warnings = []
    if not selected_prospect:
        blockers.append("missing_recommended_first_prospect")
    if not latest_review:
        blockers.append("missing_intelligence_review")
    if not latest_deliverable:
        blockers.append("missing_client_deliverable")
    if not terms_draft:
        blockers.append("missing_client_terms_draft")
    if not invoice_draft:
        blockers.append("missing_invoice_draft")
    if not consent_records:
        blockers.append("missing_candidate_consent_validation")
    if not delivery_pack:
        blockers.append("missing_manual_delivery_pack")
    if not compliance_validation:
        blockers.append("missing_launch_compliance_validation")

    for item in delivery_blocked:
        for missing in item.get("missing_checks", []) or []:
            warnings.append(f"manual_delivery_{missing}")
    for item in compliance_blocked:
        for missing in item.get("missing_compliance_checks", []) or []:
            warnings.append(f"launch_compliance_{missing}")

    passed_steps = sum(1 for passed in step_checks.values() if passed)
    dry_run_readiness_score = round(passed_steps / len(step_checks) * 100)
    approval_package = {
        "package_id": "glirn-first-client-dry-run-package-001",
        "selected_prospect_id": selected_prospect.get("prospect_id"),
        "review_id": latest_review.get("review_id"),
        "deliverable_id": latest_deliverable.get("deliverable_id"),
        "terms_id": terms_draft.get("terms_id"),
        "invoice_number": invoice_draft.get("invoice_number"),
        "delivery_id": delivery_pack.get("delivery_id"),
        "validation_id": compliance_validation.get("validation_id"),
        "approval_readiness_status": "ready_for_gareth_approval" if not blockers else "blocked_missing_artifacts",
        "gareth_approval_required": True,
        "external_action_enabled": False,
    }
    dry_run_status = (
        "completed_pending_gareth_approval"
        if approval_package["approval_readiness_status"] == "ready_for_gareth_approval"
        else "blocked_missing_artifacts"
    )
    recommended_next_action = (
        "Gareth should review the assembled approval package and decide whether to monitor, reject, or approve a human-only next step."
        if dry_run_status == "completed_pending_gareth_approval"
        else "Resolve missing dry-run artifacts before controlled launch planning."
    )
    dry_run_report = {
        "selected_prospect": selected_prospect.get("category", "No prospect selected"),
        "prospect_score": selected_prospect.get("overall_prospect_score", 0),
        "intelligence_review_status": dry_run_artifacts["intelligence_review"]["status"],
        "deliverable_status": dry_run_artifacts["client_deliverable"]["status"],
        "terms_status": dry_run_artifacts["client_terms_draft"]["status"],
        "invoice_status": dry_run_artifacts["invoice_draft"]["status"],
        "consent_status": dry_run_artifacts["candidate_consent_validation"]["status"],
        "delivery_pack_status": dry_run_artifacts["manual_delivery_pack"]["status"],
        "compliance_validation_status": dry_run_artifacts["launch_compliance_validation"]["status"],
        "approval_readiness_status": approval_package["approval_readiness_status"],
        "blockers": blockers,
        "warnings": sorted(set(warnings)),
        "readiness_score": dry_run_readiness_score,
        "recommended_next_action": recommended_next_action,
    }

    return {
        "engine": "first_client_dry_run",
        "status": "First Client Dry Run Complete" if dry_run_status == "completed_pending_gareth_approval" else "First Client Dry Run Blocked",
        "first_client_dry_run": True,
        "dry_run_status": dry_run_status,
        "dry_run_report": dry_run_report,
        "latest_dry_run_report": dry_run_report,
        "dry_run_artifacts": dry_run_artifacts,
        "gareth_approval_package": approval_package,
        "dry_run_readiness_score": dry_run_readiness_score,
        "dry_run_blockers": blockers,
        "dry_run_warnings": sorted(set(warnings)),
        "approval_readiness_status": approval_package["approval_readiness_status"],
        "outreach_enabled": False,
        "client_contact_enabled": False,
        "candidate_contact_enabled": False,
        "candidate_introduction_enabled": False,
        "delivery_enabled": False,
        "invoice_sending_enabled": False,
        "payment_collection_enabled": False,
        "external_integrations_enabled": False,
        "scraping_enabled": False,
        "live_data_fetching_enabled": False,
        "human_approval_mandatory": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def apply_first_client_dry_run_action(dry_run, action):
    base = {
        **dry_run,
        "action": action,
        "outreach_enabled": False,
        "client_contact_enabled": False,
        "candidate_contact_enabled": False,
        "candidate_introduction_enabled": False,
        "delivery_enabled": False,
        "invoice_sending_enabled": False,
        "payment_collection_enabled": False,
        "external_integrations_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    }
    if action == "approve":
        return {**base, "dry_run_status": "approved_by_gareth_for_human_review"}
    if action == "reject":
        return {**base, "dry_run_status": "rejected_by_gareth"}
    if action == "monitor":
        return {**base, "dry_run_status": "monitoring"}
    if action == "reset":
        return {**base, "dry_run_status": "reset_pending_new_dry_run"}
    return {**base, "dry_run_status": "run_completed_pending_gareth_approval"}


def build_autonomous_internal_operations_orchestrator(
    legal_opportunity_radar,
    first_prospect_selection_engine,
    revenue_command_centre,
    intelligence_review_engine,
    deliverable_factory,
    client_terms_drafting_engine,
    invoice_drafting_engine,
    candidate_consent_management_engine,
    launch_compliance_validation_engine,
    manual_delivery_control_engine,
    first_client_dry_run,
):
    top_opportunity = legal_opportunity_radar.get("top_opportunity") or {}
    selected_prospect = first_prospect_selection_engine.get("recommended_first_prospect") or {}
    highest_revenue = revenue_command_centre.get("highest_fee_opportunity") or {}
    fastest_revenue = revenue_command_centre.get("fastest_revenue_opportunity") or {}
    latest_review = intelligence_review_engine.get("latest_generated_review") or {}
    latest_deliverable = deliverable_factory.get("latest_deliverable") or {}
    terms_draft = (client_terms_drafting_engine.get("client_terms_drafts", []) or [{}])[0]
    invoice_draft = (invoice_drafting_engine.get("invoice_drafts", []) or [{}])[0]
    consent_status = candidate_consent_management_engine.get("consent_readiness_status", "not_checked")
    compliance_status = launch_compliance_validation_engine.get("compliance_validation_status", "not_validated")
    delivery_status = manual_delivery_control_engine.get("manual_delivery_status", "not_prepared")
    dry_run_status = first_client_dry_run.get("dry_run_status", "not_run")
    dry_run_blockers = first_client_dry_run.get("dry_run_blockers", []) or []
    dry_run_warnings = first_client_dry_run.get("dry_run_warnings", []) or []
    compliance_blockers = []
    for item in launch_compliance_validation_engine.get("compliance_blocked_items", []) or []:
        compliance_blockers.extend(item.get("missing_compliance_checks", []) or [])
    delivery_warnings = []
    for item in manual_delivery_control_engine.get("blocked_delivery_items", []) or []:
        delivery_warnings.extend(item.get("missing_checks", []) or [])

    blockers = sorted(set(dry_run_blockers))
    warnings = sorted(set(dry_run_warnings + [
        f"launch_compliance_{item}" for item in compliance_blockers
    ] + [
        f"manual_delivery_{item}" for item in delivery_warnings
    ]))
    expected_revenue = (
        highest_revenue.get("estimated_revenue")
        or highest_revenue.get("expected_fee_value")
        or fastest_revenue.get("estimated_value")
        or 500
    )
    approval_readiness = first_client_dry_run.get("approval_readiness_status", "required")
    final_recommendation = "approve" if (
        dry_run_status == "completed_pending_gareth_approval"
        and approval_readiness == "ready_for_gareth_approval"
        and not blockers
    ) else "monitor"
    if blockers:
        final_recommendation = "reject"

    final_package = {
        "package_id": "glirn-autonomous-final-package-001",
        "recommended_prospect_profile": selected_prospect,
        "recommended_offer": "GLIRN Senior Legal Hiring Intelligence Review",
        "expected_revenue": expected_revenue,
        "revenue_route": "Paid intelligence review with potential conversion into search mandate",
        "top_opportunity": top_opportunity,
        "intelligence_review_status": intelligence_review_engine.get("review_generation_status", "not_generated"),
        "deliverable_status": deliverable_factory.get("deliverable_status", "not_generated"),
        "terms_status": client_terms_drafting_engine.get("terms_readiness_status", "not_generated"),
        "invoice_status": invoice_drafting_engine.get("invoice_readiness_status", "not_generated"),
        "consent_status": consent_status,
        "compliance_status": compliance_status,
        "delivery_pack_status": delivery_status,
        "dry_run_status": dry_run_status,
        "review_id": latest_review.get("review_id"),
        "deliverable_id": latest_deliverable.get("deliverable_id"),
        "terms_id": terms_draft.get("terms_id"),
        "invoice_number": invoice_draft.get("invoice_number"),
        "blockers": blockers,
        "warnings": warnings,
        "final_recommendation": final_recommendation,
        "gareth_final_decision_required": True,
        "external_action_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    }
    recommendation_queue = [
        {
            "queue_id": "glirn-autonomous-recommendation-001",
            "package_id": final_package["package_id"],
            "recommendation": final_recommendation,
            "reason": "Internal cycle assembled the final Gareth approval package from existing GLIRN engines.",
            "gareth_final_decision_required": True,
        }
    ]

    return {
        "engine": "autonomous_internal_operations_orchestrator",
        "status": "Autonomous Internal Operations Cycle Complete",
        "autonomous_cycle_status": "completed_pending_gareth_final_decision" if final_package else "blocked",
        "autonomous_recommendation_queue": recommendation_queue,
        "final_gareth_approval_packages": [final_package],
        "autonomous_blockers": blockers,
        "autonomous_warnings": warnings,
        "dave_recommends_first": {
            "recommendation": f"Gareth should {final_recommendation} the final internal approval package.",
            "package_id": final_package["package_id"],
            "human_approval_required": True,
            "capital_execution": False,
        },
        "analysis_enabled": True,
        "ranking_enabled": True,
        "generation_enabled": True,
        "preparation_enabled": True,
        "validation_enabled": True,
        "unsafe_item_blocking_enabled": True,
        "client_contact_enabled": False,
        "candidate_contact_enabled": False,
        "deliverable_sending_enabled": False,
        "invoice_sending_enabled": False,
        "payment_collection_enabled": False,
        "contract_acceptance_enabled": False,
        "external_fee_proposal_enabled": False,
        "external_integrations_enabled": False,
        "scraping_enabled": False,
        "live_data_fetching_enabled": False,
        "human_approval_mandatory": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def apply_autonomous_internal_operations_action(orchestrator, action):
    base = {
        **orchestrator,
        "action": action,
        "client_contact_enabled": False,
        "candidate_contact_enabled": False,
        "deliverable_sending_enabled": False,
        "invoice_sending_enabled": False,
        "payment_collection_enabled": False,
        "contract_acceptance_enabled": False,
        "external_fee_proposal_enabled": False,
        "external_integrations_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    }
    if action == "approve-final-package":
        return {**base, "autonomous_cycle_status": "final_package_approved_by_gareth"}
    if action == "reject-final-package":
        return {**base, "autonomous_cycle_status": "final_package_rejected_by_gareth"}
    if action == "monitor-final-package":
        return {**base, "autonomous_cycle_status": "final_package_monitoring"}
    if action == "reset-cycle":
        return {**base, "autonomous_cycle_status": "reset_pending_new_cycle"}
    return {**base, "autonomous_cycle_status": "cycle_run_completed_pending_gareth_final_decision"}


def classify_public_lead_prospect_type(lead):
    sector = str(lead.get("legal_sector", "")).lower()
    practice_area = str(lead.get("practice_area", "")).lower()
    organisation = str(lead.get("organisation", "")).lower()
    hiring_need = str(lead.get("hiring_need", "")).lower()
    combined = " ".join([sector, practice_area, organisation, hiring_need])
    if "technology" in combined or "ai" in combined:
        return "Boutique Technology & AI Law Firms"
    if "corporate" in combined or "m&a" in combined or "merger" in combined:
        return "Corporate & M&A Firms"
    if "privacy" in combined or "data" in combined:
        return "Data Privacy Law Firms"
    if "intellectual" in combined or "ip" in combined:
        return "Intellectual Property Firms"
    if "in-house" in combined or "legal team" in combined:
        return "In-House Legal Teams"
    return "Specialist Legal Practices"


def classify_public_lead_type(lead):
    inquiry_type = str(lead.get("inquiry_type", "")).lower()
    need = str(lead.get("hiring_need", "")).lower()
    seniority = str(lead.get("seniority_level", "")).lower()
    career_stage = str(lead.get("career_stage", "")).lower()
    combined = " ".join([inquiry_type, need, seniority, career_stage])
    if (
        "newly qualified" in combined
        or "future legal leader" in combined
        or "future legal" in combined
        or re.search(r"\bnq\b", combined)
        or "rising legal talent" in combined
    ):
        return "future_legal_leader_candidate_lead"
    if (
        "senior legal professional" in combined
        or "career discussion" in combined
        or "partner career" in combined
        or "general counsel career" in combined
        or "legal director career" in combined
    ):
        return "senior_legal_candidate_lead"
    if "candidate" in combined:
        return "candidate_lead"
    if "intelligence" in combined or "review" in combined:
        return "intelligence_review_lead"
    if "executive" in combined or "partner" in combined or "general counsel" in combined or "chief legal officer" in combined or "clo" in combined:
        return "executive_search_lead"
    if "law firm" in combined or "legal team" in combined or "client" in combined or "hire" in combined or "search" in combined:
        return "client_lead"
    return "general_enquiry"


def route_public_lead(lead_type):
    routes = {
        "client_lead": "client_hiring_review",
        "candidate_lead": "candidate_confidential_review",
        "senior_legal_candidate_lead": "senior_legal_candidate_confidential_review",
        "future_legal_leader_candidate_lead": "future_legal_leader_confidential_review",
        "intelligence_review_lead": "gbp_500_intelligence_review",
        "executive_search_lead": "executive_search_review",
        "general_enquiry": "manual_triage",
    }
    return routes.get(lead_type, "manual_triage")


def calculate_public_lead_revenue_potential(lead):
    seniority = str(lead.get("seniority_level", "")).lower()
    need = str(lead.get("hiring_need", "")).lower()
    sector = str(lead.get("legal_sector", "")).lower()
    lead_type = classify_public_lead_type(lead)
    score = 50
    if "partner" in seniority or "general counsel" in seniority or "chief legal officer" in seniority:
        score += 25
    elif "senior" in seniority or "legal director" in seniority:
        score += 15
    if "search" in need or "hire" in need or "recruit" in need:
        score += 15
    if "technology" in sector or "ai" in sector or "corporate" in sector:
        score += 10
    if lead_type == "intelligence_review_lead":
        score += 8
    if lead_type == "executive_search_lead":
        score += 12
    if lead_type in {
        "candidate_lead",
        "senior_legal_candidate_lead",
        "future_legal_leader_candidate_lead",
    }:
        score -= 10
    return min(score, 100)


def build_public_lead_record(lead, index=1):
    lead_id = lead.get("lead_id") or f"public-lead-{index:03d}"
    prospect_type = classify_public_lead_prospect_type(lead)
    lead_type = classify_public_lead_type(lead)
    lead_route = route_public_lead(lead_type)
    revenue_score = calculate_public_lead_revenue_potential(lead)
    consent_confirmed = bool(lead.get("consent"))
    qualification_status = "qualified_for_gareth_review" if consent_confirmed else "blocked_missing_consent"
    compliance_status = "controlled_review_ready" if consent_confirmed else "blocked_missing_consent"
    recommended_action = "convert-to-approval-package" if consent_confirmed and revenue_score >= 65 else "monitor"
    if not consent_confirmed:
        recommended_action = "reject"
    elif lead_type in {
        "candidate_lead",
        "senior_legal_candidate_lead",
        "future_legal_leader_candidate_lead",
    }:
        recommended_action = "monitor"

    return {
        "lead_id": lead_id,
        "name": lead.get("name", ""),
        "organisation": lead.get("organisation", ""),
        "email": lead.get("email", ""),
        "country": lead.get("country", ""),
        "inquiry_type": lead.get("inquiry_type", ""),
        "legal_sector": lead.get("legal_sector", ""),
        "practice_area": lead.get("practice_area", ""),
        "jurisdiction": lead.get("jurisdiction", ""),
        "career_stage": lead.get("career_stage", ""),
        "confidential_career_interest": lead.get("confidential_career_interest", ""),
        "hiring_need": lead.get("hiring_need", ""),
        "seniority_level": lead.get("seniority_level", ""),
        "timescale": lead.get("timescale", ""),
        "message": lead.get("message", ""),
        "consent": consent_confirmed,
        "lead_type": lead_type,
        "lead_route": lead_route,
        "prospect_type": prospect_type,
        "lead_qualification_status": qualification_status,
        "lead_revenue_potential": revenue_score,
        "lead_compliance_status": compliance_status,
        "lead_approval_package_status": "ready_for_gareth_review" if consent_confirmed else "blocked_missing_consent",
        "recommended_action": recommended_action,
        "gareth_final_approval_required": True,
        "automatic_email_enabled": False,
        "automatic_linkedin_messaging_enabled": False,
        "automatic_introductions_enabled": False,
        "client_contact_enabled": False,
        "candidate_contact_enabled": False,
        "invoice_issuing_enabled": False,
        "payment_collection_enabled": False,
        "contract_acceptance_enabled": False,
        "external_integrations_enabled": False,
        "scraping_enabled": False,
        "live_data_fetching_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def build_website_lead_intake_engine(public_leads=None, autonomous_internal_operations_orchestrator=None):
    public_leads = public_leads or []
    records = [
        build_public_lead_record(lead, index)
        for index, lead in enumerate(public_leads, start=1)
    ]
    qualified = [
        lead for lead in records
        if lead.get("lead_qualification_status") == "qualified_for_gareth_review"
    ]
    pending_approvals = [
        lead for lead in records
        if lead.get("lead_approval_package_status") == "ready_for_gareth_review"
    ]
    latest = records[-1] if records else {}
    final_packages = (
        autonomous_internal_operations_orchestrator or {}
    ).get("final_gareth_approval_packages", []) or []
    approval_package = {
        "package_id": f"glirn-public-lead-package-{latest.get('lead_id', 'none')}",
        "lead_id": latest.get("lead_id"),
        "prospect_type": latest.get("prospect_type"),
        "recommended_offer": "GLIRN Senior Legal Hiring Intelligence Review",
        "expected_revenue": 500 if latest else 0,
        "lead_revenue_potential": latest.get("lead_revenue_potential", 0),
        "source_internal_package": (final_packages[0].get("package_id") if final_packages else None),
        "approval_status": latest.get("lead_approval_package_status", "no_public_lead"),
        "gareth_final_approval_required": True,
        "external_action_enabled": False,
    }
    recommendation = {
        "lead_id": latest.get("lead_id"),
        "recommended_action": latest.get("recommended_action", "monitor"),
        "reason": "Public enquiry classified and scored for Gareth final review." if latest else "No public lead received.",
        "gareth_final_approval_required": True,
    }

    return {
        "engine": "website_lead_intake_engine",
        "status": "Website Lead Intake Engine Active",
        "public_leads": records,
        "qualified_public_leads": qualified,
        "pending_public_lead_approvals": pending_approvals,
        "lead_qualification_status": latest.get("lead_qualification_status", "no_public_leads"),
        "lead_revenue_potential": latest.get("lead_revenue_potential", 0),
        "lead_compliance_status": latest.get("lead_compliance_status", "no_public_leads"),
        "lead_approval_package_status": latest.get("lead_approval_package_status", "no_public_leads"),
        "latest_public_lead_recommendation": recommendation,
        "latest_lead": latest,
        "gareth_approval_package": approval_package,
        "automatic_email_enabled": False,
        "client_contact_enabled": False,
        "candidate_contact_enabled": False,
        "invoice_issuing_enabled": False,
        "payment_collection_enabled": False,
        "contract_acceptance_enabled": False,
        "external_integrations_enabled": False,
        "scraping_enabled": False,
        "live_data_fetching_enabled": False,
        "human_approval_mandatory": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def apply_public_lead_action(lead, action):
    base = {
        **lead,
        "action": action,
        "automatic_email_enabled": False,
        "client_contact_enabled": False,
        "candidate_contact_enabled": False,
        "invoice_issuing_enabled": False,
        "payment_collection_enabled": False,
        "contract_acceptance_enabled": False,
        "external_integrations_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    }
    if action == "approve":
        return {**base, "lead_approval_package_status": "approved_by_gareth_for_manual_action"}
    if action == "reject":
        return {**base, "lead_approval_package_status": "rejected_by_gareth"}
    if action == "monitor":
        return {**base, "lead_approval_package_status": "monitoring"}
    return {**base, "lead_approval_package_status": "converted_to_final_approval_package"}


def suggested_glirn_service_for_lead(lead):
    lead_type = lead.get("lead_type")
    lead_route = lead.get("lead_route")
    if lead_route == "gbp_500_intelligence_review" or lead_type == "intelligence_review_lead":
        return "GBP 500 Senior Legal Hiring Intelligence Review"
    if lead_route == "executive_search_review" or lead_type == "executive_search_lead":
        return "Executive Search"
    if lead_type == "candidate_lead":
        return "Candidate Introduction"
    if lead_type == "senior_legal_candidate_lead":
        return "Executive Search Candidate Match Potential"
    if lead_type == "future_legal_leader_candidate_lead":
        return "Candidate Pipeline Relationship"
    return "General Advisory Follow-Up"


def estimate_revenue_for_public_lead(lead):
    service = suggested_glirn_service_for_lead(lead)
    if service == "GBP 500 Senior Legal Hiring Intelligence Review":
        return 500
    if service == "Executive Search":
        return 25000
    if service in {
        "Candidate Introduction",
        "Executive Search Candidate Match Potential",
        "Candidate Pipeline Relationship",
    }:
        return 0
    return 500


def calculate_public_lead_urgency_score(lead):
    timescale = str(lead.get("timescale", "")).lower()
    if "immediate" in timescale:
        return 90
    if "1-3" in timescale or "1 to 3" in timescale:
        return 75
    if "3-6" in timescale or "3 to 6" in timescale:
        return 55
    if "exploratory" in timescale:
        return 35
    return 50


def calculate_public_lead_confidence_score(lead):
    fields = [
        "organisation",
        "email",
        "country",
        "legal_sector",
        "practice_area",
        "jurisdiction",
        "hiring_need",
        "seniority_level",
        "timescale",
        "message",
    ]
    completed = sum(1 for field in fields if lead.get(field))
    consent_bonus = 10 if lead.get("consent") else 0
    return min(100, round(completed / len(fields) * 90) + consent_bonus)


def build_revenue_approval_package_for_lead(lead):
    suggested_service = suggested_glirn_service_for_lead(lead)
    estimated_revenue = estimate_revenue_for_public_lead(lead)
    urgency_score = calculate_public_lead_urgency_score(lead)
    confidence_score = calculate_public_lead_confidence_score(lead)
    recommended_action = "approve"
    if not lead.get("consent"):
        recommended_action = "needs_more_info"
    elif lead.get("lead_type") in {
        "candidate_lead",
        "senior_legal_candidate_lead",
        "future_legal_leader_candidate_lead",
    }:
        recommended_action = "monitor"
    elif confidence_score < 60:
        recommended_action = "needs_more_info"

    return {
        "package_id": f"glirn-revenue-approval-{lead.get('lead_id', 'unknown')}",
        "lead_id": lead.get("lead_id"),
        "lead_name": lead.get("name"),
        "lead_email": lead.get("email"),
        "organisation": lead.get("organisation"),
        "lead_type": lead.get("lead_type"),
        "lead_route": lead.get("lead_route"),
        "practice_area": lead.get("practice_area") or lead.get("legal_sector"),
        "jurisdiction": lead.get("jurisdiction") or lead.get("country"),
        "seniority": lead.get("seniority_level"),
        "timescale": lead.get("timescale"),
        "estimated_revenue_opportunity": estimated_revenue,
        "urgency_score": urgency_score,
        "confidence_score": confidence_score,
        "recommended_next_action": recommended_action,
        "suggested_glirn_service": suggested_service,
        "opportunity_type": (
            "relationship_building_opportunity"
            if lead.get("lead_type") == "future_legal_leader_candidate_lead"
            else "candidate_pipeline_opportunity"
            if lead.get("lead_type") in {"candidate_lead", "senior_legal_candidate_lead"}
            else "revenue_opportunity"
        ),
        "gareth_approval_status": "awaiting_review",
        "automatic_client_contact_enabled": False,
        "automatic_invoice_sending_enabled": False,
        "automatic_linkedin_messaging_enabled": False,
        "automatic_introductions_enabled": False,
        "candidate_information_sharing_enabled": False,
        "money_movement_enabled": False,
        "payment_collection_enabled": False,
        "external_integrations_enabled": False,
        "scraping_enabled": False,
        "live_data_fetching_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def build_revenue_approval_engine(website_lead_intake_engine):
    leads = website_lead_intake_engine.get("public_leads", []) or []
    packages = [
        build_revenue_approval_package_for_lead(lead)
        for lead in leads
    ]
    latest_package = packages[-1] if packages else {}
    ready = [
        package for package in packages
        if package.get("gareth_approval_status") == "awaiting_review"
    ]

    return {
        "engine": "revenue_approval_engine",
        "status": "Revenue Approval Engine Active",
        "revenue_approval_packages": packages,
        "ready_for_gareth_approval": ready,
        "latest_revenue_opportunity": latest_package,
        "latest_revenue_opportunity_status": latest_package.get("gareth_approval_status", "no_public_leads"),
        "dave_recommends": {
            "recommendation": latest_package.get("recommended_next_action", "monitor"),
            "suggested_service": latest_package.get("suggested_glirn_service", "No lead received"),
            "estimated_fee": latest_package.get("estimated_revenue_opportunity", 0),
            "gareth_approval_required": True,
        },
        "automatic_client_contact_enabled": False,
        "automatic_invoice_sending_enabled": False,
        "money_movement_enabled": False,
        "payment_collection_enabled": False,
        "external_integrations_enabled": False,
        "automatic_linkedin_messaging_enabled": False,
        "automatic_introductions_enabled": False,
        "candidate_information_sharing_enabled": False,
        "human_approval_mandatory": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def build_client_response_draft_for_revenue_package(package):
    service = package.get("suggested_glirn_service", "General Advisory Follow-Up")
    organisation = package.get("organisation") or "your organisation"
    practice_area = package.get("practice_area") or "your legal hiring area"
    jurisdiction = package.get("jurisdiction") or "your jurisdiction"

    draft_opening = (
        f"Thank you for your enquiry to GLIRN regarding {practice_area} support "
        f"for {organisation}."
    )
    service_lines = {
        "GBP 500 Senior Legal Hiring Intelligence Review": (
            "Based on the information provided, the recommended first step is a "
            "GBP 500 GLIRN Senior Legal Hiring Intelligence Review. This would "
            "help clarify the hiring priority, market difficulty, likely search "
            "route, and practical next steps before any recruitment activity begins."
        ),
        "Executive Search": (
            "Based on the information provided, GLIRN can assist with executive "
            "legal search support for senior roles such as Partner, General Counsel, "
            "Chief Legal Officer, Legal Director, or equivalent senior legal positions."
        ),
        "Candidate Introduction": (
            "Based on the information provided, GLIRN can consider whether a "
            "confidential candidate introduction route is appropriate. Candidate "
            "details would only ever be used where the required consent and approval "
            "controls are in place."
        ),
        "General Advisory Follow-Up": (
            "Based on the information provided, the recommended next step is a "
            "general advisory follow-up to understand the hiring need, jurisdiction, "
            "seniority level, and whether GLIRN can assist with legal hiring "
            "intelligence or search support."
        ),
    }
    proposed_next_step = (
        "The proposed next step is for Gareth to review this response draft and, "
        "if approved, for David Sanson to follow up manually with the prospect."
    )
    safety_note = (
        "This response does not provide legal advice, does not guarantee any "
        "placement outcome, and does not create any automatic client contact, "
        "invoice sending, contract acceptance, or payment activity."
    )

    return {
        "draft_id": f"glirn-client-response-{package.get('package_id', 'unknown')}",
        "package_id": package.get("package_id"),
        "lead_id": package.get("lead_id"),
        "organisation": organisation,
        "suggested_service": service,
        "recommended_next_action": package.get("recommended_next_action", "monitor"),
        "draft_status": "awaiting_gareth_approval",
        "draft_ready_status": "draft_ready",
        "subject": f"GLIRN enquiry follow-up - {service}",
        "draft_body": "\n\n".join([
            draft_opening,
            service_lines.get(service, service_lines["General Advisory Follow-Up"]),
            f"GLIRN can assist with senior legal hiring intelligence or search support in {jurisdiction}.",
            proposed_next_step,
            safety_note,
        ]),
        "professional_glirn_tone": True,
        "no_legal_advice_claims": True,
        "no_guaranteed_placement_claims": True,
        "gareth_approval_required": True,
        "automatic_sending_enabled": False,
        "automatic_email_enabled": False,
        "client_contact_enabled": False,
        "external_integrations_enabled": False,
        "local_draft_only": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def build_client_response_draft_engine(revenue_approval_engine):
    packages = revenue_approval_engine.get("revenue_approval_packages", []) or []
    drafts = [
        build_client_response_draft_for_revenue_package(package)
        for package in packages
    ]
    latest_draft = drafts[-1] if drafts else {}

    return {
        "engine": "client_response_draft_engine",
        "status": "Client Response Draft Ready" if drafts else "No Client Response Drafts",
        "client_response_drafts": drafts,
        "client_response_draft_ready": latest_draft,
        "pending_client_response_approvals": [
            draft for draft in drafts
            if draft.get("draft_status") == "awaiting_gareth_approval"
        ],
        "latest_client_response_draft": latest_draft,
        "draft_generation_status": latest_draft.get("draft_status", "no_revenue_package"),
        "automatic_sending_enabled": False,
        "automatic_email_enabled": False,
        "client_contact_enabled": False,
        "external_integrations_enabled": False,
        "human_approval_mandatory": True,
        "local_draft_only": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def fee_basis_for_glirn_service(service):
    if service == "GBP 500 Senior Legal Hiring Intelligence Review":
        return "fixed fee"
    if service == "Executive Search":
        return "retained search fee"
    if service == "Candidate Introduction":
        return "success fee"
    return "advisory follow-up fee"


def build_fee_proposal_pack_for_revenue_package(package, response_draft=None):
    service = package.get("suggested_glirn_service", "General Advisory Follow-Up")
    estimated_fee = package.get("estimated_revenue_opportunity", 0)
    fee_basis = fee_basis_for_glirn_service(service)
    organisation = package.get("organisation") or "your organisation"
    practice_area = package.get("practice_area") or "your legal hiring area"
    jurisdiction = package.get("jurisdiction") or "your jurisdiction"
    response_draft = response_draft or {}

    scope_by_service = {
        "GBP 500 Senior Legal Hiring Intelligence Review": (
            "Prepare a senior legal hiring intelligence review covering hiring "
            "priority, role viability, market difficulty, likely search route, "
            "jurisdiction context, and recommended next steps."
        ),
        "Executive Search": (
            "Prepare an executive legal search proposal for senior legal hiring, "
            "including role focus, search rationale, retained/search fee position, "
            "and manual next-step approval requirements."
        ),
        "Candidate Introduction": (
            "Prepare a candidate introduction proposal framework, subject to active "
            "candidate consent, client terms readiness, and Gareth approval before "
            "any candidate details are used."
        ),
        "General Advisory Follow-Up": (
            "Prepare a limited advisory follow-up scope to clarify the prospect's "
            "hiring need, practice area, jurisdiction, seniority level, and whether "
            "GLIRN can assist."
        ),
    }
    proposal_draft = (
        f"GLIRN proposes {service} for {organisation}.\n\n"
        f"Scope: {scope_by_service.get(service, scope_by_service['General Advisory Follow-Up'])}\n\n"
        f"Fee basis: {fee_basis}. Estimated fee: GBP {estimated_fee}.\n\n"
        f"GLIRN can assist with senior legal hiring intelligence or search support "
        f"for {practice_area} in {jurisdiction}. This proposal does not provide "
        f"legal advice, does not guarantee a placement, and remains subject to "
        f"Gareth approval before any client-facing use."
    )

    return {
        "proposal_pack_id": f"glirn-fee-proposal-{package.get('package_id', 'unknown')}",
        "package_id": package.get("package_id"),
        "draft_id": response_draft.get("draft_id"),
        "lead_id": package.get("lead_id"),
        "organisation": organisation,
        "suggested_glirn_service": service,
        "estimated_fee": estimated_fee,
        "fee_basis": fee_basis,
        "proposed_scope_summary": scope_by_service.get(service, scope_by_service["General Advisory Follow-Up"]),
        "client_facing_proposal_draft": proposal_draft,
        "payment_signoff_note": (
            "Gareth must approve the proposal before any client-facing use. "
            "Invoices, payment requests, billing sign-off, and money movement "
            "remain manual and cannot be triggered by GLIRN."
        ),
        "proposal_status": "awaiting_review",
        "gareth_approval_status": "awaiting_review",
        "gareth_approval_required": True,
        "local_proposal_only": True,
        "invoice_sent": False,
        "payment_request_sent": False,
        "money_movement_enabled": False,
        "client_contact_enabled": False,
        "external_integrations_enabled": False,
        "automatic_invoice_sending_enabled": False,
        "automatic_payment_collection_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def build_fee_proposal_pack_engine(revenue_approval_engine, client_response_draft_engine):
    packages = revenue_approval_engine.get("revenue_approval_packages", []) or []
    drafts = client_response_draft_engine.get("client_response_drafts", []) or []
    drafts_by_package_id = {
        draft.get("package_id"): draft
        for draft in drafts
    }
    proposal_packs = [
        build_fee_proposal_pack_for_revenue_package(
            package,
            drafts_by_package_id.get(package.get("package_id")),
        )
        for package in packages
    ]
    latest_pack = proposal_packs[-1] if proposal_packs else {}

    return {
        "engine": "fee_proposal_pack_engine",
        "status": "Fee Proposal Pack Ready" if proposal_packs else "No Fee Proposal Packs",
        "fee_proposal_packs": proposal_packs,
        "fee_proposal_pack_ready": latest_pack,
        "pending_fee_proposal_approvals": [
            pack for pack in proposal_packs
            if pack.get("proposal_status") == "awaiting_review"
        ],
        "latest_fee_proposal_pack": latest_pack,
        "proposal_generation_status": latest_pack.get("proposal_status", "no_revenue_package"),
        "invoice_sent": False,
        "payment_request_sent": False,
        "money_movement_enabled": False,
        "client_contact_enabled": False,
        "external_integrations_enabled": False,
        "local_proposal_only": True,
        "human_approval_mandatory": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def build_final_approval_object(revenue_package, response_draft=None, fee_proposal_pack=None):
    response_draft = response_draft or {}
    fee_proposal_pack = fee_proposal_pack or {}
    estimated_fee = fee_proposal_pack.get(
        "estimated_fee",
        revenue_package.get("estimated_revenue_opportunity", 0),
    )
    suggested_service = fee_proposal_pack.get(
        "suggested_glirn_service",
        revenue_package.get("suggested_glirn_service", "General Advisory Follow-Up"),
    )

    return {
        "final_approval_id": f"glirn-final-approval-{revenue_package.get('package_id', 'unknown')}",
        "package_id": revenue_package.get("package_id"),
        "draft_id": response_draft.get("draft_id"),
        "proposal_pack_id": fee_proposal_pack.get("proposal_pack_id"),
        "lead_id": revenue_package.get("lead_id"),
        "lead_name": revenue_package.get("lead_name"),
        "lead_email": revenue_package.get("lead_email"),
        "organisation": revenue_package.get("organisation"),
        "lead_route": revenue_package.get("lead_route"),
        "suggested_service": suggested_service,
        "estimated_fee": estimated_fee,
        "recommended_next_action": revenue_package.get("recommended_next_action", "monitor"),
        "dave_recommends": revenue_package.get("recommended_next_action", "monitor"),
        "revenue_approval_package": revenue_package,
        "client_response_draft": response_draft,
        "fee_proposal_pack": fee_proposal_pack,
        "final_approval_status": "awaiting_gareth_decision",
        "safety_statement": (
            "No client contact, invoice, payment request, or money movement occurs "
            "without Gareth approval."
        ),
        "gareth_final_decision_required": True,
        "client_contact_enabled": False,
        "invoice_sending_enabled": False,
        "payment_request_enabled": False,
        "money_movement_enabled": False,
        "automatic_email_enabled": False,
        "external_integrations_enabled": False,
        "local_state_only": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def build_final_approval_command_centre(
    revenue_approval_engine,
    client_response_draft_engine,
    fee_proposal_pack_engine,
):
    revenue_packages = revenue_approval_engine.get("revenue_approval_packages", []) or []
    response_drafts = client_response_draft_engine.get("client_response_drafts", []) or []
    fee_packs = fee_proposal_pack_engine.get("fee_proposal_packs", []) or []
    response_by_package_id = {
        draft.get("package_id"): draft
        for draft in response_drafts
    }
    fee_pack_by_package_id = {
        pack.get("package_id"): pack
        for pack in fee_packs
    }
    approval_objects = [
        build_final_approval_object(
            package,
            response_by_package_id.get(package.get("package_id")),
            fee_pack_by_package_id.get(package.get("package_id")),
        )
        for package in revenue_packages
    ]
    latest_object = approval_objects[-1] if approval_objects else {}

    return {
        "engine": "final_approval_command_centre",
        "status": "Gareth Final Approval Required" if approval_objects else "No Final Approvals Pending",
        "final_approval_objects": approval_objects,
        "gareth_final_approval_required": [
            item for item in approval_objects
            if item.get("final_approval_status") == "awaiting_gareth_decision"
        ],
        "latest_final_approval_object": latest_object,
        "approval_actions_supported": [
            "approve",
            "reject",
            "needs_more_information",
        ],
        "safety_statement": (
            "No client contact, invoice, payment request, or money movement occurs "
            "without Gareth approval."
        ),
        "client_contact_enabled": False,
        "invoice_sending_enabled": False,
        "payment_request_enabled": False,
        "money_movement_enabled": False,
        "automatic_email_enabled": False,
        "external_integrations_enabled": False,
        "local_state_only": True,
        "human_approval_mandatory": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def apply_final_approval_action(final_approval_object, action):
    status_by_action = {
        "approve": "approved_by_gareth",
        "reject": "rejected_by_gareth",
        "needs_more_information": "needs_more_information",
    }
    result = dict(final_approval_object)
    result["final_approval_status"] = status_by_action[action]
    result["last_local_action"] = action
    result["client_contact_enabled"] = False
    result["invoice_sending_enabled"] = False
    result["payment_request_enabled"] = False
    result["money_movement_enabled"] = False
    result["automatic_email_enabled"] = False
    result["external_integrations_enabled"] = False
    result["local_state_only"] = True
    result["capital_execution"] = False
    result["autonomous_execution"] = False
    return result


def build_client_contact_readiness_object(final_approval_object):
    final_status = final_approval_object.get("final_approval_status", "awaiting_gareth_decision")
    contact_status = (
        "ready_after_gareth_approval"
        if final_status == "approved_by_gareth"
        else "blocked_pending_gareth_approval"
    )
    fee_pack = final_approval_object.get("fee_proposal_pack", {}) or {}

    return {
        "contact_readiness_id": f"glirn-client-contact-{final_approval_object.get('final_approval_id', 'unknown')}",
        "final_approval_id": final_approval_object.get("final_approval_id"),
        "lead_id": final_approval_object.get("lead_id"),
        "lead_name": final_approval_object.get("lead_name"),
        "lead_email": final_approval_object.get("lead_email"),
        "suggested_service": final_approval_object.get("suggested_service"),
        "approved_client_response_draft": final_approval_object.get("client_response_draft", {}),
        "fee_proposal_summary": {
            "suggested_service": fee_pack.get("suggested_glirn_service", final_approval_object.get("suggested_service")),
            "estimated_fee": fee_pack.get("estimated_fee", final_approval_object.get("estimated_fee", 0)),
            "fee_basis": fee_pack.get("fee_basis"),
            "proposal_status": fee_pack.get("proposal_status"),
        },
        "final_approval_status": final_status,
        "contact_status": contact_status,
        "approval_required": True,
        "gareth_approval_gate": final_status == "approved_by_gareth",
        "local_only_safety_note": (
            "Client contact preparation is local-only. No real email, Gmail, SMTP, "
            "external client contact, or integration is enabled."
        ),
        "real_email_sent": False,
        "client_contact_executed": False,
        "gmail_smtp_connected": False,
        "external_integrations_enabled": False,
        "local_log_only": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def build_approved_client_contact_engine(final_approval_command_centre):
    final_objects = final_approval_command_centre.get("final_approval_objects", []) or []
    readiness_objects = [
        build_client_contact_readiness_object(final_object)
        for final_object in final_objects
    ]
    latest_readiness = readiness_objects[-1] if readiness_objects else {}

    return {
        "engine": "approved_client_contact_engine",
        "status": "Approved Client Contact Ready" if readiness_objects else "No Client Contact Items",
        "client_contact_readiness": readiness_objects,
        "blocked_client_contacts": [
            item for item in readiness_objects
            if item.get("contact_status") == "blocked_pending_gareth_approval"
        ],
        "ready_client_contacts": [
            item for item in readiness_objects
            if item.get("contact_status") == "ready_after_gareth_approval"
        ],
        "latest_client_contact_readiness": latest_readiness,
        "local_only_safety_note": (
            "No real email, Gmail, SMTP, external client contact, or integration is enabled."
        ),
        "real_email_sent": False,
        "client_contact_executed": False,
        "gmail_smtp_connected": False,
        "external_integrations_enabled": False,
        "local_log_only": True,
        "human_approval_mandatory": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def apply_client_contact_action(contact_readiness_object, action):
    if action != "mark_approved_contact_ready":
        raise ValueError("unsupported client contact action")
    if contact_readiness_object.get("final_approval_status") != "approved_by_gareth":
        raise ValueError("final approval must be approved_by_gareth before contact can be marked ready")

    result = dict(contact_readiness_object)
    result["contact_status"] = "contact_logged_local_only"
    result["last_local_action"] = action
    result["real_email_sent"] = False
    result["client_contact_executed"] = False
    result["gmail_smtp_connected"] = False
    result["external_integrations_enabled"] = False
    result["local_log_only"] = True
    result["capital_execution"] = False
    result["autonomous_execution"] = False
    return result


def build_email_draft_export_object(final_approval_object):
    final_status = final_approval_object.get("final_approval_status", "awaiting_gareth_decision")
    response_draft = final_approval_object.get("client_response_draft", {}) or {}
    fee_pack = final_approval_object.get("fee_proposal_pack", {}) or {}
    export_status = (
        "draft_export_ready"
        if final_status == "approved_by_gareth"
        else "blocked_pending_gareth_approval"
    )

    return {
        "email_draft_export_id": f"glirn-email-draft-{final_approval_object.get('final_approval_id', 'unknown')}",
        "final_approval_id": final_approval_object.get("final_approval_id"),
        "lead_id": final_approval_object.get("lead_id"),
        "to_email": final_approval_object.get("lead_email"),
        "lead_name": final_approval_object.get("lead_name"),
        "subject": response_draft.get(
            "subject",
            f"GLIRN enquiry follow-up - {final_approval_object.get('suggested_service', 'GLIRN')}",
        ),
        "approved_response_body": response_draft.get("draft_body", ""),
        "fee_proposal_summary": {
            "suggested_service": fee_pack.get("suggested_glirn_service", final_approval_object.get("suggested_service")),
            "estimated_fee": fee_pack.get("estimated_fee", final_approval_object.get("estimated_fee", 0)),
            "fee_basis": fee_pack.get("fee_basis"),
        },
        "suggested_glirn_service": final_approval_object.get("suggested_service"),
        "final_approval_status": final_status,
        "export_status": export_status,
        "local_only_note": "No email has been sent. Gareth must manually review and send.",
        "email_sent": False,
        "gmail_smtp_connected": False,
        "external_integrations_enabled": False,
        "local_file_only": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def build_email_draft_export_engine(final_approval_command_centre):
    final_objects = final_approval_command_centre.get("final_approval_objects", []) or []
    exports = [
        build_email_draft_export_object(final_object)
        for final_object in final_objects
    ]
    latest_export = exports[-1] if exports else {}

    return {
        "engine": "email_draft_export_engine",
        "status": "Approved Email Draft Export Ready" if exports else "No Email Draft Exports",
        "email_draft_exports": exports,
        "blocked_email_draft_exports": [
            item for item in exports
            if item.get("export_status") == "blocked_pending_gareth_approval"
        ],
        "ready_email_draft_exports": [
            item for item in exports
            if item.get("export_status") == "draft_export_ready"
        ],
        "latest_email_draft_export": latest_export,
        "local_only_note": "No email has been sent. Gareth must manually review and send.",
        "email_sent": False,
        "gmail_smtp_connected": False,
        "external_integrations_enabled": False,
        "local_file_only": True,
        "human_approval_mandatory": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def apply_email_draft_export_action(email_draft_export_object, action, file_path=None):
    if action != "export_approved_email_draft":
        raise ValueError("unsupported email draft export action")
    if email_draft_export_object.get("final_approval_status") != "approved_by_gareth":
        raise ValueError("final approval must be approved_by_gareth before email draft export")

    result = dict(email_draft_export_object)
    result["export_status"] = "exported_local_only"
    result["local_file_path"] = file_path
    result["email_sent"] = False
    result["gmail_smtp_connected"] = False
    result["external_integrations_enabled"] = False
    result["local_file_only"] = True
    result["capital_execution"] = False
    result["autonomous_execution"] = False
    return result


def build_invoice_draft_export_object(final_approval_object):
    final_status = final_approval_object.get("final_approval_status", "awaiting_gareth_decision")
    fee_pack = final_approval_object.get("fee_proposal_pack", {}) or {}
    invoice_status = (
        "invoice_draft_ready"
        if final_status == "approved_by_gareth"
        else "blocked_pending_gareth_approval"
    )

    return {
        "invoice_draft_export_id": f"glirn-invoice-draft-{final_approval_object.get('final_approval_id', 'unknown')}",
        "final_approval_id": final_approval_object.get("final_approval_id"),
        "lead_id": final_approval_object.get("lead_id"),
        "client_name": final_approval_object.get("organisation") or final_approval_object.get("lead_name"),
        "client_email": final_approval_object.get("lead_email"),
        "suggested_glirn_service": fee_pack.get("suggested_glirn_service", final_approval_object.get("suggested_service")),
        "estimated_fee": fee_pack.get("estimated_fee", final_approval_object.get("estimated_fee", 0)),
        "fee_basis": fee_pack.get("fee_basis"),
        "scope_summary": fee_pack.get("proposed_scope_summary", ""),
        "payment_signoff_note": fee_pack.get(
            "payment_signoff_note",
            "Gareth must manually review and send. No invoice or payment request has been sent.",
        ),
        "final_approval_status": final_status,
        "invoice_status": invoice_status,
        "local_only_note": "No invoice or payment request has been sent. Gareth must manually review and send.",
        "invoice_sent": False,
        "payment_request_sent": False,
        "money_movement_enabled": False,
        "external_integrations_enabled": False,
        "local_file_only": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def build_invoice_draft_export_engine(final_approval_command_centre):
    final_objects = final_approval_command_centre.get("final_approval_objects", []) or []
    exports = [
        build_invoice_draft_export_object(final_object)
        for final_object in final_objects
    ]
    latest_export = exports[-1] if exports else {}

    return {
        "engine": "invoice_draft_export_engine",
        "status": "Invoice Draft Export Ready" if exports else "No Invoice Draft Exports",
        "invoice_draft_exports": exports,
        "blocked_invoice_draft_exports": [
            item for item in exports
            if item.get("invoice_status") == "blocked_pending_gareth_approval"
        ],
        "ready_invoice_draft_exports": [
            item for item in exports
            if item.get("invoice_status") == "invoice_draft_ready"
        ],
        "latest_invoice_draft_export": latest_export,
        "local_only_note": "No invoice or payment request has been sent. Gareth must manually review and send.",
        "invoice_sent": False,
        "payment_request_sent": False,
        "money_movement_enabled": False,
        "external_integrations_enabled": False,
        "local_file_only": True,
        "human_approval_mandatory": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def apply_invoice_draft_export_action(invoice_draft_export_object, action, file_path=None):
    if action != "export_approved_invoice_draft":
        raise ValueError("unsupported invoice draft export action")
    if invoice_draft_export_object.get("final_approval_status") != "approved_by_gareth":
        raise ValueError("final approval must be approved_by_gareth before invoice draft export")

    result = dict(invoice_draft_export_object)
    result["invoice_status"] = "exported_local_only"
    result["local_file_path"] = file_path
    result["invoice_sent"] = False
    result["payment_request_sent"] = False
    result["money_movement_enabled"] = False
    result["external_integrations_enabled"] = False
    result["local_file_only"] = True
    result["capital_execution"] = False
    result["autonomous_execution"] = False
    return result


def build_deal_pack_export_object(final_approval_object):
    final_status = final_approval_object.get("final_approval_status", "awaiting_gareth_decision")
    fee_pack = final_approval_object.get("fee_proposal_pack", {}) or {}
    response_draft = final_approval_object.get("client_response_draft", {}) or {}
    deal_pack_status = (
        "deal_pack_ready"
        if final_status == "approved_by_gareth"
        else "blocked_pending_gareth_approval"
    )

    return {
        "deal_pack_export_id": f"glirn-deal-pack-{final_approval_object.get('final_approval_id', 'unknown')}",
        "final_approval_id": final_approval_object.get("final_approval_id"),
        "lead_id": final_approval_object.get("lead_id"),
        "client_name": final_approval_object.get("organisation") or final_approval_object.get("lead_name"),
        "client_email": final_approval_object.get("lead_email"),
        "lead_name": final_approval_object.get("lead_name"),
        "lead_route": final_approval_object.get("lead_route"),
        "suggested_glirn_service": fee_pack.get("suggested_glirn_service", final_approval_object.get("suggested_service")),
        "estimated_fee": fee_pack.get("estimated_fee", final_approval_object.get("estimated_fee", 0)),
        "fee_basis": fee_pack.get("fee_basis"),
        "dave_recommendation": final_approval_object.get("dave_recommends"),
        "approved_client_response_draft": response_draft,
        "fee_proposal_pack": fee_pack,
        "invoice_draft_summary": {
            "client_name": final_approval_object.get("organisation") or final_approval_object.get("lead_name"),
            "client_email": final_approval_object.get("lead_email"),
            "suggested_glirn_service": fee_pack.get("suggested_glirn_service", final_approval_object.get("suggested_service")),
            "estimated_fee": fee_pack.get("estimated_fee", final_approval_object.get("estimated_fee", 0)),
            "fee_basis": fee_pack.get("fee_basis"),
            "scope_summary": fee_pack.get("proposed_scope_summary", ""),
            "payment_signoff_note": fee_pack.get("payment_signoff_note", ""),
        },
        "safety_statement": (
            "No client contact, invoice, payment request, or money movement has occurred. "
            "Gareth must manually review and act."
        ),
        "final_approval_status": final_status,
        "deal_pack_status": deal_pack_status,
        "local_only_note": (
            "No client contact, invoice, payment request, or money movement has occurred. "
            "Gareth must manually review and act."
        ),
        "client_contact_executed": False,
        "invoice_sent": False,
        "payment_request_sent": False,
        "money_movement_enabled": False,
        "external_integrations_enabled": False,
        "local_file_only": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def build_deal_pack_export_engine(final_approval_command_centre):
    final_objects = final_approval_command_centre.get("final_approval_objects", []) or []
    exports = [
        build_deal_pack_export_object(final_object)
        for final_object in final_objects
    ]
    latest_export = exports[-1] if exports else {}

    return {
        "engine": "deal_pack_export_engine",
        "status": "Complete Deal Pack Ready" if exports else "No Deal Packs",
        "deal_pack_exports": exports,
        "blocked_deal_pack_exports": [
            item for item in exports
            if item.get("deal_pack_status") == "blocked_pending_gareth_approval"
        ],
        "ready_deal_pack_exports": [
            item for item in exports
            if item.get("deal_pack_status") == "deal_pack_ready"
        ],
        "latest_deal_pack_export": latest_export,
        "local_only_note": (
            "No client contact, invoice, payment request, or money movement has occurred. "
            "Gareth must manually review and act."
        ),
        "client_contact_executed": False,
        "invoice_sent": False,
        "payment_request_sent": False,
        "money_movement_enabled": False,
        "external_integrations_enabled": False,
        "local_file_only": True,
        "human_approval_mandatory": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def apply_deal_pack_export_action(deal_pack_export_object, action, file_path=None):
    if action != "export_approved_deal_pack":
        raise ValueError("unsupported deal pack export action")
    if deal_pack_export_object.get("final_approval_status") != "approved_by_gareth":
        raise ValueError("final approval must be approved_by_gareth before deal pack export")

    result = dict(deal_pack_export_object)
    result["deal_pack_status"] = "exported_local_only"
    result["local_file_path"] = file_path
    result["client_contact_executed"] = False
    result["invoice_sent"] = False
    result["payment_request_sent"] = False
    result["money_movement_enabled"] = False
    result["external_integrations_enabled"] = False
    result["local_file_only"] = True
    result["capital_execution"] = False
    result["autonomous_execution"] = False
    return result


def revenue_stage_for_record(final_approval_object, email_export, invoice_export, deal_pack_export, stage_override=None):
    if stage_override:
        return stage_override
    if deal_pack_export.get("deal_pack_status") == "exported_local_only":
        return "deal_pack_exported"
    if final_approval_object.get("final_approval_status") == "approved_by_gareth":
        return "approved_by_gareth"
    if final_approval_object:
        return "approval_ready"
    return "new_lead"


def build_revenue_ledger_record(
    final_approval_object,
    email_export=None,
    invoice_export=None,
    deal_pack_export=None,
    stage_override=None,
):
    email_export = email_export or {}
    invoice_export = invoice_export or {}
    deal_pack_export = deal_pack_export or {}
    fee_pack = final_approval_object.get("fee_proposal_pack", {}) or {}
    record_id = f"glirn-revenue-ledger-{final_approval_object.get('final_approval_id', 'unknown')}"

    return {
        "ledger_record_id": record_id,
        "final_approval_id": final_approval_object.get("final_approval_id"),
        "lead_client_name": final_approval_object.get("organisation") or final_approval_object.get("lead_name"),
        "client_email": final_approval_object.get("lead_email"),
        "lead_route": final_approval_object.get("lead_route"),
        "suggested_glirn_service": fee_pack.get("suggested_glirn_service", final_approval_object.get("suggested_service")),
        "estimated_fee": fee_pack.get("estimated_fee", final_approval_object.get("estimated_fee", 0)),
        "fee_basis": fee_pack.get("fee_basis"),
        "final_approval_status": final_approval_object.get("final_approval_status", "awaiting_gareth_decision"),
        "email_draft_export_status": email_export.get("export_status", "blocked_pending_gareth_approval"),
        "invoice_draft_export_status": invoice_export.get("invoice_status", "blocked_pending_gareth_approval"),
        "deal_pack_export_status": deal_pack_export.get("deal_pack_status", "blocked_pending_gareth_approval"),
        "revenue_stage": revenue_stage_for_record(
            final_approval_object,
            email_export,
            invoice_export,
            deal_pack_export,
            stage_override=stage_override,
        ),
        "actual_revenue_received": 0,
        "manual_payment_confirmation_required": True,
        "payment_collection_enabled": False,
        "money_movement_enabled": False,
        "invoice_sending_enabled": False,
        "client_contact_enabled": False,
        "external_integrations_enabled": False,
        "local_tracking_only": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def build_revenue_ledger_engine(
    final_approval_command_centre,
    email_draft_export_engine,
    invoice_draft_export_engine,
    deal_pack_export_engine,
    stage_overrides=None,
):
    stage_overrides = stage_overrides or {}
    final_objects = final_approval_command_centre.get("final_approval_objects", []) or []
    email_by_final_id = {
        item.get("final_approval_id"): item
        for item in email_draft_export_engine.get("email_draft_exports", []) or []
    }
    invoice_by_final_id = {
        item.get("final_approval_id"): item
        for item in invoice_draft_export_engine.get("invoice_draft_exports", []) or []
    }
    deal_pack_by_final_id = {
        item.get("final_approval_id"): item
        for item in deal_pack_export_engine.get("deal_pack_exports", []) or []
    }
    records = [
        build_revenue_ledger_record(
            final_object,
            email_by_final_id.get(final_object.get("final_approval_id")),
            invoice_by_final_id.get(final_object.get("final_approval_id")),
            deal_pack_by_final_id.get(final_object.get("final_approval_id")),
            stage_override=stage_overrides.get(final_object.get("final_approval_id")),
        )
        for final_object in final_objects
    ]
    latest_record = records[-1] if records else {}

    return {
        "engine": "revenue_ledger_engine",
        "status": "GLIRN Revenue Ledger Active",
        "revenue_ledger_records": records,
        "latest_revenue_ledger_record": latest_record,
        "estimated_pipeline_value": sum(float(record.get("estimated_fee", 0) or 0) for record in records),
        "actual_revenue_recorded": sum(float(record.get("actual_revenue_received", 0) or 0) for record in records),
        "latest_revenue_stage": latest_record.get("revenue_stage", "new_lead"),
        "manual_payment_confirmation_required": True,
        "payment_collection_enabled": False,
        "money_movement_enabled": False,
        "invoice_sending_enabled": False,
        "client_contact_enabled": False,
        "external_integrations_enabled": False,
        "local_tracking_only": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def apply_revenue_ledger_action(ledger_record, action):
    stage_by_action = {
        "mark_manually_sent_by_gareth": "manually_sent_by_gareth",
        "mark_payment_pending_manual": "payment_pending_manual",
        "mark_paid_manual_confirmation": "paid_manual_confirmation_required",
    }
    result = dict(ledger_record)
    result["revenue_stage"] = stage_by_action[action]
    result["last_local_action"] = action
    result["actual_revenue_received"] = ledger_record.get("actual_revenue_received", 0)
    result["manual_payment_confirmation_required"] = True
    result["payment_collection_enabled"] = False
    result["money_movement_enabled"] = False
    result["invoice_sending_enabled"] = False
    result["client_contact_enabled"] = False
    result["external_integrations_enabled"] = False
    result["local_tracking_only"] = True
    result["capital_execution"] = False
    result["autonomous_execution"] = False
    return result


def build_gareth_command_centre(
    opportunities,
    website_lead_intake_engine,
    revenue_approval_engine,
    fee_proposal_pack_engine,
    final_approval_command_centre,
    revenue_ledger_engine,
):
    revenue_packages = revenue_approval_engine.get("revenue_approval_packages", []) or []
    package_opportunities = [
        {
            "opportunity_id": package.get("package_id"),
            "client_firm_name": package.get("organisation") or package.get("lead_name") or "Unknown enquiry",
            "suggested_glirn_service": package.get("suggested_glirn_service", "General Advisory Follow-Up"),
            "estimated_fee": float(package.get("estimated_revenue_opportunity", 0) or 0),
            "priority_level": (
                "High" if package.get("urgency_score", 0) >= 75
                else "Medium" if package.get("urgency_score", 0) >= 50
                else "Low"
            ),
            "status": (
                package.get("opportunity_type")
                if package.get("opportunity_type") in {
                    "relationship_building_opportunity",
                    "candidate_pipeline_opportunity",
                }
                else package.get("gareth_approval_status", "awaiting_review")
            ),
            "opportunity_type": package.get("opportunity_type", "revenue_opportunity"),
            "expected_fee_value": float(package.get("estimated_revenue_opportunity", 0) or 0),
            "confidence_score": float(package.get("confidence_score", 0) or 0),
            "client_quality": float(package.get("confidence_score", 0) or 0),
            "candidate_quality": 0,
            "dave_recommendation": package.get("recommended_next_action", "monitor"),
            "recommendation_reason": (
                "Candidate relationship requires Gareth review; no candidate details are shared without consent."
                if package.get("opportunity_type") in {
                    "relationship_building_opportunity",
                    "candidate_pipeline_opportunity",
                }
                else f"{package.get('suggested_glirn_service', 'GLIRN service')} with "
                f"{package.get('confidence_score', 0)}% enquiry confidence and "
                f"{package.get('urgency_score', 0)}% urgency."
            ),
        }
        for package in revenue_packages
    ]
    existing_opportunities = [
        {
            "opportunity_id": item.get("opportunity_id"),
            "client_firm_name": (item.get("client_firm", {}) or {}).get("name", "Unknown firm"),
            "suggested_glirn_service": "Executive Search",
            "estimated_fee": float(item.get("expected_fee_value", 0) or 0),
            "priority_level": (
                "High" if item.get("overall_glirn_score", 0) >= 75
                else "Medium" if item.get("overall_glirn_score", 0) >= 55
                else "Low"
            ),
            "status": item.get("status", "pending_human_approval"),
            "opportunity_type": "revenue_opportunity",
            "expected_fee_value": float(item.get("expected_fee_value", 0) or 0),
            "confidence_score": round(float(item.get("placement_probability", 0) or 0) * 100, 2),
            "client_quality": float(item.get("client_quality", 0) or 0),
            "candidate_quality": float(item.get("candidate_quality", 0) or 0),
            "dave_recommendation": "Prioritise for final review",
            "recommendation_reason": (
                f"Strong fee potential with {item.get('client_quality', 0)} client quality, "
                f"{item.get('candidate_quality', 0)} candidate quality, and "
                f"{round(float(item.get('placement_probability', 0) or 0) * 100, 2)}% confidence."
            ),
        }
        for item in opportunities
    ]
    revenue_opportunities = sorted(
        package_opportunities + existing_opportunities,
        key=lambda item: item.get("estimated_fee", 0),
        reverse=True,
    )

    approval_items = [
        {
            "final_approval_id": item.get("final_approval_id"),
            "client_firm_name": item.get("organisation") or item.get("lead_name") or "Unknown enquiry",
            "recommended_action": item.get("dave_recommends", "monitor"),
            "estimated_fee": float(item.get("estimated_fee", 0) or 0),
            "final_approval_status": item.get("final_approval_status", "awaiting_gareth_decision"),
        }
        for item in final_approval_command_centre.get("final_approval_objects", []) or []
        if item.get("final_approval_status", "awaiting_gareth_decision") == "awaiting_gareth_decision"
    ]
    approval_items.sort(key=lambda item: item.get("estimated_fee", 0), reverse=True)

    recommendations = sorted(
        revenue_opportunities,
        key=lambda item: (
            item.get("expected_fee_value", 0),
            item.get("confidence_score", 0),
            item.get("client_quality", 0),
            item.get("candidate_quality", 0),
        ),
        reverse=True,
    )[:3]
    fee_packs = fee_proposal_pack_engine.get("fee_proposal_packs", []) or []
    ledger_records = revenue_ledger_engine.get("revenue_ledger_records", []) or []

    return {
        "engine": "gareth_command_centre",
        "status": "Gareth Command Centre Active",
        "default_view": "gareth_command_centre",
        "advanced_view_available": True,
        "revenue_opportunities": revenue_opportunities,
        "awaiting_gareth_approval": approval_items,
        "revenue_pipeline_summary": {
            "total_enquiries": len(website_lead_intake_engine.get("public_leads", []) or []),
            "awaiting_approval": len(approval_items),
            "approved_opportunities": sum(
                1 for item in final_approval_command_centre.get("final_approval_objects", []) or []
                if item.get("final_approval_status") == "approved_by_gareth"
            ),
            "proposal_packs_ready": len(fee_packs),
            "revenue_received": sum(float(item.get("actual_revenue_received", 0) or 0) for item in ledger_records),
            "pipeline_value": sum(float(item.get("estimated_fee", 0) or 0) for item in revenue_opportunities),
        },
        "dave_recommends": recommendations,
        "client_contact_enabled": False,
        "automatic_linkedin_messaging_enabled": False,
        "automatic_introductions_enabled": False,
        "candidate_information_sharing_enabled": False,
        "invoice_sending_enabled": False,
        "payment_collection_enabled": False,
        "money_movement_enabled": False,
        "external_integrations_enabled": False,
        "human_approval_mandatory": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def build_enquiry_notification_summary(notification_records, enquiry_count=0):
    records = list(notification_records or [])
    failures = [item for item in records if item.get("delivery_status") != "sent"]
    sent = [item for item in records if item.get("delivery_status") == "sent"]
    return {
        "new_enquiry_count": int(enquiry_count or 0),
        "notification_count": len(records),
        "notifications_sent": len(sent),
        "notification_failures_requiring_attention": failures,
        "notification_failure_count": len(failures),
        "latest_notification_status": records[-1].get("delivery_status") if records else "not_attempted",
        "manual_resend_available": bool(failures),
        "informational_only": True,
        "automatic_acceptance_enabled": False,
        "automatic_payment_enabled": False,
        "automatic_brief_generation_enabled": False,
        "automatic_candidate_outreach_enabled": False,
        "automatic_search_activity_enabled": False,
        "automatic_delivery_enabled": False,
        "external_integrations_enabled": False,
        "human_review_mandatory": True,
    }


def build_multi_agent_review_summary(review_records):
    records = list(review_records or [])
    escalated = [item for item in records if item.get("escalation_required")]
    cleared = [
        item for item in records
        if item.get("review_complete") and not item.get("escalation_required")
    ]
    return {
        "review_count": len(records),
        "completed_review_count": sum(1 for item in records if item.get("review_complete")),
        "cleared_review_count": len(cleared),
        "escalated_review_count": len(escalated),
        "escalated_reviews": escalated,
        "latest_review_status": records[-1].get("review_status") if records else "not_started",
        "delivery_blocked": bool(escalated) or not records,
        "mission_106_approval_required": True,
        "multi_agent_review_required": True,
        "gareth_final_approval_required": True,
        "automatic_acceptance_enabled": False,
        "automatic_payment_enabled": False,
        "automatic_candidate_outreach_enabled": False,
        "automatic_search_activity_enabled": False,
        "automatic_delivery_enabled": False,
        "external_commitments_enabled": False,
    }


def build_confidence_assessment_summary(assessment_records):
    records = list(assessment_records or [])
    escalated = [item for item in records if item.get("escalation_required")]
    cleared = [
        item for item in records
        if item.get("assessment_complete") and not item.get("escalation_required")
    ]
    latest = records[-1] if records else {}
    return {
        "assessment_count": len(records),
        "completed_assessment_count": sum(1 for item in records if item.get("assessment_complete")),
        "cleared_assessment_count": len(cleared),
        "escalated_assessment_count": len(escalated),
        "escalated_assessments": escalated,
        "latest_confidence_score": latest.get("confidence_score"),
        "latest_confidence_category": latest.get("confidence_category", "not_assessed"),
        "latest_evidence_sufficiency_rating": latest.get("evidence_sufficiency_rating"),
        "latest_reviewer_agreement_level": (latest.get("reviewer_agreement") or {}).get("level", "not_assessed"),
        "latest_outstanding_limitations": latest.get("outstanding_limitations", []),
        "latest_escalation_status": latest.get("assessment_status", "not_started"),
        "delivery_blocked": not records or bool(escalated),
        "mission_106_approval_required": True,
        "mission_109_review_required": True,
        "mission_110_assessment_required": True,
        "gareth_final_approval_required": True,
        "gareth_override_allowed": False,
        "automatic_acceptance_enabled": False,
        "automatic_payment_enabled": False,
        "automatic_candidate_outreach_enabled": False,
        "automatic_search_activity_enabled": False,
        "automatic_delivery_enabled": False,
        "external_commitments_enabled": False,
    }


def build_global_intelligence_summary(validation_records):
    records = list(validation_records or [])
    escalated = [item for item in records if item.get("escalation_required")]
    cleared = [
        item for item in records
        if item.get("validation_complete") and not item.get("escalation_required")
    ]
    latest = records[-1] if records else {}
    return {
        "validation_count": len(records),
        "completed_validation_count": sum(1 for item in records if item.get("validation_complete")),
        "cleared_validation_count": len(cleared),
        "escalated_validation_count": len(escalated),
        "escalated_validations": escalated,
        "latest_jurisdiction": latest.get("jurisdiction", "not_assessed"),
        "latest_practice_area": latest.get("practice_area", "not_assessed"),
        "latest_confidence_category": latest.get("confidence_category", "not_assessed"),
        "latest_evidence_sufficiency_rating": latest.get("evidence_sufficiency_rating"),
        "latest_limitations": latest.get("known_limitations", []),
        "latest_escalation_status": latest.get("validation_status", "not_started"),
        "delivery_blocked": not records or bool(escalated),
        "mission_106_approval_required": True,
        "mission_109_review_required": True,
        "mission_110_assessment_required": True,
        "mission_111_validation_required": True,
        "gareth_final_approval_required": True,
        "gareth_override_allowed": False,
        "automatic_acceptance_enabled": False,
        "automatic_payment_enabled": False,
        "automatic_candidate_outreach_enabled": False,
        "automatic_search_commitments_enabled": False,
        "automatic_delivery_enabled": False,
        "external_commitments_enabled": False,
    }


def build_decline_decision_summary(recommendation_records, decision_records=None):
    recommendations = list(recommendation_records or [])
    decisions = list(decision_records or [])
    decision_by_recommendation = {
        item.get("recommendation_id"): item for item in decisions
    }
    awaiting = [
        item for item in recommendations
        if item.get("recommendation_id") not in decision_by_recommendation
    ]
    latest = recommendations[-1] if recommendations else {}
    return {
        "recommendation_count": len(recommendations),
        "accept_recommendation_count": sum(1 for item in recommendations if item.get("recommendation") == "ACCEPT"),
        "decline_recommendation_count": sum(1 for item in recommendations if item.get("recommendation") == "DECLINE"),
        "more_information_count": sum(1 for item in recommendations if item.get("recommendation") == "MORE_INFORMATION_REQUIRED"),
        "awaiting_gareth_approval_count": len(awaiting),
        "awaiting_gareth_approval": awaiting,
        "final_decision_count": len(decisions),
        "latest_recommendation": latest.get("recommendation", "not_assessed"),
        "gareth_final_approval_required": True,
        "recommendation_only": True,
        "automatic_acceptance_enabled": False,
        "automatic_decline_enabled": False,
        "automatic_referral_enabled": False,
        "automatic_payment_enabled": False,
        "automatic_candidate_outreach_enabled": False,
        "automatic_search_commitments_enabled": False,
        "automatic_delivery_enabled": False,
        "external_commitments_enabled": False,
    }


def get_legal_practice_areas():
    return [
        LegalPracticeArea(code=sector_code(sector), name=sector).to_dict()
        for sector in LEGAL_SECTORS
    ]


def get_stub_recruitment_opportunities():
    london = Jurisdiction(code="GB-ENG", name="England & Wales", region="Europe")
    uae = Jurisdiction(code="AE", name="United Arab Emirates", region="Middle East")
    singapore = Jurisdiction(code="SG", name="Singapore", region="Asia Pacific")
    new_york = Jurisdiction(code="US-NY", name="New York", region="North America")

    opportunities = [
        RecruitmentOpportunity(
            opportunity_id="glirn-pe-partner-london-001",
            title="Private Equity Partner Search",
            candidate=Candidate(
                candidate_id="candidate-stub-001",
                full_name="Candidate A",
                practice_area="Private Equity",
                jurisdiction=london.code,
                seniority="Partner",
                consent_status="human_approval_required",
                quality_score=91,
            ),
            client_firm=ClientFirm(
                firm_id="client-stub-001",
                name="Client Firm A",
                jurisdiction=london.code,
                practice_areas=["Private Equity", "Corporate & M&A"],
                client_quality=88,
            ),
            practice_area="Private Equity",
            jurisdiction=london.name,
            expected_fee_value=85000,
            placement_probability=0.42,
            client_quality=88,
            candidate_quality=91,
            compliance_readiness=76,
            urgency_score=82,
            time_to_revenue=45,
        ),
        RecruitmentOpportunity(
            opportunity_id="glirn-ai-law-counsel-uae-001",
            title="Technology & AI Law Counsel",
            candidate=Candidate(
                candidate_id="candidate-stub-002",
                full_name="Candidate B",
                practice_area="Technology & AI Law",
                jurisdiction=uae.code,
                seniority="Counsel",
                consent_status="human_approval_required",
                quality_score=86,
            ),
            client_firm=ClientFirm(
                firm_id="client-stub-002",
                name="Client Firm B",
                jurisdiction=uae.code,
                practice_areas=["Technology & AI Law", "Commercial Law"],
                client_quality=84,
            ),
            practice_area="Technology & AI Law",
            jurisdiction=uae.name,
            expected_fee_value=52000,
            placement_probability=0.58,
            client_quality=84,
            candidate_quality=86,
            compliance_readiness=82,
            urgency_score=78,
            time_to_revenue=35,
        ),
        RecruitmentOpportunity(
            opportunity_id="glirn-inhouse-singapore-001",
            title="In-House Counsel Opportunity",
            candidate=Candidate(
                candidate_id="candidate-stub-003",
                full_name="Candidate C",
                practice_area="In-House Counsel",
                jurisdiction=singapore.code,
                seniority="Senior Legal Counsel",
                consent_status="human_approval_required",
                quality_score=79,
            ),
            client_firm=ClientFirm(
                firm_id="client-stub-003",
                name="Client Firm C",
                jurisdiction=singapore.code,
                practice_areas=["In-House Counsel", "Employment Law"],
                client_quality=80,
            ),
            practice_area="In-House Counsel",
            jurisdiction=singapore.name,
            expected_fee_value=38000,
            placement_probability=0.61,
            client_quality=80,
            candidate_quality=79,
            compliance_readiness=88,
            urgency_score=70,
            time_to_revenue=30,
        ),
        RecruitmentOpportunity(
            opportunity_id="glirn-gc-newyork-001",
            title="General Counsel Search",
            candidate=Candidate(
                candidate_id="candidate-stub-004",
                full_name="Candidate D",
                practice_area="In-House Counsel",
                jurisdiction=new_york.code,
                seniority="General Counsel",
                consent_status="human_approval_required",
                quality_score=89,
            ),
            client_firm=ClientFirm(
                firm_id="client-stub-004",
                name="Client Firm D",
                jurisdiction=new_york.code,
                practice_areas=["In-House Counsel", "Technology & AI Law"],
                client_quality=87,
            ),
            practice_area="In-House Counsel",
            jurisdiction=new_york.name,
            expected_fee_value=76000,
            placement_probability=0.48,
            client_quality=87,
            candidate_quality=89,
            compliance_readiness=84,
            urgency_score=80,
            time_to_revenue=40,
        ),
        RecruitmentOpportunity(
            opportunity_id="glirn-clo-london-001",
            title="Chief Legal Officer Search",
            candidate=Candidate(
                candidate_id="candidate-stub-005",
                full_name="Candidate E",
                practice_area="Partner & Executive Search",
                jurisdiction=london.code,
                seniority="Chief Legal Officer",
                consent_status="human_approval_required",
                quality_score=93,
            ),
            client_firm=ClientFirm(
                firm_id="client-stub-005",
                name="Client Firm E",
                jurisdiction=london.code,
                practice_areas=["Partner & Executive Search", "Corporate & M&A"],
                client_quality=92,
            ),
            practice_area="Partner & Executive Search",
            jurisdiction=london.name,
            expected_fee_value=120000,
            placement_probability=0.36,
            client_quality=92,
            candidate_quality=93,
            compliance_readiness=90,
            urgency_score=88,
            time_to_revenue=55,
        ),
    ]

    return [opportunity.to_dict() for opportunity in opportunities]


def get_glirn_dashboard_data(pending_approvals=None, deletion_requests=None, public_leads=None):
    opportunities = sorted(
        get_stub_recruitment_opportunities(),
        key=lambda item: item.get("overall_glirn_score", 0),
        reverse=True,
    )
    pending = [
        item
        for item in opportunities
        if item.get("status") == "pending_human_approval"
    ]
    highest = opportunities[0] if opportunities else None
    radar = build_legal_opportunity_radar(opportunities)
    approval_centre = build_glirn_approval_centre(
        opportunities,
        pending_approvals=pending_approvals,
    )
    compliance_core = build_glirn_compliance_core(
        opportunities,
        deletion_requests=deletion_requests,
    )
    executive_search = build_executive_search_engine(
        opportunities,
        compliance_core=compliance_core,
    )
    intelligence_network = build_legal_intelligence_network(
        opportunities,
        compliance_core=compliance_core,
    )
    commercial_revenue_engine = build_commercial_revenue_engine(
        opportunities,
        compliance_core=compliance_core,
        intelligence_network=intelligence_network,
        executive_search=executive_search,
    )
    client_acquisition_engine = build_client_acquisition_engine(
        opportunities,
        compliance_core=compliance_core,
        executive_search=executive_search,
    )
    candidate_discovery_engine = build_candidate_discovery_engine(
        opportunities,
        compliance_core=compliance_core,
        executive_search=executive_search,
    )
    matching_engine = build_matching_engine(
        candidate_discovery_engine,
        client_acquisition_engine,
    )
    executive_autopilot = build_executive_autopilot(
        radar,
        executive_search,
        client_acquisition_engine,
        candidate_discovery_engine,
        matching_engine,
        commercial_revenue_engine,
        compliance_core,
    )
    live_data_readiness = build_live_data_readiness()
    integration_governance = build_integration_governance()
    deployment_readiness = build_deployment_readiness(
        compliance_core,
        approval_centre,
        commercial_revenue_engine,
        live_data_readiness,
        integration_governance,
        executive_autopilot,
    )
    operations_command_centre = build_operations_command_centre(
        executive_autopilot,
        radar,
        client_acquisition_engine,
        candidate_discovery_engine,
        matching_engine,
        commercial_revenue_engine,
        compliance_core,
        deployment_readiness,
        approval_centre,
    )
    daily_executive_briefing = build_daily_executive_briefing(
        operations_command_centre,
        radar,
        commercial_revenue_engine,
        compliance_core,
        deployment_readiness,
        executive_autopilot,
    )
    intelligence_review_engine = build_intelligence_review_engine(
        intelligence_network,
        client_acquisition_engine,
        candidate_discovery_engine,
        matching_engine,
        commercial_revenue_engine,
        compliance_core,
        executive_autopilot,
    )
    deliverable_factory = build_client_deliverable_factory(
        executive_autopilot,
        intelligence_review_engine,
        client_acquisition_engine,
        candidate_discovery_engine,
        matching_engine,
        commercial_revenue_engine,
        compliance_core,
    )
    approval_to_action_workflow = build_approval_to_action_workflow(
        intelligence_review_engine,
        deliverable_factory,
    )
    revenue_command_centre = build_revenue_command_centre(
        radar,
        executive_autopilot,
        matching_engine,
        commercial_revenue_engine,
        deliverable_factory,
        approval_to_action_workflow,
        daily_executive_briefing,
    )
    first_client_readiness_gate = build_first_client_readiness_gate(
        radar,
        intelligence_review_engine,
        deliverable_factory,
        approval_to_action_workflow,
        commercial_revenue_engine,
        compliance_core,
        revenue_command_centre,
    )
    launch_readiness_command_centre = build_launch_readiness_command_centre(
        deployment_readiness,
        first_client_readiness_gate,
        revenue_command_centre,
        intelligence_review_engine,
        deliverable_factory,
        approval_to_action_workflow,
    )
    invoice_drafting_engine = build_invoice_drafting_engine(
        commercial_revenue_engine,
        first_client_readiness_gate,
        revenue_command_centre,
    )
    client_terms_drafting_engine = build_client_terms_drafting_engine(
        commercial_revenue_engine,
    )
    candidate_consent_management_engine = build_candidate_consent_management_engine(
        compliance_core,
    )
    manual_delivery_control_engine = build_manual_delivery_control_engine(
        approval_to_action_workflow,
        client_terms_drafting_engine,
        invoice_drafting_engine,
        candidate_consent_management_engine,
        compliance_core,
    )
    launch_compliance_validation_engine = build_launch_compliance_validation_engine(
        manual_delivery_control_engine,
        client_terms_drafting_engine,
        invoice_drafting_engine,
        candidate_consent_management_engine,
        compliance_core,
    )
    first_prospect_selection_engine = build_first_prospect_selection_engine(
        launch_readiness_command_centre,
        launch_compliance_validation_engine,
    )
    first_client_dry_run = build_first_client_dry_run(
        first_prospect_selection_engine,
        intelligence_review_engine,
        deliverable_factory,
        client_terms_drafting_engine,
        invoice_drafting_engine,
        candidate_consent_management_engine,
        manual_delivery_control_engine,
        launch_compliance_validation_engine,
    )
    autonomous_internal_operations_orchestrator = build_autonomous_internal_operations_orchestrator(
        radar,
        first_prospect_selection_engine,
        revenue_command_centre,
        intelligence_review_engine,
        deliverable_factory,
        client_terms_drafting_engine,
        invoice_drafting_engine,
        candidate_consent_management_engine,
        launch_compliance_validation_engine,
        manual_delivery_control_engine,
        first_client_dry_run,
    )
    website_lead_intake_engine = build_website_lead_intake_engine(
        public_leads,
        autonomous_internal_operations_orchestrator,
    )
    revenue_approval_engine = build_revenue_approval_engine(
        website_lead_intake_engine,
    )
    client_response_draft_engine = build_client_response_draft_engine(
        revenue_approval_engine,
    )
    fee_proposal_pack_engine = build_fee_proposal_pack_engine(
        revenue_approval_engine,
        client_response_draft_engine,
    )
    final_approval_command_centre = build_final_approval_command_centre(
        revenue_approval_engine,
        client_response_draft_engine,
        fee_proposal_pack_engine,
    )
    approved_client_contact_engine = build_approved_client_contact_engine(
        final_approval_command_centre,
    )
    email_draft_export_engine = build_email_draft_export_engine(
        final_approval_command_centre,
    )
    invoice_draft_export_engine = build_invoice_draft_export_engine(
        final_approval_command_centre,
    )
    deal_pack_export_engine = build_deal_pack_export_engine(
        final_approval_command_centre,
    )
    revenue_ledger_engine = build_revenue_ledger_engine(
        final_approval_command_centre,
        email_draft_export_engine,
        invoice_draft_export_engine,
        deal_pack_export_engine,
    )
    gareth_command_centre = build_gareth_command_centre(
        opportunities,
        website_lead_intake_engine,
        revenue_approval_engine,
        fee_proposal_pack_engine,
        final_approval_command_centre,
        revenue_ledger_engine,
    )

    return {
        "legal_sectors": get_legal_practice_areas(),
        "opportunities": opportunities,
        "legal_opportunity_radar": radar,
        "approval_centre": approval_centre,
        "compliance_core": compliance_core,
        "executive_search": executive_search,
        "intelligence_network": intelligence_network,
        "intelligence_report": intelligence_network,
        "commercial_revenue_engine": commercial_revenue_engine,
        "commercial_pipeline": commercial_revenue_engine.get("commercial_pipeline", []),
        "client_acquisition_engine": client_acquisition_engine,
        "candidate_discovery_engine": candidate_discovery_engine,
        "matching_engine": matching_engine,
        "executive_autopilot": executive_autopilot,
        "live_data_readiness": live_data_readiness,
        "source_registry": live_data_readiness.get("source_registry", []),
        "source_readiness_summary": live_data_readiness.get("source_readiness_summary", {}),
        "blocked_sources": live_data_readiness.get("blocked_sources", []),
        "approved_sources": live_data_readiness.get("approved_sources", []),
        "pending_sources": live_data_readiness.get("pending_sources", []),
        "integration_governance": integration_governance,
        "approved_integrations": integration_governance.get("approved_integrations", []),
        "blocked_integrations": integration_governance.get("blocked_integrations", []),
        "pending_integrations": integration_governance.get("pending_integrations", []),
        "governance_alerts": integration_governance.get("governance_alerts", []),
        "deployment_readiness": deployment_readiness,
        "readiness_score": deployment_readiness.get("readiness_score", 0),
        "critical_gaps": deployment_readiness.get("critical_gaps", []),
        "launch_checklist": deployment_readiness.get("launch_checklist", []),
        "operations_command_centre": operations_command_centre,
        "executive_summary": operations_command_centre.get("executive_summary", {}),
        "key_metrics": operations_command_centre.get("key_metrics", {}),
        "platform_health": operations_command_centre.get("platform_health", {}),
        "daily_executive_briefing": daily_executive_briefing,
        "intelligence_review_engine": intelligence_review_engine,
        "generated_reviews": intelligence_review_engine.get("generated_reviews", []),
        "pending_review_approvals": intelligence_review_engine.get("pending_review_approvals", []),
        "review_generation_status": intelligence_review_engine.get("review_generation_status"),
        "latest_generated_review": intelligence_review_engine.get("latest_generated_review"),
        "deliverable_factory": deliverable_factory,
        "generated_deliverables": deliverable_factory.get("generated_deliverables", []),
        "pending_deliverable_approvals": deliverable_factory.get("pending_deliverable_approvals", []),
        "latest_deliverable": deliverable_factory.get("latest_deliverable"),
        "deliverable_status": deliverable_factory.get("deliverable_status"),
        "approval_to_action_workflow": approval_to_action_workflow,
        "approved_for_human_use": approval_to_action_workflow.get("approved_for_human_use", []),
        "pending_gareth_approval": approval_to_action_workflow.get("pending_gareth_approval", []),
        "rejected_items": approval_to_action_workflow.get("rejected_items", []),
        "monitored_items": approval_to_action_workflow.get("monitored_items", []),
        "revenue_command_centre": revenue_command_centre,
        "revenue_pipeline": revenue_command_centre.get("revenue_pipeline", []),
        "revenue_funnel": revenue_command_centre.get("revenue_funnel", []),
        "highest_fee_opportunity": revenue_command_centre.get("highest_fee_opportunity"),
        "fastest_revenue_opportunity": revenue_command_centre.get("fastest_revenue_opportunity"),
        "revenue_readiness_score": revenue_command_centre.get("revenue_readiness_score", 0),
        "top_revenue_opportunities": revenue_command_centre.get("top_revenue_opportunities", []),
        "first_client_readiness_gate": first_client_readiness_gate,
        "readiness_checks": first_client_readiness_gate.get("readiness_checks", []),
        "first_client_ready_items": first_client_readiness_gate.get("first_client_ready_items", []),
        "blocked_first_client_items": first_client_readiness_gate.get("blocked_first_client_items", []),
        "monitored_first_client_items": first_client_readiness_gate.get("monitored_first_client_items", []),
        "readiness_recommendation": first_client_readiness_gate.get("readiness_recommendation"),
        "overall_first_client_readiness_score": first_client_readiness_gate.get("overall_first_client_readiness_score", 0),
        "launch_readiness_command_centre": launch_readiness_command_centre,
        "launch_readiness_score": launch_readiness_command_centre.get("launch_readiness_score", 0),
        "launch_readiness_grade": launch_readiness_command_centre.get("launch_readiness_grade"),
        "launch_ready_items": launch_readiness_command_centre.get("launch_ready_items", []),
        "launch_blocked_items": launch_readiness_command_centre.get("launch_blocked_items", []),
        "launch_missing_items": launch_readiness_command_centre.get("launch_missing_items", []),
        "launch_recommended_next_action": launch_readiness_command_centre.get("launch_recommended_next_action"),
        "invoice_drafting_engine": invoice_drafting_engine,
        "invoice_drafts": invoice_drafting_engine.get("invoice_drafts", []),
        "pending_invoice_approvals": invoice_drafting_engine.get("pending_invoice_approvals", []),
        "invoice_readiness_status": invoice_drafting_engine.get("invoice_readiness_status"),
        "client_terms_drafting_engine": client_terms_drafting_engine,
        "client_terms_drafts": client_terms_drafting_engine.get("client_terms_drafts", []),
        "pending_terms_approvals": client_terms_drafting_engine.get("pending_terms_approvals", []),
        "approved_terms_drafts": client_terms_drafting_engine.get("approved_terms_drafts", []),
        "terms_readiness_status": client_terms_drafting_engine.get("terms_readiness_status"),
        "candidate_consent_management_engine": candidate_consent_management_engine,
        "candidate_consent_records": candidate_consent_management_engine.get("candidate_consent_records", []),
        "pending_candidate_consents": candidate_consent_management_engine.get("pending_candidate_consents", []),
        "active_candidate_consents": candidate_consent_management_engine.get("active_candidate_consents", []),
        "expired_candidate_consents": candidate_consent_management_engine.get("expired_candidate_consents", []),
        "consent_readiness_status": candidate_consent_management_engine.get("consent_readiness_status"),
        "manual_delivery_control_engine": manual_delivery_control_engine,
        "delivery_ready_items": manual_delivery_control_engine.get("delivery_ready_items", []),
        "blocked_delivery_items": manual_delivery_control_engine.get("blocked_delivery_items", []),
        "manual_delivery_status": manual_delivery_control_engine.get("manual_delivery_status"),
        "launch_compliance_validation_engine": launch_compliance_validation_engine,
        "compliance_validation_checks": launch_compliance_validation_engine.get("compliance_validation_checks", []),
        "compliance_ready_items": launch_compliance_validation_engine.get("compliance_ready_items", []),
        "compliance_blocked_items": launch_compliance_validation_engine.get("compliance_blocked_items", []),
        "compliance_validation_status": launch_compliance_validation_engine.get("compliance_validation_status"),
        "compliance_risk_level": launch_compliance_validation_engine.get("compliance_risk_level"),
        "compliance_recommendation": launch_compliance_validation_engine.get("compliance_recommendation"),
        "overall_compliance_readiness_score": launch_compliance_validation_engine.get("overall_compliance_readiness_score", 0),
        "first_prospect_selection_engine": first_prospect_selection_engine,
        "prospect_profiles": first_prospect_selection_engine.get("prospect_profiles", []),
        "prospect_rankings": first_prospect_selection_engine.get("prospect_rankings", []),
        "prospect_recommendations": first_prospect_selection_engine.get("prospect_recommendations", {}),
        "launch_priority_score": first_prospect_selection_engine.get("launch_priority_score", 0),
        "recommended_first_prospect": first_prospect_selection_engine.get("recommended_first_prospect"),
        "highest_revenue_prospect": first_prospect_selection_engine.get("highest_revenue_prospect"),
        "fastest_revenue_prospect": first_prospect_selection_engine.get("fastest_revenue_prospect"),
        "first_client_dry_run": first_client_dry_run,
        "dry_run_status": first_client_dry_run.get("dry_run_status"),
        "dry_run_readiness_score": first_client_dry_run.get("dry_run_readiness_score", 0),
        "latest_dry_run_report": first_client_dry_run.get("latest_dry_run_report", {}),
        "dry_run_blockers": first_client_dry_run.get("dry_run_blockers", []),
        "dry_run_warnings": first_client_dry_run.get("dry_run_warnings", []),
        "autonomous_internal_operations_orchestrator": autonomous_internal_operations_orchestrator,
        "autonomous_cycle_status": autonomous_internal_operations_orchestrator.get("autonomous_cycle_status"),
        "final_gareth_approval_packages": autonomous_internal_operations_orchestrator.get("final_gareth_approval_packages", []),
        "autonomous_recommendation_queue": autonomous_internal_operations_orchestrator.get("autonomous_recommendation_queue", []),
        "autonomous_blockers": autonomous_internal_operations_orchestrator.get("autonomous_blockers", []),
        "autonomous_warnings": autonomous_internal_operations_orchestrator.get("autonomous_warnings", []),
        "website_lead_intake_engine": website_lead_intake_engine,
        "public_leads": website_lead_intake_engine.get("public_leads", []),
        "qualified_public_leads": website_lead_intake_engine.get("qualified_public_leads", []),
        "pending_public_lead_approvals": website_lead_intake_engine.get("pending_public_lead_approvals", []),
        "latest_public_lead_recommendation": website_lead_intake_engine.get("latest_public_lead_recommendation", {}),
        "revenue_approval_engine": revenue_approval_engine,
        "revenue_approval_packages": revenue_approval_engine.get("revenue_approval_packages", []),
        "ready_for_gareth_approval": revenue_approval_engine.get("ready_for_gareth_approval", []),
        "latest_revenue_opportunity": revenue_approval_engine.get("latest_revenue_opportunity", {}),
        "client_response_draft_engine": client_response_draft_engine,
        "client_response_drafts": client_response_draft_engine.get("client_response_drafts", []),
        "client_response_draft_ready": client_response_draft_engine.get("client_response_draft_ready", {}),
        "pending_client_response_approvals": client_response_draft_engine.get("pending_client_response_approvals", []),
        "latest_client_response_draft": client_response_draft_engine.get("latest_client_response_draft", {}),
        "fee_proposal_pack_engine": fee_proposal_pack_engine,
        "fee_proposal_packs": fee_proposal_pack_engine.get("fee_proposal_packs", []),
        "fee_proposal_pack_ready": fee_proposal_pack_engine.get("fee_proposal_pack_ready", {}),
        "pending_fee_proposal_approvals": fee_proposal_pack_engine.get("pending_fee_proposal_approvals", []),
        "latest_fee_proposal_pack": fee_proposal_pack_engine.get("latest_fee_proposal_pack", {}),
        "final_approval_command_centre": final_approval_command_centre,
        "final_approval_objects": final_approval_command_centre.get("final_approval_objects", []),
        "gareth_final_approval_required": final_approval_command_centre.get("gareth_final_approval_required", []),
        "latest_final_approval_object": final_approval_command_centre.get("latest_final_approval_object", {}),
        "approved_client_contact_engine": approved_client_contact_engine,
        "client_contact_readiness": approved_client_contact_engine.get("client_contact_readiness", []),
        "blocked_client_contacts": approved_client_contact_engine.get("blocked_client_contacts", []),
        "ready_client_contacts": approved_client_contact_engine.get("ready_client_contacts", []),
        "latest_client_contact_readiness": approved_client_contact_engine.get("latest_client_contact_readiness", {}),
        "email_draft_export_engine": email_draft_export_engine,
        "email_draft_exports": email_draft_export_engine.get("email_draft_exports", []),
        "blocked_email_draft_exports": email_draft_export_engine.get("blocked_email_draft_exports", []),
        "ready_email_draft_exports": email_draft_export_engine.get("ready_email_draft_exports", []),
        "latest_email_draft_export": email_draft_export_engine.get("latest_email_draft_export", {}),
        "invoice_draft_export_engine": invoice_draft_export_engine,
        "invoice_draft_exports": invoice_draft_export_engine.get("invoice_draft_exports", []),
        "blocked_invoice_draft_exports": invoice_draft_export_engine.get("blocked_invoice_draft_exports", []),
        "ready_invoice_draft_exports": invoice_draft_export_engine.get("ready_invoice_draft_exports", []),
        "latest_invoice_draft_export": invoice_draft_export_engine.get("latest_invoice_draft_export", {}),
        "deal_pack_export_engine": deal_pack_export_engine,
        "deal_pack_exports": deal_pack_export_engine.get("deal_pack_exports", []),
        "blocked_deal_pack_exports": deal_pack_export_engine.get("blocked_deal_pack_exports", []),
        "ready_deal_pack_exports": deal_pack_export_engine.get("ready_deal_pack_exports", []),
        "latest_deal_pack_export": deal_pack_export_engine.get("latest_deal_pack_export", {}),
        "revenue_ledger_engine": revenue_ledger_engine,
        "gareth_command_centre": gareth_command_centre,
        "revenue_ledger_records": revenue_ledger_engine.get("revenue_ledger_records", []),
        "latest_revenue_ledger_record": revenue_ledger_engine.get("latest_revenue_ledger_record", {}),
        "estimated_pipeline_value": revenue_ledger_engine.get("estimated_pipeline_value", 0),
        "actual_revenue_recorded": revenue_ledger_engine.get("actual_revenue_recorded", 0),
        "latest_revenue_stage": revenue_ledger_engine.get("latest_revenue_stage", "new_lead"),
        "summary": {
            "total_opportunities": len(opportunities),
            "pending_human_approval": len(pending),
            "dashboard_status": approval_centre.get("status"),
            "compliance_status": compliance_core.get("status"),
            "executive_search_status": executive_search.get("status"),
            "intelligence_network_status": intelligence_network.get("status"),
            "commercial_revenue_status": commercial_revenue_engine.get("status"),
            "client_acquisition_status": client_acquisition_engine.get("status"),
            "candidate_discovery_status": candidate_discovery_engine.get("status"),
            "matching_engine_status": matching_engine.get("status"),
            "executive_autopilot_status": executive_autopilot.get("status"),
            "live_data_readiness_status": live_data_readiness.get("status"),
            "integration_governance_status": integration_governance.get("status"),
            "deployment_readiness_status": deployment_readiness.get("status"),
            "operations_command_centre_status": operations_command_centre.get("status"),
            "daily_executive_briefing_status": daily_executive_briefing.get("status"),
            "intelligence_review_engine_status": intelligence_review_engine.get("status"),
            "deliverable_factory_status": deliverable_factory.get("status"),
            "approval_to_action_workflow_status": approval_to_action_workflow.get("status"),
            "revenue_command_centre_status": revenue_command_centre.get("status"),
            "first_client_readiness_gate_status": first_client_readiness_gate.get("status"),
            "launch_readiness_command_centre_status": launch_readiness_command_centre.get("status"),
            "invoice_drafting_engine_status": invoice_drafting_engine.get("status"),
            "client_terms_drafting_engine_status": client_terms_drafting_engine.get("status"),
            "candidate_consent_management_engine_status": candidate_consent_management_engine.get("status"),
            "manual_delivery_control_engine_status": manual_delivery_control_engine.get("status"),
            "launch_compliance_validation_engine_status": launch_compliance_validation_engine.get("status"),
            "first_prospect_selection_engine_status": first_prospect_selection_engine.get("status"),
            "first_client_dry_run_status": first_client_dry_run.get("dry_run_status"),
            "autonomous_internal_operations_orchestrator_status": autonomous_internal_operations_orchestrator.get("autonomous_cycle_status"),
            "website_lead_intake_engine_status": website_lead_intake_engine.get("status"),
            "revenue_approval_engine_status": revenue_approval_engine.get("status"),
            "client_response_draft_engine_status": client_response_draft_engine.get("status"),
            "fee_proposal_pack_engine_status": fee_proposal_pack_engine.get("status"),
            "final_approval_command_centre_status": final_approval_command_centre.get("status"),
            "approved_client_contact_engine_status": approved_client_contact_engine.get("status"),
            "email_draft_export_engine_status": email_draft_export_engine.get("status"),
            "invoice_draft_export_engine_status": invoice_draft_export_engine.get("status"),
            "deal_pack_export_engine_status": deal_pack_export_engine.get("status"),
            "revenue_ledger_engine_status": revenue_ledger_engine.get("status"),
            "total_expected_fee_value": sum(
                float(item.get("expected_fee_value", 0)) for item in opportunities
            ),
            "highest_score": highest.get("overall_glirn_score", 0) if highest else 0,
            "highest_opportunity": highest,
            "top_radar_opportunity": radar.get("top_opportunity"),
            "highest_value_candidate": radar.get("highest_value_candidate"),
            "highest_value_client_firm": radar.get("highest_value_client_firm"),
            "capital_execution": False,
        },
        "capital_execution": False,
    }
