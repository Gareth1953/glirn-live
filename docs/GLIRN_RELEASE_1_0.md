# GLIRN Release 1.0 Checkpoint

## Product Identity

Product name: Global Legal Intelligence & Recruitment Network

Public-facing founder name: David Sanson

Legal and tax owner: Gareth Price

Human-in-the-loop role: Gareth Price approval required before outbound action, candidate introduction, client engagement, fee proposal, report generation, candidate detail sharing, or placement action.

Capital execution: false

Autonomous execution: false

## Current Platform Status

GLIRN is a compliance-first, human-approved legal intelligence and recruitment control layer inside ArbitrageEngineV1. It ranks legal recruitment opportunities, monitors compliance readiness, estimates revenue, prioritises clients and candidates, and creates candidate-to-client placement matches.

The platform remains non-autonomous. It does not introduce candidates, contact clients, negotiate fees, send outbound communications, move money, trade, scrape, or execute vendor actions without Gareth approval.

Current test status: 166 passing tests.

## Mission History

Mission 30: GLIRN Foundation
- Added the foundation models for candidates, client firms, legal practice areas, jurisdictions, recruitment opportunities, candidate consent, client fee agreements, and human approval decisions.
- Added legal sectors, GLIRN opportunity scoring, dashboard structure, audit logging, and human approval controls.

Mission 31: GLIRN Legal Opportunity Radar
- Added the legal opportunity radar, fee estimator, priority ranking, highest-value candidate and client views, and Dave Recommends First card.
- Required Gareth approval for outbound action.

Mission 32: GLIRN Human Approval Centre
- Added a dedicated GLIRN approval queue view, approve, reject, and monitor actions, approval reason handling, action locks, and audit entries for every approval decision.
- Added locks for outbound action, candidate introduction, client engagement, and fee negotiation.

Mission 33: GLIRN Compliance Core
- Added the candidate consent ledger, client terms status, jurisdiction compliance profiles, data retention status, deletion request workflow, consent alerts, compliance readiness scoring, and compliance dashboard.
- Blocked candidate introductions and outbound actions where consent or terms are missing or expired.

Mission 34: GLIRN Executive Search Engine
- Added Partner, General Counsel, Chief Legal Officer, and senior legal candidate workflows.
- Added executive fee estimation, retained search fee estimation, seniority classification, premium opportunity flags, and high fee priority scoring.

Mission 35: GLIRN Legal Intelligence Network
- Added salary intelligence, market intelligence, hiring trend intelligence, practice area growth intelligence, jurisdiction demand intelligence, competitor hiring signals, and intelligence report controls.
- Positioned intelligence as the client hook while recruitment placements remain the main revenue engine.

Mission 36: GLIRN Commercial Revenue Engine
- Added placement fee calculation, retained search fee calculation, success fee tracking, invoice readiness, client terms readiness, fee negotiation recommendations, and commercial pipeline reporting.
- Preserved mandatory Gareth approval for fee proposals.

Mission 37: GLIRN Client Acquisition Engine
- Added target client profiles, client opportunity scoring, hiring likelihood scoring, estimated fee potential, preferred practice area matching, client readiness status, and outreach approval controls.

Mission 38: GLIRN Candidate Discovery Engine
- Added candidate seniority scoring, practice area matching, jurisdiction matching, relocation openness, consent readiness, executive candidate flags, estimated placement value, and candidate priority scoring.

Mission 39: GLIRN Matching & Placement Engine
- Connected candidate discovery with client acquisition.
- Added candidate-to-client matching, compatibility scores, consent and terms gates, match revenue scoring, placement probability scoring, ranked placement matches, and the Matching & Placement Engine panel.

## Current Active Modules

- Legal sector taxonomy
- Recruitment opportunity scoring
- Legal Opportunity Radar
- GLIRN Human Approval Centre
- GLIRN Compliance Core
- Executive Search Engine
- Legal Intelligence Network
- Commercial Revenue Engine
- Client Acquisition Engine
- Candidate Discovery Engine
- Matching & Placement Engine
- Audit logging
- Approval queue integration

## Key API Endpoints

- `GET /health`
- `GET /ui`
- `GET /glirn/dashboard`
- `POST /glirn/opportunities/{opportunity_id}/request-approval`
- `POST /glirn/approvals/{approval_id}/{decision}`
- `POST /glirn/compliance/deletion-request`
- `POST /glirn/executive-search/actions`
- `POST /glirn/intelligence/report-requests`
- `POST /glirn/commercial/actions`
- `POST /glirn/client-acquisition/actions`
- `POST /glirn/candidate-discovery/actions`
- `POST /glirn/matching/actions`

## Key UI Panels

- Legal Opportunity Radar
- GLIRN Human Approval Centre
- GLIRN Compliance Core
- Executive Search Engine
- Legal Intelligence Network
- Commercial Revenue Engine
- Client Acquisition Engine
- Candidate Discovery Engine
- Matching & Placement Engine

## Compliance Controls

- Candidate cannot be introduced without active consent.
- Client cannot receive candidate details without recorded terms status.
- Expired consent blocks outbound action.
- Missing consent creates compliance alerts.
- Deletion requests flag records.
- Candidate-specific intelligence requires active consent.
- Client-facing report generation requires Gareth approval.
- Compliance events are audit logged.

## Revenue Controls

- Placement, retained search, executive search, intelligence report, and subscription intelligence fees are modelled.
- Invoice readiness requires recorded client terms.
- Fee proposals require Gareth approval.
- Candidate submission requires active candidate consent.
- Commercial actions are audit logged.

## Human Approval Controls

- Outbound action requires Gareth approval.
- Candidate introduction requires Gareth approval.
- Client engagement requires Gareth approval.
- Fee negotiation requires Gareth approval.
- Candidate detail sharing requires Gareth approval.
- Placement action requires Gareth approval.
- Human approval remains mandatory.

## Known Limitations

- Current GLIRN data is stub data only.
- No external CRM, ATS, email, payment, or document system is integrated.
- No automated outreach is enabled.
- No live candidate or client data ingestion is enabled.
- No jurisdiction-specific legal advice is provided.
- Compliance readiness is a control signal, not legal advice.
- Revenue estimates are indicative and not guarantees.
- Matching output is ranked guidance only and cannot trigger autonomous action.

## Recommended Next Missions

Mission 40: GLIRN Release Hardening and Documentation QA.

Mission 41: GLIRN Data Import Specification for human-approved CSV or manual intake.

Mission 42: GLIRN Consent Evidence Pack for candidate and client readiness records.

Mission 43: GLIRN Pilot Workflow Simulation using stub candidate and client data.

Mission 44: GLIRN Marketplace and Services Boundary Review.

Mission 45: GLIRN Commercial Pack for Gareth-approved recruitment opportunity review.
