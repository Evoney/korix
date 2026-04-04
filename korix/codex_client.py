import os
import subprocess
import tempfile

from .config import CodexConfig
from .errors import CodexError


class CodexClient:
    def __init__(self, config: CodexConfig):
        self._config = config

    def run(self, prompt_text: str) -> str:
        use_oss, local_provider = self._config.resolve_mode()
        cmd = [self._config.bin_path, "exec"]
        if self._config.skip_git_repo_check:
            cmd.append("--skip-git-repo-check")
        if use_oss:
            cmd.append("--oss")
        if local_provider:
            cmd.extend(["--local-provider", local_provider])
        if self._config.model:
            cmd.extend(["--model", self._config.model])

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "codex-output.txt")
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
                raise CodexError(f"codex CLI not found at {self._config.bin_path}.") from exc
            except subprocess.TimeoutExpired as exc:
                raise CodexError(
                    f"codex request timed out after {self._config.timeout_seconds}s."
                ) from exc

            output = ""
            if os.path.exists(output_path):
                with open(output_path, encoding="utf-8") as handle:
                    output = handle.read().strip()

        if result.returncode != 0:
            error = result.stderr.strip() or "Codex failed to produce output."
            raise CodexError(error)
        if not output:
            raise CodexError("Codex returned empty output.")
        return output
