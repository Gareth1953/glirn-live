import json
import time
import requests
from requests.exceptions import Timeout


class Provider:
    def __init__(
        self,
        name,
        provider_type,
        endpoint,
        api_key,
        cost_per_unit,
        timeout_seconds=10,
        hard_timeout_seconds=None
    ):
        self.name = name
        self.provider_type = provider_type
        self.endpoint = endpoint
        self.api_key = api_key
        self.cost_per_unit = cost_per_unit
        self.timeout_seconds = timeout_seconds
        self.hard_timeout_seconds = hard_timeout_seconds or timeout_seconds

    def build_headers(self):
        headers = {
            "Content-Type": "application/json"
        }

        if self.provider_type == "openai":
            headers["Authorization"] = f"Bearer {self.api_key}"

        elif self.provider_type == "anthropic":
            headers["x-api-key"] = self.api_key
            headers["anthropic-version"] = "2023-06-01"

        return headers

    def extract_clean_text(self, response_text):
        try:
            data = json.loads(response_text)

            if self.provider_type == "openai":
                return data["choices"][0]["message"]["content"]

            if self.provider_type == "anthropic":
                return data["content"][0]["text"]

            return response_text

        except Exception:
            return response_text

    def call(self, payload):
        start = time.time()

        try:
            response = requests.post(
                self.endpoint,
                json=payload,
                headers=self.build_headers(),
                timeout=self.timeout_seconds
            )

            latency = time.time() - start
            raw_text = response.text
            clean_text = self.extract_clean_text(raw_text)

            return {
                "provider": self.name,
                "status": response.status_code,
                "latency": latency,
                "response_text": clean_text,
                "raw_response_text": raw_text
            }

        except Timeout as error:
            latency = time.time() - start
            return {
                "provider": self.name,
                "status": "timeout",
                "latency": latency,
                "response_text": f"Provider timed out after {self.timeout_seconds} seconds.",
                "raw_response_text": str(error)
            }

        except Exception as error:
            latency = time.time() - start
            return {
                "provider": self.name,
                "status": 500,
                "latency": latency,
                "response_text": str(error),
                "raw_response_text": str(error)
            }
