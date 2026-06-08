ALLOW = "ALLOW"
BLOCK = "BLOCK"
REQUEST_APPROVAL = "REQUEST_APPROVAL"

SUPPORTED_ACTION_TYPES = {"send_email"}


def _decision(decision, reason, reason_codes):
    return {
        "decision": decision,
        "reason": reason,
        "reason_codes": reason_codes,
        "approval_required": decision == REQUEST_APPROVAL,
        "blocked": decision == BLOCK,
        "safe_default": "do_not_execute",
        "capital_execution": False,
        "autonomous_execution": False,
    }


def evaluate_agent_action(payload):
    action_type = str(payload.get("action_type", "")).strip().lower()
    customer_facing = bool(payload.get("customer_facing", False))
    human_approved_already = bool(payload.get("human_approved_already", False))
    contains_private_data = bool(payload.get("contains_private_data", False))

    if action_type not in SUPPORTED_ACTION_TYPES:
        return _decision(
            BLOCK,
            "Unsupported action type is blocked by the Agent Safety Gate.",
            ["unsupported_action_type", "blocked_action"],
        )

    if bool(payload.get("spends_money", False)):
        return _decision(
            BLOCK,
            "Spending money is blocked in Agent Safety Gate V1.",
            ["capital_impact", "blocked_action"],
        )

    if bool(payload.get("changes_vendor", False)):
        return _decision(
            BLOCK,
            "Vendor or tool changes are blocked in Agent Safety Gate V1.",
            ["vendor_change", "blocked_action"],
        )

    if bool(payload.get("contains_legal_advice", False)):
        return _decision(
            BLOCK,
            "Legal advice is outside the safe scope and must not be sent.",
            ["legal_advice", "blocked_action"],
        )

    if bool(payload.get("contains_medical_advice", False)):
        return _decision(
            BLOCK,
            "Medical advice is outside the safe scope and must not be sent.",
            ["medical_advice", "blocked_action"],
        )

    if bool(payload.get("contains_regulated_financial_advice", False)):
        return _decision(
            BLOCK,
            "Regulated financial advice is outside the safe scope and must not be sent.",
            ["regulated_financial_advice", "blocked_action"],
        )

    if bool(payload.get("publishes_content", False)):
        return _decision(
            REQUEST_APPROVAL,
            "Publishing content requires human approval before action.",
            ["publishes_content", "human_approval_required"],
        )

    if bool(payload.get("executes_workflow", False)):
        return _decision(
            REQUEST_APPROVAL,
            "Workflow execution requires human approval before action.",
            ["executes_workflow", "human_approval_required"],
        )

    if customer_facing and contains_private_data:
        return _decision(
            BLOCK,
            "Customer-facing email containing private data is blocked.",
            ["customer_facing_action", "private_data", "blocked_action"],
        )

    if contains_private_data:
        return _decision(
            REQUEST_APPROVAL,
            "Private data requires human approval before action.",
            ["private_data", "human_approval_required"],
        )

    if customer_facing and bool(payload.get("contains_money_claim", False)):
        return _decision(
            REQUEST_APPROVAL,
            "Customer-facing email with money, pricing, refund, or discount language requires human approval.",
            ["customer_facing_action", "money_claim", "human_approval_required"],
        )

    if customer_facing and not human_approved_already:
        return _decision(
            REQUEST_APPROVAL,
            "Customer-facing email requires human approval before sending.",
            ["customer_facing_action", "human_approval_required"],
        )

    return _decision(
        ALLOW,
        "Internal or already-approved email action is allowed by the current safety policy.",
        ["low_risk_action", "allowed_action"],
    )
