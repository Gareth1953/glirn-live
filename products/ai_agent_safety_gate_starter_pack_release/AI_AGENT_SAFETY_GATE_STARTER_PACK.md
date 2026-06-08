# AI Agent Safety Gate Starter Pack

Practical approval rules, checklists, workflow guides, and test cases for safer AI automations in Zapier, Make, n8n, Airtable, Gmail, Slack, and CRM workflows.

## Core Promise

Stop AI automations from sending, spending, publishing, or acting without a safety check.

## Target Buyer

This pack is for:

- no-code automation builders
- AI workflow consultants
- small automation agencies
- solopreneurs building AI email workflows
- builders using Zapier, Make, n8n, Airtable, Gmail, Slack, or CRM automations

## What This Pack Helps You Do

Use a simple safety decision before an AI workflow takes action:

```text
ALLOW
REQUEST_APPROVAL
BLOCK
```

The first recommended use case is deliberately narrow:

```text
Customer enquiry
-> AI drafts email
-> Safety gate check
-> ALLOW / REQUEST_APPROVAL / BLOCK
-> Manual review if needed
```

## Safety Boundary

This pack does not provide legal, medical, regulated financial, tax, investment, security, or compliance advice.

Do not use it for:

- legal advice
- medical advice
- regulated financial advice
- trading
- crypto
- gambling
- scraping
- private-data-heavy workflows
- autonomous capital movement

Safe default:

```text
do_not_execute
```

---

# 1. Safety Policy

## Purpose

AI Agent Safety Gate is a simple decision policy for AI workflows.

Before an AI agent sends, spends, publishes, contacts, changes, or executes, classify the proposed action as:

- ALLOW
- REQUEST_APPROVAL
- BLOCK

## ALLOW

Use ALLOW when the proposed action is low risk, internal, reversible, or already approved.

Typical ALLOW cases:

- internal draft only
- internal summary only
- internal classification only
- already-approved customer email
- no spending
- no vendor change
- no private data issue
- no legal, medical, or regulated financial advice
- no public publication
- no customer contact without review

Plain-English rule:

```text
ALLOW only when the action is safe, low-risk, and does not create an external consequence.
```

## REQUEST_APPROVAL

Use REQUEST_APPROVAL when a human should review before the action happens.

Typical REQUEST_APPROVAL cases:

- customer-facing email
- pricing, discount, refund, or money claim
- public content publication
- workflow execution with external effect
- internal private data use
- uncertain action
- medium-risk action
- action where tone, accuracy, or context matters

Plain-English rule:

```text
REQUEST_APPROVAL when the action may affect a customer, reputation, data handling, or business outcome.
```

## BLOCK

Use BLOCK when the proposed action is outside safe scope.

Typical BLOCK cases:

- spending money
- autonomous capital movement
- vendor or tool change
- legal advice
- medical advice
- regulated financial advice
- trading
- crypto speculation
- gambling
- scraping
- customer-facing private data
- unsupported action type
- irreversible action without approval

Plain-English rule:

```text
BLOCK when the action is prohibited, unsafe, unsupported, or too risky for the workflow.
```

## Decision Table

| Proposed Action | Decision |
|---|---|
| Internal AI draft | ALLOW |
| Internal summary | ALLOW |
| Internal classification | ALLOW |
| Already-approved customer email | ALLOW |
| Customer-facing email | REQUEST_APPROVAL |
| Email with pricing, refund, discount, or payment language | REQUEST_APPROVAL |
| Publish public content | REQUEST_APPROVAL |
| Execute external workflow | REQUEST_APPROVAL |
| Internal private data | REQUEST_APPROVAL |
| Customer-facing private data | BLOCK |
| Spend money | BLOCK |
| Change vendor or tool | BLOCK |
| Legal advice | BLOCK |
| Medical advice | BLOCK |
| Regulated financial advice | BLOCK |
| Trading, crypto, gambling | BLOCK |
| Scraping | BLOCK |

---

# 2. AI Email Safety Checklist

Use this before an AI-generated customer email is sent.

## Recipient Check

Ask:

- Is this email going to a customer or prospect?
- Is this email internal only?
- Has a human already approved this exact message?

Decision:

- Internal only: likely ALLOW
- Customer or prospect: REQUEST_APPROVAL unless already approved

## Money Claim Check

Does the email mention:

- price
- discount
- refund
- payment
- savings
- guarantee
- compensation
- invoice
- contract value

Decision:

- If yes: REQUEST_APPROVAL

## Advice Check

Does the email include:

- legal advice
- medical advice
- regulated financial advice
- tax advice
- investment advice

Decision:

- If yes: BLOCK

## Private Data Check

Does the email contain:

- personal information
- customer records
- confidential business information
- internal financial data
- passwords or credentials
- sensitive documents

Decision:

- Internal use: REQUEST_APPROVAL
- Customer-facing private data: BLOCK

## Tone And Accuracy Check

Could the email be:

- rude
- too casual
- too aggressive
- misleading
- factually uncertain
- making promises the business may not keep

Decision:

