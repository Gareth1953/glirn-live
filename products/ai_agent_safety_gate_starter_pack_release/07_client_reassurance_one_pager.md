# Client Reassurance One-Pager

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

## What This Workflow Does Not Do

It does not:

- move money
- provide legal advice
- provide medical advice
- provide regulated financial advice
- trade
- use crypto workflows
- scrape websites
- automatically approve risky actions

## Simple Promise

AI drafts. Risky actions pause. Unsafe actions stop.

Human approval remains in control.
