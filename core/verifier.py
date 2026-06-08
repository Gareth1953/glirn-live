def verify_response(result):
    if result is None:
        return False

    if result.get("status") != 200:
        return False

    if result.get("latency", -1) <= 0:
        return False

    response_text = result.get("response_text")

    if response_text is None:
        return False

    if len(response_text.strip()) == 0:
        return False

    return True