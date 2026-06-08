# AI Agent Safety Gate Starter Pack

Practical approval rules, checklists, and test cases for safer AI automations in Zapier, Make, and n8n.

## What This Pack Is

This pack helps automation builders add a simple safety step before an AI-generated customer email is sent.

Before the workflow sends or acts on an AI-generated message, it asks:

- ALLOW
- REQUEST_APPROVAL
- BLOCK

The goal is simple: stop AI automations from sending, spending, publishing, contacting, changing, or executing without a safety check.

## Who It Is For

- No-code automation builders
- AI workflow consultants
- Small automation agencies
- Solopreneurs building AI email workflows
- People using Zapier, Make, n8n, Airtable, Gmail, Slack, or CRM automations

## What Is Included

1. `01_safety_policy.md`
   - Plain-English ALLOW / REQUEST_APPROVAL / BLOCK policy.

2. `02_ai_email_safety_checklist.md`
   - Before-send checklist for AI-generated customer emails.

3. `03_zapier_workflow_guide.md`
   - Where to place the safety step in Zapier.

4. `04_make_workflow_guide.md`
   - Where to place the safety step in Make.

5. `05_n8n_workflow_guide.md`
   - Where to place the safety step in n8n.

6. `06_test_cases.md`
   - 20 test cases for ALLOW, REQUEST_APPROVAL, and BLOCK.

7. `07_client_reassurance_one_pager.md`
   - Client-facing explanation for safer AI workflows.

8. `08_incident_response_checklist.md`
   - What to do when a decision looks wrong.

9. `09_pilot_runbook.md`
   - One-workflow pilot procedure.

10. `10_marketplace_listing_copy.md`
   - Ready-to-adapt listing copy for Gumroad, Lemon Squeezy, Payhip, Etsy, or similar marketplaces.

## Safety Boundary

This pack does not provide legal, medical, regulated financial, tax, investment, security, or compliance advice.

It is not for:

- autonomous capital movement
- trading
- crypto speculation
- gambling
- scraping
- regulated financial advice
- medical advice
- legal advice
- private-data-heavy workflows

The safe default is:

```text
do_not_execute
```

## Recommended First Use

Use this pack for one workflow:

```text
Customer enquiry
-> AI drafts email
-> Safety gate check
-> ALLOW / REQUEST_APPROVAL / BLOCK
-> Manual review if needed
```

Keep the first implementation narrow. Do not try to govern every AI workflow at once.
