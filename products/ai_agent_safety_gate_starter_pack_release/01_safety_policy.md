# AI Agent Safety Gate Policy

## Purpose

AI Agent Safety Gate is a simple decision policy for AI workflows.

Before an AI agent sends, spends, publishes, contacts, changes, or executes, the workflow should classify the proposed action as:

- ALLOW
- REQUEST_APPROVAL
- BLOCK

## Safe Default

If the workflow is unsure, the safe default is:

```text
do_not_execute
```

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
| Already-approved customer email | ALLOW |
| Customer-facing email | REQUEST_APPROVAL |
| Email with pricing or refund language | REQUEST_APPROVAL |
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

## Policy Promise

AI may draft. Humans approve risky action.

The system should never move capital automatically.
