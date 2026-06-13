# ArbitrageEngineV1 Runbook

## Install

Install the API dependencies:

```powershell
py -m pip install fastapi uvicorn
```

The engine also requires `requests`:

```powershell
py -m pip install requests
```

Create a local `.env` file with provider keys as needed:

```powershell
OPENAI_API_KEY=your-key-here
ANTHROPIC_API_KEY=your-key-here
```

Do not commit or print API keys.

Optional local API protection:

```powershell
$env:ARBITRAGE_API_KEY='choose-a-local-control-key'
```

When `ARBITRAGE_API_KEY` is unset, local development behavior is unchanged. When it is set, `/health` remains public. `/providers`, `/dashboard`, `/analytics/history`, `/snapshot/daily`, `/system/checkpoint`, `/opportunities`, `/opportunities/analytics`, `/opportunities/scan`, `/opportunities/{opportunity_id}/approve`, `/opportunities/{opportunity_id}/reject`, `/opportunities/{opportunity_id}/outcome`, `/research`, `/research/intake`, `/research/import`, `/research/convert`, `/research/sources`, `/research/sources/{source_name}/toggle`, `/route`, and `/providers/{provider_name}/reset-score` require the `X-API-Key` header. `/ui` requires `?key=...`.

## Test

Run the full pytest suite with third-party plugin autoload disabled:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; py -m pytest
```

Run unittest discovery:

```powershell
py -m unittest discover -s tests
```

Run the smoke test:

```powershell
.\smoke_test.ps1
```

## Start API

Start the local FastAPI service:

```powershell
.\start_api.ps1
```

Equivalent direct command:

```powershell
py -m uvicorn app:app --host 127.0.0.1 --port 8095
```

The API runs in the foreground. Press `CTRL + C` to stop it.

## API Commands

Health:

```powershell
curl http://127.0.0.1:8095/health
```

Providers:

```powershell
curl http://127.0.0.1:8095/providers
```

Providers with API protection enabled:

```powershell
curl http://127.0.0.1:8095/providers -H "X-API-Key: choose-a-local-control-key"
```

Reset provider score:

```powershell
curl -X POST http://127.0.0.1:8095/providers/OpenAI_Test/reset-score
```

Reset provider score with API protection enabled:

```powershell
curl -X POST http://127.0.0.1:8095/providers/OpenAI_Test/reset-score `
  -H "X-API-Key: choose-a-local-control-key"
```

Dashboard:

```powershell
curl http://127.0.0.1:8095/dashboard
```

Dashboard with API protection enabled:

```powershell
curl http://127.0.0.1:8095/dashboard -H "X-API-Key: choose-a-local-control-key"
```

Analytics history:

```powershell
curl http://127.0.0.1:8095/analytics/history
```

Analytics history with API protection enabled:

```powershell
curl http://127.0.0.1:8095/analytics/history -H "X-API-Key: choose-a-local-control-key"
```

Daily intelligence snapshot:

```powershell
curl http://127.0.0.1:8095/snapshot/daily
```

Daily intelligence snapshot with API protection enabled:

```powershell
curl http://127.0.0.1:8095/snapshot/daily -H "X-API-Key: choose-a-local-control-key"
```

Daily snapshot helper script:

```powershell
.\daily_snapshot.ps1
```

Create a system checkpoint:

```powershell
curl -X POST http://127.0.0.1:8095/system/checkpoint
```

Create a system checkpoint with API protection enabled:

```powershell
curl -X POST http://127.0.0.1:8095/system/checkpoint -H "X-API-Key: choose-a-local-control-key"
```

Checkpoint helper script:

```powershell
.\checkpoint.ps1
```

Opportunities:

```powershell
curl http://127.0.0.1:8095/opportunities
```

Opportunity performance analytics:

```powershell
curl http://127.0.0.1:8095/opportunities/analytics
```

Scan for review-only opportunities:

```powershell
curl -X POST http://127.0.0.1:8095/opportunities/scan
```

Opportunities with API protection enabled:

```powershell
curl http://127.0.0.1:8095/opportunities -H "X-API-Key: choose-a-local-control-key"
```

Opportunity analytics with API protection enabled:

```powershell
curl http://127.0.0.1:8095/opportunities/analytics -H "X-API-Key: choose-a-local-control-key"
```

Scan with API protection enabled:

```powershell
curl -X POST http://127.0.0.1:8095/opportunities/scan `
  -H "X-API-Key: choose-a-local-control-key"
