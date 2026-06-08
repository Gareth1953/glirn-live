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
