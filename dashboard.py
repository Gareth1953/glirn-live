import csv
import json
import os

PROVIDER_AUDIT_LOG_FILE = "logs/provider_audit.csv"
ROUTE_DECISIONS_LOG_FILE = "logs/route_decisions.csv"
COST_LOG_FILE = "logs/cost_log.csv"
SCORES_FILE = "analytics/provider_scores.json"
PROVIDERS_CONFIG_FILE = "config/providers.json"


def print_section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def load_json(path):
    if not os.path.exists(path):
        return {}

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def read_csv_rows(path):
    if not os.path.exists(path):
        return []

    with open(path, "r", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def get_provider_scores_data():
    scores = load_json(SCORES_FILE)
    providers = []

    for provider, data in scores.items():
        status = "ACTIVE"

        if data.get("score", 0) <= 10 or data.get("failure_count", 0) >= 3:
            status = "BLOCKED"

        providers.append({
            "provider": provider,
            "status": status,
            "score": data.get("score"),
            "success_count": data.get("success_count"),
            "failure_count": data.get("failure_count"),
            "average_latency": data.get("average_latency"),
            "average_cost": data.get("average_cost")
        })

    return providers


def get_provider_name_warnings():
    config = load_json(PROVIDERS_CONFIG_FILE)
    scores = load_json(SCORES_FILE)

    configured_names = {
        provider.get("name")
        for provider in config.get("providers", [])
        if provider.get("name")
    }
    scored_names = set(scores.keys())

    return {
        "configured_without_scores": sorted(configured_names - scored_names),
        "scored_without_config": sorted(scored_names - configured_names)
    }


def get_recent_provider_audit_data(limit=10):
    rows = read_csv_rows(PROVIDER_AUDIT_LOG_FILE)
    return rows[-limit:]


def get_recent_route_decisions_data(limit=10):
    rows = read_csv_rows(ROUTE_DECISIONS_LOG_FILE)
    return rows[-limit:]


def parse_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def get_routing_history_data(limit=20):
    rows = read_csv_rows(ROUTE_DECISIONS_LOG_FILE)
    provider_win_counts = {}
    latency_totals = {}
    cost_totals = {}
    provider_counts = {}

    for row in rows:
        provider = row.get("provider") or "unknown"
        latency = parse_float(row.get("latency"))
        cost = parse_float(row.get("estimated_cost"))

        provider_win_counts[provider] = provider_win_counts.get(provider, 0) + 1
        latency_totals[provider] = latency_totals.get(provider, 0.0) + latency
        cost_totals[provider] = cost_totals.get(provider, 0.0) + cost
        provider_counts[provider] = provider_counts.get(provider, 0) + 1

    average_latency_per_provider = {}
    average_cost_per_provider = {}

    for provider, count in provider_counts.items():
        average_latency_per_provider[provider] = latency_totals[provider] / count
        average_cost_per_provider[provider] = cost_totals[provider] / count

    return {
        "total_route_count": len(rows),
        "provider_win_counts": provider_win_counts,
        "average_latency_per_provider": average_latency_per_provider,
        "average_cost_per_provider": average_cost_per_provider,
        "recent_routing_history": rows[-limit:]
    }


def get_cost_summary_data():
    rows = read_csv_rows(COST_LOG_FILE)
    total_estimated_cost = 0.0
    total_avoided_cost = 0.0
    provider_wins = {}

    for row in rows:
        provider = row.get("provider", "unknown")
        provider_wins[provider] = provider_wins.get(provider, 0) + 1

        try:
            total_estimated_cost += float(row.get("estimated_cost", 0) or 0)
        except ValueError:
            pass

        try:
            total_avoided_cost += float(row.get("avoided_cost", 0) or 0)
        except ValueError:
            pass

    return {
        "total_routed_runs": len(rows),
        "total_estimated_cost": total_estimated_cost,
        "total_avoided_cost": total_avoided_cost,
        "provider_wins": provider_wins
    }


def get_dashboard_data():
    return {
        "provider_warnings": get_provider_name_warnings(),
        "provider_scores": get_provider_scores_data(),
        "cost_summary": get_cost_summary_data(),
        "routing_history": get_routing_history_data(limit=20),
        "recent_route_decisions": get_recent_route_decisions_data(limit=10),
        "recent_provider_audit_events": get_recent_provider_audit_data(limit=10)
    }


def show_provider_scores():
    providers = get_provider_scores_data()

    print_section("PROVIDER INTELLIGENCE SCORES")

    if not providers:
        print("No provider score data found.")
        return

    for provider in providers:
        print(f"\nProvider: {provider['provider']}")
        print(f"Status: {provider['status']}")
        print(f"Score: {provider['score']}")
        print(f"Success count: {provider['success_count']}")
        print(f"Failure count: {provider['failure_count']}")
        print(f"Average latency: {provider['average_latency']}")
        print(f"Average cost: {provider['average_cost']}")


def show_provider_name_warnings():
    warnings = get_provider_name_warnings()
    missing_scores = warnings["configured_without_scores"]
    unknown_scores = warnings["scored_without_config"]

    if not missing_scores and not unknown_scores:
        return

    print_section("PROVIDER CONFIG WARNINGS")

    if missing_scores:
        print("Configured providers without scores:")
        for provider in missing_scores:
            print(f"- {provider}")

    if unknown_scores:
        print("Scored providers not present in config:")
        for provider in unknown_scores:
            print(f"- {provider}")


def show_recent_provider_audit(limit=10):
    rows = read_csv_rows(PROVIDER_AUDIT_LOG_FILE)

    print_section("RECENT PROVIDER AUDIT EVENTS")

    if not rows:
        print("No provider audit log data found.")
        return

    for row in rows[-limit:]:
        print(
            f"{row.get('timestamp_utc') or row.get('timestamp')} | "
            f"{row.get('provider')} | "
            f"{row.get('decision', 'route')} | "
            f"{row.get('status_code', row.get('status'))} | "
            f"{row.get('reason', row.get('task', ''))}"
        )


def show_recent_route_decisions(limit=10):
    rows = read_csv_rows(ROUTE_DECISIONS_LOG_FILE)

    print_section("RECENT ROUTE DECISIONS")

    if not rows:
        print("No route decision data found.")
        return

    for row in rows[-limit:]:
        print(
            f"{row.get('timestamp')} | "
            f"{row.get('task_type')} | "
            f"{row.get('provider')} | "
            f"{row.get('status')} | "
            f"cost={row.get('estimated_cost')} | "
            f"latency={row.get('latency')}"
        )


def show_cost_summary():
    summary = get_cost_summary_data()

    print_section("COST ROUTING SUMMARY")

    if summary["total_routed_runs"] == 0:
        print("No cost log data found.")
        return

    print(f"Total routed runs: {summary['total_routed_runs']}")
    print(f"Total estimated cost: {summary['total_estimated_cost']}")
    print(f"Total avoided cost: {summary['total_avoided_cost']}")

    print("\nProvider wins:")

    for provider, count in summary["provider_wins"].items():
        print(f"- {provider}: {count}")


def main():
    print("\nArbitrageEngineV1 Dashboard")
    print("Phase 3.2: Dashboard Intelligence View")

    show_provider_name_warnings()
    show_provider_scores()
    show_cost_summary()
    show_recent_route_decisions(limit=10)
    show_recent_provider_audit(limit=10)


if __name__ == "__main__":
    main()