```

Approve an opportunity after human review:

```powershell
curl -X POST http://127.0.0.1:8095/opportunities/<opportunity-id>/approve `
  -H "Content-Type: application/json" `
  -d "{\"reviewer_note\":\"Approved for continued human review.\"}"
```

Reject an opportunity after human review:

```powershell
curl -X POST http://127.0.0.1:8095/opportunities/<opportunity-id>/reject `
  -H "Content-Type: application/json" `
  -d "{\"reviewer_note\":\"Rejected after manual review.\"}"
```

Record an opportunity outcome:

```powershell
curl -X POST http://127.0.0.1:8095/opportunities/<opportunity-id>/outcome `
  -H "Content-Type: application/json" `
  -d "{\"outcome_status\":\"monitored\",\"reviewer_note\":\"Monitor before any further decision.\",\"realized_value\":0}"
```

Approve with API protection enabled:

```powershell
curl -X POST http://127.0.0.1:8095/opportunities/<opportunity-id>/approve `
  -H "Content-Type: application/json" `
  -H "X-API-Key: choose-a-local-control-key" `
  -d "{\"reviewer_note\":\"Approved for continued human review.\"}"
```

Reject with API protection enabled:

```powershell
curl -X POST http://127.0.0.1:8095/opportunities/<opportunity-id>/reject `
  -H "Content-Type: application/json" `
  -H "X-API-Key: choose-a-local-control-key" `
  -d "{\"reviewer_note\":\"Rejected after manual review.\"}"
```

Record an opportunity outcome with API protection enabled:

```powershell
curl -X POST http://127.0.0.1:8095/opportunities/<opportunity-id>/outcome `
  -H "Content-Type: application/json" `
  -H "X-API-Key: choose-a-local-control-key" `
  -d "{\"outcome_status\":\"monitored\",\"reviewer_note\":\"Monitor before any further decision.\",\"realized_value\":0}"
```

Research items:

```powershell
curl http://127.0.0.1:8095/research
```

Run stub research intake:

```powershell
curl -X POST http://127.0.0.1:8095/research/intake
```

Import a manual research item:

```powershell
curl -X POST http://127.0.0.1:8095/research/import `
  -H "Content-Type: application/json" `
  -d "{\"title\":\"Manual provider pricing note\",\"url\":\"https://example.com/provider-pricing-note\",\"summary\":\"Manual research note stored for review only. URL is not fetched.\",\"category\":\"provider_pricing_changes\",\"relevance_score\":0.83}"
```

Convert high-relevance research to opportunity candidates:

```powershell
curl -X POST http://127.0.0.1:8095/research/convert
```

Research source configuration:

```powershell
curl http://127.0.0.1:8095/research/sources
```

Toggle a research source locally:

```powershell
curl -X POST http://127.0.0.1:8095/research/sources/AI%20Infrastructure%20News/toggle
```

Research items with API protection enabled:

```powershell
curl http://127.0.0.1:8095/research -H "X-API-Key: choose-a-local-control-key"
```

Run stub research intake with API protection enabled:

```powershell
curl -X POST http://127.0.0.1:8095/research/intake `
  -H "X-API-Key: choose-a-local-control-key"
```

Import manual research with API protection enabled:

```powershell
curl -X POST http://127.0.0.1:8095/research/import `
  -H "Content-Type: application/json" `
  -H "X-API-Key: choose-a-local-control-key" `
  -d "{\"title\":\"Manual provider pricing note\",\"url\":\"https://example.com/provider-pricing-note\",\"summary\":\"Manual research note stored for review only. URL is not fetched.\",\"category\":\"provider_pricing_changes\",\"relevance_score\":0.83}"
