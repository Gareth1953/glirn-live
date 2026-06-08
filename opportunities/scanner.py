from opportunities.evaluator import evaluate_opportunity
from opportunities.models import Opportunity
from opportunities.store import append_opportunities


def scan_opportunities():
    opportunities = [
        Opportunity.create(
            source="stub_ai_infrastructure_scanner",
            category="ai_infrastructure",
            title="GPU capacity cost review",
            description=(
                "Review reserved GPU capacity versus burst usage for model inference workloads. "
                "Requires human approval before any vendor or budget action."
            ),
            confidence=0.72,
            estimated_value=1250.0,
            risk_level="medium"
        ),
        Opportunity.create(
            source="stub_ai_infrastructure_scanner",
            category="ai_infrastructure",
            title="Vector database storage tier review",
            description=(
                "Evaluate whether older embeddings can move to a lower-cost storage tier. "
                "Requires human approval before any infrastructure change."
            ),
            confidence=0.68,
            estimated_value=420.0,
            risk_level="low"
        )
    ]

    evaluated = [
        evaluate_opportunity(opportunity)
        for opportunity in opportunities
    ]

    return append_opportunities(evaluated)
