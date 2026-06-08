from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from uuid import uuid4


VALID_OUTCOME_STATUSES = {
    "pending_review",
    "approved_human_review",
    "rejected_human_review",
    "monitored",
    "expired"
}


@dataclass
class Opportunity:
    id: str
    source: str
    category: str
    title: str
    description: str
    confidence: float
    estimated_value: float
    risk_level: str
    status: str
    created_at: str
    confidence_reason: str
    estimated_cost: float
    estimated_benefit: float
    risk_notes: str
    recommended_action: str

    @classmethod
    def create(
        cls,
        source,
        category,
        title,
        description,
        confidence,
        estimated_value,
        risk_level,
        status="pending_review",
        confidence_reason="Not evaluated yet.",
        estimated_cost=0.0,
        estimated_benefit=0.0,
        risk_notes="Not evaluated yet.",
        recommended_action="review"
    ):
        validate_recommended_action(recommended_action)

        return cls(
            id=str(uuid4()),
            source=source,
            category=category,
            title=title,
            description=description,
            confidence=confidence,
            estimated_value=estimated_value,
            risk_level=risk_level,
            status=status,
            created_at=datetime.now(timezone.utc).isoformat(),
            confidence_reason=confidence_reason,
            estimated_cost=estimated_cost,
            estimated_benefit=estimated_benefit,
            risk_notes=risk_notes,
            recommended_action=recommended_action
        )

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        recommended_action = data.get("recommended_action", "review")
        validate_recommended_action(recommended_action)

        return cls(
            id=data["id"],
            source=data["source"],
            category=data["category"],
            title=data["title"],
            description=data["description"],
            confidence=float(data["confidence"]),
            estimated_value=float(data["estimated_value"]),
            risk_level=data["risk_level"],
            status=data["status"],
            created_at=data["created_at"],
            confidence_reason=data.get("confidence_reason", "Legacy opportunity imported before evaluation."),
            estimated_cost=float(data.get("estimated_cost", 0.0)),
            estimated_benefit=float(data.get("estimated_benefit", data.get("estimated_value", 0.0))),
            risk_notes=data.get("risk_notes", "Legacy opportunity imported before evaluation."),
            recommended_action=recommended_action
        )


@dataclass
class OpportunityApproval:
    id: str
    opportunity_id: str
    action: str
    status: str
    capital_execution: bool
    created_at: str
    reviewer_note: str
    realized_value: float | None

    @classmethod
    def create(cls, opportunity_id, action, status, reviewer_note="", realized_value=None):
        validate_outcome_status(status)

        return cls(
            id=str(uuid4()),
            opportunity_id=opportunity_id,
            action=action,
            status=status,
            capital_execution=False,
            created_at=datetime.now(timezone.utc).isoformat(),
            reviewer_note=reviewer_note,
            realized_value=realized_value
        )

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(
            id=data["id"],
            opportunity_id=data["opportunity_id"],
            action=data["action"],
            status=data["status"],
            capital_execution=bool(data["capital_execution"]),
            created_at=data["created_at"],
            reviewer_note=data.get("reviewer_note", ""),
            realized_value=data.get("realized_value")
        )


def validate_recommended_action(recommended_action):
    if recommended_action not in {"review", "monitor", "reject"}:
        raise ValueError("recommended_action must be one of: review, monitor, reject")


def validate_outcome_status(outcome_status):
    if outcome_status not in VALID_OUTCOME_STATUSES:
        raise ValueError(
            "outcome_status must be one of: pending_review, approved_human_review, "
            "rejected_human_review, monitored, expired"
        )