```

Convert research with API protection enabled:

```powershell
curl -X POST http://127.0.0.1:8095/research/convert `
  -H "X-API-Key: choose-a-local-control-key"
```

Research source configuration with API protection enabled:

```powershell
curl http://127.0.0.1:8095/research/sources -H "X-API-Key: choose-a-local-control-key"
```

Toggle a research source with API protection enabled:

```powershell
curl -X POST http://127.0.0.1:8095/research/sources/AI%20Infrastructure%20News/toggle `
  -H "X-API-Key: choose-a-local-control-key"
```

Route:

```powershell
curl -X POST http://127.0.0.1:8095/route `
  -H "Content-Type: application/json" `
  -d "{\"task\":\"test route api\"}"
```

Route with API protection enabled:

```powershell
curl -X POST http://127.0.0.1:8095/route `
  -H "Content-Type: application/json" `
  -H "X-API-Key: choose-a-local-control-key" `
  -d "{\"task\":\"test route api\"}"
```

Local UI:

```powershell
http://127.0.0.1:8095/ui
```

The local UI includes lightweight inline SVG summaries for provider wins, recent latency trends, route counts, a daily intelligence snapshot, checkpoint creation, opportunity performance analytics, recent review-only opportunities, reviewer note fields, approval/reject controls, outcome status controls, approval and outcome history, recent research intake items, a manual research import form, a research-to-opportunity conversion button, and research source configuration status.

Local UI with API protection enabled:

```powershell
http://127.0.0.1:8095/ui?key=choose-a-local-control-key
```

## CLI Commands

Run one route:

```powershell
py main.py "test message"
```

Print dashboard:

```powershell
py dashboard.py
```

Print daily intelligence snapshot from the running API:

```powershell
.\daily_snapshot.ps1
```

`daily_snapshot.ps1` uses `http://127.0.0.1:8095` by default. Set `ARBITRAGE_BASE_URL` to target another API base URL. If `ARBITRAGE_API_KEY` is set, the script sends it as `X-API-Key`.

Create a system checkpoint from the running API:

```powershell
.\checkpoint.ps1
```

`checkpoint.ps1` uses `http://127.0.0.1:8095` by default. Set `ARBITRAGE_BASE_URL` to target another API base URL. If `ARBITRAGE_API_KEY` is set, the script sends it as `X-API-Key`.

## System Checkpoints

`POST /system/checkpoint` creates a timestamped folder under `backups/` and copies:

- `config/`
- `analytics/`
- `data/`
- `logs/`
- `RUNBOOK.md`

Checkpoint exports skip `.env`, `*.env`, and secret-named files. The response includes `checkpoint_id`, `created_at`, `files_copied`, and `backup_path`.

## Opportunity Review

Opportunities are stored in `data/opportunities.jsonl`. Approval ledger entries are stored in `data/opportunity_approvals.jsonl`. The current scanner is a stub foundation that creates AI infrastructure review items only. Each scanned opportunity is evaluated before storage.

Opportunity scan results are human-approval only:

- `approval_required` is `true`
- `execution_enabled` is `false`
- opportunity `status` defaults to `pending_review`

Opportunity evaluation fields:

- `confidence_reason`
- `estimated_cost`
- `estimated_benefit`
- `risk_notes`
- `recommended_action`

`recommended_action` is advisory only and is limited to `review`, `monitor`, or `reject`.

Approval actions update opportunity status:

- approve: `approved_human_review`
- reject: `rejected_human_review`

Outcome tracking supports these statuses:

- `pending_review`
- `approved_human_review`
- `rejected_human_review`
- `monitored`
- `expired`

Approval and outcome ledger entries can include `reviewer_note` and `realized_value`. Ledger entries always include `capital_execution` set to `false`.

Opportunity analytics are available at `/opportunities/analytics` and summarize current opportunities plus the approval ledger:

- total opportunities
- count by status
- count by recommended action
- average confidence
- total estimated value
- total estimated benefit
- total realized value from outcome entries
- approval, rejection, and monitor counts

