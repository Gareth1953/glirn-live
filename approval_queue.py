import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

QUEUE_FILE = Path("approvals/approval_queue.jsonl")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def create_approval_request(route_result: dict) -> dict:
    QUEUE_FILE.parent.mkdir(exist_ok=True)

    approval = {
        "approval_id": str(uuid.uuid4()),
        "created_at": utc_now(),
        "status": "pending_user_approval",
        "route_result": route_result,
        "decision": None,
        "decided_at": None,
        "capital_execution": False,
    }

    with QUEUE_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(approval) + "\n")

    return approval


def list_pending_approvals() -> list[dict]:
    if not QUEUE_FILE.exists():
        return []

    approvals = []

    with QUEUE_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                item = json.loads(line)
                if item.get("status") == "pending_user_approval":
                    approvals.append(item)

    return approvals


def update_approval_decision(approval_id: str, decision: str) -> dict | None:
    if decision not in {"approved", "rejected"}:
        raise ValueError("decision must be approved or rejected")

    if not QUEUE_FILE.exists():
        return None

    updated = None
    records = []

    with QUEUE_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                item = json.loads(line)

                if item.get("approval_id") == approval_id:
                    item["status"] = f"user_{decision}"
                    item["decision"] = decision
                    item["decided_at"] = utc_now()
                    item["capital_execution"] = False
                    updated = item

                records.append(item)

    with QUEUE_FILE.open("w", encoding="utf-8") as f:
        for item in records:
            f.write(json.dumps(item) + "\n")

    return updated