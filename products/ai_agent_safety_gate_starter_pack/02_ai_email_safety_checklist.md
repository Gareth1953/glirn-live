# AI Email Safety Checklist

Use this checklist before an AI-generated customer email is sent.

## 1. Recipient Check

- Is this email going to a customer or prospect?
- Is this email internal only?
- Has a human already approved this exact message?

Decision:

- Internal only: likely ALLOW
- Customer/prospect: REQUEST_APPROVAL unless already approved

## 2. Money Claim Check

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

## 3. Advice Check

Does the email include:

- legal advice
- medical advice
- regulated financial advice
- tax advice
- investment advice

Decision:

- If yes: BLOCK

## 4. Private Data Check

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

## 5. Tone And Accuracy Check

Could the email be:

- rude
- too casual
- too aggressive
- misleading
- factually uncertain
- making promises the business may not keep

Decision:

- If uncertain: REQUEST_APPROVAL

## 6. Action Check

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

## 7. Blocked Content Check

Block if the email includes:

- medical advice
- legal advice
- regulated financial advice
- gambling
- crypto speculation
- trading
- scraping request
- autonomous capital movement

Decision:

- BLOCK

## Final Decision

Use this rule:

```text
If internal and low-risk: ALLOW
If customer-facing or consequential: REQUEST_APPROVAL
If prohibited or unsafe: BLOCK
```
