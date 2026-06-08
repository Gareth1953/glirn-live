import csv
import os
from datetime import datetime, timezone

LOG_FILE = "logs/route_decisions.csv"


def initialize_audit_log():
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, mode="w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)

            writer.writerow([
                "timestamp",
                "task",
                "task_type",
                "provider",
                "latency",
                "estimated_cost",
                "status"
            ])


def log_route_decision(
    task,
    task_type,
    provider,
    latency,
    estimated_cost,
    status
):
    initialize_audit_log()

    with open(LOG_FILE, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        writer.writerow([
            datetime.now(timezone.utc).isoformat(),
            task,
            task_type,
            provider,
            latency,
            estimated_cost,
            status
        ])
