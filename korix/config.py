from collections.abc import Mapping
from dataclasses import dataclass

from .errors import LLMError


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    bin_path: str
    model: str | None
    mode: str
    local_provider: str | None
    timeout_seconds: int
    skip_git_repo_check: bool
    base_url: str | None
    api_key: str | None

    def resolve_cli_mode(self) -> tuple[bool, str | None]:
        mode = (self.mode or "online").lower()
        if mode == "auto":
            use_local = bool(self.local_provider)
            local_provider = self.local_provider if use_local else None
        elif mode == "online":
            use_local = False
            local_provider = None
        elif mode == "offline":
            use_local = True
            local_provider = self.local_provider
        else:
            raise LLMError("Invalid KORIX_LLM_MODE (use offline, online, or auto).")
        if use_local and not local_provider:
            raise LLMError(
                "Offline mode requires a local provider. Set KORIX_LLM_LOCAL_PROVIDER "
                "to a supported local backend (or set KORIX_LLM_MODE=online)."
            )
        return use_local, local_provider


def load_llm_config(env: Mapping[str, str]) -> LLMConfig:
    timeout = env.get("KORIX_LLM_TIMEOUT", "60")
    try:
        timeout_seconds = int(timeout)
    except ValueError:
        raise LLMError("KORIX_LLM_TIMEOUT must be an integer.")
    return LLMConfig(
        provider=(env.get("KORIX_LLM_PROVIDER", "cli") or "cli").strip().lower(),
        bin_path=env.get("KORIX_LLM_BIN", "llm"),
        model=env.get("KORIX_LLM_MODEL"),
        mode=env.get("KORIX_LLM_MODE", ""),
        local_provider=env.get("KORIX_LLM_LOCAL_PROVIDER"),
        timeout_seconds=timeout_seconds,
        skip_git_repo_check=env.get("KORIX_LLM_SKIP_GIT_REPO_CHECK", "1").lower()
        in {"1", "true", "yes"},
        base_url=env.get("KORIX_LLM_BASE_URL"),
        api_key=env.get("KORIX_LLM_API_KEY"),
    )
