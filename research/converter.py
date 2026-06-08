from opportunities.evaluator import evaluate_opportunity
from opportunities.models import Opportunity
from opportunities.store import append_opportunities
from research.store import list_research_items


MIN_RELEVANCE_SCORE = 0.75


def convert_research_to_opportunities(limit=20):
    research_items = list_research_items(limit=limit)
    opportunities = []

    for item in research_items:
        if item.relevance_score < MIN_RELEVANCE_SCORE:
            continue

        opportunity = Opportunity.create(
            source=f"research:{item.id}",
            category=map_research_category(item.category),
            title=f"Research candidate: {item.title}",
            description=(
                f"{item.summary} Source URL: {item.url}. "
                "Converted from research intake for human review only."
            ),
            confidence=min(max(item.relevance_score, 0.0), 1.0),
            estimated_value=estimate_value(item),
            risk_level=estimate_risk_level(item),
            status="pending_review"
        )
        opportunities.append(evaluate_opportunity(opportunity))

    return append_opportunities(opportunities)


def map_research_category(category):
    if category in {
        "ai_infrastructure_arbitrage",
        "provider_pricing_changes",
        "enterprise_ai_orchestration",
        "latency_optimisation"
    }:
        return "ai_infrastructure"

    return "system_arbitrage"


def estimate_value(item):
    return round(500.0 + (item.relevance_score * 1000.0), 2)


def estimate_risk_level(item):
    if item.relevance_score >= 0.9:
        return "medium"

    return "low"
