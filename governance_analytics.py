import json
from datetime import datetime, timezone
from pathlib import Path

QUEUE_FILE = Path("approvals/approval_queue.jsonl")
LEDGER_FILE = Path("logs/approval_ledger.jsonl")


def _read_jsonl(path):
    if not path.exists():
        return []

    records = []

    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue

            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    return records


def _parse_timestamp(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _hours_between(start, end):
    if not start or not end:
        return None

    return (end - start).total_seconds() / 3600


def _average(values):
    values = [value for value in values if value is not None]
    return round(sum(values) / len(values), 4) if values else 0


def _increment(counts, key):
    key = str(key or "unknown")
    counts[key] = counts.get(key, 0) + 1


def _queue_provider(record):
    route_result = record.get("route_result", {}) or {}
    return route_result.get("provider") or route_result.get("provider_name") or "unknown"


def _queue_task_type(record):
    route_result = record.get("route_result", {}) or {}
    return route_result.get("task_type") or "unknown"


def _ledger_provider(record):
    raw_event = record.get("raw_event", {}) or {}
    return record.get("provider") or raw_event.get("provider") or "unknown"


def _ledger_task_type(record):
    raw_event = record.get("raw_event", {}) or {}
    return record.get("task_type") or raw_event.get("task_type") or "unknown"


def _build_decision_records(queue_records, ledger_records):
    decisions = {}

    for record in queue_records:
        decision = record.get("decision")
        if decision not in {"approved", "rejected"}:
            status = record.get("status")
            if status == "user_approved":
                decision = "approved"
            elif status == "user_rejected":
                decision = "rejected"

        if decision not in {"approved", "rejected"}:
            continue

        approval_id = record.get("approval_id") or f"queue:{len(decisions)}"
        decisions[approval_id] = {
            "decision": decision,
            "created_at": _parse_timestamp(record.get("created_at")),
            "decided_at": _parse_timestamp(record.get("decided_at")),
            "provider": _queue_provider(record),
            "task_type": _queue_task_type(record),
        }

    for index, record in enumerate(ledger_records):
        decision = record.get("decision")
        if decision not in {"approved", "rejected"}:
            continue

        approval_id = record.get("approval_id") or f"ledger:{index}"
        if approval_id in decisions:
            decisions[approval_id]["provider"] = _ledger_provider(record)
            decisions[approval_id]["task_type"] = _ledger_task_type(record)
            continue

        decisions[approval_id] = {
            "decision": decision,
            "created_at": None,
            "decided_at": _parse_timestamp(record.get("timestamp")),
            "provider": _ledger_provider(record),
            "task_type": _ledger_task_type(record),
        }

    return list(decisions.values())


def get_governance_analytics(now=None):
    now = now or datetime.now(timezone.utc)
    queue_records = _read_jsonl(QUEUE_FILE)
    ledger_records = _read_jsonl(LEDGER_FILE)
    decision_records = _build_decision_records(queue_records, ledger_records)

    pending_records = [
        record
        for record in queue_records
        if record.get("status") == "pending_user_approval"
    ]
    approved_records = [
        record
        for record in decision_records
        if record.get("decision") == "approved"
    ]
    rejected_records = [
        record
        for record in decision_records
        if record.get("decision") == "rejected"
    ]

    approvals_by_provider = {}
    approvals_by_task_type = {}
    rejections_by_provider = {}
    rejections_by_task_type = {}

    for record in approved_records:
        _increment(approvals_by_provider, record.get("provider"))
        _increment(approvals_by_task_type, record.get("task_type"))

    for record in rejected_records:
        _increment(rejections_by_provider, record.get("provider"))
        _increment(rejections_by_task_type, record.get("task_type"))

    approval_hours = [
        _hours_between(record.get("created_at"), record.get("decided_at"))
        for record in approved_records
    ]
    rejection_hours = [
        _hours_between(record.get("created_at"), record.get("decided_at"))
        for record in rejected_records
    ]
    pending_hours = [
        _hours_between(_parse_timestamp(record.get("created_at")), now)
        for record in pending_records
    ]

    approved_count = len(approved_records)
    rejected_count = len(rejected_records)
    total_decisions = approved_count + rejected_count

    return {
        "pending_count": len(pending_records),
        "approved_count": approved_count,
        "rejected_count": rejected_count,
        "approval_rate": round((approved_count / total_decisions) * 100, 4) if total_decisions else 0,
        "average_approval_hours": _average(approval_hours),
        "average_rejection_hours": _average(rejection_hours),
        "oldest_pending_hours": round(max(pending_hours), 4) if pending_hours else 0,
        "approvals_by_provider": approvals_by_provider,
        "rejections_by_provider": rejections_by_provider,
        "approvals_by_task_type": approvals_by_task_type,
        "rejections_by_task_type": rejections_by_task_type,
        "capital_execution": False,
    }
