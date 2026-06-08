# Incident Response Checklist

Use this if the safety gate decision looks wrong or the workflow behaves unexpectedly.

## 1. Incorrect ALLOW

Definition:

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

## 2. Incorrect REQUEST_APPROVAL

Definition:

The gate requested approval when the user believes the action was safe.

Steps:

1. Save payload and response.
2. Ask whether the approval request was annoying or acceptable.
3. Mark as possible false positive.
4. Continue pilot unless approval friction becomes high.

## 3. Incorrect BLOCK

Definition:

The gate blocked something the user believes was safe.

Steps:

1. Save payload and response.
2. Confirm whether any business process was disrupted.
3. Mark as possible false positive.
4. Review whether the blocked reason was reasonable.

## 4. API Outage

If the safety gate is unavailable:

```text
do_not_execute
```

Steps:

1. Stop or pause workflow.
2. Do not send automatically.
3. Check API health.
4. Notify operator.
5. Resume only after a successful test call.

## 5. Approval Queue Failure

If approval is requested but no approval item is created:

1. Treat action as not approved.
2. Do not send.
3. Check approval queue.
4. Check ledger.
5. Record incident.

## 6. Incident Notes

Record:

- date
- workflow
- decision
- expected decision
- payload summary
- impact
- whether customer was affected
- correction needed

## Hard Rule

If unsure:

```text
do_not_execute
```