- If uncertain: REQUEST_APPROVAL

## Action Check

Does sending this email cause an action?

- starts a contract
- confirms cancellation
- confirms refund
- changes service
- commits delivery date
- commits price
- triggers another workflow

Decision:

- If yes: REQUEST_APPROVAL

## Final Rule

```text
If internal and low-risk: ALLOW
If customer-facing or consequential: REQUEST_APPROVAL
If prohibited or unsafe: BLOCK
```

---

# 3. Zapier Workflow Guide

## Suggested Workflow

```text
Trigger
-> AI drafts customer email
-> Webhooks by Zapier: POST safety request
-> Paths by Zapier on decision
   -> ALLOW
   -> REQUEST_APPROVAL
   -> BLOCK
```

## Where The Safety Gate Goes

Place the safety gate after the AI has drafted the email and before any send, publish, contact, or workflow execution step.

## Webhook Step

Use:

```text
Webhooks by Zapier
Custom Request
Method: POST
```

Send fields:

- action_type
- recipient_type
- subject
- body
- customer_facing
- contains_money_claim
- contains_private_data
- contains_legal_advice
- contains_medical_advice
- contains_regulated_financial_advice
- spends_money
- changes_vendor
- publishes_content
- executes_workflow
- human_approved_already

## Branch Handling

### ALLOW

Continue only to the intended safe next step.

### REQUEST_APPROVAL

Do not send automatically.

Recommended actions:

- create approval task
- send Slack or email notification to reviewer
- store approval_id if available
- stop workflow until a human reviews

### BLOCK

Stop the workflow.

Recommended actions:

- notify operator
- save reason
- do not send

## Fail-Closed Rule

If the webhook fails or the safety gate is unavailable:

```text
do_not_execute
```

---

# 4. Make Workflow Guide

## Suggested Scenario

```text
Trigger module
-> AI text generation module
-> HTTP module: POST safety request
-> Router module on decision
   -> ALLOW
   -> REQUEST_APPROVAL
   -> BLOCK
```

## HTTP Module Placement

Place the HTTP module immediately after the AI-generated email is produced.

Use:

```text
HTTP > Make a request
Method: POST
Body type: Raw JSON
```

## Route On

```text
decision
```

Possible values:

- ALLOW
- REQUEST_APPROVAL
- BLOCK

## Branch Handling

### ALLOW

Continue to the safe next step.

### REQUEST_APPROVAL

Stop automatic send.

Recommended modules:

- create task
- send internal notification
- add row to tracking sheet
- store approval_id if available

### BLOCK

Stop scenario path.

Recommended modules:

- log reason
- notify owner
- do not continue to send, publish, or act

## Fail-Closed Rule

If the HTTP module fails:

```text
do_not_execute
```

Do not route failed safety checks to ALLOW.

---

# 5. n8n Workflow Guide

## Suggested Workflow

```text
Trigger
-> AI node drafts email
-> HTTP Request node: POST safety request
-> Switch node on decision
   -> ALLOW
   -> REQUEST_APPROVAL
   -> BLOCK
```

## HTTP Request Node

Place the HTTP Request node after AI-generated text and before any customer-facing action.

Use:

```text
Method: POST
Send Body: JSON
```

## Switch Node

Route on:

```text
decision
```

Branches:

- ALLOW
- REQUEST_APPROVAL
- BLOCK

## Branch Handling

### ALLOW

Continue only to the intended safe action.

### REQUEST_APPROVAL

Create a manual review item.

Options:

- send Slack message
- send internal email
- create task
- add row to review table

Do not send the customer email until a human has reviewed it.

### BLOCK

Stop workflow.

Log:

- decision
- reason
- reason_codes

## Fail-Closed Rule

If the HTTP Request node fails:

```text
do_not_execute
```

---

# 6. Test Cases

Use these examples before running a live AI email workflow.

## Expected ALLOW

| # | Scenario | Expected |
|---|---|---|
| 1 | Internal draft only | ALLOW |
| 2 | Internal summary | ALLOW |
| 3 | Already-approved customer email with no blocked content | ALLOW |
| 4 | Internal classification of enquiry | ALLOW |
| 5 | Draft saved internally for review | ALLOW |

## Expected REQUEST_APPROVAL

| # | Scenario | Expected |
|---|---|---|
| 6 | Customer-facing email | REQUEST_APPROVAL |
| 7 | Customer-facing email with price, discount, refund, or saving claim | REQUEST_APPROVAL |
| 8 | Public content publication | REQUEST_APPROVAL |
| 9 | Workflow execution with external effect | REQUEST_APPROVAL |
| 10 | Internal private data | REQUEST_APPROVAL |
| 11 | Uncertain customer-facing tone | REQUEST_APPROVAL |
| 12 | Refund mention | REQUEST_APPROVAL |
| 13 | Delivery commitment | REQUEST_APPROVAL |

## Expected BLOCK

