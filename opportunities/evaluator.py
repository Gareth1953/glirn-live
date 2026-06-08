from opportunities.models import validate_recommended_action


def evaluate_opportunity(opportunity):
    estimated_cost = estimate_review_cost(opportunity)
    estimated_benefit = max(float(opportunity.estimated_value) - estimated_cost, 0.0)
    recommended_action = recommend_action(
        confidence=opportunity.confidence,
        risk_level=opportunity.risk_level,
        estimated_benefit=estimated_benefit
    )
    validate_recommended_action(recommended_action)

    opportunity.confidence_reason = build_confidence_reason(opportunity)
    opportunity.estimated_cost = estimated_cost
    opportunity.estimated_benefit = estimated_benefit
    opportunity.risk_notes = build_risk_notes(opportunity)
    opportunity.recommended_action = recommended_action

    return opportunity


def estimate_review_cost(opportunity):
    base_cost = 150.0

    if opportunity.risk_level == "medium":
        return base_cost + 100.0

    if opportunity.risk_level == "high":
        return base_cost + 250.0

    return base_cost


def recommend_action(confidence, risk_level, estimated_benefit):
    if risk_level == "high" or confidence < 0.45:
        return "reject"

    if confidence < 0.7 or estimated_benefit < 300:
        return "monitor"

    return "review"


def build_confidence_reason(opportunity):
    return (
        f"Stub evaluation based on source={opportunity.source}, "
        f"category={opportunity.category}, confidence={opportunity.confidence}."
    )


def build_risk_notes(opportunity):
    return (
        f"Risk level is {opportunity.risk_level}. Human review is required; "
        "no capital execution is available from this engine."
    )
