import unittest

from korix.config import load_llm_config
from korix.errors import LLMError
from korix.llm import build_provider


class LLMConfigTest(unittest.TestCase):
    def test_load_llm_config_defaults_to_cli_provider(self):
        config = load_llm_config({})
        self.assertEqual(config.provider, "cli")
        self.assertEqual(config.bin_path, "llm")
        self.assertEqual(config.timeout_seconds, 60)

    def test_openai_compatible_provider_requires_model_and_api_key(self):
        config = load_llm_config({"KORIX_LLM_PROVIDER": "openai-compatible"})
        with self.assertRaises(LLMError):
            build_provider(config)

    def test_openai_compatible_provider_builds_with_required_fields(self):
        config = load_llm_config(
            {
                "KORIX_LLM_PROVIDER": "openai-compatible",
                "KORIX_LLM_MODEL": "gpt-4.1-mini",
                "KORIX_LLM_API_KEY": "secret",
            }
        )
        provider = build_provider(config)
        self.assertEqual(provider.__class__.__name__, "OpenAICompatibleProvider")


if __name__ == "__main__":
    unittest.main()
