import json
import os

from research.models import ResearchItem


RESEARCH_FILE = os.path.join("data", "research_items.jsonl")


def ensure_parent_dir(path):
    directory = os.path.dirname(path)

    if directory:
        os.makedirs(directory, exist_ok=True)


def append_research_item(item):
    ensure_parent_dir(RESEARCH_FILE)

    with open(RESEARCH_FILE, "a", encoding="utf-8") as file:
        file.write(json.dumps(item.to_dict(), sort_keys=True) + "\n")

    return item


def append_research_items(items):
    return [
        append_research_item(item)
        for item in items
    ]


def list_research_items(limit=20):
    if not os.path.exists(RESEARCH_FILE):
        return []

    items = []

    with open(RESEARCH_FILE, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()

            if not line:
                continue

            items.append(ResearchItem.from_dict(json.loads(line)))

    return items[-limit:]
