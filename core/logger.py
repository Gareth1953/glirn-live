import csv
import os
from datetime import datetime, timezone


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WINNER_LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "cost_log.csv")
AUDIT_LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "provider_audit.csv")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def write_csv_row(file_path, headers, row):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    file_exists = os.path.exists(file_path)

    with open(file_path, "a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        if not file_exists:
            writer.writerow(headers)

        writer.writerow(row)


def safe_preview(text, max_length=160):
    if text is None:
        return ""

    cleaned = str(text).replace("\n", " ").replace("\r", " ")
    return cleaned[:max_length]


def log_winner(
    provider,
    latency,
    estimated_cost,
    status,
    reason,
    baseline_cost,
    avoided_cost,
    response_preview
):
    write_csv_row(
        WINNER_LOG_FILE,
        [
            "timestamp_utc",
            "provider",
            "latency_seconds",
            "estimated_cost",
            "status",
            "reason",
            "baseline_cost",
            "avoided_cost",
            "response_preview"
        ],
        [
            utc_now(),
            provider,
            latency,
            estimated_cost,
            status,
            reason,
            baseline_cost,
            avoided_cost,
            safe_preview(response_preview)
        ]
    )


def log_provider_attempt(
    cycle_id,
    provider,
    status_code,
    latency,
    verified,
    estimated_cost,
    decision,
    reason,
    response_preview=""
):
    write_csv_row(
        AUDIT_LOG_FILE,
        [
            "timestamp_utc",
            "cycle_id",
            "provider",
            "status_code",
            "latency_seconds",
            "verified",
            "estimated_cost",
            "decision",
            "reason",
            "response_preview"
        ],
        [
            utc_now(),
            cycle_id,
            provider,
            status_code,
            latency,
            verified,
            estimated_cost,
            decision,
            reason,
            safe_preview(response_preview)
        ]
    )
