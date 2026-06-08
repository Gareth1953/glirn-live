import json
import os
import tempfile
import unittest

from core import provider_guard


class ProviderGuardTests(unittest.TestCase):
    def test_unknown_provider_is_allowed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_scores_file = provider_guard.SCORES_FILE
            provider_guard.SCORES_FILE = os.path.join(temp_dir, "provider_scores.json")

            try:
                self.assertTrue(provider_guard.provider_allowed("NewProvider"))
            finally:
                provider_guard.SCORES_FILE = original_scores_file

    def test_provider_with_repeated_failures_is_blocked(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_scores_file = provider_guard.SCORES_FILE
            provider_guard.SCORES_FILE = os.path.join(temp_dir, "provider_scores.json")

            scores = {
                "BadProvider": {
                    "failure_count": 3,
                    "score": 50
                }
            }

            with open(provider_guard.SCORES_FILE, "w", encoding="utf-8") as file:
                json.dump(scores, file)

            try:
                self.assertFalse(provider_guard.provider_allowed("BadProvider"))
            finally:
                provider_guard.SCORES_FILE = original_scores_file

    def test_provider_with_low_score_is_blocked(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_scores_file = provider_guard.SCORES_FILE
            provider_guard.SCORES_FILE = os.path.join(temp_dir, "provider_scores.json")

            scores = {
                "LowScoreProvider": {
                    "failure_count": 0,
                    "score": 10
                }
            }

            with open(provider_guard.SCORES_FILE, "w", encoding="utf-8") as file:
                json.dump(scores, file)

            try:
                self.assertFalse(provider_guard.provider_allowed("LowScoreProvider"))
            finally:
                provider_guard.SCORES_FILE = original_scores_file


if __name__ == "__main__":
    unittest.main()
