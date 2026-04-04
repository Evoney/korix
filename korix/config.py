from collections.abc import Mapping
from dataclasses import dataclass

from .errors import CodexError


@dataclass(frozen=True)
class CodexConfig:
    bin_path: str
    model: str | None
    mode: str
    local_provider: str | None
    timeout_seconds: int
    skip_git_repo_check: bool

    def resolve_mode(self) -> tuple[bool, str | None]:
        mode = (self.mode or "online").lower()
        if mode == "auto":
            use_oss = bool(self.local_provider)
            local_provider = self.local_provider if use_oss else None
        elif mode == "online":
            use_oss = False
            local_provider = None
        elif mode == "offline":
            use_oss = True
            local_provider = self.local_provider
        else:
            raise CodexError("Invalid KORIX_CODEX_MODE (use offline, online, or auto).")
        if use_oss and not local_provider:
            raise CodexError(
                "Offline mode requires a local provider. Set KORIX_CODEX_LOCAL_PROVIDER "
                "to ollama, ollama-chat, or lmstudio (or set KORIX_CODEX_MODE=online)."
            )
        return use_oss, local_provider


def load_codex_config(env: Mapping[str, str]) -> CodexConfig:
    timeout = env.get("KORIX_CODEX_TIMEOUT", "60")
    try:
        timeout_seconds = int(timeout)
    except ValueError:
        raise CodexError("KORIX_CODEX_TIMEOUT must be an integer.")
    return CodexConfig(
        bin_path=env.get("KORIX_CODEX_BIN", "codex"),
        model=env.get("KORIX_CODEX_MODEL"),
        mode=env.get("KORIX_CODEX_MODE", ""),
        local_provider=env.get("KORIX_CODEX_LOCAL_PROVIDER"),
        timeout_seconds=timeout_seconds,
        skip_git_repo_check=env.get("KORIX_CODEX_SKIP_GIT_REPO_CHECK", "1").lower()
        in {"1", "true", "yes"},
    )
