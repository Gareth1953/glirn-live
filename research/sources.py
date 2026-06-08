import json
import os


RESEARCH_SOURCES_FILE = os.path.join("config", "research_sources.json")


def load_research_sources(path=RESEARCH_SOURCES_FILE):
    if not os.path.exists(path):
        return []

    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)

    return data.get("sources", [])


def save_research_sources(sources, path=RESEARCH_SOURCES_FILE):
    directory = os.path.dirname(path)

    if directory:
        os.makedirs(directory, exist_ok=True)

    with open(path, "w", encoding="utf-8") as file:
        json.dump({"sources": sources}, file, indent=4)


def toggle_research_source(source_name, path=RESEARCH_SOURCES_FILE):
    sources = load_research_sources(path)

    for source in sources:
        if source.get("name") == source_name:
            source["enabled"] = not bool(source.get("enabled", False))
            save_research_sources(sources, path)
            return source

    return None
