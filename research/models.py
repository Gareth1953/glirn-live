from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class ResearchItem:
    id: str
    source: str
    title: str
    url: str
    summary: str
    category: str
    relevance_score: float
    created_at: str

    @classmethod
    def create(
        cls,
        source,
        title,
        url,
        summary,
        category,
        relevance_score
    ):
        return cls(
            id=str(uuid4()),
            source=source,
            title=title,
            url=url,
            summary=summary,
            category=category,
            relevance_score=relevance_score,
            created_at=datetime.now(timezone.utc).isoformat()
        )

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(
            id=data["id"],
            source=data["source"],
            title=data["title"],
            url=data["url"],
            summary=data["summary"],
            category=data["category"],
            relevance_score=float(data["relevance_score"]),
            created_at=data["created_at"]
        )
