from html import escape
from contextlib import asynccontextmanager
import os
from pathlib import Path
import re
import shutil
import time
from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

import dashboard
from analytics.provider_scoring import reset_provider_score
from audit_logger import log_route_decision
from core.provider_guard import provider_allowed
from core.router import route_task
from governance_analytics import get_governance_analytics
from glirn import apply_autonomous_internal_operations_action, apply_candidate_consent_action, apply_client_contact_action, apply_client_terms_action, apply_deal_pack_export_action, apply_email_draft_export_action, apply_final_approval_action, apply_first_client_dry_run_action, apply_first_client_readiness_decision, apply_invoice_draft_action, apply_invoice_draft_export_action, apply_launch_compliance_action, apply_launch_readiness_decision, apply_manual_delivery_action, apply_public_lead_action, apply_revenue_ledger_action, build_client_contact_readiness_object, build_confidence_assessment_summary, build_deal_pack_export_object, build_decline_decision_summary, build_email_draft_export_object, build_enquiry_notification_summary, build_gareth_command_centre, build_global_intelligence_summary, build_invoice_draft_export_object, build_multi_agent_review_summary, build_public_lead_record, build_revenue_approval_package_for_lead, build_revenue_ledger_engine, flag_deletion_request, get_glirn_dashboard_data
from main import classify_task, load_env_file, load_provider_config, load_runtime_providers
from agent_safety_gate import REQUEST_APPROVAL, evaluate_agent_action
from opportunity_scanner import get_scanner_results
from opportunities.scanner import scan_opportunities
from opportunities.store import get_opportunity_analytics, list_approvals, list_opportunities, record_opportunity_approval, record_opportunity_outcome
from research.converter import convert_research_to_opportunities
from research.intake import intake_research_items
from research.models import ResearchItem
from research.sources import load_research_sources, toggle_research_source
from research.store import append_research_item, list_research_items
from approval_queue import (
    create_approval_request,
    list_pending_approvals,
    update_approval_decision,
)

from approval_ledger import list_approval_events, record_approval_event
from glirn_storage import append_action, get_state, initialize_schema, list_records, persistence_status, set_state, upsert_record
from glirn_responses import build_enquiry_response_package
from glirn_human_review import (
    ALLOWED_DELIVERY_STATUSES,
    ALLOWED_OUTCOMES,
    DECLINE_CRITERIA,
    HUMAN_REVIEW_CHECKLIST,
    RED_FLAG_RULES,
    evaluate_human_review,
)
from glirn_brief_template import (
    IntelligenceBriefValidationError,
    REQUIRED_DISCLAIMER,
    build_intelligence_brief_package,
)
from notification_service import deliver_enquiry_notification
from glirn_multi_agent_review import brief_content_fingerprint, run_multi_agent_review
from glirn_confidence_engine import assess_confidence, render_evidence_transparency_markdown
from glirn_global_intelligence import generate_global_legal_intelligence, render_global_intelligence_markdown
from glirn_decline_decision import apply_gareth_decision, evaluate_decline_decision
from glirn_internal_learning import (
    approve_learning_insight,
    capture_learning_outcome,
    generate_improvement_insights,
)
from glirn_external_learning import (
    approve_knowledge_update,
    generate_external_intelligence,
    ingest_public_evidence,
)
from glirn_opportunity_intelligence import (
    apply_gareth_opportunity_decision,
    generate_opportunity_recommendation,
    record_opportunity_signal,
)

BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def app_lifespan(_app):
    reload_persistent_state()
    yield


app = FastAPI(title="ArbitrageEngineV1 Local API", lifespan=app_lifespan)
app.mount("/public", StaticFiles(directory=BASE_DIR / "public", html=True), name="public")


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

CHECKPOINT_SOURCES = ["config", "analytics", "data", "logs", "RUNBOOK.md"]
BACKUPS_DIR = "backups"
PUBLIC_LEADS = []
PUBLIC_LEAD_SUBMISSION_TIMES = {}
PUBLIC_LEAD_RATE_LIMIT = 3
PUBLIC_LEAD_RATE_WINDOW_SECONDS = 60
FINAL_APPROVAL_LOCAL_STATUS = {}
REVENUE_LEDGER_LOCAL_STAGE = {}
PERSISTED_EXPORT_METADATA = {
    "email_draft": [],
    "invoice_draft": [],
    "deal_pack": [],
}
PERSISTED_RESPONSE_PACKAGES = []
PERSISTED_HUMAN_REVIEWS = []
PERSISTED_INTELLIGENCE_BRIEFS = []
PERSISTED_ENQUIRY_NOTIFICATIONS = []
PERSISTED_MULTI_AGENT_REVIEWS = []
PERSISTED_CONFIDENCE_ASSESSMENTS = []
PERSISTED_GLOBAL_INTELLIGENCE = []
PERSISTED_DECLINE_RECOMMENDATIONS = []
PERSISTED_DECLINE_DECISIONS = []
PERSISTED_LEARNING_OUTCOMES = []
PERSISTED_LEARNING_INSIGHTS = []
PERSISTED_LEARNING_APPROVALS = []
PERSISTED_EXTERNAL_EVIDENCE = []
PERSISTED_EXTERNAL_INTELLIGENCE = []
PERSISTED_KNOWLEDGE_UPDATES = []
PERSISTED_OPPORTUNITY_SIGNALS = []
PERSISTED_OPPORTUNITY_INTELLIGENCE = []
PERSISTED_OPPORTUNITY_DECISIONS = []
GLIRN_EMAIL_DRAFTS_DIR = os.path.join("data", "glirn_email_drafts")
GLIRN_INVOICE_DRAFTS_DIR = os.path.join("data", "glirn_invoice_drafts")
GLIRN_DEAL_PACKS_DIR = os.path.join("data", "glirn_deal_packs")
GLIRN_INTELLIGENCE_BRIEFS_DIR = os.path.join("data", "glirn_intelligence_briefs")


def reload_persistent_state():
    initialize_schema()
    PUBLIC_LEADS[:] = list_records("website_enquiry")
    FINAL_APPROVAL_LOCAL_STATUS.clear()
    FINAL_APPROVAL_LOCAL_STATUS.update(get_state("final_approval_statuses", {}) or {})
    REVENUE_LEDGER_LOCAL_STAGE.clear()
    REVENUE_LEDGER_LOCAL_STAGE.update(get_state("revenue_ledger_stages", {}) or {})
    PERSISTED_EXPORT_METADATA["email_draft"] = list_records("email_draft_export")
    PERSISTED_EXPORT_METADATA["invoice_draft"] = list_records("invoice_draft_export")
    PERSISTED_EXPORT_METADATA["deal_pack"] = list_records("deal_pack_export")
    PERSISTED_RESPONSE_PACKAGES[:] = list_records("enquiry_response_package")
    PERSISTED_HUMAN_REVIEWS[:] = list_records("human_review_record")
    PERSISTED_INTELLIGENCE_BRIEFS[:] = list_records("intelligence_brief_record")
    PERSISTED_ENQUIRY_NOTIFICATIONS[:] = list_records("enquiry_notification_record")
    PERSISTED_MULTI_AGENT_REVIEWS[:] = list_records("multi_agent_review_record")
    PERSISTED_CONFIDENCE_ASSESSMENTS[:] = list_records("confidence_assessment_record")
    PERSISTED_GLOBAL_INTELLIGENCE[:] = list_records("global_intelligence_record")
    PERSISTED_DECLINE_RECOMMENDATIONS[:] = list_records("decline_recommendation_record")
    PERSISTED_DECLINE_DECISIONS[:] = list_records("decline_decision_record")
    PERSISTED_LEARNING_OUTCOMES[:] = list_records("learning_outcome_record")
    PERSISTED_LEARNING_INSIGHTS[:] = list_records("learning_insight_record")
    PERSISTED_LEARNING_APPROVALS[:] = list_records("learning_approval_record")
    PERSISTED_EXTERNAL_EVIDENCE[:] = list_records("external_evidence_record")
    PERSISTED_EXTERNAL_INTELLIGENCE[:] = list_records("external_intelligence_learning_record")
    PERSISTED_KNOWLEDGE_UPDATES[:] = list_records("knowledge_base_record")
    PERSISTED_OPPORTUNITY_SIGNALS[:] = list_records("opportunity_signal_record")
    PERSISTED_OPPORTUNITY_INTELLIGENCE[:] = list_records("opportunity_intelligence_record")
    PERSISTED_OPPORTUNITY_DECISIONS[:] = list_records("opportunity_intelligence_decision_record")


reload_persistent_state()


class RouteRequest(BaseModel):
    task: str


class ResearchImportRequest(BaseModel):
    title: str
    url: str
    summary: str
    category: str
    relevance_score: float


class OpportunityReviewRequest(BaseModel):
    reviewer_note: str | None = None


class OpportunityOutcomeRequest(BaseModel):
    outcome_status: str
    reviewer_note: str | None = None
    realized_value: float | None = None


class AgentSafetyRequest(BaseModel):
    action_type: str
    recipient_type: str
    subject: str | None = None
    body: str
    customer_facing: bool = False
    contains_money_claim: bool = False
    contains_private_data: bool = False
    contains_legal_advice: bool = False
    contains_medical_advice: bool = False
    contains_regulated_financial_advice: bool = False
    spends_money: bool = False
    changes_vendor: bool = False
    publishes_content: bool = False
    executes_workflow: bool = False
    human_approved_already: bool = False


class AgentSafetyResponse(BaseModel):
    decision: str
    reason: str
    reason_codes: list[str]
    approval_required: bool
    approval_id: str | None = None
    blocked: bool
    safe_default: str
    capital_execution: bool
    autonomous_execution: bool


class GlirnApprovalDecisionRequest(BaseModel):
    approval_reason: str


class GlirnDeletionRequest(BaseModel):
    candidate_id: str
    reason: str


class GlirnExecutiveSearchActionRequest(BaseModel):
    opportunity_id: str
    action_type: str
    reason: str


class GlirnIntelligenceReportRequest(BaseModel):
    report_type: str
    audience: str
    reason: str
    include_candidate_specific_data: bool = False


class GlirnCommercialActionRequest(BaseModel):
    opportunity_id: str
    action_type: str
    reason: str


class GlirnClientAcquisitionActionRequest(BaseModel):
    client_id: str
    action_type: str
    reason: str


class GlirnCandidateDiscoveryActionRequest(BaseModel):
    candidate_id: str
    action_type: str
    reason: str


class GlirnMatchingActionRequest(BaseModel):
    match_id: str
    action_type: str
    reason: str


class GlirnLiveDataSourceActionRequest(BaseModel):
    source_id: str
    action_type: str
    reason: str


class GlirnIntegrationActionRequest(BaseModel):
    integration_id: str
    action_type: str
    reason: str


class GlirnIntelligenceReviewActionRequest(BaseModel):
    review_id: str | None = None
    action_type: str
    reason: str


class GlirnHumanReviewRequest(BaseModel):
    brief_id: str | None = None
    enquiry_date: str | None = None
    reviewer: str
    outcome: str
    approval_rationale: str
    checklist_results: dict[str, bool] = Field(default_factory=dict)
    red_flags: dict[str, bool] = Field(default_factory=dict)
    red_flag_resolutions: dict[str, bool] = Field(default_factory=dict)
    decline_criterion: str | None = None
    decline_reason: str | None = None
    delivery_status: str = "not_ready"


class GlirnIntelligenceBriefPackageRequest(BaseModel):
    brief_id: str
    final_approval_id: str | None = None
    sections: dict[str, str] = Field(default_factory=dict)


class GlirnMultiAgentReviewRequest(BaseModel):
    brief_id: str
    sections: dict[str, str] = Field(default_factory=dict)


class GlirnConfidenceAssessmentRequest(BaseModel):
    brief_id: str
    sections: dict[str, str] = Field(default_factory=dict)
    evidence_sufficiency: float = Field(ge=0, le=100)
    evidence_quality: float = Field(ge=0, le=100)
    data_recency: float = Field(ge=0, le=100)
    market_information_completeness: float = Field(ge=0, le=100)
    key_evidence_considered: list[str] = Field(default_factory=list)
    supporting_assumptions: list[str] = Field(default_factory=list)
    known_limitations: list[str] = Field(default_factory=list)
    areas_requiring_caution: list[str] = Field(default_factory=list)
    information_gaps_identified: list[str] = Field(default_factory=list)
    material_limitations_undermine_conclusions: bool = False


class GlirnGlobalIntelligenceRequest(BaseModel):
    brief_id: str
    sections: dict[str, str] = Field(default_factory=dict)
    jurisdiction: str
    practice_area: str
    indicator_ratings: dict[str, float] = Field(default_factory=dict)
    evidence_basis: list[str] = Field(default_factory=list)
    known_limitations: list[str] = Field(default_factory=list)
    information_gaps: list[str] = Field(default_factory=list)
    alternative_interpretations: list[str] = Field(default_factory=list)
    unsupported_claims_identified: bool = False
    jurisdiction_expertise_limitations: bool = False
    evidence_insufficiency_identified: bool = False
    exceeds_glirn_expertise_boundaries: bool = False


class GlirnDeclineRecommendationRequest(BaseModel):
    enquiry_id: str
    factor_scores: dict[str, float] = Field(default_factory=dict)
    evidence: dict[str, str] = Field(default_factory=dict)
    referral_suitable: bool = False
    referral_type: str | None = None
    referral_reason: str | None = None


class GlirnDeclineFinalDecisionRequest(BaseModel):
    final_decision: str
    rationale: str


class GlirnLearningOutcomeRequest(BaseModel):
    record_id: str
    brief_id: str
    gareth_decision: str
    brief_outcome: str
    remediation_outcome: str
    outcome_summary: str
    decline_reason_codes: list[str] = Field(default_factory=list)


class GlirnLearningInsightApprovalRequest(BaseModel):
    rationale: str


class GlirnExternalEvidenceRequest(BaseModel):
    evidence_id: str
    source_type: str
    title: str
    publisher: str
    source_url: str
    publication_date: str
    evidence_summary: str
    jurisdiction: str | None = None


class GlirnExternalIntelligenceRequest(BaseModel):
    topic: str
    evidence_ids: list[str] = Field(default_factory=list)


class GlirnKnowledgeUpdateApprovalRequest(BaseModel):
    rationale: str


class GlirnOpportunitySignalRequest(BaseModel):
    signal_id: str
    category: str
    source_type: str
    title: str
    publisher: str
    source_url: str
    publication_date: str
    signal_summary: str
    organisation: str
    jurisdiction: str
    practice_area: str | None = None
    signal_strength: float = 70


class GlirnOpportunityRecommendationRequest(BaseModel):
    signal_ids: list[str] = Field(default_factory=list)


class GlirnOpportunityDecisionRequest(BaseModel):
    decision: str
    rationale: str


class GlirnIntelligenceBriefFinalApprovalRequest(BaseModel):
    action_type: str
    reason: str


class GlirnDeliverableActionRequest(BaseModel):
    deliverable_id: str | None = None
    action_type: str
    reason: str


class GlirnApprovalToActionRequest(BaseModel):
    item_id: str
    action_type: str
    reason: str


class GlirnFirstClientReadinessActionRequest(BaseModel):
    item_id: str
    action_type: str
    reason: str


class GlirnLaunchReadinessActionRequest(BaseModel):
    action_type: str
    reason: str


class GlirnInvoiceActionRequest(BaseModel):
    invoice_number: str | None = None
    action_type: str
    reason: str


class GlirnClientTermsActionRequest(BaseModel):
    terms_id: str | None = None
    action_type: str
    reason: str


class GlirnCandidateConsentActionRequest(BaseModel):
    candidate_id: str | None = None
    action_type: str
    reason: str


class GlirnManualDeliveryActionRequest(BaseModel):
    delivery_id: str | None = None
    action_type: str
    reason: str


class GlirnLaunchComplianceActionRequest(BaseModel):
    validation_id: str | None = None
    action_type: str
    reason: str


class GlirnDryRunActionRequest(BaseModel):
    action_type: str
    reason: str


class GlirnAutonomousOperationsActionRequest(BaseModel):
    action_type: str
    reason: str


class GlirnPublicLeadIntakeRequest(BaseModel):
    name: str
    organisation: str
    email: str
    country: str
    inquiry_type: str
    legal_sector: str
    practice_area: str = ""
    jurisdiction: str = ""
    career_stage: str = ""
    confidential_career_interest: str = ""
    hiring_need: str
    seniority_level: str
    timescale: str = ""
    message: str
    consent: bool

    @field_validator(
        "name", "organisation", "country", "inquiry_type", "legal_sector",
        "practice_area", "jurisdiction", "career_stage", "confidential_career_interest",
        "hiring_need", "seniority_level", "timescale", "message", mode="before",
    )
    @classmethod
    def validate_public_text(cls, value, info):
        if not isinstance(value, str):
            raise ValueError("must be text")
        cleaned = value.strip()
        required_fields = {
            "name", "organisation", "country", "inquiry_type", "legal_sector",
            "hiring_need", "seniority_level", "message",
        }
        if info.field_name in required_fields and not cleaned:
            raise ValueError("field is required")
        limits = {
            "name": 120,
            "organisation": 200,
            "country": 100,
            "inquiry_type": 100,
            "legal_sector": 150,
            "practice_area": 150,
            "jurisdiction": 150,
            "career_stage": 100,
            "confidential_career_interest": 500,
            "hiring_need": 500,
            "seniority_level": 100,
            "timescale": 100,
            "message": 2000,
        }
        if len(cleaned) > limits[info.field_name]:
            raise ValueError(f"must be {limits[info.field_name]} characters or fewer")
        if "<" in cleaned or ">" in cleaned or re.search(r"javascript\s*:", cleaned, re.IGNORECASE):
            raise ValueError("HTML or script content is not allowed")
        if any(ord(character) < 32 and character not in {"\n", "\r", "\t"} for character in cleaned):
            raise ValueError("control characters are not allowed")
        return cleaned

    @field_validator("email", mode="before")
    @classmethod
    def validate_public_email(cls, value):
        if not isinstance(value, str):
            raise ValueError("valid email is required")
        cleaned = value.strip().lower()
        if len(cleaned) > 254 or not re.fullmatch(
            r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+",
            cleaned,
        ):
            raise ValueError("valid email is required")
        return cleaned


class GlirnPublicLeadActionRequest(BaseModel):
    lead_id: str | None = None
    action_type: str
    reason: str


class GlirnEnquiryNotificationResendRequest(BaseModel):
    reason: str


class GlirnFinalApprovalActionRequest(BaseModel):
    final_approval_id: str | None = None
    action_type: str
    reason: str


class GlirnClientContactActionRequest(BaseModel):
    final_approval_id: str | None = None
    action_type: str
    reason: str


class GlirnEmailDraftExportActionRequest(BaseModel):
    final_approval_id: str | None = None
    action_type: str
    reason: str


class GlirnInvoiceDraftExportActionRequest(BaseModel):
    final_approval_id: str | None = None
    action_type: str
    reason: str


class GlirnDealPackExportActionRequest(BaseModel):
    final_approval_id: str | None = None
    action_type: str
    reason: str


class GlirnRevenueLedgerActionRequest(BaseModel):
    final_approval_id: str | None = None
    ledger_record_id: str | None = None
    action_type: str
    reason: str


def configured_api_key():
    return os.getenv("ARBITRAGE_API_KEY")


def require_api_key(provided_key):
    expected_key = configured_api_key()

    if not expected_key:
        return

    if provided_key != expected_key:
        raise HTTPException(status_code=401, detail="invalid or missing API key")


def enforce_public_lead_rate_limit(email):
    if not PUBLIC_LEADS:
        PUBLIC_LEAD_SUBMISSION_TIMES.clear()
    now = time.monotonic()
    recent = [
        timestamp
        for timestamp in PUBLIC_LEAD_SUBMISSION_TIMES.get(email, [])
        if now - timestamp < PUBLIC_LEAD_RATE_WINDOW_SECONDS
    ]
    if len(recent) >= PUBLIC_LEAD_RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Too many enquiries. Please wait before trying again.")
    recent.append(now)
    PUBLIC_LEAD_SUBMISSION_TIMES[email] = recent


def safe_export_text(value):
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(
        character
        for character in text
        if ord(character) >= 32 or character in {"\n", "\t"}
    )
    return escape(text, quote=False)


def approved_local_export_path(directory, identifier):
    root = Path(directory).resolve()
    root.mkdir(parents=True, exist_ok=True)
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "-", str(identifier or "glirn-export"))
    safe_id = safe_id.strip("-_")[:180] or "glirn-export"
    target = (root / f"{safe_id}.txt").resolve()
    if os.path.commonpath([str(root), str(target)]) != str(root):
        raise HTTPException(status_code=400, detail="invalid export path")
    return str(target)


def export_engine_with_persisted_records(engine, export_type):
    engine = dict(engine or {})
    configuration = {
        "email_draft": ("email_draft_exports", "latest_email_draft_export"),
        "invoice_draft": ("invoice_draft_exports", "latest_invoice_draft_export"),
        "deal_pack": ("deal_pack_exports", "latest_deal_pack_export"),
    }
    records_key, latest_key = configuration[export_type]
    persisted = PERSISTED_EXPORT_METADATA.get(export_type, []) or []
    generated = engine.get(records_key, []) or []
    by_id = {}
    for item in generated + persisted:
        record_id = (
            item.get("email_draft_export_id")
            or item.get("invoice_draft_export_id")
            or item.get("deal_pack_export_id")
        )
        if record_id:
            by_id[record_id] = item
    records = list(by_id.values())
    engine[records_key] = records
    engine[latest_key] = records[-1] if records else {}
    return engine


def persist_safe_action(event_type, subject_id, **details):
    append_action(event_type, subject_id, details)


def attempt_enquiry_notification(enquiry, previous_record=None):
    notification = deliver_enquiry_notification(enquiry, previous_record=previous_record)
    upsert_record(
        "enquiry_notification_record",
        notification["notification_id"],
        notification,
    )
    PERSISTED_ENQUIRY_NOTIFICATIONS[:] = list_records("enquiry_notification_record")
    persist_safe_action(
        "enquiry_notification_attempt",
        notification["notification_id"],
        related_enquiry_id=notification["related_enquiry_id"],
        recipient_address=notification["recipient_address"],
        delivery_status=notification["delivery_status"],
        last_attempt_at=notification["last_attempt_at"],
        retry_attempts=notification["retry_attempts"],
        failure_reason=notification["failure_reason"],
        informational_only=True,
        sensitive_enquiry_content_logged=False,
        automatic_acceptance_enabled=False,
        automatic_payment_enabled=False,
        automatic_brief_generation_enabled=False,
        automatic_candidate_outreach_enabled=False,
        automatic_search_activity_enabled=False,
        automatic_delivery_enabled=False,
        external_integrations_enabled=False,
    )
    return notification


def is_secret_backup_path(path):
    name = os.path.basename(path).lower()
    return name == ".env" or name.endswith(".env") or "secret" in name


def copy_checkpoint_directory(source, destination):
    files_copied = 0

    for root, directories, files in os.walk(source):
        directories[:] = [
            directory
            for directory in directories
            if not is_secret_backup_path(directory)
        ]
        relative_root = os.path.relpath(root, source)
        target_root = destination if relative_root == "." else os.path.join(destination, relative_root)
        os.makedirs(target_root, exist_ok=True)

        for filename in files:
            source_file = os.path.join(root, filename)

            if is_secret_backup_path(source_file):
                continue

            shutil.copy2(source_file, os.path.join(target_root, filename))
            files_copied += 1

    return files_copied


def create_system_checkpoint():
    created_at = datetime.now(timezone.utc)
    checkpoint_id = f"checkpoint-{created_at.strftime('%Y%m%dT%H%M%S%fZ')}"
    backup_path = os.path.join(BACKUPS_DIR, checkpoint_id)
    files_copied = 0

    os.makedirs(backup_path, exist_ok=False)

    for source in CHECKPOINT_SOURCES:
        if not os.path.exists(source):
            continue

        destination = os.path.join(backup_path, source)

        if os.path.isdir(source):
            files_copied += copy_checkpoint_directory(source, destination)
        elif not is_secret_backup_path(source):
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            shutil.copy2(source, destination)
            files_copied += 1

    return {
        "checkpoint_id": checkpoint_id,
        "created_at": created_at.isoformat(),
        "files_copied": files_copied,
        "backup_path": backup_path,
        "capital_execution": False
    }
def render_approval_cards(approval_items):
    if not approval_items:
        return "<p class=\"muted\">No pending approval requests.</p>"

    cards = []

    for approval in approval_items:
        approval_id = str(approval.get("approval_id", ""))
        escaped_id = escape(approval_id)
        route_result = approval.get("route_result", {}) or {}

        cards.append(
            "<article class=\"card\">"
            f"<h3>Approval Request</h3>"
            f"<p><span>Approval ID</span>{escape(approval_id)}</p>"
            f"<p><span>Status</span><strong>{escape(str(approval.get('status', 'unknown')))}</strong></p>"
            f"<p><span>Provider</span>{escape(str(route_result.get('provider', route_result.get('provider_name', 'unknown'))))}</p>"
            f"<p><span>Task type</span>{escape(str(route_result.get('task_type', 'unknown')))}</p>"
            f"<p><span>Estimated cost</span>{escape(str(route_result.get('estimated_cost', 'unknown')))}</p>"
            f"<p><span>Avoided cost</span>{escape(str(route_result.get('avoided_cost', 'unknown')))}</p>"
            f"<p><span>Capital execution</span><strong>false</strong></p>"
            "<div class=\"action-row\">"
            f"<button class=\"approval-action\" type=\"button\" data-decision=\"approved\" data-approval-id=\"{escaped_id}\">Approve</button>"
            f"<button class=\"approval-action reject-action\" type=\"button\" data-decision=\"rejected\" data-approval-id=\"{escaped_id}\">Reject</button>"
            "</div>"
            "</article>"
        )

    return "".join(cards)

def provider_guard_status(provider_name):
    allowed = provider_allowed(provider_name)
    return {
        "allowed": allowed,
        "status": "allowed" if allowed else "blocked"
    }


def render_provider_cards(provider_items):
    cards = []

    for provider in provider_items:
        score = provider.get("score") or {}
        name = str(provider.get("name", "unknown"))
        escaped_name = escape(name)
        status_class = "ok" if provider.get("guard_allowed") else "blocked"

        cards.append(
            "<article class=\"card\">"
            f"<h3>{escaped_name}</h3>"
            f"<p><span>Type</span>{escape(str(provider.get('provider_type', 'unknown')))}</p>"
            f"<p><span>Enabled</span>{escape(str(provider.get('enabled', False)))}</p>"
            f"<p><span>Guard</span><strong class=\"{status_class}\">{escape(str(provider.get('guard_status', 'unknown')))}</strong></p>"
            f"<p><span>Score</span>{escape(str(score.get('score', 'not scored')))}</p>"
            f"<p><span>Success</span>{escape(str(score.get('success_count', 0)))}</p>"
            f"<p><span>Failures</span>{escape(str(score.get('failure_count', 0)))}</p>"
            f"<button class=\"reset-score\" type=\"button\" data-provider=\"{escaped_name}\">Reset score</button>"
            "</article>"
        )

    return "".join(cards)


def render_table(rows, columns):
    if not rows:
        return "<p class=\"muted\">No data found.</p>"

    header = "".join(f"<th>{escape(label)}</th>" for label, _ in columns)
    body_rows = []

    for row in rows:
        cells = "".join(
            f"<td>{escape(str(row.get(key, '')))}</td>"
            for _, key in columns
        )
        body_rows.append(f"<tr>{cells}</tr>")

    return (
        "<div class=\"table-wrap\">"
        "<table>"
        f"<thead><tr>{header}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table>"
        "</div>"
    )


def render_provider_wins_chart(win_counts):
    if not win_counts:
        return "<p class=\"muted\">No route history found.</p>"

    max_count = max(win_counts.values()) or 1
    rows = []

    for index, (provider, count) in enumerate(win_counts.items()):
        width = int((count / max_count) * 220)
        y = 28 + (index * 36)
        rows.append(
            f"<text x=\"0\" y=\"{y}\" class=\"chart-label\">{escape(str(provider))}</text>"
            f"<rect x=\"130\" y=\"{y - 16}\" width=\"{width}\" height=\"18\" rx=\"3\"></rect>"
            f"<text x=\"{140 + width}\" y=\"{y}\" class=\"chart-value\">{escape(str(count))}</text>"
        )

    height = 24 + (len(win_counts) * 36)
    return (
        f"<svg class=\"chart\" viewBox=\"0 0 420 {height}\" role=\"img\" aria-label=\"Provider wins chart\">"
        f"{''.join(rows)}"
        "</svg>"
    )


def render_latency_trend_chart(history_rows):
    points = []

    for row in history_rows[-12:]:
        latency = dashboard.parse_float(row.get("latency"))
        points.append((row.get("provider") or "unknown", latency))

    if not points:
        return "<p class=\"muted\">No latency history found.</p>"

    max_latency = max(latency for _, latency in points) or 1
    chart_points = []
    labels = []

    for index, (provider, latency) in enumerate(points):
        x = 20 + (index * (320 / max(len(points) - 1, 1)))
        y = 150 - ((latency / max_latency) * 120)
        chart_points.append(f"{round(x, 2)},{round(y, 2)}")
        labels.append(
            f"<circle cx=\"{round(x, 2)}\" cy=\"{round(y, 2)}\" r=\"4\"></circle>"
            f"<title>{escape(str(provider))}: {round(latency, 3)}s</title>"
        )

    return (
        "<svg class=\"chart\" viewBox=\"0 0 360 180\" role=\"img\" aria-label=\"Latency trend chart\">"
        "<line x1=\"20\" y1=\"150\" x2=\"340\" y2=\"150\" class=\"axis\"></line>"
        "<line x1=\"20\" y1=\"20\" x2=\"20\" y2=\"150\" class=\"axis\"></line>"
        f"<polyline points=\"{' '.join(chart_points)}\"></polyline>"
        f"{''.join(labels)}"
        f"<text x=\"22\" y=\"18\" class=\"chart-value\">max {round(max_latency, 3)}s</text>"
        "</svg>"
    )


def render_route_count_summary(history_data):
    recent_count = len(history_data.get("recent_routing_history", []))
    total_count = history_data.get("total_route_count", 0)
    provider_count = len(history_data.get("provider_win_counts", {}))

    return (
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Total routes</span><strong>{escape(str(total_count))}</strong></div>"
        f"<div class=\"metric\"><span>Recent routes</span><strong>{escape(str(recent_count))}</strong></div>"
        f"<div class=\"metric\"><span>Winning providers</span><strong>{escape(str(provider_count))}</strong></div>"
        "</div>"
    )


def render_opportunity_metric_summary(analytics_data):
    return (
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Total opportunities</span><strong>{escape(str(analytics_data.get('total_opportunities', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Avg. confidence</span><strong>{escape(str(analytics_data.get('average_confidence', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Estimated value</span><strong>{escape(str(analytics_data.get('total_estimated_value', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Estimated benefit</span><strong>{escape(str(analytics_data.get('total_estimated_benefit', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Realized value</span><strong>{escape(str(analytics_data.get('total_realized_value', 0)))}</strong></div>"
        "</div>"
    )


def render_governance_metric_summary(analytics_data):
    return (
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Pending</span><strong>{escape(str(analytics_data.get('pending_count', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Approved</span><strong>{escape(str(analytics_data.get('approved_count', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Rejected</span><strong>{escape(str(analytics_data.get('rejected_count', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Approval Rate %</span><strong>{escape(str(analytics_data.get('approval_rate', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Average Review Time</span><strong>{escape(str(analytics_data.get('average_approval_hours', 0)))}h</strong></div>"
        "</div>"
    )


def pending_review_opportunities(opportunity_items):
    pending = [
        opportunity
        for opportunity in opportunity_items
        if opportunity.get("status") == "pending_review"
    ]

    return sorted(
        pending,
        key=lambda opportunity: (
            float(opportunity.get("confidence", 0) or 0),
            float(opportunity.get("estimated_benefit", opportunity.get("estimated_value", 0)) or 0)
        ),
        reverse=True
    )


def render_executive_summary(health_data, provider_data, pending_opportunities, pending_approvals):
    total_pending_benefit = sum(
        float(opportunity.get("estimated_benefit", opportunity.get("estimated_value", 0)) or 0)
        for opportunity in pending_opportunities
    )
    highest_confidence = pending_opportunities[0] if pending_opportunities else None

    if pending_approvals:
        next_action = "Review route approval queue"
    elif highest_confidence:
        next_action = f"Review opportunity: {highest_confidence.get('title', 'Untitled opportunity')}"
    else:
        next_action = "No pending human review"

    enabled_provider_count = len([
        provider
        for provider in provider_data
        if provider.get("enabled")
    ])

    return (
        "<div class=\"panel\">"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>System status</span><strong>{escape(str(health_data.get('status', 'unknown')))}</strong></div>"
        "<div class=\"metric\"><span>Capital execution</span><strong>false</strong></div>"
        f"<div class=\"metric\"><span>Enabled providers</span><strong>{escape(str(enabled_provider_count))}</strong></div>"
        f"<div class=\"metric\"><span>Pending opportunity reviews</span><strong>{escape(str(len(pending_opportunities)))}</strong></div>"
        f"<div class=\"metric\"><span>Pending approval queue</span><strong>{escape(str(len(pending_approvals)))}</strong></div>"
        f"<div class=\"metric\"><span>Pending estimated benefit</span><strong>{escape(str(round(total_pending_benefit, 4)))}</strong></div>"
        f"<div class=\"metric\"><span>Highest confidence</span><strong>{escape(str(highest_confidence.get('title') if highest_confidence else 'None'))}</strong></div>"
        f"<div class=\"metric\"><span>Recommended next action</span><strong>{escape(str(next_action))}</strong></div>"
        "</div>"
        "</div>"
    )


def suggested_profit_action(opportunity):
    if not opportunity:
        return "Monitor"

    confidence = float(opportunity.get("confidence", 0) or 0)
    risk = str(opportunity.get("risk_level", "")).lower()

    if confidence < 0.45:
        return "Reject"

    if risk in {"high", "critical"}:
        return "Monitor"

    if confidence >= 0.7:
        return "Approve"

    return "Monitor"


def render_profit_command_mode(pending_opportunities, pending_approvals, scanner_data):
    total_estimated_value = sum(
        float(opportunity.get("estimated_value", 0) or 0)
        for opportunity in pending_opportunities
    )
    total_estimated_benefit = sum(
        float(opportunity.get("estimated_benefit", opportunity.get("estimated_value", 0)) or 0)
        for opportunity in pending_opportunities
    )
    best_opportunity = pending_opportunities[0] if pending_opportunities else None
    items_needing_approval = len(pending_opportunities) + len(pending_approvals)
    scanner_analytics = scanner_data.get("analytics", {}) if scanner_data else {}

    if best_opportunity:
        recommendation = (
            f"Dave says review {best_opportunity.get('title', 'this opportunity')} first. "
            f"It has the strongest profit signal right now, but Gareth approval is still required."
        )
    elif pending_approvals:
        recommendation = "Dave says clear the route approval queue before looking for new action."
    else:
        recommendation = "Dave says there is no profit action waiting for approval right now."

    return (
        "<div class=\"analytics-grid\">"
        "<div class=\"panel\">"
        "<h3>Profit Snapshot</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Today's estimated opportunity value</span><strong>{escape(str(round(total_estimated_value, 4)))}</strong></div>"
        f"<div class=\"metric\"><span>Today's estimated benefit</span><strong>{escape(str(round(total_estimated_benefit, 4)))}</strong></div>"
        f"<div class=\"metric\"><span>Best opportunity</span><strong>{escape(str(best_opportunity.get('title') if best_opportunity else 'None'))}</strong></div>"
        f"<div class=\"metric\"><span>Best confidence</span><strong>{escape(str(best_opportunity.get('confidence', 0) if best_opportunity else 0))}</strong></div>"
        f"<div class=\"metric\"><span>Best risk</span><strong>{escape(str(best_opportunity.get('risk_level', 'none') if best_opportunity else 'none'))}</strong></div>"
        f"<div class=\"metric\"><span>Items needing Gareth approval</span><strong>{escape(str(items_needing_approval))}</strong></div>"
        f"<div class=\"metric\"><span>Opportunities scanned</span><strong>{escape(str(scanner_analytics.get('opportunities_scanned', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Passed filters</span><strong>{escape(str(scanner_analytics.get('passed_filters', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Worth reviewing</span><strong>{escape(str(scanner_analytics.get('worth_reviewing', 0)))}</strong></div>"
        "<div class=\"metric\"><span>Capital execution status</span><strong>false</strong></div>"
        "</div>"
        f"<p class=\"description\"><span>Dave-style recommendation</span>{escape(recommendation)}</p>"
        "</div>"
        "<div class=\"panel\">"
        "<h3>System Status</h3>"
        "<p><span>Scanning</span><strong>System is scanning opportunities</strong></p>"
        "<p><span>Ranking</span><strong>System is ranking profit potential</strong></p>"
        "<p><span>Approval</span><strong>System is waiting for Gareth approval</strong></p>"
        "<p><span>Capital</span><strong>No capital is being moved automatically</strong></p>"
        "</div>"
        "</div>"
    )


def render_dave_recommends_card(pending_opportunities):
    opportunity = pending_opportunities[0] if pending_opportunities else None

    if not opportunity:
        return (
            "<div class=\"panel\">"
            "<h3>Dave Recommends</h3>"
            "<p class=\"muted\">No pending profit opportunity needs action right now.</p>"
            "<p><span>Capital execution</span><strong>false</strong></p>"
            "</div>"
        )

    opportunity_id = str(opportunity.get("id", ""))
    escaped_id = escape(opportunity_id)
    action = suggested_profit_action(opportunity)
    why = opportunity.get("confidence_reason") or opportunity.get("description") or "It is the highest ranked pending profit opportunity."
    button_class = "reject-action" if action == "Reject" else ""

    hidden_monitor_controls = ""
    if action == "Monitor":
        hidden_monitor_controls = (
            "<select class=\"outcome-status hidden-control\"><option value=\"monitored\" selected>monitored</option></select>"
            "<input class=\"realized-value hidden-control\" type=\"hidden\" value=\"\">"
            "<textarea class=\"outcome-note hidden-control\">Marked for monitoring from Dave Recommends.</textarea>"
        )

    if action == "Monitor":
        button = f"<button class=\"opportunity-outcome\" type=\"button\" data-opportunity-id=\"{escaped_id}\">Monitor</button>"
    else:
        button = f"<button class=\"opportunity-action {button_class}\" type=\"button\" data-action=\"{action.lower()}\" data-opportunity-id=\"{escaped_id}\">{escape(action)}</button>"

    return (
        "<div class=\"panel\">"
        "<h3>Dave Recommends</h3>"
        f"<p><span>Opportunity</span><strong>{escape(str(opportunity.get('title', 'Untitled opportunity')))}</strong></p>"
        f"<p><span>Recommended action</span><strong>{escape(action)}</strong></p>"
        f"<p class=\"description\"><span>Why this matters</span>{escape(str(why))}</p>"
        f"<textarea class=\"reviewer-note\" placeholder=\"Reviewer note\" data-opportunity-id=\"{escaped_id}\"></textarea>"
        f"{hidden_monitor_controls}"
        f"<div class=\"action-row\">{button}</div>"
        "<p class=\"muted\">Gareth stays in control. Capital execution remains false.</p>"
        "</div>"
    )


def render_wasted_money_hunter_card(scanner_data):
    analytics_data = scanner_data.get("analytics", {}) if scanner_data else {}
    opportunity = analytics_data.get("highest_value_opportunity") or {}

    if not opportunity:
        return (
            "<div class=\"panel\">"
            "<h3>Wasted Money Hunter</h3>"
            "<p class=\"muted\">No wasted money opportunities found.</p>"
            "<p><span>Capital execution</span><strong>false</strong></p>"
            "</div>"
        )

    return (
        "<div class=\"panel\">"
        "<h3>Wasted Money Hunter</h3>"
        f"<p><span>Best Opportunity</span><strong>{escape(str(opportunity.get('title', 'Unknown')))}</strong></p>"
        f"<p><span>Category</span>{escape(str(opportunity.get('category', 'unknown')))}</p>"
        f"<p><span>Estimated Annual Savings</span><strong>GBP {escape(str(opportunity.get('estimated_annual_savings', 0)))}</strong></p>"
        f"<p><span>Confidence</span>{escape(str(opportunity.get('confidence', 0)))}</p>"
        f"<p><span>Gareth Score</span>{escape(str(opportunity.get('gareth_score', 0)))}</p>"
        f"<p><span>Dave Recommends</span><strong>{escape(str(opportunity.get('recommended_action', 'review')).title())}</strong></p>"
        f"<p class=\"description\"><span>Reason</span>{escape(str(opportunity.get('reason', 'High value, low complexity, low capital requirement.')))}</p>"
        "<p class=\"muted\">No vendor action, scraping, trading, or capital movement is automated.</p>"
        "</div>"
    )


def get_agent_safety_dashboard_summary(pending_approvals):
    recent_events = list_approval_events(limit=100)
    safety_events = [
        event
        for event in recent_events
        if str(event.get("event_type", "")).startswith("agent_safety_")
    ]
    pending_safety_approvals = [
        approval
        for approval in pending_approvals
        if (approval.get("route_result", {}) or {}).get("source") == "agent_safety_gate"
    ]
    blocked_actions = [
        event
        for event in safety_events
        if event.get("event_type") == "agent_safety_blocked"
        or event.get("decision") == "BLOCK"
    ]

    return {
        "recent_evaluations": len(safety_events),
        "pending_safety_approvals": len(pending_safety_approvals),
        "blocked_actions": len(blocked_actions),
        "capital_execution": False,
    }


def render_agent_safety_gate_card(summary):
    return (
        "<div class=\"panel\">"
        "<h3>Agent Safety Gate</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Recent evaluations</span><strong>{escape(str(summary.get('recent_evaluations', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Pending safety approvals</span><strong>{escape(str(summary.get('pending_safety_approvals', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Blocked actions</span><strong>{escape(str(summary.get('blocked_actions', 0)))}</strong></div>"
        "<div class=\"metric\"><span>Capital execution</span><strong>false</strong></div>"
        "</div>"
        "<p class=\"muted\">Agent Safety Gate checks proposed actions before they happen.</p>"
        "</div>"
    )


def render_glirn_dashboard_card(glirn_data):
    summary = glirn_data.get("summary", {}) or {}
    radar = glirn_data.get("legal_opportunity_radar", {}) or {}
    highest = radar.get("top_opportunity") or summary.get("highest_opportunity") or {}
    candidate = radar.get("highest_value_candidate") or {}
    client_firm = radar.get("highest_value_client_firm") or {}
    dave_recommendation = highest.get("dave_recommendation", "Review highest-value GLIRN opportunity before any outbound action.")

    return (
        "<div class=\"panel\">"
        "<h3>Legal Opportunity Radar</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Legal sectors</span><strong>{escape(str(len(glirn_data.get('legal_sectors', []))))}</strong></div>"
        f"<div class=\"metric\"><span>Recruitment opportunities</span><strong>{escape(str(summary.get('total_opportunities', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Human approval queue</span><strong>{escape(str(summary.get('pending_human_approval', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Expected fee value</span><strong>GBP {escape(str(summary.get('total_expected_fee_value', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Top radar score</span><strong>{escape(str(highest.get('radar_priority_score', summary.get('highest_score', 0))))}</strong></div>"
        "<div class=\"metric\"><span>Capital execution</span><strong>false</strong></div>"
        "</div>"
        "<h3>Dave Recommends First</h3>"
        f"<p><span>Top GLIRN opportunity</span><strong>{escape(str(highest.get('title', 'No GLIRN opportunity available')))}</strong></p>"
        f"<p><span>Practice area</span>{escape(str(highest.get('practice_area', 'none')))}</p>"
        f"<p><span>Expected fee</span>GBP {escape(str(highest.get('expected_fee_value', 0)))}</p>"
        f"<p><span>Highest-value candidate</span>{escape(str(candidate.get('full_name', 'none')))}</p>"
        f"<p><span>Highest-value client firm</span>{escape(str(client_firm.get('name', 'none')))}</p>"
        f"<p class=\"description\"><span>Recommendation</span>{escape(str(dave_recommendation))}</p>"
        "<p class=\"muted\">Gareth approval is required before any outbound candidate, client, or fee action.</p>"
        "</div>"
    )


def render_glirn_approval_centre(glirn_data):
    approval_centre = glirn_data.get("approval_centre", {}) or {}
    locks = approval_centre.get("locks", {}) or {}
    queue = approval_centre.get("queue", []) or []

    queue_cards = []
    for item in queue[:3]:
        queue_cards.append(
            "<article class=\"card\">"
            f"<h3>{escape(str(item.get('title', 'GLIRN approval item')))}</h3>"
            f"<p><span>Status</span><strong>{escape(str(item.get('status', 'waiting_for_gareth_approval')))}</strong></p>"
            f"<p><span>Practice area</span>{escape(str(item.get('practice_area', 'unknown')))}</p>"
            f"<p><span>Expected fee</span>GBP {escape(str(item.get('expected_fee_value', 0)))}</p>"
            f"<p><span>Approval ID</span>{escape(str(item.get('approval_id') or 'not created yet'))}</p>"
            "<p><span>Actions</span>Approve / Reject / Monitor</p>"
            "<p class=\"muted\">Approval reason required. Locks remain on until Gareth approves.</p>"
            "</article>"
        )

    if not queue_cards:
        queue_cards.append("<p class=\"muted\">No GLIRN approval items waiting.</p>")

    return (
        "<div class=\"panel\">"
        "<h3>GLIRN Human Approval Centre</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Dashboard status</span><strong>{escape(str(approval_centre.get('status', 'Waiting for Gareth Approval')))}</strong></div>"
        f"<div class=\"metric\"><span>GLIRN queue</span><strong>{escape(str(approval_centre.get('pending_count', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Outbound action lock</span><strong>{escape(str(locks.get('outbound_action_locked', True)).lower())}</strong></div>"
        f"<div class=\"metric\"><span>Candidate introduction lock</span><strong>{escape(str(locks.get('candidate_introduction_locked', True)).lower())}</strong></div>"
        f"<div class=\"metric\"><span>Client engagement lock</span><strong>{escape(str(locks.get('client_engagement_locked', True)).lower())}</strong></div>"
        f"<div class=\"metric\"><span>Fee negotiation lock</span><strong>{escape(str(locks.get('fee_negotiation_locked', True)).lower())}</strong></div>"
        "</div>"
        "<p class=\"muted\">No candidate introduction, client engagement, fee proposal, or outbound action is allowed without Gareth approval.</p>"
        "<div class=\"grid\">"
        f"{''.join(queue_cards)}"
        "</div>"
        "</div>"
    )


def render_glirn_compliance_core(glirn_data):
    compliance_core = glirn_data.get("compliance_core", {}) or {}
    alerts = compliance_core.get("compliance_alerts", []) or []
    missing_alerts = compliance_core.get("missing_consent_alerts", []) or []
    expiry_alerts = compliance_core.get("consent_expiry_alerts", []) or []
    restricted = compliance_core.get("restricted_outbound_actions", []) or []

    return (
        "<div class=\"panel\">"
        "<h3>GLIRN Compliance Core</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Status</span><strong>{escape(str(compliance_core.get('status', 'Compliance-First Controls Active')))}</strong></div>"
        f"<div class=\"metric\"><span>Readiness score</span><strong>{escape(str(compliance_core.get('compliance_readiness_score', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Compliance alerts</span><strong>{escape(str(len(alerts)))}</strong></div>"
        f"<div class=\"metric\"><span>Missing consent alerts</span><strong>{escape(str(len(missing_alerts)))}</strong></div>"
        f"<div class=\"metric\"><span>Consent expiry alerts</span><strong>{escape(str(len(expiry_alerts)))}</strong></div>"
        f"<div class=\"metric\"><span>Restricted outbound actions</span><strong>{escape(str(len(restricted)))}</strong></div>"
        "</div>"
        "<p class=\"muted\">Candidate introductions require active consent. Client candidate details require recorded terms. Expired consent blocks outbound action.</p>"
        "</div>"
    )


def render_glirn_executive_search(glirn_data):
    executive_search = glirn_data.get("executive_search", {}) or {}
    top_items = executive_search.get("top_executive_opportunities", []) or []
    dave_first = executive_search.get("dave_recommends_first") or {}

    cards = []
    for item in top_items[:3]:
        cards.append(
            "<article class=\"card\">"
            f"<h3>{escape(str(item.get('title', 'Executive opportunity')))}</h3>"
            f"<p><span>Workflow</span>{escape(str(item.get('workflow', 'unknown')))}</p>"
            f"<p><span>Seniority</span>{escape(str(item.get('candidate_seniority_classification', 'unknown')))}</p>"
            f"<p><span>Estimated Placement Fee</span>GBP {escape(str(item.get('estimated_placement_fee', 0)))}</p>"
            f"<p><span>Estimated Retainer Fee</span>GBP {escape(str(item.get('estimated_retainer_fee', 0)))}</p>"
            f"<p><span>Premium Opportunity Flag</span><strong>{escape(str(item.get('premium_opportunity', False)).lower())}</strong></p>"
            f"<p><span>High-fee priority</span>{escape(str(item.get('high_fee_priority_score', 0)))}</p>"
            f"<p class=\"description\"><span>Dave Recommends</span>{escape(str(item.get('dave_recommendation', 'Review.')))}</p>"
            "</article>"
        )

    if not cards:
        cards.append("<p class=\"muted\">No executive search opportunities available.</p>")

    return (
        "<div class=\"panel\">"
        "<h3>Executive Search Engine</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Status</span><strong>{escape(str(executive_search.get('status', 'Executive Search Engine Active')))}</strong></div>"
        f"<div class=\"metric\"><span>Top Executive Opportunities</span><strong>{escape(str(len(top_items)))}</strong></div>"
        f"<div class=\"metric\"><span>Estimated Placement Fee</span><strong>GBP {escape(str(dave_first.get('estimated_placement_fee', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Estimated Retainer Fee</span><strong>GBP {escape(str(dave_first.get('estimated_retainer_fee', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Premium Opportunity Flag</span><strong>{escape(str(dave_first.get('premium_opportunity', False)).lower())}</strong></div>"
        "</div>"
        f"<p><span>Dave Recommends First</span><strong>{escape(str(dave_first.get('title', 'No executive opportunity available')))}</strong></p>"
        "<p class=\"muted\">Executive candidate outreach requires active consent. Client engagement requires client terms. Retained search proposals require Gareth approval.</p>"
        "<div class=\"grid\">"
        f"{''.join(cards)}"
        "</div>"
        "</div>"
    )


def render_glirn_legal_intelligence_network(glirn_data):
    network = glirn_data.get("intelligence_network", {}) or {}
    salary_signals = network.get("top_salary_signals", []) or []
    hot_areas = network.get("hot_practice_areas", []) or []
    jurisdictions = network.get("growing_jurisdictions", []) or []
    hiring_alerts = network.get("hiring_trend_alerts", []) or []
    dave_first = network.get("dave_recommends_first") or {}

    top_salary = salary_signals[0] if salary_signals else {}
    hot_area = hot_areas[0] if hot_areas else {}
    jurisdiction = jurisdictions[0] if jurisdictions else {}
    hiring_alert = hiring_alerts[0] if hiring_alerts else {}

    return (
        "<div class=\"panel\">"
        "<h3>Legal Intelligence Network</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Status</span><strong>{escape(str(network.get('status', 'Legal Intelligence Network Active')))}</strong></div>"
        f"<div class=\"metric\"><span>Top Salary Signals</span><strong>GBP {escape(str(top_salary.get('estimated_salary', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Hot Practice Areas</span><strong>{escape(str(hot_area.get('practice_area', 'none')))}</strong></div>"
        f"<div class=\"metric\"><span>Growing Jurisdictions</span><strong>{escape(str(jurisdiction.get('jurisdiction', 'none')))}</strong></div>"
        f"<div class=\"metric\"><span>Hiring Trend Alerts</span><strong>{escape(str(len(hiring_alerts)))}</strong></div>"
        "</div>"
        f"<p><span>Client Intelligence Hook</span>{escape(str(network.get('client_intelligence_hook', 'Use intelligence as the client hook.')))}</p>"
        f"<p><span>Dave Recommends First</span><strong>{escape(str(dave_first.get('recommendation', 'Lead with intelligence before recruitment placement.')))}</strong></p>"
        f"<p><span>Hiring alert</span>{escape(str(hiring_alert.get('title', 'No hiring trend alert')))}</p>"
        "<p class=\"muted\">Client-facing intelligence reports require Gareth approval. Candidate-specific data requires active consent.</p>"
        "</div>"
    )


def render_glirn_commercial_revenue_engine(glirn_data):
    engine = glirn_data.get("commercial_revenue_engine", {}) or {}
    highest = engine.get("highest_fee_opportunity") or {}
    dave_first = engine.get("dave_recommends_first") or {}

    return (
        "<div class=\"panel\">"
        "<h3>Commercial Revenue Engine</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Status</span><strong>{escape(str(engine.get('status', 'Commercial Revenue Controls Active')))}</strong></div>"
        f"<div class=\"metric\"><span>Estimated Revenue Pipeline</span><strong>GBP {escape(str(engine.get('estimated_revenue_pipeline', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Highest Fee Opportunity</span><strong>{escape(str(highest.get('title', 'none')))}</strong></div>"
        f"<div class=\"metric\"><span>Fee Type</span><strong>{escape(str(highest.get('fee_type', 'none')))}</strong></div>"
        f"<div class=\"metric\"><span>Invoice Readiness</span><strong>{escape(str(highest.get('invoice_readiness', 'blocked')))}</strong></div>"
        f"<div class=\"metric\"><span>Awaiting Gareth Approval</span><strong>{escape(str(engine.get('awaiting_gareth_approval', True)).lower())}</strong></div>"
        "</div>"
        f"<p><span>Dave Recommends First</span>{escape(str(dave_first.get('recommendation', 'Review commercial terms before any fee proposal.')))}</p>"
        "<p class=\"muted\">No fee proposal, invoice readiness, or candidate submission proceeds without Gareth approval and compliance readiness.</p>"
        "</div>"
    )


def render_glirn_client_acquisition_engine(glirn_data):
    engine = glirn_data.get("client_acquisition_engine", {}) or {}
    top_clients = engine.get("top_target_clients", []) or []
    highest = engine.get("highest_fee_potential_client") or {}
    dave_first = engine.get("dave_recommends_first") or {}
    top = top_clients[0] if top_clients else {}

    return (
        "<div class=\"panel\">"
        "<h3>Client Acquisition Engine</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Status</span><strong>{escape(str(engine.get('status', 'Client Acquisition Controls Active')))}</strong></div>"
        f"<div class=\"metric\"><span>Top Target Clients</span><strong>{escape(str(len(top_clients)))}</strong></div>"
        f"<div class=\"metric\"><span>Highest Fee Potential Client</span><strong>{escape(str(highest.get('client_name', 'none')))}</strong></div>"
        f"<div class=\"metric\"><span>Hiring Likelihood</span><strong>{escape(str(top.get('hiring_likelihood_score', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Recommended Practice Area</span><strong>{escape(str(top.get('preferred_practice_area_match', 'none')))}</strong></div>"
        f"<div class=\"metric\"><span>Awaiting Gareth Approval</span><strong>{escape(str(engine.get('awaiting_gareth_approval', True)).lower())}</strong></div>"
        "</div>"
        f"<p><span>Dave Recommends First</span>{escape(str(dave_first.get('recommendation', 'Review top target client before outreach.')))}</p>"
        "<p class=\"muted\">No outreach, fee discussion, or candidate details are shared without Gareth approval and compliance readiness.</p>"
        "</div>"
    )


def render_glirn_candidate_discovery_engine(glirn_data):
    engine = glirn_data.get("candidate_discovery_engine", {}) or {}
    top_candidates = engine.get("top_candidate_opportunities", []) or []
    highest = engine.get("highest_estimated_placement_value") or {}
    dave_first = engine.get("dave_recommends_first") or {}
    top = top_candidates[0] if top_candidates else {}

    return (
        "<div class=\"panel\">"
        "<h3>Candidate Discovery Engine</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Status</span><strong>{escape(str(engine.get('status', 'Candidate Discovery Controls Active')))}</strong></div>"
        f"<div class=\"metric\"><span>Top Candidate Opportunities</span><strong>{escape(str(len(top_candidates)))}</strong></div>"
        f"<div class=\"metric\"><span>Highest Estimated Placement Value</span><strong>GBP {escape(str(highest.get('estimated_placement_value', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Candidate Consent Status</span><strong>{escape(str(top.get('consent_readiness_status', 'missing')))}</strong></div>"
        f"<div class=\"metric\"><span>Practice Area Match</span><strong>{escape(str(top.get('practice_area_match_score', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Awaiting Gareth Approval</span><strong>{escape(str(engine.get('awaiting_gareth_approval', True)).lower())}</strong></div>"
        "</div>"
        f"<p><span>Dave Recommends First</span>{escape(str(dave_first.get('recommendation', 'Review top candidate before outreach.')))}</p>"
        "<p class=\"muted\">No candidate outreach, profile activation, details sharing, or candidate-specific intelligence proceeds without Gareth approval and active consent.</p>"
        "</div>"
    )


def render_glirn_matching_engine(glirn_data):
    engine = glirn_data.get("matching_engine", {}) or {}
    matches = engine.get("top_ranked_placement_matches", []) or []
    highest = engine.get("highest_match_revenue_score") or {}
    dave_first = engine.get("dave_recommends_first") or {}
    top = matches[0] if matches else {}

    return (
        "<div class=\"panel\">"
        "<h3>Matching & Placement Engine</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Status</span><strong>{escape(str(engine.get('status', 'Matching & Placement Controls Active')))}</strong></div>"
        f"<div class=\"metric\"><span>Top Ranked Placement Matches</span><strong>{escape(str(len(matches)))}</strong></div>"
        f"<div class=\"metric\"><span>Highest Match Revenue Score</span><strong>{escape(str(highest.get('match_revenue_score', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Placement Probability</span><strong>{escape(str(top.get('placement_probability_score', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Candidate Consent Status</span><strong>{escape(str(top.get('candidate_consent_status', 'missing')))}</strong></div>"
        f"<div class=\"metric\"><span>Client Terms Status</span><strong>{escape(str(top.get('client_terms_status', 'missing')))}</strong></div>"
        f"<div class=\"metric\"><span>Awaiting Gareth Approval</span><strong>{escape(str(engine.get('awaiting_gareth_approval', True)).lower())}</strong></div>"
        "</div>"
        f"<p><span>Dave Recommends First</span>{escape(str(dave_first.get('recommendation', 'Review top placement match before action.')))}</p>"
        "<p class=\"muted\">No match activation, candidate detail sharing, client-facing action, or placement action proceeds without consent, terms, and Gareth approval.</p>"
        "</div>"
    )


def render_glirn_executive_autopilot(glirn_data):
    autopilot = glirn_data.get("executive_autopilot", {}) or {}
    top_opportunity = autopilot.get("top_opportunity") or {}
    top_candidate = autopilot.get("top_candidate") or {}
    top_client = autopilot.get("top_client") or {}
    top_match = autopilot.get("top_placement_match") or {}
    dave_first = autopilot.get("dave_recommends_first") or {}

    return (
        "<div class=\"panel\">"
        "<h3>Executive Autopilot</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Status</span><strong>{escape(str(autopilot.get('status', 'Executive Autopilot Waiting for Gareth Approval')))}</strong></div>"
        f"<div class=\"metric\"><span>Top Opportunity</span><strong>{escape(str(top_opportunity.get('title', 'none')))}</strong></div>"
        f"<div class=\"metric\"><span>Top Candidate</span><strong>{escape(str(top_candidate.get('candidate_name', 'none')))}</strong></div>"
        f"<div class=\"metric\"><span>Top Client</span><strong>{escape(str(top_client.get('client_name', 'none')))}</strong></div>"
        f"<div class=\"metric\"><span>Top Placement Match</span><strong>{escape(str(top_match.get('match_id', 'none')))}</strong></div>"
        f"<div class=\"metric\"><span>Highest Estimated Fee</span><strong>GBP {escape(str(autopilot.get('highest_estimated_fee', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Highest Placement Probability</span><strong>{escape(str(autopilot.get('highest_placement_probability', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Compliance Alerts</span><strong>{escape(str(len(autopilot.get('compliance_alerts', []) or [])))}</strong></div>"
        f"<div class=\"metric\"><span>Gareth Approval Queue</span><strong>{escape(str(autopilot.get('approval_queue_count', 0)))}</strong></div>"
        "</div>"
        f"<p><span>Dave Recommends First</span>{escape(str(dave_first.get('recommendation', 'Review before any GLIRN action.')))}</p>"
        f"<p><span>Recommended focus</span><strong>{escape(str(dave_first.get('recommended_focus', 'Review')))}</strong></p>"
        "<p class=\"muted\">No autonomous outreach, candidate introduction, client engagement, or fee proposal is allowed. Human approval remains mandatory.</p>"
        "</div>"
    )


def render_glirn_live_data_readiness(glirn_data):
    readiness = glirn_data.get("live_data_readiness", {}) or {}
    summary = readiness.get("source_readiness_summary", {}) or {}
    sources = readiness.get("source_registry", []) or []
    blocked = readiness.get("blocked_sources", []) or []
    pending = readiness.get("pending_sources", []) or []
    dave_first = readiness.get("dave_recommends_first") or {}
    top_source = sources[0] if sources else {}

    return (
        "<div class=\"panel\">"
        "<h3>Live Data Readiness Layer</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Status</span><strong>{escape(str(readiness.get('status', 'Live Data Readiness Controls Active')))}</strong></div>"
        f"<div class=\"metric\"><span>Proposed data sources</span><strong>{escape(str(summary.get('pending_sources', len(pending))))}</strong></div>"
        f"<div class=\"metric\"><span>Readiness status</span><strong>{escape(str(top_source.get('ingestion_readiness_status', 'not_ready')))}</strong></div>"
        f"<div class=\"metric\"><span>Risk level</span><strong>{escape(str(top_source.get('risk_level', 'unknown')))}</strong></div>"
        f"<div class=\"metric\"><span>Approval requirement</span><strong>{escape(str(top_source.get('human_approval_required', True)).lower())}</strong></div>"
        f"<div class=\"metric\"><span>Blocked sources</span><strong>{escape(str(summary.get('blocked_sources', len(blocked))))}</strong></div>"
        "</div>"
        f"<p><span>Next recommended action</span>{escape(str(dave_first.get('recommendation', 'Review source readiness before any integration.')))}</p>"
        "<p class=\"muted\">No external services, scraping, live fetching, candidate data ingestion, or automated recruitment decisions are enabled.</p>"
        "</div>"
    )


def render_glirn_integration_governance(glirn_data):
    governance = glirn_data.get("integration_governance", {}) or {}
    integrations = governance.get("integration_registry", []) or []
    approved = governance.get("approved_integrations", []) or []
    blocked = governance.get("blocked_integrations", []) or []
    pending = governance.get("pending_integrations", []) or []
    alerts = governance.get("governance_alerts", []) or []
    dave_first = governance.get("dave_recommends_first") or {}
    top = integrations[0] if integrations else {}

    return (
        "<div class=\"panel\">"
        "<h3>Integration Governance Layer</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Status</span><strong>{escape(str(governance.get('status', 'Integration Governance Controls Active')))}</strong></div>"
        f"<div class=\"metric\"><span>Pending integrations</span><strong>{escape(str(len(pending)))}</strong></div>"
        f"<div class=\"metric\"><span>Approved integrations</span><strong>{escape(str(len(approved)))}</strong></div>"
        f"<div class=\"metric\"><span>Blocked integrations</span><strong>{escape(str(len(blocked)))}</strong></div>"
        f"<div class=\"metric\"><span>Governance alerts</span><strong>{escape(str(len(alerts)))}</strong></div>"
        f"<div class=\"metric\"><span>Governance status</span><strong>{escape(str(top.get('governance_status', 'not_ready')))}</strong></div>"
        f"<div class=\"metric\"><span>Risk score</span><strong>{escape(str(top.get('risk_score', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Readiness score</span><strong>{escape(str(top.get('readiness_score', 0)))}</strong></div>"
        "</div>"
        f"<p><span>Dave Recommends First</span>{escape(str(dave_first.get('recommendation', 'Keep integrations inactive until Gareth approves.')))}</p>"
        "<p class=\"muted\">No live integrations, scraping, outbound connections, or autonomous activation are enabled. Human approval remains mandatory.</p>"
        "</div>"
    )


def render_glirn_deployment_readiness(glirn_data):
    readiness = glirn_data.get("deployment_readiness", {}) or {}
    gaps = readiness.get("critical_gaps", []) or []
    checklist = readiness.get("launch_checklist", []) or []
    dave_first = readiness.get("dave_recommends_first") or {}

    return (
        "<div class=\"panel\">"
        "<h3>Deployment Readiness Centre</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Status</span><strong>{escape(str(readiness.get('status', 'Deployment Readiness Assessment Active')))}</strong></div>"
        f"<div class=\"metric\"><span>Readiness score</span><strong>{escape(str(readiness.get('readiness_score', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Readiness grade</span><strong>{escape(str(readiness.get('readiness_grade', 'F')))}</strong></div>"
        f"<div class=\"metric\"><span>Critical gaps</span><strong>{escape(str(len(gaps)))}</strong></div>"
        f"<div class=\"metric\"><span>Launch checklist</span><strong>{escape(str(len(checklist)))}</strong></div>"
        f"<div class=\"metric\"><span>Integration readiness</span><strong>{escape(str(readiness.get('integration_readiness', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Compliance readiness</span><strong>{escape(str(readiness.get('compliance_readiness', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Operational readiness</span><strong>{escape(str(readiness.get('operational_readiness', 0)))}</strong></div>"
        "</div>"
        f"<p><span>Dave Recommends First</span>{escape(str(dave_first.get('recommendation', 'Review readiness before any deployment decision.')))}</p>"
        "<p class=\"muted\">Assessment only. No deployment actions, external connections, or autonomous activation are enabled. Human approval remains mandatory.</p>"
        "</div>"
    )


def render_glirn_operations_command_centre(glirn_data):
    centre = glirn_data.get("operations_command_centre", {}) or {}
    metrics = centre.get("key_metrics", {}) or {}
    health = centre.get("platform_health", {}) or {}
    dave_first = centre.get("dave_recommends_first") or {}

    return (
        "<div class=\"panel\">"
        "<h3>Operations Command Centre</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Status</span><strong>{escape(str(centre.get('status', 'Operations Command Centre Active')))}</strong></div>"
        f"<div class=\"metric\"><span>Total Opportunities</span><strong>{escape(str(metrics.get('total_opportunities', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Total Candidates</span><strong>{escape(str(metrics.get('total_candidates', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Total Clients</span><strong>{escape(str(metrics.get('total_clients', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Total Matches</span><strong>{escape(str(metrics.get('total_matches', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Estimated Revenue Pipeline</span><strong>GBP {escape(str(metrics.get('estimated_revenue_pipeline', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Compliance Alerts</span><strong>{escape(str(metrics.get('compliance_alerts', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Pending Gareth Approvals</span><strong>{escape(str(metrics.get('pending_gareth_approvals', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Readiness Score</span><strong>{escape(str(metrics.get('readiness_score', 0)))}</strong></div>"
        "</div>"
        f"<p><span>Dave Recommends First</span>{escape(str(dave_first.get('recommendation', 'Review operations before any action.')))}</p>"
        f"<p><span>Platform health</span>{escape(str(health.get('deployment_readiness', 'unknown')))}</p>"
        "<p class=\"muted\">Read-only operational view. No automation changes, external connections, outreach, or deployment actions are enabled.</p>"
        "</div>"
    )


def render_glirn_daily_executive_briefing(glirn_data):
    briefing = glirn_data.get("daily_executive_briefing", {}) or {}
    opportunities = briefing.get("top_3_opportunities", []) or []
    risks = briefing.get("top_3_risks", []) or []
    revenue_actions = briefing.get("top_3_revenue_actions", []) or []
    approvals = briefing.get("pending_gareth_approvals", []) or []
    warnings = briefing.get("compliance_warnings", []) or []
    dave_today = briefing.get("dave_recommends_today") or {}

    top_opportunity = opportunities[0] if opportunities else {}
    top_risk = risks[0] if risks else {}
    top_revenue = revenue_actions[0] if revenue_actions else {}

    return (
        "<div class=\"panel\">"
        "<h3>Daily Executive Briefing</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Status</span><strong>{escape(str(briefing.get('status', 'Daily Executive Briefing Ready')))}</strong></div>"
        f"<div class=\"metric\"><span>Top 3 opportunities</span><strong>{escape(str(len(opportunities)))}</strong></div>"
        f"<div class=\"metric\"><span>Top 3 risks</span><strong>{escape(str(len(risks)))}</strong></div>"
        f"<div class=\"metric\"><span>Top 3 revenue actions</span><strong>{escape(str(len(revenue_actions)))}</strong></div>"
        f"<div class=\"metric\"><span>Pending Gareth approvals</span><strong>{escape(str(len(approvals)))}</strong></div>"
        f"<div class=\"metric\"><span>Compliance warnings</span><strong>{escape(str(len(warnings)))}</strong></div>"
        "</div>"
        f"<p><span>Top opportunity</span><strong>{escape(str(top_opportunity.get('title', 'none')))}</strong></p>"
        f"<p><span>Top risk</span>{escape(str(top_risk.get('description', 'No risk summary available.')))}</p>"
        f"<p><span>Revenue action</span>{escape(str(top_revenue.get('recommended_action', 'No revenue action available.')))}</p>"
        f"<p><span>Dave Recommends Today</span>{escape(str(dave_today.get('recommendation', 'Review briefing before action.')))}</p>"
        "<p class=\"muted\">Read-only briefing. No outreach, automation changes, external connections, or deployment actions are enabled.</p>"
        "</div>"
    )


def render_glirn_intelligence_review_engine(glirn_data):
    engine = glirn_data.get("intelligence_review_engine", {}) or {}
    latest = engine.get("latest_generated_review") or {}
    framework = latest.get("human_review_framework") or {}
    latest_human_review = engine.get("latest_human_review") or {}

    return (
        "<div class=\"panel\">"
        "<h3>Automated Intelligence Review Engine</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Status</span><strong>{escape(str(engine.get('status', 'Automated Intelligence Review Draft Ready')))}</strong></div>"
        f"<div class=\"metric\"><span>Generated reviews</span><strong>{escape(str(len(engine.get('generated_reviews', []) or [])))}</strong></div>"
        f"<div class=\"metric\"><span>Pending review approvals</span><strong>{escape(str(len(engine.get('pending_review_approvals', []) or [])))}</strong></div>"
        f"<div class=\"metric\"><span>Approval status</span><strong>{escape(str(latest.get('approval_status', 'pending_gareth_approval')))}</strong></div>"
        f"<div class=\"metric\"><span>Compliance status</span><strong>{escape(str(latest.get('compliance_status', 'review_required')))}</strong></div>"
        f"<div class=\"metric\"><span>QA status</span><strong>{escape(str(latest_human_review.get('outcome', framework.get('qa_status', 'awaiting_human_review'))))}</strong></div>"
        f"<div class=\"metric\"><span>Delivery status</span><strong>{escape(str(latest_human_review.get('delivery_status', 'not_ready')))}</strong></div>"
        "</div>"
        f"<p><span>Latest generated review title</span><strong>{escape(str(latest.get('title', 'No generated review')))}</strong></p>"
        f"<p><span>Target client profile</span>{escape(str(latest.get('target_client_profile', 'none')))}</p>"
        f"<p><span>Practice area</span>{escape(str(latest.get('practice_area', 'none')))}</p>"
        f"<p><span>Jurisdiction</span>{escape(str(latest.get('jurisdiction', 'none')))}</p>"
        f"<p><span>Recommended action</span>{escape(str(latest.get('recommended_action', 'monitor')))}</p>"
        f"<p><span>Reviewer</span>{escape(str(latest_human_review.get('reviewer', 'not assigned')))}</p>"
        f"<p><span>Red flags</span>{escape(', '.join(latest_human_review.get('unresolved_red_flags', framework.get('active_red_flags', []))) or 'none')}</p>"
        f"<p class=\"description\"><span>Approval rationale</span>{escape(str(latest_human_review.get('approval_rationale', 'Human review not yet recorded.')))}</p>"
        "<p class=\"muted\">Every intelligence brief requires the mandatory checklist and quality assurance before manual delivery. No candidate personal data is included without active consent.</p>"
        "</div>"
    )


def render_glirn_deliverable_factory(glirn_data):
    factory = glirn_data.get("deliverable_factory", {}) or {}
    latest = factory.get("latest_deliverable") or {}

    return (
        "<div class=\"panel\">"
        "<h3>Client Deliverable Factory</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Status</span><strong>{escape(str(factory.get('status', 'Client Deliverable Drafts Ready')))}</strong></div>"
        f"<div class=\"metric\"><span>Generated deliverables</span><strong>{escape(str(len(factory.get('generated_deliverables', []) or [])))}</strong></div>"
        f"<div class=\"metric\"><span>Pending deliverable approvals</span><strong>{escape(str(len(factory.get('pending_deliverable_approvals', []) or [])))}</strong></div>"
        f"<div class=\"metric\"><span>Approval status</span><strong>{escape(str(latest.get('approval_status', 'pending_gareth_approval')))}</strong></div>"
        f"<div class=\"metric\"><span>Compliance status</span><strong>{escape(str(latest.get('compliance_status', 'review_required')))}</strong></div>"
        "</div>"
        f"<p><span>Latest deliverable</span><strong>{escape(str(latest.get('title', 'No generated deliverable')))}</strong></p>"
        f"<p><span>Deliverable type</span>{escape(str(latest.get('deliverable_type', 'none')))}</p>"
        f"<p><span>Target client profile</span>{escape(str(latest.get('target_client_profile', 'none')))}</p>"
        f"<p><span>Recommended action</span>{escape(str(latest.get('recommended_action', 'review')))}</p>"
        "<p class=\"muted\">Generated drafts require Gareth approval before client-ready status or delivery. No autonomous delivery, contracts, fee proposals, or outreach are enabled.</p>"
        "</div>"
    )


def render_glirn_approval_to_action_workflow(glirn_data):
    workflow = glirn_data.get("approval_to_action_workflow", {}) or {}
    pending = workflow.get("pending_gareth_approval", []) or []
    approved = workflow.get("approved_for_human_use", []) or []
    rejected = workflow.get("rejected_items", []) or []
    monitored = workflow.get("monitored_items", []) or []
    dave_first = workflow.get("dave_recommends_first") or {}

    return (
        "<div class=\"panel\">"
        "<h3>Approval-to-Action Workflow</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Status</span><strong>{escape(str(workflow.get('status', 'Approval-to-Action Controls Active')))}</strong></div>"
        f"<div class=\"metric\"><span>Draft status</span><strong>{escape(str(workflow.get('draft_status', 'generated_drafts_pending_review')))}</strong></div>"
        f"<div class=\"metric\"><span>Approval status</span><strong>{escape(str(workflow.get('approval_status', 'pending_gareth_approval')))}</strong></div>"
        f"<div class=\"metric\"><span>Client-ready status</span><strong>{escape(str(workflow.get('client_ready_status', 'not_client_ready_without_gareth_approval')))}</strong></div>"
        f"<div class=\"metric\"><span>Action readiness</span><strong>{escape(str(workflow.get('action_readiness_status', 'human_review_required')))}</strong></div>"
        f"<div class=\"metric\"><span>Pending Gareth approval</span><strong>{escape(str(len(pending)))}</strong></div>"
        f"<div class=\"metric\"><span>Approved for human use</span><strong>{escape(str(len(approved)))}</strong></div>"
        f"<div class=\"metric\"><span>Rejected items</span><strong>{escape(str(len(rejected)))}</strong></div>"
        f"<div class=\"metric\"><span>Monitored items</span><strong>{escape(str(len(monitored)))}</strong></div>"
        "</div>"
        f"<p><span>Dave Recommends First</span>{escape(str(dave_first.get('recommendation', 'Review generated drafts before use.')))}</p>"
        "<p class=\"muted\">No automatic delivery, outreach, fee proposals, contracts, or external connections are enabled.</p>"
        "</div>"
    )


def render_glirn_revenue_command_centre(glirn_data):
    centre = glirn_data.get("revenue_command_centre", {}) or {}
    funnel = centre.get("revenue_funnel", []) or []
    top_revenue = centre.get("top_revenue_opportunities", []) or []
    highest = centre.get("highest_fee_opportunity") or {}
    fastest = centre.get("fastest_revenue_opportunity") or {}
    dave_first = centre.get("dave_recommends_first") or {}
    funnel_summary = ", ".join(
        f"{item.get('stage')}: {item.get('item_count', 0)}"
        for item in funnel
    )
    top_titles = ", ".join(
        str(item.get("title", "Revenue opportunity"))
        for item in top_revenue[:3]
    ) or "No ranked revenue opportunities"

    return (
        "<div class=\"panel\">"
        "<h3>Revenue Command Centre</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Status</span><strong>{escape(str(centre.get('status', 'Revenue Command Centre Active')))}</strong></div>"
        f"<div class=\"metric\"><span>Total Revenue Pipeline</span><strong>GBP {escape(str(centre.get('total_revenue_pipeline', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Estimated Placement Fees</span><strong>GBP {escape(str(centre.get('estimated_placement_fee_pipeline', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Estimated Intelligence Review Revenue</span><strong>GBP {escape(str(centre.get('estimated_intelligence_review_revenue', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Approved Opportunities</span><strong>{escape(str(centre.get('approved_opportunities_count', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Approved Deliverables</span><strong>{escape(str(centre.get('approved_deliverables_count', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Revenue Readiness Score</span><strong>{escape(str(centre.get('revenue_readiness_score', 0)))}</strong></div>"
        "</div>"
        f"<p><span>Revenue Funnel</span>{escape(funnel_summary or 'No revenue funnel available.')}</p>"
        f"<p><span>Highest Fee Opportunity</span><strong>{escape(str(highest.get('title', 'none')))}</strong></p>"
        f"<p><span>Fastest Revenue Opportunity</span><strong>{escape(str(fastest.get('title', 'none')))}</strong></p>"
        f"<p><span>Top Revenue Opportunities</span>{escape(top_titles)}</p>"
        f"<p><span>Recommended Next Action</span>{escape(str(dave_first.get('recommendation', 'Review revenue pipeline before action.')))}</p>"
        "<p class=\"muted\">Read-only revenue cockpit. No outreach, client delivery, fee proposals, contracts, invoicing, external integrations, scraping, or live data fetching are enabled. Human approval remains mandatory.</p>"
        "</div>"
    )


def render_glirn_invoice_drafting_engine(glirn_data):
    engine = glirn_data.get("invoice_drafting_engine", {}) or {}
    drafts = engine.get("invoice_drafts", []) or []
    pending = engine.get("pending_invoice_approvals", []) or []
    approved = engine.get("approved_invoice_drafts", []) or []
    latest = drafts[0] if drafts else {}

    return (
        "<div class=\"panel\">"
        "<h3>Invoice Drafting Engine</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Status</span><strong>{escape(str(engine.get('status', 'Invoice Drafting Engine Active')))}</strong></div>"
        f"<div class=\"metric\"><span>Invoice drafts</span><strong>{escape(str(len(drafts)))}</strong></div>"
        f"<div class=\"metric\"><span>Pending invoice approvals</span><strong>{escape(str(len(pending)))}</strong></div>"
        f"<div class=\"metric\"><span>Approved invoice drafts</span><strong>{escape(str(len(approved)))}</strong></div>"
        f"<div class=\"metric\"><span>Invoice readiness status</span><strong>{escape(str(engine.get('invoice_readiness_status', 'drafts_pending_gareth_approval')))}</strong></div>"
        f"<div class=\"metric\"><span>Total amount due</span><strong>GBP {escape(str(latest.get('total_amount_due', 0)))}</strong></div>"
        "</div>"
        f"<p><span>Latest invoice</span><strong>{escape(str(latest.get('invoice_number', 'No invoice draft')))}</strong></p>"
        f"<p><span>Customer</span>{escape(str(latest.get('customer_name', 'none')))}</p>"
        f"<p><span>Fee type</span>{escape(str(latest.get('fee_type', 'none')))}</p>"
        f"<p><span>Payment methods</span>{escape(', '.join(engine.get('supported_payment_methods', []) or []))}</p>"
        "<p class=\"muted\">Draft-only invoice layer. No automatic sending, payment collection, payment confirmation, PayPal API, Revolut API, bank integration, or external payment integration is enabled. Gareth approval and manual handling remain mandatory.</p>"
        "</div>"
    )


def render_glirn_client_terms_drafting_engine(glirn_data):
    engine = glirn_data.get("client_terms_drafting_engine", {}) or {}
    drafts = engine.get("client_terms_drafts", []) or []
    pending = engine.get("pending_terms_approvals", []) or []
    approved = engine.get("approved_terms_drafts", []) or []
    latest = drafts[0] if drafts else {}

    return (
        "<div class=\"panel\">"
        "<h3>Client Terms Drafting Engine</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Status</span><strong>{escape(str(engine.get('status', 'Client Terms Drafting Engine Active')))}</strong></div>"
        f"<div class=\"metric\"><span>Client terms drafts</span><strong>{escape(str(len(drafts)))}</strong></div>"
        f"<div class=\"metric\"><span>Pending terms approvals</span><strong>{escape(str(len(pending)))}</strong></div>"
        f"<div class=\"metric\"><span>Approved terms drafts</span><strong>{escape(str(len(approved)))}</strong></div>"
        f"<div class=\"metric\"><span>Terms readiness status</span><strong>{escape(str(engine.get('terms_readiness_status', 'drafts_pending_gareth_approval')))}</strong></div>"
        f"<div class=\"metric\"><span>Gareth approval status</span><strong>{escape(str(latest.get('gareth_approval_status', 'required')))}</strong></div>"
        "</div>"
        f"<p><span>Latest terms draft</span><strong>{escape(str(latest.get('terms_id', 'No terms draft')))}</strong></p>"
        f"<p><span>Terms type</span>{escape(str(latest.get('terms_type', 'none')))}</p>"
        f"<p><span>Service description</span>{escape(str(latest.get('service_description', 'none')))}</p>"
        "<p class=\"muted\">Draft-only terms layer. No automatic sending, agreement, contract acceptance, e-signature integration, external integration, or solicitor-approved claim is enabled. Gareth review and manual handling remain mandatory.</p>"
        "</div>"
    )


def render_glirn_candidate_consent_management_engine(glirn_data):
    engine = glirn_data.get("candidate_consent_management_engine", {}) or {}
    pending = engine.get("pending_candidate_consents", []) or []
    active = engine.get("active_candidate_consents", []) or []
    expired = engine.get("expired_candidate_consents", []) or []
    records = engine.get("candidate_consent_records", []) or []
    alerts = engine.get("consent_expiry_alerts", []) or []
    latest = records[0] if records else {}

    return (
        "<div class=\"panel\">"
        "<h3>Candidate Consent Management Engine</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Status</span><strong>{escape(str(engine.get('status', 'Candidate Consent Management Engine Active')))}</strong></div>"
        f"<div class=\"metric\"><span>Consent readiness status</span><strong>{escape(str(engine.get('consent_readiness_status', 'pending_manual_consent')))}</strong></div>"
        f"<div class=\"metric\"><span>Candidate consent readiness</span><strong>{escape(str(engine.get('candidate_consent_readiness', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Pending candidate consents</span><strong>{escape(str(len(pending)))}</strong></div>"
        f"<div class=\"metric\"><span>Active candidate consents</span><strong>{escape(str(len(active)))}</strong></div>"
        f"<div class=\"metric\"><span>Expired candidate consents</span><strong>{escape(str(len(expired)))}</strong></div>"
        f"<div class=\"metric\"><span>Consent expiry alerts</span><strong>{escape(str(len(alerts)))}</strong></div>"
        "</div>"
        f"<p><span>Latest consent record</span><strong>{escape(str(latest.get('candidate_id', 'No consent record')))}</strong></p>"
        f"<p><span>Consent status</span>{escape(str(latest.get('consent_status', 'none')))}</p>"
        f"<p><span>Consent scope</span>{escape(str(latest.get('consent_scope', 'none')))}</p>"
        "<p class=\"muted\">Consent preparation and tracking only. No candidate contact, automated consent collection, automated consent activation, external integrations, scraping, or live data fetching are enabled. Gareth approval remains mandatory.</p>"
        "</div>"
    )


def render_glirn_manual_delivery_control_engine(glirn_data):
    engine = glirn_data.get("manual_delivery_control_engine", {}) or {}
    ready = engine.get("delivery_ready_items", []) or []
    blocked = engine.get("blocked_delivery_items", []) or []
    pending = engine.get("pending_delivery_approvals", []) or []
    checklist = engine.get("delivery_checklist", {}) or {}
    missing = []
    if blocked:
        missing = blocked[0].get("missing_checks", []) or []

    return (
        "<div class=\"panel\">"
        "<h3>Manual Delivery Control Engine</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Status</span><strong>{escape(str(engine.get('status', 'Manual Delivery Control Engine Active')))}</strong></div>"
        f"<div class=\"metric\"><span>Manual delivery status</span><strong>{escape(str(engine.get('manual_delivery_status', 'blocked_pending_manual_checks')))}</strong></div>"
        f"<div class=\"metric\"><span>Delivery ready items</span><strong>{escape(str(len(ready)))}</strong></div>"
        f"<div class=\"metric\"><span>Blocked delivery items</span><strong>{escape(str(len(blocked)))}</strong></div>"
        f"<div class=\"metric\"><span>Pending delivery approvals</span><strong>{escape(str(len(pending)))}</strong></div>"
        f"<div class=\"metric\"><span>Checklist items</span><strong>{escape(str(len(checklist)))}</strong></div>"
        "</div>"
        f"<p><span>Missing checks</span>{escape(', '.join(missing) if missing else 'No missing checks recorded.')}</p>"
        "<p class=\"muted\">Delivery preparation only. GLIRN must not send, email, upload externally, or contact candidates. Gareth manually delivers approved items.</p>"
        "</div>"
    )


def render_glirn_launch_compliance_validation_engine(glirn_data):
    engine = glirn_data.get("launch_compliance_validation_engine", {}) or {}
    ready = engine.get("compliance_ready_items", []) or []
    blocked = engine.get("compliance_blocked_items", []) or []
    checks = engine.get("compliance_validation_checks", []) or []
    first_item = checks[0] if checks else {}
    missing = first_item.get("missing_compliance_checks", []) or []

    return (
        "<div class=\"panel\">"
        "<h3>Launch Compliance Validation Engine</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Status</span><strong>{escape(str(engine.get('status', 'Launch Compliance Validation Engine Active')))}</strong></div>"
        f"<div class=\"metric\"><span>Compliance readiness score</span><strong>{escape(str(engine.get('overall_compliance_readiness_score', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Risk level</span><strong>{escape(str(engine.get('compliance_risk_level', 'blocked')))}</strong></div>"
        f"<div class=\"metric\"><span>Ready items</span><strong>{escape(str(len(ready)))}</strong></div>"
        f"<div class=\"metric\"><span>Blocked items</span><strong>{escape(str(len(blocked)))}</strong></div>"
        f"<div class=\"metric\"><span>Gareth approval status</span><strong>{escape(str(first_item.get('gareth_approval_required', True)))}</strong></div>"
        "</div>"
        f"<p><span>Missing compliance checks</span>{escape(', '.join(missing) if missing else 'No missing compliance checks recorded.')}</p>"
        f"<p><span>Recommended action</span>{escape(str(engine.get('compliance_recommendation', 'monitor')))}</p>"
        "<p class=\"muted\">Compliance readiness validation only. GLIRN does not provide legal advice, claim legal certification, declare global legal compliance, or override Gareth approval.</p>"
        "</div>"
    )


def render_glirn_first_prospect_selection_engine(glirn_data):
    engine = glirn_data.get("first_prospect_selection_engine", {}) or {}
    top = engine.get("recommended_first_prospect") or {}
    dave_first = engine.get("dave_recommends_first") or {}

    return (
        "<div class=\"panel\">"
        "<h3>First Prospect Selection Engine</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Status</span><strong>{escape(str(engine.get('status', 'First Prospect Selection Engine Active')))}</strong></div>"
        f"<div class=\"metric\"><span>Top ranked prospect</span><strong>{escape(str(top.get('category', 'No prospect ranked')))}</strong></div>"
        f"<div class=\"metric\"><span>Prospect score</span><strong>{escape(str(top.get('overall_prospect_score', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Revenue potential</span><strong>{escape(str(top.get('revenue_potential_score', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Launch readiness</span><strong>{escape(str(top.get('launch_readiness_score', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Launch priority score</span><strong>{escape(str(engine.get('launch_priority_score', 0)))}</strong></div>"
        "</div>"
        f"<p><span>Dave Recommends First</span>{escape(str(dave_first.get('recommendation', 'Review the top-ranked first prospect profile.')))}</p>"
        f"<p><span>Reason</span>{escape(str(dave_first.get('reason', top.get('reason', 'No recommendation reason recorded.'))))}</p>"
        "<p class=\"muted\">Read-only prospect selection. No prospect contact, outreach, candidate contact, client contact, external integrations, scraping, or live data fetching are enabled. Human approval remains mandatory.</p>"
        "</div>"
    )


def render_glirn_first_client_dry_run(glirn_data):
    dry_run = glirn_data.get("first_client_dry_run", {}) or {}
    artifacts = dry_run.get("dry_run_artifacts", {}) or {}
    blockers = dry_run.get("dry_run_blockers", []) or []
    warnings = dry_run.get("dry_run_warnings", []) or []
    artifact_count = sum(
        1 for item in artifacts.values()
        if isinstance(item, dict) and (item.get("generated") or item.get("executed") or item.get("artifact_id"))
    )

    return (
        "<div class=\"panel\">"
        "<h3>First Client Dry Run</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Status</span><strong>{escape(str(dry_run.get('dry_run_status', 'not_run')))}</strong></div>"
        f"<div class=\"metric\"><span>Readiness score</span><strong>{escape(str(dry_run.get('dry_run_readiness_score', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Generated artifacts</span><strong>{escape(str(artifact_count))}</strong></div>"
        f"<div class=\"metric\"><span>Blockers</span><strong>{escape(str(len(blockers)))}</strong></div>"
        f"<div class=\"metric\"><span>Warnings</span><strong>{escape(str(len(warnings)))}</strong></div>"
        f"<div class=\"metric\"><span>Approval readiness</span><strong>{escape(str(dry_run.get('approval_readiness_status', 'required')))}</strong></div>"
        "</div>"
        f"<p><span>Blockers</span>{escape(', '.join(blockers) if blockers else 'No missing dry-run artifacts.')}</p>"
        f"<p><span>Warnings</span>{escape(', '.join(warnings[:6]) if warnings else 'No dry-run warnings recorded.')}</p>"
        "<p class=\"muted\">Internal dry run only. No outreach, client contact, candidate contact, candidate introduction, delivery, invoice sending, payment collection, external integrations, scraping, or live data fetching are enabled.</p>"
        "</div>"
    )


def render_glirn_autonomous_internal_operations_orchestrator(glirn_data):
    orchestrator = glirn_data.get("autonomous_internal_operations_orchestrator", {}) or {}
    packages = orchestrator.get("final_gareth_approval_packages", []) or []
    top_package = packages[0] if packages else {}
    blockers = orchestrator.get("autonomous_blockers", []) or []
    warnings = orchestrator.get("autonomous_warnings", []) or []

    return (
        "<div class=\"panel\">"
        "<h3>Autonomous Internal Operations Orchestrator</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Autonomous cycle status</span><strong>{escape(str(orchestrator.get('autonomous_cycle_status', 'not_run')))}</strong></div>"
        f"<div class=\"metric\"><span>Top final approval package</span><strong>{escape(str(top_package.get('package_id', 'No package')))}</strong></div>"
        f"<div class=\"metric\"><span>Expected revenue</span><strong>{escape(str(top_package.get('expected_revenue', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Readiness status</span><strong>{escape(str(top_package.get('dry_run_status', 'required')))}</strong></div>"
        f"<div class=\"metric\"><span>Blockers</span><strong>{escape(str(len(blockers)))}</strong></div>"
        f"<div class=\"metric\"><span>Gareth final decision required</span><strong>{escape(str(top_package.get('gareth_final_decision_required', True)))}</strong></div>"
        "</div>"
        f"<p><span>Warnings</span>{escape(', '.join(warnings[:6]) if warnings else 'No autonomous internal warnings recorded.')}</p>"
        f"<p><span>Final recommendation</span>{escape(str(top_package.get('final_recommendation', 'monitor')))}</p>"
        "<p class=\"muted\">Internal orchestration only. GLIRN may analyse, rank, generate, prepare, validate, block unsafe items, and create final approval packages. It must not contact clients or candidates, send deliverables or invoices, collect payments, accept contracts, make external fee proposals, use external integrations, scrape, or fetch live data.</p>"
        "</div>"
    )


def render_glirn_global_internet_shop_window(glirn_data):
    engine = glirn_data.get("website_lead_intake_engine", {}) or {}
    revenue_engine = glirn_data.get("revenue_approval_engine", {}) or {}
    response_engine = glirn_data.get("client_response_draft_engine", {}) or {}
    fee_engine = glirn_data.get("fee_proposal_pack_engine", {}) or {}
    final_approval_engine = glirn_data.get("final_approval_command_centre", {}) or {}
    contact_engine = glirn_data.get("approved_client_contact_engine", {}) or {}
    email_export_engine = glirn_data.get("email_draft_export_engine", {}) or {}
    invoice_export_engine = glirn_data.get("invoice_draft_export_engine", {}) or {}
    deal_pack_engine = glirn_data.get("deal_pack_export_engine", {}) or {}
    revenue_ledger = glirn_data.get("revenue_ledger_engine", {}) or {}
    latest = engine.get("latest_lead") or {}
    recommendation = engine.get("latest_public_lead_recommendation") or {}
    latest_revenue = revenue_engine.get("latest_revenue_opportunity") or {}
    dave_recommends = revenue_engine.get("dave_recommends") or {}
    latest_response = response_engine.get("latest_client_response_draft") or {}
    latest_fee_pack = fee_engine.get("latest_fee_proposal_pack") or {}
    latest_final_approval = final_approval_engine.get("latest_final_approval_object") or {}
    latest_contact = contact_engine.get("latest_client_contact_readiness") or {}
    latest_email_export = email_export_engine.get("latest_email_draft_export") or {}
    latest_invoice_export = invoice_export_engine.get("latest_invoice_draft_export") or {}
    latest_deal_pack = deal_pack_engine.get("latest_deal_pack_export") or {}
    latest_ledger_record = revenue_ledger.get("latest_revenue_ledger_record") or {}

    return (
        "<div class=\"panel\">"
        "<h3>Global Internet Shop Window</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Status</span><strong>{escape(str(engine.get('status', 'Website Lead Intake Engine Active')))}</strong></div>"
        f"<div class=\"metric\"><span>Latest lead</span><strong>{escape(str(latest.get('organisation', 'No public lead received')))}</strong></div>"
        f"<div class=\"metric\"><span>Latest lead type</span><strong>{escape(str(latest.get('lead_type', 'none')))}</strong></div>"
        f"<div class=\"metric\"><span>Lead route</span><strong>{escape(str(latest.get('lead_route', 'manual_triage')))}</strong></div>"
        f"<div class=\"metric\"><span>Revenue potential</span><strong>{escape(str(engine.get('lead_revenue_potential', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Qualification status</span><strong>{escape(str(engine.get('lead_qualification_status', 'no_public_leads')))}</strong></div>"
        f"<div class=\"metric\"><span>Gareth approval required</span><strong>{escape(str(latest.get('gareth_final_approval_required', True)))}</strong></div>"
        "</div>"
        f"<p><span>Recommended next action</span>{escape(str(recommendation.get('recommended_action', 'monitor')))}</p>"
        "<p class=\"muted\">Public lead intake only. GLIRN may receive, classify, score, and prepare approval packages. It must not send emails, contact clients or candidates, issue invoices, collect payments, accept contracts, use integrations, scrape, or fetch live data.</p>"
        "<h3>Ready for Gareth Approval</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Latest revenue opportunity</span><strong>{escape(str(latest_revenue.get('organisation', 'No revenue package')))}</strong></div>"
        f"<div class=\"metric\"><span>Dave recommends</span><strong>{escape(str(dave_recommends.get('recommendation', 'monitor')))}</strong></div>"
        f"<div class=\"metric\"><span>Estimated fee</span><strong>{escape(str(latest_revenue.get('estimated_revenue_opportunity', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Approval status</span><strong>{escape(str(latest_revenue.get('gareth_approval_status', 'awaiting_review')))}</strong></div>"
        f"<div class=\"metric\"><span>Suggested service</span><strong>{escape(str(latest_revenue.get('suggested_glirn_service', 'No lead received')))}</strong></div>"
        f"<div class=\"metric\"><span>Confidence score</span><strong>{escape(str(latest_revenue.get('confidence_score', 0)))}</strong></div>"
        "</div>"
        "<p><span>Placeholder actions</span>Approve | Reject | Needs more info</p>"
        "<p class=\"muted\">Gareth approval only. These controls are placeholders; no automatic client contact, invoice sending, or money movement is enabled.</p>"
        "<h3>Client Response Draft Ready</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Suggested service</span><strong>{escape(str(latest_response.get('suggested_service', 'No response draft')))}</strong></div>"
        f"<div class=\"metric\"><span>Recommended next action</span><strong>{escape(str(latest_response.get('recommended_next_action', 'monitor')))}</strong></div>"
        f"<div class=\"metric\"><span>Draft status</span><strong>{escape(str(latest_response.get('draft_status', 'awaiting_gareth_approval')))}</strong></div>"
        f"<div class=\"metric\"><span>Draft ready</span><strong>{escape(str(latest_response.get('draft_ready_status', 'draft_ready')))}</strong></div>"
        f"<div class=\"metric\"><span>Gareth approval required</span><strong>{escape(str(latest_response.get('gareth_approval_required', True)))}</strong></div>"
        f"<div class=\"metric\"><span>Local draft only</span><strong>{escape(str(latest_response.get('local_draft_only', True)))}</strong></div>"
        "</div>"
        f"<p><span>Draft subject</span>{escape(str(latest_response.get('subject', 'No client response draft generated yet.')))}</p>"
        "<p class=\"muted\">No response is sent automatically. Drafts remain local until Gareth approves manual client contact.</p>"
        "<h3>Fee Proposal Pack Ready</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Suggested service</span><strong>{escape(str(latest_fee_pack.get('suggested_glirn_service', 'No fee proposal pack')))}</strong></div>"
        f"<div class=\"metric\"><span>Estimated fee</span><strong>{escape(str(latest_fee_pack.get('estimated_fee', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Fee basis</span><strong>{escape(str(latest_fee_pack.get('fee_basis', 'not_set')))}</strong></div>"
        f"<div class=\"metric\"><span>Proposal status</span><strong>{escape(str(latest_fee_pack.get('proposal_status', 'awaiting_review')))}</strong></div>"
        f"<div class=\"metric\"><span>Gareth approval required</span><strong>{escape(str(latest_fee_pack.get('gareth_approval_required', True)))}</strong></div>"
        f"<div class=\"metric\"><span>Local proposal only</span><strong>{escape(str(latest_fee_pack.get('local_proposal_only', True)))}</strong></div>"
        "</div>"
        f"<p><span>Payment/sign-off note</span>{escape(str(latest_fee_pack.get('payment_signoff_note', 'No payment request or invoice is sent automatically.')))}</p>"
        "<p class=\"muted\">Commercial pack preparation only. No invoice, payment request, money movement, client contact, or external integration is enabled.</p>"
        "<h3>Gareth Final Approval Required</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Lead route</span><strong>{escape(str(latest_final_approval.get('lead_route', 'manual_triage')))}</strong></div>"
        f"<div class=\"metric\"><span>Suggested service</span><strong>{escape(str(latest_final_approval.get('suggested_service', 'No final approval package')))}</strong></div>"
        f"<div class=\"metric\"><span>Estimated fee</span><strong>{escape(str(latest_final_approval.get('estimated_fee', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Dave recommends</span><strong>{escape(str(latest_final_approval.get('dave_recommends', 'monitor')))}</strong></div>"
        f"<div class=\"metric\"><span>Final approval status</span><strong>{escape(str(latest_final_approval.get('final_approval_status', 'awaiting_gareth_decision')))}</strong></div>"
        f"<div class=\"metric\"><span>Local state only</span><strong>{escape(str(latest_final_approval.get('local_state_only', True)))}</strong></div>"
        "</div>"
        "<p><span>Placeholder actions</span>Approve | Reject | Needs more information</p>"
        "<p class=\"muted\">No client contact, invoice, payment request, or money movement occurs without Gareth approval.</p>"
        "<h3>Approved Client Contact Ready</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Lead name</span><strong>{escape(str(latest_contact.get('lead_name', 'No lead name')))}</strong></div>"
        f"<div class=\"metric\"><span>Lead email</span><strong>{escape(str(latest_contact.get('lead_email', 'No lead email')))}</strong></div>"
        f"<div class=\"metric\"><span>Suggested service</span><strong>{escape(str(latest_contact.get('suggested_service', 'No suggested service')))}</strong></div>"
        f"<div class=\"metric\"><span>Contact status</span><strong>{escape(str(latest_contact.get('contact_status', 'blocked_pending_gareth_approval')))}</strong></div>"
        f"<div class=\"metric\"><span>Gareth approval gate</span><strong>{escape(str(latest_contact.get('gareth_approval_gate', False)))}</strong></div>"
        f"<div class=\"metric\"><span>Approval required</span><strong>{escape(str(latest_contact.get('approval_required', True)))}</strong></div>"
        "</div>"
        f"<p><span>Local-only safety note</span>{escape(str(latest_contact.get('local_only_safety_note', 'No real email, Gmail, SMTP, external client contact, or integration is enabled.')))}</p>"
        "<h3>Approved Email Draft Export Ready</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Recipient email</span><strong>{escape(str(latest_email_export.get('to_email', 'No recipient email')))}</strong></div>"
        f"<div class=\"metric\"><span>Subject</span><strong>{escape(str(latest_email_export.get('subject', 'No email draft subject')))}</strong></div>"
        f"<div class=\"metric\"><span>Suggested service</span><strong>{escape(str(latest_email_export.get('suggested_glirn_service', 'No suggested service')))}</strong></div>"
        f"<div class=\"metric\"><span>Export status</span><strong>{escape(str(latest_email_export.get('export_status', 'blocked_pending_gareth_approval')))}</strong></div>"
        f"<div class=\"metric\"><span>Local file only</span><strong>{escape(str(latest_email_export.get('local_file_only', True)))}</strong></div>"
        f"<div class=\"metric\"><span>Email sent</span><strong>{escape(str(latest_email_export.get('email_sent', False)))}</strong></div>"
        "</div>"
        f"<p><span>Local-only note</span>{escape(str(latest_email_export.get('local_only_note', 'No email has been sent. Gareth must manually review and send.')))}</p>"
        "<h3>Invoice Draft Export Ready</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Client name</span><strong>{escape(str(latest_invoice_export.get('client_name', 'No client name')))}</strong></div>"
        f"<div class=\"metric\"><span>Client email</span><strong>{escape(str(latest_invoice_export.get('client_email', 'No client email')))}</strong></div>"
        f"<div class=\"metric\"><span>Suggested service</span><strong>{escape(str(latest_invoice_export.get('suggested_glirn_service', 'No suggested service')))}</strong></div>"
        f"<div class=\"metric\"><span>Estimated fee</span><strong>{escape(str(latest_invoice_export.get('estimated_fee', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Fee basis</span><strong>{escape(str(latest_invoice_export.get('fee_basis', 'not_set')))}</strong></div>"
        f"<div class=\"metric\"><span>Invoice status</span><strong>{escape(str(latest_invoice_export.get('invoice_status', 'blocked_pending_gareth_approval')))}</strong></div>"
        "</div>"
        f"<p><span>Local-only note</span>{escape(str(latest_invoice_export.get('local_only_note', 'No invoice or payment request has been sent. Gareth must manually review and send.')))}</p>"
        "<h3>Complete Deal Pack Ready</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Client name</span><strong>{escape(str(latest_deal_pack.get('client_name', 'No client name')))}</strong></div>"
        f"<div class=\"metric\"><span>Client email</span><strong>{escape(str(latest_deal_pack.get('client_email', 'No client email')))}</strong></div>"
        f"<div class=\"metric\"><span>Suggested service</span><strong>{escape(str(latest_deal_pack.get('suggested_glirn_service', 'No suggested service')))}</strong></div>"
        f"<div class=\"metric\"><span>Estimated fee</span><strong>{escape(str(latest_deal_pack.get('estimated_fee', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Fee basis</span><strong>{escape(str(latest_deal_pack.get('fee_basis', 'not_set')))}</strong></div>"
        f"<div class=\"metric\"><span>Deal pack status</span><strong>{escape(str(latest_deal_pack.get('deal_pack_status', 'blocked_pending_gareth_approval')))}</strong></div>"
        "</div>"
        f"<p><span>Local-only note</span>{escape(str(latest_deal_pack.get('local_only_note', 'No client contact, invoice, payment request, or money movement has occurred. Gareth must manually review and act.')))}</p>"
        "<h3>GLIRN Revenue Ledger</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Estimated pipeline value</span><strong>{escape(str(revenue_ledger.get('estimated_pipeline_value', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Actual revenue recorded</span><strong>{escape(str(revenue_ledger.get('actual_revenue_recorded', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Latest revenue stage</span><strong>{escape(str(revenue_ledger.get('latest_revenue_stage', 'new_lead')))}</strong></div>"
        f"<div class=\"metric\"><span>Manual payment confirmation required</span><strong>{escape(str(revenue_ledger.get('manual_payment_confirmation_required', True)))}</strong></div>"
        f"<div class=\"metric\"><span>Latest client</span><strong>{escape(str(latest_ledger_record.get('lead_client_name', 'No ledger record')))}</strong></div>"
        f"<div class=\"metric\"><span>Local tracking only</span><strong>{escape(str(latest_ledger_record.get('local_tracking_only', True)))}</strong></div>"
        "</div>"
        "<p class=\"muted\">Revenue tracking only. No payment collection, invoice sending, external contact, external integration, or money movement is enabled.</p>"
        "</div>"
    )


def render_glirn_first_client_readiness_gate(glirn_data):
    gate = glirn_data.get("first_client_readiness_gate", {}) or {}
    ready = gate.get("first_client_ready_items", []) or []
    blocked = gate.get("blocked_first_client_items", []) or []
    monitored = gate.get("monitored_first_client_items", []) or []
    checks = gate.get("readiness_checks", []) or []
    first_item = checks[0] if checks else {}
    missing = first_item.get("missing_checks", []) or []
    dave_first = gate.get("dave_recommends_first") or {}

    return (
        "<div class=\"panel\">"
        "<h3>First Client Readiness Gate</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Status</span><strong>{escape(str(gate.get('status', 'First Client Readiness Gate Active')))}</strong></div>"
        f"<div class=\"metric\"><span>Overall readiness score</span><strong>{escape(str(gate.get('overall_first_client_readiness_score', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Ready items</span><strong>{escape(str(len(ready)))}</strong></div>"
        f"<div class=\"metric\"><span>Blocked items</span><strong>{escape(str(len(blocked)))}</strong></div>"
        f"<div class=\"metric\"><span>Monitored items</span><strong>{escape(str(len(monitored)))}</strong></div>"
        f"<div class=\"metric\"><span>Gareth approval status</span><strong>{escape(str(first_item.get('gareth_approval_status', 'required')))}</strong></div>"
        "</div>"
        f"<p><span>Missing checks</span>{escape(', '.join(missing) if missing else 'No missing checks on the top item.')}</p>"
        f"<p><span>Recommended action</span>{escape(str(gate.get('readiness_recommendation', 'monitor')))}</p>"
        f"<p><span>Dave Recommends First</span>{escape(str(dave_first.get('recommendation', 'Review first-client readiness before action.')))}</p>"
        "<p class=\"muted\">Automated readiness assessment only. No client contact, candidate contact, delivery, fee proposal, invoicing, external integration, scraping, or live data fetching is enabled. Human approval remains mandatory.</p>"
        "</div>"
    )


def render_glirn_launch_readiness_command_centre(glirn_data):
    centre = glirn_data.get("launch_readiness_command_centre", {}) or {}
    ready = centre.get("launch_ready_items", []) or []
    blocked = centre.get("launch_blocked_items", []) or []
    missing = centre.get("launch_missing_items", []) or []
    dave_first = centre.get("dave_recommends_first") or {}
    missing_summary = ", ".join(
        str(item.get("description", "missing item"))
        for item in missing[:5]
    )

    return (
        "<div class=\"panel\">"
        "<h3>Launch Readiness Command Centre</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Overall launch readiness score</span><strong>{escape(str(centre.get('launch_readiness_score', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Launch readiness grade</span><strong>{escape(str(centre.get('launch_readiness_grade', 'blocked')))}</strong></div>"
        f"<div class=\"metric\"><span>Ready items</span><strong>{escape(str(len(ready)))}</strong></div>"
        f"<div class=\"metric\"><span>Blocked items</span><strong>{escape(str(len(blocked)))}</strong></div>"
        f"<div class=\"metric\"><span>Missing items</span><strong>{escape(str(len(missing)))}</strong></div>"
        f"<div class=\"metric\"><span>Gareth approval status</span><strong>{escape(str(centre.get('gareth_approval_status', 'required')))}</strong></div>"
        "</div>"
        f"<p><span>Missing launch items</span>{escape(missing_summary or 'No missing launch items recorded.')}</p>"
        f"<p><span>Recommended next action</span>{escape(str(centre.get('launch_recommended_next_action', 'monitor')))}</p>"
        f"<p><span>Dave Recommends First</span>{escape(str(dave_first.get('recommendation', 'Review launch readiness before action.')))}</p>"
        "<p class=\"muted\">Read-only launch assessment. No autonomous launch, website publishing, LinkedIn posting, outreach, delivery, fee proposals, invoicing, external integrations, scraping, or live data fetching are enabled.</p>"
        "</div>"
    )


def render_top_action_cards(pending_opportunities):
    top_actions = pending_opportunities[:3]

    if not top_actions:
        return "<p class=\"muted\">No pending review opportunities.</p>"

    cards = []

    for index, opportunity in enumerate(top_actions, start=1):
        opportunity_id = str(opportunity.get("id", ""))
        escaped_id = escape(opportunity_id)
        reason = opportunity.get("confidence_reason") or opportunity.get("description") or "Review required."

        cards.append(
            "<article class=\"card\">"
            f"<h3>{index}. {escape(str(opportunity.get('title', 'Untitled opportunity')))}</h3>"
            f"<p><span>Confidence</span>{escape(str(opportunity.get('confidence', 0)))}</p>"
            f"<p><span>Estimated benefit</span>{escape(str(opportunity.get('estimated_benefit', opportunity.get('estimated_value', 0))))}</p>"
            f"<p><span>Risk</span>{escape(str(opportunity.get('risk_level', 'unknown')))}</p>"
            f"<p><span>Recommended</span><strong>{escape(str(opportunity.get('recommended_action', 'review')))}</strong></p>"
            f"<p class=\"description\"><span>Reason</span>{escape(str(reason))}</p>"
            f"<textarea class=\"reviewer-note\" placeholder=\"Reviewer note\" data-opportunity-id=\"{escaped_id}\"></textarea>"
            "<div class=\"action-row\">"
            f"<button class=\"opportunity-action\" type=\"button\" data-action=\"approve\" data-opportunity-id=\"{escaped_id}\">Approve</button>"
            f"<button class=\"opportunity-action reject-action\" type=\"button\" data-action=\"reject\" data-opportunity-id=\"{escaped_id}\">Reject</button>"
            "<select class=\"outcome-status hidden-control\"><option value=\"monitored\" selected>monitored</option></select>"
            "<input class=\"realized-value hidden-control\" type=\"hidden\" value=\"\">"
            "<textarea class=\"outcome-note hidden-control\">Marked for monitoring from command centre.</textarea>"
            f"<button class=\"opportunity-outcome\" type=\"button\" data-opportunity-id=\"{escaped_id}\">Monitor</button>"
            "</div>"
            "<p class=\"muted\">Capital execution remains disabled.</p>"
            "</article>"
        )

    return "".join(cards)


def render_unified_review_queue(pending_opportunities, pending_approvals):
    if not pending_opportunities and not pending_approvals:
        return "<p class=\"muted\">No pending human review items.</p>"

    cards = []

    for opportunity in pending_opportunities:
        opportunity_id = str(opportunity.get("id", ""))
        escaped_id = escape(opportunity_id)
        cards.append(
            "<article class=\"card\">"
            "<h3>Opportunity Review</h3>"
            f"<p><span>Title</span><strong>{escape(str(opportunity.get('title', 'Untitled opportunity')))}</strong></p>"
            f"<p><span>Confidence</span>{escape(str(opportunity.get('confidence', 0)))}</p>"
            f"<p><span>Estimated benefit</span>{escape(str(opportunity.get('estimated_benefit', opportunity.get('estimated_value', 0))))}</p>"
            f"<p><span>Risk</span>{escape(str(opportunity.get('risk_level', 'unknown')))}</p>"
            f"<p><span>Recommended</span>{escape(str(opportunity.get('recommended_action', 'review')))}</p>"
            f"<textarea class=\"reviewer-note\" placeholder=\"Reviewer note\" data-opportunity-id=\"{escaped_id}\"></textarea>"
            "<div class=\"action-row\">"
            f"<button class=\"opportunity-action\" type=\"button\" data-action=\"approve\" data-opportunity-id=\"{escaped_id}\">Approve</button>"
            f"<button class=\"opportunity-action reject-action\" type=\"button\" data-action=\"reject\" data-opportunity-id=\"{escaped_id}\">Reject</button>"
            "</div>"
            "</article>"
        )

    for approval in pending_approvals:
        approval_id = str(approval.get("approval_id", ""))
        escaped_id = escape(approval_id)
        route_result = approval.get("route_result", {}) or {}
        cards.append(
            "<article class=\"card\">"
            "<h3>Route Approval</h3>"
            f"<p><span>Approval ID</span><strong>{escape(approval_id)}</strong></p>"
            f"<p><span>Provider</span>{escape(str(route_result.get('provider', route_result.get('provider_name', 'unknown'))))}</p>"
            f"<p><span>Task type</span>{escape(str(route_result.get('task_type', 'unknown')))}</p>"
            f"<p><span>Estimated cost</span>{escape(str(route_result.get('estimated_cost', 'unknown')))}</p>"
            "<p><span>Capital execution</span><strong>false</strong></p>"
            "<div class=\"action-row\">"
            f"<button class=\"approval-action\" type=\"button\" data-decision=\"approved\" data-approval-id=\"{escaped_id}\">Approve</button>"
            f"<button class=\"approval-action reject-action\" type=\"button\" data-decision=\"rejected\" data-approval-id=\"{escaped_id}\">Reject</button>"
            "</div>"
            "</article>"
        )

    return "".join(cards)


def render_count_bar_chart(counts, label):
    if not counts:
        return "<p class=\"muted\">No opportunity analytics found.</p>"

    max_count = max(counts.values()) or 1
    rows = []

    for index, (name, count) in enumerate(counts.items()):
        width = int((count / max_count) * 210)
        y = 28 + (index * 34)
        rows.append(
            f"<text x=\"0\" y=\"{y}\" class=\"chart-label\">{escape(str(name))}</text>"
            f"<rect x=\"155\" y=\"{y - 16}\" width=\"{width}\" height=\"18\" rx=\"3\"></rect>"
            f"<text x=\"{165 + width}\" y=\"{y}\" class=\"chart-value\">{escape(str(count))}</text>"
        )

    height = 24 + (len(counts) * 34)
    return (
        f"<svg class=\"chart\" viewBox=\"0 0 420 {height}\" role=\"img\" aria-label=\"{escape(label)}\">"
        f"{''.join(rows)}"
        "</svg>"
    )


def render_daily_snapshot(snapshot_data):
    provider_summary = snapshot_data.get("provider_summary", {})
    route_counts = snapshot_data.get("route_counts", {})
    opportunity_summary = snapshot_data.get("opportunity_analytics", {})

    return (
        "<div class=\"analytics-grid\">"
        "<div class=\"panel\">"
        "<h3>System</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Status</span><strong>{escape(str(snapshot_data.get('system_health', {}).get('status', 'unknown')))}</strong></div>"
        f"<div class=\"metric\"><span>Active providers</span><strong>{escape(str(provider_summary.get('active_count', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Blocked providers</span><strong>{escape(str(provider_summary.get('blocked_count', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Review queue</span><strong>{escape(str(snapshot_data.get('human_review_queue_count', 0)))}</strong></div>"
        "</div>"
        "</div>"
        "<div class=\"panel\">"
        "<h3>Routes</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Total routes</span><strong>{escape(str(route_counts.get('total_route_count', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Recent routes</span><strong>{escape(str(route_counts.get('recent_route_count', 0)))}</strong></div>"
        "</div>"
        "</div>"
        "<div class=\"panel\">"
        "<h3>Opportunities</h3>"
        "<div class=\"metric-grid\">"
        f"<div class=\"metric\"><span>Total</span><strong>{escape(str(opportunity_summary.get('total_opportunities', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Avg. confidence</span><strong>{escape(str(opportunity_summary.get('average_confidence', 0)))}</strong></div>"
        f"<div class=\"metric\"><span>Realized value</span><strong>{escape(str(opportunity_summary.get('total_realized_value', 0)))}</strong></div>"
        "</div>"
        "</div>"
        "<div class=\"panel\">"
        "<h3>Recent High-Confidence Opportunities</h3>"
        f"{render_table(snapshot_data.get('recent_high_confidence_opportunities', []), [('Title', 'title'), ('Confidence', 'confidence'), ('Status', 'status')])}"
        "</div>"
        "<div class=\"panel\">"
        "<h3>Recent Research Items</h3>"
        f"{render_table(snapshot_data.get('recent_research_items', []), [('Title', 'title'), ('Category', 'category'), ('Relevance', 'relevance_score')])}"
        "</div>"
        "</div>"
    )


def render_opportunity_cards(opportunity_items):
    if not opportunity_items:
        return "<p class=\"muted\">No opportunities found. Run a scan to create review-only samples.</p>"

    cards = []

    for opportunity in opportunity_items:
        opportunity_id = str(opportunity.get("id", ""))
        escaped_id = escape(opportunity_id)
        status = str(opportunity.get("status", "pending_review"))
        actions = ""

        if status == "pending_review":
            actions = (
                f"<textarea class=\"reviewer-note\" placeholder=\"Reviewer note\" data-opportunity-id=\"{escaped_id}\"></textarea>"
                "<div class=\"action-row\">"
                f"<button class=\"opportunity-action\" type=\"button\" data-action=\"approve\" data-opportunity-id=\"{escaped_id}\">Approve</button>"
                f"<button class=\"opportunity-action reject-action\" type=\"button\" data-action=\"reject\" data-opportunity-id=\"{escaped_id}\">Reject</button>"
                "</div>"
            )

        outcome_controls = (
            "<div class=\"outcome-controls\">"
            "<select class=\"outcome-status\">"
            "<option value=\"pending_review\">pending_review</option>"
            "<option value=\"approved_human_review\">approved_human_review</option>"
            "<option value=\"rejected_human_review\">rejected_human_review</option>"
            "<option value=\"monitored\">monitored</option>"
            "<option value=\"expired\">expired</option>"
            "</select>"
            "<input class=\"realized-value\" type=\"number\" step=\"0.01\" placeholder=\"Realized value\">"
            "<textarea class=\"outcome-note\" placeholder=\"Outcome reviewer note\"></textarea>"
            f"<button class=\"opportunity-outcome\" type=\"button\" data-opportunity-id=\"{escaped_id}\">Save outcome</button>"
            "</div>"
        )

        cards.append(
            "<article class=\"card\">"
            f"<h3>{escape(str(opportunity.get('title', 'Untitled opportunity')))}</h3>"
            f"<p><span>Category</span>{escape(str(opportunity.get('category', 'unknown')))}</p>"
            f"<p><span>Confidence</span>{escape(str(opportunity.get('confidence', 0)))}</p>"
            f"<p><span>Estimated value</span>{escape(str(opportunity.get('estimated_value', 0)))}</p>"
            f"<p><span>Risk</span>{escape(str(opportunity.get('risk_level', 'unknown')))}</p>"
            f"<p><span>Status</span><strong>{escape(status)}</strong></p>"
            f"<p><span>Recommended</span><strong>{escape(str(opportunity.get('recommended_action', 'review')))}</strong></p>"
            f"<p><span>Est. cost</span>{escape(str(opportunity.get('estimated_cost', 0)))}</p>"
            f"<p><span>Est. benefit</span>{escape(str(opportunity.get('estimated_benefit', opportunity.get('estimated_value', 0))))}</p>"
            f"<p class=\"description\"><span>Confidence reason</span>{escape(str(opportunity.get('confidence_reason', 'Not evaluated yet.')))}</p>"
            f"<p class=\"description\"><span>Risk notes</span>{escape(str(opportunity.get('risk_notes', 'Not evaluated yet.')))}</p>"
            f"<p class=\"description\">{escape(str(opportunity.get('description', '')))}</p>"
            f"{actions}"
            f"{outcome_controls}"
            "</article>"
        )

    return "".join(cards)


def render_research_cards(research_items):
    if not research_items:
        return "<p class=\"muted\">No research items found. Run intake to create stub research records.</p>"

    cards = []

    for item in research_items:
        cards.append(
            "<article class=\"card\">"
            f"<h3>{escape(str(item.get('title', 'Untitled research item')))}</h3>"
            f"<p><span>Category</span>{escape(str(item.get('category', 'unknown')))}</p>"
            f"<p><span>Source</span>{escape(str(item.get('source', 'unknown')))}</p>"
            f"<p><span>Relevance</span>{escape(str(item.get('relevance_score', 0)))}</p>"
            f"<p><span>URL</span>{escape(str(item.get('url', '')))}</p>"
            f"<p class=\"description\">{escape(str(item.get('summary', '')))}</p>"
            "</article>"
        )

    return "".join(cards)


def render_research_source_cards(source_items):
    if not source_items:
        return "<p class=\"muted\">No research sources configured.</p>"

    cards = []

    for source in source_items:
        name = str(source.get("name", "unknown"))
        enabled = bool(source.get("enabled", False))
        status_class = "ok" if enabled else "blocked"

        cards.append(
            "<article class=\"card\">"
            f"<h3>{escape(name)}</h3>"
            f"<p><span>Category</span>{escape(str(source.get('category', 'unknown')))}</p>"
            f"<p><span>Status</span><strong class=\"{status_class}\">{escape(str(enabled))}</strong></p>"
            f"<p><span>Cadence</span>{escape(str(source.get('refresh_cadence', 'unknown')))}</p>"
            f"<p><span>URL</span>{escape(str(source.get('url', '')))}</p>"
            f"<p class=\"description\">{escape(str(source.get('notes', '')))}</p>"
            "<div class=\"action-row\">"
            f"<button class=\"research-source-toggle\" type=\"button\" data-source=\"{escape(name)}\">Toggle source</button>"
            "</div>"
            "</article>"
        )

    return "".join(cards)


def format_gbp(value):
    return f"GBP {float(value or 0):,.0f}"


def render_gareth_command_centre(glirn_data):
    command_centre = glirn_data.get("gareth_command_centre", {}) or {}
    opportunities = command_centre.get("revenue_opportunities", []) or []
    approvals = command_centre.get("awaiting_gareth_approval", []) or []
    summary = command_centre.get("revenue_pipeline_summary", {}) or {}
    recommendations = command_centre.get("dave_recommends", []) or []
    new_enquiries = command_centre.get("new_enquiries_awaiting_review", []) or []
    human_reviews = command_centre.get("intelligence_brief_human_reviews", []) or []
    notification_summary = command_centre.get("enquiry_notification_summary", {}) or {}
    notification_failures = command_centre.get("notification_failures_requiring_attention", []) or []
    multi_agent_summary = command_centre.get("multi_agent_review_summary", {}) or {}
    multi_agent_reviews = command_centre.get("multi_agent_reviews", []) or []
    confidence_summary = command_centre.get("confidence_assessment_summary", {}) or {}
    confidence_assessments = command_centre.get("confidence_assessments", []) or []
    global_intelligence_summary = command_centre.get("global_intelligence_summary", {}) or {}
    global_intelligence_records = command_centre.get("global_intelligence_records", []) or []
    decline_decision_summary = command_centre.get("decline_decision_summary", {}) or {}
    decline_recommendations = command_centre.get("decline_recommendations", []) or []
    decline_decisions = command_centre.get("decline_decisions", []) or []

    opportunity_rows = "".join(
        "<tr>"
        f"<td><strong>{escape(str(item.get('client_firm_name', 'Unknown firm')))}</strong></td>"
        f"<td>{escape(str(item.get('suggested_glirn_service', 'Not set')))}</td>"
        f"<td><strong>{escape(format_gbp(item.get('estimated_fee', 0)))}</strong></td>"
        f"<td>{escape(str(item.get('priority_level', 'Medium')))}</td>"
        f"<td>{escape(str(item.get('status', 'review_required')))}</td>"
        "</tr>"
        for item in opportunities
    ) or '<tr><td colspan="5" class="muted">No revenue opportunities available.</td></tr>'

    approval_cards = "".join(
        "<article class=\"executive-card approval-card\">"
        f"<h3>{escape(str(item.get('client_firm_name', 'Unknown enquiry')))}</h3>"
        f"<p><span>Recommended action</span><strong>{escape(str(item.get('recommended_action', 'monitor')))}</strong></p>"
        f"<p><span>Estimated fee</span><strong>{escape(format_gbp(item.get('estimated_fee', 0)))}</strong></p>"
        f"<p><span>Final approval status</span><strong>{escape(str(item.get('final_approval_status', 'awaiting_gareth_decision')))}</strong></p>"
        "<div class=\"action-row\">"
        f"<button class=\"gareth-approval-action\" type=\"button\" data-final-approval-id=\"{escape(str(item.get('final_approval_id', '')))}\" data-action=\"approve\">Approve</button>"
        f"<button class=\"gareth-approval-action reject-action\" type=\"button\" data-final-approval-id=\"{escape(str(item.get('final_approval_id', '')))}\" data-action=\"reject\">Reject</button>"
        f"<button class=\"gareth-approval-action secondary-action\" type=\"button\" data-final-approval-id=\"{escape(str(item.get('final_approval_id', '')))}\" data-action=\"needs_more_information\">Needs More Information</button>"
        "</div></article>"
        for item in approvals
    ) or '<div class="panel"><p class="muted">Nothing is awaiting Gareth approval.</p></div>'

    recommendation_cards = "".join(
        "<article class=\"executive-card recommendation-card\">"
        f"<div class=\"rank-badge\">{index}</div>"
        f"<h3>{escape(str(item.get('client_firm_name', 'Unknown firm')))}</h3>"
        f"<p><span>Dave recommendation</span><strong>{escape(str(item.get('dave_recommendation', 'monitor')))}</strong></p>"
        f"<p><span>Estimated fee</span><strong>{escape(format_gbp(item.get('estimated_fee', 0)))}</strong></p>"
        f"<p class=\"description\"><span>Why</span>{escape(str(item.get('recommendation_reason', 'Review required.')))}</p>"
        "</article>"
        for index, item in enumerate(recommendations, start=1)
    ) or '<div class="panel"><p class="muted">No recommendations available.</p></div>'

    enquiry_cards = "".join(
        "<article class=\"executive-card enquiry-review-card\">"
        f"<h3>{escape(str(item.get('enquiry_party', 'enquiry')).title())} enquiry</h3>"
        f"<p><span>Lead type</span><strong>{escape(str(item.get('lead_type', 'unclassified')))}</strong></p>"
        f"<p><span>Acknowledgement</span><strong>{escape(str((item.get('acknowledgement') or {}).get('acknowledgement_status', 'pending')))}</strong></p>"
        f"<p><span>Opportunity</span><strong>{escape(str(item.get('opportunity_classification', 'review_required')))}</strong></p>"
        f"<p><span>Draft response status</span><strong>{escape(str((item.get('draft_response') or {}).get('response_status', 'awaiting_gareth_approval')))}</strong></p>"
        f"<p class=\"description\"><span>Suggested response</span>{escape(str(item.get('suggested_response', 'Review required.')))}</p>"
        "<div class=\"action-row\">"
        "<button class=\"secondary-action\" type=\"button\" disabled>Approve &amp; Send</button>"
        "<button class=\"secondary-action\" type=\"button\" disabled>Edit Before Sending</button>"
        "<button class=\"reject-action\" type=\"button\" disabled>Reject</button>"
        "<button class=\"secondary-action\" type=\"button\" disabled>Request More Information</button>"
        "</div><p class=\"muted\">Review actions are local-only placeholders. Substantive sending remains disabled until Gareth approval and an explicitly configured safe transport.</p>"
        "</article>"
        for item in new_enquiries
    ) or '<div class="panel"><p class="muted">No new enquiries are awaiting review.</p></div>'

    human_review_cards = "".join(
        "<article class=\"executive-card\">"
        f"<h3>{escape(str(item.get('brief_id', 'Intelligence brief')))}</h3>"
        f"<p><span>Reviewer</span><strong>{escape(str(item.get('reviewer', 'not assigned')))}</strong></p>"
        f"<p><span>Outcome</span><strong>{escape(str(item.get('outcome', 'awaiting_human_review')))}</strong></p>"
        f"<p><span>Delivery status</span><strong>{escape(str(item.get('delivery_status', 'not_ready')))}</strong></p>"
        f"<p><span>Unresolved red flags</span>{escape(', '.join(item.get('unresolved_red_flags', [])) or 'none')}</p>"
        f"<p class=\"description\"><span>Approval rationale</span>{escape(str(item.get('approval_rationale', 'Not recorded.')))}</p>"
        "<p class=\"muted\">Manual delivery only. Gareth remains final approval authority.</p>"
        "</article>"
        for item in human_reviews
    ) or '<div class="panel"><p class="muted">No intelligence brief human review has been recorded.</p></div>'

    notification_failure_cards = "".join(
        "<article class=\"executive-card\">"
        f"<h3>{escape(str(item.get('related_enquiry_id', 'Unknown enquiry')))}</h3>"
        f"<p><span>Delivery status</span><strong class=\"blocked\">{escape(str(item.get('delivery_status', 'delivery_failed')))}</strong></p>"
        f"<p><span>Recipient</span>{escape(str(item.get('recipient_address', '')))}</p>"
        f"<p><span>Last attempt</span>{escape(str(item.get('last_attempt_at', 'not recorded')))}</p>"
        f"<p><span>Retry attempts</span>{escape(str(item.get('retry_attempts', 0)))}</p>"
        "<div class=\"action-row\">"
        f"<button class=\"enquiry-notification-resend\" type=\"button\" data-notification-id=\"{escape(str(item.get('notification_id', '')))}\">Resend notification</button>"
        "</div><p class=\"muted\">Informational notification only. Manual review remains mandatory.</p>"
        "</article>"
        for item in notification_failures
    ) or '<div class="panel"><p class="muted">No notification failures require attention.</p></div>'

    multi_agent_review_cards = "".join(
        "<article class=\"executive-card\">"
        f"<h3>{escape(str(item.get('brief_id', 'Intelligence brief')))}</h3>"
        f"<p><span>Status</span><strong>{escape(str(item.get('review_status', 'not_started')))}</strong></p>"
        f"<p><span>Overall confidence</span><strong>{escape(str((item.get('consensus_summary') or {}).get('overall_confidence_score', 'not recorded')))}</strong></p>"
        f"<p><span>Escalation</span><strong>{'required' if item.get('escalation_required') else 'clear'}</strong></p>"
        f"<p class=\"description\"><span>Next action</span>{escape('; '.join((item.get('consensus_summary') or {}).get('suggested_next_actions', [])) or 'Review required.')}</p>"
        "<p class=\"muted\">Mission 106 approval, a cleared Mission 109 review, and Gareth's final approval are required. Delivery remains manual.</p>"
        "</article>"
        for item in multi_agent_reviews
    ) or '<div class="panel"><p class="muted">No multi-agent intelligence review has been recorded.</p></div>'

    confidence_assessment_cards = "".join(
        "<article class=\"executive-card\">"
        f"<h3>{escape(str(item.get('brief_id', 'Intelligence brief')))}</h3>"
        f"<p><span>Confidence score</span><strong>{escape(str(item.get('confidence_score', 'not assessed')))}</strong></p>"
        f"<p><span>Confidence category</span><strong>{escape(str(item.get('confidence_category', 'not assessed')))}</strong></p>"
        f"<p><span>Evidence sufficiency</span><strong>{escape(str(item.get('evidence_sufficiency_rating', 'not assessed')))}</strong></p>"
        f"<p><span>Reviewer agreement</span><strong>{escape(str((item.get('reviewer_agreement') or {}).get('level', 'not assessed')))}</strong></p>"
        f"<p><span>Escalation status</span><strong>{escape(str(item.get('assessment_status', 'not_started')))}</strong></p>"
        f"<p class=\"description\"><span>Outstanding limitations</span>{escape('; '.join(item.get('outstanding_limitations', [])) or 'none')}</p>"
        "<p class=\"muted\">Confidence below 70 requires remediation and repeat Mission 109 and Mission 110 assessment. Gareth cannot override unresolved escalation.</p>"
        "</article>"
        for item in confidence_assessments
    ) or '<div class="panel"><p class="muted">No Mission 110 confidence assessment has been recorded.</p></div>'

    global_intelligence_cards = "".join(
        "<article class=\"executive-card\">"
        f"<h3>{escape(str(item.get('jurisdiction', 'Jurisdiction not assessed')))}</h3>"
        f"<p><span>Practice area</span><strong>{escape(str(item.get('practice_area', 'not assessed')))}</strong></p>"
        f"<p><span>Confidence category</span><strong>{escape(str(item.get('confidence_category', 'not assessed')))}</strong></p>"
        f"<p><span>Evidence sufficiency</span><strong>{escape(str(item.get('evidence_sufficiency_rating', 'not assessed')))}</strong></p>"
        f"<p><span>Escalation status</span><strong>{escape(str(item.get('validation_status', 'not_started')))}</strong></p>"
        f"<p class=\"description\"><span>Intelligence limitations</span>{escape('; '.join(item.get('known_limitations', [])) or 'none')}</p>"
        "<p class=\"muted\">High-level hiring intelligence only. Mission 111 escalation blocks final approval and manual delivery.</p>"
        "</article>"
        for item in global_intelligence_records
    ) or '<div class="panel"><p class="muted">No Mission 111 jurisdiction intelligence validation has been recorded.</p></div>'

    decline_recommendation_cards = "".join(
        "<article class=\"executive-card\">"
        f"<h3>{escape(str(item.get('enquiry_id', 'Enquiry')))}</h3>"
        f"<p><span>Recommendation</span><strong>{escape(str(item.get('recommendation', 'not assessed')))}</strong></p>"
        f"<p><span>Client fit</span><strong>{escape(str((item.get('factor_scores') or {}).get('client_fit', 'n/a')))}</strong></p>"
        f"<p><span>Ethical risk</span><strong>{escape(str((item.get('factor_scores') or {}).get('ethical_risk', 'n/a')))}</strong></p>"
        f"<p><span>Commercial viability</span><strong>{escape(str((item.get('factor_scores') or {}).get('commercial_viability', 'n/a')))}</strong></p>"
        f"<p><span>Reputation risk</span><strong>{escape(str((item.get('factor_scores') or {}).get('reputation_risk', 'n/a')))}</strong></p>"
        f"<p><span>Delivery confidence</span><strong>{escape(str((item.get('factor_scores') or {}).get('delivery_confidence', 'n/a')))}</strong></p>"
        f"<p class=\"description\"><span>Reasoning</span>{escape('; '.join(item.get('transparent_reasoning', [])) or 'Not recorded.')}</p>"
        f"<p><span>Referral suggested</span><strong>{escape(str((item.get('referral_recommendation') or {}).get('recommended', False)))}</strong></p>"
        f"<p><span>Approval status</span><strong>{escape(str(item.get('final_decision_status', 'awaiting_gareth_approval')))}</strong></p>"
        "<p class=\"muted\">Recommendation only. Gareth must record the final decision; no acceptance, decline, referral, or external action occurs automatically.</p>"
        "</article>"
        for item in decline_recommendations
    ) or '<div class="panel"><p class="muted">No Should We Decline recommendation has been recorded.</p></div>'

    decline_decision_cards = "".join(
        "<article class=\"executive-card\">"
        f"<h3>{escape(str(item.get('enquiry_id', 'Enquiry')))}</h3>"
        f"<p><span>System recommendation</span><strong>{escape(str(item.get('system_recommendation', 'not recorded')))}</strong></p>"
        f"<p><span>Gareth final decision</span><strong>{escape(str(item.get('final_decision', 'not recorded')))}</strong></p>"
        f"<p><span>Decision by</span><strong>{escape(str(item.get('decision_by', 'not recorded')))}</strong></p>"
        f"<p class=\"description\"><span>Rationale</span>{escape(str(item.get('decision_rationale', 'Not recorded.')))}</p>"
        "<p class=\"muted\">Decision recorded locally. Any external response or referral remains manual.</p>"
        "</article>"
        for item in decline_decisions
    ) or '<div class="panel"><p class="muted">No Gareth final decline decision has been recorded.</p></div>'

    return (
        '<section id="gareth-command-centre" data-default-view="true">'
        '<div class="executive-heading">'
        '<div><p class="eyebrow">CEO VIEW</p><h1>Gareth Command Centre</h1>'
        '<p class="executive-subtitle">Revenue, approvals, and Dave\'s highest-value recommendations.</p></div>'
        '<button id="advanced-view-toggle" class="secondary-action" type="button" aria-expanded="false" aria-controls="advanced-view">Advanced View</button>'
        '</div>'
        '<section><h2>Revenue Pipeline Summary</h2><div class="executive-metrics">'
        f'<div class="executive-metric"><span>Total enquiries</span><strong>{summary.get("total_enquiries", 0)}</strong></div>'
        f'<div class="executive-metric"><span>New enquiry notifications</span><strong>{notification_summary.get("notification_count", 0)}</strong></div>'
        f'<div class="executive-metric"><span>Notification failures</span><strong>{notification_summary.get("notification_failure_count", 0)}</strong></div>'
        f'<div class="executive-metric"><span>Multi-agent reviews</span><strong>{multi_agent_summary.get("review_count", 0)}</strong></div>'
        f'<div class="executive-metric"><span>Review escalations</span><strong>{multi_agent_summary.get("escalated_review_count", 0)}</strong></div>'
        f'<div class="executive-metric"><span>Confidence assessments</span><strong>{confidence_summary.get("assessment_count", 0)}</strong></div>'
        f'<div class="executive-metric"><span>Confidence escalations</span><strong>{confidence_summary.get("escalated_assessment_count", 0)}</strong></div>'
        f'<div class="executive-metric"><span>Jurisdiction validations</span><strong>{global_intelligence_summary.get("validation_count", 0)}</strong></div>'
        f'<div class="executive-metric"><span>Jurisdiction escalations</span><strong>{global_intelligence_summary.get("escalated_validation_count", 0)}</strong></div>'
        f'<div class="executive-metric"><span>Decline recommendations</span><strong>{decline_decision_summary.get("recommendation_count", 0)}</strong></div>'
        f'<div class="executive-metric"><span>Decline decisions awaiting Gareth</span><strong>{decline_decision_summary.get("awaiting_gareth_approval_count", 0)}</strong></div>'
        f'<div class="executive-metric"><span>Awaiting approval</span><strong>{summary.get("awaiting_approval", 0)}</strong></div>'
        f'<div class="executive-metric"><span>Approved opportunities</span><strong>{summary.get("approved_opportunities", 0)}</strong></div>'
        f'<div class="executive-metric"><span>Proposal packs ready</span><strong>{summary.get("proposal_packs_ready", 0)}</strong></div>'
        f'<div class="executive-metric"><span>Revenue received</span><strong>{escape(format_gbp(summary.get("revenue_received", 0)))}</strong></div>'
        f'<div class="executive-metric primary"><span>Pipeline value</span><strong>{escape(format_gbp(summary.get("pipeline_value", 0)))}</strong></div>'
        '</div></section>'
        '<section><h2>Awaiting Gareth Approval</h2><div class="executive-grid">'
        f'{approval_cards}</div></section>'
        '<section><h2>New Enquiries Awaiting Review</h2><div class="executive-grid">'
        f'{enquiry_cards}</div></section>'
        '<section><h2>Enquiry Notification Status</h2><div class="executive-grid">'
        f'{notification_failure_cards}</div></section>'
        '<section><h2>Intelligence Brief Human Review &amp; QA</h2><div class="executive-grid">'
        f'{human_review_cards}</div></section>'
        '<section><h2>Multi-Agent Intelligence Review</h2><div class="executive-grid">'
        f'{multi_agent_review_cards}</div></section>'
        '<section><h2>Confidence &amp; Evidence Transparency</h2><div class="executive-grid">'
        f'{confidence_assessment_cards}</div></section>'
        '<section><h2>Global Legal Intelligence</h2><div class="executive-grid">'
        f'{global_intelligence_cards}</div></section>'
        '<section><h2>Should We Decline?</h2><div class="executive-grid">'
        f'{decline_recommendation_cards}</div></section>'
        '<section><h2>Gareth Decline Decisions</h2><div class="executive-grid">'
        f'{decline_decision_cards}</div></section>'
        '<section><h2>Revenue Opportunities</h2><div class="table-wrap executive-table"><table>'
        '<thead><tr><th>Client/Firm</th><th>Suggested GLIRN service</th><th>Estimated fee</th><th>Priority</th><th>Status</th></tr></thead>'
        f'<tbody>{opportunity_rows}</tbody></table></div></section>'
        '<section><h2>Dave Recommends</h2><div class="executive-grid">'
        f'{recommendation_cards}</div></section>'
        '<p class="safety-strip">Only fixed acknowledgements and approved FAQ templates may be sent automatically. Substantive responses, commitments, candidate introductions or sharing, pricing, invoices, payments, and money movement remain blocked pending Gareth approval.</p>'
        '</section>'
    )


def render_ui_page():
    health_data = health()
    provider_data = providers()["providers"]
    dashboard_data = dashboard.get_dashboard_data()
    history_data = dashboard_data["routing_history"]
    opportunity_data = opportunities()["opportunities"]
    opportunity_analytics_data = opportunity_analytics()
    governance_analytics_data = governance_analytics()
    snapshot_data = daily_snapshot()
    approval_data = opportunity_approvals()["approvals"]
    pending_approval_data = get_pending_approvals()["approvals"]
    research_data = research_items()["research"]
    research_source_data = research_sources()["sources"]
    pending_opportunity_data = pending_review_opportunities(opportunity_data)
    scanner_data = scanner_opportunities()
    agent_safety_summary = get_agent_safety_dashboard_summary(pending_approval_data)
    glirn_data = glirn_dashboard()

    route_rows = dashboard_data["recent_route_decisions"]
    audit_rows = dashboard_data["recent_provider_audit_events"]

    route_table = render_table(route_rows, [
        ("Timestamp", "timestamp"),
        ("Task type", "task_type"),
        ("Provider", "provider"),
        ("Status", "status"),
        ("Cost", "estimated_cost"),
        ("Latency", "latency")
    ])
    audit_table = render_table(audit_rows, [
        ("Timestamp", "timestamp_utc"),
        ("Provider", "provider"),
        ("Decision", "decision"),
        ("Status", "status_code"),
        ("Reason", "reason")
    ])
    approval_table = render_table(approval_data, [
        ("Timestamp", "created_at"),
        ("Opportunity", "opportunity_id"),
        ("Action", "action"),
        ("Status", "status"),
        ("Reviewer note", "reviewer_note"),
        ("Realized value", "realized_value"),
        ("Capital execution", "capital_execution")
    ])

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Gareth Command Centre</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f5f7f9;
      --panel: #ffffff;
      --text: #17202a;
      --muted: #667085;
      --line: #d9e0e7;
      --accent: #0f766e;
      --accent-2: #2563eb;
      --blocked: #b42318;
      --ok: #067647;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Arial, Helvetica, sans-serif;
      line-height: 1.4;
    }}
    header {{
      background: #17202a;
      color: white;
      padding: 20px 28px;
    }}
    header h1 {{
      margin: 0;
      font-size: 24px;
      letter-spacing: 0;
    }}
    main {{
      max-width: 1280px;
      margin: 0 auto;
      padding: 24px;
    }}
    section {{
      margin-bottom: 24px;
    }}
    h2 {{
      font-size: 18px;
      margin: 0 0 12px;
      letter-spacing: 0;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
    }}
    .analytics-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 12px;
    }}
    .card, .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }}
    .card h3 {{
      margin: 0 0 12px;
      font-size: 16px;
    }}
    .card p, .health p {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      margin: 8px 0;
    }}
    .card .description {{
      display: block;
      color: var(--text);
      margin-top: 12px;
    }}
    span, .muted {{
      color: var(--muted);
    }}
    .ok {{
      color: var(--ok);
    }}
    .blocked {{
      color: var(--blocked);
    }}
    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
      gap: 10px;
    }}
    .metric {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: #f9fbfc;
    }}
    .metric strong {{
      display: block;
      margin-top: 4px;
      font-size: 24px;
    }}
    .chart {{
      width: 100%;
      min-height: 180px;
      display: block;
    }}
    .chart rect {{
      fill: var(--accent);
    }}
    .chart polyline {{
      fill: none;
      stroke: var(--accent-2);
      stroke-width: 3;
    }}
    .chart circle {{
      fill: var(--accent-2);
    }}
    .chart .axis {{
      stroke: var(--line);
      stroke-width: 1;
    }}
    .chart-label, .chart-value {{
      fill: var(--text);
      font-size: 13px;
    }}
    .chart-value {{
      font-weight: 700;
    }}
    form {{
      display: grid;
      gap: 10px;
    }}
    input {{
      min-height: 40px;
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      font: inherit;
    }}
    select,
    textarea {{
      min-height: 88px;
      resize: vertical;
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      font: inherit;
    }}
    select {{
      min-height: 40px;
      resize: none;
    }}
    button {{
      width: fit-content;
      min-height: 40px;
      border: 0;
      border-radius: 8px;
      padding: 0 16px;
      background: var(--accent);
      color: white;
      font: inherit;
      cursor: pointer;
    }}
    .reset-score {{
      margin-top: 10px;
      background: #344054;
    }}
    .action-row {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 12px;
    }}
    .outcome-controls {{
      display: grid;
      gap: 8px;
      margin-top: 12px;
    }}
    .reject-action {{
      background: var(--blocked);
    }}
    button:disabled {{
      opacity: 0.65;
      cursor: wait;
    }}
    pre {{
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      margin: 12px 0 0;
      padding: 12px;
      background: #eef3f7;
      border-radius: 8px;
    }}
    .table-wrap {{
      overflow-x: auto;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 760px;
    }}
    th, td {{
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      font-size: 14px;
    }}
    th {{
      color: var(--muted);
      font-weight: 600;
      background: #f9fbfc;
    }}
    details {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 12px 16px;
    }}
    summary {{
      cursor: pointer;
      font-weight: 700;
      margin-bottom: 12px;
    }}
    .hidden-control {{
      display: none;
    }}
    .executive-heading {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 24px;
      margin-bottom: 28px;
    }}
    .executive-heading h1 {{ margin: 0; font-size: 34px; }}
    .eyebrow {{ margin: 0 0 6px; color: var(--accent); font-size: 12px; font-weight: 700; letter-spacing: 0.14em; }}
    .executive-subtitle {{ margin: 8px 0 0; color: var(--muted); font-size: 17px; }}
    .executive-metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; }}
    .executive-metric {{ background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 18px; }}
    .executive-metric strong {{ display: block; margin-top: 8px; font-size: 27px; }}
    .executive-metric.primary {{ background: #0f766e; color: white; border-color: #0f766e; }}
    .executive-metric.primary span {{ color: #d5f5ef; }}
    .executive-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; }}
    .executive-card {{ position: relative; background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 20px; }}
    .executive-card h3 {{ margin: 0 0 14px; font-size: 18px; }}
    .executive-card p {{ display: flex; justify-content: space-between; gap: 14px; margin: 9px 0; }}
    .executive-card .description {{ display: block; color: var(--text); }}
    .rank-badge {{ position: absolute; top: 16px; right: 16px; width: 30px; height: 30px; border-radius: 50%; background: #e7f4f2; color: var(--accent); display: grid; place-items: center; font-weight: 700; }}
    .secondary-action {{ background: #344054; }}
    .executive-table table {{ min-width: 820px; }}
    .executive-table th, .executive-table td {{ padding: 15px 16px; font-size: 15px; }}
    .safety-strip {{ padding: 14px 18px; border-radius: 10px; background: #eef3f7; color: var(--muted); text-align: center; }}
    #advanced-view[hidden] {{ display: none; }}
    #advanced-view {{ border-top: 1px solid var(--line); margin-top: 30px; padding-top: 24px; }}
    @media (max-width: 700px) {{
      .executive-heading {{ flex-direction: column; }}
      .executive-heading h1 {{ font-size: 28px; }}
    }}
  </style>
</head>
<body>
  <main>
    {render_gareth_command_centre(glirn_data)}
    <div id="advanced-view" hidden>
    <header>
      <h1>Advanced View</h1>
    </header>
    <section>
      <h2>Profit Command Mode</h2>
      {render_profit_command_mode(pending_opportunity_data, pending_approval_data, scanner_data)}
      {render_wasted_money_hunter_card(scanner_data)}
      {render_agent_safety_gate_card(agent_safety_summary)}
      {render_glirn_operations_command_centre(glirn_data)}
      {render_glirn_daily_executive_briefing(glirn_data)}
      {render_glirn_intelligence_review_engine(glirn_data)}
      {render_glirn_deliverable_factory(glirn_data)}
      {render_glirn_approval_to_action_workflow(glirn_data)}
      {render_glirn_revenue_command_centre(glirn_data)}
      {render_glirn_invoice_drafting_engine(glirn_data)}
      {render_glirn_client_terms_drafting_engine(glirn_data)}
      {render_glirn_candidate_consent_management_engine(glirn_data)}
      {render_glirn_manual_delivery_control_engine(glirn_data)}
      {render_glirn_launch_compliance_validation_engine(glirn_data)}
      {render_glirn_first_prospect_selection_engine(glirn_data)}
      {render_glirn_first_client_dry_run(glirn_data)}
      {render_glirn_autonomous_internal_operations_orchestrator(glirn_data)}
      {render_glirn_global_internet_shop_window(glirn_data)}
      {render_glirn_first_client_readiness_gate(glirn_data)}
      {render_glirn_launch_readiness_command_centre(glirn_data)}
      {render_glirn_dashboard_card(glirn_data)}
      {render_glirn_approval_centre(glirn_data)}
      {render_glirn_compliance_core(glirn_data)}
      {render_glirn_executive_search(glirn_data)}
      {render_glirn_legal_intelligence_network(glirn_data)}
      {render_glirn_commercial_revenue_engine(glirn_data)}
      {render_glirn_client_acquisition_engine(glirn_data)}
      {render_glirn_candidate_discovery_engine(glirn_data)}
      {render_glirn_matching_engine(glirn_data)}
      {render_glirn_executive_autopilot(glirn_data)}
      {render_glirn_live_data_readiness(glirn_data)}
      {render_glirn_integration_governance(glirn_data)}
      {render_glirn_deployment_readiness(glirn_data)}
    </section>

    <section>
      {render_dave_recommends_card(pending_opportunity_data)}
    </section>

    <section>
      <h2>Command Centre</h2>
      {render_executive_summary(health_data, provider_data, pending_opportunity_data, pending_approval_data)}
    </section>

    <section>
      <h2>Today's Top Actions</h2>
      <div class="grid">{render_top_action_cards(pending_opportunity_data)}</div>
    </section>

    <section>
      <h2>Unified Human Review Queue</h2>
      <div class="grid">{render_unified_review_queue(pending_opportunity_data, pending_approval_data)}</div>
    </section>

    <section>
      <h2>Advanced Engineer View</h2>
      <details>
        <summary>Advanced Diagnostics: show detailed controls, analytics, and audit tables</summary>
    <section>
      <h2>System Health</h2>
      <div class="panel health">
        <p><span>Status</span><strong class="ok">{escape(str(health_data["status"]))}</strong></p>
        <p><span>Configured providers</span>{escape(str(health_data["configured_providers"]))}</p>
        <p><span>Enabled providers</span>{escape(str(health_data["enabled_providers"]))}</p>
        <div class="action-row">
          <button id="checkpoint-button" type="button">Create Checkpoint</button>
        </div>
      </div>
    </section>

    <section>
      <h2>Providers</h2>
      <div class="grid">{render_provider_cards(provider_data)}</div>
    </section>

    <section>
      <h2>Route Task</h2>
      <div class="panel">
        <form id="route-form">
          <textarea id="task" name="task" placeholder="Enter a task to route" required></textarea>
          <button id="route-button" type="submit">Route task</button>
        </form>
        <div id="route-result" aria-live="polite">
          <p class="muted">No task routed from this page yet.</p>
        </div>
      </div>
    </section>

    <section>
      <h2>Routing Analytics</h2>
      <div class="analytics-grid">
        <div class="panel">
          <h3>Route Counts</h3>
          {render_route_count_summary(history_data)}
        </div>
        <div class="panel">
          <h3>Provider Wins</h3>
          {render_provider_wins_chart(history_data["provider_win_counts"])}
        </div>
        <div class="panel">
          <h3>Latency Trends</h3>
          {render_latency_trend_chart(history_data["recent_routing_history"])}
        </div>
      </div>
    </section>

    <section>
      <h2>Opportunities</h2>
      <div class="panel">
        <form id="scan-form">
          <button id="scan-button" type="submit">Scan opportunities</button>
        </form>
        <p class="muted">Review-only AI infrastructure opportunities. Human approval is required before any action.</p>
      </div>
      <div class="grid">{render_opportunity_cards(opportunity_data)}</div>
    </section>

    <section>
      <h2>Opportunity Analytics</h2>
      <div class="analytics-grid">
        <div class="panel">
          <h3>Performance Totals</h3>
          {render_opportunity_metric_summary(opportunity_analytics_data)}
        </div>
        <div class="panel">
          <h3>Status Counts</h3>
          {render_count_bar_chart(opportunity_analytics_data["count_by_status"], "Opportunity status counts")}
        </div>
        <div class="panel">
          <h3>Recommended Actions</h3>
          {render_count_bar_chart(opportunity_analytics_data["count_by_recommended_action"], "Opportunity recommended action counts")}
        </div>
        <div class="panel">
          <h3>Review Outcomes</h3>
          {render_count_bar_chart(opportunity_analytics_data["approval_counts"], "Opportunity approval outcome counts")}
        </div>
      </div>
    </section>

    <section>
      <h2>Governance Analytics</h2>
      <div class="panel">
        {render_governance_metric_summary(governance_analytics_data)}
      </div>
    </section>

    <section>
      <h2>Daily Intelligence Snapshot</h2>
      {render_daily_snapshot(snapshot_data)}
    </section>
    <section>
      <h2>Pending Approval Queue</h2>
      <p class="muted">Human approval is required before any governed action can proceed. Capital execution remains disabled.</p>
      <div class="grid">{render_approval_cards(pending_approval_data)}</div>
    </section>
    <section>
      <h2>Opportunity Approval History</h2>
      {approval_table}
    </section>

    <section>
      <h2>Research Intake</h2>
      <div class="panel">
        <form id="research-intake-form">
          <button id="research-intake-button" type="submit">Run research intake</button>
        </form>
        <form id="research-convert-form">
          <button id="research-convert-button" type="submit">Convert Research to Opportunities</button>
        </form>
        <p class="muted">Stub research intake only. No internet scraping, crypto workflow, or capital execution is enabled.</p>
      </div>
      <div class="panel">
        <h3>Manual Research Import</h3>
        <form id="research-import-form">
          <input id="research-import-title" name="title" placeholder="Title" required>
          <input id="research-import-url" name="url" placeholder="URL stored only, not fetched" required>
          <input id="research-import-category" name="category" placeholder="Category" required>
          <input id="research-import-relevance" name="relevance_score" type="number" min="0" max="1" step="0.01" placeholder="Relevance score 0.0 to 1.0" required>
          <textarea id="research-import-summary" name="summary" placeholder="Summary" required></textarea>
          <button id="research-import-button" type="submit">Import research</button>
        </form>
        <p class="muted">Manual imports store the URL as data only and do not fetch or scrape.</p>
      </div>
      <div class="grid">{render_research_cards(research_data)}</div>
    </section>

    <section>
      <h2>Research Sources</h2>
      <div class="panel">
        <p class="muted">Configured external source placeholders only. Toggling changes local config and does not fetch or scrape the internet.</p>
      </div>
      <div class="grid">{render_research_source_cards(research_source_data)}</div>
    </section>

    <section>
      <h2>Recent Route Decisions</h2>
      {route_table}
    </section>

    <section>
      <h2>Recent Provider Audit Events</h2>
      {audit_table}
    </section>
      </details>
    </section>
    </div>
  </main>
  <script>
    const params = new URLSearchParams(window.location.search);
    const uiKey = params.get('key');
    const form = document.getElementById('route-form');
    const taskInput = document.getElementById('task');
    const button = document.getElementById('route-button');
    const result = document.getElementById('route-result');
    const checkpointButton = document.getElementById('checkpoint-button');
    const resetButtons = document.querySelectorAll('.reset-score');
    const scanForm = document.getElementById('scan-form');
    const scanButton = document.getElementById('scan-button');
    const opportunityButtons = document.querySelectorAll('.opportunity-action');
    const approvalActionButtons = document.querySelectorAll('.approval-action');
    const opportunityOutcomeButtons = document.querySelectorAll('.opportunity-outcome');
    const researchIntakeForm = document.getElementById('research-intake-form');
    const researchIntakeButton = document.getElementById('research-intake-button');
    const researchConvertForm = document.getElementById('research-convert-form');
    const researchConvertButton = document.getElementById('research-convert-button');
    const researchImportForm = document.getElementById('research-import-form');
    const researchImportButton = document.getElementById('research-import-button');
    const researchImportTitle = document.getElementById('research-import-title');
    const researchImportUrl = document.getElementById('research-import-url');
    const researchImportCategory = document.getElementById('research-import-category');
    const researchImportRelevance = document.getElementById('research-import-relevance');
    const researchImportSummary = document.getElementById('research-import-summary');
    const researchSourceButtons = document.querySelectorAll('.research-source-toggle');
    const advancedViewToggle = document.getElementById('advanced-view-toggle');
    const advancedView = document.getElementById('advanced-view');
    const garethApprovalButtons = document.querySelectorAll('.gareth-approval-action');
    const enquiryNotificationResendButtons = document.querySelectorAll('.enquiry-notification-resend');

    advancedViewToggle.addEventListener('click', () => {{
      const willOpen = advancedView.hidden;
      advancedView.hidden = !willOpen;
      advancedViewToggle.setAttribute('aria-expanded', String(willOpen));
      advancedViewToggle.textContent = willOpen ? 'Hide Advanced View' : 'Advanced View';
    }});

    garethApprovalButtons.forEach((approvalButton) => {{
      approvalButton.addEventListener('click', async () => {{
        const finalApprovalId = approvalButton.dataset.finalApprovalId;
        const action = approvalButton.dataset.action;
        approvalButton.disabled = true;

        try {{
          const response = await fetch('/glirn/final-approval/actions', {{
            method: 'POST',
            headers: {{
              'Content-Type': 'application/json',
              ...(uiKey ? {{ 'X-API-Key': uiKey }} : {{}})
            }},
            body: JSON.stringify({{
              final_approval_id: finalApprovalId,
              action_type: action,
              reason: `Gareth Command Centre decision: ${{action}}`
            }})
          }});
          const data = await response.json();
          if (!response.ok) {{
            throw new Error(data.detail || 'Final approval action failed');
          }}
          window.location.reload();
        }} catch (error) {{
          alert(error.message);
          approvalButton.disabled = false;
        }}
      }});
    }});

    enquiryNotificationResendButtons.forEach((resendButton) => {{
      resendButton.addEventListener('click', async () => {{
        resendButton.disabled = true;
        try {{
          const response = await fetch(`/glirn/enquiry-notifications/${{resendButton.dataset.notificationId}}/resend`, {{
            method: 'POST',
            headers: {{
              'Content-Type': 'application/json',
              ...(uiKey ? {{ 'X-API-Key': uiKey }} : {{}})
            }},
            body: JSON.stringify({{ reason: 'Manual resend requested from Gareth Command Centre.' }})
          }});
          const data = await response.json();
          if (!response.ok) {{
            throw new Error(data.detail || 'Notification resend failed');
          }}
          window.location.reload();
        }} catch (error) {{
          alert(error.message);
          resendButton.disabled = false;
        }}
      }});
    }});

    form.addEventListener('submit', async (event) => {{
      event.preventDefault();
      button.disabled = true;
      result.innerHTML = '<p class="muted">Routing task...</p>';

      try {{
        const response = await fetch('/route', {{
          method: 'POST',
          headers: {{
            'Content-Type': 'application/json',
            ...(uiKey ? {{ 'X-API-Key': uiKey }} : {{}})
          }},
          body: JSON.stringify({{ task: taskInput.value }})
        }});
        const data = await response.json();

        if (!response.ok) {{
          throw new Error(data.detail || 'Route request failed');
        }}

        result.innerHTML = `
          <p><span>Selected provider</span><strong>${{escapeHtml(data.provider)}}</strong></p>
          <p><span>Status</span>${{escapeHtml(data.status)}}</p>
          <p><span>Estimated cost</span>${{escapeHtml(String(data.estimated_cost))}}</p>
          <pre>${{escapeHtml(data.response_preview || data.response_text || '')}}</pre>
        `;
      }} catch (error) {{
        result.innerHTML = `<p class="blocked">${{escapeHtml(error.message)}}</p>`;
      }} finally {{
        button.disabled = false;
      }}
    }});

    checkpointButton.addEventListener('click', async () => {{
      checkpointButton.disabled = true;

      try {{
        const response = await fetch('/system/checkpoint', {{
          method: 'POST',
          headers: {{
            ...(uiKey ? {{ 'X-API-Key': uiKey }} : {{}})
          }}
        }});
        const data = await response.json();

        if (!response.ok) {{
          throw new Error(data.detail || 'Checkpoint request failed');
        }}

        alert(`Checkpoint created: ${{data.backup_path}}`);
      }} catch (error) {{
        alert(error.message);
      }} finally {{
        checkpointButton.disabled = false;
      }}
    }});

    resetButtons.forEach((resetButton) => {{
      resetButton.addEventListener('click', async () => {{
        const providerName = resetButton.dataset.provider;
        resetButton.disabled = true;

        try {{
          const response = await fetch(`/providers/${{encodeURIComponent(providerName)}}/reset-score`, {{
            method: 'POST',
            headers: {{
              ...(uiKey ? {{ 'X-API-Key': uiKey }} : {{}})
            }}
          }});
          const data = await response.json();

          if (!response.ok) {{
            throw new Error(data.detail || 'Reset request failed');
          }}

          window.location.reload();
        }} catch (error) {{
          alert(error.message);
          resetButton.disabled = false;
        }}
      }});
    }});

    scanForm.addEventListener('submit', async (event) => {{
      event.preventDefault();
      scanButton.disabled = true;

      try {{
        const response = await fetch('/opportunities/scan', {{
          method: 'POST',
          headers: {{
            ...(uiKey ? {{ 'X-API-Key': uiKey }} : {{}})
          }}
        }});
        const data = await response.json();

        if (!response.ok) {{
          throw new Error(data.detail || 'Opportunity scan failed');
        }}

        window.location.reload();
      }} catch (error) {{
        alert(error.message);
        scanButton.disabled = false;
      }}
    }});

    opportunityButtons.forEach((actionButton) => {{
      actionButton.addEventListener('click', async () => {{
        const opportunityId = actionButton.dataset.opportunityId;
        const action = actionButton.dataset.action;
        const card = actionButton.closest('.card');
        const reviewerNote = card.querySelector('.reviewer-note');
        actionButton.disabled = true;

        try {{
          const response = await fetch(`/opportunities/${{encodeURIComponent(opportunityId)}}/${{action}}`, {{
            method: 'POST',
            headers: {{
              'Content-Type': 'application/json',
              ...(uiKey ? {{ 'X-API-Key': uiKey }} : {{}})
            }},
            body: JSON.stringify({{
              reviewer_note: reviewerNote ? reviewerNote.value : ''
            }})
          }});
          const data = await response.json();

          if (!response.ok) {{
            throw new Error(data.detail || 'Opportunity approval failed');
          }}

          window.location.reload();
        }} catch (error) {{
          alert(error.message);
          actionButton.disabled = false;
        }}
      }});
    }});

    opportunityOutcomeButtons.forEach((outcomeButton) => {{
      outcomeButton.addEventListener('click', async () => {{
        const opportunityId = outcomeButton.dataset.opportunityId;
        const card = outcomeButton.closest('.card');
        const status = card.querySelector('.outcome-status').value;
        const note = card.querySelector('.outcome-note').value;
        const realizedValueInput = card.querySelector('.realized-value').value;
        outcomeButton.disabled = true;

        try {{
          const response = await fetch(`/opportunities/${{encodeURIComponent(opportunityId)}}/outcome`, {{
            method: 'POST',
            headers: {{
              'Content-Type': 'application/json',
              ...(uiKey ? {{ 'X-API-Key': uiKey }} : {{}})
            }},
            body: JSON.stringify({{
              outcome_status: status,
              reviewer_note: note,
              realized_value: realizedValueInput === '' ? null : Number(realizedValueInput)
            }})
          }});
          const data = await response.json();

          if (!response.ok) {{
            throw new Error(data.detail || 'Opportunity outcome update failed');
          }}

          window.location.reload();
        }} catch (error) {{
          alert(error.message);
          outcomeButton.disabled = false;
        }}
      }});
    }});
    
    approvalActionButtons.forEach((approvalButton) => {{
      approvalButton.addEventListener('click', async () => {{
        const approvalId = approvalButton.dataset.approvalId;
        const decision = approvalButton.dataset.decision;

        approvalButton.disabled = true;

        try {{
          const response = await fetch(
            `/approvals/${{encodeURIComponent(approvalId)}}/${{decision}}`,
            {{
              method: 'POST',
              headers: {{
                ...(uiKey ? {{ 'X-API-Key': uiKey }} : {{}})
              }}
            }}
          );

          const data = await response.json();

          if (!response.ok) {{
            throw new Error(data.detail || 'Approval decision failed');
          }}

          window.location.reload();
        }} catch (error) {{
          alert(error.message);
          approvalButton.disabled = false;
        }}
      }});
    }});

    researchIntakeForm.addEventListener('submit', async (event) => {{
      event.preventDefault();
      researchIntakeButton.disabled = true;

      try {{
        const response = await fetch('/research/intake', {{
          method: 'POST',
          headers: {{
            ...(uiKey ? {{ 'X-API-Key': uiKey }} : {{}})
          }}
        }});
        const data = await response.json();

        if (!response.ok) {{
          throw new Error(data.detail || 'Research intake failed');
        }}

        window.location.reload();
      }} catch (error) {{
        alert(error.message);
        researchIntakeButton.disabled = false;
      }}
    }});

    researchConvertForm.addEventListener('submit', async (event) => {{
      event.preventDefault();
      researchConvertButton.disabled = true;

      try {{
        const response = await fetch('/research/convert', {{
          method: 'POST',
          headers: {{
            ...(uiKey ? {{ 'X-API-Key': uiKey }} : {{}})
          }}
        }});
        const data = await response.json();

        if (!response.ok) {{
          throw new Error(data.detail || 'Research conversion failed');
        }}

        window.location.reload();
      }} catch (error) {{
        alert(error.message);
        researchConvertButton.disabled = false;
      }}
    }});

    researchImportForm.addEventListener('submit', async (event) => {{
      event.preventDefault();
      researchImportButton.disabled = true;

      try {{
        const response = await fetch('/research/import', {{
          method: 'POST',
          headers: {{
            'Content-Type': 'application/json',
            ...(uiKey ? {{ 'X-API-Key': uiKey }} : {{}})
          }},
          body: JSON.stringify({{
            title: researchImportTitle.value,
            url: researchImportUrl.value,
            summary: researchImportSummary.value,
            category: researchImportCategory.value,
            relevance_score: Number(researchImportRelevance.value)
          }})
        }});
        const data = await response.json();

        if (!response.ok) {{
          throw new Error(data.detail || 'Research import failed');
        }}

        window.location.reload();
      }} catch (error) {{
        alert(error.message);
        researchImportButton.disabled = false;
      }}
    }});

    researchSourceButtons.forEach((sourceButton) => {{
      sourceButton.addEventListener('click', async () => {{
        const sourceName = sourceButton.dataset.source;
        sourceButton.disabled = true;

        try {{
          const response = await fetch(`/research/sources/${{encodeURIComponent(sourceName)}}/toggle`, {{
            method: 'POST',
            headers: {{
              ...(uiKey ? {{ 'X-API-Key': uiKey }} : {{}})
            }}
          }});
          const data = await response.json();

          if (!response.ok) {{
            throw new Error(data.detail || 'Research source toggle failed');
          }}

          window.location.reload();
        }} catch (error) {{
          alert(error.message);
          sourceButton.disabled = false;
        }}
      }});
    }});

    function escapeHtml(value) {{
      return value
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
    }}
  </script>
</body>
</html>"""


@app.get("/health")
def health():
    configured_providers = load_provider_config()

    return {
        "status": "healthy",
        "service": "ArbitrageEngineV1",
        "configured_providers": len(configured_providers),
        "enabled_providers": len([
            provider for provider in configured_providers
            if provider.get("enabled", False)
        ]),
        **persistence_status(),
    }


@app.get("/providers")
def providers(x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)
    configured_providers = load_provider_config()
    scores = dashboard.load_json(dashboard.SCORES_FILE)
    provider_data = []

    for provider in configured_providers:
        name = provider.get("name")
        guard = provider_guard_status(name)

        provider_data.append({
            "name": name,
            "provider_type": provider.get("provider_type"),
            "enabled": provider.get("enabled", False),
            "guard_allowed": guard["allowed"],
            "guard_status": guard["status"],
            "score": scores.get(name)
        })

    return {
        "providers": provider_data
    }


@app.post("/providers/{provider_name}/reset-score")
def reset_score(provider_name: str, x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)
    score = reset_provider_score(provider_name)

    return {
        "provider": provider_name,
        "score": score
    }


@app.get("/dashboard")
def dashboard_data(x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)
    return dashboard.get_dashboard_data()


@app.get("/analytics/history")
def analytics_history(x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)
    return dashboard.get_routing_history_data(limit=20)


@app.get("/analytics/governance")
def governance_analytics(x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)
    return get_governance_analytics()


@app.get("/snapshot/daily")
def daily_snapshot(x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)
    system_health = health()
    provider_items = providers(x_api_key)["providers"]
    route_history = dashboard.get_routing_history_data(limit=20)
    opportunity_summary = get_opportunity_analytics()
    recent_opportunities = [
        opportunity.to_dict()
        for opportunity in list_opportunities(limit=20)
    ]
    recent_research = [
        item.to_dict()
        for item in list_research_items(limit=10)
    ]
    active_providers = [
        provider.get("name")
        for provider in provider_items
        if provider.get("guard_allowed")
    ]
    blocked_providers = [
        provider.get("name")
        for provider in provider_items
        if not provider.get("guard_allowed")
    ]
    high_confidence_opportunities = [
        opportunity
        for opportunity in recent_opportunities
        if float(opportunity.get("confidence", 0)) >= 0.75
    ][-5:]
    human_review_queue_count = len([
        opportunity
        for opportunity in recent_opportunities
        if opportunity.get("status") == "pending_review"
    ])

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "system_health": system_health,
        "provider_summary": {
            "active_count": len(active_providers),
            "blocked_count": len(blocked_providers),
            "active_providers": active_providers,
            "blocked_providers": blocked_providers
        },
        "route_counts": {
            "total_route_count": route_history.get("total_route_count", 0),
            "recent_route_count": len(route_history.get("recent_routing_history", [])),
            "provider_win_counts": route_history.get("provider_win_counts", {})
        },
        "opportunity_analytics": opportunity_summary,
        "recent_high_confidence_opportunities": high_confidence_opportunities,
        "recent_research_items": recent_research,
        "human_review_queue_count": human_review_queue_count,
        "capital_execution": False
    }


@app.post("/system/checkpoint")
def system_checkpoint(x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)
    return create_system_checkpoint()


@app.get("/opportunities")
def opportunities(x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)
    return {
        "opportunities": [
            opportunity.to_dict()
            for opportunity in list_opportunities(limit=20)
        ]
    }


@app.post("/opportunities/scan")
def scan_for_opportunities(x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)
    scanned = scan_opportunities()

    return {
        "status": "pending_human_review",
        "approval_required": True,
        "execution_enabled": False,
        "opportunities": [
            opportunity.to_dict()
            for opportunity in scanned
        ]
    }


@app.get("/opportunities/analytics")
def opportunity_analytics(x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)
    return get_opportunity_analytics()


@app.get("/scanner/opportunities")
def scanner_opportunities(x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)
    return get_scanner_results()


@app.get("/glirn/dashboard")
def glirn_dashboard(x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)
    glirn_data = get_glirn_dashboard_data(
        pending_approvals=list_pending_approvals(),
        public_leads=PUBLIC_LEADS,
    )
    final_centre = dict(glirn_data.get("final_approval_command_centre", {}) or {})
    final_objects = []
    for item in final_centre.get("final_approval_objects", []) or []:
        copied = dict(item)
        stored_status = FINAL_APPROVAL_LOCAL_STATUS.get(copied.get("final_approval_id"))
        if stored_status:
            copied["final_approval_status"] = stored_status
        final_objects.append(copied)
    final_centre["final_approval_objects"] = final_objects
    final_centre["gareth_final_approval_required"] = [
        item for item in final_objects
        if item.get("final_approval_status") == "awaiting_gareth_decision"
    ]
    glirn_data["final_approval_command_centre"] = final_centre
    glirn_data["final_approval_objects"] = final_objects
    glirn_data["gareth_final_approval_required"] = final_centre["gareth_final_approval_required"]

    email_export_engine = export_engine_with_persisted_records(
        glirn_data.get("email_draft_export_engine", {}) or {}, "email_draft"
    )
    invoice_export_engine = export_engine_with_persisted_records(
        glirn_data.get("invoice_draft_export_engine", {}) or {}, "invoice_draft"
    )
    deal_pack_engine = export_engine_with_persisted_records(
        glirn_data.get("deal_pack_export_engine", {}) or {}, "deal_pack"
    )
    glirn_data["email_draft_export_engine"] = email_export_engine
    glirn_data["invoice_draft_export_engine"] = invoice_export_engine
    glirn_data["deal_pack_export_engine"] = deal_pack_engine

    human_reviews = list(PERSISTED_HUMAN_REVIEWS)
    intelligence_engine = dict(glirn_data.get("intelligence_review_engine", {}) or {})
    intelligence_engine["human_review_records"] = human_reviews
    intelligence_engine["latest_human_review"] = human_reviews[-1] if human_reviews else None
    intelligence_engine["human_review_checklist"] = HUMAN_REVIEW_CHECKLIST
    intelligence_engine["red_flag_rules"] = RED_FLAG_RULES
    intelligence_engine["decline_criteria"] = DECLINE_CRITERIA
    multi_agent_reviews = list(PERSISTED_MULTI_AGENT_REVIEWS)
    multi_agent_summary = build_multi_agent_review_summary(multi_agent_reviews)
    intelligence_engine["multi_agent_review_records"] = multi_agent_reviews
    intelligence_engine["latest_multi_agent_review"] = multi_agent_reviews[-1] if multi_agent_reviews else None
    intelligence_engine["multi_agent_review_summary"] = multi_agent_summary
    confidence_assessments = list(PERSISTED_CONFIDENCE_ASSESSMENTS)
    confidence_summary = build_confidence_assessment_summary(confidence_assessments)
    intelligence_engine["confidence_assessment_records"] = confidence_assessments
    intelligence_engine["latest_confidence_assessment"] = confidence_assessments[-1] if confidence_assessments else None
    intelligence_engine["confidence_assessment_summary"] = confidence_summary
    global_intelligence_records = list(PERSISTED_GLOBAL_INTELLIGENCE)
    global_intelligence_summary = build_global_intelligence_summary(global_intelligence_records)
    intelligence_engine["global_intelligence_records"] = global_intelligence_records
    intelligence_engine["latest_global_intelligence"] = global_intelligence_records[-1] if global_intelligence_records else None
    intelligence_engine["global_intelligence_summary"] = global_intelligence_summary
    glirn_data["intelligence_review_engine"] = intelligence_engine
    glirn_data["human_review_records"] = human_reviews
    glirn_data["multi_agent_review_records"] = multi_agent_reviews
    glirn_data["multi_agent_review_summary"] = multi_agent_summary
    glirn_data["confidence_assessment_records"] = confidence_assessments
    glirn_data["confidence_assessment_summary"] = confidence_summary
    glirn_data["global_intelligence_records"] = global_intelligence_records
    glirn_data["global_intelligence_summary"] = global_intelligence_summary
    decline_recommendations = list(PERSISTED_DECLINE_RECOMMENDATIONS)
    decline_decisions = list(PERSISTED_DECLINE_DECISIONS)
    decline_decision_summary = build_decline_decision_summary(
        decline_recommendations,
        decline_decisions,
    )
    glirn_data["decline_recommendations"] = decline_recommendations
    glirn_data["decline_decisions"] = decline_decisions
    glirn_data["decline_decision_summary"] = decline_decision_summary
    learning_summary = {
        "outcome_count": len(PERSISTED_LEARNING_OUTCOMES),
        "insight_count": len(PERSISTED_LEARNING_INSIGHTS),
        "approved_insight_count": len(PERSISTED_LEARNING_APPROVALS),
        "awaiting_gareth_approval_count": max(
            0, len(PERSISTED_LEARNING_INSIGHTS) - len(PERSISTED_LEARNING_APPROVALS)
        ),
        "recommendation_only": True,
        "gareth_approval_mandatory": True,
    }
    external_learning_summary = {
        "evidence_count": len(PERSISTED_EXTERNAL_EVIDENCE),
        "intelligence_count": len(PERSISTED_EXTERNAL_INTELLIGENCE),
        "approved_knowledge_update_count": len(PERSISTED_KNOWLEDGE_UPDATES),
        "awaiting_gareth_approval_count": max(
            0, len(PERSISTED_EXTERNAL_INTELLIGENCE) - len(PERSISTED_KNOWLEDGE_UPDATES)
        ),
        "legal_advice_provided": False,
        "automatic_regulatory_updates_enabled": False,
    }
    decided_opportunity_ids = {
        item.get("opportunity_intelligence_id") for item in PERSISTED_OPPORTUNITY_DECISIONS
    }
    opportunity_intelligence_summary = {
        "signal_count": len(PERSISTED_OPPORTUNITY_SIGNALS),
        "recommendation_count": len(PERSISTED_OPPORTUNITY_INTELLIGENCE),
        "decision_count": len(PERSISTED_OPPORTUNITY_DECISIONS),
        "awaiting_gareth_approval_count": sum(
            1 for item in PERSISTED_OPPORTUNITY_INTELLIGENCE
            if item.get("opportunity_intelligence_id") not in decided_opportunity_ids
        ),
        "gareth_approval_required": True,
        "recommendation_only": True,
        "autonomous_prospecting_enabled": False,
    }
    glirn_data["internal_learning_summary"] = learning_summary
    glirn_data["external_learning_summary"] = external_learning_summary
    glirn_data["opportunity_intelligence_summary"] = opportunity_intelligence_summary
    glirn_data["opportunity_intelligence_records"] = list(PERSISTED_OPPORTUNITY_INTELLIGENCE)

    revenue_ledger = build_revenue_ledger_engine(
        final_centre,
        email_export_engine,
        invoice_export_engine,
        deal_pack_engine,
        stage_overrides=REVENUE_LEDGER_LOCAL_STAGE,
    )
    for record in revenue_ledger.get("revenue_ledger_records", []) or []:
        upsert_record("revenue_ledger_record", record.get("ledger_record_id"), record)
    glirn_data["revenue_ledger_engine"] = revenue_ledger
    glirn_data["gareth_command_centre"] = build_gareth_command_centre(
        glirn_data.get("opportunities", []) or [],
        glirn_data.get("website_lead_intake_engine", {}) or {},
        glirn_data.get("revenue_approval_engine", {}) or {},
        glirn_data.get("fee_proposal_pack_engine", {}) or {},
        final_centre,
        revenue_ledger,
    )
    glirn_data["gareth_command_centre"]["new_enquiries_awaiting_review"] = list(PERSISTED_RESPONSE_PACKAGES)
    glirn_data["gareth_command_centre"]["intelligence_brief_human_reviews"] = human_reviews
    glirn_data["gareth_command_centre"]["multi_agent_review_summary"] = multi_agent_summary
    glirn_data["gareth_command_centre"]["multi_agent_reviews"] = multi_agent_reviews
    glirn_data["gareth_command_centre"]["escalated_multi_agent_reviews"] = multi_agent_summary["escalated_reviews"]
    glirn_data["gareth_command_centre"]["confidence_assessment_summary"] = confidence_summary
    glirn_data["gareth_command_centre"]["confidence_assessments"] = confidence_assessments
    glirn_data["gareth_command_centre"]["escalated_confidence_assessments"] = confidence_summary["escalated_assessments"]
    glirn_data["gareth_command_centre"]["global_intelligence_summary"] = global_intelligence_summary
    glirn_data["gareth_command_centre"]["global_intelligence_records"] = global_intelligence_records
    glirn_data["gareth_command_centre"]["escalated_global_intelligence"] = global_intelligence_summary["escalated_validations"]
    glirn_data["gareth_command_centre"]["decline_decision_summary"] = decline_decision_summary
    glirn_data["gareth_command_centre"]["decline_recommendations"] = decline_recommendations
    glirn_data["gareth_command_centre"]["decline_decisions"] = decline_decisions
    glirn_data["gareth_command_centre"]["internal_learning_summary"] = learning_summary
    glirn_data["gareth_command_centre"]["learning_insights"] = list(PERSISTED_LEARNING_INSIGHTS)
    glirn_data["gareth_command_centre"]["external_learning_summary"] = external_learning_summary
    glirn_data["gareth_command_centre"]["external_intelligence_learning"] = list(PERSISTED_EXTERNAL_INTELLIGENCE)
    glirn_data["gareth_command_centre"]["opportunity_intelligence_summary"] = opportunity_intelligence_summary
    glirn_data["gareth_command_centre"]["opportunity_intelligence_records"] = list(PERSISTED_OPPORTUNITY_INTELLIGENCE)
    glirn_data["gareth_command_centre"]["opportunity_intelligence_decisions"] = list(PERSISTED_OPPORTUNITY_DECISIONS)
    notification_summary = build_enquiry_notification_summary(
        PERSISTED_ENQUIRY_NOTIFICATIONS,
        enquiry_count=len(PUBLIC_LEADS),
    )
    glirn_data["gareth_command_centre"]["enquiry_notification_summary"] = notification_summary
    glirn_data["gareth_command_centre"]["enquiry_notifications"] = list(PERSISTED_ENQUIRY_NOTIFICATIONS)
    glirn_data["gareth_command_centre"]["notification_failures_requiring_attention"] = (
        notification_summary["notification_failures_requiring_attention"]
    )
    glirn_data["new_enquiries_awaiting_review"] = list(PERSISTED_RESPONSE_PACKAGES)
    glirn_data["enquiry_notification_summary"] = notification_summary
    glirn_data["enquiry_notifications"] = list(PERSISTED_ENQUIRY_NOTIFICATIONS)
    return glirn_data


@app.post("/glirn/compliance/deletion-request")
def create_glirn_deletion_request(
    request: GlirnDeletionRequest,
    x_api_key: str | None = Header(default=None)
):
    require_api_key(x_api_key)

    candidate_id = request.candidate_id.strip()
    reason = request.reason.strip()
    if not candidate_id:
        raise HTTPException(status_code=400, detail="candidate_id is required")
    if not reason:
        raise HTTPException(status_code=400, detail="reason is required")

    deletion_request = flag_deletion_request(candidate_id, reason)

    record_approval_event({
        "event_type": "glirn_compliance_event",
        "approval_id": deletion_request["request_id"],
        "decision": "DELETION_REQUEST_RECORDED",
        "provider": "glirn_compliance_core",
        "task_type": "candidate_data_deletion",
        "candidate_id": candidate_id,
        "reason": reason,
        "outbound_action_blocked": True,
        "capital_execution": False,
        "autonomous_execution": False,
    })

    return {
        "status": "deletion_request_recorded",
        "deletion_request": deletion_request,
        "outbound_action_blocked": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


@app.post("/glirn/executive-search/actions")
def record_glirn_executive_search_action(
    request: GlirnExecutiveSearchActionRequest,
    x_api_key: str | None = Header(default=None)
):
    require_api_key(x_api_key)

    opportunity_id = request.opportunity_id.strip()
    action_type = request.action_type.strip()
    reason = request.reason.strip()
    if not opportunity_id:
        raise HTTPException(status_code=400, detail="opportunity_id is required")
    if not action_type:
        raise HTTPException(status_code=400, detail="action_type is required")
    if not reason:
        raise HTTPException(status_code=400, detail="reason is required")

    if action_type not in {
        "candidate_outreach",
        "client_engagement",
        "retained_search_proposal",
        "monitor",
    }:
        raise HTTPException(status_code=400, detail="unsupported executive search action")

    glirn_data = get_glirn_dashboard_data(pending_approvals=list_pending_approvals(), public_leads=PUBLIC_LEADS)
    executive_items = glirn_data.get("executive_search", {}).get("top_executive_opportunities", [])
    item = next(
        (
            executive_item
            for executive_item in executive_items
            if executive_item.get("opportunity_id") == opportunity_id
        ),
        None,
    )

    if item is None:
        raise HTTPException(status_code=404, detail="executive search opportunity not found")

    retained_requires_approval = action_type == "retained_search_proposal"
    action_blocked = (
        item.get("outbound_action_blocked", True)
        or retained_requires_approval
    )

    record_approval_event({
        "event_type": "glirn_executive_search_action",
        "approval_id": opportunity_id,
        "decision": "ACTION_RECORDED",
        "provider": "glirn_executive_search",
        "task_type": action_type,
        "opportunity_id": opportunity_id,
        "reason": reason,
        "premium_opportunity": item.get("premium_opportunity", False),
        "estimated_placement_fee": item.get("estimated_placement_fee", 0),
        "estimated_retainer_fee": item.get("estimated_retainer_fee", 0),
        "gareth_approval_required": retained_requires_approval or action_blocked,
        "outbound_action_blocked": action_blocked,
        "capital_execution": False,
        "autonomous_execution": False,
    })

    return {
        "status": "executive_search_action_recorded",
        "opportunity_id": opportunity_id,
        "action_type": action_type,
        "gareth_approval_required": retained_requires_approval or action_blocked,
        "outbound_action_blocked": action_blocked,
        "candidate_outreach_allowed": item.get("executive_candidate_outreach_allowed", False),
        "client_engagement_allowed": item.get("client_engagement_allowed", False),
        "retained_search_proposal_requires_gareth_approval": item.get("retained_search_proposal_requires_gareth_approval", True),
        "capital_execution": False,
        "autonomous_execution": False,
    }


@app.post("/glirn/intelligence/report-requests")
def request_glirn_intelligence_report(
    request: GlirnIntelligenceReportRequest,
    x_api_key: str | None = Header(default=None)
):
    require_api_key(x_api_key)

    report_type = request.report_type.strip()
    audience = request.audience.strip()
    reason = request.reason.strip()
    if not report_type:
        raise HTTPException(status_code=400, detail="report_type is required")
    if not audience:
        raise HTTPException(status_code=400, detail="audience is required")
    if not reason:
        raise HTTPException(status_code=400, detail="reason is required")

    candidate_data_blocked = request.include_candidate_specific_data

    record_approval_event({
        "event_type": "glirn_intelligence_report_requested",
        "approval_id": f"intelligence-report-{report_type}",
        "decision": "REQUEST_APPROVAL",
        "provider": "glirn_intelligence_network",
        "task_type": report_type,
        "audience": audience,
        "reason": reason,
        "candidate_specific_data_requested": request.include_candidate_specific_data,
        "candidate_personal_data_blocked": candidate_data_blocked,
        "gareth_approval_required": True,
        "capital_execution": False,
        "autonomous_execution": False,
    })

    return {
        "status": "intelligence_report_request_recorded",
        "report_type": report_type,
        "audience": audience,
        "gareth_approval_required": True,
        "candidate_personal_data_blocked": candidate_data_blocked,
        "candidate_personal_data_included": False,
        "capital_execution": False,
        "autonomous_execution": False,
    }


@app.post("/glirn/commercial/actions")
def record_glirn_commercial_action(
    request: GlirnCommercialActionRequest,
    x_api_key: str | None = Header(default=None)
):
    require_api_key(x_api_key)

    opportunity_id = request.opportunity_id.strip()
    action_type = request.action_type.strip()
    reason = request.reason.strip()
    if not opportunity_id:
        raise HTTPException(status_code=400, detail="opportunity_id is required")
    if not action_type:
        raise HTTPException(status_code=400, detail="action_type is required")
    if not reason:
        raise HTTPException(status_code=400, detail="reason is required")
    if action_type not in {"fee_proposal", "invoice_readiness", "candidate_submission", "monitor"}:
        raise HTTPException(status_code=400, detail="unsupported commercial action")

    glirn_data = get_glirn_dashboard_data(pending_approvals=list_pending_approvals(), public_leads=PUBLIC_LEADS)
    pipeline = glirn_data.get("commercial_revenue_engine", {}).get("commercial_pipeline", [])
    item = next(
        (
            pipeline_item
            for pipeline_item in pipeline
            if pipeline_item.get("opportunity_id") == opportunity_id
        ),
        None,
    )

    if item is None:
        raise HTTPException(status_code=404, detail="commercial opportunity not found")

    fee_proposal_requires_approval = action_type == "fee_proposal" or item.get("fee_proposal_requires_gareth_approval", True)
    invoice_blocked = action_type == "invoice_readiness" and item.get("invoice_readiness") != "ready"
    candidate_submission_blocked = action_type == "candidate_submission" and not item.get("candidate_submission_allowed", False)
    action_blocked = fee_proposal_requires_approval or invoice_blocked or candidate_submission_blocked

    record_approval_event({
        "event_type": "glirn_commercial_action",
        "approval_id": opportunity_id,
        "decision": "REQUEST_APPROVAL" if action_blocked else "ACTION_RECORDED",
        "provider": "glirn_commercial_revenue_engine",
        "task_type": action_type,
        "opportunity_id": opportunity_id,
        "fee_type": item.get("fee_type"),
        "estimated_revenue": item.get("estimated_revenue", 0),
        "reason": reason,
        "gareth_approval_required": True,
        "action_blocked": action_blocked,
        "capital_execution": False,
        "autonomous_execution": False,
    })

    return {
        "status": "commercial_action_recorded",
        "opportunity_id": opportunity_id,
        "action_type": action_type,
        "fee_type": item.get("fee_type"),
        "estimated_revenue": item.get("estimated_revenue", 0),
        "gareth_approval_required": True,
        "action_blocked": action_blocked,
        "invoice_readiness": item.get("invoice_readiness"),
        "candidate_submission_allowed": item.get("candidate_submission_allowed", False),
        "capital_execution": False,
        "autonomous_execution": False,
    }


@app.post("/glirn/client-acquisition/actions")
def record_glirn_client_acquisition_action(
    request: GlirnClientAcquisitionActionRequest,
    x_api_key: str | None = Header(default=None)
):
    require_api_key(x_api_key)

    client_id = request.client_id.strip()
    action_type = request.action_type.strip()
    reason = request.reason.strip()
    if not client_id:
        raise HTTPException(status_code=400, detail="client_id is required")
    if not action_type:
        raise HTTPException(status_code=400, detail="action_type is required")
    if not reason:
        raise HTTPException(status_code=400, detail="reason is required")
    if action_type not in {"outreach", "fee_discussion", "share_candidate_details", "monitor"}:
        raise HTTPException(status_code=400, detail="unsupported client acquisition action")

    glirn_data = get_glirn_dashboard_data(pending_approvals=list_pending_approvals(), public_leads=PUBLIC_LEADS)
    clients = glirn_data.get("client_acquisition_engine", {}).get("target_client_profiles", [])
    item = next(
        (
            client
            for client in clients
            if client.get("client_id") == client_id
        ),
        None,
    )

    if item is None:
        raise HTTPException(status_code=404, detail="target client not found")

    outreach_blocked = action_type == "outreach"
    fee_discussion_blocked = action_type == "fee_discussion" and not item.get("fee_discussion_allowed", False)
    candidate_details_blocked = action_type == "share_candidate_details" and not item.get("candidate_details_allowed", False)
    action_blocked = outreach_blocked or fee_discussion_blocked or candidate_details_blocked

    record_approval_event({
        "event_type": "glirn_client_acquisition_action",
        "approval_id": client_id,
        "decision": "REQUEST_APPROVAL" if action_blocked else "ACTION_RECORDED",
        "provider": "glirn_client_acquisition_engine",
        "task_type": action_type,
        "client_id": client_id,
        "client_name": item.get("client_name"),
        "estimated_fee_potential": item.get("estimated_fee_potential", 0),
        "reason": reason,
        "gareth_approval_required": True,
        "action_blocked": action_blocked,
        "candidate_details_allowed": item.get("candidate_details_allowed", False),
        "fee_discussion_allowed": item.get("fee_discussion_allowed", False),
        "capital_execution": False,
        "autonomous_execution": False,
    })

    return {
        "status": "client_acquisition_action_recorded",
        "client_id": client_id,
        "action_type": action_type,
        "gareth_approval_required": True,
        "action_blocked": action_blocked,
        "fee_discussion_allowed": item.get("fee_discussion_allowed", False),
        "candidate_details_allowed": item.get("candidate_details_allowed", False),
        "awaiting_gareth_approval": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


@app.post("/glirn/candidate-discovery/actions")
def record_glirn_candidate_discovery_action(
    request: GlirnCandidateDiscoveryActionRequest,
    x_api_key: str | None = Header(default=None)
):
    require_api_key(x_api_key)

    candidate_id = request.candidate_id.strip()
    action_type = request.action_type.strip()
    reason = request.reason.strip()
    if not candidate_id:
        raise HTTPException(status_code=400, detail="candidate_id is required")
    if not action_type:
        raise HTTPException(status_code=400, detail="action_type is required")
    if not reason:
        raise HTTPException(status_code=400, detail="reason is required")
    if action_type not in {"outreach", "activate_profile", "share_candidate_details", "candidate_specific_intelligence", "monitor"}:
        raise HTTPException(status_code=400, detail="unsupported candidate discovery action")

    glirn_data = get_glirn_dashboard_data(pending_approvals=list_pending_approvals(), public_leads=PUBLIC_LEADS)
    candidates = glirn_data.get("candidate_discovery_engine", {}).get("candidate_profiles", [])
    item = next(
        (
            candidate
            for candidate in candidates
            if candidate.get("candidate_id") == candidate_id
        ),
        None,
    )

    if item is None:
        raise HTTPException(status_code=404, detail="candidate profile not found")

    consent_active = item.get("consent_readiness_status") == "active"
    approval_blocked = action_type == "outreach"
    activation_blocked = action_type == "activate_profile" and not consent_active
    details_blocked = action_type == "share_candidate_details" and not item.get("candidate_details_allowed", False)
    intelligence_blocked = action_type == "candidate_specific_intelligence" and not item.get("candidate_specific_intelligence_allowed", False)
    action_blocked = approval_blocked or activation_blocked or details_blocked or intelligence_blocked

    record_approval_event({
        "event_type": "glirn_candidate_discovery_action",
        "approval_id": candidate_id,
        "decision": "REQUEST_APPROVAL" if action_blocked else "ACTION_RECORDED",
        "provider": "glirn_candidate_discovery_engine",
        "task_type": action_type,
        "candidate_id": candidate_id,
        "estimated_placement_value": item.get("estimated_placement_value", 0),
        "reason": reason,
        "gareth_approval_required": True,
        "action_blocked": action_blocked,
        "consent_readiness_status": item.get("consent_readiness_status"),
        "candidate_details_allowed": item.get("candidate_details_allowed", False),
        "capital_execution": False,
        "autonomous_execution": False,
    })

    return {
        "status": "candidate_discovery_action_recorded",
        "candidate_id": candidate_id,
        "action_type": action_type,
        "gareth_approval_required": True,
        "action_blocked": action_blocked,
        "consent_readiness_status": item.get("consent_readiness_status"),
        "profile_activation_allowed": item.get("profile_activation_allowed", False),
        "candidate_details_allowed": item.get("candidate_details_allowed", False),
        "candidate_specific_intelligence_allowed": item.get("candidate_specific_intelligence_allowed", False),
        "awaiting_gareth_approval": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


@app.post("/glirn/matching/actions")
def record_glirn_matching_action(
    request: GlirnMatchingActionRequest,
    x_api_key: str | None = Header(default=None)
):
    require_api_key(x_api_key)

    match_id = request.match_id.strip()
    action_type = request.action_type.strip()
    reason = request.reason.strip()
    if not match_id:
        raise HTTPException(status_code=400, detail="match_id is required")
    if not action_type:
        raise HTTPException(status_code=400, detail="action_type is required")
    if not reason:
        raise HTTPException(status_code=400, detail="reason is required")
    if action_type not in {"activate_match", "client_facing_review", "share_candidate_details", "placement_action", "monitor"}:
        raise HTTPException(status_code=400, detail="unsupported matching action")

    glirn_data = get_glirn_dashboard_data(pending_approvals=list_pending_approvals(), public_leads=PUBLIC_LEADS)
    matches = glirn_data.get("matching_engine", {}).get("ranked_placement_matches", [])
    item = next(
        (
            match
            for match in matches
            if match.get("match_id") == match_id
        ),
        None,
    )

    if item is None:
        raise HTTPException(status_code=404, detail="placement match not found")

    activation_blocked = action_type == "activate_match" and not item.get("match_active_allowed", False)
    client_facing_blocked = action_type == "client_facing_review" and not item.get("client_facing_allowed", False)
    details_blocked = action_type == "share_candidate_details"
    placement_blocked = action_type == "placement_action"
    action_blocked = activation_blocked or client_facing_blocked or details_blocked or placement_blocked

    record_approval_event({
        "event_type": "glirn_matching_action",
        "approval_id": match_id,
        "decision": "REQUEST_APPROVAL" if action_blocked else "ACTION_RECORDED",
        "provider": "glirn_matching_engine",
        "task_type": action_type,
        "match_id": match_id,
        "match_revenue_score": item.get("match_revenue_score", 0),
        "placement_probability_score": item.get("placement_probability_score", 0),
        "reason": reason,
        "gareth_approval_required": True,
        "action_blocked": action_blocked,
        "candidate_consent_status": item.get("candidate_consent_status"),
        "client_terms_status": item.get("client_terms_status"),
        "capital_execution": False,
        "autonomous_execution": False,
    })

    return {
        "status": "matching_action_recorded",
        "match_id": match_id,
        "action_type": action_type,
        "gareth_approval_required": True,
        "action_blocked": action_blocked,
        "match_active_allowed": item.get("match_active_allowed", False),
        "client_facing_allowed": item.get("client_facing_allowed", False),
        "candidate_details_share_allowed": item.get("candidate_details_share_allowed", False),
        "placement_action_requires_gareth_approval": item.get("placement_action_requires_gareth_approval", True),
        "awaiting_gareth_approval": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


@app.post("/glirn/live-data/sources/actions")
def record_glirn_live_data_source_action(
    request: GlirnLiveDataSourceActionRequest,
    x_api_key: str | None = Header(default=None)
):
    require_api_key(x_api_key)

    source_id = request.source_id.strip()
    action_type = request.action_type.strip()
    reason = request.reason.strip()
    if not source_id:
        raise HTTPException(status_code=400, detail="source_id is required")
    if not action_type:
        raise HTTPException(status_code=400, detail="action_type is required")
    if not reason:
        raise HTTPException(status_code=400, detail="reason is required")
    if action_type not in {"propose", "approve", "block", "deactivate"}:
        raise HTTPException(status_code=400, detail="unsupported live data source action")

    glirn_data = get_glirn_dashboard_data(pending_approvals=list_pending_approvals(), public_leads=PUBLIC_LEADS)
    sources = glirn_data.get("live_data_readiness", {}).get("source_registry", [])
    source = next(
        (
            item
            for item in sources
            if item.get("source_id") == source_id
        ),
        None,
    )

    if source is None:
        raise HTTPException(status_code=404, detail="live data source not found")

    high_risk_blocked = source.get("risk_level") == "high"
    unclear_lawful_basis_blocked = source.get("lawful_basis_readiness") == "unclear"
    approval_required = True
    action_blocked = (
        action_type == "approve"
        and (high_risk_blocked or unclear_lawful_basis_blocked)
    )
    decision = "SOURCE_BLOCKED" if action_type == "block" else "REQUEST_APPROVAL"

    record_approval_event({
        "event_type": "glirn_live_data_source_action",
        "approval_id": source_id,
        "decision": decision,
        "provider": "glirn_live_data_readiness",
        "task_type": action_type,
        "source_id": source_id,
        "source_name": source.get("source_name"),
        "source_type": source.get("source_type"),
        "risk_level": source.get("risk_level"),
        "ingestion_readiness_status": source.get("ingestion_readiness_status"),
        "reason": reason,
        "gareth_approval_required": approval_required,
        "action_blocked": action_blocked,
        "contains_personal_data": source.get("contains_personal_data", False),
        "requires_candidate_consent": source.get("requires_candidate_consent", False),
        "requires_client_terms": source.get("requires_client_terms", False),
        "lawful_basis_readiness": source.get("lawful_basis_readiness"),
        "external_connection_enabled": False,
        "scraping_enabled": False,
        "live_fetching_enabled": False,
        "ingestion_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    })

    return {
        "status": "live_data_source_action_recorded",
        "source_id": source_id,
        "action_type": action_type,
        "gareth_approval_required": approval_required,
        "action_blocked": action_blocked,
        "risk_level": source.get("risk_level"),
        "ingestion_readiness_status": source.get("ingestion_readiness_status"),
        "contains_personal_data": source.get("contains_personal_data", False),
        "requires_candidate_consent": source.get("requires_candidate_consent", False),
        "requires_client_terms": source.get("requires_client_terms", False),
        "lawful_basis_readiness": source.get("lawful_basis_readiness"),
        "external_connection_enabled": False,
        "scraping_enabled": False,
        "live_fetching_enabled": False,
        "ingestion_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    }


@app.post("/glirn/integrations/actions")
def record_glirn_integration_action(
    request: GlirnIntegrationActionRequest,
    x_api_key: str | None = Header(default=None)
):
    require_api_key(x_api_key)

    integration_id = request.integration_id.strip()
    action_type = request.action_type.strip()
    reason = request.reason.strip()
    if not integration_id:
        raise HTTPException(status_code=400, detail="integration_id is required")
    if not action_type:
        raise HTTPException(status_code=400, detail="action_type is required")
    if not reason:
        raise HTTPException(status_code=400, detail="reason is required")
    if action_type not in {"propose", "approve", "reject", "suspend"}:
        raise HTTPException(status_code=400, detail="unsupported integration action")

    glirn_data = get_glirn_dashboard_data(pending_approvals=list_pending_approvals(), public_leads=PUBLIC_LEADS)
    integrations = glirn_data.get("integration_governance", {}).get("integration_registry", [])
    integration = next(
        (
            item
            for item in integrations
            if item.get("integration_id") == integration_id
        ),
        None,
    )

    if integration is None:
        raise HTTPException(status_code=404, detail="integration not found")

    high_risk_blocked = integration.get("risk_level") == "high"
    consent_blocked = (
        integration.get("contains_personal_data", False)
        and not integration.get("requires_candidate_consent", False)
    )
    action_blocked = action_type == "approve" and (high_risk_blocked or consent_blocked)
    decision = "INTEGRATION_REJECTED" if action_type == "reject" else "REQUEST_APPROVAL"
    if action_type == "suspend":
        decision = "INTEGRATION_SUSPENDED"

    record_approval_event({
        "event_type": "glirn_integration_governance_action",
        "approval_id": integration_id,
        "decision": decision,
        "provider": "glirn_integration_governance",
        "task_type": action_type,
        "integration_id": integration_id,
        "integration_name": integration.get("integration_name"),
        "integration_type": integration.get("integration_type"),
        "risk_level": integration.get("risk_level"),
        "governance_status": integration.get("governance_status"),
        "readiness_score": integration.get("readiness_score", 0),
        "reason": reason,
        "gareth_approval_required": True,
        "action_blocked": action_blocked,
        "contains_personal_data": integration.get("contains_personal_data", False),
        "requires_candidate_consent": integration.get("requires_candidate_consent", False),
        "requires_client_terms": integration.get("requires_client_terms", False),
        "external_connection_enabled": False,
        "scraping_enabled": False,
        "outbound_connection_enabled": False,
        "autonomous_activation_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    })

    return {
        "status": "integration_governance_action_recorded",
        "integration_id": integration_id,
        "action_type": action_type,
        "gareth_approval_required": True,
        "action_blocked": action_blocked,
        "risk_level": integration.get("risk_level"),
        "governance_status": integration.get("governance_status"),
        "readiness_score": integration.get("readiness_score", 0),
        "external_connection_enabled": False,
        "scraping_enabled": False,
        "outbound_connection_enabled": False,
        "autonomous_activation_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    }


@app.post("/glirn/intelligence-reviews/actions")
def record_glirn_intelligence_review_action(
    request: GlirnIntelligenceReviewActionRequest,
    x_api_key: str | None = Header(default=None)
):
    require_api_key(x_api_key)

    action_type = request.action_type.strip()
    reason = request.reason.strip()
    requested_review_id = (request.review_id or "").strip()
    if not action_type:
        raise HTTPException(status_code=400, detail="action_type is required")
    if not reason:
        raise HTTPException(status_code=400, detail="reason is required")
    if action_type not in {"generate", "approve", "reject", "monitor"}:
        raise HTTPException(status_code=400, detail="unsupported intelligence review action")

    glirn_data = get_glirn_dashboard_data(pending_approvals=list_pending_approvals(), public_leads=PUBLIC_LEADS)
    reviews = glirn_data.get("intelligence_review_engine", {}).get("generated_reviews", [])
    review = None
    if requested_review_id:
        review = next(
            (
                item
                for item in reviews
                if item.get("review_id") == requested_review_id
            ),
            None,
        )
        if review is None:
            raise HTTPException(status_code=404, detail="intelligence review not found")
    elif reviews:
        review = reviews[0]

    if review is None:
        raise HTTPException(status_code=404, detail="intelligence review not found")

    review_id = review.get("review_id")
    action_blocked = action_type == "approve"
    client_ready = False
    if action_type == "generate":
        decision = "REVIEW_GENERATED"
    elif action_type == "reject":
        decision = "REVIEW_REJECTED"
    elif action_type == "monitor":
        decision = "REVIEW_MONITORED"
    else:
        decision = "REQUEST_APPROVAL"

    record_approval_event({
        "event_type": "glirn_intelligence_review_action",
        "approval_id": review_id,
        "decision": decision,
        "provider": "glirn_intelligence_review_engine",
        "task_type": action_type,
        "review_id": review_id,
        "review_title": review.get("title"),
        "target_client_profile": review.get("target_client_profile"),
        "practice_area": review.get("practice_area"),
        "jurisdiction": review.get("jurisdiction"),
        "recommended_action": review.get("recommended_action"),
        "reason": reason,
        "gareth_approval_required": True,
        "action_blocked": action_blocked,
        "client_ready": client_ready,
        "candidate_personal_data_included": review.get("candidate_personal_data_included", False),
        "candidate_personal_data_blocked": review.get("candidate_personal_data_blocked", True),
        "client_delivery_enabled": False,
        "external_delivery_enabled": False,
        "outreach_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    })

    return {
        "status": "intelligence_review_action_recorded",
        "review_id": review_id,
        "action_type": action_type,
        "gareth_approval_required": True,
        "action_blocked": action_blocked,
        "client_ready": client_ready,
        "approval_status": review.get("approval_status", "pending_gareth_approval"),
        "compliance_status": review.get("compliance_status", "review_required"),
        "candidate_personal_data_included": review.get("candidate_personal_data_included", False),
        "candidate_personal_data_blocked": review.get("candidate_personal_data_blocked", True),
        "client_delivery_enabled": False,
        "external_delivery_enabled": False,
        "outreach_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    }


@app.post("/glirn/intelligence-briefs/human-review")
def record_glirn_human_review(
    request: GlirnHumanReviewRequest,
    x_api_key: str | None = Header(default=None),
):
    require_api_key(x_api_key)

    glirn_data = get_glirn_dashboard_data(
        pending_approvals=list_pending_approvals(),
        public_leads=PUBLIC_LEADS,
    )
    briefs = glirn_data.get("intelligence_review_engine", {}).get("generated_reviews", []) or []
    requested_brief_id = (request.brief_id or "").strip()
    brief = next(
        (item for item in briefs if item.get("review_id") == requested_brief_id),
        briefs[0] if briefs and not requested_brief_id else None,
    )
    if brief is None:
        raise HTTPException(status_code=404, detail="intelligence brief not found")

    submission = request.model_dump()
    record = evaluate_human_review(brief, submission)
    if record["validation_errors"]:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "human review requirements were not satisfied",
                "errors": record["validation_errors"],
                "incomplete_checks": record["incomplete_checks"],
                "unresolved_red_flags": record["unresolved_red_flags"],
            },
        )

    upsert_record("human_review_record", record["human_review_id"], record)
    PERSISTED_HUMAN_REVIEWS[:] = list_records("human_review_record")
    persist_safe_action(
        "intelligence_brief_human_review",
        record["human_review_id"],
        brief_id=record["brief_id"],
        enquiry_date=record["enquiry_date"],
        reviewer=record["reviewer"],
        outcome=record["outcome"],
        approval_rationale=record["approval_rationale"],
        delivery_status=record["delivery_status"],
        unresolved_red_flags=record["unresolved_red_flags"],
        candidate_consent_valid=record["candidate_consent_valid"],
        external_delivery_enabled=False,
        automatic_delivery_enabled=False,
    )
    record_approval_event({
        "event_type": "glirn_intelligence_brief_human_review",
        "approval_id": record["human_review_id"],
        "decision": record["outcome"].upper(),
        "provider": "glirn_human_review_framework",
        "task_type": "intelligence_brief_quality_assurance",
        "brief_id": record["brief_id"],
        "reviewer": record["reviewer"],
        "approval_rationale": record["approval_rationale"],
        "delivery_status": record["delivery_status"],
        "unresolved_red_flags": record["unresolved_red_flags"],
        "client_delivery_allowed": record["client_delivery_allowed"],
        "manual_delivery_only": True,
        "external_delivery_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    })
    return {
        "status": "human_review_recorded",
        "human_review_record": record,
        "available_outcomes": sorted(ALLOWED_OUTCOMES),
        "available_delivery_statuses": sorted(ALLOWED_DELIVERY_STATUSES),
        "gareth_final_approval_required": True,
        "manual_delivery_only": True,
        "external_delivery_enabled": False,
        "automatic_delivery_enabled": False,
        "payment_collection_enabled": False,
        "money_movement_enabled": False,
    }


@app.post("/glirn/intelligence-briefs/multi-agent-review")
def generate_glirn_multi_agent_review(
    request: GlirnMultiAgentReviewRequest,
    x_api_key: str | None = Header(default=None),
):
    require_api_key(x_api_key)
    glirn_data = get_glirn_dashboard_data(
        pending_approvals=list_pending_approvals(),
        public_leads=PUBLIC_LEADS,
    )
    briefs = glirn_data.get("intelligence_review_engine", {}).get("generated_reviews", []) or []
    brief = next((item for item in briefs if item.get("review_id") == request.brief_id.strip()), None)
    if brief is None:
        raise HTTPException(status_code=404, detail="intelligence brief not found")
    human_reviews = [
        record for record in PERSISTED_HUMAN_REVIEWS
        if record.get("brief_id") == brief.get("review_id")
    ]
    human_review = human_reviews[-1] if human_reviews else None
    if human_review is None:
        raise HTTPException(status_code=403, detail="Mission 106 human review is required before multi-agent review")

    review_brief = dict(brief)
    review_brief["sections"] = {
        **(brief.get("sections") or {}),
        **request.sections,
        "Required Disclaimer": REQUIRED_DISCLAIMER,
    }
    record = run_multi_agent_review(review_brief, human_review)
    upsert_record("multi_agent_review_record", record["review_id"], record)
    PERSISTED_MULTI_AGENT_REVIEWS[:] = list_records("multi_agent_review_record")
    persist_safe_action(
        "intelligence_brief_multi_agent_review",
        record["review_id"],
        brief_id=record["brief_id"],
        mission_106_review_id=record["mission_106_review_id"],
        overall_confidence_score=record["consensus_summary"]["overall_confidence_score"],
        escalation_required=record["escalation_required"],
        escalation_requirements=record["consensus_summary"]["escalation_requirements"],
        review_status=record["review_status"],
        sensitive_candidate_information_duplicated=False,
        automatic_delivery_enabled=False,
        external_commitments_enabled=False,
    )
    record_approval_event({
        "event_type": "glirn_intelligence_brief_multi_agent_review",
        "approval_id": record["review_id"],
        "decision": record["review_status"].upper(),
        "provider": "glirn_multi_agent_review_framework",
        "task_type": "intelligence_brief_multi_agent_review",
        "brief_id": record["brief_id"],
        "overall_confidence_score": record["consensus_summary"]["overall_confidence_score"],
        "escalation_required": record["escalation_required"],
        "gareth_final_approval_required": True,
        "automatic_acceptance_enabled": False,
        "automatic_payment_enabled": False,
        "automatic_candidate_outreach_enabled": False,
        "automatic_search_activity_enabled": False,
        "automatic_delivery_enabled": False,
        "external_commitments_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    })
    return {
        "status": "multi_agent_review_completed",
        "multi_agent_review": record,
        "gareth_final_approval_required": True,
        "delivery_allowed": False,
        "automatic_acceptance_enabled": False,
        "automatic_payment_enabled": False,
        "automatic_candidate_outreach_enabled": False,
        "automatic_search_activity_enabled": False,
        "automatic_delivery_enabled": False,
        "external_commitments_enabled": False,
    }


@app.post("/glirn/intelligence-briefs/confidence-assessment")
def generate_glirn_confidence_assessment(
    request: GlirnConfidenceAssessmentRequest,
    x_api_key: str | None = Header(default=None),
):
    require_api_key(x_api_key)
    glirn_data = get_glirn_dashboard_data(
        pending_approvals=list_pending_approvals(),
        public_leads=PUBLIC_LEADS,
    )
    briefs = glirn_data.get("intelligence_review_engine", {}).get("generated_reviews", []) or []
    brief = next((item for item in briefs if item.get("review_id") == request.brief_id.strip()), None)
    if brief is None:
        raise HTTPException(status_code=404, detail="intelligence brief not found")
    human_reviews = [
        record for record in PERSISTED_HUMAN_REVIEWS
        if record.get("brief_id") == brief.get("review_id")
    ]
    human_review = human_reviews[-1] if human_reviews else None
    if human_review is None:
        raise HTTPException(status_code=403, detail="Mission 106 human review is required before confidence assessment")
    multi_agent_reviews = [
        record for record in PERSISTED_MULTI_AGENT_REVIEWS
        if record.get("brief_id") == brief.get("review_id")
    ]
    multi_agent_review = multi_agent_reviews[-1] if multi_agent_reviews else None
    if multi_agent_review is None or not multi_agent_review.get("review_complete"):
        raise HTTPException(status_code=403, detail="Mission 109 multi-agent review is required before confidence assessment")
    requested_fingerprint = brief_content_fingerprint(request.sections)
    if multi_agent_review.get("content_fingerprint") != requested_fingerprint:
        raise HTTPException(status_code=409, detail="brief content changed after Mission 109 review")

    review_brief = dict(brief)
    review_brief["sections"] = {
        **(brief.get("sections") or {}),
        **request.sections,
        "Required Disclaimer": REQUIRED_DISCLAIMER,
    }
    evidence_transparency = {
        "key_evidence_considered": request.key_evidence_considered,
        "supporting_assumptions": request.supporting_assumptions,
        "known_limitations": request.known_limitations,
        "areas_requiring_caution": request.areas_requiring_caution,
        "information_gaps_identified": request.information_gaps_identified,
    }
    try:
        record = assess_confidence(
            review_brief,
            human_review,
            multi_agent_review,
            request.evidence_sufficiency,
            request.evidence_quality,
            request.data_recency,
            request.market_information_completeness,
            evidence_transparency=evidence_transparency,
            material_limitations_undermine_conclusions=request.material_limitations_undermine_conclusions,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    upsert_record("confidence_assessment_record", record["confidence_assessment_id"], record)
    PERSISTED_CONFIDENCE_ASSESSMENTS[:] = list_records("confidence_assessment_record")
    persist_safe_action(
        "intelligence_brief_confidence_assessment",
        record["confidence_assessment_id"],
        brief_id=record["brief_id"],
        mission_106_review_id=record["mission_106_review_id"],
        mission_109_review_id=record["mission_109_review_id"],
        confidence_score=record["confidence_score"],
        confidence_category=record["confidence_category"],
        evidence_sufficiency_rating=record["evidence_sufficiency_rating"],
        reviewer_agreement_level=record["reviewer_agreement"]["level"],
        escalation_required=record["escalation_required"],
        unresolved_escalations=record["unresolved_escalations"],
        confidential_source_material_logged=False,
        candidate_sensitive_information_logged=False,
        automatic_delivery_enabled=False,
        external_commitments_enabled=False,
    )
    record_approval_event({
        "event_type": "glirn_intelligence_brief_confidence_assessment",
        "approval_id": record["confidence_assessment_id"],
        "decision": record["assessment_status"].upper(),
        "provider": "glirn_confidence_engine",
        "task_type": "intelligence_brief_confidence_assessment",
        "brief_id": record["brief_id"],
        "mission_109_review_id": record["mission_109_review_id"],
        "confidence_score": record["confidence_score"],
        "confidence_category": record["confidence_category"],
        "escalation_required": record["escalation_required"],
        "gareth_override_allowed": False,
        "automatic_acceptance_enabled": False,
        "automatic_payment_enabled": False,
        "automatic_candidate_outreach_enabled": False,
        "automatic_search_activity_enabled": False,
        "automatic_delivery_enabled": False,
        "external_commitments_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    })
    return {
        "status": "confidence_assessment_completed",
        "confidence_assessment": record,
        "gareth_final_approval_required": True,
        "gareth_override_allowed": False,
        "delivery_allowed": False,
        "automatic_acceptance_enabled": False,
        "automatic_payment_enabled": False,
        "automatic_candidate_outreach_enabled": False,
        "automatic_search_activity_enabled": False,
        "automatic_delivery_enabled": False,
        "external_commitments_enabled": False,
    }


@app.post("/glirn/intelligence-briefs/global-intelligence")
def generate_glirn_global_intelligence(
    request: GlirnGlobalIntelligenceRequest,
    x_api_key: str | None = Header(default=None),
):
    require_api_key(x_api_key)
    glirn_data = get_glirn_dashboard_data(
        pending_approvals=list_pending_approvals(),
        public_leads=PUBLIC_LEADS,
    )
    briefs = glirn_data.get("intelligence_review_engine", {}).get("generated_reviews", []) or []
    brief = next((item for item in briefs if item.get("review_id") == request.brief_id.strip()), None)
    if brief is None:
        raise HTTPException(status_code=404, detail="intelligence brief not found")
    confidence_assessments = [
        record for record in PERSISTED_CONFIDENCE_ASSESSMENTS
        if record.get("brief_id") == brief.get("review_id")
    ]
    confidence_assessment = confidence_assessments[-1] if confidence_assessments else None
    if confidence_assessment is None or not confidence_assessment.get("assessment_complete"):
        raise HTTPException(status_code=403, detail="Mission 110 confidence assessment is required before global intelligence validation")
    if confidence_assessment.get("content_fingerprint") != brief_content_fingerprint(request.sections):
        raise HTTPException(status_code=409, detail="brief content changed after Mission 110 assessment")
    review_brief = dict(brief)
    review_brief["sections"] = {
        **(brief.get("sections") or {}),
        **request.sections,
        "Required Disclaimer": REQUIRED_DISCLAIMER,
    }
    try:
        record = generate_global_legal_intelligence(
            review_brief,
            confidence_assessment,
            request.jurisdiction,
            request.practice_area,
            request.indicator_ratings,
            request.evidence_basis,
            known_limitations=request.known_limitations,
            information_gaps=request.information_gaps,
            alternative_interpretations=request.alternative_interpretations,
            unsupported_claims_identified=request.unsupported_claims_identified,
            jurisdiction_expertise_limitations=request.jurisdiction_expertise_limitations,
            evidence_insufficiency_identified=request.evidence_insufficiency_identified,
            exceeds_glirn_expertise_boundaries=request.exceeds_glirn_expertise_boundaries,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    upsert_record("global_intelligence_record", record["global_intelligence_id"], record)
    PERSISTED_GLOBAL_INTELLIGENCE[:] = list_records("global_intelligence_record")
    persist_safe_action(
        "global_legal_intelligence_validation",
        record["global_intelligence_id"],
        brief_id=record["brief_id"],
        confidence_assessment_id=record["mission_110_confidence_assessment_id"],
        jurisdiction=record["jurisdiction"],
        practice_area=record["practice_area"],
        confidence_score=record["confidence_score"],
        confidence_category=record["confidence_category"],
        evidence_sufficiency_rating=record["evidence_sufficiency_rating"],
        escalation_required=record["escalation_required"],
        unresolved_escalations=record["unresolved_escalations"],
        confidential_source_material_logged=False,
        candidate_sensitive_information_logged=False,
        automatic_delivery_enabled=False,
        external_commitments_enabled=False,
    )
    record_approval_event({
        "event_type": "glirn_global_legal_intelligence_validation",
        "approval_id": record["global_intelligence_id"],
        "decision": record["validation_status"].upper(),
        "provider": "glirn_global_intelligence_engine",
        "task_type": "global_legal_intelligence_validation",
        "brief_id": record["brief_id"],
        "jurisdiction": record["jurisdiction"],
        "practice_area": record["practice_area"],
        "confidence_score": record["confidence_score"],
        "escalation_required": record["escalation_required"],
        "gareth_override_allowed": False,
        "automatic_acceptance_enabled": False,
        "automatic_payment_enabled": False,
        "automatic_candidate_outreach_enabled": False,
        "automatic_search_commitments_enabled": False,
        "automatic_delivery_enabled": False,
        "external_commitments_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    })
    return {
        "status": "global_intelligence_validation_completed",
        "global_intelligence": record,
        "gareth_final_approval_required": True,
        "gareth_override_allowed": False,
        "delivery_allowed": False,
        "automatic_acceptance_enabled": False,
        "automatic_payment_enabled": False,
        "automatic_candidate_outreach_enabled": False,
        "automatic_search_commitments_enabled": False,
        "automatic_delivery_enabled": False,
        "external_commitments_enabled": False,
    }


@app.post("/glirn/decline-decisions/recommendations")
def generate_glirn_decline_recommendation(
    request: GlirnDeclineRecommendationRequest,
    x_api_key: str | None = Header(default=None),
):
    require_api_key(x_api_key)
    try:
        record = evaluate_decline_decision(
            request.enquiry_id,
            request.factor_scores,
            request.evidence,
            referral_suitable=request.referral_suitable,
            referral_type=request.referral_type,
            referral_reason=request.referral_reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    upsert_record("decline_recommendation_record", record["recommendation_id"], record)
    PERSISTED_DECLINE_RECOMMENDATIONS[:] = list_records("decline_recommendation_record")
    persist_safe_action(
        "decline_decision_recommendation",
        record["recommendation_id"],
        enquiry_id=record["enquiry_id"],
        factor_scores=record["factor_scores"],
        recommendation=record["recommendation"],
        recommendation_reasons=record["recommendation_reasons"],
        referral_recommended=record["referral_recommendation"]["recommended"],
        gareth_final_approval_required=True,
        detailed_evidence_logged=False,
        automatic_action_executed=False,
    )
    record_approval_event({
        "event_type": "glirn_decline_decision_recommendation",
        "approval_id": record["recommendation_id"],
        "decision": record["recommendation"],
        "provider": "glirn_decline_decision_engine",
        "task_type": "should_we_decline_recommendation",
        "enquiry_id": record["enquiry_id"],
        "factor_scores": record["factor_scores"],
        "recommendation_reasons": record["recommendation_reasons"],
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
        "capital_execution": False,
        "autonomous_execution": False,
    })
    return {
        "status": "decline_recommendation_generated",
        "recommendation": record,
        "final_decision_status": "awaiting_gareth_approval",
        "gareth_final_approval_required": True,
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


@app.post("/glirn/decline-decisions/{recommendation_id}/gareth-decision")
def record_glirn_decline_final_decision(
    recommendation_id: str,
    request: GlirnDeclineFinalDecisionRequest,
    x_api_key: str | None = Header(default=None),
):
    require_api_key(x_api_key)
    recommendation = next(
        (
            item for item in PERSISTED_DECLINE_RECOMMENDATIONS
            if item.get("recommendation_id") == recommendation_id
        ),
        None,
    )
    if recommendation is None:
        raise HTTPException(status_code=404, detail="decline recommendation not found")
    try:
        decision = apply_gareth_decision(
            recommendation,
            request.final_decision,
            request.rationale,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    upsert_record("decline_decision_record", decision["decision_id"], decision)
    PERSISTED_DECLINE_DECISIONS[:] = list_records("decline_decision_record")
    persist_safe_action(
        "decline_decision_gareth_approval",
        decision["decision_id"],
        recommendation_id=decision["recommendation_id"],
        enquiry_id=decision["enquiry_id"],
        system_recommendation=decision["system_recommendation"],
        final_decision=decision["final_decision"],
        decision_by="Gareth",
        automatic_action_executed=False,
    )
    record_approval_event({
        "event_type": "glirn_decline_final_decision",
        "approval_id": decision["decision_id"],
        "decision": decision["final_decision"],
        "provider": "gareth_final_approval",
        "task_type": "should_we_decline_final_decision",
        "recommendation_id": decision["recommendation_id"],
        "enquiry_id": decision["enquiry_id"],
        "system_recommendation": decision["system_recommendation"],
        "decision_by": "Gareth",
        "automatic_action_executed": False,
        "automatic_acceptance_enabled": False,
        "automatic_decline_enabled": False,
        "automatic_referral_enabled": False,
        "automatic_payment_enabled": False,
        "automatic_candidate_outreach_enabled": False,
        "automatic_search_commitments_enabled": False,
        "automatic_delivery_enabled": False,
        "external_commitments_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    })
    return {
        "status": "gareth_final_decision_recorded",
        "decision": decision,
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


@app.post("/glirn/learning/outcomes")
def record_glirn_learning_outcome(
    request: GlirnLearningOutcomeRequest,
    x_api_key: str | None = Header(default=None),
):
    require_api_key(x_api_key)
    try:
        record = capture_learning_outcome(
            request.record_id,
            request.brief_id,
            request.gareth_decision,
            request.brief_outcome,
            request.remediation_outcome,
            request.outcome_summary,
            request.decline_reason_codes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    upsert_record("learning_outcome_record", record["learning_outcome_id"], record)
    PERSISTED_LEARNING_OUTCOMES[:] = list_records("learning_outcome_record")
    persist_safe_action(
        "glirn_learning_outcome_captured",
        record["learning_outcome_id"],
        brief_id=record["brief_id"],
        gareth_decision=record["gareth_decision"],
        brief_outcome=record["brief_outcome"],
        remediation_outcome=record["remediation_outcome"],
        decline_reason_codes=record["decline_reason_codes"],
        sensitive_outcome_summary_logged=False,
        automatic_action_executed=False,
    )
    record_approval_event({
        "event_type": "glirn_internal_learning_outcome",
        "approval_id": record["learning_outcome_id"],
        "decision": record["gareth_decision"],
        "provider": "gareth_recorded_outcome",
        "task_type": "internal_learning_outcome_capture",
        "brief_id": record["brief_id"],
        "brief_outcome": record["brief_outcome"],
        "remediation_outcome": record["remediation_outcome"],
        "sensitive_information_logged": False,
        "autonomous_execution": False,
    })
    return {"status": "learning_outcome_recorded", "learning_outcome": record}


@app.post("/glirn/learning/insights")
def generate_glirn_learning_insights(x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)
    insight = generate_improvement_insights(PERSISTED_LEARNING_OUTCOMES)
    upsert_record("learning_insight_record", insight["insight_id"], insight)
    PERSISTED_LEARNING_INSIGHTS[:] = list_records("learning_insight_record")
    persist_safe_action(
        "glirn_learning_insight_generated",
        insight["insight_id"],
        outcome_count=insight["outcome_count"],
        recommendation_count=len(insight["recommendation_improvement_insights"]),
        recommendation_only=True,
        gareth_approval_mandatory=True,
        sensitive_details_logged=False,
        automatic_action_executed=False,
    )
    return {"status": "learning_insight_generated", "insight": insight}


@app.post("/glirn/learning/insights/{insight_id}/gareth-approval")
def approve_glirn_learning_insight(
    insight_id: str,
    request: GlirnLearningInsightApprovalRequest,
    x_api_key: str | None = Header(default=None),
):
    require_api_key(x_api_key)
    insight = next((item for item in PERSISTED_LEARNING_INSIGHTS if item.get("insight_id") == insight_id), None)
    if insight is None:
        raise HTTPException(status_code=404, detail="learning insight not found")
    try:
        approval = approve_learning_insight(insight, request.rationale)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    upsert_record("learning_approval_record", approval["learning_approval_id"], approval)
    PERSISTED_LEARNING_APPROVALS[:] = list_records("learning_approval_record")
    persist_safe_action(
        "glirn_learning_insight_gareth_approval",
        approval["learning_approval_id"],
        insight_id=approval["insight_id"],
        approved_by="Gareth",
        approved_for_manual_consideration=True,
        knowledge_or_policy_updated=False,
        automatic_action_executed=False,
    )
    record_approval_event({
        "event_type": "glirn_learning_insight_approval",
        "approval_id": approval["learning_approval_id"],
        "decision": "approved_for_manual_consideration",
        "provider": "gareth_final_approval",
        "task_type": "internal_learning_insight_approval",
        "insight_id": approval["insight_id"],
        "automatic_action_executed": False,
        "autonomous_execution": False,
    })
    return {"status": "learning_insight_approved_for_manual_consideration", "approval": approval}


@app.post("/glirn/external-learning/evidence")
def record_glirn_external_evidence(
    request: GlirnExternalEvidenceRequest,
    x_api_key: str | None = Header(default=None),
):
    require_api_key(x_api_key)
    try:
        evidence = ingest_public_evidence(
            request.evidence_id,
            request.source_type,
            request.title,
            request.publisher,
            request.source_url,
            request.publication_date,
            request.evidence_summary,
            request.jurisdiction,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    upsert_record("external_evidence_record", evidence["evidence_id"], evidence)
    PERSISTED_EXTERNAL_EVIDENCE[:] = list_records("external_evidence_record")
    persist_safe_action(
        "glirn_external_evidence_ingested",
        evidence["evidence_id"],
        source_type=evidence["source_type"],
        publisher=evidence["publisher"],
        confidence_category=evidence["confidence_category"],
        evidence_weight=evidence["evidence_weight"],
        source_content_logged=False,
        external_retrieval_executed=False,
    )
    return {"status": "external_evidence_recorded", "evidence": evidence}


@app.post("/glirn/external-learning/intelligence")
def generate_glirn_external_learning_intelligence(
    request: GlirnExternalIntelligenceRequest,
    x_api_key: str | None = Header(default=None),
):
    require_api_key(x_api_key)
    requested_ids = set(request.evidence_ids)
    records = [item for item in PERSISTED_EXTERNAL_EVIDENCE if item.get("evidence_id") in requested_ids]
    if len(records) != len(requested_ids) or not records:
        raise HTTPException(status_code=404, detail="one or more external evidence records were not found")
    try:
        intelligence = generate_external_intelligence(records, request.topic)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    upsert_record(
        "external_intelligence_learning_record",
        intelligence["external_intelligence_id"],
        intelligence,
    )
    PERSISTED_EXTERNAL_INTELLIGENCE[:] = list_records("external_intelligence_learning_record")
    persist_safe_action(
        "glirn_external_intelligence_generated",
        intelligence["external_intelligence_id"],
        evidence_ids=intelligence["evidence_ids"],
        source_count=intelligence["source_count"],
        confidence_category=intelligence["confidence_category"],
        weighted_confidence_score=intelligence["weighted_confidence_score"],
        recommendation_only=True,
        legal_advice_provided=False,
        automatic_action_executed=False,
    )
    return {"status": "external_intelligence_generated", "intelligence": intelligence}


@app.post("/glirn/external-learning/intelligence/{intelligence_id}/gareth-approval")
def approve_glirn_knowledge_update(
    intelligence_id: str,
    request: GlirnKnowledgeUpdateApprovalRequest,
    x_api_key: str | None = Header(default=None),
):
    require_api_key(x_api_key)
    intelligence = next(
        (item for item in PERSISTED_EXTERNAL_INTELLIGENCE if item.get("external_intelligence_id") == intelligence_id),
        None,
    )
    if intelligence is None:
        raise HTTPException(status_code=404, detail="external intelligence record not found")
    try:
        update = approve_knowledge_update(intelligence, request.rationale)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    upsert_record("knowledge_base_record", update["knowledge_update_id"], update)
    PERSISTED_KNOWLEDGE_UPDATES[:] = list_records("knowledge_base_record")
    persist_safe_action(
        "glirn_knowledge_update_gareth_approval",
        update["knowledge_update_id"],
        external_intelligence_id=update["external_intelligence_id"],
        evidence_ids=update["evidence_ids"],
        approved_by="Gareth",
        knowledge_base_status=update["knowledge_base_status"],
        approval_rationale_logged=False,
        automatic_regulatory_change_implemented=False,
    )
    record_approval_event({
        "event_type": "glirn_external_knowledge_update_approval",
        "approval_id": update["knowledge_update_id"],
        "decision": "approved_for_manual_use",
        "provider": "gareth_final_approval",
        "task_type": "external_knowledge_update",
        "external_intelligence_id": update["external_intelligence_id"],
        "automatic_regulatory_change_implemented": False,
        "external_contact_executed": False,
        "autonomous_execution": False,
    })
    return {"status": "knowledge_update_approved_for_manual_use", "knowledge_update": update}


@app.post("/glirn/opportunity-intelligence/signals")
def record_glirn_opportunity_signal(
    request: GlirnOpportunitySignalRequest,
    x_api_key: str | None = Header(default=None),
):
    require_api_key(x_api_key)
    try:
        signal = record_opportunity_signal(
            request.signal_id,
            request.category,
            request.source_type,
            request.title,
            request.publisher,
            request.source_url,
            request.publication_date,
            request.signal_summary,
            request.organisation,
            request.jurisdiction,
            request.practice_area,
            request.signal_strength,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    upsert_record("opportunity_signal_record", signal["signal_id"], signal)
    PERSISTED_OPPORTUNITY_SIGNALS[:] = list_records("opportunity_signal_record")
    persist_safe_action(
        "glirn_opportunity_signal_recorded",
        signal["signal_id"],
        category=signal["category"],
        source_type=signal["source_type"],
        source_confidence=signal["source_confidence"],
        source_weight=signal["source_weight"],
        signal_strength=signal["signal_strength"],
        organisation=signal["organisation"],
        sensitive_signal_summary_logged=False,
        external_retrieval_executed=False,
        automatic_action_executed=False,
    )
    return {"status": "opportunity_signal_recorded", "signal": signal}


@app.post("/glirn/opportunity-intelligence/recommendations")
def generate_glirn_opportunity_intelligence(
    request: GlirnOpportunityRecommendationRequest,
    x_api_key: str | None = Header(default=None),
):
    require_api_key(x_api_key)
    requested_ids = set(request.signal_ids)
    signals = [item for item in PERSISTED_OPPORTUNITY_SIGNALS if item.get("signal_id") in requested_ids]
    if not requested_ids or len(signals) != len(requested_ids):
        raise HTTPException(status_code=404, detail="one or more opportunity signals were not found")
    try:
        recommendation = generate_opportunity_recommendation(signals)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    upsert_record(
        "opportunity_intelligence_record",
        recommendation["opportunity_intelligence_id"],
        recommendation,
    )
    PERSISTED_OPPORTUNITY_INTELLIGENCE[:] = list_records("opportunity_intelligence_record")
    persist_safe_action(
        "glirn_opportunity_recommendation_generated",
        recommendation["opportunity_intelligence_id"],
        organisation=recommendation["organisation"],
        categories=recommendation["categories"],
        signal_ids=recommendation["signal_ids"],
        source_count=recommendation["source_count"],
        confidence_score=recommendation["confidence_score"],
        confidence_category=recommendation["confidence_category"],
        priority=recommendation["priority"],
        recommendation_only=True,
        detailed_evidence_logged=False,
        automatic_action_executed=False,
    )
    record_approval_event({
        "event_type": "glirn_opportunity_intelligence_recommendation",
        "approval_id": recommendation["opportunity_intelligence_id"],
        "decision": "awaiting_gareth_approval",
        "provider": "glirn_opportunity_intelligence_engine",
        "task_type": "public_opportunity_signal_review",
        "organisation": recommendation["organisation"],
        "categories": recommendation["categories"],
        "confidence_score": recommendation["confidence_score"],
        "recommendation_only": True,
        "autonomous_execution": False,
    })
    return {
        "status": "opportunity_recommendation_generated",
        "recommendation": recommendation,
        "gareth_approval_required": True,
        "automatic_action_executed": False,
    }


@app.post("/glirn/opportunity-intelligence/{intelligence_id}/gareth-decision")
def record_glirn_opportunity_intelligence_decision(
    intelligence_id: str,
    request: GlirnOpportunityDecisionRequest,
    x_api_key: str | None = Header(default=None),
):
    require_api_key(x_api_key)
    recommendation = next(
        (
            item for item in PERSISTED_OPPORTUNITY_INTELLIGENCE
            if item.get("opportunity_intelligence_id") == intelligence_id
        ),
        None,
    )
    if recommendation is None:
        raise HTTPException(status_code=404, detail="opportunity intelligence recommendation not found")
    try:
        decision = apply_gareth_opportunity_decision(
            recommendation,
            request.decision,
            request.rationale,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    upsert_record(
        "opportunity_intelligence_decision_record",
        decision["opportunity_decision_id"],
        decision,
    )
    PERSISTED_OPPORTUNITY_DECISIONS[:] = list_records("opportunity_intelligence_decision_record")
    persist_safe_action(
        "glirn_opportunity_gareth_decision",
        decision["opportunity_decision_id"],
        opportunity_intelligence_id=decision["opportunity_intelligence_id"],
        organisation=decision["organisation"],
        decision=decision["decision"],
        decision_by="Gareth",
        decision_rationale_logged=False,
        manual_review_only=True,
        automatic_action_executed=False,
    )
    record_approval_event({
        "event_type": "glirn_opportunity_intelligence_gareth_decision",
        "approval_id": decision["opportunity_decision_id"],
        "decision": decision["decision"],
        "provider": "gareth_final_approval",
        "task_type": "opportunity_intelligence_decision",
        "opportunity_intelligence_id": decision["opportunity_intelligence_id"],
        "automatic_action_executed": False,
        "autonomous_execution": False,
    })
    return {"status": "gareth_opportunity_decision_recorded", "decision": decision}


@app.post("/glirn/intelligence-briefs/{brief_id}/final-approval")
def record_glirn_intelligence_brief_final_approval(
    brief_id: str,
    request: GlirnIntelligenceBriefFinalApprovalRequest,
    x_api_key: str | None = Header(default=None),
):
    require_api_key(x_api_key)
    action_type = request.action_type.strip()
    if action_type not in {"approve", "reject", "needs_more_information"}:
        raise HTTPException(status_code=400, detail="unsupported final approval action")
    if not request.reason.strip():
        raise HTTPException(status_code=400, detail="reason is required")
    reviews = [item for item in PERSISTED_MULTI_AGENT_REVIEWS if item.get("brief_id") == brief_id]
    review = reviews[-1] if reviews else None
    if review is None or not review.get("review_complete"):
        raise HTTPException(status_code=403, detail="Mission 109 multi-agent review is required before final approval")
    if review.get("escalation_required") or review.get("unresolved_escalations"):
        raise HTTPException(status_code=403, detail="unresolved Mission 109 escalations block final approval")
    confidence_assessments = [
        item for item in PERSISTED_CONFIDENCE_ASSESSMENTS if item.get("brief_id") == brief_id
    ]
    confidence_assessment = confidence_assessments[-1] if confidence_assessments else None
    if confidence_assessment is None or not confidence_assessment.get("assessment_complete"):
        raise HTTPException(status_code=403, detail="Mission 110 confidence assessment is required before final approval")
    if confidence_assessment.get("mission_109_review_id") != review.get("review_id"):
        raise HTTPException(status_code=409, detail="Mission 110 assessment must be repeated after Mission 109 review")
    if confidence_assessment.get("content_fingerprint") != review.get("content_fingerprint"):
        raise HTTPException(status_code=409, detail="Mission 110 assessment must be repeated after Mission 109 review")
    if confidence_assessment.get("escalation_required") or confidence_assessment.get("unresolved_escalations"):
        raise HTTPException(
            status_code=403,
            detail="unresolved Mission 110 escalations require remediation and Mission 109 and Mission 110 reassessment",
        )
    if float(confidence_assessment.get("confidence_score", 0)) < 70:
        raise HTTPException(status_code=403, detail="confidence below 70 blocks final approval")
    global_validations = [
        item for item in PERSISTED_GLOBAL_INTELLIGENCE if item.get("brief_id") == brief_id
    ]
    global_validation = global_validations[-1] if global_validations else None
    if global_validation is None or not global_validation.get("validation_complete"):
        raise HTTPException(status_code=403, detail="Mission 111 global intelligence validation is required before final approval")
    if global_validation.get("mission_110_confidence_assessment_id") != confidence_assessment.get("confidence_assessment_id"):
        raise HTTPException(status_code=409, detail="Mission 111 validation must be repeated after Mission 110 assessment")
    if global_validation.get("content_fingerprint") != confidence_assessment.get("content_fingerprint"):
        raise HTTPException(status_code=409, detail="Mission 111 validation must be repeated after Mission 110 assessment")
    if global_validation.get("escalation_required") or global_validation.get("unresolved_escalations"):
        raise HTTPException(status_code=403, detail="unresolved Mission 111 escalations block final approval")

    final_approval_id = f"intelligence-brief-final-approval-{brief_id}"
    status_map = {
        "approve": "approved_by_gareth",
        "reject": "rejected_by_gareth",
        "needs_more_information": "needs_more_information",
    }
    final_status = status_map[action_type]
    FINAL_APPROVAL_LOCAL_STATUS[final_approval_id] = final_status
    set_state("final_approval_statuses", FINAL_APPROVAL_LOCAL_STATUS)
    persist_safe_action(
        "intelligence_brief_final_approval",
        final_approval_id,
        brief_id=brief_id,
        multi_agent_review_id=review["review_id"],
        confidence_assessment_id=confidence_assessment["confidence_assessment_id"],
        global_intelligence_id=global_validation["global_intelligence_id"],
        final_approval_status=final_status,
        reason=request.reason.strip(),
        gareth_final_decision=True,
        automatic_acceptance_enabled=False,
        automatic_payment_enabled=False,
        automatic_candidate_outreach_enabled=False,
        automatic_search_activity_enabled=False,
        automatic_delivery_enabled=False,
        external_commitments_enabled=False,
    )
    record_approval_event({
        "event_type": "glirn_intelligence_brief_final_approval",
        "approval_id": final_approval_id,
        "decision": final_status.upper(),
        "provider": "gareth_final_approval",
        "task_type": "intelligence_brief_final_approval",
        "brief_id": brief_id,
        "multi_agent_review_id": review["review_id"],
        "confidence_assessment_id": confidence_assessment["confidence_assessment_id"],
        "global_intelligence_id": global_validation["global_intelligence_id"],
        "reason": request.reason.strip(),
        "gareth_final_decision": True,
        "automatic_acceptance_enabled": False,
        "automatic_payment_enabled": False,
        "automatic_candidate_outreach_enabled": False,
        "automatic_search_activity_enabled": False,
        "automatic_delivery_enabled": False,
        "external_commitments_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    })
    return {
        "status": "intelligence_brief_final_approval_recorded",
        "final_approval_id": final_approval_id,
        "brief_id": brief_id,
        "multi_agent_review_id": review["review_id"],
        "confidence_assessment_id": confidence_assessment["confidence_assessment_id"],
        "global_intelligence_id": global_validation["global_intelligence_id"],
        "final_approval_status": final_status,
        "automatic_acceptance_enabled": False,
        "automatic_payment_enabled": False,
        "automatic_candidate_outreach_enabled": False,
        "automatic_search_activity_enabled": False,
        "automatic_delivery_enabled": False,
        "external_commitments_enabled": False,
    }


@app.post("/glirn/intelligence-briefs/package")
def generate_glirn_intelligence_brief_package(
    request: GlirnIntelligenceBriefPackageRequest,
    x_api_key: str | None = Header(default=None),
):
    require_api_key(x_api_key)

    glirn_data = get_glirn_dashboard_data(
        pending_approvals=list_pending_approvals(),
        public_leads=PUBLIC_LEADS,
    )
    briefs = glirn_data.get("intelligence_review_engine", {}).get("generated_reviews", []) or []
    brief = next((item for item in briefs if item.get("review_id") == request.brief_id.strip()), None)
    if brief is None:
        raise HTTPException(status_code=404, detail="intelligence brief not found")

    matching_reviews = [
        record for record in PERSISTED_HUMAN_REVIEWS
        if record.get("brief_id") == brief.get("review_id")
    ]
    human_review = matching_reviews[-1] if matching_reviews else None
    if human_review is None:
        raise HTTPException(status_code=403, detail="Mission 106 human review is required before delivery packaging")

    matching_multi_agent_reviews = [
        record for record in PERSISTED_MULTI_AGENT_REVIEWS
        if record.get("brief_id") == brief.get("review_id")
    ]
    multi_agent_review = matching_multi_agent_reviews[-1] if matching_multi_agent_reviews else None
    if multi_agent_review is None or not multi_agent_review.get("review_complete"):
        raise HTTPException(status_code=403, detail="Mission 109 multi-agent review is required before delivery packaging")
    if multi_agent_review.get("escalation_required") or multi_agent_review.get("unresolved_escalations"):
        raise HTTPException(status_code=403, detail="unresolved Mission 109 escalations block delivery packaging")
    if multi_agent_review.get("content_fingerprint") != brief_content_fingerprint(request.sections):
        raise HTTPException(status_code=409, detail="brief content changed after Mission 109 review")

    matching_confidence_assessments = [
        record for record in PERSISTED_CONFIDENCE_ASSESSMENTS
        if record.get("brief_id") == brief.get("review_id")
    ]
    confidence_assessment = matching_confidence_assessments[-1] if matching_confidence_assessments else None
    if confidence_assessment is None or not confidence_assessment.get("assessment_complete"):
        raise HTTPException(status_code=403, detail="Mission 110 confidence assessment is required before delivery packaging")
    if confidence_assessment.get("mission_109_review_id") != multi_agent_review.get("review_id"):
        raise HTTPException(status_code=409, detail="Mission 110 assessment must be repeated after Mission 109 review")
    if confidence_assessment.get("content_fingerprint") != brief_content_fingerprint(request.sections):
        raise HTTPException(status_code=409, detail="brief content changed after Mission 110 assessment")
    if confidence_assessment.get("escalation_required") or confidence_assessment.get("unresolved_escalations"):
        raise HTTPException(
            status_code=403,
            detail="unresolved Mission 110 escalations require remediation and Mission 109 and Mission 110 reassessment",
        )
    if float(confidence_assessment.get("confidence_score", 0)) < 70:
        raise HTTPException(status_code=403, detail="confidence below 70 blocks delivery packaging")

    matching_global_validations = [
        record for record in PERSISTED_GLOBAL_INTELLIGENCE
        if record.get("brief_id") == brief.get("review_id")
    ]
    global_validation = matching_global_validations[-1] if matching_global_validations else None
    if global_validation is None or not global_validation.get("validation_complete"):
        raise HTTPException(status_code=403, detail="Mission 111 global intelligence validation is required before delivery packaging")
    if global_validation.get("mission_110_confidence_assessment_id") != confidence_assessment.get("confidence_assessment_id"):
        raise HTTPException(status_code=409, detail="Mission 111 validation must be repeated after Mission 110 assessment")
    if global_validation.get("content_fingerprint") != brief_content_fingerprint(request.sections):
        raise HTTPException(status_code=409, detail="brief content changed after Mission 111 validation")
    if global_validation.get("escalation_required") or global_validation.get("unresolved_escalations"):
        raise HTTPException(status_code=403, detail="unresolved Mission 111 escalations block delivery packaging")

    expected_final_approval_id = f"intelligence-brief-final-approval-{brief.get('review_id')}"
    requested_final_approval_id = (request.final_approval_id or expected_final_approval_id).strip()
    if requested_final_approval_id != expected_final_approval_id:
        raise HTTPException(status_code=403, detail="final approval does not match the intelligence brief")
    if FINAL_APPROVAL_LOCAL_STATUS.get(expected_final_approval_id) != "approved_by_gareth":
        raise HTTPException(status_code=403, detail="final Gareth approval is required before delivery packaging")

    audit_record_id = f"intelligence-brief-audit-{brief.get('review_id')}"
    try:
        package = build_intelligence_brief_package(
            brief,
            human_review,
            request.sections,
            audit_record_id=audit_record_id,
        )
    except IntelligenceBriefValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    evidence_markdown = render_evidence_transparency_markdown(confidence_assessment)
    package["confidence_assessment_id"] = confidence_assessment["confidence_assessment_id"]
    package["confidence_score"] = confidence_assessment["confidence_score"]
    package["confidence_category"] = confidence_assessment["confidence_category"]
    package["evidence_transparency"] = confidence_assessment["evidence_transparency"]
    global_intelligence_markdown = render_global_intelligence_markdown(global_validation)
    package["global_intelligence_id"] = global_validation["global_intelligence_id"]
    package["global_intelligence"] = global_validation
    package["sections"]["Confidence and Evidence Transparency"] = evidence_markdown
    package["sections"]["Global Legal Intelligence"] = global_intelligence_markdown
    package["markdown"] = package["markdown"].replace(
        "Delivery status: Ready for manual delivery only.",
        f"{evidence_markdown}\n\n{global_intelligence_markdown}\n\nDelivery status: Ready for manual delivery only.",
    )

    os.makedirs(GLIRN_INTELLIGENCE_BRIEFS_DIR, exist_ok=True)
    local_file_path = os.path.join(
        GLIRN_INTELLIGENCE_BRIEFS_DIR,
        package["suggested_filename"],
    )
    with open(local_file_path, "w", encoding="utf-8") as brief_file:
        brief_file.write(package["markdown"])

    brief_record = {
        **package,
        "local_file_path": local_file_path,
        "multi_agent_review_id": multi_agent_review["review_id"],
        "confidence_assessment_id": confidence_assessment["confidence_assessment_id"],
        "global_intelligence_id": global_validation["global_intelligence_id"],
        "final_approval_id": expected_final_approval_id,
        "final_approval_status": "approved_by_gareth",
    }
    audit_record = {
        "audit_record_id": audit_record_id,
        "brief_record_id": package["brief_record_id"],
        "review_record_id": package["review_record_id"],
        "multi_agent_review_id": multi_agent_review["review_id"],
        "confidence_assessment_id": confidence_assessment["confidence_assessment_id"],
        "global_intelligence_id": global_validation["global_intelligence_id"],
        "confidence_score": confidence_assessment["confidence_score"],
        "confidence_category": confidence_assessment["confidence_category"],
        "final_approval_id": expected_final_approval_id,
        "event_type": "intelligence_brief_package_generated",
        "generated_at": package["generated_at"],
        "reviewer_identity": package["reviewer_identity"],
        "review_date": package["review_date"],
        "manual_delivery_only": True,
        "automatic_acceptance_enabled": False,
        "automatic_payment_enabled": False,
        "automatic_candidate_outreach_enabled": False,
        "automatic_search_activity_enabled": False,
        "automatic_delivery_enabled": False,
        "external_delivery_enabled": False,
    }
    upsert_record("intelligence_brief_record", package["brief_record_id"], brief_record)
    upsert_record("intelligence_brief_audit_record", audit_record_id, audit_record)
    PERSISTED_INTELLIGENCE_BRIEFS[:] = list_records("intelligence_brief_record")
    persist_safe_action(
        "intelligence_brief_package_generated",
        audit_record_id,
        brief_record_id=package["brief_record_id"],
        review_record_id=package["review_record_id"],
        multi_agent_review_id=multi_agent_review["review_id"],
        confidence_assessment_id=confidence_assessment["confidence_assessment_id"],
        global_intelligence_id=global_validation["global_intelligence_id"],
        confidence_score=confidence_assessment["confidence_score"],
        confidence_category=confidence_assessment["confidence_category"],
        final_approval_id=expected_final_approval_id,
        reviewer_identity=package["reviewer_identity"],
        review_date=package["review_date"],
        local_file_path=local_file_path,
        manual_delivery_only=True,
        automatic_delivery_enabled=False,
        external_delivery_enabled=False,
    )
    record_approval_event({
        "event_type": "glirn_intelligence_brief_package_generated",
        "approval_id": audit_record_id,
        "decision": "PACKAGE_READY_FOR_MANUAL_DELIVERY",
        "provider": "glirn_intelligence_brief_delivery_framework",
        "task_type": "generate_delivery_ready_package",
        "brief_record_id": package["brief_record_id"],
        "review_record_id": package["review_record_id"],
        "multi_agent_review_id": multi_agent_review["review_id"],
        "confidence_assessment_id": confidence_assessment["confidence_assessment_id"],
        "global_intelligence_id": global_validation["global_intelligence_id"],
        "confidence_score": confidence_assessment["confidence_score"],
        "confidence_category": confidence_assessment["confidence_category"],
        "final_approval_id": expected_final_approval_id,
        "reviewer_identity": package["reviewer_identity"],
        "review_date": package["review_date"],
        "local_file_path": local_file_path,
        "manual_delivery_only": True,
        "automatic_delivery_enabled": False,
        "external_delivery_enabled": False,
        "external_integrations_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    })
    return {
        "status": "intelligence_brief_package_ready_for_manual_delivery",
        "intelligence_brief_package": brief_record,
        "audit_record": audit_record,
        "manual_delivery_only": True,
        "automatic_acceptance_enabled": False,
        "automatic_payment_enabled": False,
        "automatic_candidate_outreach_enabled": False,
        "automatic_search_activity_enabled": False,
        "automatic_delivery_enabled": False,
        "external_commitments_enabled": False,
        "external_delivery_enabled": False,
        "email_sending_enabled": False,
        "external_upload_enabled": False,
        "external_integrations_enabled": False,
    }


@app.post("/glirn/deliverables/actions")
def record_glirn_deliverable_action(
    request: GlirnDeliverableActionRequest,
    x_api_key: str | None = Header(default=None)
):
    require_api_key(x_api_key)

    action_type = request.action_type.strip()
    reason = request.reason.strip()
    requested_deliverable_id = (request.deliverable_id or "").strip()
    if not action_type:
        raise HTTPException(status_code=400, detail="action_type is required")
    if not reason:
        raise HTTPException(status_code=400, detail="reason is required")
    if action_type not in {"generate", "approve", "reject", "monitor"}:
        raise HTTPException(status_code=400, detail="unsupported deliverable action")

    glirn_data = get_glirn_dashboard_data(pending_approvals=list_pending_approvals(), public_leads=PUBLIC_LEADS)
    deliverables = glirn_data.get("deliverable_factory", {}).get("generated_deliverables", [])
    deliverable = None
    if requested_deliverable_id:
        deliverable = next(
            (
                item
                for item in deliverables
                if item.get("deliverable_id") == requested_deliverable_id
            ),
            None,
        )
        if deliverable is None:
            raise HTTPException(status_code=404, detail="deliverable not found")
    elif deliverables:
        deliverable = deliverables[0]

    if deliverable is None:
        raise HTTPException(status_code=404, detail="deliverable not found")

    deliverable_id = deliverable.get("deliverable_id")
    action_blocked = action_type == "approve"
    client_ready = False
    if action_type == "generate":
        decision = "DELIVERABLE_GENERATED"
    elif action_type == "reject":
        decision = "DELIVERABLE_REJECTED"
    elif action_type == "monitor":
        decision = "DELIVERABLE_MONITORED"
    else:
        decision = "REQUEST_APPROVAL"

    record_approval_event({
        "event_type": "glirn_deliverable_action",
        "approval_id": deliverable_id,
        "decision": decision,
        "provider": "glirn_deliverable_factory",
        "task_type": action_type,
        "deliverable_id": deliverable_id,
        "deliverable_type": deliverable.get("deliverable_type"),
        "deliverable_title": deliverable.get("title"),
        "target_client_profile": deliverable.get("target_client_profile"),
        "recommended_action": deliverable.get("recommended_action"),
        "reason": reason,
        "gareth_approval_required": True,
        "action_blocked": action_blocked,
        "client_ready": client_ready,
        "candidate_personal_data_included": deliverable.get("candidate_personal_data_included", False),
        "candidate_personal_data_blocked": deliverable.get("candidate_personal_data_blocked", True),
        "client_delivery_enabled": False,
        "external_delivery_enabled": False,
        "outreach_enabled": False,
        "fee_proposal_autonomous": False,
        "contracts_autonomous": False,
        "capital_execution": False,
        "autonomous_execution": False,
    })

    return {
        "status": "deliverable_action_recorded",
        "deliverable_id": deliverable_id,
        "action_type": action_type,
        "gareth_approval_required": True,
        "action_blocked": action_blocked,
        "client_ready": client_ready,
        "approval_status": deliverable.get("approval_status", "pending_gareth_approval"),
        "compliance_status": deliverable.get("compliance_status", "review_required"),
        "candidate_personal_data_included": deliverable.get("candidate_personal_data_included", False),
        "candidate_personal_data_blocked": deliverable.get("candidate_personal_data_blocked", True),
        "client_delivery_enabled": False,
        "external_delivery_enabled": False,
        "outreach_enabled": False,
        "fee_proposal_autonomous": False,
        "contracts_autonomous": False,
        "capital_execution": False,
        "autonomous_execution": False,
    }


@app.post("/glirn/approval-to-action/actions")
def record_glirn_approval_to_action(
    request: GlirnApprovalToActionRequest,
    x_api_key: str | None = Header(default=None)
):
    require_api_key(x_api_key)

    item_id = request.item_id.strip()
    action_type = request.action_type.strip()
    reason = request.reason.strip()
    if not item_id:
        raise HTTPException(status_code=400, detail="item_id is required")
    if not action_type:
        raise HTTPException(status_code=400, detail="action_type is required")
    if not reason:
        raise HTTPException(status_code=400, detail="reason is required")
    if action_type not in {"approve", "reject", "monitor", "reset-to-draft"}:
        raise HTTPException(status_code=400, detail="unsupported approval-to-action action")

    glirn_data = get_glirn_dashboard_data(pending_approvals=list_pending_approvals(), public_leads=PUBLIC_LEADS)
    workflow = glirn_data.get("approval_to_action_workflow", {})
    items = []
    for key in ("pending_gareth_approval", "approved_for_human_use", "rejected_items", "monitored_items"):
        items.extend(workflow.get(key, []) or [])
    item = next(
        (
            entry
            for entry in items
            if entry.get("item_id") == item_id
        ),
        None,
    )

    if item is None:
        raise HTTPException(status_code=404, detail="approval workflow item not found")

    if action_type == "approve":
        result = {
            **item,
            "approval_status": "approved_by_gareth",
            "client_ready_status": "ready_for_human_use",
            "action_readiness_status": "approved_for_human_controlled_use",
            "client_ready": True,
            "human_use_ready": True,
        }
        decision = "APPROVED_FOR_HUMAN_USE"
    elif action_type == "reject":
        result = {
            **item,
            "approval_status": "rejected_by_gareth",
            "client_ready_status": "blocked_not_client_ready",
            "action_readiness_status": "rejected",
            "client_ready": False,
            "human_use_ready": False,
        }
        decision = "REJECTED"
    elif action_type == "monitor":
        result = {
            **item,
            "approval_status": "monitoring",
            "client_ready_status": "not_client_ready",
            "action_readiness_status": "monitoring_pending_future_review",
            "client_ready": False,
            "human_use_ready": False,
        }
        decision = "MONITORED"
    else:
        result = {
            **item,
            "approval_status": "pending_gareth_approval",
            "client_ready_status": "not_client_ready",
            "action_readiness_status": "reset_to_draft",
            "client_ready": False,
            "human_use_ready": False,
        }
        decision = "RESET_TO_DRAFT"

    record_approval_event({
        "event_type": "glirn_approval_to_action",
        "approval_id": item_id,
        "decision": decision,
        "provider": "glirn_approval_to_action_workflow",
        "task_type": action_type,
        "item_id": item_id,
        "item_type": item.get("item_type"),
        "title": item.get("title"),
        "reason": reason,
        "gareth_approval_required": True,
        "client_ready": result.get("client_ready", False),
        "human_use_ready": result.get("human_use_ready", False),
        "automatic_delivery_enabled": False,
        "outreach_enabled": False,
        "external_connections_enabled": False,
        "fee_proposal_autonomous": False,
        "contracts_autonomous": False,
        "capital_execution": False,
        "autonomous_execution": False,
    })

    return {
        "status": "approval_to_action_recorded",
        "item_id": item_id,
        "action_type": action_type,
        "approval_status": result.get("approval_status"),
        "client_ready_status": result.get("client_ready_status"),
        "action_readiness_status": result.get("action_readiness_status"),
        "client_ready": result.get("client_ready", False),
        "human_use_ready": result.get("human_use_ready", False),
        "gareth_approval_required": True,
        "automatic_delivery_enabled": False,
        "outreach_enabled": False,
        "external_connections_enabled": False,
        "fee_proposal_autonomous": False,
        "contracts_autonomous": False,
        "capital_execution": False,
        "autonomous_execution": False,
    }


@app.post("/glirn/first-client-readiness/actions")
def record_glirn_first_client_readiness_action(
    request: GlirnFirstClientReadinessActionRequest,
    x_api_key: str | None = Header(default=None)
):
    require_api_key(x_api_key)

    item_id = request.item_id.strip()
    action_type = request.action_type.strip()
    reason = request.reason.strip()
    if not item_id:
        raise HTTPException(status_code=400, detail="item_id is required")
    if not action_type:
        raise HTTPException(status_code=400, detail="action_type is required")
    if not reason:
        raise HTTPException(status_code=400, detail="reason is required")
    if action_type not in {"approve", "reject", "monitor", "reset-to-review"}:
        raise HTTPException(status_code=400, detail="unsupported first-client readiness action")

    glirn_data = get_glirn_dashboard_data(pending_approvals=list_pending_approvals(), public_leads=PUBLIC_LEADS)
    gate = glirn_data.get("first_client_readiness_gate", {})
    items = []
    for key in ("readiness_checks", "first_client_ready_items", "blocked_first_client_items", "monitored_first_client_items"):
        items.extend(gate.get(key, []) or [])
    item = next(
        (
            entry
            for entry in items
            if entry.get("item_id") == item_id
        ),
        None,
    )

    if item is None:
        raise HTTPException(status_code=404, detail="first-client readiness item not found")

    result = apply_first_client_readiness_decision(item, action_type)
    decision_map = {
        "approve": "APPROVED_FOR_HUMAN_ACTION",
        "reject": "REJECTED",
        "monitor": "MONITORED",
        "reset-to-review": "RESET_TO_REVIEW",
    }
    decision = decision_map[action_type]

    record_approval_event({
        "event_type": "glirn_first_client_readiness_action",
        "approval_id": item_id,
        "decision": decision,
        "provider": "glirn_first_client_readiness_gate",
        "task_type": action_type,
        "item_id": item_id,
        "opportunity_id": item.get("opportunity_id"),
        "title": item.get("title"),
        "reason": reason,
        "gareth_approval_required": True,
        "human_action_ready": result.get("human_action_ready", False),
        "readiness_recommendation": result.get("readiness_recommendation"),
        "client_contact_enabled": False,
        "candidate_contact_enabled": False,
        "client_delivery_enabled": False,
        "fee_proposal_enabled": False,
        "contract_acceptance_enabled": False,
        "invoicing_enabled": False,
        "external_integrations_enabled": False,
        "scraping_enabled": False,
        "live_data_fetching_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    })

    return {
        "status": "first_client_readiness_action_recorded",
        "item_id": item_id,
        "action_type": action_type,
        "gareth_approval_status": result.get("gareth_approval_status"),
        "readiness_recommendation": result.get("readiness_recommendation"),
        "human_action_ready": result.get("human_action_ready", False),
        "gareth_approval_required": True,
        "client_contact_enabled": False,
        "candidate_contact_enabled": False,
        "client_delivery_enabled": False,
        "fee_proposal_enabled": False,
        "contract_acceptance_enabled": False,
        "invoicing_enabled": False,
        "external_integrations_enabled": False,
        "scraping_enabled": False,
        "live_data_fetching_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    }


@app.post("/glirn/launch-readiness/actions")
def record_glirn_launch_readiness_action(
    request: GlirnLaunchReadinessActionRequest,
    x_api_key: str | None = Header(default=None)
):
    require_api_key(x_api_key)

    action_type = request.action_type.strip()
    reason = request.reason.strip()
    if not action_type:
        raise HTTPException(status_code=400, detail="action_type is required")
    if not reason:
        raise HTTPException(status_code=400, detail="reason is required")
    if action_type not in {"approve", "reject", "monitor", "reset-to-planning"}:
        raise HTTPException(status_code=400, detail="unsupported launch readiness action")

    glirn_data = get_glirn_dashboard_data(pending_approvals=list_pending_approvals(), public_leads=PUBLIC_LEADS)
    centre = glirn_data.get("launch_readiness_command_centre", {})
    if not centre:
        raise HTTPException(status_code=404, detail="launch readiness command centre not found")

    result = apply_launch_readiness_decision(centre, action_type)
    decision_map = {
        "approve": "APPROVED_FOR_HUMAN_PLANNING",
        "reject": "REJECTED",
        "monitor": "MONITORED",
        "reset-to-planning": "RESET_TO_PLANNING",
    }
    decision = decision_map[action_type]

    record_approval_event({
        "event_type": "glirn_launch_readiness_action",
        "approval_id": "glirn-launch-readiness",
        "decision": decision,
        "provider": "glirn_launch_readiness_command_centre",
        "task_type": action_type,
        "reason": reason,
        "gareth_approval_required": True,
        "launch_readiness_grade": centre.get("launch_readiness_grade"),
        "launch_recommended_next_action": centre.get("launch_recommended_next_action"),
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
        "capital_execution": False,
        "autonomous_execution": False,
    })

    return {
        "status": "launch_readiness_action_recorded",
        "action_type": action_type,
        "gareth_approval_status": result.get("gareth_approval_status"),
        "launch_action_status": result.get("launch_action_status"),
        "launch_readiness_grade": centre.get("launch_readiness_grade"),
        "launch_recommended_next_action": centre.get("launch_recommended_next_action"),
        "gareth_approval_required": True,
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
        "capital_execution": False,
        "autonomous_execution": False,
    }


@app.post("/glirn/invoices/actions")
def record_glirn_invoice_action(
    request: GlirnInvoiceActionRequest,
    x_api_key: str | None = Header(default=None)
):
    require_api_key(x_api_key)

    action_type = request.action_type.strip()
    reason = request.reason.strip()
    invoice_number = request.invoice_number.strip() if request.invoice_number else None
    if not action_type:
        raise HTTPException(status_code=400, detail="action_type is required")
    if not reason:
        raise HTTPException(status_code=400, detail="reason is required")
    if action_type not in {"generate", "approve", "reject", "monitor", "mark-manually-sent", "mark-manually-paid"}:
        raise HTTPException(status_code=400, detail="unsupported invoice action")

    glirn_data = get_glirn_dashboard_data(pending_approvals=list_pending_approvals(), public_leads=PUBLIC_LEADS)
    engine = glirn_data.get("invoice_drafting_engine", {})
    drafts = engine.get("invoice_drafts", []) or []
    if not drafts:
        raise HTTPException(status_code=404, detail="invoice draft not found")

    if action_type != "generate" and not invoice_number:
        raise HTTPException(status_code=400, detail="invoice_number is required")
    invoice = (
        drafts[0]
        if action_type == "generate" and not invoice_number
        else next((draft for draft in drafts if draft.get("invoice_number") == invoice_number), None)
    )
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice draft not found")

    result = apply_invoice_draft_action(invoice, action_type)
    decision_map = {
        "generate": "DRAFT_GENERATED",
        "approve": "APPROVED_FOR_MANUAL_SENDING",
        "reject": "REJECTED",
        "monitor": "MONITORED",
        "mark-manually-sent": "MARKED_MANUALLY_SENT",
        "mark-manually-paid": "MARKED_MANUALLY_PAID",
    }
    decision = decision_map[action_type]

    record_approval_event({
        "event_type": "glirn_invoice_action",
        "approval_id": invoice.get("invoice_number"),
        "decision": decision,
        "provider": "glirn_invoice_drafting_engine",
        "task_type": action_type,
        "invoice_number": invoice.get("invoice_number"),
        "customer_name": invoice.get("customer_name"),
        "amount": invoice.get("amount"),
        "reason": reason,
        "gareth_approval_required": True,
        "automatic_sending_enabled": False,
        "automatic_payment_collection_enabled": False,
        "automatic_payment_confirmation_enabled": False,
        "external_payment_integration_enabled": False,
        "paypal_api_enabled": False,
        "revolut_api_enabled": False,
        "bank_integration_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    })

    return {
        "status": "invoice_action_recorded",
        "action_type": action_type,
        "invoice_number": result.get("invoice_number"),
        "approval_status": result.get("approval_status"),
        "invoice_readiness_status": result.get("invoice_readiness_status"),
        "manual_sent_status": result.get("manual_sent_status", "not_sent"),
        "manual_payment_status": result.get("manual_payment_status", "not_paid"),
        "gareth_approval_required": True,
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


@app.post("/glirn/client-terms/actions")
def record_glirn_client_terms_action(
    request: GlirnClientTermsActionRequest,
    x_api_key: str | None = Header(default=None)
):
    require_api_key(x_api_key)

    action_type = request.action_type.strip()
    reason = request.reason.strip()
    terms_id = request.terms_id.strip() if request.terms_id else None
    if not action_type:
        raise HTTPException(status_code=400, detail="action_type is required")
    if not reason:
        raise HTTPException(status_code=400, detail="reason is required")
    if action_type not in {"generate", "approve", "reject", "monitor", "mark-manually-sent", "mark-manually-agreed"}:
        raise HTTPException(status_code=400, detail="unsupported client terms action")

    glirn_data = get_glirn_dashboard_data(pending_approvals=list_pending_approvals(), public_leads=PUBLIC_LEADS)
    engine = glirn_data.get("client_terms_drafting_engine", {})
    drafts = engine.get("client_terms_drafts", []) or []
    if not drafts:
        raise HTTPException(status_code=404, detail="client terms draft not found")

    if action_type != "generate" and not terms_id:
        raise HTTPException(status_code=400, detail="terms_id is required")
    terms = (
        drafts[0]
        if action_type == "generate" and not terms_id
        else next((draft for draft in drafts if draft.get("terms_id") == terms_id), None)
    )
    if terms is None:
        raise HTTPException(status_code=404, detail="client terms draft not found")

    result = apply_client_terms_action(terms, action_type)
    decision_map = {
        "generate": "DRAFT_GENERATED",
        "approve": "APPROVED_FOR_MANUAL_USE",
        "reject": "REJECTED",
        "monitor": "MONITORED",
        "mark-manually-sent": "MARKED_MANUALLY_SENT",
        "mark-manually-agreed": "MARKED_MANUALLY_AGREED",
    }
    decision = decision_map[action_type]

    record_approval_event({
        "event_type": "glirn_client_terms_action",
        "approval_id": terms.get("terms_id"),
        "decision": decision,
        "provider": "glirn_client_terms_drafting_engine",
        "task_type": action_type,
        "terms_id": terms.get("terms_id"),
        "terms_type": terms.get("terms_type"),
        "reason": reason,
        "gareth_approval_required": True,
        "automatic_sending_enabled": False,
        "automatic_agreement_enabled": False,
        "automatic_contract_acceptance_enabled": False,
        "esignature_integration_enabled": False,
        "external_integrations_enabled": False,
        "solicitor_approved_claim": False,
        "capital_execution": False,
        "autonomous_execution": False,
    })

    return {
        "status": "client_terms_action_recorded",
        "action_type": action_type,
        "terms_id": result.get("terms_id"),
        "gareth_approval_status": result.get("gareth_approval_status"),
        "terms_readiness_status": result.get("terms_readiness_status"),
        "manual_sent_status": result.get("manual_sent_status", "not_sent"),
        "manual_agreed_status": result.get("manual_agreed_status", "not_agreed"),
        "gareth_approval_required": True,
        "automatic_sending_enabled": False,
        "automatic_agreement_enabled": False,
        "automatic_contract_acceptance_enabled": False,
        "esignature_integration_enabled": False,
        "external_integrations_enabled": False,
        "solicitor_approved_claim": False,
        "capital_execution": False,
        "autonomous_execution": False,
    }


@app.post("/glirn/candidate-consents/actions")
def record_glirn_candidate_consent_action(
    request: GlirnCandidateConsentActionRequest,
    x_api_key: str | None = Header(default=None)
):
    require_api_key(x_api_key)

    action_type = request.action_type.strip()
    reason = request.reason.strip()
    candidate_id = request.candidate_id.strip() if request.candidate_id else None
    if not action_type:
        raise HTTPException(status_code=400, detail="action_type is required")
    if not reason:
        raise HTTPException(status_code=400, detail="reason is required")
    if action_type not in {"generate", "approve", "reject", "monitor", "mark-manually-sent", "mark-manually-received", "mark-manually-withdrawn"}:
        raise HTTPException(status_code=400, detail="unsupported candidate consent action")

    glirn_data = get_glirn_dashboard_data(pending_approvals=list_pending_approvals(), public_leads=PUBLIC_LEADS)
    engine = glirn_data.get("candidate_consent_management_engine", {})
    records = engine.get("candidate_consent_records", []) or []
    if not records:
        raise HTTPException(status_code=404, detail="candidate consent record not found")

    if action_type != "generate" and not candidate_id:
        raise HTTPException(status_code=400, detail="candidate_id is required")
    consent = (
        records[0]
        if action_type == "generate" and not candidate_id
        else next((record for record in records if record.get("candidate_id") == candidate_id), None)
    )
    if consent is None:
        raise HTTPException(status_code=404, detail="candidate consent record not found")

    result = apply_candidate_consent_action(consent, action_type)
    decision_map = {
        "generate": "DRAFT_GENERATED",
        "approve": "APPROVED_FOR_MANUAL_CONSENT_PROCESS",
        "reject": "REJECTED",
        "monitor": "MONITORED",
        "mark-manually-sent": "MARKED_MANUALLY_SENT",
        "mark-manually-received": "MARKED_MANUALLY_RECEIVED",
        "mark-manually-withdrawn": "MARKED_MANUALLY_WITHDRAWN",
    }
    decision = decision_map[action_type]

    record_approval_event({
        "event_type": "glirn_candidate_consent_action",
        "approval_id": consent.get("audit_reference"),
        "decision": decision,
        "provider": "glirn_candidate_consent_management_engine",
        "task_type": action_type,
        "candidate_id": consent.get("candidate_id"),
        "reason": reason,
        "gareth_approval_required": True,
        "candidate_contact_enabled": False,
        "automated_consent_collection_enabled": False,
        "automated_consent_activation_enabled": False,
        "external_integrations_enabled": False,
        "scraping_enabled": False,
        "live_data_fetching_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    })

    return {
        "status": "candidate_consent_action_recorded",
        "action_type": action_type,
        "candidate_id": result.get("candidate_id"),
        "consent_status": result.get("consent_status"),
        "approval_status": result.get("approval_status"),
        "manual_sent_status": result.get("manual_sent_status", "not_sent"),
        "manual_received_status": result.get("manual_received_status", "not_received"),
        "manual_withdrawn_status": result.get("manual_withdrawn_status", "not_withdrawn"),
        "gareth_approval_required": True,
        "candidate_contact_enabled": False,
        "automated_consent_collection_enabled": False,
        "automated_consent_activation_enabled": False,
        "external_integrations_enabled": False,
        "scraping_enabled": False,
        "live_data_fetching_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    }


@app.post("/glirn/manual-delivery/actions")
def record_glirn_manual_delivery_action(
    request: GlirnManualDeliveryActionRequest,
    x_api_key: str | None = Header(default=None)
):
    require_api_key(x_api_key)

    action_type = request.action_type.strip()
    reason = request.reason.strip()
    delivery_id = request.delivery_id.strip() if request.delivery_id else None
    if not action_type:
        raise HTTPException(status_code=400, detail="action_type is required")
    if not reason:
        raise HTTPException(status_code=400, detail="reason is required")
    if action_type not in {"prepare", "approve", "reject", "monitor", "mark-manually-delivered"}:
        raise HTTPException(status_code=400, detail="unsupported manual delivery action")

    glirn_data = get_glirn_dashboard_data(pending_approvals=list_pending_approvals(), public_leads=PUBLIC_LEADS)
    engine = glirn_data.get("manual_delivery_control_engine", {})
    items = []
    for key in ("delivery_ready_items", "blocked_delivery_items", "pending_delivery_approvals"):
        items.extend(engine.get(key, []) or [])
    if not items:
        raise HTTPException(status_code=404, detail="manual delivery item not found")

    if action_type != "prepare" and not delivery_id:
        raise HTTPException(status_code=400, detail="delivery_id is required")
    delivery_item = (
        items[0]
        if action_type == "prepare" and not delivery_id
        else next((item for item in items if item.get("delivery_id") == delivery_id), None)
    )
    if delivery_item is None:
        raise HTTPException(status_code=404, detail="manual delivery item not found")

    result = apply_manual_delivery_action(delivery_item, action_type)
    decision_map = {
        "prepare": "PREPARED",
        "approve": "APPROVED_FOR_MANUAL_DELIVERY",
        "reject": "REJECTED",
        "monitor": "MONITORED",
        "mark-manually-delivered": "MARKED_MANUALLY_DELIVERED",
    }
    decision = decision_map[action_type]

    record_approval_event({
        "event_type": "glirn_manual_delivery_action",
        "approval_id": delivery_item.get("delivery_id"),
        "decision": decision,
        "provider": "glirn_manual_delivery_control_engine",
        "task_type": action_type,
        "delivery_id": delivery_item.get("delivery_id"),
        "source_item_id": delivery_item.get("source_item_id"),
        "reason": reason,
        "gareth_approval_required": True,
        "client_email_enabled": False,
        "external_upload_enabled": False,
        "candidate_contact_enabled": False,
        "automatic_sending_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    })

    return {
        "status": "manual_delivery_action_recorded",
        "action_type": action_type,
        "delivery_id": result.get("delivery_id"),
        "manual_delivery_status": result.get("manual_delivery_status"),
        "gareth_approval_required": True,
        "client_email_enabled": False,
        "external_upload_enabled": False,
        "candidate_contact_enabled": False,
        "automatic_sending_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    }


@app.post("/glirn/launch-compliance/actions")
def record_glirn_launch_compliance_action(
    request: GlirnLaunchComplianceActionRequest,
    x_api_key: str | None = Header(default=None)
):
    require_api_key(x_api_key)

    action_type = request.action_type.strip()
    reason = request.reason.strip()
    validation_id = request.validation_id.strip() if request.validation_id else None
    if not action_type:
        raise HTTPException(status_code=400, detail="action_type is required")
    if not reason:
        raise HTTPException(status_code=400, detail="reason is required")
    if action_type not in {"validate", "approve", "reject", "monitor", "reset-to-review"}:
        raise HTTPException(status_code=400, detail="unsupported launch compliance action")

    glirn_data = get_glirn_dashboard_data(pending_approvals=list_pending_approvals(), public_leads=PUBLIC_LEADS)
    engine = glirn_data.get("launch_compliance_validation_engine", {})
    items = []
    for key in ("compliance_ready_items", "compliance_blocked_items", "compliance_validation_checks"):
        items.extend(engine.get(key, []) or [])
    if not items:
        raise HTTPException(status_code=404, detail="launch compliance validation item not found")

    if action_type != "validate" and not validation_id:
        raise HTTPException(status_code=400, detail="validation_id is required")
    validation_item = (
        items[0]
        if action_type == "validate" and not validation_id
        else next((item for item in items if item.get("validation_id") == validation_id), None)
    )
    if validation_item is None:
        raise HTTPException(status_code=404, detail="launch compliance validation item not found")

    result = apply_launch_compliance_action(validation_item, action_type)
    decision_map = {
        "validate": "VALIDATED",
        "approve": "APPROVED_FOR_GARETH_CONSIDERATION",
        "reject": "REJECTED",
        "monitor": "MONITORED",
        "reset-to-review": "RESET_TO_REVIEW",
    }
    decision = decision_map[action_type]

    record_approval_event({
        "event_type": "glirn_launch_compliance_action",
        "approval_id": validation_item.get("validation_id"),
        "decision": decision,
        "provider": "glirn_launch_compliance_validation_engine",
        "task_type": action_type,
        "validation_id": validation_item.get("validation_id"),
        "source_item_id": validation_item.get("source_item_id"),
        "reason": reason,
        "gareth_approval_required": True,
        "legal_advice_provided": False,
        "legal_certification_claimed": False,
        "global_legal_compliance_declared": False,
        "external_integrations_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    })

    return {
        "status": "launch_compliance_action_recorded",
        "action_type": action_type,
        "validation_id": result.get("validation_id"),
        "compliance_validation_status": result.get("compliance_validation_status"),
        "compliance_recommendation": result.get("compliance_recommendation"),
        "compliance_risk_level": result.get("compliance_risk_level"),
        "gareth_approval_required": True,
        "legal_advice_provided": False,
        "legal_certification_claimed": False,
        "global_legal_compliance_declared": False,
        "external_integrations_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    }


@app.post("/glirn/dry-run/actions")
def record_glirn_dry_run_action(
    request: GlirnDryRunActionRequest,
    x_api_key: str | None = Header(default=None)
):
    require_api_key(x_api_key)

    action_type = request.action_type.strip()
    reason = request.reason.strip()
    if not action_type:
        raise HTTPException(status_code=400, detail="action_type is required")
    if not reason:
        raise HTTPException(status_code=400, detail="reason is required")
    if action_type not in {"run", "approve", "reject", "monitor", "reset"}:
        raise HTTPException(status_code=400, detail="unsupported dry run action")

    glirn_data = get_glirn_dashboard_data(pending_approvals=list_pending_approvals(), public_leads=PUBLIC_LEADS)
    dry_run = glirn_data.get("first_client_dry_run", {})
    if not dry_run:
        raise HTTPException(status_code=404, detail="first client dry run not found")

    result = apply_first_client_dry_run_action(dry_run, action_type)
    decision_map = {
        "run": "RUN_COMPLETED",
        "approve": "APPROVED_FOR_HUMAN_REVIEW",
        "reject": "REJECTED",
        "monitor": "MONITORED",
        "reset": "RESET",
    }
    decision = decision_map[action_type]

    record_approval_event({
        "event_type": "glirn_first_client_dry_run_action",
        "approval_id": result.get("gareth_approval_package", {}).get("package_id"),
        "decision": decision,
        "provider": "glirn_first_client_dry_run",
        "task_type": action_type,
        "dry_run_status": result.get("dry_run_status"),
        "dry_run_readiness_score": result.get("dry_run_readiness_score"),
        "reason": reason,
        "gareth_approval_required": True,
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
    })

    return {
        "status": "dry_run_action_recorded",
        "action_type": action_type,
        "dry_run_status": result.get("dry_run_status"),
        "dry_run_readiness_score": result.get("dry_run_readiness_score"),
        "approval_readiness_status": result.get("approval_readiness_status"),
        "dry_run_blockers": result.get("dry_run_blockers", []),
        "dry_run_warnings": result.get("dry_run_warnings", []),
        "gareth_approval_required": True,
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


@app.post("/glirn/autonomous-operations/actions")
def record_glirn_autonomous_operations_action(
    request: GlirnAutonomousOperationsActionRequest,
    x_api_key: str | None = Header(default=None)
):
    require_api_key(x_api_key)

    action_type = request.action_type.strip()
    reason = request.reason.strip()
    if not action_type:
        raise HTTPException(status_code=400, detail="action_type is required")
    if not reason:
        raise HTTPException(status_code=400, detail="reason is required")
    if action_type not in {
        "run-cycle",
        "approve-final-package",
        "reject-final-package",
        "monitor-final-package",
        "reset-cycle",
    }:
        raise HTTPException(status_code=400, detail="unsupported autonomous operations action")

    glirn_data = get_glirn_dashboard_data(pending_approvals=list_pending_approvals(), public_leads=PUBLIC_LEADS)
    orchestrator = glirn_data.get("autonomous_internal_operations_orchestrator", {})
    if not orchestrator:
        raise HTTPException(status_code=404, detail="autonomous internal operations orchestrator not found")

    result = apply_autonomous_internal_operations_action(orchestrator, action_type)
    decision_map = {
        "run-cycle": "CYCLE_RUN_COMPLETED",
        "approve-final-package": "FINAL_PACKAGE_APPROVED",
        "reject-final-package": "FINAL_PACKAGE_REJECTED",
        "monitor-final-package": "FINAL_PACKAGE_MONITORED",
        "reset-cycle": "CYCLE_RESET",
    }
    decision = decision_map[action_type]
    package = (result.get("final_gareth_approval_packages") or [{}])[0]

    record_approval_event({
        "event_type": "glirn_autonomous_internal_operations_action",
        "approval_id": package.get("package_id"),
        "decision": decision,
        "provider": "glirn_autonomous_internal_operations_orchestrator",
        "task_type": action_type,
        "autonomous_cycle_status": result.get("autonomous_cycle_status"),
        "reason": reason,
        "gareth_final_decision_required": True,
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
    })

    return {
        "status": "autonomous_operations_action_recorded",
        "action_type": action_type,
        "autonomous_cycle_status": result.get("autonomous_cycle_status"),
        "final_gareth_approval_packages": result.get("final_gareth_approval_packages", []),
        "autonomous_recommendation_queue": result.get("autonomous_recommendation_queue", []),
        "autonomous_blockers": result.get("autonomous_blockers", []),
        "autonomous_warnings": result.get("autonomous_warnings", []),
        "gareth_final_decision_required": True,
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


@app.post("/glirn/public-leads/intake")
def intake_glirn_public_lead(request: GlirnPublicLeadIntakeRequest):
    lead = request.model_dump()
    enforce_public_lead_rate_limit(lead["email"])
    lead["lead_id"] = f"public-lead-{len(PUBLIC_LEADS) + 1:03d}"
    lead["received_at"] = datetime.now(timezone.utc).isoformat()
    record = build_public_lead_record(lead, len(PUBLIC_LEADS) + 1)
    revenue_package = build_revenue_approval_package_for_lead(record)
    response_package = build_enquiry_response_package(lead, record, revenue_package)
    PUBLIC_LEADS.append(lead)
    upsert_record("website_enquiry", lead["lead_id"], lead)
    upsert_record("lead_routing_result", record.get("lead_id"), record)
    upsert_record("revenue_approval_package", revenue_package.get("package_id"), revenue_package)
    upsert_record(
        "acknowledgement",
        response_package["acknowledgement"]["acknowledgement_id"],
        response_package["acknowledgement"],
    )
    if response_package.get("faq_response"):
        upsert_record(
            "faq_response",
            response_package["faq_response"]["faq_response_id"],
            response_package["faq_response"],
        )
    upsert_record(
        "draft_response",
        response_package["draft_response"]["draft_response_id"],
        response_package["draft_response"],
    )
    upsert_record(
        "enquiry_response_package",
        response_package["response_package_id"],
        response_package,
    )
    PERSISTED_RESPONSE_PACKAGES[:] = list_records("enquiry_response_package")
    notification = attempt_enquiry_notification(lead)
    persist_safe_action(
        "public_lead_received",
        record.get("lead_id"),
        lead_type=record.get("lead_type"),
        lead_route=record.get("lead_route"),
        gareth_final_approval_required=True,
        external_action_enabled=False,
    )
    persist_safe_action(
        "enquiry_acknowledgement",
        response_package["acknowledgement"]["acknowledgement_id"],
        lead_id=record.get("lead_id"),
        acknowledgement_status=response_package["acknowledgement"]["acknowledgement_status"],
        email_sent=response_package["acknowledgement"]["email_sent"],
        substantive_response_sent=False,
    )
    if response_package.get("faq_response"):
        persist_safe_action(
            "safe_faq_response",
            response_package["faq_response"]["faq_response_id"],
            lead_id=record.get("lead_id"),
            topic=response_package["faq_response"]["topic"],
            faq_response_status=response_package["faq_response"]["faq_response_status"],
            predefined_template_only=True,
        )

    record_approval_event({
        "event_type": "glirn_public_lead_intake",
        "approval_id": record.get("lead_id"),
        "decision": "PUBLIC_LEAD_RECEIVED",
        "provider": "glirn_website_lead_intake_engine",
        "task_type": "public_lead_intake",
        "lead_id": record.get("lead_id"),
        "prospect_type": record.get("prospect_type"),
        "lead_revenue_potential": record.get("lead_revenue_potential"),
        "revenue_approval_package_id": revenue_package.get("package_id"),
        "estimated_revenue_opportunity": revenue_package.get("estimated_revenue_opportunity"),
        "gareth_final_approval_required": True,
        "automatic_email_enabled": False,
        "automatic_linkedin_messaging_enabled": False,
        "automatic_introductions_enabled": False,
        "candidate_information_sharing_enabled": False,
        "client_contact_enabled": False,
        "candidate_contact_enabled": False,
        "invoice_issuing_enabled": False,
        "payment_collection_enabled": False,
        "external_integrations_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    })

    return {
        "status": "public_lead_recorded",
        "lead_id": record.get("lead_id"),
        "prospect_type": record.get("prospect_type"),
        "lead_type": record.get("lead_type"),
        "lead_route": record.get("lead_route"),
        "lead_qualification_status": record.get("lead_qualification_status"),
        "lead_revenue_potential": record.get("lead_revenue_potential"),
        "lead_compliance_status": record.get("lead_compliance_status"),
        "lead_approval_package_status": record.get("lead_approval_package_status"),
        "revenue_approval_package": revenue_package,
        "estimated_revenue_opportunity": revenue_package.get("estimated_revenue_opportunity"),
        "gareth_approval_status": revenue_package.get("gareth_approval_status"),
        "recommended_action": record.get("recommended_action"),
        "acknowledgement": response_package.get("acknowledgement"),
        "faq_response": response_package.get("faq_response"),
        "draft_response": response_package.get("draft_response"),
        "response_package_id": response_package.get("response_package_id"),
        "notification": notification,
        "notification_delivery_status": notification.get("delivery_status"),
        "automatic_acknowledgement_enabled": True,
        "business_email_notification_enabled": True,
        "notification_informational_only": True,
        "gareth_final_approval_required": True,
        "automatic_acceptance_enabled": False,
        "automatic_payment_enabled": False,
        "automatic_candidate_outreach_enabled": False,
        "automatic_email_enabled": False,
        "automatic_linkedin_messaging_enabled": False,
        "automatic_introductions_enabled": False,
        "candidate_information_sharing_enabled": False,
        "client_contact_enabled": False,
        "candidate_contact_enabled": False,
        "invoice_issuing_enabled": False,
        "payment_collection_enabled": False,
        "automatic_brief_generation_enabled": False,
        "automatic_search_activity_enabled": False,
        "automatic_delivery_enabled": False,
        "external_integrations_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    }


@app.post("/glirn/enquiry-notifications/{notification_id}/resend")
def resend_glirn_enquiry_notification(
    notification_id: str,
    request: GlirnEnquiryNotificationResendRequest,
    x_api_key: str | None = Header(default=None),
):
    require_api_key(x_api_key)
    if not request.reason.strip():
        raise HTTPException(status_code=400, detail="reason is required")

    previous = next(
        (item for item in PERSISTED_ENQUIRY_NOTIFICATIONS if item.get("notification_id") == notification_id),
        None,
    )
    if previous is None:
        raise HTTPException(status_code=404, detail="enquiry notification not found")
    enquiry = next(
        (item for item in PUBLIC_LEADS if item.get("lead_id") == previous.get("related_enquiry_id")),
        None,
    )
    if enquiry is None:
        raise HTTPException(status_code=404, detail="related enquiry not found")

    notification = attempt_enquiry_notification(enquiry, previous_record=previous)
    persist_safe_action(
        "enquiry_notification_manual_resend",
        notification_id,
        related_enquiry_id=notification["related_enquiry_id"],
        delivery_status=notification["delivery_status"],
        retry_attempts=notification["retry_attempts"],
        reason=request.reason.strip(),
        informational_only=True,
        sensitive_enquiry_content_logged=False,
        automatic_acceptance_enabled=False,
        automatic_payment_enabled=False,
        automatic_brief_generation_enabled=False,
        automatic_candidate_outreach_enabled=False,
        automatic_search_activity_enabled=False,
        automatic_delivery_enabled=False,
        external_integrations_enabled=False,
    )
    return {
        "status": "enquiry_notification_resend_recorded",
        "notification": notification,
        "gareth_final_approval_required": True,
        "informational_only": True,
        "automatic_acceptance_enabled": False,
        "automatic_payment_enabled": False,
        "automatic_brief_generation_enabled": False,
        "automatic_candidate_outreach_enabled": False,
        "automatic_search_activity_enabled": False,
        "automatic_delivery_enabled": False,
        "external_integrations_enabled": False,
    }


@app.post("/glirn/public-leads/actions")
def record_glirn_public_lead_action(
    request: GlirnPublicLeadActionRequest,
    x_api_key: str | None = Header(default=None)
):
    require_api_key(x_api_key)

    action_type = request.action_type.strip()
    reason = request.reason.strip()
    lead_id = request.lead_id.strip() if request.lead_id else None
    if not action_type:
        raise HTTPException(status_code=400, detail="action_type is required")
    if not reason:
        raise HTTPException(status_code=400, detail="reason is required")
    if action_type not in {"approve", "reject", "monitor", "convert-to-approval-package"}:
        raise HTTPException(status_code=400, detail="unsupported public lead action")

    glirn_data = get_glirn_dashboard_data(
        pending_approvals=list_pending_approvals(),
        public_leads=PUBLIC_LEADS,
    )
    leads = glirn_data.get("website_lead_intake_engine", {}).get("public_leads", []) or []
    if not leads:
        raise HTTPException(status_code=404, detail="public lead not found")
    if action_type != "convert-to-approval-package" and not lead_id:
        raise HTTPException(status_code=400, detail="lead_id is required")
    lead = (
        leads[-1]
        if action_type == "convert-to-approval-package" and not lead_id
        else next((item for item in leads if item.get("lead_id") == lead_id), None)
    )
    if lead is None:
        raise HTTPException(status_code=404, detail="public lead not found")

    result = apply_public_lead_action(lead, action_type)
    upsert_record("lead_routing_result", result.get("lead_id"), result)
    persist_safe_action(
        "public_lead_action",
        result.get("lead_id"),
        action_type=action_type,
        gareth_final_approval_required=True,
        external_action_enabled=False,
    )
    decision_map = {
        "approve": "PUBLIC_LEAD_APPROVED",
        "reject": "PUBLIC_LEAD_REJECTED",
        "monitor": "PUBLIC_LEAD_MONITORED",
        "convert-to-approval-package": "PUBLIC_LEAD_CONVERTED_TO_APPROVAL_PACKAGE",
    }
    decision = decision_map[action_type]

    record_approval_event({
        "event_type": "glirn_public_lead_action",
        "approval_id": lead.get("lead_id"),
        "decision": decision,
        "provider": "glirn_website_lead_intake_engine",
        "task_type": action_type,
        "lead_id": lead.get("lead_id"),
        "reason": reason,
        "gareth_final_approval_required": True,
        "automatic_email_enabled": False,
        "client_contact_enabled": False,
        "candidate_contact_enabled": False,
        "invoice_issuing_enabled": False,
        "payment_collection_enabled": False,
        "external_integrations_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    })

    return {
        "status": "public_lead_action_recorded",
        "action_type": action_type,
        "lead_id": result.get("lead_id"),
        "lead_approval_package_status": result.get("lead_approval_package_status"),
        "gareth_final_approval_required": True,
        "automatic_email_enabled": False,
        "client_contact_enabled": False,
        "candidate_contact_enabled": False,
        "invoice_issuing_enabled": False,
        "payment_collection_enabled": False,
        "external_integrations_enabled": False,
        "capital_execution": False,
        "autonomous_execution": False,
    }


@app.post("/glirn/final-approval/actions")
def record_glirn_final_approval_action(
    request: GlirnFinalApprovalActionRequest,
    x_api_key: str | None = Header(default=None)
):
    require_api_key(x_api_key)

    action_type = request.action_type.strip()
    reason = request.reason.strip()
    final_approval_id = request.final_approval_id.strip() if request.final_approval_id else None
    if not action_type:
        raise HTTPException(status_code=400, detail="action_type is required")
    if not reason:
        raise HTTPException(status_code=400, detail="reason is required")
    if action_type not in {"approve", "reject", "needs_more_information"}:
        raise HTTPException(status_code=400, detail="unsupported final approval action")

    glirn_data = get_glirn_dashboard_data(
        pending_approvals=list_pending_approvals(),
        public_leads=PUBLIC_LEADS,
    )
    approval_objects = glirn_data.get("final_approval_command_centre", {}).get("final_approval_objects", []) or []
    if not approval_objects:
        raise HTTPException(status_code=404, detail="final approval object not found")
    approval_object = (
        approval_objects[-1]
        if not final_approval_id
        else next((item for item in approval_objects if item.get("final_approval_id") == final_approval_id), None)
    )
    if approval_object is None:
        raise HTTPException(status_code=404, detail="final approval object not found")

    result = apply_final_approval_action(approval_object, action_type)
    FINAL_APPROVAL_LOCAL_STATUS[result.get("final_approval_id")] = result.get("final_approval_status")
    set_state("final_approval_statuses", FINAL_APPROVAL_LOCAL_STATUS)
    persist_safe_action(
        "final_approval_action",
        result.get("final_approval_id"),
        action_type=action_type,
        final_approval_status=result.get("final_approval_status"),
        gareth_final_decision_required=True,
        external_action_enabled=False,
    )
    decision_map = {
        "approve": "FINAL_APPROVAL_APPROVED_BY_GARETH",
        "reject": "FINAL_APPROVAL_REJECTED_BY_GARETH",
        "needs_more_information": "FINAL_APPROVAL_NEEDS_MORE_INFORMATION",
    }

    record_approval_event({
        "event_type": "glirn_final_approval_action",
        "approval_id": result.get("final_approval_id"),
        "decision": decision_map[action_type],
        "provider": "glirn_final_approval_command_centre",
        "task_type": action_type,
        "reason": reason,
        "suggested_service": result.get("suggested_service"),
        "estimated_fee": result.get("estimated_fee"),
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
    })

    return {
        "status": "final_approval_action_recorded",
        "action_type": action_type,
        "final_approval_id": result.get("final_approval_id"),
        "final_approval_status": result.get("final_approval_status"),
        "suggested_service": result.get("suggested_service"),
        "estimated_fee": result.get("estimated_fee"),
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


@app.post("/glirn/client-contact/actions")
def record_glirn_client_contact_action(
    request: GlirnClientContactActionRequest,
    x_api_key: str | None = Header(default=None)
):
    require_api_key(x_api_key)

    action_type = request.action_type.strip()
    reason = request.reason.strip()
    final_approval_id = request.final_approval_id.strip() if request.final_approval_id else None
    if not action_type:
        raise HTTPException(status_code=400, detail="action_type is required")
    if not reason:
        raise HTTPException(status_code=400, detail="reason is required")
    if action_type != "mark_approved_contact_ready":
        raise HTTPException(status_code=400, detail="unsupported client contact action")

    glirn_data = get_glirn_dashboard_data(
        pending_approvals=list_pending_approvals(),
        public_leads=PUBLIC_LEADS,
    )
    approval_objects = glirn_data.get("final_approval_command_centre", {}).get("final_approval_objects", []) or []
    if not approval_objects:
        raise HTTPException(status_code=404, detail="final approval object not found")
    approval_object = (
        approval_objects[-1]
        if not final_approval_id
        else next((item for item in approval_objects if item.get("final_approval_id") == final_approval_id), None)
    )
    if approval_object is None:
        raise HTTPException(status_code=404, detail="final approval object not found")

    stored_status = FINAL_APPROVAL_LOCAL_STATUS.get(approval_object.get("final_approval_id"))
    if stored_status:
        approval_object = dict(approval_object)
        approval_object["final_approval_status"] = stored_status
    contact_readiness = build_client_contact_readiness_object(approval_object)
    if contact_readiness.get("final_approval_status") != "approved_by_gareth":
        raise HTTPException(status_code=403, detail="final approval must be approved_by_gareth before client contact can be marked ready")

    result = apply_client_contact_action(contact_readiness, action_type)
    record_approval_event({
        "event_type": "glirn_client_contact_action",
        "approval_id": result.get("contact_readiness_id"),
        "decision": "CLIENT_CONTACT_LOGGED_LOCAL_ONLY",
        "provider": "glirn_approved_client_contact_engine",
        "task_type": action_type,
        "reason": reason,
        "final_approval_id": result.get("final_approval_id"),
        "suggested_service": result.get("suggested_service"),
        "real_email_sent": False,
        "client_contact_executed": False,
        "gmail_smtp_connected": False,
        "external_integrations_enabled": False,
        "local_log_only": True,
        "capital_execution": False,
        "autonomous_execution": False,
    })

    return {
        "status": "client_contact_action_recorded",
        "action_type": action_type,
        "contact_readiness_id": result.get("contact_readiness_id"),
        "final_approval_id": result.get("final_approval_id"),
        "contact_status": result.get("contact_status"),
        "lead_name": result.get("lead_name"),
        "lead_email": result.get("lead_email"),
        "suggested_service": result.get("suggested_service"),
        "approval_required": True,
        "real_email_sent": False,
        "client_contact_executed": False,
        "gmail_smtp_connected": False,
        "external_integrations_enabled": False,
        "local_log_only": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


@app.post("/glirn/email-draft-export/actions")
def record_glirn_email_draft_export_action(
    request: GlirnEmailDraftExportActionRequest,
    x_api_key: str | None = Header(default=None)
):
    require_api_key(x_api_key)

    action_type = request.action_type.strip()
    reason = request.reason.strip()
    final_approval_id = request.final_approval_id.strip() if request.final_approval_id else None
    if not action_type:
        raise HTTPException(status_code=400, detail="action_type is required")
    if not reason:
        raise HTTPException(status_code=400, detail="reason is required")
    if action_type != "export_approved_email_draft":
        raise HTTPException(status_code=400, detail="unsupported email draft export action")

    glirn_data = get_glirn_dashboard_data(
        pending_approvals=list_pending_approvals(),
        public_leads=PUBLIC_LEADS,
    )
    approval_objects = glirn_data.get("final_approval_command_centre", {}).get("final_approval_objects", []) or []
    if not approval_objects:
        raise HTTPException(status_code=404, detail="final approval object not found")
    approval_object = (
        approval_objects[-1]
        if not final_approval_id
        else next((item for item in approval_objects if item.get("final_approval_id") == final_approval_id), None)
    )
    if approval_object is None:
        raise HTTPException(status_code=404, detail="final approval object not found")

    stored_status = FINAL_APPROVAL_LOCAL_STATUS.get(approval_object.get("final_approval_id"))
    if stored_status:
        approval_object = dict(approval_object)
        approval_object["final_approval_status"] = stored_status
    email_export = build_email_draft_export_object(approval_object)
    if email_export.get("final_approval_status") != "approved_by_gareth":
        raise HTTPException(status_code=403, detail="final approval must be approved_by_gareth before email draft export")

    file_path = approved_local_export_path(
        GLIRN_EMAIL_DRAFTS_DIR,
        email_export.get("email_draft_export_id", "glirn-email-draft"),
    )
    fee_summary = email_export.get("fee_proposal_summary", {}) or {}
    content = "\n".join([
        f"To: {safe_export_text(email_export.get('to_email', ''))}",
        f"Lead name: {safe_export_text(email_export.get('lead_name', ''))}",
        f"Subject: {safe_export_text(email_export.get('subject', ''))}",
        "",
        safe_export_text(email_export.get("approved_response_body", "")),
        "",
        "Fee proposal summary:",
        f"Suggested service: {safe_export_text(fee_summary.get('suggested_service', email_export.get('suggested_glirn_service', '')))}",
        f"Estimated fee: {safe_export_text(fee_summary.get('estimated_fee', 0))}",
        f"Fee basis: {safe_export_text(fee_summary.get('fee_basis', ''))}",
        "",
        "Local-only note: No email has been sent. Gareth must manually review and send.",
    ])
    with open(file_path, "w", encoding="utf-8") as draft_file:
        draft_file.write(content)

    result = apply_email_draft_export_action(email_export, action_type, file_path=file_path)
    upsert_record("email_draft_export", result.get("email_draft_export_id"), result)
    PERSISTED_EXPORT_METADATA["email_draft"] = list_records("email_draft_export")
    persist_safe_action(
        "email_draft_export",
        result.get("email_draft_export_id"),
        final_approval_id=result.get("final_approval_id"),
        export_status=result.get("export_status"),
        email_sent=False,
        external_integrations_enabled=False,
    )
    record_approval_event({
        "event_type": "glirn_email_draft_export_action",
        "approval_id": result.get("email_draft_export_id"),
        "decision": "EMAIL_DRAFT_EXPORTED_LOCAL_ONLY",
        "provider": "glirn_email_draft_export_engine",
        "task_type": action_type,
        "reason": reason,
        "final_approval_id": result.get("final_approval_id"),
        "local_file_path": result.get("local_file_path"),
        "email_sent": False,
        "gmail_smtp_connected": False,
        "external_integrations_enabled": False,
        "local_file_only": True,
        "capital_execution": False,
        "autonomous_execution": False,
    })

    return {
        "status": "email_draft_export_action_recorded",
        "action_type": action_type,
        "email_draft_export_id": result.get("email_draft_export_id"),
        "final_approval_id": result.get("final_approval_id"),
        "to_email": result.get("to_email"),
        "lead_name": result.get("lead_name"),
        "subject": result.get("subject"),
        "suggested_glirn_service": result.get("suggested_glirn_service"),
        "export_status": result.get("export_status"),
        "local_file_path": result.get("local_file_path"),
        "local_only_note": result.get("local_only_note"),
        "email_sent": False,
        "gmail_smtp_connected": False,
        "external_integrations_enabled": False,
        "local_file_only": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


@app.post("/glirn/invoice-draft-export/actions")
def record_glirn_invoice_draft_export_action(
    request: GlirnInvoiceDraftExportActionRequest,
    x_api_key: str | None = Header(default=None)
):
    require_api_key(x_api_key)

    action_type = request.action_type.strip()
    reason = request.reason.strip()
    final_approval_id = request.final_approval_id.strip() if request.final_approval_id else None
    if not action_type:
        raise HTTPException(status_code=400, detail="action_type is required")
    if not reason:
        raise HTTPException(status_code=400, detail="reason is required")
    if action_type != "export_approved_invoice_draft":
        raise HTTPException(status_code=400, detail="unsupported invoice draft export action")

    glirn_data = get_glirn_dashboard_data(
        pending_approvals=list_pending_approvals(),
        public_leads=PUBLIC_LEADS,
    )
    approval_objects = glirn_data.get("final_approval_command_centre", {}).get("final_approval_objects", []) or []
    if not approval_objects:
        raise HTTPException(status_code=404, detail="final approval object not found")
    approval_object = (
        approval_objects[-1]
        if not final_approval_id
        else next((item for item in approval_objects if item.get("final_approval_id") == final_approval_id), None)
    )
    if approval_object is None:
        raise HTTPException(status_code=404, detail="final approval object not found")

    stored_status = FINAL_APPROVAL_LOCAL_STATUS.get(approval_object.get("final_approval_id"))
    if stored_status:
        approval_object = dict(approval_object)
        approval_object["final_approval_status"] = stored_status
    invoice_export = build_invoice_draft_export_object(approval_object)
    if invoice_export.get("final_approval_status") != "approved_by_gareth":
        raise HTTPException(status_code=403, detail="final approval must be approved_by_gareth before invoice draft export")

    file_path = approved_local_export_path(
        GLIRN_INVOICE_DRAFTS_DIR,
        invoice_export.get("invoice_draft_export_id", "glirn-invoice-draft"),
    )
    content = "\n".join([
        f"Client name: {safe_export_text(invoice_export.get('client_name', ''))}",
        f"Client email: {safe_export_text(invoice_export.get('client_email', ''))}",
        f"Suggested GLIRN service: {safe_export_text(invoice_export.get('suggested_glirn_service', ''))}",
        f"Estimated fee: {safe_export_text(invoice_export.get('estimated_fee', 0))}",
        f"Fee basis: {safe_export_text(invoice_export.get('fee_basis', ''))}",
        "",
        "Scope summary:",
        safe_export_text(invoice_export.get("scope_summary", "")),
        "",
        "Payment/sign-off note:",
        safe_export_text(invoice_export.get("payment_signoff_note", "")),
        "",
        "Local-only note: No invoice or payment request has been sent. Gareth must manually review and send.",
    ])
    with open(file_path, "w", encoding="utf-8") as draft_file:
        draft_file.write(content)

    result = apply_invoice_draft_export_action(invoice_export, action_type, file_path=file_path)
    upsert_record("invoice_draft_export", result.get("invoice_draft_export_id"), result)
    PERSISTED_EXPORT_METADATA["invoice_draft"] = list_records("invoice_draft_export")
    persist_safe_action(
        "invoice_draft_export",
        result.get("invoice_draft_export_id"),
        final_approval_id=result.get("final_approval_id"),
        invoice_status=result.get("invoice_status"),
        invoice_sent=False,
        payment_request_sent=False,
        money_movement_enabled=False,
    )
    record_approval_event({
        "event_type": "glirn_invoice_draft_export_action",
        "approval_id": result.get("invoice_draft_export_id"),
        "decision": "INVOICE_DRAFT_EXPORTED_LOCAL_ONLY",
        "provider": "glirn_invoice_draft_export_engine",
        "task_type": action_type,
        "reason": reason,
        "final_approval_id": result.get("final_approval_id"),
        "local_file_path": result.get("local_file_path"),
        "invoice_sent": False,
        "payment_request_sent": False,
        "money_movement_enabled": False,
        "external_integrations_enabled": False,
        "local_file_only": True,
        "capital_execution": False,
        "autonomous_execution": False,
    })

    return {
        "status": "invoice_draft_export_action_recorded",
        "action_type": action_type,
        "invoice_draft_export_id": result.get("invoice_draft_export_id"),
        "final_approval_id": result.get("final_approval_id"),
        "client_name": result.get("client_name"),
        "client_email": result.get("client_email"),
        "suggested_glirn_service": result.get("suggested_glirn_service"),
        "estimated_fee": result.get("estimated_fee"),
        "fee_basis": result.get("fee_basis"),
        "invoice_status": result.get("invoice_status"),
        "local_file_path": result.get("local_file_path"),
        "local_only_note": result.get("local_only_note"),
        "invoice_sent": False,
        "payment_request_sent": False,
        "money_movement_enabled": False,
        "external_integrations_enabled": False,
        "local_file_only": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


@app.post("/glirn/deal-pack-export/actions")
def record_glirn_deal_pack_export_action(
    request: GlirnDealPackExportActionRequest,
    x_api_key: str | None = Header(default=None)
):
    require_api_key(x_api_key)

    action_type = request.action_type.strip()
    reason = request.reason.strip()
    final_approval_id = request.final_approval_id.strip() if request.final_approval_id else None
    if not action_type:
        raise HTTPException(status_code=400, detail="action_type is required")
    if not reason:
        raise HTTPException(status_code=400, detail="reason is required")
    if action_type != "export_approved_deal_pack":
        raise HTTPException(status_code=400, detail="unsupported deal pack export action")

    glirn_data = get_glirn_dashboard_data(
        pending_approvals=list_pending_approvals(),
        public_leads=PUBLIC_LEADS,
    )
    approval_objects = glirn_data.get("final_approval_command_centre", {}).get("final_approval_objects", []) or []
    if not approval_objects:
        raise HTTPException(status_code=404, detail="final approval object not found")
    approval_object = (
        approval_objects[-1]
        if not final_approval_id
        else next((item for item in approval_objects if item.get("final_approval_id") == final_approval_id), None)
    )
    if approval_object is None:
        raise HTTPException(status_code=404, detail="final approval object not found")

    stored_status = FINAL_APPROVAL_LOCAL_STATUS.get(approval_object.get("final_approval_id"))
    if stored_status:
        approval_object = dict(approval_object)
        approval_object["final_approval_status"] = stored_status
    deal_pack = build_deal_pack_export_object(approval_object)
    if deal_pack.get("final_approval_status") != "approved_by_gareth":
        raise HTTPException(status_code=403, detail="final approval must be approved_by_gareth before deal pack export")

    file_path = approved_local_export_path(
        GLIRN_DEAL_PACKS_DIR,
        deal_pack.get("deal_pack_export_id", "glirn-deal-pack"),
    )
    response_draft = deal_pack.get("approved_client_response_draft", {}) or {}
    fee_pack = deal_pack.get("fee_proposal_pack", {}) or {}
    invoice_summary = deal_pack.get("invoice_draft_summary", {}) or {}
    content = "\n".join([
        "GLIRN Complete Deal Pack",
        "",
        f"Client name: {safe_export_text(deal_pack.get('client_name', ''))}",
        f"Client email: {safe_export_text(deal_pack.get('client_email', ''))}",
        f"Lead name: {safe_export_text(deal_pack.get('lead_name', ''))}",
        f"Lead route: {safe_export_text(deal_pack.get('lead_route', ''))}",
        f"Suggested GLIRN service: {safe_export_text(deal_pack.get('suggested_glirn_service', ''))}",
        f"Estimated fee: {safe_export_text(deal_pack.get('estimated_fee', 0))}",
        f"Fee basis: {safe_export_text(deal_pack.get('fee_basis', ''))}",
        f"Dave recommendation: {safe_export_text(deal_pack.get('dave_recommendation', ''))}",
        "",
        "Approved client response draft:",
        f"Subject: {safe_export_text(response_draft.get('subject', ''))}",
        safe_export_text(response_draft.get("draft_body", "")),
        "",
        "Fee proposal pack:",
        safe_export_text(fee_pack.get("client_facing_proposal_draft", "")),
        "",
        "Invoice draft summary:",
        f"Client name: {safe_export_text(invoice_summary.get('client_name', ''))}",
        f"Client email: {safe_export_text(invoice_summary.get('client_email', ''))}",
        f"Suggested service: {safe_export_text(invoice_summary.get('suggested_glirn_service', ''))}",
        f"Estimated fee: {safe_export_text(invoice_summary.get('estimated_fee', 0))}",
        f"Fee basis: {safe_export_text(invoice_summary.get('fee_basis', ''))}",
        f"Scope summary: {safe_export_text(invoice_summary.get('scope_summary', ''))}",
        f"Payment/sign-off note: {safe_export_text(invoice_summary.get('payment_signoff_note', ''))}",
        "",
        f"Safety statement: {safe_export_text(deal_pack.get('safety_statement', ''))}",
        f"Local-only note: {safe_export_text(deal_pack.get('local_only_note', ''))}",
    ])
    with open(file_path, "w", encoding="utf-8") as deal_pack_file:
        deal_pack_file.write(content)

    result = apply_deal_pack_export_action(deal_pack, action_type, file_path=file_path)
    upsert_record("deal_pack_export", result.get("deal_pack_export_id"), result)
    PERSISTED_EXPORT_METADATA["deal_pack"] = list_records("deal_pack_export")
    persist_safe_action(
        "deal_pack_export",
        result.get("deal_pack_export_id"),
        final_approval_id=result.get("final_approval_id"),
        deal_pack_status=result.get("deal_pack_status"),
        client_contact_executed=False,
        invoice_sent=False,
        payment_request_sent=False,
        money_movement_enabled=False,
    )
    record_approval_event({
        "event_type": "glirn_deal_pack_export_action",
        "approval_id": result.get("deal_pack_export_id"),
        "decision": "DEAL_PACK_EXPORTED_LOCAL_ONLY",
        "provider": "glirn_deal_pack_export_engine",
        "task_type": action_type,
        "reason": reason,
        "final_approval_id": result.get("final_approval_id"),
        "local_file_path": result.get("local_file_path"),
        "client_contact_executed": False,
        "invoice_sent": False,
        "payment_request_sent": False,
        "money_movement_enabled": False,
        "external_integrations_enabled": False,
        "local_file_only": True,
        "capital_execution": False,
        "autonomous_execution": False,
    })

    return {
        "status": "deal_pack_export_action_recorded",
        "action_type": action_type,
        "deal_pack_export_id": result.get("deal_pack_export_id"),
        "final_approval_id": result.get("final_approval_id"),
        "client_name": result.get("client_name"),
        "client_email": result.get("client_email"),
        "suggested_glirn_service": result.get("suggested_glirn_service"),
        "estimated_fee": result.get("estimated_fee"),
        "fee_basis": result.get("fee_basis"),
        "deal_pack_status": result.get("deal_pack_status"),
        "local_file_path": result.get("local_file_path"),
        "local_only_note": result.get("local_only_note"),
        "client_contact_executed": False,
        "invoice_sent": False,
        "payment_request_sent": False,
        "money_movement_enabled": False,
        "external_integrations_enabled": False,
        "local_file_only": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


def build_local_revenue_ledger():
    glirn_data = get_glirn_dashboard_data(
        pending_approvals=list_pending_approvals(),
        public_leads=PUBLIC_LEADS,
    )
    final_approval_centre = glirn_data.get("final_approval_command_centre", {}) or {}
    final_objects = []
    for item in final_approval_centre.get("final_approval_objects", []) or []:
        copied = dict(item)
        stored_status = FINAL_APPROVAL_LOCAL_STATUS.get(copied.get("final_approval_id"))
        if stored_status:
            copied["final_approval_status"] = stored_status
        final_objects.append(copied)
    final_approval_centre = dict(final_approval_centre)
    final_approval_centre["final_approval_objects"] = final_objects

    email_export_engine = export_engine_with_persisted_records(
        glirn_data.get("email_draft_export_engine", {}) or {}, "email_draft"
    )
    invoice_export_engine = export_engine_with_persisted_records(
        glirn_data.get("invoice_draft_export_engine", {}) or {}, "invoice_draft"
    )
    deal_pack_engine = export_engine_with_persisted_records(
        glirn_data.get("deal_pack_export_engine", {}) or {}, "deal_pack"
    )
    ledger = build_revenue_ledger_engine(
        final_approval_centre,
        email_export_engine,
        invoice_export_engine,
        deal_pack_engine,
        stage_overrides=REVENUE_LEDGER_LOCAL_STAGE,
    )
    for record in ledger.get("revenue_ledger_records", []) or []:
        upsert_record("revenue_ledger_record", record.get("ledger_record_id"), record)
    return ledger


@app.get("/glirn/revenue-ledger")
def get_glirn_revenue_ledger(x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)
    return build_local_revenue_ledger()


@app.post("/glirn/revenue-ledger/actions")
def record_glirn_revenue_ledger_action(
    request: GlirnRevenueLedgerActionRequest,
    x_api_key: str | None = Header(default=None)
):
    require_api_key(x_api_key)

    action_type = request.action_type.strip()
    reason = request.reason.strip()
    final_approval_id = request.final_approval_id.strip() if request.final_approval_id else None
    ledger_record_id = request.ledger_record_id.strip() if request.ledger_record_id else None
    if not action_type:
        raise HTTPException(status_code=400, detail="action_type is required")
    if not reason:
        raise HTTPException(status_code=400, detail="reason is required")
    if action_type not in {
        "mark_manually_sent_by_gareth",
        "mark_payment_pending_manual",
        "mark_paid_manual_confirmation",
    }:
        raise HTTPException(status_code=400, detail="unsupported revenue ledger action")

    ledger = build_local_revenue_ledger()
    records = ledger.get("revenue_ledger_records", []) or []
    if not records:
        raise HTTPException(status_code=404, detail="revenue ledger record not found")
    record = (
        records[-1]
        if not final_approval_id and not ledger_record_id
        else next(
            (
                item for item in records
                if item.get("final_approval_id") == final_approval_id
                or item.get("ledger_record_id") == ledger_record_id
            ),
            None,
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="revenue ledger record not found")

    result = apply_revenue_ledger_action(record, action_type)
    REVENUE_LEDGER_LOCAL_STAGE[result.get("final_approval_id")] = result.get("revenue_stage")
    set_state("revenue_ledger_stages", REVENUE_LEDGER_LOCAL_STAGE)
    upsert_record("revenue_ledger_record", result.get("ledger_record_id"), result)
    persist_safe_action(
        "revenue_ledger_action",
        result.get("ledger_record_id"),
        final_approval_id=result.get("final_approval_id"),
        revenue_stage=result.get("revenue_stage"),
        payment_collection_enabled=False,
        money_movement_enabled=False,
    )
    record_approval_event({
        "event_type": "glirn_revenue_ledger_action",
        "approval_id": result.get("ledger_record_id"),
        "decision": result.get("revenue_stage"),
        "provider": "glirn_revenue_ledger_engine",
        "task_type": action_type,
        "reason": reason,
        "final_approval_id": result.get("final_approval_id"),
        "actual_revenue_received": result.get("actual_revenue_received"),
        "manual_payment_confirmation_required": True,
        "payment_collection_enabled": False,
        "money_movement_enabled": False,
        "invoice_sending_enabled": False,
        "client_contact_enabled": False,
        "external_integrations_enabled": False,
        "local_tracking_only": True,
        "capital_execution": False,
        "autonomous_execution": False,
    })

    return {
        "status": "revenue_ledger_action_recorded",
        "action_type": action_type,
        "ledger_record_id": result.get("ledger_record_id"),
        "final_approval_id": result.get("final_approval_id"),
        "revenue_stage": result.get("revenue_stage"),
        "actual_revenue_received": result.get("actual_revenue_received"),
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


@app.post("/glirn/approvals/{approval_id}/{decision}")
def decide_glirn_approval(
    approval_id: str,
    decision: str,
    request: GlirnApprovalDecisionRequest,
    x_api_key: str | None = Header(default=None)
):
    require_api_key(x_api_key)

    if decision not in {"approve", "reject", "monitor"}:
        raise HTTPException(status_code=400, detail="decision must be approve, reject, or monitor")

    approval_reason = request.approval_reason.strip()
    if not approval_reason:
        raise HTTPException(status_code=400, detail="approval reason is required")

    pending_approvals = list_pending_approvals()
    approval = next(
        (
            item
            for item in pending_approvals
            if item.get("approval_id") == approval_id
            and (item.get("route_result", {}) or {}).get("source") == "glirn"
        ),
        None,
    )

    if approval is None:
        raise HTTPException(status_code=404, detail="pending glirn approval not found")

    queue_decision = {
        "approve": "approved",
        "reject": "rejected",
    }.get(decision)
    updated_approval = update_approval_decision(approval_id, queue_decision) if queue_decision else approval

    record_approval_event({
        "event_type": "glirn_approval_decision",
        "approval_id": approval_id,
        "decision": decision,
        "provider": "glirn",
        "task_type": "recruitment_opportunity",
        "estimated_cost": 0,
        "avoided_cost": 0,
        "approval_reason": approval_reason,
        "outbound_action_locked": True,
        "candidate_introduction_locked": True,
        "client_engagement_locked": True,
        "fee_negotiation_locked": True,
        "capital_execution": False,
        "autonomous_execution": False,
    })

    return {
        "status": f"glirn_{decision}_recorded",
        "approval_id": approval_id,
        "decision": decision,
        "approval_reason": approval_reason,
        "approval": updated_approval,
        "outbound_action_locked": True,
        "candidate_introduction_locked": True,
        "client_engagement_locked": True,
        "fee_negotiation_locked": True,
        "capital_execution": False,
        "autonomous_execution": False,
    }


@app.post("/glirn/opportunities/{opportunity_id}/request-approval")
def request_glirn_human_approval(
    opportunity_id: str,
    x_api_key: str | None = Header(default=None)
):
    require_api_key(x_api_key)

    glirn_data = get_glirn_dashboard_data(public_leads=PUBLIC_LEADS)
    opportunity = next(
        (
            item
            for item in glirn_data.get("opportunities", [])
            if item.get("opportunity_id") == opportunity_id
        ),
        None,
    )

    if opportunity is None:
        raise HTTPException(status_code=404, detail="glirn opportunity not found")

    approval = create_approval_request({
        "source": "glirn",
        "subject_type": "recruitment_opportunity",
        "opportunity_id": opportunity.get("opportunity_id"),
        "title": opportunity.get("title"),
        "practice_area": opportunity.get("practice_area"),
        "jurisdiction": opportunity.get("jurisdiction"),
        "expected_fee_value": opportunity.get("expected_fee_value"),
        "placement_probability": opportunity.get("placement_probability"),
        "client_quality": opportunity.get("client_quality"),
        "candidate_quality": opportunity.get("candidate_quality"),
        "compliance_readiness": opportunity.get("compliance_readiness"),
        "urgency_score": opportunity.get("urgency_score"),
        "time_to_revenue": opportunity.get("time_to_revenue"),
        "overall_glirn_score": opportunity.get("overall_glirn_score"),
        "approval_required": True,
        "capital_execution": False,
        "autonomous_execution": False,
    })

    record_approval_event({
        "event_type": "glirn_approval_requested",
        "approval_id": approval["approval_id"],
        "decision": "REQUEST_APPROVAL",
        "provider": "glirn",
        "task_type": "recruitment_opportunity",
        "estimated_cost": 0,
        "avoided_cost": 0,
        "capital_execution": False,
        "opportunity_id": opportunity.get("opportunity_id"),
        "overall_glirn_score": opportunity.get("overall_glirn_score"),
    })

    return {
        "status": "pending_human_approval",
        "approval_required": True,
        "approval_id": approval["approval_id"],
        "opportunity": opportunity,
        "approval": approval,
        "capital_execution": False,
        "autonomous_execution": False,
    }


@app.post("/opportunities/{opportunity_id}/approve")
def approve_opportunity(
    opportunity_id: str,
    request: OpportunityReviewRequest | None = None,
    x_api_key: str | None = Header(default=None)
):
    require_api_key(x_api_key)
    reviewer_note = request.reviewer_note.strip() if request and request.reviewer_note else ""
    opportunity, approval = record_opportunity_approval(opportunity_id, "approve", reviewer_note=reviewer_note)

    if opportunity is None:
        raise HTTPException(status_code=404, detail="opportunity not found")

    return {
        "status": "approved_human_review",
        "capital_execution": False,
        "opportunity": opportunity.to_dict(),
        "approval": approval.to_dict()
    }


@app.post("/opportunities/{opportunity_id}/reject")
def reject_opportunity(
    opportunity_id: str,
    request: OpportunityReviewRequest | None = None,
    x_api_key: str | None = Header(default=None)
):
    require_api_key(x_api_key)
    reviewer_note = request.reviewer_note.strip() if request and request.reviewer_note else ""
    opportunity, approval = record_opportunity_approval(opportunity_id, "reject", reviewer_note=reviewer_note)

    if opportunity is None:
        raise HTTPException(status_code=404, detail="opportunity not found")

    return {
        "status": "rejected_human_review",
        "capital_execution": False,
        "opportunity": opportunity.to_dict(),
        "approval": approval.to_dict()
    }


@app.post("/opportunities/{opportunity_id}/outcome")
def update_opportunity_outcome(
    opportunity_id: str,
    request: OpportunityOutcomeRequest,
    x_api_key: str | None = Header(default=None)
):
    require_api_key(x_api_key)
    reviewer_note = request.reviewer_note.strip() if request.reviewer_note else ""

    try:
        opportunity, approval = record_opportunity_outcome(
            opportunity_id,
            request.outcome_status,
            reviewer_note=reviewer_note,
            realized_value=request.realized_value
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if opportunity is None:
        raise HTTPException(status_code=404, detail="opportunity not found")

    return {
        "status": request.outcome_status,
        "capital_execution": False,
        "opportunity": opportunity.to_dict(),
        "approval": approval.to_dict()
    }


def opportunity_approvals(x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)
    return {
        "approvals": [
            approval.to_dict()
            for approval in list_approvals(limit=20)
        ]
    }


@app.get("/research")
def research_items(x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)
    return {
        "research": [
            item.to_dict()
            for item in list_research_items(limit=20)
        ]
    }


@app.post("/research/intake")
def run_research_intake(x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)
    items = intake_research_items()

    return {
        "status": "research_intake_complete",
        "scraping_enabled": False,
        "capital_execution": False,
        "research": [
            item.to_dict()
            for item in items
        ]
    }


@app.post("/research/import")
def import_research(request: ResearchImportRequest, x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)

    title = request.title.strip()
    url = request.url.strip()
    summary = request.summary.strip()
    category = request.category.strip()

    if not title:
        raise HTTPException(status_code=400, detail="title is required")

    if not url:
        raise HTTPException(status_code=400, detail="url is required")

    if not summary:
        raise HTTPException(status_code=400, detail="summary is required")

    if not category:
        raise HTTPException(status_code=400, detail="category is required")

    if request.relevance_score < 0.0 or request.relevance_score > 1.0:
        raise HTTPException(status_code=400, detail="relevance_score must be between 0.0 and 1.0")

    if "crypto" in category.lower():
        raise HTTPException(status_code=400, detail="category must not contain crypto")

    item = ResearchItem.create(
        source="manual_import",
        title=title,
        url=url,
        summary=summary,
        category=category,
        relevance_score=request.relevance_score
    )
    append_research_item(item)

    return {
        "status": "research_imported",
        "fetching_enabled": False,
        "scraping_enabled": False,
        "capital_execution": False,
        "research": item.to_dict()
    }


@app.post("/research/convert")
def convert_research(x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)
    converted = convert_research_to_opportunities(limit=20)

    return {
        "status": "pending_human_review",
        "approval_required": True,
        "execution_enabled": False,
        "scraping_enabled": False,
        "opportunities": [
            opportunity.to_dict()
            for opportunity in converted
        ]
    }


@app.get("/research/sources")
def research_sources(x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)
    return {
        "sources": load_research_sources()
    }


@app.post("/research/sources/{source_name}/toggle")
def toggle_research_source_endpoint(source_name: str, x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)
    source = toggle_research_source(source_name)

    if source is None:
        raise HTTPException(status_code=404, detail="research source not found")

    return {
        "source": source,
        "fetching_enabled": False,
        "scraping_enabled": False,
        "capital_execution": False
    }


@app.post("/agent-safety/evaluate", response_model=AgentSafetyResponse)
def evaluate_agent_safety(
    request: AgentSafetyRequest,
    x_api_key: str | None = Header(default=None)
):
    require_api_key(x_api_key)

    payload = request.model_dump()
    result = evaluate_agent_action(payload)
    approval_id = None

    if result["decision"] == REQUEST_APPROVAL:
        approval = create_approval_request({
            "source": "agent_safety_gate",
            "action_type": payload.get("action_type"),
            "recipient_type": payload.get("recipient_type"),
            "subject": payload.get("subject"),
            "decision": result["decision"],
            "reason": result["reason"],
            "reason_codes": result["reason_codes"],
            "customer_facing": payload.get("customer_facing"),
            "contains_money_claim": payload.get("contains_money_claim"),
            "contains_private_data": payload.get("contains_private_data"),
            "capital_execution": False,
            "autonomous_execution": False,
        })
        approval_id = approval["approval_id"]

        record_approval_event({
            "event_type": "agent_safety_approval_requested",
            "approval_id": approval_id,
            "decision": result["decision"],
            "provider": "agent_safety_gate",
            "task_type": payload.get("action_type"),
            "capital_execution": False,
            "reason_codes": result["reason_codes"],
        })

    event_type = "agent_safety_blocked" if result["blocked"] else "agent_safety_evaluated"
    record_approval_event({
        "event_type": event_type,
        "approval_id": approval_id,
        "decision": result["decision"],
        "provider": "agent_safety_gate",
        "task_type": payload.get("action_type"),
        "capital_execution": False,
        "reason_codes": result["reason_codes"],
        "safe_default": result["safe_default"],
    })

    return {
        **result,
        "approval_id": approval_id,
        "capital_execution": False,
        "autonomous_execution": False,
    }


@app.post("/approvals/create")
def create_approval(payload: dict, x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)

    approval = create_approval_request(payload)

    record_approval_event({
        "event_type": "approval_created",
        "approval_id": approval["approval_id"],
        "provider": payload.get("provider"),
        "task_type": payload.get("task_type"),
        "estimated_cost": payload.get("estimated_cost"),
        "avoided_cost": payload.get("avoided_cost"),
    })

    return approval


@app.get("/approvals/pending")
def get_pending_approvals(x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)

    approvals = list_pending_approvals()

    return {
        "pending_count": len(approvals),
        "approvals": approvals,
        "capital_execution": False
    }


@app.post("/approvals/{approval_id}/{decision}")
def decide_approval(
    approval_id: str,
    decision: str,
    x_api_key: str | None = Header(default=None)
):
    require_api_key(x_api_key)

    updated = update_approval_decision(approval_id, decision)

    if not updated:
        raise HTTPException(status_code=404, detail="approval not found")

    record_approval_event({
        "event_type": "approval_decision",
        "approval_id": approval_id,
        "decision": decision,
        "provider": (
            updated.get("route_result", {})
            .get("provider")
        ),
        "task_type": (
            updated.get("route_result", {})
            .get("task_type")
        ),
    })

    return {
        "status": updated.get("status"),
        "capital_execution": False,
        "approval": updated
    }

@app.get("/ui", response_class=HTMLResponse)
def ui(key: str | None = Query(default=None)):
    require_api_key(key)
    return HTMLResponse(render_ui_page())


@app.post("/route")
def route(request: RouteRequest, x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)
    task_text = request.task.strip()

    if not task_text:
        raise HTTPException(status_code=400, detail="task is required")

    load_env_file()

    task_type = classify_task(task_text)
    providers = load_runtime_providers(task_text)

    if not providers:
        raise HTTPException(status_code=503, detail="no providers loaded")

    result = route_task({
        "task_text": task_text,
        "task_type": task_type
    }, providers)

    if result is None:
        raise HTTPException(status_code=502, detail="no valid AI route found")

    log_route_decision(
        task=task_text,
        task_type=result["task_type"],
        provider=result["provider_name"],
        latency=result["latency"],
        estimated_cost=result["estimated_cost"],
        status=result["status"]
    )

    return {
        "provider": result["provider_name"],
        "task_type": result["task_type"],
        "latency": result["latency"],
        "estimated_cost": result["estimated_cost"],
        "baseline_cost": result["baseline_cost"],
        "avoided_cost": result["avoided_cost"],
        "status": result["status"],
        "response_text": result["response_text"],
        "response_preview": result["response_preview"],
        "cycle_id": result["cycle_id"]
    }
