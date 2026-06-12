import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

os.environ.setdefault(
    "GLIRN_DB_PATH",
    os.path.join(tempfile.gettempdir(), f"glirn-tests-{os.getpid()}.db"),
)

import app
import glirn_human_review
import glirn_confidence_engine
import glirn_multi_agent_review
import glirn_responses
import glirn_storage
import notification_service


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app.app)

    def test_health_returns_system_status(self):
        with patch.dict("os.environ", {}, clear=True), patch("app.load_provider_config", return_value=[
            {"name": "OpenAI_Test", "enabled": True},
            {"name": "Anthropic_Test", "enabled": False}
        ]):
            response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["configured_providers"], 2)
        self.assertEqual(data["enabled_providers"], 1)

    def test_gareth_command_centre_is_default_and_advanced_view_is_toggleable(self):
        data = app.get_glirn_dashboard_data(public_leads=[])
        body = app.render_gareth_command_centre(data)

        self.assertIn('id="gareth-command-centre" data-default-view="true"', body)
        self.assertIn("Gareth Command Centre", body)
        self.assertIn('id="advanced-view-toggle"', body)
        self.assertIn('aria-expanded="false"', body)

        source = open(app.__file__, "r", encoding="utf-8").read()
        self.assertIn('<div id="advanced-view" hidden>', source)
        self.assertIn("advancedView.hidden = !willOpen", source)
        self.assertIn("/glirn/final-approval/actions", source)

    def test_providers_returns_scores_enabled_and_guard_status(self):
        with patch.dict("os.environ", {}, clear=True), patch("app.load_provider_config", return_value=[
            {
                "name": "OpenAI_Test",
                "provider_type": "openai",
                "enabled": True,
                "api_key_env": "OPENAI_API_KEY"
            }
        ]), patch("app.dashboard.load_json", return_value={
            "OpenAI_Test": {
                "score": 90,
                "success_count": 2,
                "failure_count": 0
            }
        }), patch("app.provider_allowed", return_value=True):
            response = self.client.get("/providers")

        self.assertEqual(response.status_code, 200)
        provider = response.json()["providers"][0]
        self.assertEqual(provider["name"], "OpenAI_Test")
        self.assertTrue(provider["enabled"])
        self.assertTrue(provider["guard_allowed"])
        self.assertEqual(provider["guard_status"], "allowed")
        self.assertEqual(provider["score"]["score"], 90)
        self.assertNotIn("api_key_env", provider)

    def test_route_uses_existing_runtime_loader_and_router(self):
        route_result = {
            "provider_name": "OpenAI_Test",
            "task_type": "general",
            "latency": 0.2,
            "estimated_cost": 0.001,
            "baseline_cost": 0.001,
            "avoided_cost": 0.0,
            "status": "verified_live_response",
            "response_text": "Test message received!",
            "response_preview": "Test message received!",
            "cycle_id": "unit-cycle"
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.load_env_file"), \
                patch("app.load_runtime_providers", return_value=[object()]) as load_providers, \
                patch("app.route_task", return_value=route_result) as route_task, \
                patch("app.log_route_decision") as log_route:
            response = self.client.post("/route", json={"task": "test message"})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["provider"], "OpenAI_Test")
        self.assertEqual(data["response_text"], "Test message received!")
        load_providers.assert_called_once_with("test message")
        route_task.assert_called_once()
        log_route.assert_called_once()

    def test_ui_renders_local_control_panel_without_key_fields(self):
        with patch.dict("os.environ", {}, clear=True), patch("app.health", return_value={
            "status": "healthy",
            "service": "ArbitrageEngineV1",
            "configured_providers": 1,
            "enabled_providers": 1
        }), patch("app.providers", return_value={
            "providers": [
                {
                    "name": "OpenAI_Test",
                    "provider_type": "openai",
                    "enabled": True,
                    "guard_allowed": True,
                    "guard_status": "allowed",
                    "score": {
                        "score": 90,
                        "success_count": 2,
                        "failure_count": 0
                    }
                }
            ]
        }), patch("app.dashboard.get_dashboard_data", return_value={
            "routing_history": {
                "total_route_count": 2,
                "provider_win_counts": {
                    "OpenAI_Test": 2
                },
                "average_latency_per_provider": {
                    "OpenAI_Test": 0.25
                },
                "average_cost_per_provider": {
                    "OpenAI_Test": 0.0015
                },
                "recent_routing_history": [
                    {
                        "timestamp": "2026-05-27T00:00:00+00:00",
                        "task_type": "general",
                        "provider": "OpenAI_Test",
                        "status": "verified_live_response",
                        "estimated_cost": "0.001",
                        "latency": "0.2"
                    },
                    {
                        "timestamp": "2026-05-27T00:01:00+00:00",
                        "task_type": "general",
                        "provider": "OpenAI_Test",
                        "status": "verified_live_response",
                        "estimated_cost": "0.002",
                        "latency": "0.3"
                    }
                ]
            },
            "recent_route_decisions": [
                {
                    "timestamp": "2026-05-27T00:00:00+00:00",
                    "task_type": "general",
                    "provider": "OpenAI_Test",
                    "status": "verified_live_response",
                    "estimated_cost": "0.001",
                    "latency": "0.2"
                }
            ],
            "recent_provider_audit_events": [
                {
                    "timestamp_utc": "2026-05-27T00:00:00+00:00",
                    "provider": "OpenAI_Test",
                    "decision": "winner",
                    "status_code": "200",
                    "reason": "unit test"
                }
            ]
        }), patch("app.opportunities", return_value={
            "opportunities": [
                {
                    "id": "opp-1",
                    "source": "stub_ai_infrastructure_scanner",
                    "category": "ai_infrastructure",
                    "title": "GPU capacity cost review",
                    "description": "Requires human approval before any vendor or budget action.",
                    "confidence": 0.72,
                    "estimated_value": 1250.0,
                    "risk_level": "medium",
                    "status": "pending_review",
                    "created_at": "2026-05-28T00:00:00+00:00",
                    "confidence_reason": "Stub evaluation based on AI infrastructure signals.",
                    "estimated_cost": 250.0,
                    "estimated_benefit": 1000.0,
                    "risk_notes": "Human review is required; no capital execution is available.",
                    "recommended_action": "review"
                }
            ]
        }), patch("app.opportunity_analytics", return_value={
            "total_opportunities": 1,
            "count_by_status": {
                "pending_review": 1
            },
            "count_by_recommended_action": {
                "review": 1
            },
            "average_confidence": 0.72,
            "total_estimated_value": 1250.0,
            "total_estimated_benefit": 1000.0,
            "total_realized_value": 0,
            "approval_counts": {
                "approved": 1,
                "rejected": 0,
                "monitored": 0
            },
            "capital_execution": False
        }), patch("app.governance_analytics", return_value={
            "pending_count": 1,
            "approved_count": 2,
            "rejected_count": 1,
            "approval_rate": 66.6667,
            "average_approval_hours": 2,
            "average_rejection_hours": 3,
            "oldest_pending_hours": 4,
            "approvals_by_provider": {
                "OpenAI_Test": 2
            },
            "rejections_by_provider": {
                "Anthropic_Test": 1
            },
            "approvals_by_task_type": {
                "general": 2
            },
            "rejections_by_task_type": {
                "research": 1
            },
            "capital_execution": False
        }), patch("app.scanner_opportunities", return_value={
            "opportunities": [
                {
                    "id": "wasted-money-overlapping-ai-tools",
                    "category": "overlapping_ai_tools",
                    "title": "Duplicate AI Tool Spend",
                    "confidence": 88,
                    "estimated_value": 12000.0,
                    "estimated_benefit": 12000.0,
                    "estimated_annual_savings": 12000.0,
                    "implementation_difficulty": "low",
                    "gareth_score": 95,
                    "risk_level": "medium",
                    "status": "pending_review",
                    "recommended_action": "review",
                    "reason": "High value, low complexity, low capital requirement.",
                    "capital_execution": False
                }
            ],
            "analytics": {
                "opportunities_scanned": 7,
                "passed_filters": 7,
                "worth_reviewing": 7,
                "total_wasted_money_opportunities": 7,
                "average_estimated_annual_savings": 9000,
                "highest_value_opportunity": {
                    "id": "wasted-money-overlapping-ai-tools",
                    "category": "overlapping_ai_tools",
                    "title": "Duplicate AI Tool Spend",
                    "confidence": 88,
                    "estimated_annual_savings": 12000.0,
                    "implementation_difficulty": "low",
                    "gareth_score": 95,
                    "recommended_action": "review",
                    "reason": "High value, low complexity, low capital requirement.",
                    "capital_execution": False
                },
                "average_gareth_score": 88.57,
                "categories": {
                    "overlapping_ai_tools": 1,
                    "duplicate_software_subscriptions": 1,
                    "unused_saas_licences": 1,
                    "excess_ai_api_spend": 1,
                    "expensive_manual_processes": 1,
                    "inefficient_reporting_workflows": 1,
                    "avoidable_recurring_costs": 1
                },
                "capital_execution": False,
                "fetching_enabled": False,
                "scraping_enabled": False,
                "execution_enabled": False
            },
            "categories": [
                "duplicate_software_subscriptions",
                "overlapping_ai_tools",
                "unused_saas_licences",
                "excess_ai_api_spend",
                "expensive_manual_processes",
                "inefficient_reporting_workflows",
                "avoidable_recurring_costs"
            ],
            "capital_execution": False,
            "fetching_enabled": False,
            "scraping_enabled": False,
            "execution_enabled": False
        }), patch("app.daily_snapshot", return_value={
            "generated_at": "2026-05-28T00:00:00+00:00",
            "system_health": {
                "status": "healthy"
            },
            "provider_summary": {
                "active_count": 1,
                "blocked_count": 0,
                "active_providers": ["OpenAI_Test"],
                "blocked_providers": []
            },
            "route_counts": {
                "total_route_count": 2,
                "recent_route_count": 2,
                "provider_win_counts": {
                    "OpenAI_Test": 2
                }
            },
            "opportunity_analytics": {
                "total_opportunities": 1,
                "average_confidence": 0.72,
                "total_realized_value": 0
            },
            "recent_high_confidence_opportunities": [
                {
                    "title": "GPU capacity cost review",
                    "confidence": 0.82,
                    "status": "pending_review"
                }
            ],
            "recent_research_items": [
                {
                    "title": "Provider pricing change monitor",
                    "category": "provider_pricing_changes",
                    "relevance_score": 0.88
                }
            ],
            "human_review_queue_count": 1,
            "capital_execution": False
        }), patch("app.opportunity_approvals", return_value={
            "approvals": [
                {
                    "id": "approval-1",
                    "opportunity_id": "opp-1",
                    "action": "approve",
                    "status": "approved_human_review",
                    "capital_execution": False,
                    "created_at": "2026-05-28T00:01:00+00:00"
                }
            ]
        }), patch("app.research_items", return_value={
            "research": [
                {
                    "id": "research-1",
                    "source": "stub_research_intake",
                    "title": "Provider pricing change monitor",
                    "url": "internal://research/provider-pricing-changes",
                    "summary": "Monitor model provider pricing changes. No capital execution is enabled.",
                    "category": "provider_pricing_changes",
                    "relevance_score": 0.88,
                    "created_at": "2026-05-28T00:02:00+00:00"
                }
            ]
        }), patch("app.research_sources", return_value={
            "sources": [
                {
                    "name": "AI Infrastructure News",
                    "category": "ai_infrastructure_news",
                    "url": "https://example.com/ai-infrastructure-news",
                    "enabled": False,
                    "refresh_cadence": "daily",
                    "notes": "No live fetching or scraping is implemented."
                }
            ]
        }), patch("app.list_approval_events", return_value=[
            {
                "event_type": "agent_safety_evaluated",
                "decision": "ALLOW"
            },
            {
                "event_type": "agent_safety_blocked",
                "decision": "BLOCK"
            }
        ]):
            response = self.client.get("/ui")

        self.assertEqual(response.status_code, 200)
        body = response.text
        self.assertIn("Profit Command Mode", body)
        self.assertIn("Today's estimated opportunity value", body)
        self.assertIn("Today's estimated benefit", body)
        self.assertIn("Dave-style recommendation", body)
        self.assertIn("Items needing Gareth approval", body)
        self.assertIn("Opportunities scanned", body)
        self.assertIn("Passed filters", body)
        self.assertIn("Worth reviewing", body)
        self.assertIn("Capital execution status", body)
        self.assertIn("Wasted Money Hunter", body)
        self.assertIn("Duplicate AI Tool Spend", body)
        self.assertIn("Estimated Annual Savings", body)
        self.assertIn("Gareth Score", body)
        self.assertIn("Agent Safety Gate", body)
        self.assertIn("Recent evaluations", body)
        self.assertIn("Pending safety approvals", body)
        self.assertIn("Blocked actions", body)
        self.assertIn("Legal Opportunity Radar", body)
        self.assertIn("Top GLIRN opportunity", body)
        self.assertIn("Dave Recommends First", body)
        self.assertIn("Gareth approval is required before any outbound", body)
        self.assertIn("GLIRN Human Approval Centre", body)
        self.assertIn("Waiting for Gareth Approval", body)
        self.assertIn("Outbound action lock", body)
        self.assertIn("Candidate introduction lock", body)
        self.assertIn("Client engagement lock", body)
        self.assertIn("Fee negotiation lock", body)
        self.assertIn("GLIRN Compliance Core", body)
        self.assertIn("Compliance-First Controls Active", body)
        self.assertIn("Compliance alerts", body)
        self.assertIn("Restricted outbound actions", body)
        self.assertIn("Executive Search Engine", body)
        self.assertIn("Top Executive Opportunities", body)
        self.assertIn("Estimated Placement Fee", body)
        self.assertIn("Estimated Retainer Fee", body)
        self.assertIn("Premium Opportunity Flag", body)
        self.assertIn("Legal Intelligence Network", body)
        self.assertIn("Top Salary Signals", body)
        self.assertIn("Hot Practice Areas", body)
        self.assertIn("Growing Jurisdictions", body)
        self.assertIn("Hiring Trend Alerts", body)
        self.assertIn("Client Intelligence Hook", body)
        self.assertIn("Commercial Revenue Engine", body)
        self.assertIn("Estimated Revenue Pipeline", body)
        self.assertIn("Highest Fee Opportunity", body)
        self.assertIn("Invoice Readiness", body)
        self.assertIn("Awaiting Gareth Approval", body)
        self.assertIn("Client Acquisition Engine", body)
        self.assertIn("Top Target Clients", body)
        self.assertIn("Highest Fee Potential Client", body)
        self.assertIn("Hiring Likelihood", body)
        self.assertIn("Recommended Practice Area", body)
        self.assertIn("Candidate Discovery Engine", body)
        self.assertIn("Top Candidate Opportunities", body)
        self.assertIn("Highest Estimated Placement Value", body)
        self.assertIn("Candidate Consent Status", body)
        self.assertIn("Practice Area Match", body)
        self.assertIn("Matching & Placement Engine", body)
        self.assertIn("Top Ranked Placement Matches", body)
        self.assertIn("Highest Match Revenue Score", body)
        self.assertIn("Placement Probability", body)
        self.assertIn("Client Terms Status", body)
        self.assertIn("Executive Autopilot", body)
        self.assertIn("Top Opportunity", body)
        self.assertIn("Top Candidate", body)
        self.assertIn("Top Client", body)
        self.assertIn("Top Placement Match", body)
        self.assertIn("Highest Estimated Fee", body)
        self.assertIn("Highest Placement Probability", body)
        self.assertIn("Gareth Approval Queue", body)
        self.assertIn("Live Data Readiness Layer", body)
        self.assertIn("Proposed data sources", body)
        self.assertIn("Readiness status", body)
        self.assertIn("Risk level", body)
        self.assertIn("Approval requirement", body)
        self.assertIn("Blocked sources", body)
        self.assertIn("Next recommended action", body)
        self.assertIn("Integration Governance Layer", body)
        self.assertIn("Pending integrations", body)
        self.assertIn("Approved integrations", body)
        self.assertIn("Blocked integrations", body)
        self.assertIn("Governance alerts", body)
        self.assertIn("Governance status", body)
        self.assertIn("Deployment Readiness Centre", body)
        self.assertIn("Readiness score", body)
        self.assertIn("Readiness grade", body)
        self.assertIn("Critical gaps", body)
        self.assertIn("Launch checklist", body)
        self.assertIn("Integration readiness", body)
        self.assertIn("Operations Command Centre", body)
        self.assertIn("Total Opportunities", body)
        self.assertIn("Total Candidates", body)
        self.assertIn("Total Clients", body)
        self.assertIn("Total Matches", body)
        self.assertIn("Estimated Revenue Pipeline", body)
        self.assertIn("Pending Gareth Approvals", body)
        self.assertIn("Readiness Score", body)
        self.assertIn("Platform health", body)
        self.assertIn("Daily Executive Briefing", body)
        self.assertIn("Top 3 opportunities", body)
        self.assertIn("Top 3 risks", body)
        self.assertIn("Top 3 revenue actions", body)
        self.assertIn("Pending Gareth approvals", body)
        self.assertIn("Compliance warnings", body)
        self.assertIn("Dave Recommends Today", body)
        self.assertIn("Automated Intelligence Review Engine", body)
        self.assertIn("Latest generated review title", body)
        self.assertIn("Target client profile", body)
        self.assertIn("Approval status", body)
        self.assertIn("Compliance status", body)
        self.assertIn("Client Deliverable Factory", body)
        self.assertIn("Latest deliverable", body)
        self.assertIn("Deliverable type", body)
        self.assertIn("Generated deliverables", body)
        self.assertIn("Pending deliverable approvals", body)
        self.assertIn("Approval-to-Action Workflow", body)
        self.assertIn("Draft status", body)
        self.assertIn("Client-ready status", body)
        self.assertIn("Action readiness", body)
        self.assertIn("Approved for human use", body)
        self.assertIn("Rejected items", body)
        self.assertIn("Monitored items", body)
        self.assertIn("Revenue Command Centre", body)
        self.assertIn("Total Revenue Pipeline", body)
        self.assertIn("Revenue Funnel", body)
        self.assertIn("Highest Fee Opportunity", body)
        self.assertIn("Fastest Revenue Opportunity", body)
        self.assertIn("Top Revenue Opportunities", body)
        self.assertIn("Revenue Readiness Score", body)
        self.assertIn("Recommended Next Action", body)
        self.assertIn("Invoice Drafting Engine", body)
        self.assertIn("Invoice drafts", body)
        self.assertIn("Pending invoice approvals", body)
        self.assertIn("Approved invoice drafts", body)
        self.assertIn("Invoice readiness status", body)
        self.assertIn("Payment methods", body)
        self.assertIn("Client Terms Drafting Engine", body)
        self.assertIn("Client terms drafts", body)
        self.assertIn("Pending terms approvals", body)
        self.assertIn("Approved terms drafts", body)
        self.assertIn("Terms readiness status", body)
        self.assertIn("Candidate Consent Management Engine", body)
        self.assertIn("Consent readiness status", body)
        self.assertIn("Candidate consent readiness", body)
        self.assertIn("Pending candidate consents", body)
        self.assertIn("Active candidate consents", body)
        self.assertIn("Expired candidate consents", body)
        self.assertIn("Manual Delivery Control Engine", body)
        self.assertIn("Manual delivery status", body)
        self.assertIn("Delivery ready items", body)
        self.assertIn("Blocked delivery items", body)
        self.assertIn("Pending delivery approvals", body)
        self.assertIn("Launch Compliance Validation Engine", body)
        self.assertIn("Compliance readiness score", body)
        self.assertIn("Risk level", body)
        self.assertIn("Missing compliance checks", body)
        self.assertIn("Recommended action", body)
        self.assertIn("First Prospect Selection Engine", body)
        self.assertIn("Top ranked prospect", body)
        self.assertIn("Prospect score", body)
        self.assertIn("Revenue potential", body)
        self.assertIn("Launch priority score", body)
        self.assertIn("First Client Dry Run", body)
        self.assertIn("Readiness score", body)
        self.assertIn("Generated artifacts", body)
        self.assertIn("Approval readiness", body)
        self.assertIn("Autonomous Internal Operations Orchestrator", body)
        self.assertIn("Autonomous cycle status", body)
        self.assertIn("Top final approval package", body)
        self.assertIn("Expected revenue", body)
        self.assertIn("Gareth final decision required", body)
        self.assertIn("Global Internet Shop Window", body)
        self.assertIn("Latest lead", body)
        self.assertIn("Latest lead type", body)
        self.assertIn("Lead route", body)
        self.assertIn("Qualification status", body)
        self.assertIn("Ready for Gareth Approval", body)
        self.assertIn("Latest revenue opportunity", body)
        self.assertIn("Dave recommends", body)
        self.assertIn("Estimated fee", body)
        self.assertIn("Approval status", body)
        self.assertIn("Client Response Draft Ready", body)
        self.assertIn("Suggested service", body)
        self.assertIn("Draft status", body)
        self.assertIn("Local draft only", body)
        self.assertIn("Fee Proposal Pack Ready", body)
        self.assertIn("Fee basis", body)
        self.assertIn("Proposal status", body)
        self.assertIn("Gareth Final Approval Required", body)
        self.assertIn("Lead route", body)
        self.assertIn("Final approval status", body)
        self.assertIn("No client contact, invoice, payment request, or money movement occurs without Gareth approval.", body)
        self.assertIn("Approved Client Contact Ready", body)
        self.assertIn("Lead name", body)
        self.assertIn("Lead email", body)
        self.assertIn("Contact status", body)
        self.assertIn("Gareth approval gate", body)
        self.assertIn("Local-only safety note", body)
        self.assertIn("Approved Email Draft Export Ready", body)
        self.assertIn("Recipient email", body)
        self.assertIn("Export status", body)
        self.assertIn("No email has been sent. Gareth must manually review and send.", body)
        self.assertIn("Invoice Draft Export Ready", body)
        self.assertIn("Client name", body)
        self.assertIn("Client email", body)
        self.assertIn("Invoice status", body)
        self.assertIn("No invoice or payment request has been sent. Gareth must manually review and send.", body)
        self.assertIn("Complete Deal Pack Ready", body)
        self.assertIn("Deal pack status", body)
        self.assertIn("No client contact, invoice, payment request, or money movement has occurred. Gareth must manually review and act.", body)
        self.assertIn("GLIRN Revenue Ledger", body)
        self.assertIn("Estimated pipeline value", body)
        self.assertIn("Actual revenue recorded", body)
        self.assertIn("Latest revenue stage", body)
        self.assertIn("Manual payment confirmation required", body)
        self.assertIn("First Client Readiness Gate", body)
        self.assertIn("Overall readiness score", body)
        self.assertIn("Ready items", body)
        self.assertIn("Blocked items", body)
        self.assertIn("Missing checks", body)
        self.assertIn("Gareth approval status", body)
        self.assertIn("Launch Readiness Command Centre", body)
        self.assertIn("Overall launch readiness score", body)
        self.assertIn("Launch readiness grade", body)
        self.assertIn("Missing items", body)
        self.assertIn("Missing launch items", body)
        self.assertIn("System is scanning opportunities", body)
        self.assertIn("System is ranking profit potential", body)
        self.assertIn("System is waiting for Gareth approval", body)
        self.assertIn("No capital is being moved automatically", body)
        self.assertIn("Dave Recommends", body)
        self.assertIn("Why this matters", body)
        self.assertIn("Advanced Engineer View", body)
        self.assertIn("Command Centre", body)
        self.assertIn("Today's Top Actions", body)
        self.assertIn("Unified Human Review Queue", body)
        self.assertIn("Advanced Diagnostics", body)
        self.assertIn("Capital execution", body)
        self.assertIn("Recommended next action", body)
        self.assertIn("Opportunity Review", body)
        self.assertIn("System Health", body)
        self.assertIn("Create Checkpoint", body)
        self.assertIn("/system/checkpoint", body)
        self.assertIn("Providers", body)
        self.assertIn("Route Task", body)
        self.assertIn("Routing Analytics", body)
        self.assertIn("Provider Wins", body)
        self.assertIn("Latency Trends", body)
        self.assertIn("Route Counts", body)
        self.assertIn("Opportunities", body)
        self.assertIn("Scan opportunities", body)
        self.assertIn("GPU capacity cost review", body)
        self.assertIn("Human approval is required", body)
        self.assertIn("Recommended", body)
        self.assertIn("Confidence reason", body)
        self.assertIn("Est. cost", body)
        self.assertIn("Est. benefit", body)
        self.assertIn("Risk notes", body)
        self.assertIn("no capital execution is available", body)
        self.assertIn("Approve", body)
        self.assertIn("Reject", body)
        self.assertIn("Reviewer note", body)
        self.assertIn("Save outcome", body)
        self.assertIn("monitored", body)
        self.assertIn("expired", body)
        self.assertIn("Realized value", body)
        self.assertIn("Opportunity Analytics", body)
        self.assertIn("Performance Totals", body)
        self.assertIn("Status Counts", body)
        self.assertIn("Recommended Actions", body)
        self.assertIn("Review Outcomes", body)
        self.assertIn("Opportunity status counts", body)
        self.assertIn("Governance Analytics", body)
        self.assertIn("Approval Rate %", body)
        self.assertIn("Average Review Time", body)
        self.assertIn("Daily Intelligence Snapshot", body)
        self.assertIn("Recent High-Confidence Opportunities", body)
        self.assertIn("Review queue", body)
        self.assertIn("Opportunity Approval History", body)
        self.assertIn("approved_human_review", body)
        self.assertIn("Research Intake", body)
        self.assertIn("Run research intake", body)
        self.assertIn("Convert Research to Opportunities", body)
        self.assertIn("Manual Research Import", body)
        self.assertIn("Import research", body)
        self.assertIn("do not fetch or scrape", body)
        self.assertIn("Provider pricing change monitor", body)
        self.assertIn("No internet scraping", body)
        self.assertIn("Research Sources", body)
        self.assertIn("AI Infrastructure News", body)
        self.assertIn("Toggle source", body)
        self.assertIn("does not fetch or scrape", body)
        self.assertIn("Provider wins chart", body)
        self.assertIn("Latency trend chart", body)
        self.assertIn("Recent Route Decisions", body)
        self.assertIn("Recent Provider Audit Events", body)
        self.assertIn("OpenAI_Test", body)
        self.assertIn("fetch('/route'", body)
        self.assertIn("Reset score", body)
        self.assertIn("/reset-score", body)
        self.assertNotIn("api_key", body.lower())

    def test_research_returns_recent_items(self):
        research = {
            "id": "research-1",
            "source": "stub_research_intake",
            "title": "Provider pricing change monitor",
            "url": "internal://research/provider-pricing-changes",
            "summary": "Monitor model provider pricing changes.",
            "category": "provider_pricing_changes",
            "relevance_score": 0.88,
            "created_at": "2026-05-28T00:02:00+00:00"
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_research_items") as list_items:
            list_items.return_value = [type("ResearchStub", (), {
                "to_dict": lambda self: research
            })()]
            response = self.client.get("/research")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"research": [research]})
        list_items.assert_called_once_with(limit=20)

    def test_research_intake_is_stub_only_without_scraping_or_execution(self):
        research = {
            "id": "research-1",
            "source": "stub_research_intake",
            "title": "Provider pricing change monitor",
            "url": "internal://research/provider-pricing-changes",
            "summary": "Monitor model provider pricing changes.",
            "category": "provider_pricing_changes",
            "relevance_score": 0.88,
            "created_at": "2026-05-28T00:02:00+00:00"
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.intake_research_items") as intake_items:
            intake_items.return_value = [type("ResearchStub", (), {
                "to_dict": lambda self: research
            })()]
            response = self.client.post("/research/intake")

        data = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["status"], "research_intake_complete")
        self.assertFalse(data["scraping_enabled"])
        self.assertFalse(data["capital_execution"])
        self.assertEqual(data["research"], [research])

    def test_research_import_persists_manual_item_without_fetching(self):
        payload = {
            "title": "Manual pricing note",
            "url": "https://example.com/provider-pricing",
            "summary": "Manual research note stored for review only.",
            "category": "provider_pricing_changes",
            "relevance_score": 0.83
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.append_research_item") as append_item:
            response = self.client.post("/research/import", json=payload)

        data = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["status"], "research_imported")
        self.assertFalse(data["fetching_enabled"])
        self.assertFalse(data["scraping_enabled"])
        self.assertFalse(data["capital_execution"])
        self.assertEqual(data["research"]["source"], "manual_import")
        self.assertEqual(data["research"]["title"], payload["title"])
        self.assertEqual(data["research"]["url"], payload["url"])
        self.assertEqual(data["research"]["summary"], payload["summary"])
        self.assertEqual(data["research"]["category"], payload["category"])
        self.assertEqual(data["research"]["relevance_score"], payload["relevance_score"])
        append_item.assert_called_once()

    def test_research_import_rejects_relevance_score_outside_range(self):
        payload = {
            "title": "Manual pricing note",
            "url": "https://example.com/provider-pricing",
            "summary": "Manual research note stored for review only.",
            "category": "provider_pricing_changes",
            "relevance_score": 1.1
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.append_research_item") as append_item:
            response = self.client.post("/research/import", json=payload)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "relevance_score must be between 0.0 and 1.0")
        append_item.assert_not_called()

    def test_research_import_rejects_category_containing_crypto(self):
        payload = {
            "title": "Manual pricing note",
            "url": "https://example.com/provider-pricing",
            "summary": "Manual research note stored for review only.",
            "category": "crypto_pricing_changes",
            "relevance_score": 0.6
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.append_research_item") as append_item:
            response = self.client.post("/research/import", json=payload)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "category must not contain crypto")
        append_item.assert_not_called()

    def test_research_convert_creates_review_only_opportunity_candidates(self):
        opportunity = {
            "id": "opp-1",
            "source": "research:research-1",
            "category": "ai_infrastructure",
            "title": "Research candidate: Provider pricing change monitor",
            "description": "Converted from research intake for human review only.",
            "confidence": 0.88,
            "estimated_value": 1380.0,
            "risk_level": "low",
            "status": "pending_review",
            "created_at": "2026-05-28T00:03:00+00:00",
            "confidence_reason": "Stub evaluation.",
            "estimated_cost": 150.0,
            "estimated_benefit": 1230.0,
            "risk_notes": "Human review is required; no capital execution is available.",
            "recommended_action": "review"
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.convert_research_to_opportunities") as convert_items:
            convert_items.return_value = [type("OpportunityStub", (), {
                "to_dict": lambda self: opportunity
            })()]
            response = self.client.post("/research/convert")

        data = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["status"], "pending_human_review")
        self.assertTrue(data["approval_required"])
        self.assertFalse(data["execution_enabled"])
        self.assertFalse(data["scraping_enabled"])
        self.assertEqual(data["opportunities"], [opportunity])
        convert_items.assert_called_once_with(limit=20)

    def test_research_sources_returns_configured_sources(self):
        sources = [
            {
                "name": "AI Infrastructure News",
                "category": "ai_infrastructure_news",
                "url": "https://example.com/ai-infrastructure-news",
                "enabled": False,
                "refresh_cadence": "daily",
                "notes": "No live fetching or scraping is implemented."
            }
        ]

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.load_research_sources", return_value=sources) as load_sources:
            response = self.client.get("/research/sources")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"sources": sources})
        load_sources.assert_called_once()

    def test_toggle_research_source_updates_local_config_only(self):
        source = {
            "name": "AI Infrastructure News",
            "category": "ai_infrastructure_news",
            "url": "https://example.com/ai-infrastructure-news",
            "enabled": True,
            "refresh_cadence": "daily",
            "notes": "No live fetching or scraping is implemented."
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.toggle_research_source", return_value=source) as toggle:
            response = self.client.post("/research/sources/AI%20Infrastructure%20News/toggle")

        data = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["source"], source)
        self.assertFalse(data["fetching_enabled"])
        self.assertFalse(data["scraping_enabled"])
        self.assertFalse(data["capital_execution"])
        toggle.assert_called_once_with("AI Infrastructure News")

    def test_toggle_research_source_returns_not_found_for_unknown_source(self):
        with patch.dict("os.environ", {}, clear=True), \
                patch("app.toggle_research_source", return_value=None):
            response = self.client.post("/research/sources/Missing/toggle")

        self.assertEqual(response.status_code, 404)

    def test_opportunities_returns_recent_opportunities(self):
        opportunity = {
            "id": "opp-1",
            "source": "stub_ai_infrastructure_scanner",
            "category": "ai_infrastructure",
            "title": "GPU capacity cost review",
            "description": "Requires human approval before any vendor or budget action.",
            "confidence": 0.72,
            "estimated_value": 1250.0,
            "risk_level": "medium",
            "status": "pending_review",
            "created_at": "2026-05-28T00:00:00+00:00",
            "confidence_reason": "Stub evaluation based on AI infrastructure signals.",
            "estimated_cost": 250.0,
            "estimated_benefit": 1000.0,
            "risk_notes": "Human review is required; no capital execution is available.",
            "recommended_action": "review"
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_opportunities") as list_items:
            list_items.return_value = [type("OpportunityStub", (), {
                "to_dict": lambda self: opportunity
            })()]
            response = self.client.get("/opportunities")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"opportunities": [opportunity]})
        list_items.assert_called_once_with(limit=20)

    def test_scan_opportunities_requires_human_review_only(self):
        opportunity = {
            "id": "opp-1",
            "source": "stub_ai_infrastructure_scanner",
            "category": "ai_infrastructure",
            "title": "GPU capacity cost review",
            "description": "Requires human approval before any vendor or budget action.",
            "confidence": 0.72,
            "estimated_value": 1250.0,
            "risk_level": "medium",
            "status": "pending_review",
            "created_at": "2026-05-28T00:00:00+00:00",
            "confidence_reason": "Stub evaluation based on AI infrastructure signals.",
            "estimated_cost": 250.0,
            "estimated_benefit": 1000.0,
            "risk_notes": "Human review is required; no capital execution is available.",
            "recommended_action": "review"
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.scan_opportunities") as scan_items:
            scan_items.return_value = [type("OpportunityStub", (), {
                "to_dict": lambda self: opportunity
            })()]
            response = self.client.post("/opportunities/scan")

        data = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["status"], "pending_human_review")
        self.assertTrue(data["approval_required"])
        self.assertFalse(data["execution_enabled"])
        self.assertEqual(data["opportunities"], [opportunity])

    def test_opportunity_analytics_returns_performance_summary(self):
        analytics = {
            "total_opportunities": 2,
            "count_by_status": {
                "pending_review": 1,
                "monitored": 1
            },
            "count_by_recommended_action": {
                "review": 1,
                "monitor": 1
            },
            "average_confidence": 0.75,
            "total_estimated_value": 2000.0,
            "total_estimated_benefit": 1500.0,
            "total_realized_value": 100.0,
            "approval_counts": {
                "approved": 1,
                "rejected": 0,
                "monitored": 1
            },
            "capital_execution": False
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.get_opportunity_analytics", return_value=analytics) as get_analytics:
            response = self.client.get("/opportunities/analytics")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), analytics)
        get_analytics.assert_called_once()

    def test_scanner_opportunities_returns_stub_discovery_results(self):
        scanner_results = {
            "opportunities": [
                {
                    "id": "wasted-money-overlapping-ai-tools",
                    "category": "overlapping_ai_tools",
                    "title": "Duplicate AI Tool Spend",
                    "estimated_annual_savings": 12000.0,
                    "implementation_difficulty": "low",
                    "gareth_score": 95,
                    "confidence": 88,
                    "status": "pending_review",
                    "capital_execution": False
                }
            ],
            "analytics": {
                "opportunities_scanned": 7,
                "passed_filters": 7,
                "worth_reviewing": 7,
                "total_wasted_money_opportunities": 7,
                "average_estimated_annual_savings": 9000,
                "highest_value_opportunity": {
                    "title": "Duplicate AI Tool Spend",
                    "estimated_annual_savings": 12000.0,
                    "gareth_score": 95,
                    "confidence": 88
                },
                "average_gareth_score": 88.57,
                "capital_execution": False,
                "fetching_enabled": False,
                "scraping_enabled": False,
                "execution_enabled": False
            },
            "categories": [
                "duplicate_software_subscriptions",
                "overlapping_ai_tools",
                "unused_saas_licences",
                "excess_ai_api_spend",
                "expensive_manual_processes",
                "inefficient_reporting_workflows",
                "avoidable_recurring_costs"
            ],
            "capital_execution": False,
            "fetching_enabled": False,
            "scraping_enabled": False,
            "execution_enabled": False
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.get_scanner_results", return_value=scanner_results) as get_results:
            response = self.client.get("/scanner/opportunities")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), scanner_results)
        get_results.assert_called_once()

    def test_approve_opportunity_records_human_review_without_execution(self):
        opportunity = {
            "id": "opp-1",
            "source": "stub_ai_infrastructure_scanner",
            "category": "ai_infrastructure",
            "title": "GPU capacity cost review",
            "description": "Requires human approval before any vendor or budget action.",
            "confidence": 0.72,
            "estimated_value": 1250.0,
            "risk_level": "medium",
            "status": "approved_human_review",
            "created_at": "2026-05-28T00:00:00+00:00"
        }
        approval = {
            "id": "approval-1",
            "opportunity_id": "opp-1",
            "action": "approve",
            "status": "approved_human_review",
            "capital_execution": False,
            "reviewer_note": "Approved for monitoring.",
            "realized_value": None,
            "created_at": "2026-05-28T00:01:00+00:00"
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.record_opportunity_approval") as record:
            record.return_value = (
                type("OpportunityStub", (), {"to_dict": lambda self: opportunity})(),
                type("ApprovalStub", (), {"to_dict": lambda self: approval})()
            )
            response = self.client.post(
                "/opportunities/opp-1/approve",
                json={"reviewer_note": "Approved for monitoring."}
            )

        data = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["status"], "approved_human_review")
        self.assertFalse(data["capital_execution"])
        self.assertEqual(data["opportunity"], opportunity)
        self.assertEqual(data["approval"], approval)
        record.assert_called_once_with("opp-1", "approve", reviewer_note="Approved for monitoring.")

    def test_reject_opportunity_records_human_review_without_execution(self):
        opportunity = {
            "id": "opp-1",
            "source": "stub_ai_infrastructure_scanner",
            "category": "ai_infrastructure",
            "title": "GPU capacity cost review",
            "description": "Requires human approval before any vendor or budget action.",
            "confidence": 0.72,
            "estimated_value": 1250.0,
            "risk_level": "medium",
            "status": "rejected_human_review",
            "created_at": "2026-05-28T00:00:00+00:00"
        }
        approval = {
            "id": "approval-1",
            "opportunity_id": "opp-1",
            "action": "reject",
            "status": "rejected_human_review",
            "capital_execution": False,
            "reviewer_note": "",
            "realized_value": None,
            "created_at": "2026-05-28T00:01:00+00:00"
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.record_opportunity_approval") as record:
            record.return_value = (
                type("OpportunityStub", (), {"to_dict": lambda self: opportunity})(),
                type("ApprovalStub", (), {"to_dict": lambda self: approval})()
            )
            response = self.client.post("/opportunities/opp-1/reject")

        data = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["status"], "rejected_human_review")
        self.assertFalse(data["capital_execution"])
        self.assertEqual(data["opportunity"], opportunity)
        self.assertEqual(data["approval"], approval)
        record.assert_called_once_with("opp-1", "reject", reviewer_note="")

    def test_opportunity_outcome_records_status_note_and_realized_value(self):
        opportunity = {
            "id": "opp-1",
            "source": "stub_ai_infrastructure_scanner",
            "category": "ai_infrastructure",
            "title": "GPU capacity cost review",
            "description": "Requires human approval before any vendor or budget action.",
            "confidence": 0.72,
            "estimated_value": 1250.0,
            "risk_level": "medium",
            "status": "monitored",
            "created_at": "2026-05-28T00:00:00+00:00"
        }
        approval = {
            "id": "approval-1",
            "opportunity_id": "opp-1",
            "action": "outcome",
            "status": "monitored",
            "capital_execution": False,
            "reviewer_note": "Monitor before deciding.",
            "realized_value": 125.5,
            "created_at": "2026-05-28T00:01:00+00:00"
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.record_opportunity_outcome") as record:
            record.return_value = (
                type("OpportunityStub", (), {"to_dict": lambda self: opportunity})(),
                type("ApprovalStub", (), {"to_dict": lambda self: approval})()
            )
            response = self.client.post(
                "/opportunities/opp-1/outcome",
                json={
                    "outcome_status": "monitored",
                    "reviewer_note": "Monitor before deciding.",
                    "realized_value": 125.5
                }
            )

        data = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["status"], "monitored")
        self.assertFalse(data["capital_execution"])
        self.assertEqual(data["opportunity"], opportunity)
        self.assertEqual(data["approval"], approval)
        record.assert_called_once_with(
            "opp-1",
            "monitored",
            reviewer_note="Monitor before deciding.",
            realized_value=125.5
        )

    def test_opportunity_outcome_rejects_invalid_status(self):
        with patch.dict("os.environ", {}, clear=True), \
                patch("app.record_opportunity_outcome", side_effect=ValueError("outcome_status must be valid")):
            response = self.client.post(
                "/opportunities/opp-1/outcome",
                json={"outcome_status": "executed", "reviewer_note": "", "realized_value": None}
            )

        self.assertEqual(response.status_code, 400)

    def test_opportunity_outcome_returns_not_found_for_unknown_id(self):
        with patch.dict("os.environ", {}, clear=True), \
                patch("app.record_opportunity_outcome", return_value=(None, None)):
            response = self.client.post(
                "/opportunities/missing/outcome",
                json={"outcome_status": "expired", "reviewer_note": "No longer relevant.", "realized_value": 0}
            )

        self.assertEqual(response.status_code, 404)

    def test_opportunity_approval_returns_not_found_for_unknown_id(self):
        with patch.dict("os.environ", {}, clear=True), \
                patch("app.record_opportunity_approval", return_value=(None, None)):
            response = self.client.post("/opportunities/missing/approve")

        self.assertEqual(response.status_code, 404)

    def test_analytics_history_returns_route_aggregates(self):
        history = {
            "total_route_count": 2,
            "provider_win_counts": {
                "OpenAI_Test": 1,
                "Anthropic_Test": 1
            },
            "average_latency_per_provider": {
                "OpenAI_Test": 0.2,
                "Anthropic_Test": 0.4
            },
            "average_cost_per_provider": {
                "OpenAI_Test": 0.001,
                "Anthropic_Test": 0.002
            },
            "recent_routing_history": [
                {
                    "timestamp": "2026-05-27T00:00:00+00:00",
                    "provider": "OpenAI_Test",
                    "latency": "0.2",
                    "estimated_cost": "0.001",
                    "status": "verified_live_response"
                }
            ]
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.dashboard.get_routing_history_data", return_value=history) as get_history:
            response = self.client.get("/analytics/history")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), history)
        get_history.assert_called_once_with(limit=20)

    def test_governance_analytics_returns_review_summary(self):
        analytics = {
            "pending_count": 1,
            "approved_count": 2,
            "rejected_count": 1,
            "approval_rate": 66.6667,
            "average_approval_hours": 2,
            "average_rejection_hours": 3,
            "oldest_pending_hours": 4,
            "approvals_by_provider": {
                "OpenAI_Test": 2
            },
            "rejections_by_provider": {
                "Anthropic_Test": 1
            },
            "approvals_by_task_type": {
                "general": 2
            },
            "rejections_by_task_type": {
                "research": 1
            },
            "capital_execution": False
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.get_governance_analytics", return_value=analytics) as get_analytics:
            response = self.client.get("/analytics/governance")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), analytics)
        get_analytics.assert_called_once()

    def test_daily_snapshot_returns_intelligence_summary(self):
        provider_data = {
            "providers": [
                {
                    "name": "OpenAI_Test",
                    "guard_allowed": True
                },
                {
                    "name": "Anthropic_Test",
                    "guard_allowed": False
                }
            ]
        }
        route_history = {
            "total_route_count": 4,
            "provider_win_counts": {
                "OpenAI_Test": 4
            },
            "recent_routing_history": [
                {"provider": "OpenAI_Test"},
                {"provider": "OpenAI_Test"}
            ]
        }
        analytics = {
            "total_opportunities": 2,
            "count_by_status": {
                "pending_review": 1,
                "monitored": 1
            },
            "count_by_recommended_action": {
                "review": 2
            },
            "average_confidence": 0.81,
            "total_estimated_value": 2000.0,
            "total_estimated_benefit": 1500.0,
            "total_realized_value": 100.0,
            "approval_counts": {
                "approved": 1,
                "rejected": 0,
                "monitored": 1
            },
            "capital_execution": False
        }
        low_opportunity = {
            "id": "opp-1",
            "title": "Lower confidence",
            "confidence": 0.7,
            "status": "pending_review"
        }
        high_opportunity = {
            "id": "opp-2",
            "title": "High confidence",
            "confidence": 0.88,
            "status": "monitored"
        }
        research = {
            "id": "research-1",
            "title": "Provider pricing change monitor",
            "category": "provider_pricing_changes",
            "relevance_score": 0.9
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.health", return_value={
                    "status": "healthy",
                    "service": "ArbitrageEngineV1",
                    "configured_providers": 2,
                    "enabled_providers": 1
                }), \
                patch("app.providers", return_value=provider_data), \
                patch("app.dashboard.get_routing_history_data", return_value=route_history), \
                patch("app.get_opportunity_analytics", return_value=analytics), \
                patch("app.list_opportunities") as list_opportunities, \
                patch("app.list_research_items") as list_research:
            list_opportunities.return_value = [
                type("OpportunityStub", (), {"to_dict": lambda self: low_opportunity})(),
                type("OpportunityStub", (), {"to_dict": lambda self: high_opportunity})()
            ]
            list_research.return_value = [
                type("ResearchStub", (), {"to_dict": lambda self: research})()
            ]
            response = self.client.get("/snapshot/daily")

        data = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["system_health"]["status"], "healthy")
        self.assertEqual(data["provider_summary"]["active_count"], 1)
        self.assertEqual(data["provider_summary"]["blocked_count"], 1)
        self.assertEqual(data["route_counts"]["total_route_count"], 4)
        self.assertEqual(data["route_counts"]["recent_route_count"], 2)
        self.assertEqual(data["opportunity_analytics"], analytics)
        self.assertEqual(data["recent_high_confidence_opportunities"], [high_opportunity])
        self.assertEqual(data["recent_research_items"], [research])
        self.assertEqual(data["human_review_queue_count"], 1)
        self.assertFalse(data["capital_execution"])

    def test_system_checkpoint_endpoint_returns_metadata(self):
        checkpoint = {
            "checkpoint_id": "checkpoint-20260528T000000000000Z",
            "created_at": "2026-05-28T00:00:00+00:00",
            "files_copied": 5,
            "backup_path": "backups/checkpoint-20260528T000000000000Z",
            "capital_execution": False
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.create_system_checkpoint", return_value=checkpoint) as create_checkpoint:
            response = self.client.post("/system/checkpoint")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), checkpoint)
        create_checkpoint.assert_called_once()

    def test_create_system_checkpoint_copies_allowed_paths_without_env_or_secrets(self):
        current_dir = os.getcwd()

        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                os.chdir(temp_dir)
                os.makedirs("config", exist_ok=True)
                os.makedirs("analytics", exist_ok=True)
                os.makedirs("data", exist_ok=True)
                os.makedirs("logs", exist_ok=True)

                with open("config/providers.json", "w", encoding="utf-8") as file:
                    file.write("{}")
                with open("config/.env", "w", encoding="utf-8") as file:
                    file.write("SECRET=value")
                with open("analytics/provider_scores.json", "w", encoding="utf-8") as file:
                    file.write("{}")
                with open("data/opportunities.jsonl", "w", encoding="utf-8") as file:
                    file.write("{}\n")
                with open("logs/route_decisions.csv", "w", encoding="utf-8") as file:
                    file.write("timestamp\n")
                with open("logs/secret_token.txt", "w", encoding="utf-8") as file:
                    file.write("do-not-copy")
                with open("RUNBOOK.md", "w", encoding="utf-8") as file:
                    file.write("# Runbook")

                metadata = app.create_system_checkpoint()

                self.assertTrue(metadata["checkpoint_id"].startswith("checkpoint-"))
                self.assertEqual(metadata["files_copied"], 5)
                self.assertFalse(metadata["capital_execution"])
                self.assertTrue(os.path.exists(os.path.join(metadata["backup_path"], "config", "providers.json")))
                self.assertTrue(os.path.exists(os.path.join(metadata["backup_path"], "RUNBOOK.md")))
                self.assertFalse(os.path.exists(os.path.join(metadata["backup_path"], "config", ".env")))
                self.assertFalse(os.path.exists(os.path.join(metadata["backup_path"], "logs", "secret_token.txt")))
            finally:
                os.chdir(current_dir)

    def test_reset_score_endpoint_resets_selected_provider(self):
        reset_score = {
            "success_count": 0,
            "failure_count": 0,
            "average_latency": 0,
            "average_cost": 0,
            "score": 100
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.reset_provider_score", return_value=reset_score) as reset:
            response = self.client.post("/providers/OpenAI_Test/reset-score")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "provider": "OpenAI_Test",
            "score": reset_score
        })
        reset.assert_called_once_with("OpenAI_Test")

    def test_protected_mode_keeps_health_public(self):
        with patch.dict("os.environ", {"ARBITRAGE_API_KEY": "unit-key"}, clear=True), \
                patch("app.load_provider_config", return_value=[]):
            response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)

    def test_protected_mode_rejects_missing_header_for_providers(self):
        with patch.dict("os.environ", {"ARBITRAGE_API_KEY": "unit-key"}, clear=True):
            response = self.client.get("/providers")

        self.assertEqual(response.status_code, 401)

    def test_protected_mode_accepts_header_for_providers(self):
        with patch.dict("os.environ", {"ARBITRAGE_API_KEY": "unit-key"}, clear=True), \
                patch("app.load_provider_config", return_value=[]), \
                patch("app.dashboard.load_json", return_value={}):
            response = self.client.get("/providers", headers={"X-API-Key": "unit-key"})

        self.assertEqual(response.status_code, 200)

    def test_protected_mode_requires_header_for_reset_score(self):
        with patch.dict("os.environ", {"ARBITRAGE_API_KEY": "unit-key"}, clear=True):
            missing = self.client.post("/providers/OpenAI_Test/reset-score")

        self.assertEqual(missing.status_code, 401)

        reset_score = {
            "success_count": 0,
            "failure_count": 0,
            "average_latency": 0,
            "average_cost": 0,
            "score": 100
        }

        with patch.dict("os.environ", {"ARBITRAGE_API_KEY": "unit-key"}, clear=True), \
                patch("app.reset_provider_score", return_value=reset_score):
            allowed = self.client.post(
                "/providers/OpenAI_Test/reset-score",
                headers={"X-API-Key": "unit-key"}
            )

        self.assertEqual(allowed.status_code, 200)

    def test_protected_mode_requires_header_for_analytics_history(self):
        with patch.dict("os.environ", {"ARBITRAGE_API_KEY": "unit-key"}, clear=True):
            missing = self.client.get("/analytics/history")

        self.assertEqual(missing.status_code, 401)

        with patch.dict("os.environ", {"ARBITRAGE_API_KEY": "unit-key"}, clear=True), \
                patch("app.dashboard.get_routing_history_data", return_value={
                    "total_route_count": 0,
                    "provider_win_counts": {},
                    "average_latency_per_provider": {},
                    "average_cost_per_provider": {},
                    "recent_routing_history": []
                }):
            allowed = self.client.get(
                "/analytics/history",
                headers={"X-API-Key": "unit-key"}
            )

        self.assertEqual(allowed.status_code, 200)

    def test_protected_mode_requires_header_for_daily_snapshot(self):
        with patch.dict("os.environ", {"ARBITRAGE_API_KEY": "unit-key"}, clear=True):
            missing = self.client.get("/snapshot/daily")

        self.assertEqual(missing.status_code, 401)

        with patch.dict("os.environ", {"ARBITRAGE_API_KEY": "unit-key"}, clear=True), \
                patch("app.health", return_value={
                    "status": "healthy",
                    "service": "ArbitrageEngineV1",
                    "configured_providers": 0,
                    "enabled_providers": 0
                }), \
                patch("app.providers", return_value={"providers": []}), \
                patch("app.dashboard.get_routing_history_data", return_value={
                    "total_route_count": 0,
                    "provider_win_counts": {},
                    "recent_routing_history": []
                }), \
                patch("app.get_opportunity_analytics", return_value={
                    "total_opportunities": 0,
                    "count_by_status": {},
                    "count_by_recommended_action": {},
                    "average_confidence": 0,
                    "total_estimated_value": 0,
                    "total_estimated_benefit": 0,
                    "total_realized_value": 0,
                    "approval_counts": {
                        "approved": 0,
                        "rejected": 0,
                        "monitored": 0
                    },
                    "capital_execution": False
                }), \
                patch("app.list_opportunities", return_value=[]), \
                patch("app.list_research_items", return_value=[]):
            allowed = self.client.get(
                "/snapshot/daily",
                headers={"X-API-Key": "unit-key"}
            )

        self.assertEqual(allowed.status_code, 200)

    def test_protected_mode_requires_header_for_system_checkpoint(self):
        with patch.dict("os.environ", {"ARBITRAGE_API_KEY": "unit-key"}, clear=True):
            missing = self.client.post("/system/checkpoint")

        self.assertEqual(missing.status_code, 401)

        checkpoint = {
            "checkpoint_id": "checkpoint-20260528T000000000000Z",
            "created_at": "2026-05-28T00:00:00+00:00",
            "files_copied": 5,
            "backup_path": "backups/checkpoint-20260528T000000000000Z",
            "capital_execution": False
        }

        with patch.dict("os.environ", {"ARBITRAGE_API_KEY": "unit-key"}, clear=True), \
                patch("app.create_system_checkpoint", return_value=checkpoint):
            allowed = self.client.post(
                "/system/checkpoint",
                headers={"X-API-Key": "unit-key"}
            )

        self.assertEqual(allowed.status_code, 200)

    def test_protected_mode_requires_header_for_opportunities(self):
        with patch.dict("os.environ", {"ARBITRAGE_API_KEY": "unit-key"}, clear=True):
            missing_list = self.client.get("/opportunities")
            missing_scan = self.client.post("/opportunities/scan")
            missing_analytics = self.client.get("/opportunities/analytics")

        self.assertEqual(missing_list.status_code, 401)
        self.assertEqual(missing_scan.status_code, 401)
        self.assertEqual(missing_analytics.status_code, 401)

        with patch.dict("os.environ", {"ARBITRAGE_API_KEY": "unit-key"}, clear=True), \
                patch("app.list_opportunities", return_value=[]), \
                patch("app.scan_opportunities", return_value=[]), \
                patch("app.get_opportunity_analytics", return_value={
                    "total_opportunities": 0,
                    "count_by_status": {},
                    "count_by_recommended_action": {},
                    "average_confidence": 0,
                    "total_estimated_value": 0,
                    "total_estimated_benefit": 0,
                    "total_realized_value": 0,
                    "approval_counts": {
                        "approved": 0,
                        "rejected": 0,
                        "monitored": 0
                    },
                    "capital_execution": False
                }):
            allowed_list = self.client.get(
                "/opportunities",
                headers={"X-API-Key": "unit-key"}
            )
            allowed_scan = self.client.post(
                "/opportunities/scan",
                headers={"X-API-Key": "unit-key"}
            )
            allowed_analytics = self.client.get(
                "/opportunities/analytics",
                headers={"X-API-Key": "unit-key"}
            )

        self.assertEqual(allowed_list.status_code, 200)
        self.assertEqual(allowed_scan.status_code, 200)
        self.assertEqual(allowed_analytics.status_code, 200)

    def test_protected_mode_requires_header_for_opportunity_approval_actions(self):
        with patch.dict("os.environ", {"ARBITRAGE_API_KEY": "unit-key"}, clear=True):
            missing_approve = self.client.post("/opportunities/opp-1/approve")
            missing_reject = self.client.post("/opportunities/opp-1/reject")
            missing_outcome = self.client.post(
                "/opportunities/opp-1/outcome",
                json={"outcome_status": "monitored", "reviewer_note": "", "realized_value": None}
            )

        self.assertEqual(missing_approve.status_code, 401)
        self.assertEqual(missing_reject.status_code, 401)
        self.assertEqual(missing_outcome.status_code, 401)

        opportunity = {
            "id": "opp-1",
            "source": "stub_ai_infrastructure_scanner",
            "category": "ai_infrastructure",
            "title": "GPU capacity cost review",
            "description": "Requires human approval before any vendor or budget action.",
            "confidence": 0.72,
            "estimated_value": 1250.0,
            "risk_level": "medium",
            "status": "approved_human_review",
            "created_at": "2026-05-28T00:00:00+00:00"
        }
        approval = {
            "id": "approval-1",
            "opportunity_id": "opp-1",
            "action": "approve",
            "status": "approved_human_review",
            "capital_execution": False,
            "reviewer_note": "",
            "realized_value": None,
            "created_at": "2026-05-28T00:01:00+00:00"
        }
        outcome = {
            "id": "approval-2",
            "opportunity_id": "opp-1",
            "action": "outcome",
            "status": "monitored",
            "capital_execution": False,
            "reviewer_note": "Watch for follow-up.",
            "realized_value": 25.0,
            "created_at": "2026-05-28T00:02:00+00:00"
        }

        with patch.dict("os.environ", {"ARBITRAGE_API_KEY": "unit-key"}, clear=True), \
                patch("app.record_opportunity_approval") as record, \
                patch("app.record_opportunity_outcome") as record_outcome:
            record.return_value = (
                type("OpportunityStub", (), {"to_dict": lambda self: opportunity})(),
                type("ApprovalStub", (), {"to_dict": lambda self: approval})()
            )
            record_outcome.return_value = (
                type("OpportunityStub", (), {"to_dict": lambda self: opportunity})(),
                type("ApprovalStub", (), {"to_dict": lambda self: outcome})()
            )
            allowed = self.client.post(
                "/opportunities/opp-1/approve",
                headers={"X-API-Key": "unit-key"}
            )
            allowed_outcome = self.client.post(
                "/opportunities/opp-1/outcome",
                json={
                    "outcome_status": "monitored",
                    "reviewer_note": "Watch for follow-up.",
                    "realized_value": 25.0
                },
                headers={"X-API-Key": "unit-key"}
            )

        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed_outcome.status_code, 200)

    def test_protected_mode_requires_header_for_research(self):
        with patch.dict("os.environ", {"ARBITRAGE_API_KEY": "unit-key"}, clear=True):
            missing_list = self.client.get("/research")
            missing_intake = self.client.post("/research/intake")
            missing_import = self.client.post("/research/import", json={
                "title": "Manual pricing note",
                "url": "https://example.com/provider-pricing",
                "summary": "Manual research note stored for review only.",
                "category": "provider_pricing_changes",
                "relevance_score": 0.83
            })
            missing_convert = self.client.post("/research/convert")
            missing_sources = self.client.get("/research/sources")
            missing_toggle = self.client.post("/research/sources/AI%20Infrastructure%20News/toggle")

        self.assertEqual(missing_list.status_code, 401)
        self.assertEqual(missing_intake.status_code, 401)
        self.assertEqual(missing_import.status_code, 401)
        self.assertEqual(missing_convert.status_code, 401)
        self.assertEqual(missing_sources.status_code, 401)
        self.assertEqual(missing_toggle.status_code, 401)

        with patch.dict("os.environ", {"ARBITRAGE_API_KEY": "unit-key"}, clear=True), \
                patch("app.list_research_items", return_value=[]), \
                patch("app.append_research_item"), \
                patch("app.intake_research_items", return_value=[]), \
                patch("app.convert_research_to_opportunities", return_value=[]), \
                patch("app.load_research_sources", return_value=[]), \
                patch("app.toggle_research_source", return_value={
                    "name": "AI Infrastructure News",
                    "enabled": True
                }):
            allowed_list = self.client.get(
                "/research",
                headers={"X-API-Key": "unit-key"}
            )
            allowed_intake = self.client.post(
                "/research/intake",
                headers={"X-API-Key": "unit-key"}
            )
            allowed_import = self.client.post(
                "/research/import",
                json={
                    "title": "Manual pricing note",
                    "url": "https://example.com/provider-pricing",
                    "summary": "Manual research note stored for review only.",
                    "category": "provider_pricing_changes",
                    "relevance_score": 0.83
                },
                headers={"X-API-Key": "unit-key"}
            )
            allowed_convert = self.client.post(
                "/research/convert",
                headers={"X-API-Key": "unit-key"}
            )
            allowed_sources = self.client.get(
                "/research/sources",
                headers={"X-API-Key": "unit-key"}
            )
            allowed_toggle = self.client.post(
                "/research/sources/AI%20Infrastructure%20News/toggle",
                headers={"X-API-Key": "unit-key"}
            )

        self.assertEqual(allowed_list.status_code, 200)
        self.assertEqual(allowed_intake.status_code, 200)
        self.assertEqual(allowed_import.status_code, 200)
        self.assertEqual(allowed_convert.status_code, 200)
        self.assertEqual(allowed_sources.status_code, 200)
        self.assertEqual(allowed_toggle.status_code, 200)

    def test_protected_mode_requires_query_key_for_ui(self):
        with patch.dict("os.environ", {"ARBITRAGE_API_KEY": "unit-key"}, clear=True):
            missing = self.client.get("/ui")

        self.assertEqual(missing.status_code, 401)

        with patch.dict("os.environ", {"ARBITRAGE_API_KEY": "unit-key"}, clear=True), \
                patch("app.render_ui_page", return_value="<html>ok</html>"):
            allowed = self.client.get("/ui?key=unit-key")

        self.assertEqual(allowed.status_code, 200)

    def test_protected_mode_requires_header_for_route(self):
        with patch.dict("os.environ", {"ARBITRAGE_API_KEY": "unit-key"}, clear=True):
            missing = self.client.post("/route", json={"task": "test"})

        self.assertEqual(missing.status_code, 401)

        route_result = {
            "provider_name": "OpenAI_Test",
            "task_type": "general",
            "latency": 0.2,
            "estimated_cost": 0.001,
            "baseline_cost": 0.001,
            "avoided_cost": 0.0,
            "status": "verified_live_response",
            "response_text": "ok",
            "response_preview": "ok",
            "cycle_id": "unit-cycle"
        }

        with patch.dict("os.environ", {"ARBITRAGE_API_KEY": "unit-key"}, clear=True), \
                patch("app.load_env_file"), \
                patch("app.load_runtime_providers", return_value=[object()]), \
                patch("app.route_task", return_value=route_result), \
                patch("app.log_route_decision"):
            allowed = self.client.post(
                "/route",
                json={"task": "test"},
                headers={"X-API-Key": "unit-key"}
            )

        self.assertEqual(allowed.status_code, 200)

    def test_agent_safety_allows_internal_email_and_logs_evaluation(self):
        payload = {
            "action_type": "send_email",
            "recipient_type": "internal",
            "subject": "Draft",
            "body": "Internal draft only.",
            "customer_facing": False
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.record_approval_event") as record_event:
            response = self.client.post("/agent-safety/evaluate", json=payload)

        data = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["decision"], "ALLOW")
        self.assertFalse(data["approval_required"])
        self.assertIsNone(data["approval_id"])
        self.assertFalse(data["blocked"])
        self.assertEqual(data["safe_default"], "do_not_execute")
        self.assertFalse(data["capital_execution"])
        self.assertFalse(data["autonomous_execution"])
        record_event.assert_called_once()
        self.assertEqual(record_event.call_args.args[0]["event_type"], "agent_safety_evaluated")

    def test_agent_safety_requests_approval_and_creates_queue_item(self):
        payload = {
            "action_type": "send_email",
            "recipient_type": "customer",
            "subject": "Reply",
            "body": "Thanks for your message.",
            "customer_facing": True
        }
        approval = {
            "approval_id": "approval-123",
            "capital_execution": False
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.create_approval_request", return_value=approval) as create_approval, \
                patch("app.record_approval_event") as record_event:
            response = self.client.post("/agent-safety/evaluate", json=payload)

        data = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["decision"], "REQUEST_APPROVAL")
        self.assertTrue(data["approval_required"])
        self.assertEqual(data["approval_id"], "approval-123")
        self.assertFalse(data["blocked"])
        self.assertFalse(data["capital_execution"])
        self.assertFalse(data["autonomous_execution"])
        create_approval.assert_called_once()
        approval_payload = create_approval.call_args.args[0]
        self.assertEqual(approval_payload["source"], "agent_safety_gate")
        self.assertEqual(approval_payload["action_type"], "send_email")
        self.assertFalse(approval_payload["capital_execution"])
        self.assertFalse(approval_payload["autonomous_execution"])
        self.assertEqual(record_event.call_count, 2)
        self.assertEqual(record_event.call_args_list[0].args[0]["event_type"], "agent_safety_approval_requested")

    def test_agent_safety_blocks_regulated_financial_advice_without_approval_item(self):
        payload = {
            "action_type": "send_email",
            "recipient_type": "customer",
            "subject": "Investment",
            "body": "This is regulated financial advice.",
            "customer_facing": True,
            "contains_regulated_financial_advice": True
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.create_approval_request") as create_approval, \
                patch("app.record_approval_event") as record_event:
            response = self.client.post("/agent-safety/evaluate", json=payload)

        data = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["decision"], "BLOCK")
        self.assertFalse(data["approval_required"])
        self.assertIsNone(data["approval_id"])
        self.assertTrue(data["blocked"])
        self.assertIn("regulated_financial_advice", data["reason_codes"])
        self.assertFalse(data["capital_execution"])
        self.assertFalse(data["autonomous_execution"])
        create_approval.assert_not_called()
        record_event.assert_called_once()
        self.assertEqual(record_event.call_args.args[0]["event_type"], "agent_safety_blocked")

    def test_glirn_dashboard_returns_foundation_data(self):
        glirn_data = {
            "legal_sectors": [
                {"code": "corporate_and_ma", "name": "Corporate & M&A", "capital_execution": False}
            ],
            "opportunities": [
                {
                    "opportunity_id": "glirn-test-001",
                    "title": "Private Equity Partner Search",
                    "expected_fee_value": 85000,
                    "overall_glirn_score": 76.4,
                    "capital_execution": False
                }
            ],
            "legal_opportunity_radar": {
                "engine": "legal_opportunity_radar",
                "top_opportunity": {
                    "opportunity_id": "glirn-test-001",
                    "title": "Private Equity Partner Search",
                    "radar_priority_score": 77.1,
                    "dave_recommendation": "Review first.",
                    "capital_execution": False
                },
                "highest_value_candidate": {
                    "full_name": "Candidate A",
                    "expected_fee_value": 85000,
                    "approval_required": True,
                    "capital_execution": False
                },
                "highest_value_client_firm": {
                    "name": "Client Firm A",
                    "expected_fee_value": 85000,
                    "approval_required": True,
                    "capital_execution": False
                },
                "approval_required_for_outbound_action": True,
                "capital_execution": False,
                "autonomous_execution": False
            },
            "approval_centre": {
                "status": "Waiting for Gareth Approval",
                "pending_count": 1,
                "queue": [
                    {
                        "approval_id": "approval-glirn-123",
                        "opportunity_id": "glirn-test-001",
                        "title": "Private Equity Partner Search",
                        "allowed_actions": ["approve", "reject", "monitor"],
                        "approval_reason_required": True,
                        "outbound_action_locked": True,
                        "candidate_introduction_locked": True,
                        "client_engagement_locked": True,
                        "fee_negotiation_locked": True,
                        "capital_execution": False
                    }
                ],
                "locks": {
                    "outbound_action_locked": True,
                    "candidate_introduction_locked": True,
                    "client_engagement_locked": True,
                    "fee_negotiation_locked": True
                },
                "capital_execution": False,
                "autonomous_execution": False
            },
            "compliance_core": {
                "status": "Compliance-First Controls Active",
                "candidate_consent_ledger": [],
                "client_consent_terms_status": [],
                "jurisdiction_compliance_profile": [],
                "data_retention_status": [],
                "deletion_request_workflow": [],
                "consent_expiry_alerts": [],
                "missing_consent_alerts": [],
                "compliance_alerts": [],
                "restricted_outbound_actions": [],
                "compliance_readiness_score": 100,
                "capital_execution": False,
                "autonomous_execution": False
            },
            "executive_search": {
                "status": "Executive Search Engine Active",
                "top_executive_opportunities": [
                    {
                        "opportunity_id": "glirn-test-001",
                        "title": "Private Equity Partner Search",
                        "workflow": "Partner Search workflow",
                        "candidate_seniority_classification": "Partner",
                        "estimated_placement_fee": 85000,
                        "estimated_retainer_fee": 28330.5,
                        "premium_opportunity": True,
                        "high_fee_priority_score": 80,
                        "executive_candidate_outreach_allowed": True,
                        "client_engagement_allowed": True,
                        "retained_search_proposal_requires_gareth_approval": True,
                        "outbound_action_blocked": False,
                        "capital_execution": False,
                        "autonomous_execution": False
                    }
                ],
                "dave_recommends_first": {
                    "title": "Private Equity Partner Search",
                    "estimated_placement_fee": 85000,
                    "estimated_retainer_fee": 28330.5,
                    "premium_opportunity": True,
                },
                "retained_search_proposal_requires_gareth_approval": True,
                "capital_execution": False,
                "autonomous_execution": False
            },
            "intelligence_network": {
                "status": "Legal Intelligence Network Active",
                "top_salary_signals": [
                    {
                        "practice_area": "Private Equity",
                        "estimated_salary": 283333.33,
                        "candidate_personal_data_included": False,
                        "capital_execution": False
                    }
                ],
                "hot_practice_areas": [
                    {
                        "practice_area": "Private Equity",
                        "growth_score": 88
                    }
                ],
                "growing_jurisdictions": [
                    {
                        "jurisdiction": "England & Wales",
                        "demand_score": 90
                    }
                ],
                "hiring_trend_alerts": [
                    {
                        "title": "Rising demand for Private Equity"
                    }
                ],
                "client_intelligence_hook": "Use intelligence as the client hook.",
                "dave_recommends_first": {
                    "recommendation": "Lead with intelligence, then qualify recruitment demand."
                },
                "client_facing_report_generation_requires_gareth_approval": True,
                "candidate_personal_data_exposed_without_consent": False,
                "capital_execution": False,
                "autonomous_execution": False
            },
            "intelligence_report": {
                "status": "Legal Intelligence Network Active"
            },
            "commercial_revenue_engine": {
                "status": "Commercial Revenue Controls Active",
                "estimated_revenue_pipeline": 85000,
                "commercial_pipeline": [
                    {
                        "opportunity_id": "glirn-test-001",
                        "title": "Private Equity Partner Search",
                        "fee_type": "executive search fee",
                        "estimated_revenue": 85000,
                        "invoice_readiness": "ready",
                        "client_terms_readiness": "recorded",
                        "candidate_submission_allowed": True,
                        "fee_proposal_requires_gareth_approval": True,
                        "awaiting_gareth_approval": True,
                        "capital_execution": False,
                        "autonomous_execution": False
                    }
                ],
                "highest_fee_opportunity": {
                    "opportunity_id": "glirn-test-001",
                    "title": "Private Equity Partner Search",
                    "fee_type": "executive search fee",
                    "estimated_revenue": 85000,
                    "invoice_readiness": "ready"
                },
                "dave_recommends_first": {
                    "recommendation": "Request Gareth approval for premium fee negotiation.",
                    "awaiting_gareth_approval": True
                },
                "awaiting_gareth_approval": True,
                "capital_execution": False,
                "autonomous_execution": False
            },
            "commercial_pipeline": [],
            "client_acquisition_engine": {
                "status": "Client Acquisition Controls Active",
                "top_target_clients": [
                    {
                        "client_id": "client-stub-001",
                        "client_name": "Client Firm A",
                        "target_client_type": "Private equity-backed companies",
                        "hiring_likelihood_score": 78,
                        "estimated_fee_potential": 85000,
                        "preferred_practice_area_match": "Private Equity",
                        "client_readiness_status": "ready",
                        "outreach_approval_required": True,
                        "candidate_details_allowed": True,
                        "capital_execution": False
                    }
                ],
                "highest_fee_potential_client": {
                    "client_id": "client-stub-001",
                    "client_name": "Client Firm A",
                    "estimated_fee_potential": 85000
                },
                "target_client_profiles": [],
                "outreach_approval_queue": [],
                "dave_recommends_first": {
                    "recommendation": "Review top target client before any outreach.",
                    "awaiting_gareth_approval": True
                },
                "awaiting_gareth_approval": True,
                "capital_execution": False,
                "autonomous_execution": False
            },
            "candidate_discovery_engine": {
                "status": "Candidate Discovery Controls Active",
                "top_candidate_opportunities": [
                    {
                        "candidate_id": "candidate-stub-001",
                        "candidate_name": "Candidate A",
                        "candidate_seniority_classification": "Partner",
                        "estimated_placement_value": 85000,
                        "consent_readiness_status": "active",
                        "practice_area_match_score": 94,
                        "candidate_priority_score": 82,
                        "outreach_approval_required": True,
                        "candidate_details_allowed": True,
                        "capital_execution": False
                    }
                ],
                "highest_estimated_placement_value": {
                    "candidate_id": "candidate-stub-001",
                    "candidate_name": "Candidate A",
                    "estimated_placement_value": 85000
                },
                "candidate_profiles": [],
                "dave_recommends_first": {
                    "recommendation": "Review top candidate before any outreach or profile activation.",
                    "awaiting_gareth_approval": True
                },
                "awaiting_gareth_approval": True,
                "capital_execution": False,
                "autonomous_execution": False
            },
            "matching_engine": {
                "status": "Matching & Placement Controls Active",
                "top_ranked_placement_matches": [
                    {
                        "match_id": "match-candidate-stub-001-client-stub-001",
                        "candidate_name": "Candidate A",
                        "client_name": "Client Firm A",
                        "match_revenue_score": 84,
                        "placement_probability_score": 78,
                        "candidate_consent_status": "active",
                        "client_terms_status": "recorded",
                        "awaiting_gareth_approval": True,
                        "capital_execution": False
                    }
                ],
                "ranked_placement_matches": [
                    {
                        "match_id": "match-candidate-stub-001-client-stub-001",
                        "candidate_name": "Candidate A",
                        "client_name": "Client Firm A",
                        "match_revenue_score": 84,
                        "placement_probability_score": 78,
                        "candidate_consent_status": "active",
                        "client_terms_status": "recorded",
                        "match_active_allowed": True,
                        "client_facing_allowed": True,
                        "candidate_details_share_allowed": False,
                        "placement_action_requires_gareth_approval": True,
                        "awaiting_gareth_approval": True,
                        "capital_execution": False
                    }
                ],
                "highest_match_revenue_score": {
                    "match_id": "match-candidate-stub-001-client-stub-001",
                    "match_revenue_score": 84
                },
                "dave_recommends_first": {
                    "recommendation": "Request Gareth approval before sharing any candidate details.",
                    "awaiting_gareth_approval": True
                },
                "awaiting_gareth_approval": True,
                "capital_execution": False,
                "autonomous_execution": False
            },
            "executive_autopilot": {
                "engine": "executive_autopilot",
                "status": "Executive Autopilot Waiting for Gareth Approval",
                "top_opportunity": {
                    "opportunity_id": "glirn-test-001",
                    "title": "Private Equity Partner Search",
                    "expected_fee_value": 85000
                },
                "top_candidate": {
                    "candidate_id": "candidate-stub-001",
                    "candidate_name": "Candidate A",
                    "estimated_placement_value": 85000
                },
                "top_client": {
                    "client_id": "client-stub-001",
                    "client_name": "Client Firm A",
                    "estimated_fee_potential": 85000
                },
                "top_placement_match": {
                    "match_id": "match-candidate-stub-001-client-stub-001",
                    "candidate_name": "Candidate A",
                    "client_name": "Client Firm A",
                    "placement_probability_score": 78
                },
                "highest_estimated_fee": 85000,
                "highest_placement_probability": 78,
                "compliance_alerts": [],
                "compliance_gate_clear": True,
                "top_match_gate_clear": True,
                "gareth_approval_queue": [
                    {
                        "queue_type": "Placement Match Review",
                        "target_id": "match-candidate-stub-001-client-stub-001",
                        "approval_required": True
                    }
                ],
                "approval_queue_count": 1,
                "ranked_recommendations": [
                    {
                        "recommendation_type": "Top Placement Match",
                        "title": "Candidate A to Client Firm A",
                        "score": 84,
                        "approval_required": True
                    }
                ],
                "dave_recommends_first": {
                    "recommendation": "Review the highest-ranked GLIRN placement route.",
                    "recommended_focus": "Top Placement Match",
                    "title": "Candidate A to Client Firm A",
                    "approval_required": True
                },
                "human_approval_mandatory": True,
                "capital_execution": False,
                "autonomous_execution": False
            },
            "live_data_readiness": {
                "engine": "live_data_readiness",
                "status": "Live Data Readiness Controls Active",
                "source_registry": [
                    {
                        "source_id": "source-candidate-csv-import",
                        "source_name": "Human-approved candidate CSV import",
                        "source_type": "manual_csv",
                        "jurisdiction": "England & Wales",
                        "contains_personal_data": True,
                        "requires_candidate_consent": True,
                        "requires_client_terms": False,
                        "lawful_basis_required": True,
                        "lawful_basis_readiness": "ready",
                        "human_approval_required": True,
                        "status": "proposed",
                        "risk_level": "medium",
                        "compliance_readiness_score": 55,
                        "ingestion_readiness_status": "pending_gareth_approval",
                        "capital_execution": False,
                    }
                ],
                "source_readiness_summary": {
                    "total_sources": 1,
                    "approved_sources": 0,
                    "pending_sources": 1,
                    "blocked_sources": 0,
                    "not_ready_sources": 1,
                    "external_connections_enabled": False,
                    "scraping_enabled": False,
                    "live_fetching_enabled": False,
                    "ingestion_enabled": False,
                },
                "blocked_sources": [],
                "approved_sources": [],
                "pending_sources": [
                    {
                        "source_id": "source-candidate-csv-import",
                        "source_name": "Human-approved candidate CSV import",
                    }
                ],
                "dave_recommends_first": {
                    "recommendation": "Review proposed sources before approving any future data integration.",
                    "human_approval_required": True,
                    "capital_execution": False,
                },
                "human_approval_required": True,
                "capital_execution": False,
                "autonomous_execution": False
            },
            "integration_governance": {
                "engine": "integration_governance",
                "status": "Integration Governance Controls Active",
                "integration_registry": [
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
                        "human_approval_required": True,
                        "status": "pending",
                        "compliance_score": 100,
                        "approval_score": 35,
                        "readiness_score": 63.25,
                        "risk_score": 55,
                        "governance_status": "pending_gareth_approval",
                        "capital_execution": False,
                    }
                ],
                "approved_integrations": [],
                "blocked_integrations": [],
                "pending_integrations": [
                    {
                        "integration_id": "integration-manual-csv-upload",
                        "integration_name": "Manual CSV Upload",
                    }
                ],
                "governance_alerts": [],
                "dave_recommends_first": {
                    "recommendation": "Keep all future integrations inactive until Gareth approves governance.",
                    "human_approval_required": True,
                    "capital_execution": False,
                },
                "human_approval_required": True,
                "external_connections_enabled": False,
                "scraping_enabled": False,
                "outbound_connections_enabled": False,
                "autonomous_activation_enabled": False,
                "capital_execution": False,
                "autonomous_execution": False
            },
            "deployment_readiness": {
                "engine": "deployment_readiness",
                "status": "Deployment Readiness Assessment Active",
                "technical_readiness": 90,
                "compliance_readiness": 80,
                "commercial_readiness": 75,
                "operational_readiness": 80,
                "documentation_readiness": 85,
                "integration_readiness": 45,
                "readiness_percentage": 75.2,
                "readiness_score": 75.2,
                "readiness_grade": "B",
                "critical_gaps": [
                    "Keep high-risk integrations blocked before launch."
                ],
                "recommended_actions": [
                    "Review all compliance, source, and integration gates."
                ],
                "launch_checklist": [
                    {
                        "item": "platform status",
                        "status": "ready",
                        "detail": "Core GLIRN dashboard and engines are available."
                    },
                    {
                        "item": "audit status",
                        "status": "active",
                        "detail": "Approval and governance actions are audit logged."
                    }
                ],
                "dave_recommends_first": {
                    "recommendation": "Do not deploy externally until Gareth reviews critical gaps.",
                    "human_approval_required": True,
                    "capital_execution": False,
                },
                "deployment_actions_enabled": False,
                "external_connections_enabled": False,
                "assessment_only": True,
                "human_approval_mandatory": True,
                "capital_execution": False,
                "autonomous_execution": False
            },
            "operations_command_centre": {
                "engine": "operations_command_centre",
                "status": "Operations Command Centre Active",
                "executive_summary": {
                    "top_opportunity": {
                        "title": "Private Equity Partner Search"
                    },
                    "top_candidate": {
                        "candidate_name": "Candidate A"
                    },
                    "top_client": {
                        "client_name": "Client Firm A"
                    },
                    "top_placement_match": {
                        "match_id": "match-candidate-stub-001-client-stub-001"
                    },
                    "highest_estimated_fee": 85000,
                    "highest_placement_probability": 78,
                },
                "key_metrics": {
                    "total_opportunities": 1,
                    "total_candidates": 1,
                    "total_clients": 1,
                    "total_matches": 1,
                    "estimated_revenue_pipeline": 85000,
                    "compliance_alerts": 0,
                    "pending_gareth_approvals": 1,
                    "readiness_score": 75.2,
                },
                "platform_health": {
                    "executive_autopilot": "Executive Autopilot Waiting for Gareth Approval",
                    "opportunity_radar": "Legal Opportunity Radar Active",
                    "client_acquisition": "Client Acquisition Controls Active",
                    "candidate_discovery": "Candidate Discovery Controls Active",
                    "matching_engine": "Matching & Placement Controls Active",
                    "commercial_revenue_engine": "Commercial Revenue Controls Active",
                    "compliance_core": "Compliance-First Controls Active",
                    "deployment_readiness": "Deployment Readiness Assessment Active",
                    "read_only": True,
                    "external_connections_enabled": False,
                },
                "dave_recommends_first": {
                    "recommendation": "Work through Gareth approval queue before client or candidate action.",
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
                "autonomous_execution": False
            },
            "executive_summary": {
                "top_opportunity": {
                    "title": "Private Equity Partner Search"
                },
            },
            "key_metrics": {
                "total_opportunities": 1,
                "total_candidates": 1,
                "total_clients": 1,
                "total_matches": 1,
                "estimated_revenue_pipeline": 85000,
                "compliance_alerts": 0,
                "pending_gareth_approvals": 1,
                "readiness_score": 75.2,
            },
            "platform_health": {
                "deployment_readiness": "Deployment Readiness Assessment Active",
                "read_only": True,
            },
            "daily_executive_briefing": {
                "engine": "daily_executive_briefing",
                "status": "Daily Executive Briefing Ready",
                "top_3_opportunities": [
                    {
                        "opportunity_id": "glirn-test-001",
                        "title": "Private Equity Partner Search",
                    }
                ],
                "top_3_risks": [
                    {
                        "risk_type": "deployment_readiness_gap",
                        "description": "Keep high-risk integrations blocked before launch.",
                    }
                ],
                "top_3_revenue_actions": [
                    {
                        "opportunity_id": "glirn-test-001",
                        "title": "Private Equity Partner Search",
                        "fee_type": "executive search fee",
                        "estimated_revenue": 85000,
                        "recommended_action": "Review fee opportunity with Gareth approval.",
                    }
                ],
                "pending_gareth_approvals": [
                    {
                        "queue_type": "Placement Match Review",
                        "target_id": "match-candidate-stub-001-client-stub-001",
                    }
                ],
                "compliance_warnings": [],
                "dave_recommends_today": {
                    "recommendation": "Clear the highest-priority Gareth approval items before client or candidate action.",
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
            },
            "intelligence_review_engine": {
                "engine": "intelligence_review_engine",
                "status": "Automated Intelligence Review Draft Ready",
                "review_generation_status": "generated_pending_gareth_approval",
                "generated_reviews": [
                    {
                        "review_id": "glirn-review-001",
                        "title": "GLIRN Senior Legal Hiring Intelligence Review - Client Firm A",
                        "target_client_profile": "Client Firm A",
                        "practice_area": "Private Equity",
                        "jurisdiction": "England & Wales",
                        "approval_status": "pending_gareth_approval",
                        "client_ready": False,
                        "client_delivery_allowed": False,
                        "compliance_status": "controlled",
                        "candidate_personal_data_included": True,
                        "candidate_personal_data_blocked": False,
                        "recommended_action": "start search",
                    }
                ],
                "pending_review_approvals": [
                    {
                        "review_id": "glirn-review-001",
                        "title": "GLIRN Senior Legal Hiring Intelligence Review - Client Firm A",
                        "approval_required": True,
                    }
                ],
                "latest_generated_review": {
                    "review_id": "glirn-review-001",
                    "title": "GLIRN Senior Legal Hiring Intelligence Review - Client Firm A",
                    "target_client_profile": "Client Firm A",
                    "practice_area": "Private Equity",
                    "jurisdiction": "England & Wales",
                    "approval_status": "pending_gareth_approval",
                    "compliance_status": "controlled",
                    "recommended_action": "start search",
                },
                "dave_recommends_first": {
                    "recommendation": "Review the generated intelligence draft before any client-facing use.",
                    "review_id": "glirn-review-001",
                    "human_approval_required": True,
                    "capital_execution": False,
                },
                "client_delivery_enabled": False,
                "human_approval_mandatory": True,
                "capital_execution": False,
                "autonomous_execution": False,
            },
            "generated_reviews": [
                {
                    "review_id": "glirn-review-001",
                    "title": "GLIRN Senior Legal Hiring Intelligence Review - Client Firm A",
                }
            ],
            "pending_review_approvals": [
                {
                    "review_id": "glirn-review-001",
                    "approval_required": True,
                }
            ],
            "review_generation_status": "generated_pending_gareth_approval",
            "latest_generated_review": {
                "review_id": "glirn-review-001",
                "title": "GLIRN Senior Legal Hiring Intelligence Review - Client Firm A",
            },
            "deliverable_factory": {
                "engine": "deliverable_factory",
                "status": "Client Deliverable Drafts Ready",
                "deliverable_generation_status": "generated_pending_gareth_approval",
                "generated_deliverables": [
                    {
                        "deliverable_id": "glirn-deliverable-search-mandate-001",
                        "deliverable_type": "Search Mandate Proposal",
                        "title": "Search Mandate Proposal - Client Firm A",
                        "target_client_profile": "Client Firm A",
                        "approval_status": "pending_gareth_approval",
                        "client_ready": False,
                        "client_delivery_allowed": False,
                        "compliance_status": "controlled",
                        "recommended_action": "review",
                        "candidate_personal_data_included": False,
                        "candidate_personal_data_blocked": True,
                    }
                ],
                "pending_deliverable_approvals": [
                    {
                        "deliverable_id": "glirn-deliverable-search-mandate-001",
                        "title": "Search Mandate Proposal - Client Firm A",
                        "deliverable_type": "Search Mandate Proposal",
                        "approval_required": True,
                    }
                ],
                "latest_deliverable": {
                    "deliverable_id": "glirn-deliverable-search-mandate-001",
                    "deliverable_type": "Search Mandate Proposal",
                    "title": "Search Mandate Proposal - Client Firm A",
                    "target_client_profile": "Client Firm A",
                    "approval_status": "pending_gareth_approval",
                    "client_ready": False,
                    "client_delivery_allowed": False,
                    "compliance_status": "controlled",
                    "recommended_action": "review",
                },
                "deliverable_status": "pending_gareth_approval",
                "dave_recommends_first": {
                    "recommendation": "Review generated client deliverables before any client-facing use.",
                    "deliverable_id": "glirn-deliverable-search-mandate-001",
                    "human_approval_required": True,
                    "capital_execution": False,
                },
                "client_delivery_enabled": False,
                "human_approval_mandatory": True,
                "capital_execution": False,
                "autonomous_execution": False,
            },
            "generated_deliverables": [
                {
                    "deliverable_id": "glirn-deliverable-search-mandate-001",
                    "title": "Search Mandate Proposal - Client Firm A",
                }
            ],
            "pending_deliverable_approvals": [
                {
                    "deliverable_id": "glirn-deliverable-search-mandate-001",
                    "approval_required": True,
                }
            ],
            "latest_deliverable": {
                "deliverable_id": "glirn-deliverable-search-mandate-001",
                "title": "Search Mandate Proposal - Client Firm A",
            },
            "deliverable_status": "pending_gareth_approval",
            "approval_to_action_workflow": {
                "engine": "approval_to_action_workflow",
                "status": "Approval-to-Action Controls Active",
                "draft_status": "generated_drafts_pending_review",
                "approval_status": "pending_gareth_approval",
                "client_ready_status": "not_client_ready_without_gareth_approval",
                "action_readiness_status": "human_review_required",
                "pending_gareth_approval": [
                    {
                        "item_id": "glirn-deliverable-search-mandate-001",
                        "item_type": "client_deliverable",
                        "title": "Search Mandate Proposal - Client Firm A",
                        "draft_status": "generated_draft",
                        "approval_status": "pending_gareth_approval",
                        "client_ready_status": "not_client_ready",
                        "action_readiness_status": "awaiting_gareth_approval",
                        "client_ready": False,
                        "human_use_ready": False,
                    }
                ],
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
            },
            "approved_for_human_use": [],
            "pending_gareth_approval": [
                {
                    "item_id": "glirn-deliverable-search-mandate-001",
                    "client_ready": False,
                }
            ],
            "rejected_items": [],
            "monitored_items": [],
            "revenue_command_centre": {
                "engine": "revenue_command_centre",
                "status": "Revenue Command Centre Active",
                "revenue_pipeline": [
                    {
                        "opportunity_id": "glirn-pe-partner-london-001",
                        "title": "Private Equity Partner Search",
                        "fee_type": "executive search fee",
                        "estimated_revenue": 85000,
                        "invoice_readiness": "blocked",
                    }
                ],
                "total_revenue_pipeline": 85000,
                "estimated_placement_fee_pipeline": 85000,
                "estimated_intelligence_review_revenue": 500,
                "approved_opportunities_count": 0,
                "approved_deliverables_count": 0,
                "highest_fee_opportunity": {
                    "opportunity_id": "glirn-pe-partner-london-001",
                    "title": "Private Equity Partner Search",
                    "estimated_revenue": 85000,
                },
                "fastest_revenue_opportunity": {
                    "opportunity_id": "glirn-pe-partner-london-001",
                    "title": "Private Equity Partner Search",
                    "invoice_readiness": "blocked",
                },
                "revenue_readiness_score": 87,
                "revenue_funnel": [
                    {
                        "stage": "Opportunity",
                        "item_count": 1,
                        "estimated_value": 85000,
                        "readiness_status": "ranked_pending_gareth_review",
                    }
                ],
                "top_revenue_opportunities": [
                    {
                        "opportunity_id": "glirn-pe-partner-london-001",
                        "title": "Private Equity Partner Search",
                        "estimated_revenue": 85000,
                    }
                ],
                "dave_recommends_first": {
                    "recommendation": "Review Private Equity Partner Search first.",
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
                "human_approval_mandatory": True,
                "capital_execution": False,
                "autonomous_execution": False,
            },
            "revenue_pipeline": [
                {
                    "opportunity_id": "glirn-pe-partner-london-001",
                    "title": "Private Equity Partner Search",
                    "estimated_revenue": 85000,
                }
            ],
            "revenue_funnel": [
                {
                    "stage": "Opportunity",
                    "item_count": 1,
                    "estimated_value": 85000,
                    "readiness_status": "ranked_pending_gareth_review",
                }
            ],
            "highest_fee_opportunity": {
                "opportunity_id": "glirn-pe-partner-london-001",
                "title": "Private Equity Partner Search",
                "estimated_revenue": 85000,
            },
            "fastest_revenue_opportunity": {
                "opportunity_id": "glirn-pe-partner-london-001",
                "title": "Private Equity Partner Search",
                "invoice_readiness": "blocked",
            },
            "revenue_readiness_score": 87,
            "top_revenue_opportunities": [
                {
                    "opportunity_id": "glirn-pe-partner-london-001",
                    "title": "Private Equity Partner Search",
                    "estimated_revenue": 85000,
                }
            ],
            "first_client_readiness_gate": {
                "engine": "first_client_readiness_gate",
                "status": "First Client Readiness Gate Active",
                "readiness_checks": [
                    {
                        "item_id": "first-client-glirn-pe-partner-london-001",
                        "opportunity_id": "glirn-pe-partner-london-001",
                        "title": "Private Equity Partner Search",
                        "missing_checks": ["client_terms_ready"],
                        "gareth_approval_status": "required",
                        "overall_first_client_readiness_score": 72,
                        "readiness_recommendation": "blocked_missing_terms",
                        "human_action_ready": False,
                    }
                ],
                "first_client_ready_items": [],
                "blocked_first_client_items": [
                    {
                        "item_id": "first-client-glirn-pe-partner-london-001",
                        "title": "Private Equity Partner Search",
                        "readiness_recommendation": "blocked_missing_terms",
                    }
                ],
                "monitored_first_client_items": [],
                "readiness_recommendation": "blocked_missing_terms",
                "overall_first_client_readiness_score": 72,
                "dave_recommends_first": {
                    "recommendation": "Review Private Equity Partner Search first.",
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
                "human_approval_mandatory": True,
                "capital_execution": False,
                "autonomous_execution": False,
            },
            "readiness_checks": [
                {
                    "item_id": "first-client-glirn-pe-partner-london-001",
                    "title": "Private Equity Partner Search",
                }
            ],
            "first_client_ready_items": [],
            "blocked_first_client_items": [
                {
                    "item_id": "first-client-glirn-pe-partner-london-001",
                    "title": "Private Equity Partner Search",
                }
            ],
            "monitored_first_client_items": [],
            "readiness_recommendation": "blocked_missing_terms",
            "overall_first_client_readiness_score": 72,
            "launch_readiness_command_centre": {
                "engine": "launch_readiness_command_centre",
                "status": "Launch Readiness Command Centre Active",
                "launch_readiness_score": 68,
                "launch_readiness_grade": "blocked",
                "overall_launch_readiness_score": 68,
                "brand_score": 100,
                "commercial_score": 50,
                "compliance_score": 80,
                "revenue_score": 85,
                "operational_score": 45,
                "launch_ready_items": [
                    {"category": "brand_readiness", "status": "ready"}
                ],
                "launch_blocked_items": [
                    {"category": "payment_process_readiness", "reason": "missing payment process"}
                ],
                "launch_missing_items": [
                    {"gap_code": "payment_process_readiness", "description": "missing payment process"}
                ],
                "launch_recommended_next_action": "confirm_payment_process",
                "gareth_approval_status": "required",
                "dave_recommends_first": {
                    "recommendation": "Next launch action: confirm_payment_process.",
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
                "human_approval_mandatory": True,
                "capital_execution": False,
                "autonomous_execution": False,
            },
            "launch_readiness_score": 68,
            "launch_readiness_grade": "blocked",
            "launch_ready_items": [
                {"category": "brand_readiness", "status": "ready"}
            ],
            "launch_blocked_items": [
                {"category": "payment_process_readiness", "reason": "missing payment process"}
            ],
            "launch_missing_items": [
                {"gap_code": "payment_process_readiness", "description": "missing payment process"}
            ],
            "launch_recommended_next_action": "confirm_payment_process",
            "invoice_drafting_engine": {
                "engine": "invoice_drafting_engine",
                "status": "Invoice Drafting Engine Active",
                "invoice_drafts": [
                    {
                        "invoice_number": "GLIRN-INV-001",
                        "invoice_date": "2026-06-05",
                        "supply_date": "2026-06-05",
                        "seller_name": "David Sanson",
                        "seller_business_name": "Global Legal Intelligence & Recruitment Network",
                        "seller_contact_details": "To be confirmed by Gareth Price before manual sending.",
                        "customer_name": "Client Firm A",
                        "customer_address": "To be confirmed manually before sending.",
                        "service_description": "Private Equity Partner Search",
                        "fee_type": "executive search fee",
                        "amount": 85000,
                        "VAT_status": "VAT not applied - confirm VAT position with Gareth Price before sending.",
                        "VAT_amount_if_applicable": 0,
                        "total_amount_due": 85000,
                        "payment_method_options": [
                            "PayPal Business",
                            "Revolut UK Bank Transfer",
                        ],
                        "payment_due_date": "To be confirmed manually before sending.",
                        "payment_reference": "GLIRN-001",
                        "notes": "Draft only. Gareth must approve, send, and confirm payment manually.",
                        "approval_status": "pending_gareth_approval",
                    }
                ],
                "invoice_readiness_status": "drafts_pending_gareth_approval",
                "pending_invoice_approvals": [
                    {
                        "invoice_number": "GLIRN-INV-001",
                        "approval_required": True,
                    }
                ],
                "approved_invoice_drafts": [],
                "supported_payment_methods": [
                    "PayPal Business",
                    "Revolut UK Bank Transfer",
                ],
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
            },
            "invoice_drafts": [
                {
                    "invoice_number": "GLIRN-INV-001",
                    "customer_name": "Client Firm A",
                }
            ],
            "pending_invoice_approvals": [
                {
                    "invoice_number": "GLIRN-INV-001",
                    "approval_required": True,
                }
            ],
            "invoice_readiness_status": "drafts_pending_gareth_approval",
            "client_terms_drafting_engine": {
                "engine": "client_terms_drafting_engine",
                "status": "Client Terms Drafting Engine Active",
                "client_terms_drafts": [
                    {
                        "terms_id": "GLIRN-TERMS-REVIEW-001",
                        "terms_type": "GBP 500 GLIRN Senior Legal Hiring Intelligence Review",
                        "client_name_placeholder": "Client Firm A",
                        "service_description": "Fixed-scope GLIRN Senior Legal Hiring Intelligence Review.",
                        "scope_of_work": "Scope to be reviewed by Gareth.",
                        "fee_structure": "GBP 500 fixed review fee.",
                        "payment_method_options": [
                            "PayPal Business",
                            "Revolut UK Bank Transfer",
                        ],
                        "payment_timing": "To be confirmed manually.",
                        "no_guarantee_of_placement_wording": "No guarantee of placement.",
                        "confidentiality_wording": "Information should be confidential.",
                        "candidate_consent_requirement": "Candidate details require active consent.",
                        "client_terms_requirement_before_candidate_details": "Client terms required before candidate details.",
                        "human_approval_statement": "Gareth approval required.",
                        "data_protection_note": "No candidate personal data without consent.",
                        "cancellation_note": "To be confirmed manually.",
                        "governing_jurisdiction_placeholder": "To be confirmed manually.",
                        "gareth_approval_status": "required",
                    }
                ],
                "pending_terms_approvals": [
                    {
                        "terms_id": "GLIRN-TERMS-REVIEW-001",
                        "approval_required": True,
                    }
                ],
                "approved_terms_drafts": [],
                "terms_readiness_status": "drafts_pending_gareth_approval",
                "automatic_sending_enabled": False,
                "automatic_agreement_enabled": False,
                "automatic_contract_acceptance_enabled": False,
                "esignature_integration_enabled": False,
                "external_integrations_enabled": False,
                "solicitor_approved_claim": False,
                "human_approval_mandatory": True,
                "capital_execution": False,
                "autonomous_execution": False,
            },
            "client_terms_drafts": [
                {
                    "terms_id": "GLIRN-TERMS-REVIEW-001",
                    "terms_type": "GBP 500 GLIRN Senior Legal Hiring Intelligence Review",
                }
            ],
            "pending_terms_approvals": [
                {
                    "terms_id": "GLIRN-TERMS-REVIEW-001",
                    "approval_required": True,
                }
            ],
            "approved_terms_drafts": [],
            "terms_readiness_status": "drafts_pending_gareth_approval",
            "candidate_consent_management_engine": {
                "engine": "candidate_consent_management_engine",
                "status": "Candidate Consent Management Engine Active",
                "candidate_consent_records": [
                    {
                        "candidate_id": "candidate-stub-001",
                        "candidate_name_placeholder": "Candidate A",
                        "jurisdiction": "England & Wales",
                        "consent_status": "active",
                        "consent_date": "recorded in consent ledger",
                        "consent_expiry_date": "2026-12-31T23:59:59+00:00",
                        "consent_scope": "candidate_introduction",
                        "permitted_use": "candidate introduction",
                        "approval_status": "recorded",
                        "audit_reference": "consent-candidate-stub-001",
                    },
                    {
                        "candidate_id": "candidate-stub-002",
                        "candidate_name_placeholder": "Candidate B",
                        "jurisdiction": "jurisdiction to be confirmed manually",
                        "consent_status": "draft",
                        "consent_date": "to be confirmed manually",
                        "consent_expiry_date": None,
                        "consent_scope": "none",
                        "permitted_use": "none until manually confirmed",
                        "approval_status": "pending_gareth_approval",
                        "audit_reference": "consent-candidate-stub-002",
                    },
                ],
                "pending_candidate_consents": [
                    {"candidate_id": "candidate-stub-002", "consent_status": "draft"}
                ],
                "active_candidate_consents": [
                    {"candidate_id": "candidate-stub-001", "consent_status": "active"}
                ],
                "expired_candidate_consents": [],
                "consent_readiness_status": "pending_manual_consent",
                "candidate_consent_readiness": 50,
                "consent_expiry_alerts": [],
                "consent_compliance_status": "pending_manual_consent",
                "candidate_contact_enabled": False,
                "automated_consent_collection_enabled": False,
                "automated_consent_activation_enabled": False,
                "external_integrations_enabled": False,
                "scraping_enabled": False,
                "live_data_fetching_enabled": False,
                "human_approval_mandatory": True,
                "capital_execution": False,
                "autonomous_execution": False,
            },
            "candidate_consent_records": [
                {"candidate_id": "candidate-stub-001", "consent_status": "active"}
            ],
            "pending_candidate_consents": [
                {"candidate_id": "candidate-stub-002", "consent_status": "draft"}
            ],
            "active_candidate_consents": [
                {"candidate_id": "candidate-stub-001", "consent_status": "active"}
            ],
            "expired_candidate_consents": [],
            "consent_readiness_status": "pending_manual_consent",
            "manual_delivery_control_engine": {
                "engine": "manual_delivery_control_engine",
                "status": "Manual Delivery Control Engine Active",
                "delivery_ready_items": [],
                "blocked_delivery_items": [
                    {
                        "delivery_id": "delivery-glirn-deliverable-search-mandate-001",
                        "source_item_id": "glirn-deliverable-search-mandate-001",
                        "title": "Search Mandate Proposal - Client Firm A",
                        "missing_checks": ["gareth_approval", "client_terms_readiness"],
                        "manual_delivery_status": "blocked",
                    }
                ],
                "delivery_checklist": {
                    "gareth_approval": False,
                    "client_terms_readiness": False,
                    "payment_readiness": False,
                    "compliance_readiness": True,
                    "consent_readiness": True,
                    "deliverable_approved_status": False,
                    "no_candidate_personal_data_unless_consent_active": True,
                },
                "manual_delivery_status": "blocked_pending_manual_checks",
                "pending_delivery_approvals": [
                    {
                        "delivery_id": "delivery-glirn-deliverable-search-mandate-001",
                        "manual_delivery_status": "blocked",
                    }
                ],
                "client_email_enabled": False,
                "external_upload_enabled": False,
                "candidate_contact_enabled": False,
                "automatic_sending_enabled": False,
                "human_delivery_only": True,
                "human_approval_mandatory": True,
                "capital_execution": False,
                "autonomous_execution": False,
            },
            "delivery_ready_items": [],
            "blocked_delivery_items": [
                {
                    "delivery_id": "delivery-glirn-deliverable-search-mandate-001",
                    "manual_delivery_status": "blocked",
                }
            ],
            "manual_delivery_status": "blocked_pending_manual_checks",
            "launch_compliance_validation_engine": {
                "engine": "launch_compliance_validation_engine",
                "status": "Launch Compliance Validation Engine Active",
                "compliance_validation_checks": [
                    {
                        "validation_id": "compliance-delivery-glirn-deliverable-search-mandate-001",
                        "source_item_id": "glirn-deliverable-search-mandate-001",
                        "title": "Search Mandate Proposal - Client Firm A",
                        "missing_compliance_checks": ["client_terms_status", "deliverable_approval_status"],
                        "compliance_validation_status": "blocked",
                        "compliance_recommendation": "blocked_missing_terms",
                        "compliance_risk_level": "blocked",
                        "gareth_approval_required": True,
                    }
                ],
                "compliance_ready_items": [],
                "compliance_blocked_items": [
                    {
                        "validation_id": "compliance-delivery-glirn-deliverable-search-mandate-001",
                        "compliance_validation_status": "blocked",
                    }
                ],
                "compliance_validation_status": "blocked_pending_compliance_checks",
                "compliance_recommendation": "blocked_missing_terms",
                "compliance_risk_level": "blocked",
                "overall_compliance_readiness_score": 45,
                "legal_advice_provided": False,
                "legal_certification_claimed": False,
                "global_legal_compliance_declared": False,
                "external_integrations_enabled": False,
                "human_approval_mandatory": True,
                "capital_execution": False,
                "autonomous_execution": False,
            },
            "compliance_validation_checks": [
                {
                    "validation_id": "compliance-delivery-glirn-deliverable-search-mandate-001",
                    "compliance_validation_status": "blocked",
                }
            ],
            "compliance_ready_items": [],
            "compliance_blocked_items": [
                {
                    "validation_id": "compliance-delivery-glirn-deliverable-search-mandate-001",
                    "compliance_validation_status": "blocked",
                }
            ],
            "compliance_validation_status": "blocked_pending_compliance_checks",
            "compliance_risk_level": "blocked",
            "compliance_recommendation": "blocked_missing_terms",
            "overall_compliance_readiness_score": 45,
            "first_prospect_selection_engine": {
                "engine": "first_prospect_selection_engine",
                "status": "First Prospect Selection Engine Active",
                "prospect_profiles": [
                    {
                        "prospect_id": "first-prospect-001",
                        "category": "Boutique Technology & AI Law Firms",
                        "revenue_potential_score": 78,
                        "ease_of_acquisition_score": 86,
                        "launch_readiness_score": 88,
                        "market_demand_score": 91,
                        "compliance_complexity_score": 76,
                        "overall_prospect_score": 86.4,
                        "launch_priority_score": 86.4,
                    }
                ],
                "prospect_rankings": [
                    {
                        "prospect_id": "first-prospect-001",
                        "category": "Boutique Technology & AI Law Firms",
                        "revenue_potential_score": 78,
                        "ease_of_acquisition_score": 86,
                        "launch_readiness_score": 88,
                        "market_demand_score": 91,
                        "compliance_complexity_score": 76,
                        "overall_prospect_score": 86.4,
                        "launch_priority_score": 86.4,
                    }
                ],
                "prospect_recommendations": {},
                "launch_priority_score": 86.4,
                "recommended_first_prospect": {
                    "prospect_id": "first-prospect-001",
                    "category": "Boutique Technology & AI Law Firms",
                    "revenue_potential_score": 78,
                    "launch_readiness_score": 88,
                    "overall_prospect_score": 86.4,
                    "reason": "High relevance to legal intelligence.",
                },
                "highest_revenue_prospect": {
                    "prospect_id": "first-prospect-002",
                    "category": "Corporate & M&A Firms",
                    "revenue_potential_score": 92,
                },
                "fastest_revenue_prospect": {
                    "prospect_id": "first-prospect-001",
                    "category": "Boutique Technology & AI Law Firms",
                    "ease_of_acquisition_score": 86,
                    "launch_readiness_score": 88,
                },
                "dave_recommends_first": {
                    "recommendation": "Start launch preparation with Boutique Technology & AI Law Firms.",
                    "reason": "High relevance to legal intelligence.",
                },
                "outreach_enabled": False,
                "candidate_contact_enabled": False,
                "client_contact_enabled": False,
                "external_integrations_enabled": False,
                "scraping_enabled": False,
                "live_data_fetching_enabled": False,
                "human_approval_mandatory": True,
                "capital_execution": False,
                "autonomous_execution": False,
            },
            "prospect_rankings": [
                {
                    "prospect_id": "first-prospect-001",
                    "category": "Boutique Technology & AI Law Firms",
                }
            ],
            "recommended_first_prospect": {
                "prospect_id": "first-prospect-001",
                "category": "Boutique Technology & AI Law Firms",
            },
            "highest_revenue_prospect": {
                "prospect_id": "first-prospect-002",
                "category": "Corporate & M&A Firms",
            },
            "fastest_revenue_prospect": {
                "prospect_id": "first-prospect-001",
                "category": "Boutique Technology & AI Law Firms",
            },
            "first_client_dry_run": {
                "engine": "first_client_dry_run",
                "status": "First Client Dry Run Complete",
                "dry_run_status": "completed_pending_gareth_approval",
                "dry_run_readiness_score": 100,
                "dry_run_artifacts": {
                    "intelligence_review": {
                        "artifact_id": "glirn-review-001",
                        "generated": True,
                    },
                    "client_deliverable": {
                        "artifact_id": "glirn-deliverable-search-mandate-001",
                        "generated": True,
                    },
                    "client_terms_draft": {
                        "artifact_id": "glirn-terms-review-001",
                        "generated": True,
                    },
                    "invoice_draft": {
                        "artifact_id": "GLIRN-INV-001",
                        "generated": True,
                    },
                    "candidate_consent_validation": {
                        "artifact_id": "candidate-stub-001",
                        "executed": True,
                    },
                    "manual_delivery_pack": {
                        "artifact_id": "delivery-glirn-deliverable-search-mandate-001",
                        "generated": True,
                    },
                    "launch_compliance_validation": {
                        "artifact_id": "compliance-delivery-glirn-deliverable-search-mandate-001",
                        "executed": True,
                    },
                },
                "gareth_approval_package": {
                    "package_id": "glirn-first-client-dry-run-package-001",
                    "approval_readiness_status": "ready_for_gareth_approval",
                    "gareth_approval_required": True,
                    "external_action_enabled": False,
                },
                "dry_run_report": {
                    "selected_prospect": "Boutique Technology & AI Law Firms",
                    "readiness_score": 100,
                    "approval_readiness_status": "ready_for_gareth_approval",
                },
                "latest_dry_run_report": {
                    "selected_prospect": "Boutique Technology & AI Law Firms",
                    "readiness_score": 100,
                    "approval_readiness_status": "ready_for_gareth_approval",
                },
                "dry_run_blockers": [],
                "dry_run_warnings": ["manual_delivery_gareth_approval"],
                "approval_readiness_status": "ready_for_gareth_approval",
                "outreach_enabled": False,
                "client_contact_enabled": False,
                "candidate_contact_enabled": False,
                "candidate_introduction_enabled": False,
                "delivery_enabled": False,
                "invoice_sending_enabled": False,
                "payment_collection_enabled": False,
                "external_integrations_enabled": False,
                "human_approval_mandatory": True,
                "capital_execution": False,
                "autonomous_execution": False,
            },
            "dry_run_status": "completed_pending_gareth_approval",
            "dry_run_readiness_score": 100,
            "latest_dry_run_report": {
                "selected_prospect": "Boutique Technology & AI Law Firms",
                "readiness_score": 100,
            },
            "dry_run_blockers": [],
            "dry_run_warnings": ["manual_delivery_gareth_approval"],
            "autonomous_internal_operations_orchestrator": {
                "engine": "autonomous_internal_operations_orchestrator",
                "status": "Autonomous Internal Operations Cycle Complete",
                "autonomous_cycle_status": "completed_pending_gareth_final_decision",
                "final_gareth_approval_packages": [
                    {
                        "package_id": "glirn-autonomous-final-package-001",
                        "recommended_prospect_profile": {
                            "prospect_id": "first-prospect-001",
                            "category": "Boutique Technology & AI Law Firms",
                        },
                        "recommended_offer": "GLIRN Senior Legal Hiring Intelligence Review",
                        "expected_revenue": 500,
                        "revenue_route": "Paid intelligence review with potential conversion into search mandate",
                        "intelligence_review_status": "generated_pending_gareth_approval",
                        "deliverable_status": "drafts_pending_gareth_approval",
                        "terms_status": "drafts_pending_gareth_approval",
                        "invoice_status": "drafts_pending_gareth_approval",
                        "consent_status": "pending_manual_consent",
                        "compliance_status": "blocked_pending_compliance_checks",
                        "delivery_pack_status": "blocked_pending_manual_checks",
                        "dry_run_status": "completed_pending_gareth_approval",
                        "blockers": [],
                        "warnings": ["manual_delivery_gareth_approval"],
                        "final_recommendation": "approve",
                        "gareth_final_decision_required": True,
                        "external_action_enabled": False,
                    }
                ],
                "autonomous_recommendation_queue": [
                    {
                        "queue_id": "glirn-autonomous-recommendation-001",
                        "package_id": "glirn-autonomous-final-package-001",
                        "recommendation": "approve",
                        "gareth_final_decision_required": True,
                    }
                ],
                "autonomous_blockers": [],
                "autonomous_warnings": ["manual_delivery_gareth_approval"],
                "dave_recommends_first": {
                    "recommendation": "Gareth should approve the final internal approval package.",
                },
                "client_contact_enabled": False,
                "candidate_contact_enabled": False,
                "deliverable_sending_enabled": False,
                "invoice_sending_enabled": False,
                "payment_collection_enabled": False,
                "contract_acceptance_enabled": False,
                "external_fee_proposal_enabled": False,
                "external_integrations_enabled": False,
                "human_approval_mandatory": True,
                "capital_execution": False,
                "autonomous_execution": False,
            },
            "autonomous_cycle_status": "completed_pending_gareth_final_decision",
            "final_gareth_approval_packages": [
                {
                    "package_id": "glirn-autonomous-final-package-001",
                    "final_recommendation": "approve",
                }
            ],
            "autonomous_recommendation_queue": [
                {
                    "queue_id": "glirn-autonomous-recommendation-001",
                    "recommendation": "approve",
                }
            ],
            "website_lead_intake_engine": {
                "engine": "website_lead_intake_engine",
                "status": "Website Lead Intake Engine Active",
                "public_leads": [
                    {
                        "lead_id": "public-lead-001",
                        "organisation": "Boutique AI Law LLP",
                        "prospect_type": "Boutique Technology & AI Law Firms",
                        "lead_type": "executive_search_lead",
                        "lead_route": "executive_search_review",
                        "lead_qualification_status": "qualified_for_gareth_review",
                        "lead_revenue_potential": 100,
                        "lead_compliance_status": "controlled_review_ready",
                        "lead_approval_package_status": "ready_for_gareth_review",
                        "recommended_action": "convert-to-approval-package",
                        "gareth_final_approval_required": True,
                    }
                ],
                "qualified_public_leads": [
                    {"lead_id": "public-lead-001"}
                ],
                "pending_public_lead_approvals": [
                    {"lead_id": "public-lead-001"}
                ],
                "lead_qualification_status": "qualified_for_gareth_review",
                "lead_revenue_potential": 100,
                "lead_compliance_status": "controlled_review_ready",
                "lead_approval_package_status": "ready_for_gareth_review",
                "latest_public_lead_recommendation": {
                    "lead_id": "public-lead-001",
                    "recommended_action": "convert-to-approval-package",
                    "gareth_final_approval_required": True,
                },
                "latest_lead": {
                    "lead_id": "public-lead-001",
                    "organisation": "Boutique AI Law LLP",
                    "lead_type": "executive_search_lead",
                    "lead_route": "executive_search_review",
                    "lead_revenue_potential": 100,
                    "gareth_final_approval_required": True,
                },
                "gareth_approval_package": {
                    "package_id": "glirn-public-lead-package-public-lead-001",
                    "approval_status": "ready_for_gareth_review",
                    "gareth_final_approval_required": True,
                    "external_action_enabled": False,
                },
                "automatic_email_enabled": False,
                "client_contact_enabled": False,
                "candidate_contact_enabled": False,
                "invoice_issuing_enabled": False,
                "payment_collection_enabled": False,
                "external_integrations_enabled": False,
                "capital_execution": False,
                "autonomous_execution": False,
            },
            "public_leads": [
                {"lead_id": "public-lead-001"}
            ],
            "qualified_public_leads": [
                {"lead_id": "public-lead-001"}
            ],
            "pending_public_lead_approvals": [
                {"lead_id": "public-lead-001"}
            ],
            "latest_public_lead_recommendation": {
                "lead_id": "public-lead-001",
                "recommended_action": "convert-to-approval-package",
            },
            "revenue_approval_engine": {
                "engine": "revenue_approval_engine",
                "status": "Revenue Approval Engine Active",
                "revenue_approval_packages": [
                    {
                        "package_id": "glirn-revenue-approval-public-lead-001",
                        "lead_id": "public-lead-001",
                        "organisation": "Boutique AI Law LLP",
                        "lead_type": "executive_search_lead",
                        "lead_route": "executive_search_review",
                        "practice_area": "Technology & AI Law",
                        "jurisdiction": "England & Wales",
                        "seniority": "Partner",
                        "timescale": "1-3 months",
                        "estimated_revenue_opportunity": 25000,
                        "urgency_score": 75,
                        "confidence_score": 92,
                        "recommended_next_action": "approve",
                        "suggested_glirn_service": "Executive Search",
                        "gareth_approval_status": "awaiting_review",
                        "automatic_client_contact_enabled": False,
                        "automatic_invoice_sending_enabled": False,
                        "money_movement_enabled": False,
                    }
                ],
                "ready_for_gareth_approval": [
                    {"package_id": "glirn-revenue-approval-public-lead-001"}
                ],
                "latest_revenue_opportunity": {
                    "package_id": "glirn-revenue-approval-public-lead-001",
                    "organisation": "Boutique AI Law LLP",
                    "estimated_revenue_opportunity": 25000,
                    "gareth_approval_status": "awaiting_review",
                    "suggested_glirn_service": "Executive Search",
                    "confidence_score": 92,
                },
                "dave_recommends": {
                    "recommendation": "approve",
                    "estimated_fee": 25000,
                    "gareth_approval_required": True,
                },
                "automatic_client_contact_enabled": False,
                "automatic_invoice_sending_enabled": False,
                "money_movement_enabled": False,
                "payment_collection_enabled": False,
                "capital_execution": False,
                "autonomous_execution": False,
            },
            "revenue_approval_packages": [
                {"package_id": "glirn-revenue-approval-public-lead-001"}
            ],
            "ready_for_gareth_approval": [
                {"package_id": "glirn-revenue-approval-public-lead-001"}
            ],
            "latest_revenue_opportunity": {
                "package_id": "glirn-revenue-approval-public-lead-001",
                "organisation": "Boutique AI Law LLP",
            },
            "client_response_draft_engine": {
                "engine": "client_response_draft_engine",
                "status": "Client Response Draft Ready",
                "client_response_drafts": [
                    {
                        "draft_id": "glirn-client-response-glirn-revenue-approval-public-lead-001",
                        "package_id": "glirn-revenue-approval-public-lead-001",
                        "suggested_service": "Executive Search",
                        "recommended_next_action": "approve",
                        "draft_status": "awaiting_gareth_approval",
                        "draft_ready_status": "draft_ready",
                        "subject": "GLIRN enquiry follow-up - Executive Search",
                        "automatic_sending_enabled": False,
                        "automatic_email_enabled": False,
                        "client_contact_enabled": False,
                        "local_draft_only": True,
                    }
                ],
                "client_response_draft_ready": {
                    "draft_id": "glirn-client-response-glirn-revenue-approval-public-lead-001",
                    "suggested_service": "Executive Search",
                    "recommended_next_action": "approve",
                    "draft_status": "awaiting_gareth_approval",
                    "draft_ready_status": "draft_ready",
                    "subject": "GLIRN enquiry follow-up - Executive Search",
                    "gareth_approval_required": True,
                    "local_draft_only": True,
                },
                "pending_client_response_approvals": [
                    {"draft_id": "glirn-client-response-glirn-revenue-approval-public-lead-001"}
                ],
                "latest_client_response_draft": {
                    "draft_id": "glirn-client-response-glirn-revenue-approval-public-lead-001",
                    "suggested_service": "Executive Search",
                    "recommended_next_action": "approve",
                    "draft_status": "awaiting_gareth_approval",
                    "draft_ready_status": "draft_ready",
                    "subject": "GLIRN enquiry follow-up - Executive Search",
                    "gareth_approval_required": True,
                    "local_draft_only": True,
                },
                "automatic_sending_enabled": False,
                "automatic_email_enabled": False,
                "client_contact_enabled": False,
                "external_integrations_enabled": False,
                "capital_execution": False,
                "autonomous_execution": False,
            },
            "client_response_drafts": [
                {"draft_id": "glirn-client-response-glirn-revenue-approval-public-lead-001"}
            ],
            "client_response_draft_ready": {
                "draft_id": "glirn-client-response-glirn-revenue-approval-public-lead-001",
            },
            "pending_client_response_approvals": [
                {"draft_id": "glirn-client-response-glirn-revenue-approval-public-lead-001"}
            ],
            "latest_client_response_draft": {
                "draft_id": "glirn-client-response-glirn-revenue-approval-public-lead-001",
            },
            "fee_proposal_pack_engine": {
                "engine": "fee_proposal_pack_engine",
                "status": "Fee Proposal Pack Ready",
                "fee_proposal_packs": [
                    {
                        "proposal_pack_id": "glirn-fee-proposal-glirn-revenue-approval-public-lead-001",
                        "package_id": "glirn-revenue-approval-public-lead-001",
                        "draft_id": "glirn-client-response-glirn-revenue-approval-public-lead-001",
                        "suggested_glirn_service": "Executive Search",
                        "estimated_fee": 25000,
                        "fee_basis": "retained search fee",
                        "proposal_status": "awaiting_review",
                        "gareth_approval_status": "awaiting_review",
                        "gareth_approval_required": True,
                        "payment_signoff_note": "Gareth must approve the proposal before any client-facing use.",
                        "invoice_sent": False,
                        "payment_request_sent": False,
                        "money_movement_enabled": False,
                        "client_contact_enabled": False,
                        "external_integrations_enabled": False,
                        "local_proposal_only": True,
                    }
                ],
                "fee_proposal_pack_ready": {
                    "proposal_pack_id": "glirn-fee-proposal-glirn-revenue-approval-public-lead-001",
                    "suggested_glirn_service": "Executive Search",
                    "estimated_fee": 25000,
                    "fee_basis": "retained search fee",
                    "proposal_status": "awaiting_review",
                    "gareth_approval_required": True,
                    "payment_signoff_note": "Gareth must approve the proposal before any client-facing use.",
                    "local_proposal_only": True,
                },
                "pending_fee_proposal_approvals": [
                    {"proposal_pack_id": "glirn-fee-proposal-glirn-revenue-approval-public-lead-001"}
                ],
                "latest_fee_proposal_pack": {
                    "proposal_pack_id": "glirn-fee-proposal-glirn-revenue-approval-public-lead-001",
                    "suggested_glirn_service": "Executive Search",
                    "estimated_fee": 25000,
                    "fee_basis": "retained search fee",
                    "proposal_status": "awaiting_review",
                    "gareth_approval_required": True,
                    "payment_signoff_note": "Gareth must approve the proposal before any client-facing use.",
                    "local_proposal_only": True,
                },
                "invoice_sent": False,
                "payment_request_sent": False,
                "money_movement_enabled": False,
                "client_contact_enabled": False,
                "external_integrations_enabled": False,
                "capital_execution": False,
                "autonomous_execution": False,
            },
            "fee_proposal_packs": [
                {"proposal_pack_id": "glirn-fee-proposal-glirn-revenue-approval-public-lead-001"}
            ],
            "fee_proposal_pack_ready": {
                "proposal_pack_id": "glirn-fee-proposal-glirn-revenue-approval-public-lead-001",
            },
            "pending_fee_proposal_approvals": [
                {"proposal_pack_id": "glirn-fee-proposal-glirn-revenue-approval-public-lead-001"}
            ],
            "latest_fee_proposal_pack": {
                "proposal_pack_id": "glirn-fee-proposal-glirn-revenue-approval-public-lead-001",
            },
            "final_approval_command_centre": {
                "engine": "final_approval_command_centre",
                "status": "Gareth Final Approval Required",
                "final_approval_objects": [
                    {
                        "final_approval_id": "glirn-final-approval-glirn-revenue-approval-public-lead-001",
                        "package_id": "glirn-revenue-approval-public-lead-001",
                        "draft_id": "glirn-client-response-glirn-revenue-approval-public-lead-001",
                        "proposal_pack_id": "glirn-fee-proposal-glirn-revenue-approval-public-lead-001",
                        "lead_name": "Alex Client",
                        "lead_email": "alex@example.com",
                        "lead_route": "executive_search_review",
                        "suggested_service": "Executive Search",
                        "estimated_fee": 25000,
                        "recommended_next_action": "approve",
                        "dave_recommends": "approve",
                        "final_approval_status": "awaiting_gareth_decision",
                        "client_contact_enabled": False,
                        "invoice_sending_enabled": False,
                        "payment_request_enabled": False,
                        "money_movement_enabled": False,
                        "local_state_only": True,
                    }
                ],
                "gareth_final_approval_required": [
                    {"final_approval_id": "glirn-final-approval-glirn-revenue-approval-public-lead-001"}
                ],
                "latest_final_approval_object": {
                    "final_approval_id": "glirn-final-approval-glirn-revenue-approval-public-lead-001",
                    "lead_route": "executive_search_review",
                    "suggested_service": "Executive Search",
                    "estimated_fee": 25000,
                    "dave_recommends": "approve",
                    "final_approval_status": "awaiting_gareth_decision",
                    "local_state_only": True,
                },
                "client_contact_enabled": False,
                "invoice_sending_enabled": False,
                "payment_request_enabled": False,
                "money_movement_enabled": False,
                "automatic_email_enabled": False,
                "external_integrations_enabled": False,
                "capital_execution": False,
                "autonomous_execution": False,
            },
            "final_approval_objects": [
                {"final_approval_id": "glirn-final-approval-glirn-revenue-approval-public-lead-001"}
            ],
            "gareth_final_approval_required": [
                {"final_approval_id": "glirn-final-approval-glirn-revenue-approval-public-lead-001"}
            ],
            "latest_final_approval_object": {
                "final_approval_id": "glirn-final-approval-glirn-revenue-approval-public-lead-001",
            },
            "approved_client_contact_engine": {
                "engine": "approved_client_contact_engine",
                "status": "Approved Client Contact Ready",
                "client_contact_readiness": [
                    {
                        "contact_readiness_id": "glirn-client-contact-glirn-final-approval-glirn-revenue-approval-public-lead-001",
                        "final_approval_id": "glirn-final-approval-glirn-revenue-approval-public-lead-001",
                        "lead_name": "Alex Client",
                        "lead_email": "alex@example.com",
                        "suggested_service": "Executive Search",
                        "contact_status": "blocked_pending_gareth_approval",
                        "approval_required": True,
                        "gareth_approval_gate": False,
                        "local_only_safety_note": "No real email, Gmail, SMTP, external client contact, or integration is enabled.",
                        "real_email_sent": False,
                        "client_contact_executed": False,
                        "gmail_smtp_connected": False,
                        "external_integrations_enabled": False,
                        "local_log_only": True,
                    }
                ],
                "blocked_client_contacts": [
                    {"contact_readiness_id": "glirn-client-contact-glirn-final-approval-glirn-revenue-approval-public-lead-001"}
                ],
                "ready_client_contacts": [],
                "latest_client_contact_readiness": {
                    "contact_readiness_id": "glirn-client-contact-glirn-final-approval-glirn-revenue-approval-public-lead-001",
                    "lead_name": "Alex Client",
                    "lead_email": "alex@example.com",
                    "suggested_service": "Executive Search",
                    "contact_status": "blocked_pending_gareth_approval",
                    "approval_required": True,
                    "gareth_approval_gate": False,
                    "local_only_safety_note": "No real email, Gmail, SMTP, external client contact, or integration is enabled.",
                },
                "real_email_sent": False,
                "client_contact_executed": False,
                "gmail_smtp_connected": False,
                "external_integrations_enabled": False,
                "capital_execution": False,
                "autonomous_execution": False,
            },
            "client_contact_readiness": [
                {"contact_readiness_id": "glirn-client-contact-glirn-final-approval-glirn-revenue-approval-public-lead-001"}
            ],
            "blocked_client_contacts": [
                {"contact_readiness_id": "glirn-client-contact-glirn-final-approval-glirn-revenue-approval-public-lead-001"}
            ],
            "ready_client_contacts": [],
            "latest_client_contact_readiness": {
                "contact_readiness_id": "glirn-client-contact-glirn-final-approval-glirn-revenue-approval-public-lead-001",
            },
            "email_draft_export_engine": {
                "engine": "email_draft_export_engine",
                "status": "Approved Email Draft Export Ready",
                "email_draft_exports": [
                    {
                        "email_draft_export_id": "glirn-email-draft-glirn-final-approval-glirn-revenue-approval-public-lead-001",
                        "final_approval_id": "glirn-final-approval-glirn-revenue-approval-public-lead-001",
                        "to_email": "alex@example.com",
                        "lead_name": "Alex Client",
                        "subject": "GLIRN enquiry follow-up - Executive Search",
                        "suggested_glirn_service": "Executive Search",
                        "export_status": "blocked_pending_gareth_approval",
                        "local_only_note": "No email has been sent. Gareth must manually review and send.",
                        "email_sent": False,
                        "gmail_smtp_connected": False,
                        "external_integrations_enabled": False,
                        "local_file_only": True,
                    }
                ],
                "blocked_email_draft_exports": [
                    {"email_draft_export_id": "glirn-email-draft-glirn-final-approval-glirn-revenue-approval-public-lead-001"}
                ],
                "ready_email_draft_exports": [],
                "latest_email_draft_export": {
                    "email_draft_export_id": "glirn-email-draft-glirn-final-approval-glirn-revenue-approval-public-lead-001",
                    "to_email": "alex@example.com",
                    "lead_name": "Alex Client",
                    "subject": "GLIRN enquiry follow-up - Executive Search",
                    "suggested_glirn_service": "Executive Search",
                    "export_status": "blocked_pending_gareth_approval",
                    "local_only_note": "No email has been sent. Gareth must manually review and send.",
                    "email_sent": False,
                    "local_file_only": True,
                },
                "email_sent": False,
                "gmail_smtp_connected": False,
                "external_integrations_enabled": False,
                "capital_execution": False,
                "autonomous_execution": False,
            },
            "email_draft_exports": [
                {"email_draft_export_id": "glirn-email-draft-glirn-final-approval-glirn-revenue-approval-public-lead-001"}
            ],
            "blocked_email_draft_exports": [
                {"email_draft_export_id": "glirn-email-draft-glirn-final-approval-glirn-revenue-approval-public-lead-001"}
            ],
            "ready_email_draft_exports": [],
            "latest_email_draft_export": {
                "email_draft_export_id": "glirn-email-draft-glirn-final-approval-glirn-revenue-approval-public-lead-001",
            },
            "invoice_draft_export_engine": {
                "engine": "invoice_draft_export_engine",
                "status": "Invoice Draft Export Ready",
                "invoice_draft_exports": [
                    {
                        "invoice_draft_export_id": "glirn-invoice-draft-glirn-final-approval-glirn-revenue-approval-public-lead-001",
                        "final_approval_id": "glirn-final-approval-glirn-revenue-approval-public-lead-001",
                        "client_name": "Boutique AI Law LLP",
                        "client_email": "alex@example.com",
                        "suggested_glirn_service": "Executive Search",
                        "estimated_fee": 25000,
                        "fee_basis": "retained search fee",
                        "scope_summary": "Prepare an executive legal search proposal.",
                        "payment_signoff_note": "Gareth must approve before manual use.",
                        "invoice_status": "blocked_pending_gareth_approval",
                        "local_only_note": "No invoice or payment request has been sent. Gareth must manually review and send.",
                        "invoice_sent": False,
                        "payment_request_sent": False,
                        "money_movement_enabled": False,
                        "external_integrations_enabled": False,
                        "local_file_only": True,
                    }
                ],
                "blocked_invoice_draft_exports": [
                    {"invoice_draft_export_id": "glirn-invoice-draft-glirn-final-approval-glirn-revenue-approval-public-lead-001"}
                ],
                "ready_invoice_draft_exports": [],
                "latest_invoice_draft_export": {
                    "invoice_draft_export_id": "glirn-invoice-draft-glirn-final-approval-glirn-revenue-approval-public-lead-001",
                    "client_name": "Boutique AI Law LLP",
                    "client_email": "alex@example.com",
                    "suggested_glirn_service": "Executive Search",
                    "estimated_fee": 25000,
                    "fee_basis": "retained search fee",
                    "invoice_status": "blocked_pending_gareth_approval",
                    "local_only_note": "No invoice or payment request has been sent. Gareth must manually review and send.",
                    "invoice_sent": False,
                    "payment_request_sent": False,
                    "money_movement_enabled": False,
                    "local_file_only": True,
                },
                "invoice_sent": False,
                "payment_request_sent": False,
                "money_movement_enabled": False,
                "external_integrations_enabled": False,
                "capital_execution": False,
                "autonomous_execution": False,
            },
            "invoice_draft_exports": [
                {"invoice_draft_export_id": "glirn-invoice-draft-glirn-final-approval-glirn-revenue-approval-public-lead-001"}
            ],
            "blocked_invoice_draft_exports": [
                {"invoice_draft_export_id": "glirn-invoice-draft-glirn-final-approval-glirn-revenue-approval-public-lead-001"}
            ],
            "ready_invoice_draft_exports": [],
            "latest_invoice_draft_export": {
                "invoice_draft_export_id": "glirn-invoice-draft-glirn-final-approval-glirn-revenue-approval-public-lead-001",
            },
            "deal_pack_export_engine": {
                "engine": "deal_pack_export_engine",
                "status": "Complete Deal Pack Ready",
                "deal_pack_exports": [
                    {
                        "deal_pack_export_id": "glirn-deal-pack-glirn-final-approval-glirn-revenue-approval-public-lead-001",
                        "final_approval_id": "glirn-final-approval-glirn-revenue-approval-public-lead-001",
                        "client_name": "Boutique AI Law LLP",
                        "client_email": "alex@example.com",
                        "lead_route": "executive_search_review",
                        "suggested_glirn_service": "Executive Search",
                        "estimated_fee": 25000,
                        "fee_basis": "retained search fee",
                        "dave_recommendation": "approve",
                        "deal_pack_status": "blocked_pending_gareth_approval",
                        "local_only_note": "No client contact, invoice, payment request, or money movement has occurred. Gareth must manually review and act.",
                        "client_contact_executed": False,
                        "invoice_sent": False,
                        "payment_request_sent": False,
                        "money_movement_enabled": False,
                        "external_integrations_enabled": False,
                        "local_file_only": True,
                    }
                ],
                "blocked_deal_pack_exports": [
                    {"deal_pack_export_id": "glirn-deal-pack-glirn-final-approval-glirn-revenue-approval-public-lead-001"}
                ],
                "ready_deal_pack_exports": [],
                "latest_deal_pack_export": {
                    "deal_pack_export_id": "glirn-deal-pack-glirn-final-approval-glirn-revenue-approval-public-lead-001",
                    "client_name": "Boutique AI Law LLP",
                    "client_email": "alex@example.com",
                    "suggested_glirn_service": "Executive Search",
                    "estimated_fee": 25000,
                    "fee_basis": "retained search fee",
                    "deal_pack_status": "blocked_pending_gareth_approval",
                    "local_only_note": "No client contact, invoice, payment request, or money movement has occurred. Gareth must manually review and act.",
                },
                "client_contact_executed": False,
                "invoice_sent": False,
                "payment_request_sent": False,
                "money_movement_enabled": False,
                "external_integrations_enabled": False,
                "capital_execution": False,
                "autonomous_execution": False,
            },
            "deal_pack_exports": [
                {"deal_pack_export_id": "glirn-deal-pack-glirn-final-approval-glirn-revenue-approval-public-lead-001"}
            ],
            "blocked_deal_pack_exports": [
                {"deal_pack_export_id": "glirn-deal-pack-glirn-final-approval-glirn-revenue-approval-public-lead-001"}
            ],
            "ready_deal_pack_exports": [],
            "latest_deal_pack_export": {
                "deal_pack_export_id": "glirn-deal-pack-glirn-final-approval-glirn-revenue-approval-public-lead-001",
            },
            "revenue_ledger_engine": {
                "engine": "revenue_ledger_engine",
                "status": "GLIRN Revenue Ledger Active",
                "revenue_ledger_records": [
                    {
                        "ledger_record_id": "glirn-revenue-ledger-glirn-final-approval-glirn-revenue-approval-public-lead-001",
                        "final_approval_id": "glirn-final-approval-glirn-revenue-approval-public-lead-001",
                        "lead_client_name": "Boutique AI Law LLP",
                        "client_email": "alex@example.com",
                        "lead_route": "executive_search_review",
                        "suggested_glirn_service": "Executive Search",
                        "estimated_fee": 25000,
                        "fee_basis": "retained search fee",
                        "final_approval_status": "awaiting_gareth_decision",
                        "email_draft_export_status": "blocked_pending_gareth_approval",
                        "invoice_draft_export_status": "blocked_pending_gareth_approval",
                        "deal_pack_export_status": "blocked_pending_gareth_approval",
                        "revenue_stage": "approval_ready",
                        "actual_revenue_received": 0,
                        "manual_payment_confirmation_required": True,
                        "payment_collection_enabled": False,
                        "money_movement_enabled": False,
                        "external_integrations_enabled": False,
                        "local_tracking_only": True,
                    }
                ],
                "latest_revenue_ledger_record": {
                    "ledger_record_id": "glirn-revenue-ledger-glirn-final-approval-glirn-revenue-approval-public-lead-001",
                    "lead_client_name": "Boutique AI Law LLP",
                    "revenue_stage": "approval_ready",
                    "local_tracking_only": True,
                },
                "estimated_pipeline_value": 25000,
                "actual_revenue_recorded": 0,
                "latest_revenue_stage": "approval_ready",
                "manual_payment_confirmation_required": True,
                "payment_collection_enabled": False,
                "money_movement_enabled": False,
                "external_integrations_enabled": False,
                "capital_execution": False,
                "autonomous_execution": False,
            },
            "revenue_ledger_records": [
                {"ledger_record_id": "glirn-revenue-ledger-glirn-final-approval-glirn-revenue-approval-public-lead-001"}
            ],
            "latest_revenue_ledger_record": {
                "ledger_record_id": "glirn-revenue-ledger-glirn-final-approval-glirn-revenue-approval-public-lead-001",
            },
            "estimated_pipeline_value": 25000,
            "actual_revenue_recorded": 0,
            "latest_revenue_stage": "approval_ready",
            "summary": {
                "total_opportunities": 1,
                "pending_human_approval": 1,
                "total_expected_fee_value": 85000,
                "highest_score": 76.4,
                "highest_opportunity": {
                    "title": "Private Equity Partner Search"
                },
                "client_response_draft_engine_status": "Client Response Draft Ready",
                "fee_proposal_pack_engine_status": "Fee Proposal Pack Ready",
                "final_approval_command_centre_status": "Gareth Final Approval Required",
                "approved_client_contact_engine_status": "Approved Client Contact Ready",
                "email_draft_export_engine_status": "Approved Email Draft Export Ready",
                "invoice_draft_export_engine_status": "Invoice Draft Export Ready",
                "deal_pack_export_engine_status": "Complete Deal Pack Ready",
                "revenue_ledger_engine_status": "GLIRN Revenue Ledger Active",
                "capital_execution": False
            },
            "capital_execution": False
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.get_glirn_dashboard_data", return_value=glirn_data):
            response = self.client.get("/glirn/dashboard")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["summary"]["pending_human_approval"], 1)
        self.assertEqual(data["legal_sectors"][0]["name"], "Corporate & M&A")
        self.assertEqual(data["legal_opportunity_radar"]["engine"], "legal_opportunity_radar")
        self.assertTrue(data["legal_opportunity_radar"]["approval_required_for_outbound_action"])
        self.assertEqual(data["approval_centre"]["status"], "Waiting for Gareth Approval")
        self.assertTrue(data["approval_centre"]["locks"]["outbound_action_locked"])
        self.assertEqual(data["compliance_core"]["status"], "Compliance-First Controls Active")
        self.assertEqual(data["executive_search"]["status"], "Executive Search Engine Active")
        self.assertEqual(data["intelligence_network"]["status"], "Legal Intelligence Network Active")
        self.assertEqual(data["commercial_revenue_engine"]["status"], "Commercial Revenue Controls Active")
        self.assertEqual(data["client_acquisition_engine"]["status"], "Client Acquisition Controls Active")
        self.assertEqual(data["candidate_discovery_engine"]["status"], "Candidate Discovery Controls Active")
        self.assertEqual(data["matching_engine"]["status"], "Matching & Placement Controls Active")
        self.assertEqual(data["executive_autopilot"]["status"], "Executive Autopilot Waiting for Gareth Approval")
        self.assertEqual(data["live_data_readiness"]["status"], "Live Data Readiness Controls Active")
        self.assertEqual(data["integration_governance"]["status"], "Integration Governance Controls Active")
        self.assertEqual(data["deployment_readiness"]["status"], "Deployment Readiness Assessment Active")
        self.assertEqual(data["operations_command_centre"]["status"], "Operations Command Centre Active")
        self.assertEqual(data["daily_executive_briefing"]["status"], "Daily Executive Briefing Ready")
        self.assertEqual(data["intelligence_review_engine"]["status"], "Automated Intelligence Review Draft Ready")
        self.assertEqual(data["deliverable_factory"]["status"], "Client Deliverable Drafts Ready")
        self.assertEqual(data["approval_to_action_workflow"]["status"], "Approval-to-Action Controls Active")
        self.assertEqual(data["revenue_command_centre"]["status"], "Revenue Command Centre Active")
        self.assertEqual(data["first_client_readiness_gate"]["status"], "First Client Readiness Gate Active")
        self.assertEqual(data["launch_readiness_command_centre"]["status"], "Launch Readiness Command Centre Active")
        self.assertEqual(data["invoice_drafting_engine"]["status"], "Invoice Drafting Engine Active")
        self.assertEqual(data["client_terms_drafting_engine"]["status"], "Client Terms Drafting Engine Active")
        self.assertEqual(data["candidate_consent_management_engine"]["status"], "Candidate Consent Management Engine Active")
        self.assertEqual(data["manual_delivery_control_engine"]["status"], "Manual Delivery Control Engine Active")
        self.assertEqual(data["launch_compliance_validation_engine"]["status"], "Launch Compliance Validation Engine Active")
        self.assertEqual(data["first_prospect_selection_engine"]["status"], "First Prospect Selection Engine Active")
        self.assertEqual(data["first_client_dry_run"]["dry_run_status"], "completed_pending_gareth_approval")
        self.assertEqual(data["autonomous_internal_operations_orchestrator"]["autonomous_cycle_status"], "completed_pending_gareth_final_decision")
        self.assertEqual(data["website_lead_intake_engine"]["status"], "Website Lead Intake Engine Active")
        self.assertEqual(data["revenue_approval_engine"]["status"], "Revenue Approval Engine Active")
        self.assertEqual(data["client_response_draft_engine"]["status"], "Client Response Draft Ready")
        self.assertEqual(data["fee_proposal_pack_engine"]["status"], "Fee Proposal Pack Ready")
        self.assertEqual(data["final_approval_command_centre"]["status"], "Gareth Final Approval Required")
        self.assertEqual(data["approved_client_contact_engine"]["status"], "Approved Client Contact Ready")
        self.assertEqual(data["email_draft_export_engine"]["status"], "Approved Email Draft Export Ready")
        self.assertEqual(data["invoice_draft_export_engine"]["status"], "Invoice Draft Export Ready")
        self.assertEqual(data["deal_pack_export_engine"]["status"], "Complete Deal Pack Ready")
        self.assertEqual(data["revenue_ledger_engine"]["status"], "GLIRN Revenue Ledger Active")
        self.assertIn("key_metrics", data)
        self.assertIn("platform_health", data)
        self.assertFalse(data["capital_execution"])

    def test_glirn_approval_request_creates_queue_item_and_audit_event(self):
        opportunity = {
            "opportunity_id": "glirn-test-001",
            "title": "Private Equity Partner Search",
            "practice_area": "Private Equity",
            "jurisdiction": "England & Wales",
            "expected_fee_value": 85000,
            "placement_probability": 0.42,
            "client_quality": 88,
            "candidate_quality": 91,
            "compliance_readiness": 76,
            "urgency_score": 82,
            "time_to_revenue": 45,
            "overall_glirn_score": 76.4,
            "capital_execution": False
        }
        glirn_data = {
            "legal_sectors": [],
            "opportunities": [opportunity],
            "summary": {
                "total_opportunities": 1,
                "pending_human_approval": 1,
                "capital_execution": False
            },
            "capital_execution": False
        }
        approval = {
            "approval_id": "approval-glirn-123",
            "status": "pending_user_approval",
            "capital_execution": False
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.get_glirn_dashboard_data", return_value=glirn_data), \
                patch("app.create_approval_request", return_value=approval) as create_approval, \
                patch("app.record_approval_event") as record_event:
            response = self.client.post("/glirn/opportunities/glirn-test-001/request-approval")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "pending_human_approval")
        self.assertTrue(data["approval_required"])
        self.assertEqual(data["approval_id"], "approval-glirn-123")
        self.assertFalse(data["capital_execution"])
        create_approval.assert_called_once()
        approval_payload = create_approval.call_args.args[0]
        self.assertEqual(approval_payload["source"], "glirn")
        self.assertEqual(approval_payload["subject_type"], "recruitment_opportunity")
        self.assertFalse(approval_payload["capital_execution"])
        record_event.assert_called_once()
        self.assertEqual(record_event.call_args.args[0]["event_type"], "glirn_approval_requested")

    def test_glirn_approval_request_returns_404_for_unknown_opportunity(self):
        with patch.dict("os.environ", {}, clear=True), \
                patch("app.get_glirn_dashboard_data", return_value={
                    "legal_sectors": [],
                    "opportunities": [],
                    "summary": {},
                    "capital_execution": False
                }), \
                patch("app.create_approval_request") as create_approval:
            response = self.client.post("/glirn/opportunities/missing/request-approval")

        self.assertEqual(response.status_code, 404)
        create_approval.assert_not_called()

    def test_glirn_approval_centre_approve_records_queue_update_and_audit(self):
        approval = {
            "approval_id": "approval-glirn-123",
            "route_result": {
                "source": "glirn",
                "opportunity_id": "glirn-test-001",
            },
            "capital_execution": False,
        }
        updated = {
            **approval,
            "status": "user_approved",
            "decision": "approved",
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[approval]), \
                patch("app.update_approval_decision", return_value=updated) as update_decision, \
                patch("app.record_approval_event") as record_event:
            response = self.client.post(
                "/glirn/approvals/approval-glirn-123/approve",
                json={"approval_reason": "Candidate and client quality are strong."},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "glirn_approve_recorded")
        self.assertEqual(data["decision"], "approve")
        self.assertTrue(data["outbound_action_locked"])
        self.assertTrue(data["candidate_introduction_locked"])
        self.assertTrue(data["client_engagement_locked"])
        self.assertTrue(data["fee_negotiation_locked"])
        self.assertFalse(data["capital_execution"])
        update_decision.assert_called_once_with("approval-glirn-123", "approved")
        record_event.assert_called_once()
        self.assertEqual(record_event.call_args.args[0]["event_type"], "glirn_approval_decision")
        self.assertEqual(record_event.call_args.args[0]["decision"], "approve")

    def test_glirn_approval_centre_monitor_records_audit_without_queue_update(self):
        approval = {
            "approval_id": "approval-glirn-123",
            "route_result": {
                "source": "glirn",
                "opportunity_id": "glirn-test-001",
            },
            "capital_execution": False,
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[approval]), \
                patch("app.update_approval_decision") as update_decision, \
                patch("app.record_approval_event") as record_event:
            response = self.client.post(
                "/glirn/approvals/approval-glirn-123/monitor",
                json={"approval_reason": "Need more evidence before outreach."},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "glirn_monitor_recorded")
        self.assertEqual(data["decision"], "monitor")
        update_decision.assert_not_called()
        record_event.assert_called_once()
        self.assertEqual(record_event.call_args.args[0]["decision"], "monitor")
        self.assertTrue(record_event.call_args.args[0]["outbound_action_locked"])

    def test_glirn_approval_centre_requires_approval_reason(self):
        approval = {
            "approval_id": "approval-glirn-123",
            "route_result": {
                "source": "glirn",
                "opportunity_id": "glirn-test-001",
            },
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[approval]), \
                patch("app.record_approval_event") as record_event:
            response = self.client.post(
                "/glirn/approvals/approval-glirn-123/reject",
                json={"approval_reason": "   "},
            )

        self.assertEqual(response.status_code, 400)
        record_event.assert_not_called()

    def test_glirn_deletion_request_flags_record_and_creates_audit_entry(self):
        with patch.dict("os.environ", {}, clear=True), \
                patch("app.record_approval_event") as record_event:
            response = self.client.post(
                "/glirn/compliance/deletion-request",
                json={
                    "candidate_id": "candidate-stub-001",
                    "reason": "Candidate requested deletion."
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "deletion_request_recorded")
        self.assertTrue(data["deletion_request"]["record_flagged"])
        self.assertTrue(data["outbound_action_blocked"])
        self.assertFalse(data["capital_execution"])
        record_event.assert_called_once()
        event = record_event.call_args.args[0]
        self.assertEqual(event["event_type"], "glirn_compliance_event")
        self.assertEqual(event["decision"], "DELETION_REQUEST_RECORDED")
        self.assertEqual(event["provider"], "glirn_compliance_core")
        self.assertTrue(event["outbound_action_blocked"])

    def test_glirn_executive_search_action_creates_audit_entry(self):
        glirn_data = {
            "executive_search": {
                "top_executive_opportunities": [
                    {
                        "opportunity_id": "glirn-test-001",
                        "premium_opportunity": True,
                        "estimated_placement_fee": 85000,
                        "estimated_retainer_fee": 28330.5,
                        "executive_candidate_outreach_allowed": True,
                        "client_engagement_allowed": True,
                        "retained_search_proposal_requires_gareth_approval": True,
                        "outbound_action_blocked": False,
                    }
                ]
            }
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.get_glirn_dashboard_data", return_value=glirn_data), \
                patch("app.record_approval_event") as record_event:
            response = self.client.post(
                "/glirn/executive-search/actions",
                json={
                    "opportunity_id": "glirn-test-001",
                    "action_type": "retained_search_proposal",
                    "reason": "Prepare retained proposal for Gareth review.",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "executive_search_action_recorded")
        self.assertTrue(data["gareth_approval_required"])
        self.assertTrue(data["outbound_action_blocked"])
        self.assertFalse(data["capital_execution"])
        record_event.assert_called_once()
        event = record_event.call_args.args[0]
        self.assertEqual(event["event_type"], "glirn_executive_search_action")
        self.assertEqual(event["provider"], "glirn_executive_search")
        self.assertTrue(event["premium_opportunity"])
        self.assertTrue(event["gareth_approval_required"])
        self.assertFalse(event["capital_execution"])

    def test_glirn_intelligence_report_request_requires_approval_and_audits(self):
        with patch.dict("os.environ", {}, clear=True), \
                patch("app.record_approval_event") as record_event:
            response = self.client.post(
                "/glirn/intelligence/report-requests",
                json={
                    "report_type": "market_intelligence",
                    "audience": "client",
                    "reason": "Prepare client-facing hook.",
                    "include_candidate_specific_data": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "intelligence_report_request_recorded")
        self.assertTrue(data["gareth_approval_required"])
        self.assertTrue(data["candidate_personal_data_blocked"])
        self.assertFalse(data["candidate_personal_data_included"])
        self.assertFalse(data["capital_execution"])
        record_event.assert_called_once()
        event = record_event.call_args.args[0]
        self.assertEqual(event["event_type"], "glirn_intelligence_report_requested")
        self.assertEqual(event["provider"], "glirn_intelligence_network")
        self.assertEqual(event["decision"], "REQUEST_APPROVAL")
        self.assertTrue(event["candidate_personal_data_blocked"])
        self.assertTrue(event["gareth_approval_required"])

    def test_glirn_commercial_action_creates_audit_entry(self):
        glirn_data = {
            "commercial_revenue_engine": {
                "commercial_pipeline": [
                    {
                        "opportunity_id": "glirn-test-001",
                        "fee_type": "executive search fee",
                        "estimated_revenue": 85000,
                        "invoice_readiness": "ready",
                        "candidate_submission_allowed": True,
                        "fee_proposal_requires_gareth_approval": True,
                    }
                ]
            }
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.get_glirn_dashboard_data", return_value=glirn_data), \
                patch("app.record_approval_event") as record_event:
            response = self.client.post(
                "/glirn/commercial/actions",
                json={
                    "opportunity_id": "glirn-test-001",
                    "action_type": "fee_proposal",
                    "reason": "Prepare Gareth-approved fee proposal.",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "commercial_action_recorded")
        self.assertTrue(data["gareth_approval_required"])
        self.assertTrue(data["action_blocked"])
        self.assertFalse(data["capital_execution"])
        record_event.assert_called_once()
        event = record_event.call_args.args[0]
        self.assertEqual(event["event_type"], "glirn_commercial_action")
        self.assertEqual(event["provider"], "glirn_commercial_revenue_engine")
        self.assertEqual(event["decision"], "REQUEST_APPROVAL")
        self.assertTrue(event["gareth_approval_required"])

    def test_glirn_client_acquisition_action_creates_audit_entry(self):
        glirn_data = {
            "client_acquisition_engine": {
                "target_client_profiles": [
                    {
                        "client_id": "client-stub-001",
                        "client_name": "Client Firm A",
                        "estimated_fee_potential": 85000,
                        "fee_discussion_allowed": True,
                        "candidate_details_allowed": False,
                    }
                ]
            }
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.get_glirn_dashboard_data", return_value=glirn_data), \
                patch("app.record_approval_event") as record_event:
            response = self.client.post(
                "/glirn/client-acquisition/actions",
                json={
                    "client_id": "client-stub-001",
                    "action_type": "outreach",
                    "reason": "Ask Gareth to approve initial client outreach.",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "client_acquisition_action_recorded")
        self.assertTrue(data["gareth_approval_required"])
        self.assertTrue(data["action_blocked"])
        self.assertFalse(data["capital_execution"])
        record_event.assert_called_once()
        event = record_event.call_args.args[0]
        self.assertEqual(event["event_type"], "glirn_client_acquisition_action")
        self.assertEqual(event["provider"], "glirn_client_acquisition_engine")
        self.assertEqual(event["decision"], "REQUEST_APPROVAL")
        self.assertTrue(event["gareth_approval_required"])

    def test_glirn_candidate_discovery_action_creates_audit_entry(self):
        glirn_data = {
            "candidate_discovery_engine": {
                "candidate_profiles": [
                    {
                        "candidate_id": "candidate-stub-001",
                        "estimated_placement_value": 85000,
                        "consent_readiness_status": "active",
                        "profile_activation_allowed": True,
                        "candidate_details_allowed": True,
                        "candidate_specific_intelligence_allowed": True,
                    }
                ]
            }
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.get_glirn_dashboard_data", return_value=glirn_data), \
                patch("app.record_approval_event") as record_event:
            response = self.client.post(
                "/glirn/candidate-discovery/actions",
                json={
                    "candidate_id": "candidate-stub-001",
                    "action_type": "outreach",
                    "reason": "Ask Gareth to approve candidate outreach.",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "candidate_discovery_action_recorded")
        self.assertTrue(data["gareth_approval_required"])
        self.assertTrue(data["action_blocked"])
        self.assertFalse(data["capital_execution"])
        record_event.assert_called_once()
        event = record_event.call_args.args[0]
        self.assertEqual(event["event_type"], "glirn_candidate_discovery_action")
        self.assertEqual(event["provider"], "glirn_candidate_discovery_engine")
        self.assertEqual(event["decision"], "REQUEST_APPROVAL")
        self.assertTrue(event["gareth_approval_required"])

    def test_glirn_matching_action_creates_audit_entry(self):
        glirn_data = {
            "matching_engine": {
                "ranked_placement_matches": [
                    {
                        "match_id": "match-candidate-stub-001-client-stub-001",
                        "candidate_id": "candidate-stub-001",
                        "client_id": "client-stub-001",
                        "match_revenue_score": 84,
                        "placement_probability_score": 78,
                        "candidate_consent_status": "active",
                        "client_terms_status": "recorded",
                        "match_active_allowed": True,
                        "client_facing_allowed": True,
                        "candidate_details_share_allowed": False,
                        "placement_action_requires_gareth_approval": True,
                    }
                ]
            }
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.get_glirn_dashboard_data", return_value=glirn_data), \
                patch("app.record_approval_event") as record_event:
            response = self.client.post(
                "/glirn/matching/actions",
                json={
                    "match_id": "match-candidate-stub-001-client-stub-001",
                    "action_type": "placement_action",
                    "reason": "Ask Gareth to approve placement action.",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "matching_action_recorded")
        self.assertTrue(data["gareth_approval_required"])
        self.assertTrue(data["action_blocked"])
        self.assertFalse(data["capital_execution"])
        record_event.assert_called_once()
        event = record_event.call_args.args[0]
        self.assertEqual(event["event_type"], "glirn_matching_action")
        self.assertEqual(event["provider"], "glirn_matching_engine")
        self.assertEqual(event["decision"], "REQUEST_APPROVAL")
        self.assertTrue(event["gareth_approval_required"])

    def test_glirn_live_data_source_action_creates_audit_entry(self):
        glirn_data = {
            "live_data_readiness": {
                "source_registry": [
                    {
                        "source_id": "source-candidate-csv-import",
                        "source_name": "Human-approved candidate CSV import",
                        "source_type": "manual_csv",
                        "risk_level": "medium",
                        "contains_personal_data": True,
                        "requires_candidate_consent": True,
                        "requires_client_terms": False,
                        "lawful_basis_readiness": "ready",
                        "ingestion_readiness_status": "pending_gareth_approval",
                    }
                ]
            }
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.get_glirn_dashboard_data", return_value=glirn_data), \
                patch("app.record_approval_event") as record_event:
            response = self.client.post(
                "/glirn/live-data/sources/actions",
                json={
                    "source_id": "source-candidate-csv-import",
                    "action_type": "approve",
                    "reason": "Ask Gareth to approve future manual source readiness.",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "live_data_source_action_recorded")
        self.assertTrue(data["gareth_approval_required"])
        self.assertFalse(data["external_connection_enabled"])
        self.assertFalse(data["scraping_enabled"])
        self.assertFalse(data["live_fetching_enabled"])
        self.assertFalse(data["ingestion_enabled"])
        self.assertFalse(data["capital_execution"])
        record_event.assert_called_once()
        event = record_event.call_args.args[0]
        self.assertEqual(event["event_type"], "glirn_live_data_source_action")
        self.assertEqual(event["provider"], "glirn_live_data_readiness")
        self.assertEqual(event["decision"], "REQUEST_APPROVAL")
        self.assertTrue(event["gareth_approval_required"])
        self.assertFalse(event["scraping_enabled"])
        self.assertFalse(event["ingestion_enabled"])

    def test_glirn_integration_action_creates_audit_entry(self):
        glirn_data = {
            "integration_governance": {
                "integration_registry": [
                    {
                        "integration_id": "integration-manual-csv-upload",
                        "integration_name": "Manual CSV Upload",
                        "integration_type": "manual_import",
                        "risk_level": "medium",
                        "contains_personal_data": True,
                        "requires_candidate_consent": True,
                        "requires_client_terms": False,
                        "governance_status": "pending_gareth_approval",
                        "readiness_score": 63.25,
                    }
                ]
            }
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.get_glirn_dashboard_data", return_value=glirn_data), \
                patch("app.record_approval_event") as record_event:
            response = self.client.post(
                "/glirn/integrations/actions",
                json={
                    "integration_id": "integration-manual-csv-upload",
                    "action_type": "approve",
                    "reason": "Ask Gareth to approve future integration governance.",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "integration_governance_action_recorded")
        self.assertTrue(data["gareth_approval_required"])
        self.assertFalse(data["external_connection_enabled"])
        self.assertFalse(data["scraping_enabled"])
        self.assertFalse(data["outbound_connection_enabled"])
        self.assertFalse(data["autonomous_activation_enabled"])
        self.assertFalse(data["capital_execution"])
        record_event.assert_called_once()
        event = record_event.call_args.args[0]
        self.assertEqual(event["event_type"], "glirn_integration_governance_action")
        self.assertEqual(event["provider"], "glirn_integration_governance")
        self.assertEqual(event["decision"], "REQUEST_APPROVAL")
        self.assertTrue(event["gareth_approval_required"])
        self.assertFalse(event["scraping_enabled"])
        self.assertFalse(event["autonomous_activation_enabled"])

    def test_glirn_intelligence_review_action_creates_audit_entry(self):
        glirn_data = {
            "intelligence_review_engine": {
                "generated_reviews": [
                    {
                        "review_id": "glirn-review-001",
                        "title": "GLIRN Senior Legal Hiring Intelligence Review - Client Firm A",
                        "target_client_profile": "Client Firm A",
                        "practice_area": "Private Equity",
                        "jurisdiction": "England & Wales",
                        "approval_status": "pending_gareth_approval",
                        "compliance_status": "controlled",
                        "recommended_action": "start search",
                        "candidate_personal_data_included": False,
                        "candidate_personal_data_blocked": True,
                    }
                ]
            }
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.get_glirn_dashboard_data", return_value=glirn_data), \
                patch("app.record_approval_event") as record_event:
            response = self.client.post(
                "/glirn/intelligence-reviews/actions",
                json={
                    "review_id": "glirn-review-001",
                    "action_type": "approve",
                    "reason": "Ask Gareth to review before client-facing use.",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "intelligence_review_action_recorded")
        self.assertTrue(data["gareth_approval_required"])
        self.assertTrue(data["action_blocked"])
        self.assertFalse(data["client_ready"])
        self.assertFalse(data["client_delivery_enabled"])
        self.assertFalse(data["outreach_enabled"])
        self.assertFalse(data["capital_execution"])
        record_event.assert_called_once()
        event = record_event.call_args.args[0]
        self.assertEqual(event["event_type"], "glirn_intelligence_review_action")
        self.assertEqual(event["provider"], "glirn_intelligence_review_engine")
        self.assertEqual(event["decision"], "REQUEST_APPROVAL")
        self.assertTrue(event["gareth_approval_required"])
        self.assertTrue(event["candidate_personal_data_blocked"])
        self.assertFalse(event["external_delivery_enabled"])

    def test_human_review_endpoint_blocks_incomplete_approval(self):
        brief = {
            "review_id": "glirn-review-human-001",
            "candidate_personal_data_included": False,
            "candidate_personal_data_blocked": True,
            "human_review_framework": {
                "red_flags": {key: False for key in glirn_human_review.RED_FLAG_RULES}
            },
        }
        glirn_data = {
            "intelligence_review_engine": {"generated_reviews": [brief]}
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.get_glirn_dashboard_data", return_value=glirn_data):
            response = self.client.post(
                "/glirn/intelligence-briefs/human-review",
                json={
                    "brief_id": brief["review_id"],
                    "reviewer": "Gareth",
                    "outcome": "approved_for_manual_delivery",
                    "approval_rationale": "Ready for controlled delivery.",
                    "checklist_results": {},
                },
            )

        self.assertEqual(response.status_code, 422)
        detail = response.json()["detail"]
        self.assertIn("all mandatory checklist items must pass before approval", detail["errors"])
        self.assertEqual(
            set(detail["incomplete_checks"]),
            set(glirn_human_review.HUMAN_REVIEW_CHECKLIST),
        )

    def test_human_review_endpoint_persists_audits_and_remains_manual_only(self):
        brief = {
            "review_id": "glirn-review-human-002",
            "candidate_personal_data_included": False,
            "candidate_personal_data_blocked": True,
            "human_review_framework": {
                "red_flags": {key: False for key in glirn_human_review.RED_FLAG_RULES}
            },
        }
        glirn_data = {
            "intelligence_review_engine": {"generated_reviews": [brief]}
        }
        checklist = {key: True for key in glirn_human_review.HUMAN_REVIEW_CHECKLIST}
        stored_records = []

        def store_review(record_type, record_id, payload):
            self.assertEqual(record_type, "human_review_record")
            stored_records[:] = [dict(payload)]

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.get_glirn_dashboard_data", return_value=glirn_data), \
                patch("app.upsert_record", side_effect=store_review), \
                patch("app.list_records", side_effect=lambda record_type: list(stored_records)), \
                patch("app.persist_safe_action") as persist_action, \
                patch("app.record_approval_event") as record_event, \
                patch.object(app, "PERSISTED_HUMAN_REVIEWS", []):
            response = self.client.post(
                "/glirn/intelligence-briefs/human-review",
                json={
                    "brief_id": brief["review_id"],
                    "enquiry_date": "2026-06-09T09:00:00+00:00",
                    "reviewer": "Gareth",
                    "outcome": "approved_for_manual_delivery",
                    "approval_rationale": "Evidence and limitations checked.",
                    "checklist_results": checklist,
                    "delivery_status": "ready_for_manual_delivery",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        record = data["human_review_record"]
        self.assertEqual(record["reviewer"], "Gareth")
        self.assertEqual(record["delivery_status"], "ready_for_manual_delivery")
        self.assertTrue(record["approved_for_manual_delivery"])
        self.assertTrue(record["manual_delivery_only"])
        self.assertFalse(record["external_delivery_enabled"])
        self.assertFalse(record["automatic_delivery_enabled"])
        self.assertFalse(data["payment_collection_enabled"])
        self.assertFalse(data["money_movement_enabled"])
        self.assertEqual(stored_records[0]["brief_id"], brief["review_id"])
        persist_action.assert_called_once()
        self.assertEqual(persist_action.call_args.args[0], "intelligence_brief_human_review")
        record_event.assert_called_once()
        event = record_event.call_args.args[0]
        self.assertEqual(event["reviewer"], "Gareth")
        self.assertEqual(event["approval_rationale"], "Evidence and limitations checked.")
        self.assertTrue(event["manual_delivery_only"])
        self.assertFalse(event["external_delivery_enabled"])

    def test_glirn_deliverable_action_creates_audit_entry(self):
        glirn_data = {
            "deliverable_factory": {
                "generated_deliverables": [
                    {
                        "deliverable_id": "glirn-deliverable-search-mandate-001",
                        "deliverable_type": "Search Mandate Proposal",
                        "title": "Search Mandate Proposal - Client Firm A",
                        "target_client_profile": "Client Firm A",
                        "approval_status": "pending_gareth_approval",
                        "compliance_status": "controlled",
                        "recommended_action": "review",
                        "candidate_personal_data_included": False,
                        "candidate_personal_data_blocked": True,
                    }
                ]
            }
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.get_glirn_dashboard_data", return_value=glirn_data), \
                patch("app.record_approval_event") as record_event:
            response = self.client.post(
                "/glirn/deliverables/actions",
                json={
                    "deliverable_id": "glirn-deliverable-search-mandate-001",
                    "action_type": "approve",
                    "reason": "Ask Gareth to approve before client-facing use.",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "deliverable_action_recorded")
        self.assertTrue(data["gareth_approval_required"])
        self.assertTrue(data["action_blocked"])
        self.assertFalse(data["client_ready"])
        self.assertFalse(data["client_delivery_enabled"])
        self.assertFalse(data["fee_proposal_autonomous"])
        self.assertFalse(data["contracts_autonomous"])
        self.assertFalse(data["capital_execution"])
        record_event.assert_called_once()
        event = record_event.call_args.args[0]
        self.assertEqual(event["event_type"], "glirn_deliverable_action")
        self.assertEqual(event["provider"], "glirn_deliverable_factory")
        self.assertEqual(event["decision"], "REQUEST_APPROVAL")
        self.assertTrue(event["gareth_approval_required"])
        self.assertFalse(event["external_delivery_enabled"])
        self.assertFalse(event["fee_proposal_autonomous"])

    def test_glirn_approval_to_action_approve_makes_item_ready_for_human_use(self):
        glirn_data = {
            "approval_to_action_workflow": {
                "pending_gareth_approval": [
                    {
                        "item_id": "glirn-deliverable-search-mandate-001",
                        "item_type": "client_deliverable",
                        "title": "Search Mandate Proposal - Client Firm A",
                        "client_ready": False,
                        "human_use_ready": False,
                    }
                ],
                "approved_for_human_use": [],
                "rejected_items": [],
                "monitored_items": [],
            }
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.get_glirn_dashboard_data", return_value=glirn_data), \
                patch("app.record_approval_event") as record_event:
            response = self.client.post(
                "/glirn/approval-to-action/actions",
                json={
                    "item_id": "glirn-deliverable-search-mandate-001",
                    "action_type": "approve",
                    "reason": "Gareth approved for human-controlled use.",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "approval_to_action_recorded")
        self.assertEqual(data["approval_status"], "approved_by_gareth")
        self.assertEqual(data["client_ready_status"], "ready_for_human_use")
        self.assertTrue(data["client_ready"])
        self.assertTrue(data["human_use_ready"])
        self.assertFalse(data["automatic_delivery_enabled"])
        record_event.assert_called_once()
        event = record_event.call_args.args[0]
        self.assertEqual(event["event_type"], "glirn_approval_to_action")
        self.assertEqual(event["decision"], "APPROVED_FOR_HUMAN_USE")
        self.assertTrue(event["client_ready"])
        self.assertFalse(event["outreach_enabled"])

    def test_glirn_approval_to_action_reject_blocks_client_ready_status(self):
        glirn_data = {
            "approval_to_action_workflow": {
                "pending_gareth_approval": [
                    {
                        "item_id": "glirn-review-001",
                        "item_type": "intelligence_review",
                        "title": "GLIRN Review",
                    }
                ],
                "approved_for_human_use": [],
                "rejected_items": [],
                "monitored_items": [],
            }
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.get_glirn_dashboard_data", return_value=glirn_data), \
                patch("app.record_approval_event"):
            response = self.client.post(
                "/glirn/approval-to-action/actions",
                json={
                    "item_id": "glirn-review-001",
                    "action_type": "reject",
                    "reason": "Not suitable for client use.",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["approval_status"], "rejected_by_gareth")
        self.assertEqual(data["client_ready_status"], "blocked_not_client_ready")
        self.assertFalse(data["client_ready"])

    def test_glirn_approval_to_action_monitor_keeps_item_pending(self):
        glirn_data = {
            "approval_to_action_workflow": {
                "pending_gareth_approval": [
                    {
                        "item_id": "glirn-deliverable-fee-proposal-001",
                        "item_type": "client_deliverable",
                        "title": "Fee Proposal",
                    }
                ],
                "approved_for_human_use": [],
                "rejected_items": [],
                "monitored_items": [],
            }
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.get_glirn_dashboard_data", return_value=glirn_data), \
                patch("app.record_approval_event"):
            response = self.client.post(
                "/glirn/approval-to-action/actions",
                json={
                    "item_id": "glirn-deliverable-fee-proposal-001",
                    "action_type": "monitor",
                    "reason": "Keep under review.",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["approval_status"], "monitoring")
        self.assertEqual(data["action_readiness_status"], "monitoring_pending_future_review")
        self.assertFalse(data["client_ready"])

    def test_glirn_first_client_readiness_approve_makes_item_ready_for_human_action(self):
        glirn_data = {
            "first_client_readiness_gate": {
                "readiness_checks": [
                    {
                        "item_id": "first-client-glirn-pe-partner-london-001",
                        "opportunity_id": "glirn-pe-partner-london-001",
                        "title": "Private Equity Partner Search",
                        "human_action_ready": False,
                    }
                ],
                "first_client_ready_items": [],
                "blocked_first_client_items": [],
                "monitored_first_client_items": [],
            }
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.get_glirn_dashboard_data", return_value=glirn_data), \
                patch("app.record_approval_event") as record_event:
            response = self.client.post(
                "/glirn/first-client-readiness/actions",
                json={
                    "item_id": "first-client-glirn-pe-partner-london-001",
                    "action_type": "approve",
                    "reason": "Gareth approved for human action only.",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "first_client_readiness_action_recorded")
        self.assertEqual(data["gareth_approval_status"], "approved_by_gareth")
        self.assertEqual(data["readiness_recommendation"], "approve_for_human_action")
        self.assertTrue(data["human_action_ready"])
        self.assertFalse(data["client_contact_enabled"])
        self.assertFalse(data["client_delivery_enabled"])
        self.assertFalse(data["invoicing_enabled"])
        record_event.assert_called_once()
        event = record_event.call_args.args[0]
        self.assertEqual(event["event_type"], "glirn_first_client_readiness_action")
        self.assertEqual(event["provider"], "glirn_first_client_readiness_gate")
        self.assertEqual(event["decision"], "APPROVED_FOR_HUMAN_ACTION")
        self.assertTrue(event["human_action_ready"])
        self.assertFalse(event["client_contact_enabled"])

    def test_glirn_first_client_readiness_reject_remains_blocked(self):
        glirn_data = {
            "first_client_readiness_gate": {
                "readiness_checks": [
                    {
                        "item_id": "first-client-glirn-ai-law-counsel-uae-001",
                        "opportunity_id": "glirn-ai-law-counsel-uae-001",
                        "title": "Technology & AI Law Counsel",
                    }
                ],
                "first_client_ready_items": [],
                "blocked_first_client_items": [],
                "monitored_first_client_items": [],
            }
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.get_glirn_dashboard_data", return_value=glirn_data), \
                patch("app.record_approval_event"):
            response = self.client.post(
                "/glirn/first-client-readiness/actions",
                json={
                    "item_id": "first-client-glirn-ai-law-counsel-uae-001",
                    "action_type": "reject",
                    "reason": "Not suitable for first client.",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["gareth_approval_status"], "rejected_by_gareth")
        self.assertEqual(data["readiness_recommendation"], "reject")
        self.assertFalse(data["human_action_ready"])

    def test_glirn_first_client_readiness_monitor_remains_pending(self):
        glirn_data = {
            "first_client_readiness_gate": {
                "readiness_checks": [
                    {
                        "item_id": "first-client-glirn-inhouse-singapore-001",
                        "opportunity_id": "glirn-inhouse-singapore-001",
                        "title": "In-House Counsel Opportunity",
                    }
                ],
                "first_client_ready_items": [],
                "blocked_first_client_items": [],
                "monitored_first_client_items": [],
            }
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.get_glirn_dashboard_data", return_value=glirn_data), \
                patch("app.record_approval_event"):
            response = self.client.post(
                "/glirn/first-client-readiness/actions",
                json={
                    "item_id": "first-client-glirn-inhouse-singapore-001",
                    "action_type": "monitor",
                    "reason": "Keep under review.",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["gareth_approval_status"], "monitoring")
        self.assertEqual(data["readiness_recommendation"], "monitor")
        self.assertFalse(data["human_action_ready"])

    def test_glirn_launch_readiness_approved_action_audit_logged(self):
        glirn_data = {
            "launch_readiness_command_centre": {
                "engine": "launch_readiness_command_centre",
                "launch_readiness_grade": "blocked",
                "launch_recommended_next_action": "confirm_payment_process",
            }
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.get_glirn_dashboard_data", return_value=glirn_data), \
                patch("app.record_approval_event") as record_event:
            response = self.client.post(
                "/glirn/launch-readiness/actions",
                json={
                    "action_type": "approve",
                    "reason": "Gareth approved human planning only.",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "launch_readiness_action_recorded")
        self.assertEqual(data["gareth_approval_status"], "approved_by_gareth")
        self.assertEqual(data["launch_action_status"], "approved_for_human_planning")
        self.assertFalse(data["autonomous_launch_enabled"])
        self.assertFalse(data["website_publishing_enabled"])
        self.assertFalse(data["linkedin_posting_enabled"])
        self.assertFalse(data["outreach_enabled"])
        record_event.assert_called_once()
        event = record_event.call_args.args[0]
        self.assertEqual(event["event_type"], "glirn_launch_readiness_action")
        self.assertEqual(event["provider"], "glirn_launch_readiness_command_centre")
        self.assertEqual(event["decision"], "APPROVED_FOR_HUMAN_PLANNING")
        self.assertFalse(event["autonomous_launch_enabled"])
        self.assertFalse(event["website_publishing_enabled"])

    def test_glirn_invoice_manual_sent_status_works(self):
        glirn_data = {
            "invoice_drafting_engine": {
                "invoice_drafts": [
                    {
                        "invoice_number": "GLIRN-INV-001",
                        "customer_name": "Client Firm A",
                        "amount": 85000,
                        "manual_sent_status": "not_sent",
                    }
                ]
            }
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.get_glirn_dashboard_data", return_value=glirn_data), \
                patch("app.record_approval_event") as record_event:
            response = self.client.post(
                "/glirn/invoices/actions",
                json={
                    "invoice_number": "GLIRN-INV-001",
                    "action_type": "mark-manually-sent",
                    "reason": "Gareth sent invoice manually.",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "invoice_action_recorded")
        self.assertEqual(data["manual_sent_status"], "sent_manually_by_gareth")
        self.assertEqual(data["invoice_readiness_status"], "manually_sent")
        self.assertFalse(data["automatic_sending_enabled"])
        self.assertFalse(data["paypal_api_enabled"])
        record_event.assert_called_once()
        event = record_event.call_args.args[0]
        self.assertEqual(event["event_type"], "glirn_invoice_action")
        self.assertEqual(event["provider"], "glirn_invoice_drafting_engine")
        self.assertEqual(event["decision"], "MARKED_MANUALLY_SENT")
        self.assertFalse(event["automatic_sending_enabled"])

    def test_glirn_invoice_manual_paid_status_works(self):
        glirn_data = {
            "invoice_drafting_engine": {
                "invoice_drafts": [
                    {
                        "invoice_number": "GLIRN-INV-001",
                        "customer_name": "Client Firm A",
                        "amount": 85000,
                        "manual_payment_status": "not_paid",
                    }
                ]
            }
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.get_glirn_dashboard_data", return_value=glirn_data), \
                patch("app.record_approval_event") as record_event:
            response = self.client.post(
                "/glirn/invoices/actions",
                json={
                    "invoice_number": "GLIRN-INV-001",
                    "action_type": "mark-manually-paid",
                    "reason": "Gareth confirmed payment manually.",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["manual_payment_status"], "paid_manually_confirmed_by_gareth")
        self.assertEqual(data["invoice_readiness_status"], "manual_payment_recorded")
        self.assertFalse(data["automatic_payment_collection_enabled"])
        self.assertFalse(data["automatic_payment_confirmation_enabled"])
        record_event.assert_called_once()
        self.assertEqual(record_event.call_args.args[0]["decision"], "MARKED_MANUALLY_PAID")

    def test_glirn_client_terms_manual_sent_status_works(self):
        glirn_data = {
            "client_terms_drafting_engine": {
                "client_terms_drafts": [
                    {
                        "terms_id": "GLIRN-TERMS-REVIEW-001",
                        "terms_type": "GBP 500 GLIRN Senior Legal Hiring Intelligence Review",
                        "manual_sent_status": "not_sent",
                    }
                ]
            }
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.get_glirn_dashboard_data", return_value=glirn_data), \
                patch("app.record_approval_event") as record_event:
            response = self.client.post(
                "/glirn/client-terms/actions",
                json={
                    "terms_id": "GLIRN-TERMS-REVIEW-001",
                    "action_type": "mark-manually-sent",
                    "reason": "Gareth sent terms manually.",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "client_terms_action_recorded")
        self.assertEqual(data["manual_sent_status"], "sent_manually_by_gareth")
        self.assertEqual(data["terms_readiness_status"], "manually_sent")
        self.assertFalse(data["automatic_sending_enabled"])
        self.assertFalse(data["esignature_integration_enabled"])
        record_event.assert_called_once()
        event = record_event.call_args.args[0]
        self.assertEqual(event["event_type"], "glirn_client_terms_action")
        self.assertEqual(event["provider"], "glirn_client_terms_drafting_engine")
        self.assertEqual(event["decision"], "MARKED_MANUALLY_SENT")
        self.assertFalse(event["automatic_sending_enabled"])

    def test_glirn_client_terms_manual_agreed_status_works(self):
        glirn_data = {
            "client_terms_drafting_engine": {
                "client_terms_drafts": [
                    {
                        "terms_id": "GLIRN-TERMS-CONTINGENCY-001",
                        "terms_type": "contingency search mandate",
                        "manual_agreed_status": "not_agreed",
                    }
                ]
            }
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.get_glirn_dashboard_data", return_value=glirn_data), \
                patch("app.record_approval_event") as record_event:
            response = self.client.post(
                "/glirn/client-terms/actions",
                json={
                    "terms_id": "GLIRN-TERMS-CONTINGENCY-001",
                    "action_type": "mark-manually-agreed",
                    "reason": "Gareth recorded manual client agreement.",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["manual_agreed_status"], "agreed_manually_by_gareth")
        self.assertEqual(data["terms_readiness_status"], "manual_agreement_recorded")
        self.assertFalse(data["automatic_agreement_enabled"])
        self.assertFalse(data["automatic_contract_acceptance_enabled"])
        self.assertFalse(data["solicitor_approved_claim"])
        record_event.assert_called_once()
        self.assertEqual(record_event.call_args.args[0]["decision"], "MARKED_MANUALLY_AGREED")

    def test_glirn_candidate_consent_action_audit_logging_works(self):
        glirn_data = {
            "candidate_consent_management_engine": {
                "candidate_consent_records": [
                    {
                        "candidate_id": "candidate-stub-002",
                        "candidate_name_placeholder": "Candidate B",
                        "consent_status": "draft",
                        "audit_reference": "consent-candidate-stub-002",
                    }
                ]
            }
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.get_glirn_dashboard_data", return_value=glirn_data), \
                patch("app.record_approval_event") as record_event:
            response = self.client.post(
                "/glirn/candidate-consents/actions",
                json={
                    "candidate_id": "candidate-stub-002",
                    "action_type": "mark-manually-received",
                    "reason": "Gareth received consent manually.",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "candidate_consent_action_recorded")
        self.assertEqual(data["consent_status"], "active")
        self.assertEqual(data["manual_received_status"], "received_manually_by_gareth")
        self.assertFalse(data["candidate_contact_enabled"])
        self.assertFalse(data["automated_consent_collection_enabled"])
        self.assertFalse(data["automated_consent_activation_enabled"])
        record_event.assert_called_once()
        event = record_event.call_args.args[0]
        self.assertEqual(event["event_type"], "glirn_candidate_consent_action")
        self.assertEqual(event["provider"], "glirn_candidate_consent_management_engine")
        self.assertEqual(event["decision"], "MARKED_MANUALLY_RECEIVED")
        self.assertFalse(event["candidate_contact_enabled"])

    def test_glirn_manual_delivery_mark_manually_delivered_status_works(self):
        glirn_data = {
            "manual_delivery_control_engine": {
                "delivery_ready_items": [
                    {
                        "delivery_id": "delivery-review-001",
                        "source_item_id": "glirn-review-001",
                        "title": "GLIRN Review",
                        "manual_delivery_status": "approved_for_manual_delivery",
                    }
                ],
                "blocked_delivery_items": [],
                "pending_delivery_approvals": [],
            }
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.get_glirn_dashboard_data", return_value=glirn_data), \
                patch("app.record_approval_event") as record_event:
            response = self.client.post(
                "/glirn/manual-delivery/actions",
                json={
                    "delivery_id": "delivery-review-001",
                    "action_type": "mark-manually-delivered",
                    "reason": "Gareth delivered manually.",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "manual_delivery_action_recorded")
        self.assertEqual(data["manual_delivery_status"], "delivered_manually_by_gareth")
        self.assertFalse(data["client_email_enabled"])
        self.assertFalse(data["external_upload_enabled"])
        self.assertFalse(data["candidate_contact_enabled"])
        record_event.assert_called_once()
        event = record_event.call_args.args[0]
        self.assertEqual(event["event_type"], "glirn_manual_delivery_action")
        self.assertEqual(event["provider"], "glirn_manual_delivery_control_engine")
        self.assertEqual(event["decision"], "MARKED_MANUALLY_DELIVERED")
        self.assertFalse(event["automatic_sending_enabled"])

    def test_glirn_launch_compliance_approve_status_and_audit_work(self):
        glirn_data = {
            "launch_compliance_validation_engine": {
                "compliance_ready_items": [
                    {
                        "validation_id": "compliance-review-001",
                        "source_item_id": "glirn-review-001",
                        "title": "GLIRN Review Compliance Check",
                        "compliance_validation_status": "ready_for_gareth_review",
                        "compliance_recommendation": "approve_for_human_use",
                        "compliance_risk_level": "low_risk",
                    }
                ],
                "compliance_blocked_items": [],
                "compliance_validation_checks": [],
            }
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.get_glirn_dashboard_data", return_value=glirn_data), \
                patch("app.record_approval_event") as record_event:
            response = self.client.post(
                "/glirn/launch-compliance/actions",
                json={
                    "validation_id": "compliance-review-001",
                    "action_type": "approve",
                    "reason": "Gareth approved compliance validation for human use.",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "launch_compliance_action_recorded")
        self.assertEqual(data["compliance_validation_status"], "approved_for_gareth_consideration")
        self.assertFalse(data["legal_advice_provided"])
        self.assertFalse(data["legal_certification_claimed"])
        self.assertFalse(data["global_legal_compliance_declared"])
        self.assertFalse(data["external_integrations_enabled"])
        record_event.assert_called_once()
        event = record_event.call_args.args[0]
        self.assertEqual(event["event_type"], "glirn_launch_compliance_action")
        self.assertEqual(event["provider"], "glirn_launch_compliance_validation_engine")
        self.assertEqual(event["decision"], "APPROVED_FOR_GARETH_CONSIDERATION")
        self.assertFalse(event["external_integrations_enabled"])

    def test_glirn_dry_run_action_audit_logging_works(self):
        glirn_data = {
            "first_client_dry_run": {
                "engine": "first_client_dry_run",
                "dry_run_status": "completed_pending_gareth_approval",
                "dry_run_readiness_score": 100,
                "approval_readiness_status": "ready_for_gareth_approval",
                "dry_run_blockers": [],
                "dry_run_warnings": [],
                "gareth_approval_package": {
                    "package_id": "glirn-first-client-dry-run-package-001",
                    "gareth_approval_required": True,
                    "external_action_enabled": False,
                },
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
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.get_glirn_dashboard_data", return_value=glirn_data), \
                patch("app.record_approval_event") as record_event:
            response = self.client.post(
                "/glirn/dry-run/actions",
                json={
                    "action_type": "run",
                    "reason": "Run first client dry-run rehearsal.",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "dry_run_action_recorded")
        self.assertEqual(data["dry_run_status"], "run_completed_pending_gareth_approval")
        self.assertEqual(data["dry_run_readiness_score"], 100)
        self.assertFalse(data["outreach_enabled"])
        self.assertFalse(data["delivery_enabled"])
        self.assertFalse(data["invoice_sending_enabled"])
        record_event.assert_called_once()
        event = record_event.call_args.args[0]
        self.assertEqual(event["event_type"], "glirn_first_client_dry_run_action")
        self.assertEqual(event["provider"], "glirn_first_client_dry_run")
        self.assertEqual(event["decision"], "RUN_COMPLETED")
        self.assertFalse(event["external_integrations_enabled"])

    def test_glirn_autonomous_operations_action_audit_logging_works(self):
        glirn_data = {
            "autonomous_internal_operations_orchestrator": {
                "engine": "autonomous_internal_operations_orchestrator",
                "autonomous_cycle_status": "completed_pending_gareth_final_decision",
                "final_gareth_approval_packages": [
                    {
                        "package_id": "glirn-autonomous-final-package-001",
                        "final_recommendation": "approve",
                        "gareth_final_decision_required": True,
                    }
                ],
                "autonomous_recommendation_queue": [],
                "autonomous_blockers": [],
                "autonomous_warnings": [],
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
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.get_glirn_dashboard_data", return_value=glirn_data), \
                patch("app.record_approval_event") as record_event:
            response = self.client.post(
                "/glirn/autonomous-operations/actions",
                json={
                    "action_type": "run-cycle",
                    "reason": "Run internal autonomous cycle.",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "autonomous_operations_action_recorded")
        self.assertEqual(data["autonomous_cycle_status"], "cycle_run_completed_pending_gareth_final_decision")
        self.assertFalse(data["client_contact_enabled"])
        self.assertFalse(data["candidate_contact_enabled"])
        self.assertFalse(data["deliverable_sending_enabled"])
        self.assertFalse(data["invoice_sending_enabled"])
        self.assertFalse(data["payment_collection_enabled"])
        record_event.assert_called_once()
        event = record_event.call_args.args[0]
        self.assertEqual(event["event_type"], "glirn_autonomous_internal_operations_action")
        self.assertEqual(event["provider"], "glirn_autonomous_internal_operations_orchestrator")
        self.assertEqual(event["decision"], "CYCLE_RUN_COMPLETED")
        self.assertFalse(event["external_integrations_enabled"])

    def test_public_website_pages_exist(self):
        expected_files = [
            "index.html",
            "about.html",
            "services.html",
            "intelligence-review.html",
            "executive-search.html",
            "contact.html",
            "privacy.html",
            "terms.html",
        ]

        for filename in expected_files:
            self.assertTrue(os.path.exists(os.path.join("public", filename)), filename)

    def test_public_index_route_serves_static_page(self):
        response = self.client.get("/public/index.html")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Global Legal Intelligence & Recruitment Network", response.text)

    def test_public_root_route_serves_index_page(self):
        response = self.client.get("/public/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Global Legal Intelligence & Recruitment Network", response.text)

    def test_public_homepage_contains_conversion_upgrade_copy(self):
        response = self.client.get("/public/index.html")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Helping law firms and legal professionals make better career and hiring decisions.",
            response.text,
        )
        self.assertIn("Why Clients Choose GLIRN", response.text)
        self.assertIn("GLIRN Principles", response.text)
        self.assertIn("Unsure whether to recruit?", response.text)
        self.assertIn(
            "AI-assisted, human-reviewed hiring intelligence, executive search support, and confidential career conversations for legal organisations and legal professionals at every stage of their journey.",
            response.text,
        )
        self.assertIn("Human-led. Technology-enhanced. Confidentiality-first.", response.text)
        self.assertIn("Reduce Hiring Risk Before Committing to Search", response.text)
        self.assertIn(
            "Gain greater clarity before committing to a full executive search process.",
            response.text,
        )
        self.assertIn("What the &pound;500 Senior Legal Hiring Intelligence Brief May Include", response.text)
        self.assertIn("Role and hiring priority assessment", response.text)
        self.assertIn("Market difficulty analysis", response.text)
        self.assertIn("Talent availability overview", response.text)
        self.assertIn("Search viability considerations", response.text)
        self.assertIn("Suggested discussion points", response.text)
        self.assertIn("Request a Confidential Brief", response.text)
        principle_items = [
            "Confidentiality-first approach",
            "Human-led decision making",
            "Technology-enhanced market intelligence",
            "No candidate details shared without consent",
            "Structured legal hiring intelligence support",
        ]
        self.assertIn('<ul class="principles-list">', response.text)
        for principle in principle_items:
            self.assertIn(f"<li>{principle}</li>", response.text)
        review_position = response.text.index("What the &pound;500 Senior Legal Hiring Intelligence Brief May Include")
        cta_position = response.text.index("Unsure whether to recruit?")
        trust_position = response.text.index("Why Clients Choose GLIRN")
        self.assertLess(review_position, cta_position)
        self.assertLess(cta_position, trust_position)
        self.assertNotIn(
            "Helping law firms and legal teams make better senior hiring decisions.",
            response.text,
        )
        self.assertNotIn(
            "GLIRN intends to explore relevant professional recruitment memberships and standards bodies as the business develops.",
            response.text,
        )
        self.assertNotIn(
            "Intelligence-led legal recruitment for law firms, specialist practices, and legal teams making senior hiring decisions.",
            response.text,
        )

    def test_public_homepage_supports_employers_and_future_legal_talent(self):
        response = self.client.get("/public/index.html")

        self.assertEqual(response.status_code, 200)
        for expected in [
            "Supporting Both Sides of the Legal Talent Market",
            "For Legal Professionals &amp; Future Legal Leaders",
            "Future Legal Leaders",
            "Newly Qualified Solicitors",
            "Candidate Confidentiality",
            "No candidate information is shared without consent.",
            "The GLIRN Approach",
            "Register Your Interest Confidentially",
        ]:
            self.assertIn(expected, response.text)

    def test_public_homepage_explains_career_pathways_standards_and_next_steps(self):
        response = self.client.get("/public/index.html")

        self.assertEqual(response.status_code, 200)
        for expected in [
            "Understanding Legal Career Pathways",
            "Supporting Legal Talent at Every Career Stage",
            "Professional Standards",
            "Newly Qualified Solicitor",
            "Associate",
            "Senior Associate",
            "Legal Director",
            "Partner",
            "General Counsel",
            "Chief Legal Officer",
            "Ready to Take the Next Step?",
            "Request a Confidential Brief",
            "Arrange a Confidential Career Discussion",
            "Arrange a confidential career discussion to explore opportunities, long-term career progression, and your future within the legal profession.",
            "Ethical candidate handling",
            "Long-term relationship focus",
            "Future-focused legal talent development",
        ]:
            self.assertIn(expected, response.text)

        final_cta_position = response.text.index("Ready to Take the Next Step?")
        principles_position = response.text.index("GLIRN Principles")
        self.assertGreater(final_cta_position, principles_position)

        prohibited_claims = [
            "rec member",
            "rec certified",
            "regulated by rec",
            "recruitment qualification",
            "legal qualification",
            "professionally accredited",
        ]
        body = response.text.lower()
        for claim in prohibited_claims:
            self.assertNotIn(claim, body)

    def test_public_pages_do_not_claim_unheld_recruitment_credentials(self):
        prohibited = [
            "rec member",
            "rec certified",
            "regulated by rec",
            "accredited",
            "qualified legal recruiters",
        ]
        for page in ["index.html", "about.html", "services.html", "contact.html"]:
            body = self.client.get(f"/public/{page}").text.lower()
            for claim in prohibited:
                self.assertNotIn(claim, body, page)

    def test_about_page_retains_restrained_future_membership_context(self):
        response = self.client.get("/public/about.html")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "GLIRN intends to explore relevant professional recruitment memberships and standards bodies as the business develops.",
            response.text,
        )

    def test_intelligence_brief_page_contains_expanded_manually_accepted_brief(self):
        response = self.client.get("/public/intelligence-review.html")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Role and hiring priority assessment", response.text)
        self.assertIn("Market difficulty analysis", response.text)
        self.assertIn("Talent availability overview", response.text)
        self.assertIn("Search viability considerations", response.text)
        self.assertIn("Suggested discussion points", response.text)
        self.assertIn("&pound;500", response.text)
        self.assertIn("Unsure whether to recruit?", response.text)
        self.assertIn("Request a Confidential Brief", response.text)
        self.assertIn("A confidential first step", response.text)
        self.assertIn("Gain clarity before committing to search.", response.text)
        self.assertIn("subject to manual scope review and written acceptance before paid work begins", response.text)
        self.assertIn("No payment is requested automatically.", response.text)
        self.assertIn('<ul class="principles-list">', response.text)

    def test_public_pages_use_safe_intelligence_brief_positioning(self):
        pages = [
            "index.html",
            "about.html",
            "services.html",
            "intelligence-review.html",
            "executive-search.html",
            "contact.html",
            "privacy.html",
            "terms.html",
        ]
        disclaimer = (
            "GLIRN does not provide legal advice, regulated recruitment advice, or guaranteed hiring outcomes. "
            "Any intelligence brief is intended to support internal discussion and must be reviewed alongside "
            "independent professional judgement."
        )

        for page in pages:
            response = self.client.get(f"/public/{page}")
            self.assertEqual(response.status_code, 200, page)
            self.assertIn(disclaimer, response.text, page)
            self.assertNotIn("Senior Legal Hiring Intelligence Review", response.text, page)
            self.assertNotIn("Hiring Intelligence Review", response.text, page)
            self.assertNotIn("Professional legal recruitment support", response.text, page)

        homepage = self.client.get("/public/index.html").text
        contact = self.client.get("/public/contact.html").text
        terms = self.client.get("/public/terms.html").text
        self.assertIn("AI-assisted, human-reviewed", homepage)
        self.assertIn("All enquiries are manually reviewed before any paid work is accepted.", contact)
        self.assertIn("No payment is requested automatically.", homepage)
        self.assertIn("GLIRN does not take automatic payment through the public website.", terms)
        self.assertIn("GBP 500 Senior Legal Hiring Intelligence Brief", contact)
        qa_statement = "Every intelligence brief is subject to human review and quality assurance before delivery."
        decline_statement = (
            "GLIRN may decline engagements where another specialist adviser would better serve the client's needs."
        )
        for page in ["index.html", "services.html", "intelligence-review.html", "terms.html"]:
            body = self.client.get(f"/public/{page}").text
            self.assertIn(qa_statement, body, page)
            self.assertIn(decline_statement, body, page)

    def test_core_public_pages_return_200_without_prohibited_claims(self):
        pages = [
            "index.html",
            "about.html",
            "services.html",
            "intelligence-review.html",
            "executive-search.html",
            "contact.html",
        ]

        for page in pages:
            response = self.client.get(f"/public/{page}")
            self.assertEqual(response.status_code, 200, page)
            body = response.text.lower()
            self.assertNotIn("we provide legal advice", body, page)
            self.assertNotIn("legal advice service", body, page)
            self.assertNotIn("guaranteed placement", body, page)
            self.assertNotIn("placement guaranteed", body, page)

    def test_render_release_manifest_uses_public_bind_and_health_check(self):
        project_root = Path(__file__).resolve().parents[1]
        requirements = (project_root / "requirements.txt").read_text(encoding="utf-8")
        render_config = (project_root / "render.yaml").read_text(encoding="utf-8")
        gitignore = (project_root / ".gitignore").read_text(encoding="utf-8")

        for dependency in ["fastapi", "pydantic", "requests", "uvicorn"]:
            self.assertIn(dependency, requirements.lower())
        self.assertIn("uvicorn app:app --host 0.0.0.0 --port $PORT", render_config)
        self.assertIn("healthCheckPath: /health", render_config)
        self.assertIn("mountPath: /var/data", render_config)
        self.assertIn("value: /var/data/glirn_live.db", render_config)
        self.assertIn("sync: false", render_config)
        self.assertIn(".env", gitignore)

    def test_public_static_mount_is_independent_of_working_directory(self):
        self.assertEqual(Path(app.BASE_DIR), Path(app.__file__).resolve().parent)
        self.assertTrue((app.BASE_DIR / "public" / "index.html").is_file())

    def test_sqlite_schema_auto_creates_and_enquiry_survives_reload(self):
        original_leads = list(app.PUBLIC_LEADS)
        original_approvals = dict(app.FINAL_APPROVAL_LOCAL_STATUS)
        original_stages = dict(app.REVENUE_LEDGER_LOCAL_STAGE)
        original_exports = {key: list(value) for key, value in app.PERSISTED_EXPORT_METADATA.items()}
        try:
            with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
                os.environ,
                {"GLIRN_DB_PATH": os.path.join(temp_dir, "nested", "glirn.db")},
                clear=False,
            ):
                lead = {"lead_id": "persisted-lead-1", "name": "Persistent Client"}
                route = {"lead_id": "persisted-lead-1", "lead_route": "intelligence_review_lead"}
                package = {"package_id": "persisted-package-1", "lead_id": "persisted-lead-1"}
                glirn_storage.upsert_record("website_enquiry", lead["lead_id"], lead)
                glirn_storage.upsert_record("lead_routing_result", route["lead_id"], route)
                glirn_storage.upsert_record("revenue_approval_package", package["package_id"], package)

                app.reload_persistent_state()

                self.assertEqual(app.PUBLIC_LEADS, [lead])
                self.assertEqual(glirn_storage.list_records("lead_routing_result"), [route])
                self.assertEqual(glirn_storage.list_records("revenue_approval_package"), [package])
                self.assertTrue(Path(os.environ["GLIRN_DB_PATH"]).is_file())
        finally:
            app.PUBLIC_LEADS[:] = original_leads
            app.FINAL_APPROVAL_LOCAL_STATUS.clear()
            app.FINAL_APPROVAL_LOCAL_STATUS.update(original_approvals)
            app.REVENUE_LEDGER_LOCAL_STAGE.clear()
            app.REVENUE_LEDGER_LOCAL_STAGE.update(original_stages)
            app.PERSISTED_EXPORT_METADATA.update(original_exports)

    def test_approval_and_revenue_ledger_state_survive_reload(self):
        original_approvals = dict(app.FINAL_APPROVAL_LOCAL_STATUS)
        original_stages = dict(app.REVENUE_LEDGER_LOCAL_STAGE)
        try:
            with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
                os.environ,
                {"GLIRN_DB_PATH": os.path.join(temp_dir, "glirn.db")},
                clear=False,
            ):
                approval_state = {"approval-1": "approved_by_gareth"}
                ledger_state = {"approval-1": "payment_pending_manual"}
                ledger_record = {
                    "ledger_record_id": "ledger-1",
                    "final_approval_id": "approval-1",
                    "revenue_stage": "payment_pending_manual",
                    "actual_revenue_received": 0,
                }
                glirn_storage.set_state("final_approval_statuses", approval_state)
                glirn_storage.set_state("revenue_ledger_stages", ledger_state)
                glirn_storage.upsert_record("revenue_ledger_record", "ledger-1", ledger_record)

                app.reload_persistent_state()

                self.assertEqual(app.FINAL_APPROVAL_LOCAL_STATUS, approval_state)
                self.assertEqual(app.REVENUE_LEDGER_LOCAL_STAGE, ledger_state)
                self.assertEqual(glirn_storage.list_records("revenue_ledger_record"), [ledger_record])
        finally:
            app.FINAL_APPROVAL_LOCAL_STATUS.clear()
            app.FINAL_APPROVAL_LOCAL_STATUS.update(original_approvals)
            app.REVENUE_LEDGER_LOCAL_STAGE.clear()
            app.REVENUE_LEDGER_LOCAL_STAGE.update(original_stages)

    def test_export_metadata_and_audit_safe_history_survive_reload(self):
        original_exports = {key: list(value) for key, value in app.PERSISTED_EXPORT_METADATA.items()}
        try:
            with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
                os.environ,
                {"GLIRN_DB_PATH": os.path.join(temp_dir, "glirn.db")},
                clear=False,
            ):
                records = {
                    "email_draft": ("email_draft_export", "email-1", {"email_draft_export_id": "email-1", "email_sent": False}),
                    "invoice_draft": ("invoice_draft_export", "invoice-1", {"invoice_draft_export_id": "invoice-1", "invoice_sent": False}),
                    "deal_pack": ("deal_pack_export", "deal-1", {"deal_pack_export_id": "deal-1", "client_contact_executed": False}),
                }
                for _, (category, record_id, payload) in records.items():
                    glirn_storage.upsert_record(category, record_id, payload)
                glirn_storage.append_action(
                    "final_approval_action",
                    "approval-1",
                    {"final_approval_status": "approved_by_gareth", "external_action_enabled": False},
                )

                app.reload_persistent_state()

                for export_type, (_, _, payload) in records.items():
                    self.assertEqual(app.PERSISTED_EXPORT_METADATA[export_type], [payload])
                history = glirn_storage.list_actions()
                self.assertEqual(history[0]["action_type"], "final_approval_action")
                self.assertFalse(history[0]["payload"]["external_action_enabled"])
        finally:
            app.PERSISTED_EXPORT_METADATA.update(original_exports)

    def test_health_reports_persistence_path_and_default_warning(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ,
            {"GLIRN_DB_PATH": os.path.join(temp_dir, "glirn.db")},
            clear=False,
        ), patch("app.load_provider_config", return_value=[]):
            configured = app.health()

        self.assertTrue(configured["persistence_enabled"])
        self.assertTrue(configured["persistence_path"].endswith("glirn.db"))
        self.assertNotIn("persistence_warning", configured)

        with patch.dict(os.environ, {}, clear=True), patch("app.load_provider_config", return_value=[]):
            default = app.health()
        self.assertEqual(
            default["persistence_warning"],
            "GLIRN_DB_PATH is using non-persistent default storage",
        )

    def test_persisted_enquiry_reappears_in_gareth_command_centre_after_reload(self):
        original_leads = list(app.PUBLIC_LEADS)
        try:
            with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
                os.environ,
                {"GLIRN_DB_PATH": os.path.join(temp_dir, "glirn.db")},
                clear=False,
            ), patch("app.list_pending_approvals", return_value=[]):
                lead = {
                    "lead_id": "persisted-command-lead",
                    "name": "Persistent Search Client",
                    "organisation": "Persistent Legal LLP",
                    "email": "persistent@example.com",
                    "country": "England",
                    "inquiry_type": "Executive Search Enquiry",
                    "legal_sector": "Corporate Law",
                    "practice_area": "Corporate Law",
                    "jurisdiction": "England & Wales",
                    "hiring_need": "Partner search",
                    "seniority_level": "Partner",
                    "timescale": "1-3 months",
                    "message": "Confidential executive search support required.",
                    "consent": True,
                    "received_at": "2026-06-08T00:00:00+00:00",
                }
                glirn_storage.upsert_record("website_enquiry", lead["lead_id"], lead)
                app.PUBLIC_LEADS.clear()
                app.reload_persistent_state()

                response = self.client.get("/glirn/dashboard")

                self.assertEqual(response.status_code, 200)
                opportunities = response.json()["gareth_command_centre"]["revenue_opportunities"]
                self.assertTrue(any(item["client_firm_name"] == "Persistent Legal LLP" for item in opportunities))
        finally:
            app.PUBLIC_LEADS[:] = original_leads

    def test_upgraded_public_lead_form_exists(self):
        response = self.client.get("/public/contact.html")

        self.assertEqual(response.status_code, 200)
        self.assertIn('name="inquiry_type"', response.text)
        self.assertIn('name="practice_area"', response.text)
        self.assertIn('name="jurisdiction"', response.text)
        self.assertIn('name="timescale"', response.text)
        self.assertIn("/glirn/public-leads/intake", response.text)
        self.assertIn('maxlength="2000"', response.text)
        self.assertIn("Senior Legal Professional Career Discussion", response.text)
        self.assertIn("Newly Qualified / Future Legal Leader Interest", response.text)
        self.assertIn('name="career_stage"', response.text)
        self.assertIn('name="confidential_career_interest"', response.text)

    def test_senior_and_future_legal_candidate_enquiries_route_safely(self):
        base = {
            "organisation": "Candidate Confidential",
            "country": "England",
            "legal_sector": "Technology & AI Law",
            "practice_area": "Technology & AI Law",
            "jurisdiction": "England & Wales",
            "hiring_need": "Confidential career discussion",
            "timescale": "Exploratory",
            "message": "I would welcome a confidential discussion.",
            "consent": True,
        }
        cases = [
            ({
                **base,
                "name": "Senior Candidate",
                "email": "senior.candidate@example.com",
                "inquiry_type": "Senior Legal Professional Career Discussion",
                "seniority_level": "General Counsel",
                "career_stage": "General Counsel / Chief Legal Officer",
                "confidential_career_interest": "Leadership opportunity exploration",
            }, "senior_legal_candidate_lead", "senior_legal_candidate_confidential_review"),
            ({
                **base,
                "name": "Future Leader",
                "email": "future.leader@example.com",
                "inquiry_type": "Newly Qualified / Future Legal Leader Interest",
                "seniority_level": "Newly Qualified Solicitor",
                "career_stage": "Newly Qualified Solicitor",
                "confidential_career_interest": "Building a specialist legal career",
            }, "future_legal_leader_candidate_lead", "future_legal_leader_confidential_review"),
        ]

        for payload, expected_type, expected_route in cases:
            with patch("app.PUBLIC_LEADS", []), \
                    patch("app.PUBLIC_LEAD_SUBMISSION_TIMES", {}), \
                    patch("app.record_approval_event"):
                response = self.client.post("/glirn/public-leads/intake", json=payload)

            self.assertEqual(response.status_code, 200, response.text)
            data = response.json()
            self.assertEqual(data["lead_type"], expected_type)
            self.assertEqual(data["lead_route"], expected_route)
            self.assertEqual(data["estimated_revenue_opportunity"], 0)
            self.assertTrue(data["gareth_final_approval_required"])
            self.assertFalse(data["automatic_email_enabled"])
            self.assertFalse(data["automatic_linkedin_messaging_enabled"])
            self.assertFalse(data["automatic_introductions_enabled"])
            self.assertFalse(data["candidate_information_sharing_enabled"])
            self.assertFalse(data["client_contact_enabled"])
            self.assertFalse(data["candidate_contact_enabled"])
            self.assertFalse(data["payment_collection_enabled"])
            self.assertFalse(data["external_integrations_enabled"])

    def test_employer_and_candidate_acknowledgements_are_created_immediately(self):
        base = {
            "organisation": "Confidential Legal LLP",
            "country": "England",
            "legal_sector": "Corporate Law",
            "practice_area": "Corporate Law",
            "jurisdiction": "England & Wales",
            "hiring_need": "Confidential review",
            "seniority_level": "Partner",
            "timescale": "Exploratory",
            "message": "Please review this enquiry personally.",
            "consent": True,
        }
        cases = [
            ({
                **base,
                "name": "Employer Contact",
                "email": "ack.employer@example.com",
                "inquiry_type": "Law Firm / Legal Team Enquiry",
            }, "GLIRN Enquiry Received", "will be reviewed confidentially", "employer"),
            ({
                **base,
                "name": "Candidate Contact",
                "email": "ack.candidate@example.com",
                "inquiry_type": "Senior Legal Professional Career Discussion",
                "career_stage": "General Counsel / Chief Legal Officer",
                "confidential_career_interest": "Discreet market exploration",
            }, "GLIRN Confidential Career Enquiry Received", "No candidate information is shared without consent", "candidate"),
        ]

        for payload, subject, expected_body, recipient_type in cases:
            with self.subTest(recipient_type=recipient_type), tempfile.TemporaryDirectory() as tmpdir, \
                    patch.dict("os.environ", {"GLIRN_DB_PATH": os.path.join(tmpdir, "live.db")}, clear=True), \
                    patch("app.PUBLIC_LEADS", []), \
                    patch("app.PUBLIC_LEAD_SUBMISSION_TIMES", {}), \
                    patch("app.PERSISTED_RESPONSE_PACKAGES", []), \
                    patch("glirn_responses.smtplib.SMTP") as smtp, \
                    patch("app.record_approval_event"):
                response = self.client.post("/glirn/public-leads/intake", json=payload)

            self.assertEqual(response.status_code, 200, response.text)
            acknowledgement = response.json()["acknowledgement"]
            self.assertEqual(acknowledgement["subject"], subject)
            self.assertIn(expected_body, acknowledgement["body"])
            self.assertEqual(acknowledgement["recipient_type"], recipient_type)
            self.assertEqual(acknowledgement["acknowledgement_status"], "queued_local_only")
            self.assertFalse(acknowledgement["email_sent"])
            self.assertTrue(response.json()["automatic_acknowledgement_enabled"])
            smtp.assert_not_called()

    def test_only_approved_faq_topics_use_predefined_automatic_templates(self):
        cases = {
            "intelligence_review": "What is the GBP 500 Intelligence Review?",
            "services": "What services does GLIRN provide?",
            "confidentiality": "Are enquiries confidential?",
            "candidates": "Does GLIRN support candidates?",
            "future_legal_leaders": "Does GLIRN support future legal leaders?",
            "international": "Does GLIRN work internationally?",
        }
        with tempfile.TemporaryDirectory() as tmpdir, \
                patch.dict("os.environ", {"GLIRN_DB_PATH": os.path.join(tmpdir, "live.db")}, clear=True), \
                patch("app.PUBLIC_LEADS", []), \
                patch("app.PUBLIC_LEAD_SUBMISSION_TIMES", {}), \
                patch("app.PERSISTED_RESPONSE_PACKAGES", []), \
                patch("app.record_approval_event"):
            for index, (expected_topic, message) in enumerate(cases.items(), start=1):
                payload = {
                    "name": f"FAQ Contact {index}",
                    "organisation": "FAQ Legal LLP",
                    "email": f"faq{index}@example.com",
                    "country": "England",
                    "inquiry_type": "General Enquiry",
                    "legal_sector": "Corporate Law",
                    "hiring_need": "Information request",
                    "seniority_level": "Other",
                    "message": message,
                    "consent": True,
                }
                response = self.client.post("/glirn/public-leads/intake", json=payload)
                self.assertEqual(response.status_code, 200, response.text)
                faq = response.json()["faq_response"]
                self.assertEqual(faq["topic"], expected_topic)
                self.assertTrue(faq["predefined_template_only"])
                self.assertFalse(faq["freeform_ai_response_enabled"])
                self.assertEqual(faq["faq_response_status"], "queued_local_only")
                self.assertEqual(response.json()["draft_response"]["response_status"], "safe_faq_template_handled")

    def test_non_faq_enquiry_creates_approval_gated_draft_only(self):
        payload = {
            "name": "Bespoke Search Contact",
            "organisation": "Bespoke Legal LLP",
            "email": "bespoke.response@example.com",
            "country": "England",
            "inquiry_type": "Executive Search Enquiry",
            "legal_sector": "Corporate Law",
            "hiring_need": "Partner succession planning",
            "seniority_level": "Partner",
            "message": "We need a tailored response concerning a sensitive partner succession requirement.",
            "consent": True,
        }
        with tempfile.TemporaryDirectory() as tmpdir, \
                patch.dict("os.environ", {"GLIRN_DB_PATH": os.path.join(tmpdir, "live.db")}, clear=True), \
                patch("app.PUBLIC_LEADS", []), \
                patch("app.PUBLIC_LEAD_SUBMISSION_TIMES", {}), \
                patch("app.PERSISTED_RESPONSE_PACKAGES", []), \
                patch("app.record_approval_event"):
            response = self.client.post("/glirn/public-leads/intake", json=payload)

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertIsNone(data["faq_response"])
        self.assertEqual(data["draft_response"]["response_status"], "awaiting_gareth_approval")
        self.assertTrue(data["draft_response"]["gareth_approval_required"])
        self.assertFalse(data["draft_response"]["substantive_response_sent"])
        self.assertFalse(data["draft_response"]["automatic_sending_enabled"])
        self.assertFalse(data["automatic_email_enabled"])

    def test_response_package_persists_after_reload_and_appears_in_command_centre(self):
        payload = {
            "name": "Persistent Enquiry",
            "organisation": "Persistent Legal LLP",
            "email": "persistent.response@example.com",
            "country": "England",
            "inquiry_type": "Law Firm / Legal Team Enquiry",
            "legal_sector": "Corporate Law",
            "hiring_need": "Confidential hiring support",
            "seniority_level": "Partner",
            "message": "Please prepare a tailored confidential response.",
            "consent": True,
        }
        with tempfile.TemporaryDirectory() as tmpdir, \
                patch.dict("os.environ", {"GLIRN_DB_PATH": os.path.join(tmpdir, "live.db")}, clear=True), \
                patch("app.PUBLIC_LEADS", []), \
                patch("app.PUBLIC_LEAD_SUBMISSION_TIMES", {}), \
                patch("app.FINAL_APPROVAL_LOCAL_STATUS", {}), \
                patch("app.REVENUE_LEDGER_LOCAL_STAGE", {}), \
                patch("app.PERSISTED_EXPORT_METADATA", {"email_draft": [], "invoice_draft": [], "deal_pack": []}), \
                patch("app.PERSISTED_RESPONSE_PACKAGES", []) as response_packages, \
                patch("app.record_approval_event"):
            response = self.client.post("/glirn/public-leads/intake", json=payload)
            self.assertEqual(response.status_code, 200, response.text)
            response_packages.clear()
            app.reload_persistent_state()
            self.assertEqual(len(response_packages), 1)
            dashboard_response = self.client.get("/glirn/dashboard")
            ui_response = self.client.get("/ui")

        self.assertEqual(dashboard_response.status_code, 200)
        pending = dashboard_response.json()["gareth_command_centre"]["new_enquiries_awaiting_review"]
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["acknowledgement"]["acknowledgement_status"], "queued_local_only")
        self.assertEqual(pending[0]["draft_response"]["response_status"], "awaiting_gareth_approval")
        self.assertIn("New Enquiries Awaiting Review", ui_response.text)
        self.assertIn("Approve &amp; Send", ui_response.text)
        self.assertIn("Request More Information", ui_response.text)

    def test_configured_smtp_transport_sends_fixed_template(self):
        smtp_environment = {
            "GLIRN_SMTP_HOST": "smtp.example.com",
            "GLIRN_SMTP_PORT": "587",
            "GLIRN_SMTP_USERNAME": "glirn-user",
            "GLIRN_SMTP_PASSWORD": "test-password",
            "GLIRN_FROM_EMAIL": "enquiries@example.com",
        }
        with patch.dict("os.environ", smtp_environment, clear=True), \
                patch("glirn_responses.smtplib.SMTP") as smtp:
            result = glirn_responses.deliver_template_email(
                "recipient@example.com",
                glirn_responses.EMPLOYER_ACKNOWLEDGEMENT["subject"],
                glirn_responses.EMPLOYER_ACKNOWLEDGEMENT["body"],
            )

        self.assertEqual(result["status"], "sent")
        self.assertTrue(result["email_sent"])
        smtp.assert_called_once_with("smtp.example.com", 587, timeout=10)
        transport = smtp.return_value.__enter__.return_value
        transport.starttls.assert_called_once_with()
        transport.login.assert_called_once_with("glirn-user", "test-password")
        transport.send_message.assert_called_once()

    def test_enquiry_notification_email_contains_required_fields_and_full_message(self):
        enquiry = {
            "lead_id": "public-lead-108",
            "received_at": "2026-06-11T09:15:00+00:00",
            "inquiry_type": "Executive Search Enquiry",
            "name": "Alex Client",
            "organisation": "Example Legal LLP",
            "country": "England",
            "practice_area": "Technology Law",
            "jurisdiction": "England & Wales",
            "seniority_level": "Partner",
            "timescale": "1-3 months",
            "message": "This is the complete confidential enquiry message.",
        }

        email = notification_service.build_enquiry_notification_email(enquiry)

        self.assertEqual(
            email["subject"],
            "[GLIRN] New Enquiry Received – Manual Review Required",
        )
        self.assertEqual(
            email["recipient_address"],
            "legalintelligencerecruitment@outlook.com",
        )
        for expected in [
            "Enquiry ID: public-lead-108",
            "Submission timestamp: 2026-06-11T09:15:00+00:00",
            "Enquiry type: Executive Search Enquiry",
            "Name: Alex Client",
            "Organisation: Example Legal LLP",
            "Country: England",
            "Practice area: Technology Law",
            "Jurisdiction: England & Wales",
            "Seniority: Partner",
            "Timescale: 1-3 months",
            "This is the complete confidential enquiry message.",
            notification_service.MANUAL_REVIEW_NOTICE,
        ]:
            self.assertIn(expected, email["body"])

    def test_configured_business_notification_sends_to_fixed_recipient(self):
        enquiry = {
            "lead_id": "public-lead-108",
            "received_at": "2026-06-11T09:15:00+00:00",
            "inquiry_type": "General Enquiry",
            "name": "Notification Test",
            "organisation": "Example Legal LLP",
            "country": "England",
            "practice_area": "Corporate Law",
            "jurisdiction": "England & Wales",
            "seniority_level": "Partner",
            "timescale": "Exploratory",
            "message": "Please notify Gareth.",
        }
        smtp_environment = {
            "GLIRN_SMTP_HOST": "smtp.example.com",
            "GLIRN_SMTP_PORT": "587",
            "GLIRN_SMTP_USERNAME": "glirn-user",
            "GLIRN_SMTP_PASSWORD": "test-password",
            "GLIRN_FROM_EMAIL": "enquiries@example.com",
        }

        with patch.dict("os.environ", smtp_environment, clear=True), \
                patch("notification_service.smtplib.SMTP") as smtp:
            result = notification_service.deliver_enquiry_notification(enquiry)

        self.assertEqual(result["delivery_status"], "sent")
        self.assertEqual(result["recipient_address"], notification_service.GLIRN_BUSINESS_EMAIL)
        self.assertEqual(result["attempt_count"], 1)
        transport = smtp.return_value.__enter__.return_value
        sent_message = transport.send_message.call_args.args[0]
        self.assertEqual(sent_message["To"], notification_service.GLIRN_BUSINESS_EMAIL)
        self.assertEqual(sent_message["Subject"], notification_service.NOTIFICATION_SUBJECT)
        self.assertIn(notification_service.MANUAL_REVIEW_NOTICE, sent_message.get_content())

    def test_notification_failure_does_not_prevent_enquiry_persistence(self):
        payload = {
            "name": "Failure Test",
            "organisation": "Failure Legal LLP",
            "email": "failure@example.com",
            "country": "England",
            "inquiry_type": "Law Firm / Legal Team Enquiry",
            "legal_sector": "Corporate Law",
            "practice_area": "Corporate Law",
            "jurisdiction": "England & Wales",
            "hiring_need": "Partner review",
            "seniority_level": "Partner",
            "timescale": "1-3 months",
            "message": "Persist this enquiry even when notification delivery fails.",
            "consent": True,
        }
        failed_notification = {
            "notification_id": "glirn-enquiry-notification-public-lead-001",
            "related_enquiry_id": "public-lead-001",
            "recipient_address": notification_service.GLIRN_BUSINESS_EMAIL,
            "delivery_status": "delivery_failed",
            "created_at": "2026-06-11T09:00:00+00:00",
            "last_attempt_at": "2026-06-11T09:00:00+00:00",
            "delivered_at": None,
            "attempt_count": 1,
            "retry_attempts": 0,
            "failure_reason": "smtp_delivery_failed",
            "manual_resend_available": True,
            "informational_only": True,
            "business_email_notification_only": True,
            "automatic_acceptance_enabled": False,
            "automatic_payment_enabled": False,
            "automatic_brief_generation_enabled": False,
            "automatic_candidate_outreach_enabled": False,
            "automatic_search_activity_enabled": False,
            "automatic_delivery_enabled": False,
            "external_integrations_enabled": False,
        }

        with tempfile.TemporaryDirectory() as tmpdir, \
                patch.dict("os.environ", {"GLIRN_DB_PATH": os.path.join(tmpdir, "live.db")}, clear=True), \
                patch("app.PUBLIC_LEADS", []), \
                patch("app.PUBLIC_LEAD_SUBMISSION_TIMES", {}), \
                patch("app.PERSISTED_RESPONSE_PACKAGES", []), \
                patch("app.PERSISTED_ENQUIRY_NOTIFICATIONS", []), \
                patch("app.deliver_enquiry_notification", return_value=failed_notification), \
                patch("app.record_approval_event"):
            response = self.client.post("/glirn/public-leads/intake", json=payload)
            enquiries = glirn_storage.list_records("website_enquiry")
            notifications = glirn_storage.list_records("enquiry_notification_record")
            actions = glirn_storage.list_actions()

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(enquiries), 1)
        self.assertEqual(enquiries[0]["message"], payload["message"])
        self.assertEqual(notifications[0]["delivery_status"], "delivery_failed")
        notification_actions = [item for item in actions if item["action_type"] == "enquiry_notification_attempt"]
        self.assertEqual(len(notification_actions), 1)
        self.assertNotIn("message", notification_actions[0]["payload"])
        self.assertFalse(notification_actions[0]["payload"]["sensitive_enquiry_content_logged"])

    def test_manual_notification_resend_updates_retry_status(self):
        enquiry = {
            "lead_id": "public-lead-108",
            "name": "Resend Test",
            "message": "Confidential message",
        }
        previous = {
            "notification_id": "glirn-enquiry-notification-public-lead-108",
            "related_enquiry_id": "public-lead-108",
            "recipient_address": notification_service.GLIRN_BUSINESS_EMAIL,
            "delivery_status": "delivery_failed",
            "created_at": "2026-06-11T09:00:00+00:00",
            "last_attempt_at": "2026-06-11T09:00:00+00:00",
            "attempt_count": 1,
            "retry_attempts": 0,
            "failure_reason": "smtp_not_configured",
        }
        resent = {
            **previous,
            "delivery_status": "sent",
            "last_attempt_at": "2026-06-11T09:05:00+00:00",
            "delivered_at": "2026-06-11T09:05:00+00:00",
            "attempt_count": 2,
            "retry_attempts": 1,
            "failure_reason": None,
            "manual_resend_available": False,
        }

        with tempfile.TemporaryDirectory() as tmpdir, \
                patch.dict("os.environ", {"GLIRN_DB_PATH": os.path.join(tmpdir, "live.db")}, clear=True), \
                patch("app.PUBLIC_LEADS", [enquiry]), \
                patch("app.PERSISTED_ENQUIRY_NOTIFICATIONS", [previous]), \
                patch("app.deliver_enquiry_notification", return_value=resent):
            response = self.client.post(
                "/glirn/enquiry-notifications/glirn-enquiry-notification-public-lead-108/resend",
                json={"reason": "Retry after SMTP configuration check."},
            )

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["notification"]["delivery_status"], "sent")
        self.assertEqual(data["notification"]["retry_attempts"], 1)
        self.assertTrue(data["informational_only"])
        self.assertFalse(data["automatic_acceptance_enabled"])
        self.assertFalse(data["automatic_payment_enabled"])
        self.assertFalse(data["automatic_brief_generation_enabled"])
        self.assertFalse(data["automatic_candidate_outreach_enabled"])
        self.assertFalse(data["automatic_search_activity_enabled"])
        self.assertFalse(data["automatic_delivery_enabled"])
        self.assertFalse(data["external_integrations_enabled"])

    def test_command_centre_surfaces_notification_failure_and_manual_resend(self):
        failed = {
            "notification_id": "glirn-enquiry-notification-public-lead-108",
            "related_enquiry_id": "public-lead-108",
            "recipient_address": notification_service.GLIRN_BUSINESS_EMAIL,
            "delivery_status": "delivery_failed",
            "last_attempt_at": "2026-06-11T09:00:00+00:00",
            "retry_attempts": 0,
        }
        with patch("app.PERSISTED_ENQUIRY_NOTIFICATIONS", [failed]), \
                patch("app.list_pending_approvals", return_value=[]):
            dashboard_response = self.client.get("/glirn/dashboard")
            ui_response = self.client.get("/ui")

        self.assertEqual(dashboard_response.status_code, 200)
        summary = dashboard_response.json()["gareth_command_centre"]["enquiry_notification_summary"]
        self.assertEqual(summary["notification_failure_count"], 1)
        self.assertTrue(summary["manual_resend_available"])
        self.assertIn("Enquiry Notification Status", ui_response.text)
        self.assertIn("Resend notification", ui_response.text)
        self.assertIn("/glirn/enquiry-notifications/", ui_response.text)

    def test_public_lead_validation_rejects_invalid_email_missing_type_and_long_message(self):
        payload = {
            "name": "Validation Client",
            "organisation": "Validation Legal LLP",
            "email": "not-an-email",
            "country": "England",
            "legal_sector": "Corporate Law",
            "hiring_need": "Senior hire",
            "seniority_level": "Partner",
            "message": "x" * 2001,
            "consent": True,
        }

        with patch("app.PUBLIC_LEADS", []), patch("app.PUBLIC_LEAD_SUBMISSION_TIMES", {}):
            response = self.client.post("/glirn/public-leads/intake", json=payload)

        self.assertEqual(response.status_code, 422)
        self.assertNotIn("Traceback", response.text)

    def test_public_lead_validation_rejects_script_injection(self):
        payload = {
            "name": "<script>alert(1)</script>",
            "organisation": "Safe Legal LLP",
            "email": "safe@example.com",
            "country": "England",
            "inquiry_type": "Intelligence Review",
            "legal_sector": "Corporate Law",
            "hiring_need": "Senior hiring review",
            "seniority_level": "Partner",
            "message": "Confidential review request.",
            "consent": True,
        }

        leads = []
        with patch("app.PUBLIC_LEADS", leads), patch("app.PUBLIC_LEAD_SUBMISSION_TIMES", {}):
            response = self.client.post("/glirn/public-leads/intake", json=payload)

        self.assertEqual(response.status_code, 422)
        self.assertEqual(leads, [])
        self.assertNotIn("Traceback", response.text)

    def test_public_lead_rate_limit_is_local_and_deterministic(self):
        payload = {
            "name": "Rate Test",
            "organisation": "Rate Legal LLP",
            "email": "rate@example.com",
            "country": "England",
            "inquiry_type": "General Enquiry",
            "legal_sector": "Corporate Law",
            "hiring_need": "General information",
            "seniority_level": "Other",
            "message": "Please provide information.",
            "consent": True,
        }

        with patch("app.PUBLIC_LEADS", []), \
                patch("app.PUBLIC_LEAD_SUBMISSION_TIMES", {}), \
                patch("app.record_approval_event"):
            responses = [
                self.client.post("/glirn/public-leads/intake", json=payload)
                for _ in range(app.PUBLIC_LEAD_RATE_LIMIT + 1)
            ]

        self.assertTrue(all(response.status_code == 200 for response in responses[:-1]))
        self.assertEqual(responses[-1].status_code, 429)
        self.assertNotIn("Traceback", responses[-1].text)

    def test_security_headers_are_added_to_public_and_internal_responses(self):
        for path in ["/public/index.html", "/health", "/glirn/dashboard"]:
            response = self.client.get(path)
            self.assertEqual(response.headers["x-content-type-options"], "nosniff")
            self.assertEqual(response.headers["x-frame-options"], "DENY")
            self.assertEqual(response.headers["referrer-policy"], "strict-origin-when-cross-origin")

    def test_export_helpers_escape_text_and_contain_traversal_paths(self):
        self.assertEqual(app.safe_export_text("<script>alert(1)</script>"), "&lt;script&gt;alert(1)&lt;/script&gt;")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = app.approved_local_export_path(tmpdir, "../../outside<script>")
            self.assertEqual(os.path.commonpath([os.path.abspath(tmpdir), path]), os.path.abspath(tmpdir))
            self.assertNotIn("..", os.path.basename(path))
            self.assertTrue(path.endswith(".txt"))

    def test_configured_secret_is_not_rendered_in_public_dashboard_or_ui(self):
        secret = "mission-95-secret-value"
        with patch.dict("os.environ", {"ARBITRAGE_API_KEY": secret}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]):
            public_response = self.client.get("/public/index.html")
            dashboard_response = self.client.get("/glirn/dashboard", headers={"X-API-Key": secret})
            ui_response = self.client.get(f"/ui?key={secret}")

        self.assertNotIn(secret, public_response.text)
        self.assertNotIn(secret, dashboard_response.text)
        self.assertNotIn(secret, ui_response.text)

    def test_glirn_public_lead_intake_endpoint_records_and_scores_lead(self):
        payload = {
            "name": "Alex Client",
            "organisation": "Boutique AI Law LLP",
            "email": "alex@example.com",
            "country": "England",
            "inquiry_type": "Law Firm",
            "legal_sector": "Technology & AI Law",
            "practice_area": "Technology & AI Law",
            "jurisdiction": "England & Wales",
            "hiring_need": "Partner search",
            "seniority_level": "Partner",
            "timescale": "1-3 months",
            "message": "We may need senior hiring support.",
            "consent": True,
        }

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.PUBLIC_LEADS", []), \
                patch("app.record_approval_event") as record_event:
            response = self.client.post("/glirn/public-leads/intake", json=payload)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "public_lead_recorded")
        self.assertEqual(data["prospect_type"], "Boutique Technology & AI Law Firms")
        self.assertEqual(data["lead_type"], "executive_search_lead")
        self.assertEqual(data["lead_route"], "executive_search_review")
        self.assertEqual(data["lead_qualification_status"], "qualified_for_gareth_review")
        self.assertGreaterEqual(data["lead_revenue_potential"], 90)
        self.assertEqual(data["estimated_revenue_opportunity"], 25000)
        self.assertEqual(data["gareth_approval_status"], "awaiting_review")
        self.assertEqual(data["revenue_approval_package"]["suggested_glirn_service"], "Executive Search")
        self.assertFalse(data["revenue_approval_package"]["automatic_client_contact_enabled"])
        self.assertFalse(data["revenue_approval_package"]["money_movement_enabled"])
        self.assertEqual(
            data["notification"]["recipient_address"],
            "legalintelligencerecruitment@outlook.com",
        )
        self.assertEqual(data["notification_delivery_status"], "delivery_failed")
        self.assertTrue(data["notification_informational_only"])
        self.assertFalse(data["automatic_email_enabled"])
        self.assertFalse(data["automatic_acceptance_enabled"])
        self.assertFalse(data["automatic_payment_enabled"])
        self.assertFalse(data["automatic_brief_generation_enabled"])
        self.assertFalse(data["automatic_candidate_outreach_enabled"])
        self.assertFalse(data["automatic_search_activity_enabled"])
        self.assertFalse(data["automatic_delivery_enabled"])
        self.assertFalse(data["client_contact_enabled"])
        self.assertFalse(data["candidate_contact_enabled"])
        record_event.assert_called_once()
        event = record_event.call_args.args[0]
        self.assertEqual(event["event_type"], "glirn_public_lead_intake")
        self.assertEqual(event["provider"], "glirn_website_lead_intake_engine")
        self.assertFalse(event["external_integrations_enabled"])

    def test_glirn_public_lead_action_audit_logging_works(self):
        public_leads = [
            {
                "lead_id": "public-lead-001",
                "name": "Alex Client",
                "organisation": "Boutique AI Law LLP",
                "email": "alex@example.com",
                "country": "England",
                "inquiry_type": "Law Firm",
                "legal_sector": "Technology & AI Law",
                "practice_area": "Technology & AI Law",
                "jurisdiction": "England & Wales",
                "hiring_need": "Partner search",
                "seniority_level": "Partner",
                "timescale": "1-3 months",
                "message": "We may need senior hiring support.",
                "consent": True,
            }
        ]

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.PUBLIC_LEADS", public_leads), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.record_approval_event") as record_event:
            response = self.client.post(
                "/glirn/public-leads/actions",
                json={
                    "lead_id": "public-lead-001",
                    "action_type": "convert-to-approval-package",
                    "reason": "Convert qualified public lead for Gareth review.",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "public_lead_action_recorded")
        self.assertEqual(data["lead_approval_package_status"], "converted_to_final_approval_package")
        self.assertFalse(data["automatic_email_enabled"])
        self.assertFalse(data["client_contact_enabled"])
        self.assertFalse(data["invoice_issuing_enabled"])
        record_event.assert_called_once()
        event = record_event.call_args.args[0]
        self.assertEqual(event["event_type"], "glirn_public_lead_action")
        self.assertEqual(event["provider"], "glirn_website_lead_intake_engine")
        self.assertEqual(event["decision"], "PUBLIC_LEAD_CONVERTED_TO_APPROVAL_PACKAGE")
        self.assertFalse(event["payment_collection_enabled"])

    def test_glirn_final_approval_action_updates_local_status_only(self):
        public_leads = [
            {
                "lead_id": "public-lead-001",
                "name": "Alex Client",
                "organisation": "Boutique AI Law LLP",
                "email": "alex@example.com",
                "country": "England",
                "inquiry_type": "Law Firm",
                "legal_sector": "Technology & AI Law",
                "practice_area": "Technology & AI Law",
                "jurisdiction": "England & Wales",
                "hiring_need": "Partner search",
                "seniority_level": "Partner",
                "timescale": "1-3 months",
                "message": "We may need senior hiring support.",
                "consent": True,
            }
        ]

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.PUBLIC_LEADS", public_leads), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.record_approval_event") as record_event:
            response = self.client.post(
                "/glirn/final-approval/actions",
                json={
                    "action_type": "approve",
                    "reason": "Approved for manual Gareth-controlled follow-up.",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "final_approval_action_recorded")
        self.assertEqual(data["final_approval_status"], "approved_by_gareth")
        self.assertFalse(data["client_contact_enabled"])
        self.assertFalse(data["invoice_sending_enabled"])
        self.assertFalse(data["payment_request_enabled"])
        self.assertFalse(data["money_movement_enabled"])
        self.assertTrue(data["local_state_only"])
        record_event.assert_called_once()
        event = record_event.call_args.args[0]
        self.assertEqual(event["event_type"], "glirn_final_approval_action")
        self.assertEqual(event["provider"], "glirn_final_approval_command_centre")
        self.assertEqual(event["decision"], "FINAL_APPROVAL_APPROVED_BY_GARETH")
        self.assertFalse(event["client_contact_enabled"])
        self.assertFalse(event["invoice_sending_enabled"])
        self.assertFalse(event["payment_request_enabled"])
        self.assertFalse(event["money_movement_enabled"])

    def test_glirn_client_contact_action_refuses_without_gareth_approval(self):
        public_leads = [
            {
                "lead_id": "public-lead-001",
                "name": "Alex Client",
                "organisation": "Boutique AI Law LLP",
                "email": "alex@example.com",
                "country": "England",
                "inquiry_type": "Law Firm",
                "legal_sector": "Technology & AI Law",
                "practice_area": "Technology & AI Law",
                "jurisdiction": "England & Wales",
                "hiring_need": "Partner search",
                "seniority_level": "Partner",
                "timescale": "1-3 months",
                "message": "We may need senior hiring support.",
                "consent": True,
            }
        ]

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.PUBLIC_LEADS", public_leads), \
                patch("app.FINAL_APPROVAL_LOCAL_STATUS", {}), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.record_approval_event"):
            response = self.client.post(
                "/glirn/client-contact/actions",
                json={
                    "action_type": "mark_approved_contact_ready",
                    "reason": "Try contact before final approval.",
                },
            )

        self.assertEqual(response.status_code, 403)

    def test_glirn_client_contact_action_logs_local_only_after_gareth_approval(self):
        public_leads = [
            {
                "lead_id": "public-lead-001",
                "name": "Alex Client",
                "organisation": "Boutique AI Law LLP",
                "email": "alex@example.com",
                "country": "England",
                "inquiry_type": "Law Firm",
                "legal_sector": "Technology & AI Law",
                "practice_area": "Technology & AI Law",
                "jurisdiction": "England & Wales",
                "hiring_need": "Partner search",
                "seniority_level": "Partner",
                "timescale": "1-3 months",
                "message": "We may need senior hiring support.",
                "consent": True,
            }
        ]
        final_approval_id = "glirn-final-approval-glirn-revenue-approval-public-lead-001"

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.PUBLIC_LEADS", public_leads), \
                patch("app.FINAL_APPROVAL_LOCAL_STATUS", {final_approval_id: "approved_by_gareth"}), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.record_approval_event") as record_event:
            response = self.client.post(
                "/glirn/client-contact/actions",
                json={
                    "final_approval_id": final_approval_id,
                    "action_type": "mark_approved_contact_ready",
                    "reason": "Mark approved contact ready locally.",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "client_contact_action_recorded")
        self.assertEqual(data["contact_status"], "contact_logged_local_only")
        self.assertEqual(data["lead_email"], "alex@example.com")
        self.assertFalse(data["real_email_sent"])
        self.assertFalse(data["client_contact_executed"])
        self.assertFalse(data["gmail_smtp_connected"])
        self.assertFalse(data["external_integrations_enabled"])
        self.assertTrue(data["local_log_only"])
        record_event.assert_called_once()
        event = record_event.call_args.args[0]
        self.assertEqual(event["event_type"], "glirn_client_contact_action")
        self.assertEqual(event["provider"], "glirn_approved_client_contact_engine")
        self.assertEqual(event["decision"], "CLIENT_CONTACT_LOGGED_LOCAL_ONLY")
        self.assertFalse(event["real_email_sent"])
        self.assertFalse(event["client_contact_executed"])
        self.assertFalse(event["external_integrations_enabled"])

    def test_glirn_email_draft_export_refuses_without_gareth_approval(self):
        public_leads = [
            {
                "lead_id": "public-lead-001",
                "name": "Alex Client",
                "organisation": "Boutique AI Law LLP",
                "email": "alex@example.com",
                "country": "England",
                "inquiry_type": "Law Firm",
                "legal_sector": "Technology & AI Law",
                "practice_area": "Technology & AI Law",
                "jurisdiction": "England & Wales",
                "hiring_need": "Partner search",
                "seniority_level": "Partner",
                "timescale": "1-3 months",
                "message": "We may need senior hiring support.",
                "consent": True,
            }
        ]

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.PUBLIC_LEADS", public_leads), \
                patch("app.FINAL_APPROVAL_LOCAL_STATUS", {}), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.record_approval_event"):
            response = self.client.post(
                "/glirn/email-draft-export/actions",
                json={
                    "action_type": "export_approved_email_draft",
                    "reason": "Try export before final approval.",
                },
            )

        self.assertEqual(response.status_code, 403)

    def test_glirn_email_draft_export_creates_local_file_after_gareth_approval(self):
        public_leads = [
            {
                "lead_id": "public-lead-001",
                "name": "Alex Client",
                "organisation": "Boutique AI Law LLP",
                "email": "alex@example.com",
                "country": "England",
                "inquiry_type": "Law Firm",
                "legal_sector": "Technology & AI Law",
                "practice_area": "Technology & AI Law",
                "jurisdiction": "England & Wales",
                "hiring_need": "Partner search",
                "seniority_level": "Partner",
                "timescale": "1-3 months",
                "message": "We may need senior hiring support.",
                "consent": True,
            }
        ]
        final_approval_id = "glirn-final-approval-glirn-revenue-approval-public-lead-001"

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict("os.environ", {}, clear=True), \
                    patch("app.PUBLIC_LEADS", public_leads), \
                    patch("app.FINAL_APPROVAL_LOCAL_STATUS", {final_approval_id: "approved_by_gareth"}), \
                    patch("app.GLIRN_EMAIL_DRAFTS_DIR", tmpdir), \
                    patch("app.list_pending_approvals", return_value=[]), \
                    patch("app.record_approval_event") as record_event:
                response = self.client.post(
                    "/glirn/email-draft-export/actions",
                    json={
                        "final_approval_id": final_approval_id,
                        "action_type": "export_approved_email_draft",
                        "reason": "Export approved email draft locally.",
                    },
                )

            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "email_draft_export_action_recorded")
            self.assertEqual(data["export_status"], "exported_local_only")
            self.assertEqual(data["to_email"], "alex@example.com")
            self.assertFalse(data["email_sent"])
            self.assertFalse(data["gmail_smtp_connected"])
            self.assertFalse(data["external_integrations_enabled"])
            self.assertTrue(data["local_file_only"])
            self.assertTrue(os.path.exists(data["local_file_path"]))
            with open(data["local_file_path"], "r", encoding="utf-8") as draft_file:
                content = draft_file.read()
            self.assertIn("To: alex@example.com", content)
            self.assertIn("Subject: GLIRN enquiry follow-up - Executive Search", content)
            self.assertIn("Fee proposal summary:", content)
            self.assertIn("No email has been sent. Gareth must manually review and send.", content)

        record_event.assert_called_once()
        event = record_event.call_args.args[0]
        self.assertEqual(event["event_type"], "glirn_email_draft_export_action")
        self.assertEqual(event["provider"], "glirn_email_draft_export_engine")
        self.assertEqual(event["decision"], "EMAIL_DRAFT_EXPORTED_LOCAL_ONLY")
        self.assertFalse(event["email_sent"])
        self.assertFalse(event["external_integrations_enabled"])

    def test_glirn_invoice_draft_export_refuses_without_gareth_approval(self):
        public_leads = [
            {
                "lead_id": "public-lead-001",
                "name": "Alex Client",
                "organisation": "Boutique AI Law LLP",
                "email": "alex@example.com",
                "country": "England",
                "inquiry_type": "Law Firm",
                "legal_sector": "Technology & AI Law",
                "practice_area": "Technology & AI Law",
                "jurisdiction": "England & Wales",
                "hiring_need": "Partner search",
                "seniority_level": "Partner",
                "timescale": "1-3 months",
                "message": "We may need senior hiring support.",
                "consent": True,
            }
        ]

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.PUBLIC_LEADS", public_leads), \
                patch("app.FINAL_APPROVAL_LOCAL_STATUS", {}), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.record_approval_event"):
            response = self.client.post(
                "/glirn/invoice-draft-export/actions",
                json={
                    "action_type": "export_approved_invoice_draft",
                    "reason": "Try invoice export before final approval.",
                },
            )

        self.assertEqual(response.status_code, 403)

    def test_glirn_invoice_draft_export_creates_local_file_after_gareth_approval(self):
        public_leads = [
            {
                "lead_id": "public-lead-001",
                "name": "Alex Client",
                "organisation": "Boutique AI Law LLP",
                "email": "alex@example.com",
                "country": "England",
                "inquiry_type": "Law Firm",
                "legal_sector": "Technology & AI Law",
                "practice_area": "Technology & AI Law",
                "jurisdiction": "England & Wales",
                "hiring_need": "Partner search",
                "seniority_level": "Partner",
                "timescale": "1-3 months",
                "message": "We may need senior hiring support.",
                "consent": True,
            }
        ]
        final_approval_id = "glirn-final-approval-glirn-revenue-approval-public-lead-001"

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict("os.environ", {}, clear=True), \
                    patch("app.PUBLIC_LEADS", public_leads), \
                    patch("app.FINAL_APPROVAL_LOCAL_STATUS", {final_approval_id: "approved_by_gareth"}), \
                    patch("app.GLIRN_INVOICE_DRAFTS_DIR", tmpdir), \
                    patch("app.list_pending_approvals", return_value=[]), \
                    patch("app.record_approval_event") as record_event:
                response = self.client.post(
                    "/glirn/invoice-draft-export/actions",
                    json={
                        "final_approval_id": final_approval_id,
                        "action_type": "export_approved_invoice_draft",
                        "reason": "Export approved invoice draft locally.",
                    },
                )

            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "invoice_draft_export_action_recorded")
            self.assertEqual(data["invoice_status"], "exported_local_only")
            self.assertEqual(data["client_email"], "alex@example.com")
            self.assertEqual(data["suggested_glirn_service"], "Executive Search")
            self.assertFalse(data["invoice_sent"])
            self.assertFalse(data["payment_request_sent"])
            self.assertFalse(data["money_movement_enabled"])
            self.assertFalse(data["external_integrations_enabled"])
            self.assertTrue(data["local_file_only"])
            self.assertTrue(os.path.exists(data["local_file_path"]))
            with open(data["local_file_path"], "r", encoding="utf-8") as draft_file:
                content = draft_file.read()
            self.assertIn("Client name: Boutique AI Law LLP", content)
            self.assertIn("Client email: alex@example.com", content)
            self.assertIn("Suggested GLIRN service: Executive Search", content)
            self.assertIn("Estimated fee: 25000", content)
            self.assertIn("No invoice or payment request has been sent. Gareth must manually review and send.", content)

        record_event.assert_called_once()
        event = record_event.call_args.args[0]
        self.assertEqual(event["event_type"], "glirn_invoice_draft_export_action")
        self.assertEqual(event["provider"], "glirn_invoice_draft_export_engine")
        self.assertEqual(event["decision"], "INVOICE_DRAFT_EXPORTED_LOCAL_ONLY")
        self.assertFalse(event["invoice_sent"])
        self.assertFalse(event["payment_request_sent"])
        self.assertFalse(event["money_movement_enabled"])
        self.assertFalse(event["external_integrations_enabled"])

    def test_glirn_deal_pack_export_refuses_without_gareth_approval(self):
        public_leads = [
            {
                "lead_id": "public-lead-001",
                "name": "Alex Client",
                "organisation": "Boutique AI Law LLP",
                "email": "alex@example.com",
                "country": "England",
                "inquiry_type": "Law Firm",
                "legal_sector": "Technology & AI Law",
                "practice_area": "Technology & AI Law",
                "jurisdiction": "England & Wales",
                "hiring_need": "Partner search",
                "seniority_level": "Partner",
                "timescale": "1-3 months",
                "message": "We may need senior hiring support.",
                "consent": True,
            }
        ]

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.PUBLIC_LEADS", public_leads), \
                patch("app.FINAL_APPROVAL_LOCAL_STATUS", {}), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.record_approval_event"):
            response = self.client.post(
                "/glirn/deal-pack-export/actions",
                json={
                    "action_type": "export_approved_deal_pack",
                    "reason": "Try deal pack export before final approval.",
                },
            )

        self.assertEqual(response.status_code, 403)

    def test_glirn_deal_pack_export_creates_local_file_after_gareth_approval(self):
        public_leads = [
            {
                "lead_id": "public-lead-001",
                "name": "Alex Client",
                "organisation": "Boutique AI Law LLP",
                "email": "alex@example.com",
                "country": "England",
                "inquiry_type": "Law Firm",
                "legal_sector": "Technology & AI Law",
                "practice_area": "Technology & AI Law",
                "jurisdiction": "England & Wales",
                "hiring_need": "Partner search",
                "seniority_level": "Partner",
                "timescale": "1-3 months",
                "message": "We may need senior hiring support.",
                "consent": True,
            }
        ]
        final_approval_id = "glirn-final-approval-glirn-revenue-approval-public-lead-001"

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict("os.environ", {}, clear=True), \
                    patch("app.PUBLIC_LEADS", public_leads), \
                    patch("app.FINAL_APPROVAL_LOCAL_STATUS", {final_approval_id: "approved_by_gareth"}), \
                    patch("app.GLIRN_DEAL_PACKS_DIR", tmpdir), \
                    patch("app.list_pending_approvals", return_value=[]), \
                    patch("app.record_approval_event") as record_event:
                response = self.client.post(
                    "/glirn/deal-pack-export/actions",
                    json={
                        "final_approval_id": final_approval_id,
                        "action_type": "export_approved_deal_pack",
                        "reason": "Export approved deal pack locally.",
                    },
                )

            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "deal_pack_export_action_recorded")
            self.assertEqual(data["deal_pack_status"], "exported_local_only")
            self.assertEqual(data["client_email"], "alex@example.com")
            self.assertEqual(data["suggested_glirn_service"], "Executive Search")
            self.assertFalse(data["client_contact_executed"])
            self.assertFalse(data["invoice_sent"])
            self.assertFalse(data["payment_request_sent"])
            self.assertFalse(data["money_movement_enabled"])
            self.assertFalse(data["external_integrations_enabled"])
            self.assertTrue(data["local_file_only"])
            self.assertTrue(os.path.exists(data["local_file_path"]))
            with open(data["local_file_path"], "r", encoding="utf-8") as deal_pack_file:
                content = deal_pack_file.read()
            self.assertIn("GLIRN Complete Deal Pack", content)
            self.assertIn("Client name: Boutique AI Law LLP", content)
            self.assertIn("Client email: alex@example.com", content)
            self.assertIn("Approved client response draft:", content)
            self.assertIn("Fee proposal pack:", content)
            self.assertIn("Invoice draft summary:", content)
            self.assertIn("No client contact, invoice, payment request, or money movement has occurred. Gareth must manually review and act.", content)

        record_event.assert_called_once()
        event = record_event.call_args.args[0]
        self.assertEqual(event["event_type"], "glirn_deal_pack_export_action")
        self.assertEqual(event["provider"], "glirn_deal_pack_export_engine")
        self.assertEqual(event["decision"], "DEAL_PACK_EXPORTED_LOCAL_ONLY")
        self.assertFalse(event["client_contact_executed"])
        self.assertFalse(event["invoice_sent"])
        self.assertFalse(event["payment_request_sent"])
        self.assertFalse(event["money_movement_enabled"])
        self.assertFalse(event["external_integrations_enabled"])

    def test_glirn_revenue_ledger_endpoint_returns_local_records(self):
        public_leads = [
            {
                "lead_id": "public-lead-001",
                "name": "Alex Client",
                "organisation": "Boutique AI Law LLP",
                "email": "alex@example.com",
                "country": "England",
                "inquiry_type": "Law Firm",
                "legal_sector": "Technology & AI Law",
                "practice_area": "Technology & AI Law",
                "jurisdiction": "England & Wales",
                "hiring_need": "Partner search",
                "seniority_level": "Partner",
                "timescale": "1-3 months",
                "message": "We may need senior hiring support.",
                "consent": True,
            }
        ]

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.PUBLIC_LEADS", public_leads), \
                patch("app.FINAL_APPROVAL_LOCAL_STATUS", {}), \
                patch("app.REVENUE_LEDGER_LOCAL_STAGE", {}), \
                patch("app.list_pending_approvals", return_value=[]):
            response = self.client.get("/glirn/revenue-ledger")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "GLIRN Revenue Ledger Active")
        self.assertEqual(data["revenue_ledger_records"][0]["actual_revenue_received"], 0)
        self.assertTrue(data["revenue_ledger_records"][0]["manual_payment_confirmation_required"])
        self.assertFalse(data["payment_collection_enabled"])
        self.assertFalse(data["money_movement_enabled"])
        self.assertFalse(data["external_integrations_enabled"])

    def test_glirn_revenue_ledger_action_updates_stage_locally_only(self):
        public_leads = [
            {
                "lead_id": "public-lead-001",
                "name": "Alex Client",
                "organisation": "Boutique AI Law LLP",
                "email": "alex@example.com",
                "country": "England",
                "inquiry_type": "Law Firm",
                "legal_sector": "Technology & AI Law",
                "practice_area": "Technology & AI Law",
                "jurisdiction": "England & Wales",
                "hiring_need": "Partner search",
                "seniority_level": "Partner",
                "timescale": "1-3 months",
                "message": "We may need senior hiring support.",
                "consent": True,
            }
        ]

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.PUBLIC_LEADS", public_leads), \
                patch("app.FINAL_APPROVAL_LOCAL_STATUS", {}), \
                patch("app.REVENUE_LEDGER_LOCAL_STAGE", {}), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.record_approval_event") as record_event:
            response = self.client.post(
                "/glirn/revenue-ledger/actions",
                json={
                    "action_type": "mark_payment_pending_manual",
                    "reason": "Manual payment now pending.",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "revenue_ledger_action_recorded")
        self.assertEqual(data["revenue_stage"], "payment_pending_manual")
        self.assertEqual(data["actual_revenue_received"], 0)
        self.assertTrue(data["manual_payment_confirmation_required"])
        self.assertFalse(data["payment_collection_enabled"])
        self.assertFalse(data["money_movement_enabled"])
        self.assertFalse(data["invoice_sending_enabled"])
        self.assertFalse(data["client_contact_enabled"])
        self.assertFalse(data["external_integrations_enabled"])
        record_event.assert_called_once()
        event = record_event.call_args.args[0]
        self.assertEqual(event["event_type"], "glirn_revenue_ledger_action")
        self.assertEqual(event["provider"], "glirn_revenue_ledger_engine")
        self.assertFalse(event["payment_collection_enabled"])
        self.assertFalse(event["money_movement_enabled"])
        self.assertFalse(event["external_integrations_enabled"])

    def test_protected_mode_requires_header_for_agent_safety(self):
        payload = {
            "action_type": "send_email",
            "recipient_type": "internal",
            "body": "Internal draft only."
        }

        with patch.dict("os.environ", {"ARBITRAGE_API_KEY": "unit-key"}, clear=True):
            missing = self.client.post("/agent-safety/evaluate", json=payload)

        self.assertEqual(missing.status_code, 401)

        with patch.dict("os.environ", {"ARBITRAGE_API_KEY": "unit-key"}, clear=True), \
                patch("app.record_approval_event"):
            allowed = self.client.post(
                "/agent-safety/evaluate",
                json=payload,
                headers={"X-API-Key": "unit-key"}
            )

        self.assertEqual(allowed.status_code, 200)


class Mission109ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app.app)
        self.sections = {
            name: f"Evidence-led approved content for {name}."
            for name in glirn_multi_agent_review.CLIENT_CONTENT_SECTIONS
        }
        self.brief = {
            "review_id": "brief-109",
            "sections": {},
            "human_review_framework": {"red_flags": {}},
            "candidate_personal_data_included": False,
            "candidate_personal_data_blocked": False,
        }
        self.human_review = {
            "human_review_id": "human-review-brief-109",
            "brief_id": "brief-109",
            "reviewer": "Gareth",
            "reviewed_at": "2026-06-11T09:00:00+00:00",
            "outcome": "approved_for_manual_delivery",
            "approval_rationale": "Mission 106 controls completed.",
            "approved_for_manual_delivery": True,
            "delivery_status": "ready_for_manual_delivery",
            "validation_errors": [],
            "incomplete_checks": [],
            "unresolved_red_flags": [],
        }
        self.glirn_data = {
            "intelligence_review_engine": {"generated_reviews": [self.brief]}
        }

    def cleared_review(self):
        return {
            "review_id": "multi-agent-review-brief-109",
            "brief_id": "brief-109",
            "review_complete": True,
            "content_fingerprint": glirn_multi_agent_review.brief_content_fingerprint(self.sections),
            "escalation_required": False,
            "unresolved_escalations": [],
            "review_status": "cleared_for_gareth_approval",
            "consensus_summary": {
                "overall_confidence_score": 89.0,
                "suggested_next_actions": ["Submit the cleared review to Gareth for final approval."],
            },
        }

    def cleared_confidence_assessment(self):
        return {
            "confidence_assessment_id": "confidence-assessment-brief-109",
            "brief_id": "brief-109",
            "mission_109_review_id": "multi-agent-review-brief-109",
            "content_fingerprint": glirn_multi_agent_review.brief_content_fingerprint(self.sections),
            "assessment_complete": True,
            "confidence_score": 88,
            "confidence_category": "High Confidence",
            "evidence_sufficiency_rating": 90,
            "reviewer_agreement": {"level": "High"},
            "outstanding_limitations": ["Market observations are time-sensitive."],
            "evidence_transparency": {
                "key_evidence_considered": ["Reviewed market observations."],
                "supporting_assumptions": ["Market conditions remain comparable."],
                "known_limitations": ["Market observations are time-sensitive."],
                "areas_requiring_caution": ["Validate observations before action."],
                "information_gaps_identified": ["No material gaps identified."],
                "alternative_interpretations": ["Alternative demand conditions were considered."],
            },
            "escalation_required": False,
            "unresolved_escalations": [],
            "assessment_status": "cleared_for_gareth_approval",
        }

    def test_multi_agent_review_executes_all_roles_and_persists_audit_safe_record(self):
        stored = []

        def store_record(category, record_id, payload):
            stored.append((category, record_id, dict(payload)))

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.get_glirn_dashboard_data", return_value=self.glirn_data), \
                patch.object(app, "PERSISTED_HUMAN_REVIEWS", [self.human_review]), \
                patch.object(app, "PERSISTED_MULTI_AGENT_REVIEWS", []), \
                patch("app.upsert_record", side_effect=store_record), \
                patch("app.list_records", return_value=[]), \
                patch("app.persist_safe_action") as persist_action, \
                patch("app.record_approval_event") as approval_event:
            response = self.client.post(
                "/glirn/intelligence-briefs/multi-agent-review",
                json={"brief_id": "brief-109", "sections": self.sections},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        review = data["multi_agent_review"]
        self.assertEqual(
            tuple(item["reviewer_role"] for item in review["reviewer_outputs"]),
            glirn_multi_agent_review.REVIEWER_ROLES,
        )
        self.assertEqual(stored[0][0], "multi_agent_review_record")
        self.assertFalse(review["sensitive_candidate_information_duplicated"])
        self.assertTrue(data["gareth_final_approval_required"])
        self.assertFalse(data["delivery_allowed"])
        self.assertFalse(data["automatic_acceptance_enabled"])
        self.assertFalse(data["automatic_payment_enabled"])
        self.assertFalse(data["automatic_candidate_outreach_enabled"])
        self.assertFalse(data["automatic_delivery_enabled"])
        self.assertFalse(data["external_commitments_enabled"])
        persist_action.assert_called_once()
        approval_event.assert_called_once()

    def test_unresolved_escalation_blocks_gareth_final_approval(self):
        review = self.cleared_review()
        review["escalation_required"] = True
        review["unresolved_escalations"] = ["evidence_insufficiency"]

        with patch.dict("os.environ", {}, clear=True), \
                patch.object(app, "PERSISTED_MULTI_AGENT_REVIEWS", [review]):
            response = self.client.post(
                "/glirn/intelligence-briefs/brief-109/final-approval",
                json={"action_type": "approve", "reason": "Final review completed."},
            )

        self.assertEqual(response.status_code, 403)
        self.assertIn("unresolved Mission 109 escalations", response.json()["detail"])

    def test_gareth_final_approval_is_required_and_remains_non_delivery_action(self):
        with patch.dict("os.environ", {}, clear=True), \
                patch.object(app, "PERSISTED_MULTI_AGENT_REVIEWS", [self.cleared_review()]), \
                patch.object(app, "PERSISTED_CONFIDENCE_ASSESSMENTS", [self.cleared_confidence_assessment()]), \
                patch.dict(app.FINAL_APPROVAL_LOCAL_STATUS, {}, clear=True), \
                patch("app.set_state"), \
                patch("app.persist_safe_action") as persist_action, \
                patch("app.record_approval_event") as approval_event:
            response = self.client.post(
                "/glirn/intelligence-briefs/brief-109/final-approval",
                json={"action_type": "approve", "reason": "Gareth approves the reviewed brief."},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["final_approval_status"], "approved_by_gareth")
        self.assertFalse(data["automatic_delivery_enabled"])
        self.assertFalse(data["external_commitments_enabled"])
        persist_action.assert_called_once()
        approval_event.assert_called_once()

    def test_delivery_package_rejects_missing_review_and_changed_reviewed_content(self):
        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.get_glirn_dashboard_data", return_value=self.glirn_data), \
                patch.object(app, "PERSISTED_HUMAN_REVIEWS", [self.human_review]), \
                patch.object(app, "PERSISTED_MULTI_AGENT_REVIEWS", []):
            missing = self.client.post(
                "/glirn/intelligence-briefs/package",
                json={"brief_id": "brief-109", "sections": self.sections},
            )
        self.assertEqual(missing.status_code, 403)
        self.assertIn("Mission 109 multi-agent review is required", missing.json()["detail"])

        changed_sections = dict(self.sections)
        changed_sections["Market Observations"] = "Changed after review."
        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.get_glirn_dashboard_data", return_value=self.glirn_data), \
                patch.object(app, "PERSISTED_HUMAN_REVIEWS", [self.human_review]), \
                patch.object(app, "PERSISTED_MULTI_AGENT_REVIEWS", [self.cleared_review()]):
            changed = self.client.post(
                "/glirn/intelligence-briefs/package",
                json={"brief_id": "brief-109", "sections": changed_sections},
            )
        self.assertEqual(changed.status_code, 409)
        self.assertIn("content changed after Mission 109 review", changed.json()["detail"])

    def test_command_centre_surfaces_multi_agent_status_and_escalations(self):
        review = self.cleared_review()
        review["escalation_required"] = True
        review["review_status"] = "escalated_delivery_blocked"

        with patch.object(app, "PERSISTED_MULTI_AGENT_REVIEWS", [review]), \
                patch.object(app, "PERSISTED_HUMAN_REVIEWS", []), \
                patch.object(app, "PERSISTED_CONFIDENCE_ASSESSMENTS", []), \
                patch.object(app, "PERSISTED_ENQUIRY_NOTIFICATIONS", []):
            dashboard_data = app.glirn_dashboard()
            rendered = app.render_gareth_command_centre(dashboard_data)

        summary = dashboard_data["gareth_command_centre"]["multi_agent_review_summary"]
        self.assertEqual(summary["review_count"], 1)
        self.assertEqual(summary["escalated_review_count"], 1)
        self.assertIn("Multi-Agent Intelligence Review", rendered)
        self.assertIn("escalated_delivery_blocked", rendered)
        self.assertIn("Delivery remains manual", rendered)


class Mission110ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app.app)
        self.sections = {
            name: f"Evidence-led approved content for {name}."
            for name in glirn_multi_agent_review.CLIENT_CONTENT_SECTIONS
        }
        self.brief = {
            "review_id": "brief-110",
            "sections": {},
            "human_review_framework": {"red_flags": {}},
            "candidate_personal_data_included": False,
            "candidate_personal_data_blocked": False,
        }
        self.human_review = {
            "human_review_id": "human-review-brief-110",
            "brief_id": "brief-110",
            "reviewer": "Gareth",
            "reviewed_at": "2026-06-12T09:00:00+00:00",
            "outcome": "approved_for_manual_delivery",
            "approval_rationale": "Mission 106 controls completed.",
            "approved_for_manual_delivery": True,
            "delivery_status": "ready_for_manual_delivery",
            "validation_errors": [],
            "incomplete_checks": [],
            "unresolved_red_flags": [],
        }
        self.multi_agent_review = {
            "review_id": "multi-agent-review-brief-110",
            "brief_id": "brief-110",
            "mission_106_review_id": "human-review-brief-110",
            "review_complete": True,
            "content_fingerprint": glirn_multi_agent_review.brief_content_fingerprint(self.sections),
            "reviewer_outputs": [
                {
                    "reviewer_role": role,
                    "confidence_score": 90,
                    "findings": ["Reviewed."],
                    "concerns": ["Alternative interpretation."] if "Devil" in role else [],
                    "recommendations": ["Validate material observations."],
                }
                for role in glirn_multi_agent_review.REVIEWER_ROLES
            ],
            "escalation_required": False,
            "unresolved_escalations": [],
            "review_status": "cleared_for_gareth_approval",
        }
        self.glirn_data = {"intelligence_review_engine": {"generated_reviews": [self.brief]}}

    def assessment_payload(self, rating=90, material_limitations=False):
        return {
            "brief_id": "brief-110",
            "sections": self.sections,
            "evidence_sufficiency": rating,
            "evidence_quality": rating,
            "data_recency": rating,
            "market_information_completeness": rating,
            "key_evidence_considered": ["Market source contact source@example.com."],
            "supporting_assumptions": ["Demand remains stable."],
            "known_limitations": ["Market information is time-sensitive."],
            "areas_requiring_caution": ["Validate before acting."],
            "information_gaps_identified": ["No material gap identified."],
            "material_limitations_undermine_conclusions": material_limitations,
        }

    def cleared_assessment(self):
        return glirn_confidence_engine.assess_confidence(
            self.brief,
            self.human_review,
            self.multi_agent_review,
            90,
            90,
            90,
            90,
        )

    def test_confidence_assessment_requires_mission_106_and_mission_109(self):
        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.get_glirn_dashboard_data", return_value=self.glirn_data), \
                patch.object(app, "PERSISTED_HUMAN_REVIEWS", []), \
                patch.object(app, "PERSISTED_MULTI_AGENT_REVIEWS", []):
            no_human = self.client.post(
                "/glirn/intelligence-briefs/confidence-assessment",
                json=self.assessment_payload(),
            )
        self.assertEqual(no_human.status_code, 403)
        self.assertIn("Mission 106", no_human.json()["detail"])

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.get_glirn_dashboard_data", return_value=self.glirn_data), \
                patch.object(app, "PERSISTED_HUMAN_REVIEWS", [self.human_review]), \
                patch.object(app, "PERSISTED_MULTI_AGENT_REVIEWS", []):
            no_multi = self.client.post(
                "/glirn/intelligence-briefs/confidence-assessment",
                json=self.assessment_payload(),
            )
        self.assertEqual(no_multi.status_code, 403)
        self.assertIn("Mission 109", no_multi.json()["detail"])

    def test_confidence_assessment_persists_transparency_but_audit_avoids_source_content(self):
        stored = []

        def store_record(category, record_id, payload):
            stored.append((category, record_id, dict(payload)))

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.get_glirn_dashboard_data", return_value=self.glirn_data), \
                patch.object(app, "PERSISTED_HUMAN_REVIEWS", [self.human_review]), \
                patch.object(app, "PERSISTED_MULTI_AGENT_REVIEWS", [self.multi_agent_review]), \
                patch.object(app, "PERSISTED_CONFIDENCE_ASSESSMENTS", []), \
                patch("app.upsert_record", side_effect=store_record), \
                patch("app.list_records", return_value=[]), \
                patch("app.persist_safe_action") as persist_action, \
                patch("app.record_approval_event") as approval_event:
            response = self.client.post(
                "/glirn/intelligence-briefs/confidence-assessment",
                json=self.assessment_payload(),
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        assessment = data["confidence_assessment"]
        self.assertEqual(stored[0][0], "confidence_assessment_record")
        self.assertIn("[redacted email]", assessment["evidence_transparency"]["key_evidence_considered"][0])
        self.assertIn("alternative_interpretations", assessment["evidence_transparency"])
        audit_payload = persist_action.call_args.kwargs
        self.assertNotIn("key_evidence_considered", audit_payload)
        self.assertNotIn("known_limitations", audit_payload)
        self.assertFalse(audit_payload["confidential_source_material_logged"])
        self.assertFalse(audit_payload["candidate_sensitive_information_logged"])
        self.assertFalse(data["gareth_override_allowed"])
        self.assertFalse(data["automatic_acceptance_enabled"])
        self.assertFalse(data["automatic_payment_enabled"])
        self.assertFalse(data["automatic_candidate_outreach_enabled"])
        self.assertFalse(data["automatic_search_activity_enabled"])
        self.assertFalse(data["automatic_delivery_enabled"])
        self.assertFalse(data["external_commitments_enabled"])
        approval_event.assert_called_once()

    def test_low_confidence_blocks_gareth_approval_without_override(self):
        low = glirn_confidence_engine.assess_confidence(
            self.brief,
            self.human_review,
            self.multi_agent_review,
            20,
            20,
            20,
            20,
        )
        with patch.dict("os.environ", {}, clear=True), \
                patch.object(app, "PERSISTED_MULTI_AGENT_REVIEWS", [self.multi_agent_review]), \
                patch.object(app, "PERSISTED_CONFIDENCE_ASSESSMENTS", [low]):
            response = self.client.post(
                "/glirn/intelligence-briefs/brief-110/final-approval",
                json={"action_type": "approve", "reason": "Attempt direct Gareth override."},
            )

        self.assertEqual(response.status_code, 403)
        self.assertIn("remediation and Mission 109 and Mission 110 reassessment", response.json()["detail"])
        self.assertFalse(low["gareth_override_allowed"])

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.get_glirn_dashboard_data", return_value=self.glirn_data), \
                patch.object(app, "PERSISTED_HUMAN_REVIEWS", [self.human_review]), \
                patch.object(app, "PERSISTED_MULTI_AGENT_REVIEWS", [self.multi_agent_review]), \
                patch.object(app, "PERSISTED_CONFIDENCE_ASSESSMENTS", [low]), \
                patch.dict(app.FINAL_APPROVAL_LOCAL_STATUS, {
                    "intelligence-brief-final-approval-brief-110": "approved_by_gareth",
                }, clear=True):
            package = self.client.post(
                "/glirn/intelligence-briefs/package",
                json={"brief_id": "brief-110", "sections": self.sections},
            )

        self.assertEqual(package.status_code, 403)
        self.assertIn("remediation and Mission 109 and Mission 110 reassessment", package.json()["detail"])

    def test_final_approval_and_package_cannot_bypass_mission_110(self):
        with patch.dict("os.environ", {}, clear=True), \
                patch.object(app, "PERSISTED_MULTI_AGENT_REVIEWS", [self.multi_agent_review]), \
                patch.object(app, "PERSISTED_CONFIDENCE_ASSESSMENTS", []):
            approval = self.client.post(
                "/glirn/intelligence-briefs/brief-110/final-approval",
                json={"action_type": "approve", "reason": "Attempt without Mission 110."},
            )
        self.assertEqual(approval.status_code, 403)
        self.assertIn("Mission 110 confidence assessment is required", approval.json()["detail"])

        with patch.dict("os.environ", {}, clear=True), \
                patch("app.list_pending_approvals", return_value=[]), \
                patch("app.get_glirn_dashboard_data", return_value=self.glirn_data), \
                patch.object(app, "PERSISTED_HUMAN_REVIEWS", [self.human_review]), \
                patch.object(app, "PERSISTED_MULTI_AGENT_REVIEWS", [self.multi_agent_review]), \
                patch.object(app, "PERSISTED_CONFIDENCE_ASSESSMENTS", []):
            package = self.client.post(
                "/glirn/intelligence-briefs/package",
                json={"brief_id": "brief-110", "sections": self.sections},
            )
        self.assertEqual(package.status_code, 403)
        self.assertIn("Mission 110 confidence assessment is required", package.json()["detail"])

    def test_mission_110_must_be_repeated_after_mission_109_content_changes(self):
        assessment = self.cleared_assessment()
        reassessed_review = dict(self.multi_agent_review)
        reassessed_review["content_fingerprint"] = "new-mission-109-fingerprint"
        with patch.dict("os.environ", {}, clear=True), \
                patch.object(app, "PERSISTED_MULTI_AGENT_REVIEWS", [reassessed_review]), \
                patch.object(app, "PERSISTED_CONFIDENCE_ASSESSMENTS", [assessment]):
            response = self.client.post(
                "/glirn/intelligence-briefs/brief-110/final-approval",
                json={"action_type": "approve", "reason": "Attempt using stale Mission 110 assessment."},
            )

        self.assertEqual(response.status_code, 409)
        self.assertIn("Mission 110 assessment must be repeated", response.json()["detail"])

    def test_command_centre_displays_confidence_evidence_and_escalation_status(self):
        assessment = self.cleared_assessment()
        with patch.object(app, "PERSISTED_CONFIDENCE_ASSESSMENTS", [assessment]), \
                patch.object(app, "PERSISTED_MULTI_AGENT_REVIEWS", [self.multi_agent_review]), \
                patch.object(app, "PERSISTED_HUMAN_REVIEWS", [self.human_review]), \
                patch.object(app, "PERSISTED_ENQUIRY_NOTIFICATIONS", []):
            dashboard_data = app.glirn_dashboard()
            rendered = app.render_gareth_command_centre(dashboard_data)

        summary = dashboard_data["gareth_command_centre"]["confidence_assessment_summary"]
        self.assertEqual(summary["latest_confidence_category"], assessment["confidence_category"])
        self.assertIn("Confidence &amp; Evidence Transparency", rendered)
        self.assertIn("Evidence sufficiency", rendered)
        self.assertIn("Reviewer agreement", rendered)
        self.assertIn("Outstanding limitations", rendered)
        self.assertIn("Gareth cannot override unresolved escalation", rendered)


if __name__ == "__main__":
    unittest.main()