The daily intelligence snapshot is available at `/snapshot/daily` and summarizes system health, active and blocked providers, route counts, opportunity analytics, recent high-confidence opportunities, recent research items, and the pending human review queue count.

No capital execution workflow is implemented.

## Research Intake

Research items are stored in `data/research_items.jsonl`.

Research source definitions are stored in `config/research_sources.json`. All external source definitions are disabled by default.

The current research intake is stub-only. It creates internal research records for AI infrastructure arbitrage, provider pricing changes, enterprise AI orchestration, latency optimisation, and non-crypto system arbitrage.

Manual research import accepts `title`, `url`, `summary`, `category`, and `relevance_score`. The `url` is stored only and is never fetched. `relevance_score` must be from `0.0` to `1.0`, and imported categories must not contain `crypto`.

Research conversion creates opportunity candidates only for research items with `relevance_score >= 0.75`. Converted opportunities remain non-crypto, use `pending_review`, require human approval, and return `execution_enabled` as `false`.

Toggling a research source only changes its local `enabled` flag. No internet fetching is implemented. No internet scraping is implemented. No crypto workflow is implemented. No capital execution workflow is implemented.

## Troubleshooting

If `curl` cannot connect to `127.0.0.1:8095`, start the API first:

```powershell
.\start_api.ps1
```

If no providers load, check that `.env` exists and contains an API key for at least one enabled provider in `config/providers.json`.

If Anthropic does not route, confirm `enabled` is set to `true` in `config/providers.json` and that `ANTHROPIC_API_KEY` is set. A provider can still be blocked by guard status if its score is too low or it has repeated failures.

