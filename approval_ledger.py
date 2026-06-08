import json
from datetime import datetime, timezone
from pathlib import Path

LEDGER_FILE = Path("logs/approval_ledger.jsonl")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def record_approval_event(event: dict) -> dict:
    LEDGER_FILE.parent.mkdir(exist_ok=True)

    ledger_entry = {
        "timestamp": utc_now(),
        "event_type": event.get("event_type", "approval_event"),
        "approval_id": event.get("approval_id"),
        "decision": event.get("decision"),
        "provider": event.get("provider"),
        "task_type": event.get("task_type"),
        "estimated_cost": event.get("estimated_cost"),
        "avoided_cost": event.get("avoided_cost"),
        "capital_execution": False,
        "raw_event": event,
    }

    with LEDGER_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(ledger_entry) + "\n")

    return ledger_entry


def list_approval_events(limit: int = 50) -> list[dict]:
    if not LEDGER_FILE.exists():
        return []

    events = []

    with LEDGER_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))

    return events[-limit:]
