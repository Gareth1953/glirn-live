import uuid
import queue
import threading
import time

from core.verifier import verify_response
from core.logger import log_winner, log_provider_attempt
from core.provider_guard import provider_allowed
from analytics.provider_scoring import update_provider_score


def estimate_cost(response_text, provider):
    unit_count = len(response_text)
    return unit_count * provider.cost_per_unit


def call_provider_with_timeout(provider, provider_task, timeout_seconds):
    result_queue = queue.Queue(maxsize=1)

    def target():
        try:
            result_queue.put(provider.call(provider_task))
        except Exception as error:
            result_queue.put({
                "provider": provider.name,
                "status": 500,
                "latency": -1,
                "response_text": str(error),
                "raw_response_text": str(error)
            })

    start = time.time()
    thread = threading.Thread(target=target, daemon=True)
    thread.start()

    try:
        return result_queue.get(timeout=timeout_seconds)
    except queue.Empty:
        latency = time.time() - start
        return {
            "provider": provider.name,
            "status": "timeout",
            "latency": latency,
            "response_text": f"Provider timed out after {timeout_seconds} seconds.",
            "raw_response_text": ""
        }


def route_task(task, providers):
    cycle_id = str(uuid.uuid4())
    valid_results = []

    task_type = "unknown"

    if isinstance(task, dict):
        task_type = task.get("task_type", "unknown")

    for provider in providers:
        if not provider_allowed(provider.name):
            print(f"Provider skipped: {provider.name} blocked by provider_guard.")
            log_provider_attempt(
                cycle_id=cycle_id,
                provider=provider.name,
                status_code="skipped",
                latency=0,
                verified=False,
                estimated_cost="",
                decision="skipped",
                reason="Provider blocked by provider_guard due to low score or repeated failures",
                response_preview=""
            )
            continue

        provider_task = getattr(provider, "phase_task", task)
        timeout_seconds = getattr(
            provider,
            "hard_timeout_seconds",
            getattr(provider, "timeout_seconds", 10)
        )

        print(f"Provider running: {provider.name} with timeout {timeout_seconds}s.")
        result = call_provider_with_timeout(provider, provider_task, timeout_seconds)

        if result.get("status") == "timeout":
            print(f"Provider timed out: {provider.name} after {round(result.get('latency', 0), 3)}s.")

            update_provider_score(
                provider=provider.name,
                success=False,
                latency=0,
                cost=0
            )

            log_provider_attempt(
                cycle_id=cycle_id,
                provider=provider.name,
                status_code="timeout",
                latency=result.get("latency"),
                verified=False,
                estimated_cost="",
                decision="timed_out",
                reason=f"Provider timed out for task_type={task_type}",
                response_preview=result.get("response_text", "")
            )
            continue

        verified = verify_response(result)

        if verified:
            print(f"Provider candidate: {provider.name} returned a verified response.")
            estimated_cost = estimate_cost(result["response_text"], provider)

            update_provider_score(
                provider=provider.name,
                success=True,
                latency=result["latency"],
                cost=estimated_cost
            )

            valid_results.append({
                "provider_name": provider.name,
                "latency": result["latency"],
                "estimated_cost": estimated_cost,
                "status": "verified_live_response",
                "response_text": result["response_text"],
                "task_type": task_type
            })

            log_provider_attempt(
                cycle_id=cycle_id,
                provider=provider.name,
                status_code=result["status"],
                latency=result["latency"],
                verified=True,
                estimated_cost=estimated_cost,
                decision="candidate",
                reason=f"Provider returned verified live response for task_type={task_type}",
                response_preview=result["response_text"]
            )

        else:
            print(f"Provider failed: {provider.name} returned status {result.get('status')}.")
            update_provider_score(
                provider=provider.name,
                success=False,
                latency=0,
                cost=0
            )

            log_provider_attempt(
                cycle_id=cycle_id,
                provider=provider.name,
                status_code=result.get("status"),
                latency=result.get("latency"),
                verified=False,
                estimated_cost="",
                decision="rejected",
                reason=f"Provider failed verification for task_type={task_type}",
                response_preview=result.get("response_text", "")
            )

    if len(valid_results) == 0:
        print("Routing failed: no provider returned a valid response.")
        return None

    best = sorted(
        valid_results,
        key=lambda item: (item["estimated_cost"], item["latency"])
    )[0]

    print(f"Provider selected: {best['provider_name']} won this routing cycle.")

    baseline_cost = max(item["estimated_cost"] for item in valid_results)
    avoided_cost = baseline_cost - best["estimated_cost"]

    for item in valid_results:
        if item["provider_name"] == best["provider_name"]:
            decision = "winner"
            reason = f"Lowest estimated cost for task_type={task_type}, latency used as tie-breaker"
        else:
            decision = "not_selected"
            reason = f"Higher estimated cost than winner for task_type={task_type}"

        log_provider_attempt(
            cycle_id=cycle_id,
            provider=item["provider_name"],
            status_code=200,
            latency=item["latency"],
            verified=True,
            estimated_cost=item["estimated_cost"],
            decision=decision,
            reason=reason,
            response_preview=item["response_text"]
        )

    log_winner(
        provider=best["provider_name"],
        latency=best["latency"],
        estimated_cost=best["estimated_cost"],
        status=best["status"],
        reason=f"Lowest estimated cost for task_type={task_type}, latency used as tie-breaker",
        baseline_cost=baseline_cost,
        avoided_cost=avoided_cost,
        response_preview=best["response_text"]
    )

    best["cycle_id"] = cycle_id
    best["baseline_cost"] = baseline_cost
    best["avoided_cost"] = avoided_cost
    best["response_preview"] = best["response_text"][:160]

    return best