If pytest fails while importing unrelated global plugins, use the supported command:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; py -m pytest
```

If port `8095` is already in use, stop the existing process or start Uvicorn manually on another port:

```powershell
py -m uvicorn app:app --host 127.0.0.1 --port 8096
```

If protected endpoints return `401`, either unset `ARBITRAGE_API_KEY` for local development or send the configured key. `.\smoke_test.ps1` automatically sends the `X-API-Key` header when `ARBITRAGE_API_KEY` is present in the shell environment. Resetting a provider score sets its success and failure counters, average latency, and average cost to `0`, and restores `score` to `100`.

## GLIRN Persistent Storage

GLIRN stores live enquiries, routing results, approval packages, final approval statuses, export metadata, revenue ledger records, and audit-safe action history in SQLite.

The local default is `data/glirn_live.db`. Set `GLIRN_DB_PATH` to override it. The Render Blueprint mounts a persistent disk at `/var/data` and sets `GLIRN_DB_PATH=/var/data/glirn_live.db`. If the environment variable is absent, the app still boots but `/health` reports `persistence_warning: GLIRN_DB_PATH is using non-persistent default storage`.

## Controlled enquiry acknowledgements

GLIRN creates an immediate fixed acknowledgement for each valid public enquiry. Configure external delivery with `GLIRN_SMTP_HOST`, `GLIRN_SMTP_PORT`, `GLIRN_SMTP_USERNAME`, `GLIRN_SMTP_PASSWORD`, and `GLIRN_FROM_EMAIL`. All five values are required before any SMTP connection is attempted.

If SMTP is not configured or delivery fails, the enquiry still succeeds and the acknowledgement is persisted as `queued_local_only`. The Command Centre shows its status for local review.

Automatic informational responses are limited to predefined templates covering the GBP 500 Intelligence Review, GLIRN services, confidentiality, candidate support, future legal leaders, and international support. Every other enquiry creates a draft with `awaiting_gareth_approval`; no personalised response, commitment, introduction, pricing negotiation, invoice, payment request, or money movement is automatic.

## Intelligence brief human review and quality assurance

Every intelligence brief must complete the Mission 106 human review checklist before it can become ready for manual delivery. The reviewer must be named and must record an outcome and approval rationale. The checklist covers scope, evidence, separation of fact from speculation, human review of AI-assisted content, confidence limitations, advice boundaries, candidate consent, confidentiality, non-guarantee wording, and final wording quality.

The following red flags require additional review and block approval until resolved: low AI confidence, speculative content, candidate-specific intelligence, wording that could imply legal or regulated recruitment advice, and insufficient evidence. Candidate-specific intelligence also requires active candidate consent.

GLIRN should decline work where legal or regulated recruitment advice is requested, evidence is insufficient, consent is unavailable, the request is outside GLIRN's expertise, guarantees or improper influence are requested, confidentiality or ethical handling cannot be maintained, or another specialist adviser would better serve the client.

Record reviews through `POST /glirn/intelligence-briefs/human-review`. Records are persisted as `human_review_record` entries and audit-safe actions. The audit trail records the enquiry date, reviewer, outcome, approval rationale, delivery status, and red-flag state without copying candidate-specific details. Delivery remains manual and Gareth remains final approval authority.

## Intelligence Brief template and delivery package

Mission 107 standardises every delivery-ready GLIRN Intelligence Brief with these mandatory sections: Client Context, Scope of Brief, Hiring Priority Assessment, Market Observations, Risks and Considerations, Indicative Next Steps, Human Review Summary, and Required Disclaimer.

Generate a package through `POST /glirn/intelligence-briefs/package`. The request must identify the source brief and provide the first six client-content sections. GLIRN inserts the Mission 106 human review summary and required disclaimer. Package generation is rejected unless a matching persisted Mission 106 record is approved for manual delivery with no validation errors, incomplete checks, or unresolved red flags.

The generated Markdown file is stored locally under `data/glirn_intelligence_briefs/`. Its brief record links to the Mission 106 review record and a dedicated audit record, including reviewer identity and review date. Email sending, external upload, external integrations, and automatic delivery remain disabled. A human must deliver the package manually.

Human-led. Technology-enhanced. Confidentiality-first.

## Global legal intelligence engine

Mission 111 adds jurisdiction-aware, high-level hiring intelligence for the United Kingdom, United Arab Emirates, Singapore, European Union, and United States. Submit a validation through `POST /glirn/intelligence-briefs/global-intelligence` after Mission 110 using the exact brief content assessed by Mission 110.

Each validation covers hiring difficulty, practice-area demand, market competitiveness, jurisdiction-specific considerations, candidate scarcity, and talent mobility. Every record includes jurisdiction, practice area, intelligence summary, evidence transparency summary, the authoritative Mission 110 confidence score and category, limitations, information gaps, alternative interpretations, and review timestamp.

Observations are cautious interpretations of supplied indicator ratings and evidence summaries. They are not asserted market facts, legal advice, candidate-specific intelligence, or search commitments. Candidate-specific intelligence remains prohibited without valid consent, and detailed evidence or confidential source material is not copied into audit-safe action records.

Mission 111 automatically escalates confidence below 70, jurisdiction expertise limitations, insufficient evidence, unresolved reviewer disagreement, intelligence outside GLIRN's expertise boundaries, unsupported claims, unresolved Mission 110 escalation, and incomplete candidate consent. Escalated intelligence cannot receive final Gareth approval or proceed to delivery packaging, and Gareth cannot override an unresolved escalation directly.

Delivery eligibility requires Mission 106 approval, completed Mission 109 review, completed Mission 110 confidence assessment, completed Mission 111 validation of the same content, no unresolved escalation, and Gareth's final approval. The generated package remains local and manual-only. Acceptance, payment, candidate outreach, search commitments, brief delivery, and external commitments remain disabled.

Human-led. Technology-enhanced. Confidentiality-first.

## Confidence scoring and evidence transparency

Mission 110 adds a separate confidence assessment after Mission 109. Submit it through `POST /glirn/intelligence-briefs/confidence-assessment` using the exact content reviewed in Mission 109. The weighted score covers evidence sufficiency, evidence quality, reviewer agreement, escalation presence, Mission 106 outcome, candidate consent completeness, data recency, and market information completeness.

Confidence categories are Very High Confidence (90-100), High Confidence (75-89), Moderate Confidence (60-74), and Low Confidence (below 60). Any score below 70 creates an unresolved escalation. Inadequate evidence sufficiency, significant reviewer disagreement, material limitations that undermine conclusions, unresolved Mission 109 escalation, invalid Mission 106 approval, or incomplete candidate consent also create Mission 110 escalations.

Mission 110 records include key evidence considered, supporting assumptions, known limitations, caution areas, information gaps, and alternative interpretations identified in Mission 109. Contact details are redacted from summaries, candidate-data minimisation remains mandatory, and audit-safe records contain ratings and outcomes without copying confidential source material.

Gareth cannot directly override an unresolved Mission 110 escalation. The brief must be remediated, reassessed through Mission 109, and reassessed through Mission 110 before final approval. Delivery packaging requires valid Mission 106 approval, completed and escalation-free Mission 109 review, completed and escalation-free Mission 110 assessment of the same content with confidence of at least 70, and Gareth's final approval.

The generated local Markdown package includes confidence score, confidence category, evidence sufficiency, reviewer agreement, limitations, caution areas, information gaps, and alternative interpretations. Acceptance, payment, candidate outreach, search activity, delivery, and external commitments remain manual and disabled.

Human-led. Technology-enhanced. Confidentiality-first.

## Enquiry notification framework

Mission 108 sends an informational notification to `legalintelligencerecruitment@outlook.com` after a valid website enquiry and its response records have been persisted. The notification uses the configured `GLIRN_SMTP_HOST`, `GLIRN_SMTP_PORT`, `GLIRN_SMTP_USERNAME`, `GLIRN_SMTP_PASSWORD`, and `GLIRN_FROM_EMAIL` settings.

The notification contains the enquiry ID, submission timestamp, enquiry type, name, organisation, country, practice area, jurisdiction, seniority, timescale, full enquiry message, and the mandatory manual-review warning. It does not accept work, initiate payment discussion, generate an intelligence brief, contact a candidate, begin search activity, or deliver any service.

Notification metadata is persisted as an `enquiry_notification_record`. Audit-safe action history records the notification ID, related enquiry ID, recipient, delivery status, attempt timestamp, failure reason, and retry count without copying the enquiry message. A delivery failure never reverses or blocks enquiry persistence.

The Gareth Command Centre displays notification counts and failures requiring attention. Failed notifications can be retried manually through `POST /glirn/enquiry-notifications/{notification_id}/resend`. This endpoint only resends the fixed business notification and requires the configured API key when protected mode is enabled.

All enquiries remain subject to Mission 106 human review. Gareth remains the sole approval authority for acceptance, payment discussions, intelligence brief preparation, search activity, and delivery.

## Multi-agent intelligence review

Mission 109 adds four independent review perspectives before an Intelligence Brief can reach Gareth for final approval: Intelligence Analyst, Risk Reviewer, Devil's Advocate Reviewer, and Quality Assurance Reviewer. Start the review through `POST /glirn/intelligence-briefs/multi-agent-review` after a Mission 106 human review record exists.

Each persisted `multi_agent_review_record` links the brief and Mission 106 review, records the four reviewer outputs and confidence scores, and includes the consensus summary and timestamp. Audit-safe history stores identifiers, scores, status, and escalation outcomes without duplicating candidate-sensitive content.

The review automatically escalates when average confidence is below 70, any reviewer requests escalation, legal-advice inference risk is identified, candidate consent is unresolved, or evidence is insufficient. Escalated briefs cannot receive final approval or be packaged for delivery. Resolve the issues, update the brief, and repeat the multi-agent review.

Record Gareth's final decision through `POST /glirn/intelligence-briefs/{brief_id}/final-approval`. Package generation through `POST /glirn/intelligence-briefs/package` requires a valid Mission 106 approval, a completed and escalation-free Mission 109 review of the exact content, and final approval by Gareth. The generated package remains local and manual-only; no acceptance, payment, candidate outreach, delivery, or external commitment is automatic.

Human-led. Technology-enhanced. Confidentiality-first.
