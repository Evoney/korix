import json
import os
import subprocess
import tempfile
import urllib.error
import urllib.request
from abc import ABC, abstractmethod

from .config import LLMConfig
from .errors import LLMError

DEFAULT_OPENAI_COMPATIBLE_BASE_URL = "https://api.openai.com/v1"
SUPPORTED_PROVIDERS = ("cli", "openai-compatible")


class LLMProvider(ABC):
    @abstractmethod
    def run(self, prompt_text: str) -> str:
        raise NotImplementedError


class CLIProvider(LLMProvider):
    def __init__(self, config: LLMConfig):
        self._config = config

    def run(self, prompt_text: str) -> str:
        use_local, local_provider = self._config.resolve_cli_mode()
        cmd = [self._config.bin_path, "exec"]
        if self._config.skip_git_repo_check:
            cmd.append("--skip-git-repo-check")
        if use_local:
            cmd.append("--oss")
        if local_provider:
            cmd.extend(["--local-provider", local_provider])
        if self._config.model:
            cmd.extend(["--model", self._config.model])

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "llm-output.txt")
            cmd.extend(["--output-last-message", output_path])
            try:
                result = subprocess.run(
                    cmd,
                    input=prompt_text,
                    capture_output=True,
                    text=True,
                    timeout=self._config.timeout_seconds,
                    check=False,
                )
            except FileNotFoundError as exc:
                raise LLMError(f"LLM CLI not found at {self._config.bin_path}.") from exc
            except subprocess.TimeoutExpired as exc:
                raise LLMError(
                    f"LLM request timed out after {self._config.timeout_seconds}s."
                ) from exc

            output = ""
            if os.path.exists(output_path):
                with open(output_path, encoding="utf-8") as handle:
                    output = handle.read().strip()

        if result.returncode != 0:
            error = result.stderr.strip() or "LLM CLI failed to produce output."
            raise LLMError(error)
        if not output:
            raise LLMError("LLM provider returned empty output.")
        return output


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, config: LLMConfig):
        self._config = config
        if not config.model:
            raise LLMError("Model is required for the openai-compatible provider.")
        if not config.api_key:
            raise LLMError("API key is required for the openai-compatible provider.")
        self._base_url = (config.base_url or DEFAULT_OPENAI_COMPATIBLE_BASE_URL).rstrip("/")

    def run(self, prompt_text: str) -> str:
        payload = {
            "model": self._config.model,
            "messages": [{"role": "user", "content": prompt_text}],
            "temperature": 0,
        }
        request = urllib.request.Request(
            f"{self._base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self._config.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore").strip()
            message = detail or f"Provider HTTP error {exc.code}."
            raise LLMError(message) from exc
        except urllib.error.URLError as exc:
            raise LLMError(f"Unable to reach provider at {self._base_url}.") from exc

        try:
            payload = json.loads(body)
            return payload["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise LLMError("Provider returned an unexpected response shape.") from exc


def build_provider(config: LLMConfig) -> LLMProvider:
    provider = (config.provider or "cli").strip().lower()
    if provider == "cli":
        return CLIProvider(config)
    if provider == "openai-compatible":
        return OpenAICompatibleProvider(config)
    raise LLMError(
        f"Unsupported provider '{config.provider}'. Use one of: {', '.join(SUPPORTED_PROVIDERS)}."
    )


def test_provider_connection(provider: LLMProvider) -> str:
    return provider.run("Reply with exactly: OK")
