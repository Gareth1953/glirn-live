# n8n Workflow Guide

## Goal

Use n8n to check an AI-generated customer email before any external action.

## Suggested Workflow

```text
Trigger
-> AI node drafts email
-> HTTP Request node: POST safety gate request
-> Switch node on decision
   -> ALLOW
   -> REQUEST_APPROVAL
   -> BLOCK
```

## HTTP Request Node

Place the HTTP Request node after the AI-generated text and before any customer-facing action.

Use:

```text
Method: POST
Send Body: JSON
```

Include the proposed action fields:

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

Do not treat missing safety response as approval.
