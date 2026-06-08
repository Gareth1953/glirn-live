import json
import os
import tempfile
import unittest

from analytics import provider_scoring


class ProviderScoringTests(unittest.TestCase):
    def test_success_creates_score_record(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_scores_file = provider_scoring.SCORES_FILE
            provider_scoring.SCORES_FILE = os.path.join(temp_dir, "provider_scores.json")

            try:
                result = provider_scoring.update_provider_score(
                    provider="UnitProvider",
                    success=True,
                    latency=1.0,
                    cost=0.01
                )

                self.assertEqual(result["success_count"], 1)
                self.assertEqual(result["failure_count"], 0)
                self.assertGreater(result["score"], 0)

                with open(provider_scoring.SCORES_FILE, "r", encoding="utf-8") as file:
                    saved = json.load(file)

                self.assertIn("UnitProvider", saved)
            finally:
                provider_scoring.SCORES_FILE = original_scores_file

    def test_failure_reduces_score_and_counts_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_scores_file = provider_scoring.SCORES_FILE
            provider_scoring.SCORES_FILE = os.path.join(temp_dir, "provider_scores.json")

            try:
                result = provider_scoring.update_provider_score(
                    provider="FailingProvider",
                    success=False,
                    latency=0,
                    cost=0
                )

                self.assertEqual(result["success_count"], 0)
                self.assertEqual(result["failure_count"], 1)
                self.assertLess(result["score"], 100)
            finally:
                provider_scoring.SCORES_FILE = original_scores_file

    def test_reset_provider_score_restores_recovery_defaults(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_scores_file = provider_scoring.SCORES_FILE
            provider_scoring.SCORES_FILE = os.path.join(temp_dir, "provider_scores.json")

            try:
                with open(provider_scoring.SCORES_FILE, "w", encoding="utf-8") as file:
                    json.dump({
                        "RecoverProvider": {
                            "success_count": 3,
                            "failure_count": 5,
                            "average_latency": 2.5,
                            "average_cost": 0.04,
                            "score": 12
                        }
                    }, file)

                result = provider_scoring.reset_provider_score("RecoverProvider")

                self.assertEqual(result, {
                    "success_count": 0,
                    "failure_count": 0,
                    "average_latency": 0,
                    "average_cost": 0,
                    "score": 100
                })

                with open(provider_scoring.SCORES_FILE, "r", encoding="utf-8") as file:
                    saved = json.load(file)

                self.assertEqual(saved["RecoverProvider"], result)
            finally:
                provider_scoring.SCORES_FILE = original_scores_file


if __name__ == "__main__":
    unittest.main()
