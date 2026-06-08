import time
import unittest
from unittest.mock import patch

from core import router


class HangingProvider:
    name = "HangingProvider"
    cost_per_unit = 0.000001
    hard_timeout_seconds = 0.1
    timeout_seconds = 10

    def call(self, payload):
        time.sleep(2)
        return {
            "provider": self.name,
            "status": 200,
            "latency": 2,
            "response_text": "late response",
            "raw_response_text": "late response"
        }


class RouterNoHangTests(unittest.TestCase):
    def test_hanging_provider_times_out_without_blocking_route_cycle(self):
        provider = HangingProvider()
        start = time.time()

        with patch("core.router.provider_allowed", return_value=True), \
                patch("core.router.update_provider_score") as update_score, \
                patch("core.router.log_provider_attempt") as log_attempt, \
                patch("core.router.log_winner"):
            result = router.route_task(
                {"task_text": "hello", "task_type": "general"},
                [provider]
            )

        elapsed = time.time() - start

        self.assertIsNone(result)
        self.assertLess(elapsed, 1.0)
        update_score.assert_called_once_with(
            provider="HangingProvider",
            success=False,
            latency=0,
            cost=0
        )
        self.assertEqual(log_attempt.call_args.kwargs["decision"], "timed_out")


if __name__ == "__main__":
    unittest.main()
