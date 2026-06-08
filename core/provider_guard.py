import json
import os

SCORES_FILE = "analytics/provider_scores.json"


def load_provider_scores():
    if not os.path.exists(SCORES_FILE):
        return {}

    with open(SCORES_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def provider_allowed(provider_name):
    scores = load_provider_scores()

    if provider_name not in scores:
        return True

    provider = scores[provider_name]

    failures = provider.get("failure_count", 0)
    score = provider.get("score", 100)

    if failures >= 3:
        return False

    if score <= 10:
        return False

    return True