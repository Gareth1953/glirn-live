import json
import os

from opportunities.models import Opportunity, OpportunityApproval, validate_outcome_status


OPPORTUNITIES_FILE = os.path.join("data", "opportunities.jsonl")
APPROVALS_FILE = os.path.join("data", "opportunity_approvals.jsonl")


def ensure_store_dir():
    directory = os.path.dirname(OPPORTUNITIES_FILE)

    if directory:
        os.makedirs(directory, exist_ok=True)


def ensure_parent_dir(path):
    directory = os.path.dirname(path)

    if directory:
        os.makedirs(directory, exist_ok=True)


def append_opportunity(opportunity):
    ensure_parent_dir(OPPORTUNITIES_FILE)

    with open(OPPORTUNITIES_FILE, "a", encoding="utf-8") as file:
        file.write(json.dumps(opportunity.to_dict(), sort_keys=True) + "\n")

    return opportunity


def append_opportunities(opportunities):
    return [
        append_opportunity(opportunity)
        for opportunity in opportunities
    ]


def list_opportunities(limit=20):
    opportunities = read_all_opportunities()
    return opportunities[-limit:]


def read_all_opportunities():
    if not os.path.exists(OPPORTUNITIES_FILE):
        return []

    opportunities = []

    with open(OPPORTUNITIES_FILE, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()

            if not line:
                continue

            opportunities.append(Opportunity.from_dict(json.loads(line)))

    return opportunities


def find_opportunity(opportunity_id):
    for opportunity in read_all_opportunities():
        if opportunity.id == opportunity_id:
            return opportunity

    return None


def update_opportunity_status(opportunity_id, status):
    opportunities = read_all_opportunities()
    updated = None

    for opportunity in opportunities:
        if opportunity.id == opportunity_id:
            opportunity.status = status
            updated = opportunity
            break

    if updated is None:
        return None

    ensure_parent_dir(OPPORTUNITIES_FILE)

    with open(OPPORTUNITIES_FILE, "w", encoding="utf-8") as file:
        for opportunity in opportunities:
            file.write(json.dumps(opportunity.to_dict(), sort_keys=True) + "\n")

    return updated


def append_approval(approval):
    ensure_parent_dir(APPROVALS_FILE)

    with open(APPROVALS_FILE, "a", encoding="utf-8") as file:
        file.write(json.dumps(approval.to_dict(), sort_keys=True) + "\n")

    return approval


def list_approvals(limit=20):
    approvals = read_all_approvals()
    return approvals[-limit:]


def read_all_approvals():
    if not os.path.exists(APPROVALS_FILE):
        return []

    approvals = []

    with open(APPROVALS_FILE, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()

            if not line:
                continue

            approvals.append(OpportunityApproval.from_dict(json.loads(line)))

    return approvals


def get_opportunity_analytics():
    opportunities = read_all_opportunities()
    approvals = read_all_approvals()
    total_opportunities = len(opportunities)
    count_by_status = {}
    count_by_recommended_action = {}
    total_confidence = 0.0
    total_estimated_value = 0.0
    total_estimated_benefit = 0.0
    total_realized_value = 0.0
    approval_counts = {
        "approved": 0,
        "rejected": 0,
        "monitored": 0
    }

    for opportunity in opportunities:
        count_by_status[opportunity.status] = count_by_status.get(opportunity.status, 0) + 1
        count_by_recommended_action[opportunity.recommended_action] = (
            count_by_recommended_action.get(opportunity.recommended_action, 0) + 1
        )
        total_confidence += opportunity.confidence
        total_estimated_value += opportunity.estimated_value
        total_estimated_benefit += opportunity.estimated_benefit

    for approval in approvals:
        if approval.status == "approved_human_review":
            approval_counts["approved"] += 1
        elif approval.status == "rejected_human_review":
            approval_counts["rejected"] += 1
        elif approval.status == "monitored":
            approval_counts["monitored"] += 1

        if approval.action == "outcome" and approval.realized_value is not None:
            total_realized_value += float(approval.realized_value)

    return {
        "total_opportunities": total_opportunities,
        "count_by_status": count_by_status,
        "count_by_recommended_action": count_by_recommended_action,
        "average_confidence": round(total_confidence / total_opportunities, 4) if total_opportunities else 0,
        "total_estimated_value": round(total_estimated_value, 4),
        "total_estimated_benefit": round(total_estimated_benefit, 4),
        "total_realized_value": round(total_realized_value, 4),
        "approval_counts": approval_counts,
        "capital_execution": False
    }


def record_opportunity_approval(opportunity_id, action, reviewer_note=""):
    status_by_action = {
        "approve": "approved_human_review",
        "reject": "rejected_human_review"
    }
    status = status_by_action[action]
    opportunity = update_opportunity_status(opportunity_id, status)

    if opportunity is None:
        return None, None

    approval = append_approval(OpportunityApproval.create(
        opportunity_id=opportunity_id,
        action=action,
        status=status,
        reviewer_note=reviewer_note
    ))

    return opportunity, approval


def record_opportunity_outcome(opportunity_id, outcome_status, reviewer_note="", realized_value=None):
    validate_outcome_status(outcome_status)
    opportunity = update_opportunity_status(opportunity_id, outcome_status)

    if opportunity is None:
        return None, None

    approval = append_approval(OpportunityApproval.create(
        opportunity_id=opportunity_id,
        action="outcome",
        status=outcome_status,
        reviewer_note=reviewer_note,
        realized_value=realized_value
    ))

    return opportunity, approval
