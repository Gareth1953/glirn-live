from research.models import ResearchItem
from research.store import append_research_items


def intake_research_items():
    items = [
        ResearchItem.create(
            source="stub_research_intake",
            title="AI infrastructure arbitrage watchlist",
            url="internal://research/ai-infrastructure-arbitrage",
            summary=(
                "Track capacity, utilization, and reserved compute gaps across AI infrastructure. "
                "This is intake only and requires human review before action."
            ),
            category="ai_infrastructure_arbitrage",
            relevance_score=0.91
        ),
        ResearchItem.create(
            source="stub_research_intake",
            title="Provider pricing change monitor",
            url="internal://research/provider-pricing-changes",
            summary=(
                "Monitor model provider pricing changes and routing implications for enterprise workloads. "
                "No provider or capital action is executed by this intake."
            ),
            category="provider_pricing_changes",
            relevance_score=0.88
        ),
        ResearchItem.create(
            source="stub_research_intake",
            title="Enterprise AI orchestration patterns",
            url="internal://research/enterprise-ai-orchestration",
            summary=(
                "Capture orchestration patterns that may improve routing, fallback, and governance controls."
            ),
            category="enterprise_ai_orchestration",
            relevance_score=0.82
        ),
        ResearchItem.create(
            source="stub_research_intake",
            title="Latency optimisation review queue",
            url="internal://research/latency-optimisation",
            summary=(
                "Track non-crypto system arbitrage signals from latency, caching, and provider selection improvements."
            ),
            category="latency_optimisation",
            relevance_score=0.79
        )
    ]

    return append_research_items(items)
