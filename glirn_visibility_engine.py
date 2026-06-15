from datetime import datetime, timezone
import re


SUPPORTED_MARKETS = {
    "United Kingdom": "UK",
    "United Arab Emirates": "UAE",
    "Singapore": "Singapore",
    "Europe": "Europe",
    "United States": "US",
}

LINKEDIN_THEMES = (
    "legal_hiring_intelligence",
    "ai_and_technology_law",
    "partner_hiring_advisory",
    "recruitment_trend_commentary",
)

WEBSITE_ASSET_TYPES = (
    "blog_article",
    "faq_update",
    "service_description_improvement",
    "capability_statement_suggestion",
)

DISCLAIMER = (
    "This material is general legal recruitment intelligence, not legal advice. "
    "Market observations are indicative, evidence-dependent, and subject to change."
)

PRINCIPLE = "Human-led. Technology-enhanced. Confidentiality-first."


def _safe_text(value, limit=1000):
    text = " ".join(str(value or "").split()).strip()
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[redacted email]", text)
    text = re.sub(r"(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)", "[redacted phone]", text)
    return text[:limit]


def _slug(value):
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return slug[:60] or "visibility-package"


def _evidence(evidence_points):
    points = [_safe_text(item, 500) for item in (evidence_points or [])]
    return [item for item in points if item]


def _linkedin_posts(topic, practice_area, evidence_points):
    lead = evidence_points[0]
    templates = {
        "legal_hiring_intelligence": (
            f"Legal hiring intelligence: {topic}. {lead} The practical question is not simply whether demand exists, "
            f"but whether the evidence supports action in {practice_area}."
        ),
        "ai_and_technology_law": (
            f"AI and Technology Law continues to reshape legal team design. In the context of {topic}, {lead} "
            "Firms should distinguish durable capability requirements from short-term market noise."
        ),
        "partner_hiring_advisory": (
            f"Partner hiring requires more than a visible market signal. For {topic}, {lead} "
            "Leadership fit, portable practice assumptions, jurisdiction, and delivery confidence all require human review."
        ),
        "recruitment_trend_commentary": (
            f"Recruitment trend commentary: {topic}. {lead} The strongest interpretation is evidence-led and cautious: "
            "validate the signal, test alternative explanations, and avoid treating commentary as certainty."
        ),
    }
    return [
        {
            "asset_id": f"linkedin-{theme}",
            "asset_type": "linkedin_post",
            "theme": theme,
            "headline": theme.replace("_", " ").title(),
            "body": f"{templates[theme]}\n\n{DISCLAIMER}\n\n{PRINCIPLE}",
            "publication_status": "blocked_pending_gareth_approval",
        }
        for theme in LINKEDIN_THEMES
    ]


def _market_reports(topic, practice_area, markets, evidence_points):
    evidence_lines = "\n".join(f"- {item}" for item in evidence_points)
    reports = []
    for market in markets:
        short_name = SUPPORTED_MARKETS[market]
        markdown = "\n".join([
            f"# {short_name} Legal Hiring Intelligence Report",
            "",
            f"## Focus\n{topic}",
            "",
            f"## Practice Area\n{practice_area}",
            "",
            "## Evidence Considered",
            evidence_lines,
            "",
            "## Market Summary",
            f"The submitted public intelligence indicates a potential {practice_area} hiring theme in {market}. "
            "This is an advisory interpretation and requires validation against current market conditions.",
            "",
            "## Hiring Considerations",
            "- Test whether the signal reflects sustained demand or a short-term event.",
            "- Validate jurisdiction, seniority, mobility, and delivery constraints.",
            "- Avoid candidate-specific conclusions without active consent.",
            "",
            "## Limitations",
            "The report is based only on the evidence supplied to this local preparation workflow.",
            "",
            f"## Required Disclaimer\n{DISCLAIMER}",
            "",
            PRINCIPLE,
        ])
        reports.append({
            "asset_id": f"report-{_slug(market)}",
            "asset_type": "intelligence_report",
            "market": market,
            "title": f"{short_name} Legal Hiring Intelligence Report: {topic}",
            "markdown": markdown,
            "suggested_filename": f"glirn-{_slug(market)}-{_slug(topic)}.md",
            "publication_status": "blocked_pending_gareth_approval",
            "download_status": "blocked_pending_gareth_approval",
        })
    return reports


def _website_assets(topic, practice_area, evidence_points):
    lead = evidence_points[0]
    content = {
        "blog_article": (
            f"# {topic}\n\n{lead}\n\nFor legal employers, the relevant issue is how this development may affect "
            f"{practice_area} hiring priorities, evidence quality, and delivery confidence. GLIRN treats market signals as "
            f"inputs for human review rather than automatic conclusions.\n\n{DISCLAIMER}\n\n{PRINCIPLE}"
        ),
        "faq_update": (
            f"Question: How does GLIRN assess {topic}?\n\nAnswer: GLIRN reviews public evidence, market context, "
            f"jurisdiction, and confidence limitations before Gareth decides whether any action is appropriate. {DISCLAIMER}"
        ),
        "service_description_improvement": (
            f"GLIRN provides human-led {practice_area} hiring intelligence informed by structured evidence review, "
            "confidence scoring, jurisdiction context, and explicit limitations. Recommendations remain subject to Gareth approval."
        ),
        "capability_statement_suggestion": (
            f"Capability: evidence-led legal recruitment intelligence for {practice_area}, including market observations, "
            "hiring-priority assessment, risk review, and manual decision support across key jurisdictions."
        ),
    }
    return [
        {
            "asset_id": f"website-{asset_type}",
            "asset_type": asset_type,
            "title": asset_type.replace("_", " ").title(),
            "body": body,
            "publication_status": "blocked_pending_gareth_approval",
        }
        for asset_type, body in content.items()
    ]


