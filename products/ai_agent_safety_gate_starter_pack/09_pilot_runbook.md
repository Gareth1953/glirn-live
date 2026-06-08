# One-Workflow Pilot Runbook

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

Do not start pilot until all three branches behave correctly.

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
