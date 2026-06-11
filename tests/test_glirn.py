import unittest

from glirn_human_review import (
    DECLINE_CRITERIA,
    HUMAN_REVIEW_CHECKLIST,
    RED_FLAG_RULES,
    build_initial_human_review_framework,
    evaluate_human_review,
)

from glirn import (
    LEGAL_SECTORS,
    Candidate,
    ClientFirm,
    CandidateConsentRecord,
    ClientFeeAgreement,
    ComplianceAlert,
    HumanApprovalDecision,
    Jurisdiction,
    LegalPracticeArea,
    RecruitmentOpportunity,
    build_candidate_consent_management_engine,
    build_candidate_specific_report,
    build_approval_to_action_workflow,
    build_client_terms_drafting_engine,
    build_glirn_approval_centre,
    build_glirn_compliance_core,
    build_executive_search_engine,
    build_commercial_revenue_engine,
    build_client_acquisition_engine,
    build_candidate_discovery_engine,
    build_client_deliverable_factory,
    build_deployment_readiness,
    build_daily_executive_briefing,
    build_executive_autopilot,
    build_intelligence_review_engine,
    build_operations_command_centre,
    build_integration_governance,
    build_matching_engine,
    build_manual_delivery_control_engine,
    build_legal_intelligence_network,
    build_legal_opportunity_radar,
    build_live_data_readiness,
    build_first_client_readiness_gate,
    build_invoice_drafting_engine,
    build_launch_readiness_command_centre,
    build_launch_compliance_validation_engine,
    build_first_prospect_selection_engine,
    build_first_client_dry_run,
    build_autonomous_internal_operations_orchestrator,
    build_website_lead_intake_engine,
    build_revenue_approval_engine,
    build_client_response_draft_engine,
    build_fee_proposal_pack_engine,
    build_final_approval_command_centre,
    apply_final_approval_action,
    build_approved_client_contact_engine,
    build_client_contact_readiness_object,
    apply_client_contact_action,
    build_email_draft_export_engine,
    build_enquiry_notification_summary,
    build_email_draft_export_object,
    apply_email_draft_export_action,
    build_invoice_draft_export_engine,
    build_invoice_draft_export_object,
    apply_invoice_draft_export_action,
    build_deal_pack_export_engine,
    build_deal_pack_export_object,
    apply_deal_pack_export_action,
    build_revenue_ledger_engine,
    build_gareth_command_centre,
    apply_revenue_ledger_action,
    build_revenue_command_centre,
    calculate_glirn_score,
    calculate_high_fee_priority_score,
    calculate_client_opportunity_score,
    calculate_hiring_likelihood_score,
    calculate_intelligence_report_fee,
    calculate_candidate_priority_score,
    calculate_match_revenue_score,
    calculate_placement_probability_score,
    calculate_practice_area_compatibility,
    calculate_source_readiness,
    calculate_integration_governance,
    calculate_placement_fee,
    calculate_retained_search_commercial_fee,
    classify_candidate_seniority,
    create_compliance_alerts,
    evaluate_compliance_readiness,
    estimate_executive_placement_fee,
    estimate_client_fee_potential,
    estimate_candidate_placement_value,
    estimate_fee_value,
    estimate_retained_search_fee,
    flag_deletion_request,
    generate_market_intelligence,
    generate_salary_intelligence,
    get_integration_registry,
    get_live_data_source_registry,
    build_candidate_consent_ledger,
    build_client_terms_status,
    build_data_retention_status,
    get_glirn_dashboard_data,
    get_stub_recruitment_opportunities,
    is_premium_executive_opportunity,
    rank_hot_practice_areas,
    rank_jurisdiction_demand,
)


