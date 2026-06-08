# GLIRN Architecture

## System Overview

Global Legal Intelligence & Recruitment Network is implemented as a module inside ArbitrageEngineV1. The system combines legal recruitment opportunity scoring, compliance controls, human approval, commercial revenue estimation, client acquisition, candidate discovery, and candidate-to-client matching.

The architecture is intentionally human-in-the-loop. GLIRN can rank and recommend, but it cannot perform outbound actions, introduce candidates, share candidate details, negotiate fees, or execute placements without Gareth Price approval.

## Core Modules

- Legal sector taxonomy: standard legal market sectors and practice areas.
- Opportunity scoring: expected fee value, placement probability, quality, compliance, urgency, time to revenue, and overall GLIRN score.
- Legal Opportunity Radar: identifies and ranks highest-fee legal recruitment opportunities.
- Human Approval Centre: central queue and lock status for Gareth approval.
- Compliance Core: consent, terms, jurisdiction, retention, deletion, and alert controls.
- Executive Search Engine: premium Partner, GC, CLO, Legal Director, and senior candidate workflows.
- Legal Intelligence Network: salary, market, practice area, jurisdiction, hiring trend, and competitor signals.
- Commercial Revenue Engine: fee calculators, invoice readiness, fee type classification, and commercial pipeline.
- Client Acquisition Engine: target client profiles, hiring likelihood, fee potential, and client readiness.
- Candidate Discovery Engine: candidate seniority, practice and jurisdiction fit, consent readiness, and placement value.
- Matching & Placement Engine: candidate-to-client compatibility, gates, match revenue score, and placement probability.

## Data Models

Core GLIRN models are defined in `glirn.py`:

- `Candidate`
- `ClientFirm`
- `LegalPracticeArea`
- `Jurisdiction`
- `RecruitmentOpportunity`
- `CandidateConsentRecord`
- `ClientFeeAgreement`
- `HumanApprovalDecision`
- `ComplianceAlert`

Supporting score and record fields include:

- `expected_fee_value`
- `placement_probability`
- `client_quality`
- `candidate_quality`
- `compliance_readiness`
- `urgency_score`
- `time_to_revenue`
- `overall_glirn_score`
- `candidate_priority_score`
- `client_opportunity_score`
- `match_revenue_score`
- `placement_probability_score`

## Dashboard Structure

`GET /glirn/dashboard` returns the GLIRN dashboard payload.

Main sections:

- `legal_sectors`
- `opportunities`
- `legal_opportunity_radar`
- `approval_centre`
- `compliance_core`
- `executive_search`
- `intelligence_network`
- `commercial_revenue_engine`
- `client_acquisition_engine`
- `candidate_discovery_engine`
- `matching_engine`
- `summary`
- `capital_execution`

The `/ui` dashboard renders GLIRN panels using helper functions in `app.py`.

## API Structure

Read endpoint:

- `GET /glirn/dashboard`

Action and approval endpoints:

- `POST /glirn/opportunities/{opportunity_id}/request-approval`
- `POST /glirn/approvals/{approval_id}/{decision}`
- `POST /glirn/compliance/deletion-request`
- `POST /glirn/executive-search/actions`
- `POST /glirn/intelligence/report-requests`
- `POST /glirn/commercial/actions`
- `POST /glirn/client-acquisition/actions`
- `POST /glirn/candidate-discovery/actions`
- `POST /glirn/matching/actions`

Each action endpoint preserves safe defaults:

- `capital_execution: false`
- `autonomous_execution: false`
- Gareth approval required where outbound, commercial, report, candidate, client, or placement action is involved.

## Audit Logging Structure

GLIRN action endpoints record events through the existing approval ledger pattern.

Audit events include:

- event type
- provider/module name
- decision
- target entity id
- action type
- reason
- approval requirement
- blocked status
- relevant score fields
- consent or terms status where relevant
- `capital_execution: false`
- `autonomous_execution: false`

Representative GLIRN event types:

- `glirn_approval_decision`
- `glirn_compliance_event`
- `glirn_executive_search_action`
- `glirn_intelligence_report_requested`
- `glirn_commercial_action`
- `glirn_client_acquisition_action`
- `glirn_candidate_discovery_action`
- `glirn_matching_action`

## Compliance Gate Structure

Compliance gates are evaluated before outbound or client-facing actions.

Candidate gates:

- Active candidate consent is required.
- Expired consent blocks outbound action.
- Missing consent creates alerts.
- Candidate-specific intelligence requires active consent.
- Candidate details cannot be shared without Gareth approval.

Client gates:

- Client terms status must be recorded before candidate details are shared.
- Fee discussion requires recorded client terms.
- Client-facing report generation requires Gareth approval.

Data handling gates:

- Deletion requests flag records.
- Data retention status is included in compliance readiness.
- Compliance events are audit logged.

## Human Approval Flow

1. GLIRN identifies or ranks an opportunity.
2. A proposed action is represented as a review item or action request.
3. If the action touches outbound communication, candidate details, client engagement, fee proposal, report generation, or placement, the action is locked.
4. Gareth reviews the request.
5. Gareth approves, rejects, or monitors.
6. The decision is recorded in the approval ledger.
7. The system remains non-autonomous unless future missions explicitly add approved external integrations.

## Commercial Revenue Flow

1. Recruitment opportunity is scored.
2. Fee type is classified.
3. Estimated revenue is calculated.
4. Client terms readiness is checked.
5. Candidate consent readiness is checked.
6. Fee proposal is locked pending Gareth approval.
7. Invoice readiness is only marked ready when client terms are recorded.
8. Commercial action is audit logged.

Revenue types currently modelled:

- Contingency placement fee
- Retained search fee
- Executive search fee
- Intelligence report fee
- Subscription intelligence fee

## Candidate-to-Client Matching Flow

1. Candidate Discovery Engine creates candidate profiles.
2. Client Acquisition Engine creates target client profiles.
3. Matching & Placement Engine compares candidate and client profiles.
4. Compatibility scores are calculated:
   - practice area compatibility
   - jurisdiction compatibility
   - seniority compatibility
   - salary or fee compatibility
   - relocation compatibility
5. Consent and terms gates are checked.
6. Match revenue score is calculated.
7. Placement probability score is calculated.
8. Ranked placement matches are returned.
9. Placement actions remain locked pending Gareth approval.
10. Match actions are audit logged.

## Future Integration Points

Potential future integrations, all subject to human approval and compliance review:

- CSV or manual data intake
- Candidate consent evidence storage
- Client terms evidence storage
- CRM export
- ATS export
- Email draft generation
- Document pack generation
- Invoice draft generation
- Marketplace listing for intelligence reports
- Read-only reporting dashboard

No future integration should bypass active consent, client terms readiness, Gareth approval, audit logging, or the capital execution false rule.