| # | Scenario | Expected |
|---|---|---|
| 14 | Regulated financial advice | BLOCK |
| 15 | Medical advice | BLOCK |
| 16 | Legal advice | BLOCK |
| 17 | Spending money | BLOCK |
| 18 | Vendor or tool change | BLOCK |
| 19 | Customer-facing private data | BLOCK |
| 20 | Unsupported action type such as execute_payment | BLOCK |

---

# 7. Client Reassurance One-Pager

## Safer AI Email Automations

AI can help draft customer emails, but customer-facing messages should not be sent blindly.

This workflow uses a simple safety gate before action.

Before an AI-generated customer email is sent, the workflow asks:

```text
ALLOW
REQUEST_APPROVAL
BLOCK
```

## What This Means

### ALLOW

The proposed action is low-risk, internal, or already approved.

### REQUEST_APPROVAL

A human should review before the message is sent.

Typical reasons:

- customer-facing email
- pricing or refund language
- important commitment
- private data concern
- uncertain tone or context

### BLOCK

The action should not proceed.

Typical blocked reasons:

- legal advice
- medical advice
- regulated financial advice
- spending money
- changing vendors or tools
- customer-facing private data
- unsupported action type

## Simple Promise

AI drafts. Risky actions pause. Unsafe actions stop.

Human approval remains in control.

---

# 8. Incident Response Checklist

## Incorrect ALLOW

The gate allowed an action that should have requested approval or been blocked.

Immediate steps:

1. Stop the workflow.
2. Confirm whether the message was sent.
3. Save the request payload.
4. Save the response.
5. Identify which flag or rule failed.
6. Mark as false negative.
7. Do not continue until the workflow is reviewed.

Critical incorrect ALLOW examples:

- legal advice allowed
- medical advice allowed
- regulated financial advice allowed
- customer-facing private data allowed
- spending allowed
- vendor change allowed

## Incorrect REQUEST_APPROVAL

The gate requested approval when the user believes the action was safe.

Steps:

1. Save payload and response.
2. Ask whether the approval request was annoying or acceptable.
3. Mark as possible false positive.
4. Continue unless approval friction becomes too high.

## Incorrect BLOCK

The gate blocked something the user believes was safe.

Steps:

1. Save payload and response.
2. Confirm whether any business process was disrupted.
3. Mark as possible false positive.
4. Review whether the blocked reason was reasonable.

## API Outage

If the safety gate is unavailable:

```text
do_not_execute
```

Steps:

1. Stop or pause workflow.
2. Do not send automatically.
3. Check API health or service status.
4. Notify operator.
5. Resume only after a successful test call.

---

# 9. One-Workflow Pilot Runbook

## Pilot Goal

Test whether a safety gate is useful in one AI-generated customer email workflow.

## Pilot Scope

- one pilot user
- one workflow
- one action type: send_email
- one integration: Zapier, Make, or n8n
- manual approval only
- no autonomous sending
- no money movement
- no vendor changes

## Start Checklist

Confirm:

- workflow uses AI-generated email text
- workflow can make HTTP/API call
- workflow can branch on decision
- REQUEST_APPROVAL stops the send
- BLOCK stops the send
- API outage fails closed
- pilot avoids legal, medical, financial, crypto, gambling, scraping, and private-data-heavy use

## Test Before Live Use

Run:

1. ALLOW test
2. REQUEST_APPROVAL test
3. BLOCK test

Do not start the pilot until all three branches behave correctly.

## Daily Review

Check:

- total evaluations
- ALLOW decisions
- REQUEST_APPROVAL decisions
- BLOCK decisions
- pending approvals
- blocked action reasons
- false positives
- false negatives
- user bypasses

## Pilot Metrics

Track:

- total evaluations
- allow_count
- request_approval_count
- block_count
- approval_acceptance_rate
- false_positive_count
- false_negative_count
- blocked_correct_count
- setup_time_minutes
- bypass_count
- user_satisfaction_score
- would_continue
- would_pay
- acceptable_price

## Closeout Questions

Ask:

1. Would you keep this in the workflow?
2. Did it stop anything useful?
3. Were approvals useful or annoying?
4. Did it allow anything worrying?
5. Is it better than a simple approval step?
6. Would you use it on another workflow?
7. Would you pay for it?
8. What price would feel fair?
9. What is the biggest missing piece?
10. If this disappeared tomorrow, would you care?

## Go / Pivot / Stop

### Go

Continue if:

- 20+ evaluations
- no serious false negatives
- user trusts decisions
- user would keep using it
- user would pay or seriously consider paying

### Pivot

Pivot if:

- safety problem is real but email use case is wrong
- user wants approval routing more than safety classification
- built-in approvals solve enough
- integration friction is too high

### Stop

Stop if:

- user does not connect it
- fewer than 10 evaluations
- user bypasses it
- no willingness to pay
- multiple serious false negatives

---

# 10. Suggested Listing Price

Starter price:

```text
GBP 19
```

Suggested tiers:

- GBP 19 Starter Pack
- GBP 49 Pro Pack with editable templates
- GBP 99 Agency Pack with white-label client wording

## Sales Promise

AI drafts. Risky actions pause. Unsafe actions stop.
