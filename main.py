import json
import os
import sys

from core.providers import Provider
from core.router import route_task
from audit_logger import log_route_decision


def load_env_file(path=".env"):
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()

            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip().strip('"').strip("'")


def load_provider_settings(path="config/providers.json"):
    defaults = {
        "timeout_seconds": 10,
        "hard_timeout_seconds": 10
    }

    if not os.path.exists(path):
        return defaults

    try:
        with open(path, "r", encoding="utf-8") as file:
            config = json.load(file)
    except (OSError, json.JSONDecodeError):
        return defaults

    timeout_seconds = config.get("timeout_seconds", defaults["timeout_seconds"])
    hard_timeout_seconds = config.get("hard_timeout_seconds", timeout_seconds)

    return {
        "timeout_seconds": timeout_seconds,
        "hard_timeout_seconds": hard_timeout_seconds
    }


def load_provider_config(path="config/providers.json"):
    if not os.path.exists(path):
        return []

    try:
        with open(path, "r", encoding="utf-8") as file:
            config = json.load(file)
    except (OSError, json.JSONDecodeError):
        return []

    return config.get("providers", [])


def classify_task(task_text):
    text = task_text.lower()

    if any(word in text for word in ["code", "python", "debug", "fix", "script"]):
        return "coding"

    if any(word in text for word in ["explain", "summarize", "analyse", "analyze", "why", "how", "future"]):
        return "reasoning"

    return "general"


def build_openai_payload(task_text):
    return {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "system",
                "content": "Answer clearly and concisely."
            },
            {
                "role": "user",
                "content": task_text
            }
        ],
        "max_tokens": 250
    }


def build_anthropic_payload(task_text):
    return {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 250,
        "messages": [
            {
                "role": "user",
                "content": task_text
            }
        ]
    }


def build_payload(provider_type, task_text):
    if provider_type == "openai":
        return build_openai_payload(task_text)

    if provider_type == "anthropic":
        return build_anthropic_payload(task_text)

    return {
        "task_text": task_text
    }


def load_runtime_providers(task_text, config_path="config/providers.json"):
    provider_settings = load_provider_settings(config_path)
    configured_providers = load_provider_config(config_path)
    providers = []

    for provider_config in configured_providers:
        if not provider_config.get("enabled", False):
            continue

        api_key_env = provider_config.get("api_key_env")
        api_key = os.getenv(api_key_env, "") if api_key_env else ""

        if not api_key:
            continue

        provider = Provider(
            name=provider_config["name"],
            provider_type=provider_config["provider_type"],
            endpoint=provider_config["endpoint"],
            api_key=api_key,
            cost_per_unit=provider_config["cost_per_unit"],
            timeout_seconds=provider_settings["timeout_seconds"],
            hard_timeout_seconds=provider_settings["hard_timeout_seconds"]
        )
        provider.phase_task = build_payload(provider.provider_type, task_text)
        providers.append(provider)

    return providers


def main():
    load_env_file()

    print("ArbitrageEngineV1 is running.")
    print("Phase 3.0: Persistent audit logging.")

    if len(sys.argv) > 1:
        task_text = " ".join(sys.argv[1:])
    else:
        task_text = input("Enter task: ")

    task_type = classify_task(task_text)

    provider_settings = load_provider_settings()
    providers = load_runtime_providers(task_text)

    print(f"Task: {task_text}")
    print(f"Task type: {task_type}")
    print(f"Providers loaded: {len(providers)}")
    print(f"Provider timeout: {provider_settings['timeout_seconds']}s")
    print(f"Hard provider timeout: {provider_settings['hard_timeout_seconds']}s")
    print("Press CTRL + C to stop cleanly.")

    if not providers:
        print("\nERROR: No providers loaded.")
        print("Check your .env file contains OPENAI_API_KEY and/or ANTHROPIC_API_KEY.")
        return

    task = {
        "task_text": task_text,
        "task_type": task_type
    }

    best_route = route_task(task, providers)

    if best_route is None:
        print("\nNO VALID AI ROUTE FOUND")
        return

    print("\nBEST AI ROUTE")
    print(f"Provider: {best_route['provider_name']}")
    print(f"Task type: {best_route['task_type']}")
    print(f"Latency: {best_route['latency']}")
    print(f"Estimated cost: {best_route['estimated_cost']}")
    print(f"Baseline cost: {best_route['baseline_cost']}")
    print(f"Avoided cost: {best_route['avoided_cost']}")
    print(f"Status: {best_route['status']}")

    log_route_decision(
        task=task_text,
        task_type=best_route["task_type"],
        provider=best_route["provider_name"],
        latency=best_route["latency"],
        estimated_cost=best_route["estimated_cost"],
        status=best_route["status"]
    )

    print("\nAI RESPONSE PREVIEW:")
    print(best_route["response_text"])


if __name__ == "__main__":
    main()
