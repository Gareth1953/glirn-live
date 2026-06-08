import json
import os

SCORES_FILE = "analytics/provider_scores.json"
RESET_SCORE = {
    "success_count": 0,
    "failure_count": 0,
    "average_latency": 0,
    "average_cost": 0,
    "score": 100
}


def load_scores():
    if not os.path.exists(SCORES_FILE):
        return {}

    with open(SCORES_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def save_scores(scores):
    with open(SCORES_FILE, "w", encoding="utf-8") as file:
        json.dump(scores, file, indent=4)


def reset_provider_score(provider):
    scores = load_scores()
    scores[provider] = RESET_SCORE.copy()
    save_scores(scores)
    return scores[provider]


def update_provider_score(provider, success, latency, cost):
    scores = load_scores()

    if provider not in scores:
        scores[provider] = RESET_SCORE.copy()

    data = scores[provider]

    if success:
        data["success_count"] += 1
    else:
        data["failure_count"] += 1

    total_attempts = data["success_count"] + data["failure_count"]

    if success:
        data["average_latency"] = (
            (data["average_latency"] * (data["success_count"] - 1)) + latency
        ) / data["success_count"]

        data["average_cost"] = (
            (data["average_cost"] * (data["success_count"] - 1)) + cost
        ) / data["success_count"]

    reliability = data["success_count"] / total_attempts if total_attempts else 1

    latency_penalty = min(data["average_latency"] * 3, 30)
    cost_penalty = min(data["average_cost"] * 1000, 30)
    failure_penalty = data["failure_count"] * 5

    data["score"] = max(
        0,
        round((reliability * 100) - latency_penalty - cost_penalty - failure_penalty, 2)
    )

    scores[provider] = data
    save_scores(scores)

    return data
