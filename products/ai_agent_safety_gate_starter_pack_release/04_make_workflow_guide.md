# Make Workflow Guide

## Goal

Use Make to route an AI-generated customer email through a safety gate before action.

## Suggested Scenario

```text
Trigger module
-> AI text generation module
-> HTTP module: POST safety gate request
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

## Required Decision Field

The response field to route on is:

```text
decision
```

Possible values:

- ALLOW
- REQUEST_APPROVAL
- BLOCK

## Router Branches

### ALLOW

Continue to the safe next step.

For the first pilot, prefer:

- save draft
- notify internal user
- move to low-risk next module

### REQUEST_APPROVAL

Stop automatic send.

Recommended modules:

- create task
- send internal notification
- add row to tracking sheet
- store approval_id

### BLOCK

Stop scenario path.

Recommended modules:

- log reason
- notify owner
- do not continue to send/publish/action

## Fail-Closed Rule

If the HTTP module fails:

```text
do_not_execute
```

Do not route failed safety checks to the ALLOW branch.

## Pilot Advice

Keep the pilot to one customer email workflow. Do not add multiple policies or multiple action types in the first test.
