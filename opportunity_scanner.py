from datetime import datetime, timezone

OPPORTUNITY_CATEGORIES = [
    "duplicate_software_subscriptions",
    "overlapping_ai_tools",
    "unused_saas_licences",
    "excess_ai_api_spend",
    "expensive_manual_processes",
    "inefficient_reporting_workflows",
    "avoidable_recurring_costs",
]

DIFFICULTY_SCORE = {
    "low": 100,
    "medium": 70,
    "high": 35,
}


def calculate_gareth_score(
    implementation_difficulty,
    global_applicability,
    recurring_value,
    operational_complexity,
):
    difficulty_score = DIFFICULTY_SCORE.get(implementation_difficulty, 50)
    global_score = 100 if global_applicability else 50
    recurring_score = 100 if recurring_value else 55
    complexity_score = DIFFICULTY_SCORE.get(operational_complexity, 50)

    return round(
        (difficulty_score * 0.25)
        + (100 * 0.2)
        + (100 * 0.2)
        + (global_score * 0.15)
        + (recurring_score * 0.1)
        + (complexity_score * 0.1)
    )


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def scan_opportunity_stubs():
    scanned_at = utc_now()

    return [
        {
            "id": "wasted-money-overlapping-ai-tools",
            "category": "overlapping_ai_tools",
            "title": "Duplicate AI Tool Spend",
            "description": "Multiple AI subscriptions appear to solve the same writing, research, and summarisation jobs.",
            "confidence": 88,
            "estimated_value": 12000.0,
            "estimated_benefit": 12000.0,
            "estimated_annual_savings": 12000.0,
            "implementation_difficulty": "low",
            "gareth_score": calculate_gareth_score("low", True, True, "low"),
            "risk_level": "medium",
            "status": "pending_review",
            "recommended_action": "review",
            "reason": "High value, low complexity, low capital requirement.",
            "scanned_at": scanned_at,
            "capital_execution": False,
            "fetching_enabled": False,
            "scraping_enabled": False,
            "execution_enabled": False,
        },
        {
            "id": "wasted-money-duplicate-software-subscriptions",
            "category": "duplicate_software_subscriptions",
            "title": "Duplicate Software Subscriptions",
            "description": "Several paid tools appear to overlap across CRM, project tracking, forms, and reporting.",
            "confidence": 82,
            "estimated_value": 8400.0,
            "estimated_benefit": 8400.0,
            "estimated_annual_savings": 8400.0,
            "implementation_difficulty": "low",
            "gareth_score": calculate_gareth_score("low", True, True, "low"),
            "risk_level": "low",
            "status": "pending_review",
            "recommended_action": "review",
            "reason": "Recurring software spend can often be reduced after a simple human-approved audit.",
            "scanned_at": scanned_at,
            "capital_execution": False,
            "fetching_enabled": False,
            "scraping_enabled": False,
            "execution_enabled": False,
        },
        {
            "id": "wasted-money-unused-saas-licences",
            "category": "unused_saas_licences",
            "title": "Unused SaaS Licences",
            "description": "Paid seats may be assigned to inactive users or teams no longer using the software.",
            "confidence": 76,
            "estimated_value": 6000.0,
            "estimated_benefit": 6000.0,
            "estimated_annual_savings": 6000.0,
            "implementation_difficulty": "medium",
            "gareth_score": calculate_gareth_score("medium", True, True, "medium"),
            "risk_level": "medium",
            "status": "pending_review",
            "recommended_action": "review",
            "reason": "Seat-level clean-up can create recurring savings, but needs client confirmation.",
            "scanned_at": scanned_at,
            "capital_execution": False,
            "fetching_enabled": False,
            "scraping_enabled": False,
            "execution_enabled": False,
        },
        {
            "id": "wasted-money-excess-ai-api-spend",
            "category": "excess_ai_api_spend",
            "title": "Excess AI/API Spend",
            "description": "AI API usage may include expensive models for low-value tasks that cheaper routes can handle.",
            "confidence": 84,
            "estimated_value": 15000.0,
            "estimated_benefit": 15000.0,
            "estimated_annual_savings": 15000.0,
            "implementation_difficulty": "medium",
            "gareth_score": calculate_gareth_score("medium", True, True, "medium"),
            "risk_level": "medium",
            "status": "pending_review",
            "recommended_action": "review",
            "reason": "Potentially high annual savings, but any provider change requires Gareth approval.",
            "scanned_at": scanned_at,
            "capital_execution": False,
            "fetching_enabled": False,
            "scraping_enabled": False,
            "execution_enabled": False,
        },
        {
            "id": "wasted-money-expensive-manual-processes",
            "category": "expensive_manual_processes",
            "title": "Expensive Manual Admin Time",
            "description": "Repeated admin work may be consuming senior staff time that could be reduced with simple process changes.",
            "confidence": 72,
            "estimated_value": 9600.0,
            "estimated_benefit": 9600.0,
            "estimated_annual_savings": 9600.0,
            "implementation_difficulty": "medium",
            "gareth_score": calculate_gareth_score("medium", True, True, "medium"),
            "risk_level": "low",
            "status": "pending_review",
            "recommended_action": "review",
            "reason": "Staff time savings can be valuable, but the workflow should be confirmed manually.",
            "scanned_at": scanned_at,
            "capital_execution": False,
            "fetching_enabled": False,
            "scraping_enabled": False,
            "execution_enabled": False,
        },
        {
            "id": "wasted-money-inefficient-reporting-workflows",
            "category": "inefficient_reporting_workflows",
            "title": "Inefficient Reporting Workflow",
            "description": "Manual report preparation may duplicate data entry and review effort every week.",
            "confidence": 70,
            "estimated_value": 7200.0,
            "estimated_benefit": 7200.0,
            "estimated_annual_savings": 7200.0,
            "implementation_difficulty": "medium",
            "gareth_score": calculate_gareth_score("medium", True, True, "medium"),
            "risk_level": "low",
            "status": "pending_review",
            "recommended_action": "monitor",
            "reason": "Likely recurring waste, but process detail is needed before recommending change.",
            "scanned_at": scanned_at,
            "capital_execution": False,
            "fetching_enabled": False,
            "scraping_enabled": False,
            "execution_enabled": False,
        },
        {
            "id": "wasted-money-avoidable-recurring-costs",
            "category": "avoidable_recurring_costs",
            "title": "Avoidable Recurring Business Costs",
            "description": "Routine services and subscriptions may no longer match current business usage.",
            "confidence": 66,
            "estimated_value": 4800.0,
            "estimated_benefit": 4800.0,
            "estimated_annual_savings": 4800.0,
            "implementation_difficulty": "low",
            "gareth_score": calculate_gareth_score("low", True, True, "low"),
            "risk_level": "low",
            "status": "pending_review",
            "recommended_action": "monitor",
            "reason": "Good low-capital target once current invoices are confirmed by a human.",
            "scanned_at": scanned_at,
            "capital_execution": False,
            "fetching_enabled": False,
            "scraping_enabled": False,
            "execution_enabled": False,
        },
    ]