class GlirnFoundationTests(unittest.TestCase):
    def test_legal_sectors_include_required_foundation_areas(self):
        self.assertIn("Corporate & M&A", LEGAL_SECTORS)
        self.assertIn("Technology & AI Law", LEGAL_SECTORS)
        self.assertIn("Partner & Executive Search", LEGAL_SECTORS)
        self.assertEqual(len(LEGAL_SECTORS), 12)

    def test_foundation_models_are_serializable_and_capital_safe(self):
        practice_area = LegalPracticeArea(code="corporate_and_ma", name="Corporate & M&A")
        jurisdiction = Jurisdiction(code="GB-ENG", name="England & Wales")
        candidate = Candidate(
            candidate_id="candidate-1",
            full_name="Candidate A",
            practice_area=practice_area.name,
            jurisdiction=jurisdiction.code,
            seniority="Partner",
            quality_score=90,
        )
        client = ClientFirm(
            firm_id="client-1",
            name="Client Firm A",
            jurisdiction=jurisdiction.code,
            practice_areas=[practice_area.name],
            client_quality=88,
        )
        consent = CandidateConsentRecord(
            consent_id="consent-1",
            candidate_id=candidate.candidate_id,
            consent_status="human_approval_required",
        )
        agreement = ClientFeeAgreement(
            agreement_id="fee-1",
            firm_id=client.firm_id,
            fee_percentage=25,
            payment_terms="payable on placement",
        )
        decision = HumanApprovalDecision(
            decision_id="decision-1",
            subject_id="opp-1",
            subject_type="recruitment_opportunity",
            decision="REQUEST_APPROVAL",
        )

        for item in [practice_area, jurisdiction, candidate, client, consent, agreement, decision]:
            data = item.to_dict()
            self.assertIn("capital_execution", data)
            self.assertFalse(data["capital_execution"])

    def test_recruitment_opportunity_contains_scoring_fields(self):
        candidate = Candidate(
            candidate_id="candidate-1",
            full_name="Candidate A",
            practice_area="Private Equity",
            jurisdiction="GB-ENG",
            seniority="Partner",
            quality_score=91,
        )
        client = ClientFirm(
            firm_id="client-1",
            name="Client Firm A",
            jurisdiction="GB-ENG",
            practice_areas=["Private Equity"],
            client_quality=88,
        )

        opportunity = RecruitmentOpportunity(
            opportunity_id="glirn-test-001",
            title="Private Equity Partner Search",
            candidate=candidate,
            client_firm=client,
            practice_area="Private Equity",
            jurisdiction="England & Wales",
            expected_fee_value=85000,
            placement_probability=0.42,
            client_quality=88,
            candidate_quality=91,
            compliance_readiness=76,
            urgency_score=82,
            time_to_revenue=45,
        ).to_dict()

        for key in [
            "expected_fee_value",
            "placement_probability",
            "client_quality",
            "candidate_quality",
            "compliance_readiness",
            "urgency_score",
            "time_to_revenue",
            "overall_glirn_score",
        ]:
            self.assertIn(key, opportunity)

        self.assertGreater(opportunity["overall_glirn_score"], 0)
        self.assertEqual(opportunity["status"], "pending_human_approval")
        self.assertFalse(opportunity["capital_execution"])

    def test_dashboard_data_returns_stub_opportunities_and_summary(self):
        data = get_glirn_dashboard_data()

        self.assertEqual(len(data["legal_sectors"]), 12)
        self.assertGreaterEqual(len(data["opportunities"]), 1)
        self.assertEqual(
            data["summary"]["pending_human_approval"],
            len(data["opportunities"]),
        )
        self.assertGreater(data["summary"]["total_expected_fee_value"], 0)
        self.assertFalse(data["capital_execution"])

    def test_glirn_score_rewards_higher_quality_inputs(self):
        weak_score = calculate_glirn_score(
            expected_fee_value=10000,
            placement_probability=0.2,
            client_quality=40,
            candidate_quality=40,
            compliance_readiness=40,
            urgency_score=40,
            time_to_revenue=80,
        )
        strong_score = calculate_glirn_score(
            expected_fee_value=90000,
            placement_probability=0.7,
            client_quality=90,
            candidate_quality=90,
            compliance_readiness=90,
            urgency_score=90,
            time_to_revenue=20,
        )

        self.assertGreater(strong_score, weak_score)

    def test_fee_estimator_returns_expected_fee_value(self):
        estimate = estimate_fee_value(
            annual_compensation=200000,
            fee_percentage=25,
            placement_probability=0.5,
        )

        self.assertEqual(estimate["gross_fee_value"], 50000)
        self.assertEqual(estimate["expected_fee_value"], 25000)
        self.assertFalse(estimate["capital_execution"])

    def test_legal_opportunity_radar_ranks_highest_priority_first(self):
        opportunities = get_stub_recruitment_opportunities()
        radar = build_legal_opportunity_radar(opportunities)

        ranked = radar["opportunities_ranked"]
        self.assertGreaterEqual(len(ranked), 1)
        self.assertEqual(ranked[0]["priority_rank"], 1)
        self.assertGreaterEqual(
            ranked[0]["radar_priority_score"],
            ranked[-1]["radar_priority_score"],
        )
        self.assertIsNotNone(radar["top_opportunity"])
        self.assertIsNotNone(radar["dave_recommends_first"])
        self.assertTrue(radar["approval_required_for_outbound_action"])
        self.assertFalse(radar["capital_execution"])
        self.assertFalse(radar["autonomous_execution"])

    def test_radar_exposes_highest_value_candidate_and_client_views(self):
        radar = build_legal_opportunity_radar(get_stub_recruitment_opportunities())

        candidate = radar["highest_value_candidate"]
        client_firm = radar["highest_value_client_firm"]

        self.assertEqual(candidate["full_name"], "Candidate E")
        self.assertEqual(client_firm["name"], "Client Firm E")
        self.assertTrue(candidate["approval_required"])
        self.assertTrue(client_firm["approval_required"])
        self.assertFalse(candidate["capital_execution"])
        self.assertFalse(client_firm["capital_execution"])

    def test_dashboard_includes_legal_opportunity_radar(self):
        data = get_glirn_dashboard_data()

        self.assertIn("legal_opportunity_radar", data)
        self.assertEqual(data["legal_opportunity_radar"]["engine"], "legal_opportunity_radar")
        self.assertIn("top_radar_opportunity", data["summary"])
        self.assertIn("highest_value_candidate", data["summary"])
        self.assertIn("highest_value_client_firm", data["summary"])

    def test_approval_centre_locks_all_outbound_actions(self):
        approval_centre = build_glirn_approval_centre(
            get_stub_recruitment_opportunities(),
            pending_approvals=[],
        )

        self.assertEqual(approval_centre["status"], "Waiting for Gareth Approval")
        self.assertGreaterEqual(approval_centre["pending_count"], 1)
        self.assertTrue(approval_centre["locks"]["outbound_action_locked"])
        self.assertTrue(approval_centre["locks"]["candidate_introduction_locked"])
        self.assertTrue(approval_centre["locks"]["client_engagement_locked"])
        self.assertTrue(approval_centre["locks"]["fee_negotiation_locked"])
        self.assertFalse(approval_centre["capital_execution"])
        self.assertFalse(approval_centre["autonomous_execution"])

    def test_approval_centre_queue_items_require_reason_and_offer_actions(self):
        approval_centre = build_glirn_approval_centre(
            get_stub_recruitment_opportunities(),
            pending_approvals=[
                {
                    "approval_id": "approval-glirn-001",
                    "route_result": {
                        "source": "glirn",
                        "opportunity_id": "glirn-pe-partner-london-001",
                    },
                }
            ],
        )

        first_item = approval_centre["queue"][0]
        self.assertEqual(first_item["approval_id"], "approval-glirn-001")
        self.assertEqual(first_item["allowed_actions"], ["approve", "reject", "monitor"])
        self.assertTrue(first_item["approval_reason_required"])
        self.assertTrue(first_item["outbound_action_locked"])
        self.assertTrue(first_item["candidate_introduction_locked"])
        self.assertTrue(first_item["client_engagement_locked"])
        self.assertTrue(first_item["fee_negotiation_locked"])

    def test_dashboard_includes_approval_centre(self):
        data = get_glirn_dashboard_data()

        self.assertIn("approval_centre", data)
        self.assertEqual(data["approval_centre"]["status"], "Waiting for Gareth Approval")
        self.assertEqual(data["summary"]["dashboard_status"], "Waiting for Gareth Approval")

    def test_consent_active_allows_readiness(self):
        readiness = evaluate_compliance_readiness(
            {"consent_status": "active"},
            {"terms_status": "recorded"},
            {"deletion_requested": False},
        )

        self.assertTrue(readiness["candidate_introduction_allowed"])
        self.assertTrue(readiness["client_candidate_details_allowed"])
        self.assertTrue(readiness["outbound_action_allowed"])
        self.assertEqual(readiness["compliance_readiness_score"], 100)
        self.assertFalse(readiness["capital_execution"])

    def test_missing_consent_blocks_introduction(self):
        readiness = evaluate_compliance_readiness(
            {"consent_status": "missing"},
            {"terms_status": "recorded"},
            {"deletion_requested": False},
        )

        self.assertFalse(readiness["candidate_introduction_allowed"])
        self.assertTrue(readiness["outbound_action_blocked"])
        self.assertLess(readiness["compliance_readiness_score"], 100)

    def test_expired_consent_blocks_outbound_action(self):
        readiness = evaluate_compliance_readiness(
            {"consent_status": "expired"},
            {"terms_status": "recorded"},
            {"deletion_requested": False},
        )

        self.assertFalse(readiness["outbound_action_allowed"])
        self.assertTrue(readiness["outbound_action_blocked"])

    def test_deletion_request_flags_record(self):
        deletion_request = flag_deletion_request(
            "candidate-stub-001",
            "Candidate requested deletion.",
        )

        self.assertTrue(deletion_request["record_flagged"])
        self.assertTrue(deletion_request["outbound_action_blocked"])
        self.assertEqual(deletion_request["status"], "deletion_review_required")
        self.assertFalse(deletion_request["capital_execution"])

    def test_compliance_alert_is_created_for_missing_consent(self):
        consent_ledger = [
            {"candidate_id": "candidate-stub-002", "consent_status": "missing"},
        ]
        client_terms = [
            {"firm_id": "client-stub-002", "terms_status": "recorded"},
        ]
        retention = [
            {"candidate_id": "candidate-stub-002", "deletion_requested": False},
        ]

        alerts = create_compliance_alerts(consent_ledger, client_terms, retention)

        self.assertEqual(alerts[0]["alert_type"], "missing_consent")
        self.assertTrue(alerts[0]["outbound_action_blocked"])
        self.assertFalse(alerts[0]["capital_execution"])

    def test_compliance_core_contains_ledgers_alerts_and_restricted_actions(self):
        compliance_core = build_glirn_compliance_core(get_stub_recruitment_opportunities())

        self.assertEqual(compliance_core["status"], "Compliance-First Controls Active")
        self.assertGreaterEqual(len(compliance_core["candidate_consent_ledger"]), 1)
        self.assertGreaterEqual(len(compliance_core["client_consent_terms_status"]), 1)
        self.assertGreaterEqual(len(compliance_core["jurisdiction_compliance_profile"]), 1)
        self.assertGreaterEqual(len(compliance_core["data_retention_status"]), 1)
        self.assertGreaterEqual(len(compliance_core["missing_consent_alerts"]), 1)
        self.assertGreaterEqual(len(compliance_core["consent_expiry_alerts"]), 1)
        self.assertGreaterEqual(len(compliance_core["restricted_outbound_actions"]), 1)
        self.assertLess(compliance_core["compliance_readiness_score"], 100)
        self.assertFalse(compliance_core["capital_execution"])

    def test_deletion_request_adds_retention_alert(self):
        opportunities = get_stub_recruitment_opportunities()
        deletion_request = flag_deletion_request("candidate-stub-001", "Remove record.")
        compliance_core = build_glirn_compliance_core(
            opportunities,
            deletion_requests=[deletion_request],
        )

        deletion_alerts = [
            alert for alert in compliance_core["compliance_alerts"]
            if alert["alert_type"] == "deletion_request"
        ]
        self.assertEqual(len(deletion_alerts), 1)
        self.assertTrue(deletion_alerts[0]["outbound_action_blocked"])

    def test_dashboard_includes_compliance_core(self):
        data = get_glirn_dashboard_data()

        self.assertIn("compliance_core", data)
        self.assertEqual(data["compliance_core"]["status"], "Compliance-First Controls Active")
        self.assertEqual(data["summary"]["compliance_status"], "Compliance-First Controls Active")

    def test_partner_opportunity_marked_premium(self):
        opportunity = next(
            item for item in get_stub_recruitment_opportunities()
            if item["opportunity_id"] == "glirn-pe-partner-london-001"
        )

        seniority = classify_candidate_seniority(opportunity)

        self.assertEqual(seniority, "Partner")
        self.assertTrue(is_premium_executive_opportunity(seniority))

    def test_gc_opportunity_marked_premium(self):
        opportunity = next(
            item for item in get_stub_recruitment_opportunities()
            if item["opportunity_id"] == "glirn-gc-newyork-001"
        )

        seniority = classify_candidate_seniority(opportunity)

        self.assertEqual(seniority, "General Counsel")
        self.assertTrue(is_premium_executive_opportunity(seniority))

    def test_clo_opportunity_marked_premium(self):
        opportunity = next(
            item for item in get_stub_recruitment_opportunities()
            if item["opportunity_id"] == "glirn-clo-london-001"
        )

        seniority = classify_candidate_seniority(opportunity)

        self.assertEqual(seniority, "Chief Legal Officer")
        self.assertTrue(is_premium_executive_opportunity(seniority))

    def test_retained_fee_calculated(self):
        placement = estimate_executive_placement_fee(annual_compensation=300000)
        retainer = estimate_retained_search_fee(placement["estimated_placement_fee"])

        self.assertEqual(placement["estimated_placement_fee"], 90000)
        self.assertEqual(retainer["estimated_retainer_fee"], 29997)
        self.assertTrue(retainer["gareth_approval_required"])
        self.assertFalse(retainer["capital_execution"])

    def test_high_fee_priority_score_calculated(self):
        opportunity = next(
            item for item in get_stub_recruitment_opportunities()
            if item["opportunity_id"] == "glirn-clo-london-001"
        )
        readiness = {
            "compliance_readiness_score": 100,
        }

        score = calculate_high_fee_priority_score(opportunity, readiness)

        self.assertGreater(score, 70)

    def test_missing_consent_blocks_executive_action(self):
        executive_search = build_executive_search_engine(get_stub_recruitment_opportunities())
        missing_consent_item = next(
            item for item in executive_search["top_executive_opportunities"]
            if item["opportunity_id"] == "glirn-ai-law-counsel-uae-001"
        )

        self.assertFalse(missing_consent_item["executive_candidate_outreach_allowed"])
        self.assertTrue(missing_consent_item["outbound_action_blocked"])
        self.assertIn("missing_or_inactive_candidate_consent", missing_consent_item["blocked_reasons"])

    def test_missing_client_terms_blocks_client_action(self):
        executive_search = build_executive_search_engine(get_stub_recruitment_opportunities())
        missing_terms_item = next(
            item for item in executive_search["top_executive_opportunities"]
            if item["opportunity_id"] == "glirn-gc-newyork-001"
        )

        self.assertFalse(missing_terms_item["client_engagement_allowed"])
        self.assertTrue(missing_terms_item["outbound_action_blocked"])
        self.assertIn("missing_client_terms_status", missing_terms_item["blocked_reasons"])

    def test_dashboard_includes_executive_search(self):
        data = get_glirn_dashboard_data()

        self.assertIn("executive_search", data)
        self.assertEqual(data["executive_search"]["status"], "Executive Search Engine Active")
        self.assertIn("executive_search_status", data["summary"])
        self.assertIsNotNone(data["executive_search"]["dave_recommends_first"])

    def test_salary_intelligence_generated(self):
        salary_signals = generate_salary_intelligence(get_stub_recruitment_opportunities())

        self.assertGreaterEqual(len(salary_signals), 1)
        self.assertIn("estimated_salary", salary_signals[0])
        self.assertFalse(salary_signals[0]["candidate_personal_data_included"])
        self.assertFalse(salary_signals[0]["capital_execution"])

    def test_market_intelligence_generated(self):
        market = generate_market_intelligence(get_stub_recruitment_opportunities())

        self.assertGreater(market["total_expected_fee_value"], 0)
        self.assertIn("client_intelligence_hook", market)
        self.assertFalse(market["candidate_personal_data_included"])

    def test_hot_practice_areas_ranked(self):
        ranked = rank_hot_practice_areas(get_stub_recruitment_opportunities())

        self.assertGreaterEqual(len(ranked), 1)
        self.assertGreaterEqual(ranked[0]["growth_score"], ranked[-1]["growth_score"])

    def test_jurisdiction_demand_ranked(self):
        ranked = rank_jurisdiction_demand(get_stub_recruitment_opportunities())

        self.assertGreaterEqual(len(ranked), 1)
        self.assertGreaterEqual(ranked[0]["demand_score"], ranked[-1]["demand_score"])

    def test_candidate_personal_data_blocked_without_consent(self):
        opportunity = next(
            item for item in get_stub_recruitment_opportunities()
            if item["opportunity_id"] == "glirn-ai-law-counsel-uae-001"
        )
        report = build_candidate_specific_report(
            opportunity,
            {"consent_status": "missing"},
        )

        self.assertTrue(report["blocked"])
        self.assertFalse(report["candidate_personal_data_included"])
        self.assertEqual(report["blocked_reason"], "candidate_personal_data_blocked_without_active_consent")

    def test_legal_intelligence_network_requires_gareth_approval_for_reports(self):
        network = build_legal_intelligence_network(get_stub_recruitment_opportunities())

        self.assertEqual(network["status"], "Legal Intelligence Network Active")
        self.assertTrue(network["client_facing_report_generation_requires_gareth_approval"])
        self.assertTrue(network["candidate_specific_reports_require_active_consent"])
        self.assertFalse(network["candidate_personal_data_exposed_without_consent"])
        self.assertIsNotNone(network["dave_recommends_first"])

    def test_dashboard_includes_intelligence_network(self):
        data = get_glirn_dashboard_data()

        self.assertIn("intelligence_network", data)
        self.assertIn("intelligence_report", data)
        self.assertEqual(data["intelligence_network"]["status"], "Legal Intelligence Network Active")
        self.assertIn("intelligence_network_status", data["summary"])

    def test_placement_fee_calculated(self):
        fee = calculate_placement_fee(annual_compensation=200000, fee_percentage=25)

        self.assertEqual(fee["fee_type"], "contingency placement fee")
        self.assertEqual(fee["calculated_fee"], 50000)
        self.assertFalse(fee["capital_execution"])

    def test_retained_commercial_fee_calculated(self):
        fee = calculate_retained_search_commercial_fee(
            annual_compensation=300000,
            fee_percentage=30,
        )

        self.assertEqual(fee["fee_type"], "retained search fee")
        self.assertEqual(fee["estimated_placement_fee"], 90000)
        self.assertEqual(fee["estimated_retainer_fee"], 29997)
        self.assertTrue(fee["gareth_approval_required"])

    def test_intelligence_report_fee_calculated(self):
        fee = calculate_intelligence_report_fee("market_intelligence")
        subscription = calculate_intelligence_report_fee("subscription_intelligence")

        self.assertEqual(fee["fee_type"], "intelligence report fee")
        self.assertEqual(fee["calculated_fee"], 750)
        self.assertEqual(subscription["fee_type"], "subscription intelligence fee")
        self.assertTrue(fee["gareth_approval_required"])

    def test_invoice_readiness_blocked_without_client_terms(self):
        engine = build_commercial_revenue_engine(get_stub_recruitment_opportunities())
        missing_terms_item = next(
            item for item in engine["commercial_pipeline"]
            if item["opportunity_id"] == "glirn-gc-newyork-001"
        )

        self.assertEqual(missing_terms_item["client_terms_readiness"], "missing")
        self.assertEqual(missing_terms_item["invoice_readiness"], "blocked")
        self.assertIn("missing_client_terms", missing_terms_item["blocked_reasons"])

    def test_fee_proposal_requires_approval(self):
        engine = build_commercial_revenue_engine(get_stub_recruitment_opportunities())
        first_item = engine["commercial_pipeline"][0]

        self.assertTrue(first_item["fee_proposal_requires_gareth_approval"])
        self.assertTrue(first_item["human_approval_required"])
        self.assertTrue(engine["awaiting_gareth_approval"])

    def test_dashboard_includes_commercial_revenue_engine(self):
        data = get_glirn_dashboard_data()

        self.assertIn("commercial_revenue_engine", data)
        self.assertIn("commercial_pipeline", data)
        self.assertEqual(data["commercial_revenue_engine"]["status"], "Commercial Revenue Controls Active")
        self.assertIn("commercial_revenue_status", data["summary"])
        self.assertIsNotNone(data["commercial_revenue_engine"]["highest_fee_opportunity"])

    def test_client_opportunity_score_calculated(self):
        opportunity = get_stub_recruitment_opportunities()[0]
        score = calculate_client_opportunity_score(opportunity, "ready")

        self.assertGreater(score, 0)
        self.assertLessEqual(score, 100)

    def test_hiring_likelihood_score_calculated(self):
        opportunity = get_stub_recruitment_opportunities()[0]
        score = calculate_hiring_likelihood_score(opportunity)

        self.assertGreater(score, 0)
        self.assertLessEqual(score, 100)

    def test_fee_potential_estimated(self):
        opportunity = get_stub_recruitment_opportunities()[0]
        potential = estimate_client_fee_potential(opportunity)

        self.assertEqual(potential, opportunity["expected_fee_value"])

    def test_client_acquisition_outreach_blocked_without_approval(self):
        engine = build_client_acquisition_engine(get_stub_recruitment_opportunities())
        first_client = engine["top_target_clients"][0]

        self.assertTrue(first_client["outreach_approval_required"])
        self.assertTrue(first_client["outreach_blocked_without_approval"])
        self.assertTrue(engine["awaiting_gareth_approval"])

    def test_client_acquisition_candidate_data_blocked_without_consent(self):
        engine = build_client_acquisition_engine(get_stub_recruitment_opportunities())
        missing_consent_client = next(
            item for item in engine["target_client_profiles"]
            if item["opportunity_id"] == "glirn-ai-law-counsel-uae-001"
        )

        self.assertFalse(missing_consent_client["candidate_consent_active"])
        self.assertFalse(missing_consent_client["candidate_details_allowed"])

    def test_dashboard_includes_client_acquisition_engine(self):
        data = get_glirn_dashboard_data()

        self.assertIn("client_acquisition_engine", data)
        self.assertEqual(data["client_acquisition_engine"]["status"], "Client Acquisition Controls Active")
        self.assertIn("client_acquisition_status", data["summary"])
        self.assertIsNotNone(data["client_acquisition_engine"]["highest_fee_potential_client"])

    def test_candidate_priority_score_calculated(self):
        opportunity = get_stub_recruitment_opportunities()[0]
        score = calculate_candidate_priority_score(opportunity, consent_status="active")

        self.assertGreater(score, 0)
        self.assertLessEqual(score, 100)

    def test_executive_candidate_flagged(self):
        engine = build_candidate_discovery_engine(get_stub_recruitment_opportunities())
        candidate = next(
            item for item in engine["candidate_profiles"]
            if item["candidate_id"] == "candidate-stub-005"
        )

        self.assertTrue(candidate["executive_candidate"])

    def test_estimated_candidate_placement_value_calculated(self):
        opportunity = get_stub_recruitment_opportunities()[0]
        value = estimate_candidate_placement_value(opportunity)

        self.assertEqual(value, opportunity["expected_fee_value"])

    def test_consent_readiness_blocks_activation(self):
        engine = build_candidate_discovery_engine(get_stub_recruitment_opportunities())
        candidate = next(
            item for item in engine["candidate_profiles"]
            if item["candidate_id"] == "candidate-stub-002"
        )

        self.assertEqual(candidate["consent_readiness_status"], "missing")
        self.assertFalse(candidate["profile_activation_allowed"])
        self.assertFalse(candidate["candidate_details_allowed"])

    def test_candidate_discovery_outreach_blocked_without_approval(self):
        engine = build_candidate_discovery_engine(get_stub_recruitment_opportunities())
        candidate = engine["top_candidate_opportunities"][0]

        self.assertTrue(candidate["outreach_approval_required"])
        self.assertTrue(candidate["outreach_blocked_without_approval"])
        self.assertTrue(engine["awaiting_gareth_approval"])

    def test_dashboard_includes_candidate_discovery_engine(self):
        data = get_glirn_dashboard_data()

        self.assertIn("candidate_discovery_engine", data)
        self.assertEqual(data["candidate_discovery_engine"]["status"], "Candidate Discovery Controls Active")
        self.assertIn("candidate_discovery_status", data["summary"])
        self.assertIsNotNone(data["candidate_discovery_engine"]["highest_estimated_placement_value"])

    def test_candidate_to_client_match_created(self):
        data = get_glirn_dashboard_data()
        matching = build_matching_engine(
            data["candidate_discovery_engine"],
            data["client_acquisition_engine"],
        )

        self.assertGreaterEqual(len(matching["ranked_placement_matches"]), 1)
        self.assertIn("match_id", matching["ranked_placement_matches"][0])

    def test_matching_compatibility_scores_calculated(self):
        data = get_glirn_dashboard_data()
        matching = build_matching_engine(
            data["candidate_discovery_engine"],
            data["client_acquisition_engine"],
        )
        match = matching["ranked_placement_matches"][0]

        self.assertGreater(match["practice_area_compatibility_score"], 0)
        self.assertGreater(match["jurisdiction_compatibility_score"], 0)
        self.assertGreater(match["seniority_compatibility_score"], 0)
        self.assertGreater(match["salary_fee_compatibility_score"], 0)
        self.assertGreater(match["relocation_compatibility_score"], 0)

    def test_match_blocked_without_candidate_consent(self):
        data = get_glirn_dashboard_data()
        matching = build_matching_engine(
            data["candidate_discovery_engine"],
            data["client_acquisition_engine"],
        )
        blocked = next(
            item for item in matching["ranked_placement_matches"]
            if item["candidate_consent_status"] != "active"
        )

        self.assertFalse(blocked["match_active_allowed"])
        self.assertIn("missing_or_inactive_candidate_consent", blocked["blocked_reasons"])

    def test_match_blocked_without_client_terms(self):
        data = get_glirn_dashboard_data()
        matching = build_matching_engine(
            data["candidate_discovery_engine"],
            data["client_acquisition_engine"],
        )
        blocked = next(
            item for item in matching["ranked_placement_matches"]
            if item["client_terms_status"] != "recorded"
        )

        self.assertFalse(blocked["client_facing_allowed"])
        self.assertIn("missing_client_terms", blocked["blocked_reasons"])

    def test_placement_action_requires_approval(self):
        data = get_glirn_dashboard_data()
        matching = data["matching_engine"]
        match = matching["ranked_placement_matches"][0]

        self.assertTrue(match["placement_action_requires_gareth_approval"])
        self.assertTrue(match["human_approval_required"])
        self.assertTrue(matching["awaiting_gareth_approval"])

    def test_match_revenue_score_calculated(self):
        data = get_glirn_dashboard_data()
        match = data["matching_engine"]["ranked_placement_matches"][0]

        self.assertGreater(match["match_revenue_score"], 0)
        self.assertGreater(match["placement_probability_score"], 0)

    def test_dashboard_includes_matching_engine(self):
        data = get_glirn_dashboard_data()

        self.assertIn("matching_engine", data)
        self.assertEqual(data["matching_engine"]["status"], "Matching & Placement Controls Active")
        self.assertIn("matching_engine_status", data["summary"])
        self.assertIsNotNone(data["matching_engine"]["highest_match_revenue_score"])

    def test_executive_autopilot_aggregation_works(self):
        data = get_glirn_dashboard_data()
        autopilot = data["executive_autopilot"]

        self.assertEqual(autopilot["engine"], "executive_autopilot")
        self.assertIn("top_opportunity", autopilot)
        self.assertIn("top_candidate", autopilot)
        self.assertIn("top_client", autopilot)
        self.assertIn("top_placement_match", autopilot)
        self.assertGreater(autopilot["highest_estimated_fee"], 0)
        self.assertGreater(autopilot["highest_placement_probability"], 0)

    def test_executive_autopilot_ranking_works(self):
        data = get_glirn_dashboard_data()
        ranked = data["executive_autopilot"]["ranked_recommendations"]

        self.assertGreaterEqual(len(ranked), 1)
        self.assertGreaterEqual(ranked[0]["score"], ranked[-1]["score"])

    def test_executive_autopilot_recommendation_generated(self):
        data = get_glirn_dashboard_data()
        recommendation = data["executive_autopilot"]["dave_recommends_first"]

        self.assertTrue(recommendation["approval_required"])
        self.assertIn("recommendation", recommendation)
        self.assertIn("recommended_focus", recommendation)

    def test_executive_autopilot_compliance_gate_respected(self):
        data = get_glirn_dashboard_data()
        autopilot = build_executive_autopilot(
            data["legal_opportunity_radar"],
            data["executive_search"],
            data["client_acquisition_engine"],
            data["candidate_discovery_engine"],
            data["matching_engine"],
            data["commercial_revenue_engine"],
            {
                **data["compliance_core"],
                "compliance_alerts": [{"alert_type": "missing_candidate_consent"}],
            },
        )

        self.assertFalse(autopilot["compliance_gate_clear"])
        self.assertIn("compliance alerts", autopilot["dave_recommends_first"]["recommendation"].lower())

    def test_executive_autopilot_approval_queue_generated(self):
        data = get_glirn_dashboard_data()
        autopilot = data["executive_autopilot"]

        self.assertGreaterEqual(autopilot["approval_queue_count"], 1)
        self.assertTrue(all(item["approval_required"] for item in autopilot["gareth_approval_queue"]))
        self.assertTrue(autopilot["human_approval_mandatory"])
        self.assertFalse(autopilot["capital_execution"])

    def test_dashboard_includes_executive_autopilot(self):
        data = get_glirn_dashboard_data()

        self.assertIn("executive_autopilot", data)
        self.assertEqual(data["executive_autopilot"]["status"], "Executive Autopilot Waiting for Gareth Approval")
        self.assertIn("executive_autopilot_status", data["summary"])

    def test_live_data_source_registry_created(self):
        registry = get_live_data_source_registry()

        self.assertGreaterEqual(len(registry), 1)
        self.assertIn("source_id", registry[0])
        self.assertIn("source_name", registry[0])
        self.assertTrue(registry[0]["human_approval_required"])

    def test_live_data_readiness_score_calculated(self):
        source = get_live_data_source_registry()[0]
        readiness = calculate_source_readiness(source)

        self.assertIn("compliance_readiness_score", readiness)
        self.assertGreaterEqual(readiness["compliance_readiness_score"], 0)
        self.assertLessEqual(readiness["compliance_readiness_score"], 100)

    def test_high_risk_live_data_source_blocked_by_default(self):
        readiness = build_live_data_readiness()
        high_risk = next(
            source for source in readiness["source_registry"]
            if source["risk_level"] == "high"
        )

        self.assertTrue(high_risk["blocked_by_default"])
        self.assertEqual(high_risk["ingestion_readiness_status"], "blocked_high_risk_default")
        self.assertIn(high_risk, readiness["blocked_sources"])

    def test_candidate_personal_data_source_requires_consent_controls(self):
        readiness = build_live_data_readiness()
        personal_source = next(
            source for source in readiness["source_registry"]
            if source["contains_personal_data"]
        )

        self.assertTrue(personal_source["requires_candidate_consent"])
        self.assertEqual(personal_source["consent_readiness"], "ready")

    def test_live_data_source_cannot_activate_without_gareth_approval(self):
        readiness = build_live_data_readiness()
        proposed = next(
            source for source in readiness["source_registry"]
            if source["status"] == "proposed"
        )

        self.assertEqual(proposed["approval_readiness"], "requires_gareth_approval")
        self.assertEqual(proposed["ingestion_readiness_status"], "pending_gareth_approval")

    def test_unclear_lawful_basis_blocks_readiness(self):
        readiness = build_live_data_readiness()
        unclear = next(
            source for source in readiness["source_registry"]
            if source["lawful_basis_readiness"] == "unclear"
            and source["risk_level"] != "high"
        )

        self.assertEqual(unclear["ingestion_readiness_status"], "not_ready_lawful_basis_unclear")

    def test_dashboard_includes_live_data_readiness(self):
        data = get_glirn_dashboard_data()

        self.assertIn("live_data_readiness", data)
        self.assertIn("source_registry", data)
        self.assertIn("source_readiness_summary", data)
        self.assertIn("blocked_sources", data)
        self.assertIn("approved_sources", data)
        self.assertIn("pending_sources", data)
        self.assertEqual(data["live_data_readiness"]["status"], "Live Data Readiness Controls Active")
        self.assertIn("live_data_readiness_status", data["summary"])

    def test_integration_governance_scoring(self):
        integration = get_integration_registry()[0]
        governed = calculate_integration_governance(integration)

        self.assertIn("compliance_score", governed)
        self.assertIn("approval_score", governed)
        self.assertIn("readiness_score", governed)
        self.assertIn("risk_score", governed)
        self.assertIn("governance_status", governed)
        self.assertGreaterEqual(governed["readiness_score"], 0)
        self.assertLessEqual(governed["readiness_score"], 100)

    def test_integration_governance_high_risk_blocked(self):
        governance = build_integration_governance()
        high_risk = next(
            item for item in governance["integration_registry"]
            if item["risk_level"] == "high"
        )

        self.assertTrue(high_risk["blocked_by_default"])
        self.assertEqual(high_risk["governance_status"], "blocked_high_risk_default")
        self.assertIn(high_risk, governance["blocked_integrations"])

    def test_personal_data_integration_requires_consent_controls(self):
        governance = build_integration_governance()
        personal = next(
            item for item in governance["integration_registry"]
            if item["contains_personal_data"]
        )

        self.assertTrue(personal["requires_candidate_consent"])

    def test_integration_governance_dashboard_rendering_data(self):
        data = get_glirn_dashboard_data()

        self.assertIn("integration_governance", data)
        self.assertIn("approved_integrations", data)
        self.assertIn("blocked_integrations", data)
        self.assertIn("pending_integrations", data)
        self.assertIn("governance_alerts", data)
        self.assertEqual(data["integration_governance"]["status"], "Integration Governance Controls Active")
        self.assertIn("integration_governance_status", data["summary"])

    def test_deployment_readiness_score_generated(self):
        data = get_glirn_dashboard_data()
        readiness = data["deployment_readiness"]

        self.assertIn("readiness_percentage", readiness)
        self.assertIn("readiness_grade", readiness)
        self.assertGreaterEqual(readiness["readiness_percentage"], 0)
        self.assertLessEqual(readiness["readiness_percentage"], 100)
        self.assertFalse(readiness["deployment_actions_enabled"])

    def test_deployment_launch_checklist_generated(self):
        data = get_glirn_dashboard_data()
        checklist = data["deployment_readiness"]["launch_checklist"]

        self.assertGreaterEqual(len(checklist), 1)
        self.assertIn("platform status", [item["item"] for item in checklist])
        self.assertIn("audit status", [item["item"] for item in checklist])

    def test_deployment_critical_gaps_identified(self):
        data = get_glirn_dashboard_data()
        readiness = build_deployment_readiness(
            data["compliance_core"],
            data["approval_centre"],
            data["commercial_revenue_engine"],
            data["live_data_readiness"],
            data["integration_governance"],
            data["executive_autopilot"],
        )

        self.assertGreaterEqual(len(readiness["critical_gaps"]), 1)
        self.assertTrue(readiness["assessment_only"])
        self.assertTrue(readiness["human_approval_mandatory"])

    def test_dashboard_includes_deployment_readiness(self):
        data = get_glirn_dashboard_data()

        self.assertIn("deployment_readiness", data)
        self.assertIn("readiness_score", data)
        self.assertIn("critical_gaps", data)
        self.assertIn("launch_checklist", data)
        self.assertEqual(data["deployment_readiness"]["status"], "Deployment Readiness Assessment Active")
        self.assertIn("deployment_readiness_status", data["summary"])

    def test_operations_command_centre_aggregation_works(self):
        data = get_glirn_dashboard_data()
        centre = build_operations_command_centre(
            data["executive_autopilot"],
            data["legal_opportunity_radar"],
            data["client_acquisition_engine"],
            data["candidate_discovery_engine"],
            data["matching_engine"],
            data["commercial_revenue_engine"],
            data["compliance_core"],
            data["deployment_readiness"],
            data["approval_centre"],
        )

        self.assertEqual(centre["engine"], "operations_command_centre")
        self.assertIn("executive_summary", centre)
        self.assertIn("key_metrics", centre)
        self.assertIn("platform_health", centre)
        self.assertTrue(centre["read_only"])

    def test_operations_command_centre_executive_metrics_generated(self):
        data = get_glirn_dashboard_data()
        metrics = data["operations_command_centre"]["key_metrics"]

        self.assertGreater(metrics["total_opportunities"], 0)
        self.assertGreater(metrics["total_candidates"], 0)
        self.assertGreater(metrics["total_clients"], 0)
        self.assertGreater(metrics["total_matches"], 0)
        self.assertIn("estimated_revenue_pipeline", metrics)
        self.assertIn("readiness_score", metrics)

    def test_dashboard_includes_operations_command_centre(self):
        data = get_glirn_dashboard_data()

        self.assertIn("operations_command_centre", data)
        self.assertIn("executive_summary", data)
        self.assertIn("key_metrics", data)
        self.assertIn("platform_health", data)
        self.assertEqual(data["operations_command_centre"]["status"], "Operations Command Centre Active")
        self.assertIn("operations_command_centre_status", data["summary"])

    def test_daily_executive_briefing_generated(self):
        data = get_glirn_dashboard_data()
        briefing = data["daily_executive_briefing"]

        self.assertEqual(briefing["engine"], "daily_executive_briefing")
        self.assertEqual(briefing["status"], "Daily Executive Briefing Ready")
        self.assertTrue(briefing["read_only"])
        self.assertTrue(briefing["human_approval_mandatory"])

    def test_daily_executive_briefing_top_opportunities_included(self):
        data = get_glirn_dashboard_data()
        opportunities = data["daily_executive_briefing"]["top_3_opportunities"]

        self.assertGreaterEqual(len(opportunities), 1)
        self.assertLessEqual(len(opportunities), 3)
        self.assertIn("title", opportunities[0])

    def test_daily_executive_briefing_risks_included(self):
        data = get_glirn_dashboard_data()
        risks = data["daily_executive_briefing"]["top_3_risks"]

        self.assertGreaterEqual(len(risks), 1)
        self.assertIn("risk_type", risks[0])
        self.assertIn("description", risks[0])

    def test_daily_executive_briefing_revenue_actions_included(self):
        data = get_glirn_dashboard_data()
        actions = data["daily_executive_briefing"]["top_3_revenue_actions"]

        self.assertGreaterEqual(len(actions), 1)
        self.assertIn("recommended_action", actions[0])

    def test_daily_executive_briefing_approvals_included(self):
        data = get_glirn_dashboard_data()
        briefing = build_daily_executive_briefing(
            data["operations_command_centre"],
            data["legal_opportunity_radar"],
            data["commercial_revenue_engine"],
            data["compliance_core"],
            data["deployment_readiness"],
            data["executive_autopilot"],
        )

        self.assertGreaterEqual(len(briefing["pending_gareth_approvals"]), 1)
        self.assertIn("dave_recommends_today", briefing)

    def test_dashboard_includes_daily_executive_briefing(self):
        data = get_glirn_dashboard_data()

        self.assertIn("daily_executive_briefing", data)
        self.assertEqual(data["daily_executive_briefing"]["status"], "Daily Executive Briefing Ready")
        self.assertIn("daily_executive_briefing_status", data["summary"])

    def test_intelligence_review_generated(self):
        data = get_glirn_dashboard_data()
        engine = data["intelligence_review_engine"]

        self.assertEqual(engine["engine"], "intelligence_review_engine")
        self.assertEqual(engine["review_generation_status"], "generated_pending_gareth_approval")
        self.assertGreaterEqual(len(engine["generated_reviews"]), 1)

    def test_intelligence_review_includes_required_sections(self):
        data = get_glirn_dashboard_data()
        review = data["intelligence_review_engine"]["latest_generated_review"]
        sections = review["sections"]
        required = [
            "Executive Summary",
            "Client Context",
            "Practice Area Focus",
            "Jurisdiction Focus",
            "Market Signal Summary",
            "Hiring Difficulty Assessment",
            "Recommended Priority Role",
            "Candidate Profile Specification",
            "Indicative Fee Model",
            "Compliance Summary",
        ]

        for section in required:
            self.assertIn(section, sections)

    def test_intelligence_review_uses_existing_glirn_module_data(self):
        data = get_glirn_dashboard_data()
        engine = build_intelligence_review_engine(
            data["intelligence_network"],
            data["client_acquisition_engine"],
            data["candidate_discovery_engine"],
            data["matching_engine"],
            data["commercial_revenue_engine"],
            data["compliance_core"],
            data["executive_autopilot"],
        )
        review = engine["latest_generated_review"]

        self.assertIn("Legal Intelligence Network", review["source_modules"])
        self.assertIn("Client Acquisition Engine", review["source_modules"])
        self.assertIn("Matching Engine", review["source_modules"])
        self.assertEqual(review["target_client_profile"], data["client_acquisition_engine"]["top_target_clients"][0]["client_name"])

    def test_intelligence_review_requires_gareth_approval_before_client_ready(self):
        data = get_glirn_dashboard_data()
        review = data["intelligence_review_engine"]["latest_generated_review"]

        self.assertEqual(review["approval_status"], "pending_gareth_approval")
        self.assertFalse(review["client_ready"])
        self.assertFalse(review["client_delivery_allowed"])
        self.assertTrue(review["approval_required_before_client_ready"])

    def test_intelligence_brief_contains_mandatory_human_review_framework(self):
        review = get_glirn_dashboard_data()["intelligence_review_engine"]["latest_generated_review"]
        framework = review["human_review_framework"]

        self.assertEqual(
            {item["check_id"] for item in framework["checklist"]},
            set(HUMAN_REVIEW_CHECKLIST),
        )
        self.assertEqual(set(framework["red_flag_rules"]), set(RED_FLAG_RULES))
        self.assertEqual(set(framework["decline_criteria"]), set(DECLINE_CRITERIA))
        self.assertTrue(framework["human_review_required"])
        self.assertTrue(framework["quality_assurance_required"])
        self.assertFalse(framework["client_delivery_allowed"])

    def test_human_review_approval_requires_complete_checklist_and_resolved_red_flags(self):
        brief = {
            "review_id": "brief-001",
            "candidate_personal_data_included": False,
            "candidate_personal_data_blocked": True,
        }
        brief["human_review_framework"] = build_initial_human_review_framework(
            brief,
            ai_confidence=40,
            speculative_content=True,
            evidence_sufficient=False,
        )
        submission = {
            "reviewer": "Gareth",
            "outcome": "approved_for_manual_delivery",
            "approval_rationale": "Reviewed against the quality framework.",
            "checklist_results": {key: True for key in HUMAN_REVIEW_CHECKLIST},
            "red_flag_resolutions": {},
            "delivery_status": "ready_for_manual_delivery",
        }

        unresolved = evaluate_human_review(brief, submission)
        self.assertFalse(unresolved["approved_for_manual_delivery"])
        self.assertIn("low_ai_confidence", unresolved["unresolved_red_flags"])
        self.assertIn("speculative_content", unresolved["unresolved_red_flags"])
        self.assertIn("insufficient_evidence", unresolved["unresolved_red_flags"])
        self.assertEqual(unresolved["delivery_status"], "blocked")

        submission["red_flag_resolutions"] = {
            name: True for name, active in unresolved["red_flags"].items() if active
        }
        approved = evaluate_human_review(brief, submission)
        self.assertTrue(approved["approved_for_manual_delivery"])
        self.assertEqual(approved["delivery_status"], "ready_for_manual_delivery")
        self.assertTrue(approved["manual_delivery_only"])
        self.assertFalse(approved["external_delivery_enabled"])

    def test_candidate_specific_human_review_requires_active_consent(self):
        brief = {
            "review_id": "brief-candidate-001",
            "candidate_personal_data_included": True,
            "candidate_personal_data_blocked": True,
        }
        brief["human_review_framework"] = build_initial_human_review_framework(brief)
        record = evaluate_human_review(brief, {
            "reviewer": "Gareth",
            "outcome": "approved_for_manual_delivery",
            "approval_rationale": "Candidate-specific brief reviewed.",
            "checklist_results": {key: True for key in HUMAN_REVIEW_CHECKLIST},
            "red_flag_resolutions": {"candidate_specific_intelligence": True},
            "delivery_status": "ready_for_manual_delivery",
        })

        self.assertFalse(record["candidate_consent_valid"])
        self.assertFalse(record["approved_for_manual_delivery"])
        self.assertIn("candidate_specific_intelligence", record["unresolved_red_flags"])

    def test_decline_record_uses_defined_criteria_and_blocks_delivery(self):
        brief = {
            "review_id": "brief-decline-001",
            "candidate_personal_data_included": False,
            "candidate_personal_data_blocked": True,
        }
        record = evaluate_human_review(brief, {
            "reviewer": "Gareth",
            "outcome": "declined",
            "approval_rationale": "A specialist adviser is better placed.",
            "checklist_results": {},
            "decline_criterion": "specialist_adviser_better_placed",
            "delivery_status": "blocked",
        })

        self.assertEqual(record["outcome"], "declined")
        self.assertEqual(record["delivery_status"], "blocked")
        self.assertEqual(
            record["decline_reason"],
            "Another specialist adviser would better serve the client's needs.",
        )
        self.assertFalse(record["client_delivery_allowed"])

    def test_intelligence_review_candidate_personal_data_blocked_without_consent(self):
        data = get_glirn_dashboard_data()
        blocked_candidate_engine = {
            **data["candidate_discovery_engine"],
            "top_candidate_opportunities": [
                {
                    **data["candidate_discovery_engine"]["top_candidate_opportunities"][0],
                    "consent_readiness_status": "missing",
                    "candidate_name": "Candidate X",
                }
            ],
        }
        engine = build_intelligence_review_engine(
            data["intelligence_network"],
            data["client_acquisition_engine"],
            blocked_candidate_engine,
            data["matching_engine"],
            data["commercial_revenue_engine"],
            data["compliance_core"],
            data["executive_autopilot"],
        )
        review = engine["latest_generated_review"]

        self.assertFalse(review["candidate_personal_data_included"])
        self.assertTrue(review["candidate_personal_data_blocked"])
        self.assertIsNone(review["sections"]["Candidate Profile Specification"]["candidate_name"])

    def test_dashboard_includes_intelligence_review_engine(self):
        data = get_glirn_dashboard_data()

        self.assertIn("intelligence_review_engine", data)
        self.assertIn("generated_reviews", data)
        self.assertIn("pending_review_approvals", data)
        self.assertIn("review_generation_status", data)
        self.assertIn("latest_generated_review", data)
        self.assertEqual(data["intelligence_review_engine"]["status"], "Automated Intelligence Review Draft Ready")
        self.assertIn("intelligence_review_engine_status", data["summary"])

    def test_search_mandate_proposal_generated(self):
        data = get_glirn_dashboard_data()
        deliverables = data["deliverable_factory"]["generated_deliverables"]
        item = next(deliverable for deliverable in deliverables if deliverable["deliverable_type"] == "Search Mandate Proposal")

        self.assertIn("client_context", item["sections"])
        self.assertIn("fee_model", item["sections"])

    def test_executive_search_proposal_generated(self):
        data = get_glirn_dashboard_data()
        deliverables = data["deliverable_factory"]["generated_deliverables"]
        item = next(deliverable for deliverable in deliverables if deliverable["deliverable_type"] == "Executive Search Proposal")

        self.assertIn("executive_role_summary", item["sections"])
        self.assertIn("proposed_retained_search_model", item["sections"])

    def test_fee_proposal_generated(self):
        data = get_glirn_dashboard_data()
        deliverables = data["deliverable_factory"]["generated_deliverables"]
        item = next(deliverable for deliverable in deliverables if deliverable["deliverable_type"] == "Fee Proposal")

        self.assertIn("fee_structure", item["sections"])
        self.assertIn("approval_requirements", item["sections"])
        self.assertFalse(item["client_ready"])

    def test_candidate_shortlist_generated(self):
        data = get_glirn_dashboard_data()
        deliverables = data["deliverable_factory"]["generated_deliverables"]
        item = next(deliverable for deliverable in deliverables if deliverable["deliverable_type"] == "Candidate Shortlist Report")

        self.assertIn("anonymised_candidate_profiles", item["sections"])
        self.assertFalse(item["candidate_personal_data_included"])
        self.assertTrue(item["candidate_personal_data_blocked"])

    def test_market_intelligence_report_generated(self):
        data = get_glirn_dashboard_data()
        deliverables = data["deliverable_factory"]["generated_deliverables"]
        item = next(deliverable for deliverable in deliverables if deliverable["deliverable_type"] == "Market Intelligence Report")

        self.assertIn("market_demand_indicators", item["sections"])
        self.assertIn("practice_area_observations", item["sections"])

    def test_client_meeting_brief_generated(self):
        data = get_glirn_dashboard_data()
        deliverables = data["deliverable_factory"]["generated_deliverables"]
        item = next(deliverable for deliverable in deliverables if deliverable["deliverable_type"] == "Client Meeting Brief")

        self.assertIn("meeting_objective", item["sections"])
        self.assertIn("recommended_outcome", item["sections"])

    def test_deliverable_approval_required_before_client_ready(self):
        data = get_glirn_dashboard_data()
        factory = build_client_deliverable_factory(
            data["executive_autopilot"],
            data["intelligence_review_engine"],
            data["client_acquisition_engine"],
            data["candidate_discovery_engine"],
            data["matching_engine"],
            data["commercial_revenue_engine"],
            data["compliance_core"],
        )
        latest = factory["latest_deliverable"]

        self.assertEqual(latest["approval_status"], "pending_gareth_approval")
        self.assertFalse(latest["client_ready"])
        self.assertFalse(latest["client_delivery_allowed"])
        self.assertTrue(factory["human_approval_mandatory"])

    def test_dashboard_includes_deliverable_factory(self):
        data = get_glirn_dashboard_data()

        self.assertIn("deliverable_factory", data)
        self.assertIn("generated_deliverables", data)
        self.assertIn("pending_deliverable_approvals", data)
        self.assertIn("latest_deliverable", data)
        self.assertIn("deliverable_status", data)
        self.assertEqual(data["deliverable_factory"]["status"], "Client Deliverable Drafts Ready")
        self.assertIn("deliverable_factory_status", data["summary"])

    def test_generated_draft_remains_not_client_ready(self):
        data = get_glirn_dashboard_data()
        workflow = data["approval_to_action_workflow"]
        item = workflow["pending_gareth_approval"][0]

        self.assertEqual(item["draft_status"], "generated_draft")
        self.assertFalse(item["client_ready"])
        self.assertEqual(item["client_ready_status"], "not_client_ready")

    def test_approval_to_action_dashboard_includes_workflow(self):
        data = get_glirn_dashboard_data()

        self.assertIn("approval_to_action_workflow", data)
        self.assertIn("approved_for_human_use", data)
        self.assertIn("pending_gareth_approval", data)
        self.assertIn("rejected_items", data)
        self.assertIn("monitored_items", data)
        self.assertEqual(data["approval_to_action_workflow"]["status"], "Approval-to-Action Controls Active")
        self.assertIn("approval_to_action_workflow_status", data["summary"])

    def test_approval_to_action_workflow_has_control_queues(self):
        data = get_glirn_dashboard_data()
        workflow = build_approval_to_action_workflow(
            data["intelligence_review_engine"],
            data["deliverable_factory"],
        )

        self.assertGreaterEqual(len(workflow["pending_gareth_approval"]), 1)
        self.assertEqual(workflow["approved_deliverable_queue"], [])
        self.assertEqual(workflow["rejected_deliverable_queue"], [])
        self.assertEqual(workflow["monitored_deliverable_queue"], [])
        self.assertFalse(workflow["automatic_delivery_enabled"])

    def test_revenue_pipeline_generated(self):
        data = get_glirn_dashboard_data()
        centre = build_revenue_command_centre(
            data["legal_opportunity_radar"],
            data["executive_autopilot"],
            data["matching_engine"],
            data["commercial_revenue_engine"],
            data["deliverable_factory"],
            data["approval_to_action_workflow"],
            data["daily_executive_briefing"],
        )

        self.assertEqual(centre["engine"], "revenue_command_centre")
        self.assertGreater(centre["total_revenue_pipeline"], 0)
        self.assertGreater(len(centre["revenue_pipeline"]), 0)
        self.assertTrue(centre["read_only"])
        self.assertFalse(centre["invoicing_enabled"])

    def test_revenue_funnel_generated(self):
        data = get_glirn_dashboard_data()
        funnel = data["revenue_command_centre"]["revenue_funnel"]
        stages = [item["stage"] for item in funnel]

        self.assertEqual(stages, [
            "Opportunity",
            "Intelligence Review",
            "Search Mandate",
            "Candidate Match",
            "Placement",
            "Invoice Ready",
        ])
        self.assertTrue(all("readiness_status" in item for item in funnel))

    def test_highest_fee_opportunity_identified(self):
        data = get_glirn_dashboard_data()
        highest = data["revenue_command_centre"]["highest_fee_opportunity"]

        self.assertIsNotNone(highest)
        self.assertGreater(highest["estimated_revenue"], 0)
        self.assertEqual(data["highest_fee_opportunity"], highest)

    def test_fastest_revenue_opportunity_identified(self):
        data = get_glirn_dashboard_data()
        fastest = data["revenue_command_centre"]["fastest_revenue_opportunity"]

        self.assertIsNotNone(fastest)
        self.assertIn("invoice_readiness", fastest)
        self.assertEqual(data["fastest_revenue_opportunity"], fastest)

    def test_revenue_readiness_score_calculated(self):
        data = get_glirn_dashboard_data()
        score = data["revenue_command_centre"]["revenue_readiness_score"]

        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)
        self.assertEqual(data["revenue_readiness_score"], score)

    def test_dashboard_includes_revenue_command_centre(self):
        data = get_glirn_dashboard_data()

        self.assertIn("revenue_command_centre", data)
        self.assertIn("revenue_pipeline", data)
        self.assertIn("revenue_funnel", data)
        self.assertIn("highest_fee_opportunity", data)
        self.assertIn("fastest_revenue_opportunity", data)
        self.assertIn("top_revenue_opportunities", data)
        self.assertEqual(data["revenue_command_centre"]["status"], "Revenue Command Centre Active")
        self.assertIn("revenue_command_centre_status", data["summary"])

    def test_first_client_readiness_gate_generated(self):
        data = get_glirn_dashboard_data()
        gate = data["first_client_readiness_gate"]

        self.assertEqual(gate["engine"], "first_client_readiness_gate")
        self.assertEqual(gate["status"], "First Client Readiness Gate Active")
        self.assertGreaterEqual(len(gate["readiness_checks"]), 1)
        self.assertTrue(gate["human_approval_mandatory"])
        self.assertFalse(gate["client_contact_enabled"])

    def test_first_client_readiness_scores_calculated(self):
        data = get_glirn_dashboard_data()
        item = data["first_client_readiness_gate"]["readiness_checks"][0]

        self.assertIn("client_readiness_score", item)
        self.assertIn("compliance_readiness_score", item)
        self.assertIn("commercial_readiness_score", item)
        self.assertIn("deliverable_readiness_score", item)
        self.assertIn("approval_readiness_score", item)
        self.assertIn("overall_first_client_readiness_score", item)
        self.assertGreaterEqual(item["overall_first_client_readiness_score"], 0)
        self.assertLessEqual(item["overall_first_client_readiness_score"], 100)

    def test_missing_consent_blocks_first_client_readiness(self):
        data = get_glirn_dashboard_data()
        gate = data["first_client_readiness_gate"]

        self.assertGreaterEqual(len(gate["blocked_first_client_items"]), 1)
        self.assertIn(
            gate["blocked_first_client_items"][0]["readiness_recommendation"],
            {
                "blocked_missing_consent",
                "blocked_missing_terms",
                "blocked_missing_compliance",
                "blocked_missing_fee_model",
                "blocked_missing_deliverable",
                "reject",
            },
        )

    def test_missing_client_terms_blocks_first_client_readiness(self):
        data = get_glirn_dashboard_data()
        item = data["first_client_readiness_gate"]["readiness_checks"][0]

        if not item["readiness_checks"]["client_terms_ready"]:
            self.assertEqual(item["readiness_recommendation"], "blocked_missing_terms")
        else:
            self.assertTrue(item["readiness_checks"]["client_terms_ready"])

    def test_missing_deliverable_blocks_first_client_readiness(self):
        data = get_glirn_dashboard_data()
        opportunity = data["legal_opportunity_radar"]["opportunities_ranked"][0]
        commercial = {
            **data["commercial_revenue_engine"],
            "commercial_pipeline": [
                {
                    "opportunity_id": opportunity["opportunity_id"],
                    "fee_type": "executive search fee",
                    "client_terms_readiness": "recorded",
                    "blocked_reasons": [],
                }
            ],
        }
        gate = build_first_client_readiness_gate(
            {"opportunities_ranked": [opportunity]},
            data["intelligence_review_engine"],
            {"generated_deliverables": []},
            data["approval_to_action_workflow"],
            commercial,
            {"compliance_alerts": []},
            data["revenue_command_centre"],
        )

        item = gate["readiness_checks"][0]
        self.assertFalse(item["readiness_checks"]["deliverable_generated"])
        self.assertIn("deliverable_generated", item["missing_checks"])
        self.assertEqual(item["readiness_recommendation"], "blocked_missing_deliverable")

    def test_missing_fee_model_blocks_first_client_readiness(self):
        data = get_glirn_dashboard_data()
        opportunity = data["legal_opportunity_radar"]["opportunities_ranked"][0]
        commercial = {
            **data["commercial_revenue_engine"],
            "commercial_pipeline": [
                {
                    "opportunity_id": opportunity["opportunity_id"],
                    "fee_type": None,
                    "client_terms_readiness": "recorded",
                    "blocked_reasons": [],
                }
            ],
        }
        gate = build_first_client_readiness_gate(
            {"opportunities_ranked": [opportunity]},
            data["intelligence_review_engine"],
            data["deliverable_factory"],
            data["approval_to_action_workflow"],
            commercial,
            {"compliance_alerts": []},
            data["revenue_command_centre"],
        )

        item = gate["readiness_checks"][0]
        self.assertFalse(item["readiness_checks"]["fee_model_ready"])
        self.assertIn("fee_model_ready", item["missing_checks"])
        self.assertEqual(item["readiness_recommendation"], "blocked_missing_fee_model")

    def test_dashboard_includes_first_client_readiness_gate(self):
        data = get_glirn_dashboard_data()

        self.assertIn("first_client_readiness_gate", data)
        self.assertIn("readiness_checks", data)
        self.assertIn("first_client_ready_items", data)
        self.assertIn("blocked_first_client_items", data)
        self.assertIn("monitored_first_client_items", data)
        self.assertIn("readiness_recommendation", data)
        self.assertIn("overall_first_client_readiness_score", data)
        self.assertEqual(data["first_client_readiness_gate"]["status"], "First Client Readiness Gate Active")
        self.assertIn("first_client_readiness_gate_status", data["summary"])

    def test_launch_readiness_command_centre_generated(self):
        data = get_glirn_dashboard_data()
        centre = data["launch_readiness_command_centre"]

        self.assertEqual(centre["engine"], "launch_readiness_command_centre")
        self.assertEqual(centre["status"], "Launch Readiness Command Centre Active")
        self.assertTrue(centre["human_approval_mandatory"])
        self.assertFalse(centre["autonomous_launch_enabled"])

    def test_launch_readiness_score_calculated(self):
        data = get_glirn_dashboard_data()
        centre = data["launch_readiness_command_centre"]

        self.assertIn("launch_readiness_score", centre)
        self.assertIn("overall_launch_readiness_score", centre)
        self.assertGreaterEqual(centre["launch_readiness_score"], 0)
        self.assertLessEqual(centre["launch_readiness_score"], 100)

    def test_launch_readiness_grade_calculated(self):
        data = get_glirn_dashboard_data()
        grade = data["launch_readiness_command_centre"]["launch_readiness_grade"]

        self.assertIn(grade, {"launch_ready", "nearly_ready", "not_ready", "blocked"})

    def test_missing_website_asset_detected(self):
        data = get_glirn_dashboard_data()
        centre = build_launch_readiness_command_centre(
            data["deployment_readiness"],
            data["first_client_readiness_gate"],
            data["revenue_command_centre"],
            data["intelligence_review_engine"],
            data["deliverable_factory"],
            data["approval_to_action_workflow"],
            launch_assets={"website_asset_ready": False},
        )

        descriptions = [item["description"] for item in centre["launch_missing_items"]]
        self.assertIn("missing website asset", descriptions)

    def test_missing_linkedin_asset_detected(self):
        data = get_glirn_dashboard_data()
        centre = build_launch_readiness_command_centre(
            data["deployment_readiness"],
            data["first_client_readiness_gate"],
            data["revenue_command_centre"],
            data["intelligence_review_engine"],
            data["deliverable_factory"],
            data["approval_to_action_workflow"],
            launch_assets={"linkedin_asset_ready": False},
        )

        descriptions = [item["description"] for item in centre["launch_missing_items"]]
        self.assertIn("missing LinkedIn profile asset", descriptions)

    def test_missing_sample_review_detected(self):
        data = get_glirn_dashboard_data()
        centre = build_launch_readiness_command_centre(
            data["deployment_readiness"],
            data["first_client_readiness_gate"],
            data["revenue_command_centre"],
            {"latest_generated_review": None},
            data["deliverable_factory"],
            data["approval_to_action_workflow"],
        )

        descriptions = [item["description"] for item in centre["launch_missing_items"]]
        self.assertIn("missing sample intelligence review", descriptions)
        self.assertEqual(centre["launch_recommended_next_action"], "create_sample_review")

    def test_missing_payment_process_detected(self):
        data = get_glirn_dashboard_data()
        centre = build_launch_readiness_command_centre(
            data["deployment_readiness"],
            data["first_client_readiness_gate"],
            data["revenue_command_centre"],
            data["intelligence_review_engine"],
            data["deliverable_factory"],
            data["approval_to_action_workflow"],
            launch_assets={"payment_process_ready": False},
        )

        descriptions = [item["description"] for item in centre["launch_missing_items"]]
        self.assertIn("missing payment process", descriptions)

    def test_launch_blocked_items_identified(self):
        data = get_glirn_dashboard_data()
        centre = data["launch_readiness_command_centre"]

        self.assertGreaterEqual(len(centre["launch_blocked_items"]), 1)
        self.assertIn("reason", centre["launch_blocked_items"][0])

    def test_launch_recommended_next_action_generated(self):
        data = get_glirn_dashboard_data()
        action = data["launch_readiness_command_centre"]["launch_recommended_next_action"]

        self.assertIn(action, {
            "create_sample_review",
            "publish_website_copy",
            "complete_linkedin_profile",
            "confirm_first_offer",
            "confirm_client_terms_process",
            "confirm_payment_process",
            "approve_first_client_action",
            "monitor",
        })

    def test_dashboard_includes_launch_readiness_command_centre(self):
        data = get_glirn_dashboard_data()

        self.assertIn("launch_readiness_command_centre", data)
        self.assertIn("launch_readiness_score", data)
        self.assertIn("launch_readiness_grade", data)
        self.assertIn("launch_ready_items", data)
        self.assertIn("launch_blocked_items", data)
        self.assertIn("launch_missing_items", data)
        self.assertIn("launch_recommended_next_action", data)
        self.assertEqual(data["launch_readiness_command_centre"]["status"], "Launch Readiness Command Centre Active")
        self.assertIn("launch_readiness_command_centre_status", data["summary"])

    def test_invoice_draft_generated(self):
        data = get_glirn_dashboard_data()
        engine = build_invoice_drafting_engine(
            data["commercial_revenue_engine"],
            data["first_client_readiness_gate"],
            data["revenue_command_centre"],
        )

        self.assertEqual(engine["engine"], "invoice_drafting_engine")
        self.assertGreaterEqual(len(engine["invoice_drafts"]), 1)
        self.assertEqual(engine["status"], "Invoice Drafting Engine Active")

    def test_invoice_includes_required_fields(self):
        data = get_glirn_dashboard_data()
        draft = data["invoice_drafting_engine"]["invoice_drafts"][0]
        required_fields = {
            "invoice_number",
            "invoice_date",
            "supply_date",
            "seller_name",
            "seller_business_name",
            "seller_contact_details",
            "customer_name",
            "customer_address",
            "service_description",
            "fee_type",
            "amount",
            "VAT_status",
            "VAT_amount_if_applicable",
            "total_amount_due",
            "payment_method_options",
            "payment_due_date",
            "payment_reference",
            "notes",
        }

        self.assertTrue(required_fields.issubset(draft.keys()))

    def test_invoice_supports_paypal_business(self):
        data = get_glirn_dashboard_data()
        draft = data["invoice_drafting_engine"]["invoice_drafts"][0]

        self.assertIn("PayPal Business", draft["payment_method_options"])

    def test_invoice_supports_revolut_uk_bank_transfer(self):
        data = get_glirn_dashboard_data()
        draft = data["invoice_drafting_engine"]["invoice_drafts"][0]

        self.assertIn("Revolut UK Bank Transfer", draft["payment_method_options"])

    def test_invoice_cannot_be_sent_automatically(self):
        data = get_glirn_dashboard_data()
        engine = data["invoice_drafting_engine"]
        draft = engine["invoice_drafts"][0]

        self.assertFalse(engine["automatic_sending_enabled"])
        self.assertFalse(draft["automatic_sending_enabled"])
        self.assertFalse(draft["automatic_payment_collection_enabled"])
        self.assertFalse(draft["external_payment_integration_enabled"])

    def test_invoice_requires_gareth_approval(self):
        data = get_glirn_dashboard_data()
        draft = data["invoice_drafting_engine"]["invoice_drafts"][0]

        self.assertTrue(draft["human_approval_required"])
        self.assertEqual(draft["approval_status"], "pending_gareth_approval")
        self.assertIn("gareth_approval_status", draft["invoice_readiness_checks"])

    def test_dashboard_includes_invoice_drafting_engine(self):
        data = get_glirn_dashboard_data()

        self.assertIn("invoice_drafting_engine", data)
        self.assertIn("invoice_drafts", data)
        self.assertIn("pending_invoice_approvals", data)
        self.assertIn("invoice_readiness_status", data)
        self.assertEqual(data["invoice_drafting_engine"]["status"], "Invoice Drafting Engine Active")
        self.assertIn("invoice_drafting_engine_status", data["summary"])

    def test_client_terms_draft_generated(self):
        data = get_glirn_dashboard_data()
        engine = build_client_terms_drafting_engine(data["commercial_revenue_engine"])

        self.assertEqual(engine["engine"], "client_terms_drafting_engine")
        self.assertEqual(engine["status"], "Client Terms Drafting Engine Active")
        self.assertGreaterEqual(len(engine["client_terms_drafts"]), 5)

    def test_review_terms_generated(self):
        data = get_glirn_dashboard_data()
        terms_types = [item["terms_type"] for item in data["client_terms_drafting_engine"]["client_terms_drafts"]]

        self.assertIn("GBP 500 GLIRN Senior Legal Hiring Intelligence Review", terms_types)

    def test_contingency_terms_generated(self):
        data = get_glirn_dashboard_data()
        terms_types = [item["terms_type"] for item in data["client_terms_drafting_engine"]["client_terms_drafts"]]

        self.assertIn("contingency search mandate", terms_types)

    def test_retained_terms_generated(self):
        data = get_glirn_dashboard_data()
        terms_types = [item["terms_type"] for item in data["client_terms_drafting_engine"]["client_terms_drafts"]]

        self.assertIn("retained search mandate", terms_types)

    def test_executive_search_terms_generated(self):
        data = get_glirn_dashboard_data()
        terms_types = [item["terms_type"] for item in data["client_terms_drafting_engine"]["client_terms_drafts"]]

        self.assertIn("executive search mandate", terms_types)

    def test_terms_require_gareth_approval(self):
        data = get_glirn_dashboard_data()
        draft = data["client_terms_drafting_engine"]["client_terms_drafts"][0]

        self.assertTrue(draft["human_approval_required"])
        self.assertEqual(draft["gareth_approval_status"], "required")
        self.assertEqual(draft["terms_readiness_status"], "draft_pending_gareth_approval")

    def test_terms_cannot_be_automatically_sent(self):
        data = get_glirn_dashboard_data()
        draft = data["client_terms_drafting_engine"]["client_terms_drafts"][0]

        self.assertFalse(draft["automatic_sending_enabled"])
        self.assertFalse(data["client_terms_drafting_engine"]["automatic_sending_enabled"])

    def test_terms_cannot_be_automatically_agreed(self):
        data = get_glirn_dashboard_data()
        draft = data["client_terms_drafting_engine"]["client_terms_drafts"][0]

        self.assertFalse(draft["automatic_agreement_enabled"])
        self.assertFalse(draft["automatic_contract_acceptance_enabled"])
        self.assertFalse(draft["esignature_integration_enabled"])
        self.assertFalse(draft["solicitor_approved_claim"])

    def test_dashboard_includes_client_terms_drafting_engine(self):
        data = get_glirn_dashboard_data()

        self.assertIn("client_terms_drafting_engine", data)
        self.assertIn("client_terms_drafts", data)
        self.assertIn("pending_terms_approvals", data)
        self.assertIn("approved_terms_drafts", data)
        self.assertIn("terms_readiness_status", data)
        self.assertEqual(data["client_terms_drafting_engine"]["status"], "Client Terms Drafting Engine Active")
        self.assertIn("client_terms_drafting_engine_status", data["summary"])

    def test_candidate_consent_draft_generated(self):
        data = get_glirn_dashboard_data()
        engine = build_candidate_consent_management_engine(data["compliance_core"])

        self.assertEqual(engine["engine"], "candidate_consent_management_engine")
        self.assertEqual(engine["status"], "Candidate Consent Management Engine Active")
        self.assertGreaterEqual(len(engine["candidate_consent_records"]), 1)
        self.assertIn("draft", {item["consent_status"] for item in engine["candidate_consent_records"]})

    def test_candidate_consent_readiness_calculated(self):
        data = get_glirn_dashboard_data()
        engine = data["candidate_consent_management_engine"]

        self.assertIn("candidate_consent_readiness", engine)
        self.assertGreaterEqual(engine["candidate_consent_readiness"], 0)
        self.assertLessEqual(engine["candidate_consent_readiness"], 100)
        self.assertIn(engine["consent_compliance_status"], {"ready", "pending_manual_consent", "blocked"})

    def test_candidate_consent_expiry_tracked(self):
        data = get_glirn_dashboard_data()
        engine = data["candidate_consent_management_engine"]

        self.assertGreaterEqual(len(engine["expired_candidate_consents"]), 1)
        expired = engine["expired_candidate_consents"][0]
        self.assertEqual(expired["consent_status"], "expired")
        self.assertIn("consent_expiry_date", expired)

    def test_candidate_consent_withdrawal_tracked(self):
        data = get_glirn_dashboard_data()
        record = data["candidate_consent_management_engine"]["candidate_consent_records"][0]
        from glirn import apply_candidate_consent_action

        result = apply_candidate_consent_action(record, "mark-manually-withdrawn")

        self.assertEqual(result["consent_status"], "withdrawn")
        self.assertEqual(result["manual_withdrawn_status"], "withdrawn_manually_recorded_by_gareth")
        self.assertFalse(result["candidate_contact_enabled"])

    def test_dashboard_includes_candidate_consent_management_engine(self):
        data = get_glirn_dashboard_data()

        self.assertIn("candidate_consent_management_engine", data)
        self.assertIn("pending_candidate_consents", data)
        self.assertIn("active_candidate_consents", data)
        self.assertIn("expired_candidate_consents", data)
        self.assertIn("consent_readiness_status", data)
        self.assertEqual(data["candidate_consent_management_engine"]["status"], "Candidate Consent Management Engine Active")
        self.assertIn("candidate_consent_management_engine_status", data["summary"])

    def test_manual_delivery_pack_prepared(self):
        data = get_glirn_dashboard_data()
        engine = build_manual_delivery_control_engine(
            data["approval_to_action_workflow"],
            data["client_terms_drafting_engine"],
            data["invoice_drafting_engine"],
            data["candidate_consent_management_engine"],
            data["compliance_core"],
        )

        self.assertEqual(engine["engine"], "manual_delivery_control_engine")
        self.assertEqual(engine["status"], "Manual Delivery Control Engine Active")
        self.assertGreaterEqual(
            len(engine["delivery_ready_items"]) + len(engine["blocked_delivery_items"]),
            1,
        )
        self.assertFalse(engine["client_email_enabled"])

    def test_manual_delivery_blocked_if_not_approved(self):
        data = get_glirn_dashboard_data()
        blocked = data["manual_delivery_control_engine"]["blocked_delivery_items"][0]

        self.assertIn("gareth_approval", blocked["missing_checks"])
        self.assertEqual(blocked["manual_delivery_status"], "blocked")

    def test_manual_delivery_blocked_if_terms_missing(self):
        data = get_glirn_dashboard_data()
        blocked = data["manual_delivery_control_engine"]["blocked_delivery_items"][0]

        self.assertIn("client_terms_readiness", blocked["missing_checks"])

    def test_manual_delivery_blocked_if_consent_missing_where_needed(self):
        data = get_glirn_dashboard_data()
        workflow = {
            "approved_for_human_use": [
                {
                    "item_id": "candidate-shortlist",
                    "item_type": "client_deliverable",
                    "title": "Candidate Shortlist",
                    "approval_status": "approved_by_gareth",
                    "candidate_personal_data_included": True,
                }
            ],
            "pending_gareth_approval": [],
        }
        consent_engine = {**data["candidate_consent_management_engine"], "active_candidate_consents": []}
        engine = build_manual_delivery_control_engine(
            workflow,
            data["client_terms_drafting_engine"],
            data["invoice_drafting_engine"],
            consent_engine,
            {"compliance_alerts": []},
        )

        blocked = engine["blocked_delivery_items"][0]
        self.assertIn("consent_readiness", blocked["missing_checks"])

    def test_dashboard_includes_manual_delivery_control_engine(self):
        data = get_glirn_dashboard_data()

        self.assertIn("manual_delivery_control_engine", data)
        self.assertIn("delivery_ready_items", data)
        self.assertIn("blocked_delivery_items", data)
        self.assertIn("manual_delivery_status", data)
        self.assertEqual(data["manual_delivery_control_engine"]["status"], "Manual Delivery Control Engine Active")
        self.assertIn("manual_delivery_control_engine_status", data["summary"])

    def test_launch_compliance_validation_generated(self):
        data = get_glirn_dashboard_data()
        engine = build_launch_compliance_validation_engine(
            data["manual_delivery_control_engine"],
            data["client_terms_drafting_engine"],
            data["invoice_drafting_engine"],
            data["candidate_consent_management_engine"],
            data["compliance_core"],
        )

        self.assertEqual(engine["engine"], "launch_compliance_validation_engine")
        self.assertEqual(engine["status"], "Launch Compliance Validation Engine Active")
        self.assertGreaterEqual(len(engine["compliance_validation_checks"]), 1)
        self.assertFalse(engine["legal_advice_provided"])
        self.assertFalse(engine["global_legal_compliance_declared"])

    def test_launch_compliance_readiness_score_calculated(self):
        data = get_glirn_dashboard_data()
        engine = data["launch_compliance_validation_engine"]

        self.assertIn("overall_compliance_readiness_score", engine)
        self.assertGreaterEqual(engine["overall_compliance_readiness_score"], 0)
        self.assertLessEqual(engine["overall_compliance_readiness_score"], 100)

    def test_launch_compliance_missing_candidate_consent_blocks_readiness(self):
        data = get_glirn_dashboard_data()
        manual_engine = {
            "delivery_ready_items": [
                {
                    "delivery_id": "delivery-candidate-data",
                    "source_item_id": "candidate-shortlist",
                    "source_item_type": "candidate_shortlist",
                    "title": "Candidate shortlist with personal data",
                    "manual_delivery_status": "ready_for_manual_delivery",
                    "candidate_personal_data_included": True,
                    "gareth_approval_required": True,
                }
            ],
            "blocked_delivery_items": [],
        }
        consent_engine = {**data["candidate_consent_management_engine"], "active_candidate_consents": []}
        engine = build_launch_compliance_validation_engine(
            manual_engine,
            data["client_terms_drafting_engine"],
            data["invoice_drafting_engine"],
            consent_engine,
            data["compliance_core"],
        )

        blocked = engine["compliance_blocked_items"][0]
        self.assertIn("candidate_consent_status", blocked["missing_compliance_checks"])
        self.assertEqual(blocked["compliance_recommendation"], "blocked_missing_consent")

    def test_launch_compliance_missing_client_terms_blocks_readiness(self):
        data = get_glirn_dashboard_data()
        terms_engine = {**data["client_terms_drafting_engine"], "client_terms_drafts": []}
        manual_engine = {
            "delivery_ready_items": [
                {
                    "delivery_id": "delivery-ready-no-terms",
                    "source_item_id": "ready-deliverable",
                    "source_item_type": "client_deliverable",
                    "title": "Ready deliverable without terms",
                    "manual_delivery_status": "ready_for_manual_delivery",
                    "candidate_personal_data_included": False,
                    "gareth_approval_required": True,
                }
            ],
            "blocked_delivery_items": [],
        }
        engine = build_launch_compliance_validation_engine(
            manual_engine,
            terms_engine,
            data["invoice_drafting_engine"],
            data["candidate_consent_management_engine"],
            data["compliance_core"],
        )

        blocked = engine["compliance_blocked_items"][0]
        self.assertIn("client_terms_status", blocked["missing_compliance_checks"])
        self.assertEqual(blocked["compliance_recommendation"], "blocked_missing_terms")

    def test_launch_compliance_missing_audit_trail_blocks_readiness(self):
        engine = build_launch_compliance_validation_engine(
            {"delivery_ready_items": [], "blocked_delivery_items": []},
            {"client_terms_drafts": []},
            {"invoice_drafts": []},
            {"active_candidate_consents": [], "expired_candidate_consents": []},
            {"compliance_alerts": [], "jurisdiction_profiles": []},
        )

        blocked = engine["compliance_blocked_items"][0]
        self.assertIn("audit_trail_present", blocked["missing_compliance_checks"])
        self.assertEqual(blocked["compliance_recommendation"], "blocked_missing_audit")

    def test_launch_compliance_missing_approval_blocks_readiness(self):
        data = get_glirn_dashboard_data()
        manual_engine = {
            "delivery_ready_items": [],
            "blocked_delivery_items": [
                {
                    "delivery_id": "delivery-not-approved",
                    "source_item_id": "draft-deliverable",
                    "source_item_type": "client_deliverable",
                    "title": "Unapproved deliverable",
                    "manual_delivery_status": "blocked",
                    "candidate_personal_data_included": False,
                    "gareth_approval_required": True,
                }
            ],
        }
        engine = build_launch_compliance_validation_engine(
            manual_engine,
            data["client_terms_drafting_engine"],
            data["invoice_drafting_engine"],
            data["candidate_consent_management_engine"],
            data["compliance_core"],
        )

        blocked = engine["compliance_blocked_items"][0]
        self.assertIn("deliverable_approval_status", blocked["missing_compliance_checks"])
        self.assertEqual(blocked["compliance_recommendation"], "blocked_missing_approval")

    def test_launch_compliance_recommendation_and_risk_level_calculated(self):
        data = get_glirn_dashboard_data()
        engine = data["launch_compliance_validation_engine"]

        self.assertIn(engine["compliance_recommendation"], {
            "approve_for_human_use",
            "monitor",
            "blocked_missing_consent",
            "blocked_missing_terms",
            "blocked_missing_audit",
            "blocked_missing_jurisdiction",
            "blocked_missing_approval",
            "blocked_high_risk",
        })
        self.assertIn(engine["compliance_risk_level"], {"low_risk", "moderate_risk", "high_risk", "blocked"})

    def test_dashboard_includes_launch_compliance_validation_engine(self):
        data = get_glirn_dashboard_data()

        self.assertIn("launch_compliance_validation_engine", data)
        self.assertIn("compliance_ready_items", data)
        self.assertIn("compliance_blocked_items", data)
        self.assertIn("compliance_validation_status", data)
        self.assertEqual(data["launch_compliance_validation_engine"]["status"], "Launch Compliance Validation Engine Active")
        self.assertIn("launch_compliance_validation_engine_status", data["summary"])

    def test_first_prospect_rankings_generated(self):
        data = get_glirn_dashboard_data()
        engine = build_first_prospect_selection_engine(
            data["launch_readiness_command_centre"],
            data["launch_compliance_validation_engine"],
        )

        self.assertEqual(engine["engine"], "first_prospect_selection_engine")
        self.assertEqual(engine["status"], "First Prospect Selection Engine Active")
        self.assertEqual(len(engine["prospect_profiles"]), 8)
        self.assertEqual(len(engine["prospect_rankings"]), 8)
        self.assertFalse(engine["outreach_enabled"])

    def test_first_prospect_scoring_calculated(self):
        data = get_glirn_dashboard_data()
        top = data["first_prospect_selection_engine"]["prospect_rankings"][0]

        self.assertIn("revenue_potential_score", top)
        self.assertIn("ease_of_acquisition_score", top)
        self.assertIn("launch_readiness_score", top)
        self.assertIn("market_demand_score", top)
        self.assertIn("compliance_complexity_score", top)
        self.assertGreater(top["overall_prospect_score"], 0)
        self.assertLessEqual(top["overall_prospect_score"], 100)

    def test_first_prospect_recommended_prospect_generated(self):
        data = get_glirn_dashboard_data()
        engine = data["first_prospect_selection_engine"]

        self.assertIn("recommended_first_prospect", engine)
        self.assertEqual(
            engine["recommended_first_prospect"]["prospect_id"],
            engine["prospect_rankings"][0]["prospect_id"],
        )
        self.assertIn("Dave", "Dave")
        self.assertIn("dave_recommends_first", engine)

    def test_first_prospect_highest_revenue_identified(self):
        data = get_glirn_dashboard_data()
        highest = data["first_prospect_selection_engine"]["highest_revenue_prospect"]

        self.assertEqual(highest["category"], "Corporate & M&A Firms")
        self.assertEqual(highest["revenue_potential_score"], 92)

    def test_first_prospect_fastest_revenue_identified(self):
        data = get_glirn_dashboard_data()
        fastest = data["first_prospect_selection_engine"]["fastest_revenue_prospect"]

        self.assertIn(fastest["category"], {
            "Boutique Technology & AI Law Firms",
            "Legal Technology Companies",
        })
        self.assertGreaterEqual(
            fastest["ease_of_acquisition_score"] + fastest["launch_readiness_score"],
            168,
        )

    def test_dashboard_includes_first_prospect_selection_engine(self):
        data = get_glirn_dashboard_data()

        self.assertIn("first_prospect_selection_engine", data)
        self.assertIn("prospect_rankings", data)
        self.assertIn("recommended_first_prospect", data)
        self.assertIn("highest_revenue_prospect", data)
        self.assertIn("fastest_revenue_prospect", data)
        self.assertEqual(data["first_prospect_selection_engine"]["status"], "First Prospect Selection Engine Active")
        self.assertIn("first_prospect_selection_engine_status", data["summary"])

    def test_first_client_dry_run_executes_successfully(self):
        data = get_glirn_dashboard_data()
        dry_run = build_first_client_dry_run(
            data["first_prospect_selection_engine"],
            data["intelligence_review_engine"],
            data["deliverable_factory"],
            data["client_terms_drafting_engine"],
            data["invoice_drafting_engine"],
            data["candidate_consent_management_engine"],
            data["manual_delivery_control_engine"],
            data["launch_compliance_validation_engine"],
        )

        self.assertEqual(dry_run["engine"], "first_client_dry_run")
        self.assertEqual(dry_run["dry_run_status"], "completed_pending_gareth_approval")
        self.assertEqual(dry_run["approval_readiness_status"], "ready_for_gareth_approval")
        self.assertFalse(dry_run["outreach_enabled"])
        self.assertFalse(dry_run["external_integrations_enabled"])

    def test_first_client_dry_run_intelligence_review_generated(self):
        data = get_glirn_dashboard_data()
        artifact = data["first_client_dry_run"]["dry_run_artifacts"]["intelligence_review"]

        self.assertTrue(artifact["generated"])
        self.assertEqual(artifact["artifact_id"], "glirn-review-001")

    def test_first_client_dry_run_deliverable_generated(self):
        data = get_glirn_dashboard_data()
        artifact = data["first_client_dry_run"]["dry_run_artifacts"]["client_deliverable"]

        self.assertTrue(artifact["generated"])
        self.assertIsNotNone(artifact["artifact_id"])

    def test_first_client_dry_run_terms_generated(self):
        data = get_glirn_dashboard_data()
        artifact = data["first_client_dry_run"]["dry_run_artifacts"]["client_terms_draft"]

        self.assertTrue(artifact["generated"])
        self.assertIsNotNone(artifact["artifact_id"])

    def test_first_client_dry_run_invoice_generated(self):
        data = get_glirn_dashboard_data()
        artifact = data["first_client_dry_run"]["dry_run_artifacts"]["invoice_draft"]

        self.assertTrue(artifact["generated"])
        self.assertIsNotNone(artifact["artifact_id"])

    def test_first_client_dry_run_consent_validation_executed(self):
        data = get_glirn_dashboard_data()
        artifact = data["first_client_dry_run"]["dry_run_artifacts"]["candidate_consent_validation"]

        self.assertTrue(artifact["executed"])
        self.assertIn("status", artifact)

    def test_first_client_dry_run_delivery_pack_generated(self):
        data = get_glirn_dashboard_data()
        artifact = data["first_client_dry_run"]["dry_run_artifacts"]["manual_delivery_pack"]

        self.assertTrue(artifact["generated"])
        self.assertIsNotNone(artifact["artifact_id"])

    def test_first_client_dry_run_compliance_validation_executed(self):
        data = get_glirn_dashboard_data()
        artifact = data["first_client_dry_run"]["dry_run_artifacts"]["launch_compliance_validation"]

        self.assertTrue(artifact["executed"])
        self.assertIsNotNone(artifact["artifact_id"])

    def test_first_client_dry_run_approval_package_created(self):
        data = get_glirn_dashboard_data()
        package = data["first_client_dry_run"]["gareth_approval_package"]

        self.assertEqual(package["package_id"], "glirn-first-client-dry-run-package-001")
        self.assertTrue(package["gareth_approval_required"])
        self.assertFalse(package["external_action_enabled"])

    def test_first_client_dry_run_readiness_score_calculated(self):
        data = get_glirn_dashboard_data()

        self.assertEqual(data["first_client_dry_run"]["dry_run_readiness_score"], 100)
        self.assertEqual(data["dry_run_readiness_score"], 100)

    def test_first_client_dry_run_blockers_reported_correctly(self):
        data = get_glirn_dashboard_data()

        self.assertEqual(data["first_client_dry_run"]["dry_run_blockers"], [])
        self.assertIsInstance(data["first_client_dry_run"]["dry_run_warnings"], list)

    def test_dashboard_includes_first_client_dry_run(self):
        data = get_glirn_dashboard_data()

        self.assertIn("first_client_dry_run", data)
        self.assertIn("dry_run_status", data)
        self.assertIn("dry_run_readiness_score", data)
        self.assertIn("latest_dry_run_report", data)
        self.assertIn("dry_run_blockers", data)
        self.assertIn("dry_run_warnings", data)
        self.assertIn("first_client_dry_run_status", data["summary"])

    def test_autonomous_internal_operations_cycle_runs(self):
        data = get_glirn_dashboard_data()
        orchestrator = build_autonomous_internal_operations_orchestrator(
            data["legal_opportunity_radar"],
            data["first_prospect_selection_engine"],
            data["revenue_command_centre"],
            data["intelligence_review_engine"],
            data["deliverable_factory"],
            data["client_terms_drafting_engine"],
            data["invoice_drafting_engine"],
            data["candidate_consent_management_engine"],
            data["launch_compliance_validation_engine"],
            data["manual_delivery_control_engine"],
            data["first_client_dry_run"],
        )

        self.assertEqual(orchestrator["engine"], "autonomous_internal_operations_orchestrator")
        self.assertEqual(orchestrator["autonomous_cycle_status"], "completed_pending_gareth_final_decision")
        self.assertTrue(orchestrator["analysis_enabled"])
        self.assertTrue(orchestrator["validation_enabled"])

    def test_autonomous_final_approval_package_generated(self):
        data = get_glirn_dashboard_data()
        package = data["autonomous_internal_operations_orchestrator"]["final_gareth_approval_packages"][0]

        self.assertEqual(package["package_id"], "glirn-autonomous-final-package-001")
        self.assertTrue(package["gareth_final_decision_required"])
        self.assertEqual(package["final_recommendation"], "approve")

    def test_autonomous_package_includes_opportunity_prospect_and_revenue_data(self):
        data = get_glirn_dashboard_data()
        package = data["autonomous_internal_operations_orchestrator"]["final_gareth_approval_packages"][0]

        self.assertIn("top_opportunity", package)
        self.assertIn("recommended_prospect_profile", package)
        self.assertIn("expected_revenue", package)
        self.assertIn("revenue_route", package)

    def test_autonomous_package_includes_artifact_statuses(self):
        data = get_glirn_dashboard_data()
        package = data["autonomous_internal_operations_orchestrator"]["final_gareth_approval_packages"][0]

        self.assertIn("intelligence_review_status", package)
        self.assertIn("deliverable_status", package)
        self.assertIn("terms_status", package)
        self.assertIn("invoice_status", package)

    def test_autonomous_package_includes_compliance_and_consent_statuses(self):
        data = get_glirn_dashboard_data()
        package = data["autonomous_internal_operations_orchestrator"]["final_gareth_approval_packages"][0]

        self.assertIn("consent_status", package)
        self.assertIn("compliance_status", package)
        self.assertIn("delivery_pack_status", package)
        self.assertIn("dry_run_status", package)

    def test_autonomous_blockers_and_warnings_included(self):
        data = get_glirn_dashboard_data()
        orchestrator = data["autonomous_internal_operations_orchestrator"]

        self.assertIn("autonomous_blockers", orchestrator)
        self.assertIn("autonomous_warnings", orchestrator)
        self.assertIsInstance(orchestrator["autonomous_warnings"], list)

    def test_autonomous_no_external_action_allowed(self):
        data = get_glirn_dashboard_data()
        orchestrator = data["autonomous_internal_operations_orchestrator"]

        self.assertFalse(orchestrator["client_contact_enabled"])
        self.assertFalse(orchestrator["candidate_contact_enabled"])
        self.assertFalse(orchestrator["deliverable_sending_enabled"])
        self.assertFalse(orchestrator["invoice_sending_enabled"])
        self.assertFalse(orchestrator["payment_collection_enabled"])
        self.assertFalse(orchestrator["external_integrations_enabled"])

    def test_dashboard_includes_autonomous_internal_operations_orchestrator(self):
        data = get_glirn_dashboard_data()

        self.assertIn("autonomous_internal_operations_orchestrator", data)
        self.assertIn("autonomous_cycle_status", data)
        self.assertIn("final_gareth_approval_packages", data)
        self.assertIn("autonomous_recommendation_queue", data)
        self.assertEqual(
            data["autonomous_internal_operations_orchestrator"]["status"],
            "Autonomous Internal Operations Cycle Complete",
        )
        self.assertIn("autonomous_internal_operations_orchestrator_status", data["summary"])

    def test_website_lead_intake_engine_records_and_classifies_lead(self):
        data = get_glirn_dashboard_data(public_leads=[
            {
                "name": "Alex Client",
                "organisation": "Boutique AI Law LLP",
                "email": "alex@example.com",
                "country": "England",
                "legal_sector": "Technology & AI Law",
                "hiring_need": "Partner search",
                "seniority_level": "Partner",
                "message": "We may need senior hiring support.",
                "consent": True,
            }
        ])
        engine = data["website_lead_intake_engine"]
        lead = engine["public_leads"][0]

        self.assertEqual(engine["engine"], "website_lead_intake_engine")
        self.assertEqual(lead["prospect_type"], "Boutique Technology & AI Law Firms")
        self.assertEqual(lead["lead_type"], "executive_search_lead")
        self.assertEqual(lead["lead_route"], "executive_search_review")
        self.assertEqual(lead["lead_qualification_status"], "qualified_for_gareth_review")

    def test_website_lead_revenue_potential_calculated(self):
        engine = build_website_lead_intake_engine([
            {
                "organisation": "Corporate AI Firm",
                "legal_sector": "Technology & AI Law",
                "hiring_need": "Executive search for partner",
                "seniority_level": "Partner",
                "consent": True,
            }
        ])

        self.assertGreaterEqual(engine["public_leads"][0]["lead_revenue_potential"], 90)

    def test_website_lead_approval_package_created_and_no_contact(self):
        data = get_glirn_dashboard_data(public_leads=[
            {
                "organisation": "Boutique AI Law LLP",
                "legal_sector": "Technology & AI Law",
                "hiring_need": "Partner search",
                "seniority_level": "Partner",
                "consent": True,
            }
        ])
        engine = data["website_lead_intake_engine"]

        self.assertEqual(engine["gareth_approval_package"]["approval_status"], "ready_for_gareth_review")
        self.assertFalse(engine["automatic_email_enabled"])
        self.assertFalse(engine["client_contact_enabled"])
        self.assertFalse(engine["candidate_contact_enabled"])
        self.assertFalse(engine["external_integrations_enabled"])

    def test_dashboard_includes_website_lead_intake_engine(self):
        data = get_glirn_dashboard_data()

        self.assertIn("website_lead_intake_engine", data)
        self.assertIn("public_leads", data)
        self.assertIn("qualified_public_leads", data)
        self.assertIn("pending_public_lead_approvals", data)
        self.assertIn("latest_public_lead_recommendation", data)
        self.assertIn("website_lead_intake_engine_status", data["summary"])

    def test_public_client_lead_routed_correctly(self):
        engine = build_website_lead_intake_engine([
            {
                "inquiry_type": "In-House Legal Team",
                "organisation": "Growth Legal Team",
                "legal_sector": "Commercial Law",
                "hiring_need": "Need to hire a senior lawyer",
                "seniority_level": "Senior Associate",
                "consent": True,
            }
        ])

        lead = engine["public_leads"][0]
        self.assertEqual(lead["lead_type"], "client_lead")
        self.assertEqual(lead["lead_route"], "client_hiring_review")

    def test_public_candidate_lead_routed_correctly(self):
        engine = build_website_lead_intake_engine([
            {
                "inquiry_type": "Candidate",
                "organisation": "Individual",
                "legal_sector": "Technology & AI Law",
                "hiring_need": "Confidential career conversation",
                "seniority_level": "Candidate",
                "consent": True,
            }
        ])

        lead = engine["public_leads"][0]
        self.assertEqual(lead["lead_type"], "candidate_lead")
        self.assertEqual(lead["lead_route"], "candidate_confidential_review")

    def test_senior_and_future_legal_candidate_routes_are_distinct(self):
        engine = build_website_lead_intake_engine([
            {
                "inquiry_type": "Senior Legal Professional Career Discussion",
                "organisation": "Candidate Confidential",
                "legal_sector": "Corporate Law",
                "hiring_need": "Confidential career discussion",
                "seniority_level": "General Counsel",
                "career_stage": "General Counsel / Chief Legal Officer",
                "consent": True,
            },
            {
                "inquiry_type": "Newly Qualified / Future Legal Leader Interest",
                "organisation": "Candidate Confidential",
                "legal_sector": "Technology & AI Law",
                "hiring_need": "Future legal career discussion",
                "seniority_level": "Newly Qualified Solicitor",
                "career_stage": "Newly Qualified Solicitor",
                "consent": True,
            },
        ])

        senior, future = engine["public_leads"]
        self.assertEqual(senior["lead_type"], "senior_legal_candidate_lead")
        self.assertEqual(senior["lead_route"], "senior_legal_candidate_confidential_review")
        self.assertEqual(future["lead_type"], "future_legal_leader_candidate_lead")
        self.assertEqual(future["lead_route"], "future_legal_leader_confidential_review")

    def test_employer_enquiry_text_does_not_trigger_nq_candidate_route(self):
        engine = build_website_lead_intake_engine([{
            "inquiry_type": "Law Firm / Legal Team Enquiry",
            "organisation": "Employer Legal LLP",
            "legal_sector": "Corporate Law",
            "hiring_need": "Confidential hiring enquiry",
            "seniority_level": "Partner",
            "consent": True,
        }])

        lead = engine["public_leads"][0]
        self.assertNotEqual(lead["lead_type"], "future_legal_leader_candidate_lead")
        self.assertNotEqual(lead["lead_route"], "future_legal_leader_confidential_review")

    def test_candidate_routes_are_zero_revenue_consent_gated_command_opportunities(self):
        data = get_glirn_dashboard_data(public_leads=[
            {
                "lead_id": "senior-candidate-1",
                "name": "Senior Candidate",
                "inquiry_type": "Senior Legal Professional Career Discussion",
                "organisation": "Candidate Confidential",
                "email": "senior@example.com",
                "country": "England",
                "legal_sector": "Corporate Law",
                "practice_area": "Corporate Law",
                "jurisdiction": "England & Wales",
                "hiring_need": "Confidential career discussion",
                "seniority_level": "General Counsel",
                "career_stage": "General Counsel / Chief Legal Officer",
                "timescale": "Exploratory",
                "message": "Confidential discussion",
                "consent": True,
            },
            {
                "lead_id": "future-candidate-1",
                "name": "Future Candidate",
                "inquiry_type": "Newly Qualified / Future Legal Leader Interest",
                "organisation": "Candidate Confidential",
                "email": "future@example.com",
                "country": "England",
                "legal_sector": "Technology & AI Law",
                "practice_area": "Technology & AI Law",
                "jurisdiction": "England & Wales",
                "hiring_need": "Future legal career discussion",
                "seniority_level": "Newly Qualified Solicitor",
                "career_stage": "Newly Qualified Solicitor",
                "timescale": "Exploratory",
                "message": "Confidential discussion",
                "consent": True,
            },
        ])
        packages = data["revenue_approval_packages"]
        by_type = {item["lead_type"]: item for item in packages}
        command_items = {
            item["opportunity_type"]: item
            for item in data["gareth_command_centre"]["revenue_opportunities"]
            if item.get("opportunity_type") != "revenue_opportunity"
        }

        self.assertEqual(by_type["senior_legal_candidate_lead"]["estimated_revenue_opportunity"], 0)
        self.assertEqual(by_type["future_legal_leader_candidate_lead"]["estimated_revenue_opportunity"], 0)
        self.assertIn("candidate_pipeline_opportunity", command_items)
        self.assertIn("relationship_building_opportunity", command_items)
        self.assertFalse(data["website_lead_intake_engine"]["candidate_contact_enabled"])
        self.assertFalse(data["website_lead_intake_engine"]["automatic_email_enabled"])
        self.assertFalse(data["gareth_command_centre"]["automatic_linkedin_messaging_enabled"])
        self.assertFalse(data["gareth_command_centre"]["automatic_introductions_enabled"])
        self.assertFalse(data["gareth_command_centre"]["candidate_information_sharing_enabled"])

    def test_public_executive_search_lead_routed_correctly(self):
        engine = build_website_lead_intake_engine([
            {
                "inquiry_type": "Law Firm",
                "organisation": "Boutique AI Law LLP",
                "legal_sector": "Technology & AI Law",
                "hiring_need": "Partner search",
                "seniority_level": "Partner",
                "consent": True,
            }
        ])

        lead = engine["public_leads"][0]
        self.assertEqual(lead["lead_type"], "executive_search_lead")
        self.assertEqual(lead["lead_route"], "executive_search_review")

    def test_revenue_approval_package_generated_for_each_lead_route(self):
        lead_engine = build_website_lead_intake_engine([
            {"inquiry_type": "Law Firm", "organisation": "Client LLP", "legal_sector": "Commercial Law", "hiring_need": "Need to hire", "seniority_level": "Senior Associate", "timescale": "1-3 months", "consent": True},
            {"inquiry_type": "Candidate", "organisation": "Individual", "legal_sector": "Technology & AI Law", "hiring_need": "Career conversation", "seniority_level": "Candidate", "timescale": "Exploratory", "consent": True},
            {"inquiry_type": "Law Firm", "organisation": "Review LLP", "legal_sector": "Technology & AI Law", "hiring_need": "Intelligence review", "seniority_level": "Partner", "timescale": "Immediate", "consent": True},
            {"inquiry_type": "Law Firm", "organisation": "Executive LLP", "legal_sector": "Technology & AI Law", "hiring_need": "Partner search", "seniority_level": "Partner", "timescale": "Immediate", "consent": True},
        ])
        revenue_engine = build_revenue_approval_engine(lead_engine)
        packages = revenue_engine["revenue_approval_packages"]

        self.assertEqual(len(packages), 4)
        self.assertEqual({item["gareth_approval_status"] for item in packages}, {"awaiting_review"})
        self.assertIn("GBP 500 Senior Legal Hiring Intelligence Review", {item["suggested_glirn_service"] for item in packages})
        self.assertIn("Executive Search", {item["suggested_glirn_service"] for item in packages})
        self.assertIn("Candidate Introduction", {item["suggested_glirn_service"] for item in packages})

    def test_revenue_approval_estimated_revenue_assigned_correctly(self):
        lead_engine = build_website_lead_intake_engine([
            {"inquiry_type": "Law Firm", "organisation": "Review LLP", "legal_sector": "Technology & AI Law", "hiring_need": "Intelligence review", "seniority_level": "Partner", "timescale": "Immediate", "consent": True},
            {"inquiry_type": "Law Firm", "organisation": "Executive LLP", "legal_sector": "Technology & AI Law", "hiring_need": "Partner search", "seniority_level": "Partner", "timescale": "Immediate", "consent": True},
        ])
        packages = build_revenue_approval_engine(lead_engine)["revenue_approval_packages"]

        self.assertEqual(packages[0]["estimated_revenue_opportunity"], 500)
        self.assertEqual(packages[1]["estimated_revenue_opportunity"], 25000)

    def test_revenue_approval_no_contact_or_money_movement(self):
        data = get_glirn_dashboard_data(public_leads=[
            {"inquiry_type": "Law Firm", "organisation": "Executive LLP", "legal_sector": "Technology & AI Law", "hiring_need": "Partner search", "seniority_level": "Partner", "timescale": "Immediate", "consent": True}
        ])
        engine = data["revenue_approval_engine"]
        package = engine["revenue_approval_packages"][0]

        self.assertEqual(package["gareth_approval_status"], "awaiting_review")
        self.assertFalse(package["automatic_client_contact_enabled"])
        self.assertFalse(package["automatic_invoice_sending_enabled"])
        self.assertFalse(package["money_movement_enabled"])
        self.assertFalse(engine["payment_collection_enabled"])

    def test_dashboard_includes_revenue_approval_engine(self):
        data = get_glirn_dashboard_data()

        self.assertIn("revenue_approval_engine", data)
        self.assertIn("revenue_approval_packages", data)
        self.assertIn("ready_for_gareth_approval", data)
        self.assertIn("latest_revenue_opportunity", data)
        self.assertIn("revenue_approval_engine_status", data["summary"])

    def test_client_response_draft_generated_after_revenue_package(self):
        lead_engine = build_website_lead_intake_engine([
            {"inquiry_type": "Law Firm", "organisation": "Executive LLP", "legal_sector": "Technology & AI Law", "hiring_need": "Partner search", "seniority_level": "Partner", "timescale": "Immediate", "consent": True}
        ])
        revenue_engine = build_revenue_approval_engine(lead_engine)
        draft_engine = build_client_response_draft_engine(revenue_engine)
        draft = draft_engine["client_response_drafts"][0]

        self.assertEqual(draft_engine["status"], "Client Response Draft Ready")
        self.assertEqual(draft["draft_status"], "awaiting_gareth_approval")
        self.assertEqual(draft["draft_ready_status"], "draft_ready")
        self.assertIn("Thank you for your enquiry to GLIRN", draft["draft_body"])
        self.assertTrue(draft["gareth_approval_required"])

    def test_client_response_draft_per_service_type(self):
        lead_engine = build_website_lead_intake_engine([
            {"inquiry_type": "Law Firm", "organisation": "Review LLP", "legal_sector": "Technology & AI Law", "hiring_need": "Intelligence review", "seniority_level": "Partner", "timescale": "Immediate", "consent": True},
            {"inquiry_type": "Law Firm", "organisation": "Executive LLP", "legal_sector": "Technology & AI Law", "hiring_need": "Partner search", "seniority_level": "Partner", "timescale": "Immediate", "consent": True},
            {"inquiry_type": "Candidate", "organisation": "Individual", "legal_sector": "Technology & AI Law", "hiring_need": "Career conversation", "seniority_level": "Candidate", "timescale": "Exploratory", "consent": True},
            {"inquiry_type": "Other", "organisation": "General Enquiry", "legal_sector": "Commercial Law", "hiring_need": "Need guidance", "seniority_level": "Other", "timescale": "Exploratory", "consent": True},
        ])
        draft_engine = build_client_response_draft_engine(
            build_revenue_approval_engine(lead_engine)
        )
        drafts_by_service = {
            draft["suggested_service"]: draft["draft_body"]
            for draft in draft_engine["client_response_drafts"]
        }

        self.assertIn("GBP 500 GLIRN Senior Legal Hiring Intelligence Review", drafts_by_service["GBP 500 Senior Legal Hiring Intelligence Review"])
        self.assertIn("executive legal search support", drafts_by_service["Executive Search"])
        self.assertIn("confidential candidate introduction route", drafts_by_service["Candidate Introduction"])
        self.assertIn("general advisory follow-up", drafts_by_service["General Advisory Follow-Up"])

    def test_client_response_draft_no_automatic_sending_or_contact(self):
        data = get_glirn_dashboard_data(public_leads=[
            {"inquiry_type": "Law Firm", "organisation": "Executive LLP", "legal_sector": "Technology & AI Law", "hiring_need": "Partner search", "seniority_level": "Partner", "timescale": "Immediate", "consent": True}
        ])
        engine = data["client_response_draft_engine"]
        draft = engine["client_response_drafts"][0]

        self.assertFalse(draft["automatic_sending_enabled"])
        self.assertFalse(draft["automatic_email_enabled"])
        self.assertFalse(draft["client_contact_enabled"])
        self.assertFalse(engine["client_contact_enabled"])
        self.assertTrue(draft["local_draft_only"])

    def test_dashboard_includes_client_response_draft_engine(self):
        data = get_glirn_dashboard_data()

        self.assertIn("client_response_draft_engine", data)
        self.assertIn("client_response_drafts", data)
        self.assertIn("client_response_draft_ready", data)
        self.assertIn("pending_client_response_approvals", data)
        self.assertIn("latest_client_response_draft", data)
        self.assertIn("client_response_draft_engine_status", data["summary"])

    def test_fee_proposal_generated_for_each_service_type(self):
        lead_engine = build_website_lead_intake_engine([
            {"inquiry_type": "Law Firm", "organisation": "Review LLP", "legal_sector": "Technology & AI Law", "hiring_need": "Intelligence review", "seniority_level": "Partner", "timescale": "Immediate", "consent": True},
            {"inquiry_type": "Law Firm", "organisation": "Executive LLP", "legal_sector": "Technology & AI Law", "hiring_need": "Partner search", "seniority_level": "Partner", "timescale": "Immediate", "consent": True},
            {"inquiry_type": "Candidate", "organisation": "Individual", "legal_sector": "Technology & AI Law", "hiring_need": "Career conversation", "seniority_level": "Candidate", "timescale": "Exploratory", "consent": True},
            {"inquiry_type": "Other", "organisation": "General Enquiry", "legal_sector": "Commercial Law", "hiring_need": "Need guidance", "seniority_level": "Other", "timescale": "Exploratory", "consent": True},
        ])
        revenue_engine = build_revenue_approval_engine(lead_engine)
        response_engine = build_client_response_draft_engine(revenue_engine)
        fee_engine = build_fee_proposal_pack_engine(revenue_engine, response_engine)
        services = {
            pack["suggested_glirn_service"]: pack["fee_basis"]
            for pack in fee_engine["fee_proposal_packs"]
        }

        self.assertEqual(services["GBP 500 Senior Legal Hiring Intelligence Review"], "fixed fee")
        self.assertEqual(services["Executive Search"], "retained search fee")
        self.assertEqual(services["Candidate Introduction"], "success fee")
        self.assertEqual(services["General Advisory Follow-Up"], "advisory follow-up fee")

    def test_gbp_500_review_fee_proposal_uses_fixed_fee(self):
        lead_engine = build_website_lead_intake_engine([
            {"inquiry_type": "Law Firm", "organisation": "Review LLP", "legal_sector": "Technology & AI Law", "hiring_need": "Intelligence review", "seniority_level": "Partner", "timescale": "Immediate", "consent": True},
        ])
        revenue_engine = build_revenue_approval_engine(lead_engine)
        fee_engine = build_fee_proposal_pack_engine(
            revenue_engine,
            build_client_response_draft_engine(revenue_engine),
        )
        pack = fee_engine["fee_proposal_packs"][0]

        self.assertEqual(pack["suggested_glirn_service"], "GBP 500 Senior Legal Hiring Intelligence Review")
        self.assertEqual(pack["estimated_fee"], 500)
        self.assertEqual(pack["fee_basis"], "fixed fee")
        self.assertIn("GBP 500", pack["client_facing_proposal_draft"])

    def test_fee_proposal_status_defaults_to_awaiting_review(self):
        data = get_glirn_dashboard_data(public_leads=[
            {"inquiry_type": "Law Firm", "organisation": "Executive LLP", "legal_sector": "Technology & AI Law", "hiring_need": "Partner search", "seniority_level": "Partner", "timescale": "Immediate", "consent": True}
        ])
        pack = data["fee_proposal_pack_engine"]["fee_proposal_packs"][0]

        self.assertEqual(pack["proposal_status"], "awaiting_review")
        self.assertEqual(pack["gareth_approval_status"], "awaiting_review")
        self.assertTrue(pack["gareth_approval_required"])

    def test_fee_proposal_no_invoice_payment_or_contact(self):
        data = get_glirn_dashboard_data(public_leads=[
            {"inquiry_type": "Law Firm", "organisation": "Executive LLP", "legal_sector": "Technology & AI Law", "hiring_need": "Partner search", "seniority_level": "Partner", "timescale": "Immediate", "consent": True}
        ])
        engine = data["fee_proposal_pack_engine"]
        pack = engine["fee_proposal_packs"][0]

        self.assertFalse(pack["invoice_sent"])
        self.assertFalse(pack["payment_request_sent"])
        self.assertFalse(pack["money_movement_enabled"])
        self.assertFalse(pack["client_contact_enabled"])
        self.assertFalse(engine["external_integrations_enabled"])
        self.assertTrue(pack["local_proposal_only"])

    def test_dashboard_includes_fee_proposal_pack_engine(self):
        data = get_glirn_dashboard_data()

        self.assertIn("fee_proposal_pack_engine", data)
        self.assertIn("fee_proposal_packs", data)
        self.assertIn("fee_proposal_pack_ready", data)
        self.assertIn("pending_fee_proposal_approvals", data)
        self.assertIn("latest_fee_proposal_pack", data)
        self.assertIn("fee_proposal_pack_engine_status", data["summary"])

    def test_unified_final_approval_object_generated(self):
        lead_engine = build_website_lead_intake_engine([
            {"inquiry_type": "Law Firm", "organisation": "Executive LLP", "legal_sector": "Technology & AI Law", "hiring_need": "Partner search", "seniority_level": "Partner", "timescale": "Immediate", "consent": True}
        ])
        revenue_engine = build_revenue_approval_engine(lead_engine)
        response_engine = build_client_response_draft_engine(revenue_engine)
        fee_engine = build_fee_proposal_pack_engine(revenue_engine, response_engine)
        centre = build_final_approval_command_centre(revenue_engine, response_engine, fee_engine)
        approval = centre["final_approval_objects"][0]

        self.assertIn("revenue_approval_package", approval)
        self.assertIn("client_response_draft", approval)
        self.assertIn("fee_proposal_pack", approval)
        self.assertEqual(approval["suggested_service"], "Executive Search")
        self.assertEqual(approval["estimated_fee"], 25000)
        self.assertEqual(approval["final_approval_status"], "awaiting_gareth_decision")

    def test_final_approval_default_status_is_awaiting_gareth_decision(self):
        data = get_glirn_dashboard_data(public_leads=[
            {"inquiry_type": "Law Firm", "organisation": "Review LLP", "legal_sector": "Technology & AI Law", "hiring_need": "Intelligence review", "seniority_level": "Partner", "timescale": "Immediate", "consent": True}
        ])
        approval = data["final_approval_command_centre"]["final_approval_objects"][0]

        self.assertEqual(approval["final_approval_status"], "awaiting_gareth_decision")
        self.assertTrue(approval["gareth_final_decision_required"])

    def test_final_approval_actions_update_status_only(self):
        data = get_glirn_dashboard_data(public_leads=[
            {"inquiry_type": "Law Firm", "organisation": "Executive LLP", "legal_sector": "Technology & AI Law", "hiring_need": "Partner search", "seniority_level": "Partner", "timescale": "Immediate", "consent": True}
        ])
        approval = data["final_approval_command_centre"]["final_approval_objects"][0]

        approved = apply_final_approval_action(approval, "approve")
        rejected = apply_final_approval_action(approval, "reject")
        more_info = apply_final_approval_action(approval, "needs_more_information")

        self.assertEqual(approved["final_approval_status"], "approved_by_gareth")
        self.assertEqual(rejected["final_approval_status"], "rejected_by_gareth")
        self.assertEqual(more_info["final_approval_status"], "needs_more_information")
        self.assertFalse(approved["client_contact_enabled"])
        self.assertFalse(approved["invoice_sending_enabled"])
        self.assertFalse(approved["payment_request_enabled"])
        self.assertFalse(approved["money_movement_enabled"])

    def test_dashboard_includes_final_approval_command_centre(self):
        data = get_glirn_dashboard_data()

        self.assertIn("final_approval_command_centre", data)
        self.assertIn("final_approval_objects", data)
        self.assertIn("gareth_final_approval_required", data)
        self.assertIn("latest_final_approval_object", data)
        self.assertIn("final_approval_command_centre_status", data["summary"])

    def test_client_contact_blocked_before_gareth_approval(self):
        data = get_glirn_dashboard_data(public_leads=[
            {"name": "Alex Client", "email": "alex@example.com", "inquiry_type": "Law Firm", "organisation": "Executive LLP", "legal_sector": "Technology & AI Law", "hiring_need": "Partner search", "seniority_level": "Partner", "timescale": "Immediate", "consent": True}
        ])
        readiness = data["approved_client_contact_engine"]["client_contact_readiness"][0]

        self.assertEqual(readiness["contact_status"], "blocked_pending_gareth_approval")
        self.assertFalse(readiness["gareth_approval_gate"])
        self.assertFalse(readiness["real_email_sent"])
        self.assertFalse(readiness["client_contact_executed"])

    def test_client_contact_ready_only_after_gareth_approval(self):
        data = get_glirn_dashboard_data(public_leads=[
            {"name": "Alex Client", "email": "alex@example.com", "inquiry_type": "Law Firm", "organisation": "Executive LLP", "legal_sector": "Technology & AI Law", "hiring_need": "Partner search", "seniority_level": "Partner", "timescale": "Immediate", "consent": True}
        ])
        approval = data["final_approval_command_centre"]["final_approval_objects"][0]
        approved = apply_final_approval_action(approval, "approve")
        readiness = build_client_contact_readiness_object(approved)

        self.assertEqual(readiness["final_approval_status"], "approved_by_gareth")
        self.assertEqual(readiness["contact_status"], "ready_after_gareth_approval")
        self.assertTrue(readiness["gareth_approval_gate"])

    def test_client_contact_action_logs_local_only_after_approval(self):
        data = get_glirn_dashboard_data(public_leads=[
            {"name": "Alex Client", "email": "alex@example.com", "inquiry_type": "Law Firm", "organisation": "Executive LLP", "legal_sector": "Technology & AI Law", "hiring_need": "Partner search", "seniority_level": "Partner", "timescale": "Immediate", "consent": True}
        ])
        approval = data["final_approval_command_centre"]["final_approval_objects"][0]
        readiness = build_client_contact_readiness_object(
            apply_final_approval_action(approval, "approve")
        )
        result = apply_client_contact_action(readiness, "mark_approved_contact_ready")

        self.assertEqual(result["contact_status"], "contact_logged_local_only")
        self.assertFalse(result["real_email_sent"])
        self.assertFalse(result["client_contact_executed"])
        self.assertFalse(result["gmail_smtp_connected"])
        self.assertFalse(result["external_integrations_enabled"])

    def test_dashboard_includes_approved_client_contact_engine(self):
        data = get_glirn_dashboard_data()

        self.assertIn("approved_client_contact_engine", data)
        self.assertIn("client_contact_readiness", data)
        self.assertIn("blocked_client_contacts", data)
        self.assertIn("ready_client_contacts", data)
        self.assertIn("latest_client_contact_readiness", data)
        self.assertIn("approved_client_contact_engine_status", data["summary"])

    def test_email_draft_export_blocked_before_gareth_approval(self):
        data = get_glirn_dashboard_data(public_leads=[
            {"name": "Alex Client", "email": "alex@example.com", "inquiry_type": "Law Firm", "organisation": "Executive LLP", "legal_sector": "Technology & AI Law", "hiring_need": "Partner search", "seniority_level": "Partner", "timescale": "Immediate", "consent": True}
        ])
        export_item = data["email_draft_export_engine"]["email_draft_exports"][0]

        self.assertEqual(export_item["export_status"], "blocked_pending_gareth_approval")
        self.assertFalse(export_item["email_sent"])
        self.assertFalse(export_item["external_integrations_enabled"])

    def test_email_draft_export_ready_after_gareth_approval(self):
        data = get_glirn_dashboard_data(public_leads=[
            {"name": "Alex Client", "email": "alex@example.com", "inquiry_type": "Law Firm", "organisation": "Executive LLP", "legal_sector": "Technology & AI Law", "hiring_need": "Partner search", "seniority_level": "Partner", "timescale": "Immediate", "consent": True}
        ])
        approval = data["final_approval_command_centre"]["final_approval_objects"][0]
        approved = apply_final_approval_action(approval, "approve")
        export_item = build_email_draft_export_object(approved)

        self.assertEqual(export_item["export_status"], "draft_export_ready")
        self.assertEqual(export_item["to_email"], "alex@example.com")
        self.assertIn("GLIRN enquiry follow-up", export_item["subject"])

    def test_email_draft_export_action_marks_exported_local_only(self):
        data = get_glirn_dashboard_data(public_leads=[
            {"name": "Alex Client", "email": "alex@example.com", "inquiry_type": "Law Firm", "organisation": "Executive LLP", "legal_sector": "Technology & AI Law", "hiring_need": "Partner search", "seniority_level": "Partner", "timescale": "Immediate", "consent": True}
        ])
        approval = data["final_approval_command_centre"]["final_approval_objects"][0]
        export_item = build_email_draft_export_object(
            apply_final_approval_action(approval, "approve")
        )
        result = apply_email_draft_export_action(export_item, "export_approved_email_draft", "draft.txt")

        self.assertEqual(result["export_status"], "exported_local_only")
        self.assertEqual(result["local_file_path"], "draft.txt")
        self.assertFalse(result["email_sent"])
        self.assertFalse(result["gmail_smtp_connected"])
        self.assertFalse(result["external_integrations_enabled"])

    def test_dashboard_includes_email_draft_export_engine(self):
        data = get_glirn_dashboard_data()

        self.assertIn("email_draft_export_engine", data)
        self.assertIn("email_draft_exports", data)
        self.assertIn("blocked_email_draft_exports", data)
        self.assertIn("ready_email_draft_exports", data)
        self.assertIn("latest_email_draft_export", data)
        self.assertIn("email_draft_export_engine_status", data["summary"])

    def test_invoice_draft_export_blocked_before_gareth_approval(self):
        data = get_glirn_dashboard_data(public_leads=[
            {"name": "Alex Client", "email": "alex@example.com", "inquiry_type": "Law Firm", "organisation": "Executive LLP", "legal_sector": "Technology & AI Law", "hiring_need": "Partner search", "seniority_level": "Partner", "timescale": "Immediate", "consent": True}
        ])
        export_item = data["invoice_draft_export_engine"]["invoice_draft_exports"][0]

        self.assertEqual(export_item["invoice_status"], "blocked_pending_gareth_approval")
        self.assertFalse(export_item["invoice_sent"])
        self.assertFalse(export_item["payment_request_sent"])
        self.assertFalse(export_item["money_movement_enabled"])

    def test_invoice_draft_export_ready_after_gareth_approval(self):
        data = get_glirn_dashboard_data(public_leads=[
            {"name": "Alex Client", "email": "alex@example.com", "inquiry_type": "Law Firm", "organisation": "Executive LLP", "legal_sector": "Technology & AI Law", "hiring_need": "Partner search", "seniority_level": "Partner", "timescale": "Immediate", "consent": True}
        ])
        approval = data["final_approval_command_centre"]["final_approval_objects"][0]
        approved = apply_final_approval_action(approval, "approve")
        export_item = build_invoice_draft_export_object(approved)

        self.assertEqual(export_item["invoice_status"], "invoice_draft_ready")
        self.assertEqual(export_item["client_email"], "alex@example.com")
        self.assertEqual(export_item["suggested_glirn_service"], "Executive Search")

    def test_invoice_draft_export_action_marks_exported_local_only(self):
        data = get_glirn_dashboard_data(public_leads=[
            {"name": "Alex Client", "email": "alex@example.com", "inquiry_type": "Law Firm", "organisation": "Executive LLP", "legal_sector": "Technology & AI Law", "hiring_need": "Partner search", "seniority_level": "Partner", "timescale": "Immediate", "consent": True}
        ])
        approval = data["final_approval_command_centre"]["final_approval_objects"][0]
        export_item = build_invoice_draft_export_object(
            apply_final_approval_action(approval, "approve")
        )
        result = apply_invoice_draft_export_action(export_item, "export_approved_invoice_draft", "invoice.txt")

        self.assertEqual(result["invoice_status"], "exported_local_only")
        self.assertEqual(result["local_file_path"], "invoice.txt")
        self.assertFalse(result["invoice_sent"])
        self.assertFalse(result["payment_request_sent"])
        self.assertFalse(result["money_movement_enabled"])
        self.assertFalse(result["external_integrations_enabled"])

    def test_dashboard_includes_invoice_draft_export_engine(self):
        data = get_glirn_dashboard_data()

        self.assertIn("invoice_draft_export_engine", data)
        self.assertIn("invoice_draft_exports", data)
        self.assertIn("blocked_invoice_draft_exports", data)
        self.assertIn("ready_invoice_draft_exports", data)
        self.assertIn("latest_invoice_draft_export", data)
        self.assertIn("invoice_draft_export_engine_status", data["summary"])

    def test_deal_pack_export_blocked_before_gareth_approval(self):
        data = get_glirn_dashboard_data(public_leads=[
            {"name": "Alex Client", "email": "alex@example.com", "inquiry_type": "Law Firm", "organisation": "Executive LLP", "legal_sector": "Technology & AI Law", "hiring_need": "Partner search", "seniority_level": "Partner", "timescale": "Immediate", "consent": True}
        ])
        export_item = data["deal_pack_export_engine"]["deal_pack_exports"][0]

        self.assertEqual(export_item["deal_pack_status"], "blocked_pending_gareth_approval")
        self.assertFalse(export_item["client_contact_executed"])
        self.assertFalse(export_item["invoice_sent"])
        self.assertFalse(export_item["payment_request_sent"])
        self.assertFalse(export_item["money_movement_enabled"])

    def test_deal_pack_export_ready_after_gareth_approval(self):
        data = get_glirn_dashboard_data(public_leads=[
            {"name": "Alex Client", "email": "alex@example.com", "inquiry_type": "Law Firm", "organisation": "Executive LLP", "legal_sector": "Technology & AI Law", "hiring_need": "Partner search", "seniority_level": "Partner", "timescale": "Immediate", "consent": True}
        ])
        approval = data["final_approval_command_centre"]["final_approval_objects"][0]
        approved = apply_final_approval_action(approval, "approve")
        export_item = build_deal_pack_export_object(approved)

        self.assertEqual(export_item["deal_pack_status"], "deal_pack_ready")
        self.assertEqual(export_item["client_email"], "alex@example.com")
        self.assertEqual(export_item["suggested_glirn_service"], "Executive Search")
        self.assertIn("approved_client_response_draft", export_item)
        self.assertIn("fee_proposal_pack", export_item)
        self.assertIn("invoice_draft_summary", export_item)

    def test_deal_pack_export_action_marks_exported_local_only(self):
        data = get_glirn_dashboard_data(public_leads=[
            {"name": "Alex Client", "email": "alex@example.com", "inquiry_type": "Law Firm", "organisation": "Executive LLP", "legal_sector": "Technology & AI Law", "hiring_need": "Partner search", "seniority_level": "Partner", "timescale": "Immediate", "consent": True}
        ])
        approval = data["final_approval_command_centre"]["final_approval_objects"][0]
        export_item = build_deal_pack_export_object(
            apply_final_approval_action(approval, "approve")
        )
        result = apply_deal_pack_export_action(export_item, "export_approved_deal_pack", "deal-pack.txt")

        self.assertEqual(result["deal_pack_status"], "exported_local_only")
        self.assertEqual(result["local_file_path"], "deal-pack.txt")
        self.assertFalse(result["client_contact_executed"])
        self.assertFalse(result["invoice_sent"])
        self.assertFalse(result["payment_request_sent"])
        self.assertFalse(result["money_movement_enabled"])
        self.assertFalse(result["external_integrations_enabled"])

    def test_dashboard_includes_deal_pack_export_engine(self):
        data = get_glirn_dashboard_data()

        self.assertIn("deal_pack_export_engine", data)
        self.assertIn("deal_pack_exports", data)
        self.assertIn("blocked_deal_pack_exports", data)
        self.assertIn("ready_deal_pack_exports", data)
        self.assertIn("latest_deal_pack_export", data)
        self.assertIn("deal_pack_export_engine_status", data["summary"])

    def test_revenue_ledger_record_created(self):
        data = get_glirn_dashboard_data(public_leads=[
            {"name": "Alex Client", "email": "alex@example.com", "inquiry_type": "Law Firm", "organisation": "Executive LLP", "legal_sector": "Technology & AI Law", "hiring_need": "Partner search", "seniority_level": "Partner", "timescale": "Immediate", "consent": True}
        ])
        record = data["revenue_ledger_engine"]["revenue_ledger_records"][0]

        self.assertEqual(record["lead_client_name"], "Executive LLP")
        self.assertEqual(record["client_email"], "alex@example.com")
        self.assertEqual(record["suggested_glirn_service"], "Executive Search")
        self.assertEqual(record["actual_revenue_received"], 0)
        self.assertTrue(record["manual_payment_confirmation_required"])

    def test_revenue_ledger_stage_updates_locally_only(self):
        data = get_glirn_dashboard_data(public_leads=[
            {"name": "Alex Client", "email": "alex@example.com", "inquiry_type": "Law Firm", "organisation": "Executive LLP", "legal_sector": "Technology & AI Law", "hiring_need": "Partner search", "seniority_level": "Partner", "timescale": "Immediate", "consent": True}
        ])
        record = data["revenue_ledger_engine"]["revenue_ledger_records"][0]
        result = apply_revenue_ledger_action(record, "mark_payment_pending_manual")

        self.assertEqual(result["revenue_stage"], "payment_pending_manual")
        self.assertEqual(result["actual_revenue_received"], 0)
        self.assertTrue(result["manual_payment_confirmation_required"])
        self.assertFalse(result["payment_collection_enabled"])
        self.assertFalse(result["money_movement_enabled"])
        self.assertFalse(result["external_integrations_enabled"])

    def test_dashboard_includes_revenue_ledger_engine(self):
        data = get_glirn_dashboard_data()

        self.assertIn("revenue_ledger_engine", data)
        self.assertIn("revenue_ledger_records", data)
        self.assertIn("latest_revenue_ledger_record", data)
        self.assertIn("estimated_pipeline_value", data)
        self.assertIn("actual_revenue_recorded", data)
        self.assertIn("latest_revenue_stage", data)
        self.assertIn("revenue_ledger_engine_status", data["summary"])

    def test_gareth_command_centre_sorts_revenue_and_limits_recommendations(self):
        data = get_glirn_dashboard_data(public_leads=[
            {"lead_id": "lead-1", "name": "One", "organisation": "Review Firm", "email": "one@example.com", "inquiry_type": "Law Firm", "legal_sector": "Employment Law", "hiring_need": "Market review", "seniority_level": "Senior", "timescale": "3-6 months", "message": "Review", "consent": True},
            {"lead_id": "lead-2", "name": "Two", "organisation": "Search Firm", "email": "two@example.com", "inquiry_type": "Law Firm", "legal_sector": "Technology & AI Law", "hiring_need": "Partner search", "seniority_level": "Partner", "timescale": "Immediate", "message": "Search", "consent": True},
        ])
        command = data["gareth_command_centre"]
        fees = [item["estimated_fee"] for item in command["revenue_opportunities"]]

        self.assertEqual(fees, sorted(fees, reverse=True))
        self.assertLessEqual(len(command["dave_recommends"]), 3)
        self.assertEqual(command["default_view"], "gareth_command_centre")
        self.assertTrue(command["advanced_view_available"])

    def test_gareth_command_centre_preserves_safety_controls(self):
        data = get_glirn_dashboard_data()
        command = data["gareth_command_centre"]

        self.assertFalse(command["client_contact_enabled"])
        self.assertFalse(command["invoice_sending_enabled"])
        self.assertFalse(command["payment_collection_enabled"])
        self.assertFalse(command["money_movement_enabled"])
        self.assertFalse(command["external_integrations_enabled"])
        self.assertTrue(command["human_approval_mandatory"])

    def test_enquiry_notification_summary_tracks_failures_and_preserves_safeguards(self):
        summary = build_enquiry_notification_summary([
            {
                "notification_id": "notification-1",
                "delivery_status": "sent",
            },
            {
                "notification_id": "notification-2",
                "delivery_status": "delivery_failed",
                "manual_resend_available": True,
            },
        ], enquiry_count=2)

        self.assertEqual(summary["new_enquiry_count"], 2)
        self.assertEqual(summary["notification_count"], 2)
        self.assertEqual(summary["notifications_sent"], 1)
        self.assertEqual(summary["notification_failure_count"], 1)
        self.assertTrue(summary["manual_resend_available"])
        self.assertTrue(summary["human_review_mandatory"])
        self.assertFalse(summary["automatic_acceptance_enabled"])
        self.assertFalse(summary["automatic_payment_enabled"])
        self.assertFalse(summary["automatic_brief_generation_enabled"])
        self.assertFalse(summary["automatic_candidate_outreach_enabled"])
        self.assertFalse(summary["automatic_search_activity_enabled"])
        self.assertFalse(summary["automatic_delivery_enabled"])
        self.assertFalse(summary["external_integrations_enabled"])


if __name__ == "__main__":
    unittest.main()
