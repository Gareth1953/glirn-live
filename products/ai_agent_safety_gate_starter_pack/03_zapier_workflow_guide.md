# Zapier Workflow Guide

## Goal

Add a safety decision step before an AI-generated customer email is sent.

## Suggested Workflow

```text
Trigger
-> AI drafts customer email
-> Webhooks by Zapier: POST to safety gate
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

Continue only if the action is safe.

Recommended first pilot:

- Save draft
- Notify internal channel
- Continue to low-risk next step

### REQUEST_APPROVAL

Do not send automatically.

Recommended actions:

- Create approval task
- Send Slack/email notification to reviewer
- Store approval_id
- Stop the workflow until a human reviews

### BLOCK

Stop the workflow.

Recommended actions:

- Notify operator
- Save reason
- Do not send

## Fail-Closed Rule

If the webhook fails or the safety gate is unavailable:

```text
do_not_execute
```

The workflow should stop or request manual review.

## Pilot Advice

Do not try to auto-resume after approval in V1. Treat REQUEST_APPROVAL as a manual stop point.