def get_scanner_analytics(opportunities=None):
    opportunities = opportunities if opportunities is not None else scan_opportunity_stubs()
    passed_filter_items = [
        opportunity
        for opportunity in opportunities
        if float(opportunity.get("confidence", 0) or 0) >= 60
    ]
    worth_reviewing_items = [
        opportunity
        for opportunity in passed_filter_items
        if opportunity.get("status") == "pending_review"
    ]

    category_counts = {}
    for opportunity in opportunities:
        category = str(opportunity.get("category", "unknown"))
        category_counts[category] = category_counts.get(category, 0) + 1

    savings_values = [
        float(opportunity.get("estimated_annual_savings", 0) or 0)
        for opportunity in opportunities
    ]
    gareth_scores = [
        float(opportunity.get("gareth_score", 0) or 0)
        for opportunity in opportunities
    ]
    highest_value = max(
        opportunities,
        key=lambda opportunity: float(opportunity.get("estimated_annual_savings", 0) or 0),
        default=None,
    )

    return {
        "opportunities_scanned": len(opportunities),
        "passed_filters": len(passed_filter_items),
        "worth_reviewing": len(worth_reviewing_items),
        "total_wasted_money_opportunities": len(opportunities),
        "average_estimated_annual_savings": round(sum(savings_values) / len(savings_values), 2) if savings_values else 0,
        "highest_value_opportunity": highest_value,
        "average_gareth_score": round(sum(gareth_scores) / len(gareth_scores), 2) if gareth_scores else 0,
        "categories": category_counts,
        "capital_execution": False,
        "fetching_enabled": False,
        "scraping_enabled": False,
        "execution_enabled": False,
    }


def get_scanner_results():
    opportunities = scan_opportunity_stubs()

    return {
        "opportunities": opportunities,
        "analytics": get_scanner_analytics(opportunities),
        "categories": OPPORTUNITY_CATEGORIES,
        "capital_execution": False,
        "fetching_enabled": False,
        "scraping_enabled": False,
        "execution_enabled": False,
    }