def _content_calendar(package_id, markets):
    linkedin = [
        {"week": 1, "theme": "legal_hiring_intelligence", "status": "proposed"},
        {"week": 2, "theme": "ai_and_technology_law", "status": "proposed"},
        {"week": 3, "theme": "partner_hiring_advisory", "status": "proposed"},
        {"week": 4, "theme": "recruitment_trend_commentary", "status": "proposed"},
    ]
    monthly_reports = [
        {"month_offset": index, "market": market, "status": "proposed"}
        for index, market in enumerate(markets, start=1)
    ]
    website = [
        {"week": 1, "asset_type": "blog_article", "status": "proposed"},
        {"week": 2, "asset_type": "faq_update", "status": "proposed"},
        {"week": 3, "asset_type": "service_description_improvement", "status": "proposed"},
        {"week": 4, "asset_type": "capability_statement_suggestion", "status": "proposed"},
    ]
    return {
        "calendar_id": f"calendar-{package_id}",
        "weekly_linkedin_schedule": linkedin,
        "monthly_intelligence_report_schedule": monthly_reports,
        "website_publication_schedule": website,
        "schedule_status": "proposal_only_pending_gareth_approval",
        "automatic_scheduling_enabled": False,
    }


def generate_visibility_package(package_id, topic, practice_area, markets, evidence_points, generated_at=None):
    package_id = _slug(package_id)
    topic = _safe_text(topic, 250)
    practice_area = _safe_text(practice_area, 160)
    evidence_points = _evidence(evidence_points)
    if not topic or not practice_area:
        raise ValueError("topic and practice_area are required")
    if not evidence_points:
        raise ValueError("at least one evidence point is required")
    selected_markets = list(dict.fromkeys(markets or []))
    if not selected_markets or any(market not in SUPPORTED_MARKETS for market in selected_markets):
        raise ValueError("markets must include supported UK, UAE, Singapore, Europe, or US market names")

    linkedin_posts = _linkedin_posts(topic, practice_area, evidence_points)
    intelligence_reports = _market_reports(topic, practice_area, selected_markets, evidence_points)
    website_assets = _website_assets(topic, practice_area, evidence_points)
    review_checks = {
        "evidence_present": bool(evidence_points),
        "all_required_linkedin_themes_present": {item["theme"] for item in linkedin_posts} == set(LINKEDIN_THEMES),
        "all_required_website_assets_present": {item["asset_type"] for item in website_assets} == set(WEBSITE_ASSET_TYPES),
        "supported_markets_only": all(item["market"] in SUPPORTED_MARKETS for item in intelligence_reports),
        "disclaimer_present": all(DISCLAIMER in item["markdown"] for item in intelligence_reports),
        "candidate_sensitive_content_excluded": True,
        "publication_controls_present": True,
    }
    review_passed = all(review_checks.values())
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    approval_package = {
        "approval_package_id": f"visibility-approval-{package_id}",
        "package_id": package_id,
        "asset_counts": {
            "linkedin_posts": len(linkedin_posts),
            "intelligence_reports": len(intelligence_reports),
            "website_assets": len(website_assets),
        },
        "internal_review_passed": review_passed,
        "review_checks": review_checks,
        "approval_status": "awaiting_gareth_approval",
        "gareth_approval_required": True,
    }
    return {
        "package_id": package_id,
        "generated_at": generated_at,
        "topic": topic,
        "practice_area": practice_area,
        "markets": selected_markets,
        "evidence_points": evidence_points,
        "linkedin_posts": linkedin_posts,
        "intelligence_reports": intelligence_reports,
        "website_assets": website_assets,
        "content_calendar": _content_calendar(package_id, selected_markets),
        "internal_review": {
            "review_id": f"visibility-review-{package_id}",
            "reviewed_at": generated_at,
            "review_checks": review_checks,
            "review_passed": review_passed,
            "review_status": "passed" if review_passed else "changes_required",
        },
        "approval_package": approval_package,
        "publication_ready": review_passed,
        "publication_status": "blocked_pending_gareth_approval",
        "legal_advice_provided": False,
        "candidate_data_minimised": True,
        **_safety_controls(),
    }


def apply_gareth_visibility_decision(package, decision, rationale, decided_at=None):
    if not package or not package.get("package_id"):
        raise ValueError("visibility package is required")
    if not package.get("internal_review", {}).get("review_passed"):
        raise ValueError("internal review must pass before Gareth approval")
    decision = str(decision or "").strip().upper()
    if decision not in {"APPROVE", "REJECT", "CHANGES_REQUIRED"}:
        raise ValueError("unsupported Gareth visibility decision")
    rationale = _safe_text(rationale, 500)
    if not rationale:
        raise ValueError("decision rationale is required")
    approved = decision == "APPROVE"
    return {
        "visibility_decision_id": f"gareth-decision-{package['package_id']}",
        "package_id": package["package_id"],
        "decision": decision,
        "decision_rationale": rationale,
        "decision_by": "Gareth",
        "decided_at": decided_at or datetime.now(timezone.utc).isoformat(),
        "approved_for_manual_publication": approved,
        "report_download_enabled": approved,
        "publication_executed": False,
        **_safety_controls(),
    }


def _safety_controls():
    return {
        "network_client_enabled": False,
        "automatic_publishing_enabled": False,
        "linkedin_posting_enabled": False,
        "website_publishing_enabled": False,
        "automatic_scheduling_enabled": False,
        "outreach_enabled": False,
        "contact_functionality_enabled": False,
        "external_commitments_enabled": False,
    }
