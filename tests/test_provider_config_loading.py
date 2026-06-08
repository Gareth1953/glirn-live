import json
import os
import tempfile
import unittest
from unittest.mock import patch

import main


class ProviderConfigLoadingTests(unittest.TestCase):
    def write_config(self, temp_dir, providers):
        path = os.path.join(temp_dir, "providers.json")

        with open(path, "w", encoding="utf-8") as file:
            json.dump({
                "timeout_seconds": 4,
                "hard_timeout_seconds": 5,
                "providers": providers
            }, file)

        return path

    def test_loads_enabled_openai_provider_from_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = self.write_config(temp_dir, [
                {
                    "name": "OpenAI_Test",
                    "provider_type": "openai",
                    "endpoint": "https://api.openai.com/v1/chat/completions",
                    "api_key_env": "OPENAI_API_KEY",
                    "cost_per_unit": 0.000002,
                    "enabled": True
                }
            ])

            with patch.dict(os.environ, {"OPENAI_API_KEY": "unit-test-key"}, clear=True):
                providers = main.load_runtime_providers("test message", config_path)

            self.assertEqual(len(providers), 1)
            self.assertEqual(providers[0].name, "OpenAI_Test")
            self.assertEqual(providers[0].provider_type, "openai")
            self.assertEqual(providers[0].timeout_seconds, 4)
            self.assertEqual(providers[0].hard_timeout_seconds, 5)
            self.assertEqual(providers[0].phase_task["messages"][1]["content"], "test message")

    def test_skips_disabled_anthropic_provider(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = self.write_config(temp_dir, [
                {
                    "name": "Anthropic_Test",
                    "provider_type": "anthropic",
                    "endpoint": "https://api.anthropic.com/v1/messages",
                    "api_key_env": "ANTHROPIC_API_KEY",
                    "cost_per_unit": 0.000015,
                    "enabled": False
                }
            ])

            with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "unit-test-key"}, clear=True):
                providers = main.load_runtime_providers("test message", config_path)

            self.assertEqual(providers, [])

    def test_skips_enabled_provider_when_api_key_is_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = self.write_config(temp_dir, [
                {
                    "name": "OpenAI_Test",
                    "provider_type": "openai",
                    "endpoint": "https://api.openai.com/v1/chat/completions",
                    "api_key_env": "OPENAI_API_KEY",
                    "cost_per_unit": 0.000002,
                    "enabled": True
                }
            ])

            with patch.dict(os.environ, {}, clear=True):
                providers = main.load_runtime_providers("test message", config_path)

            self.assertEqual(providers, [])


if __name__ == "__main__":
    unittest.main()
