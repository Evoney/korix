import json
import shutil
import subprocess
from collections.abc import Sequence
from typing import Any

from .errors import KubectlError


class KubectlClient:
    def __init__(self):
        self._binary = "kubectl"

    def ensure_installed(self) -> None:
        if shutil.which(self._binary) is None:
            raise KubectlError("kubectl is not installed or not on PATH.")

    def run(self, args: Sequence[str], check: bool = False) -> subprocess.CompletedProcess:
        return subprocess.run(args, capture_output=True, text=True, check=check)

    def get_json(self, args: Sequence[str], error_message: str) -> dict[str, Any]:
        result = self.run(args, check=False)
        if result.returncode != 0:
            message = result.stderr.strip() or error_message
            raise KubectlError(message)
        try:
            return json.loads(result.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise KubectlError(error_message) from exc

    def current_context(self) -> str | None:
        result = self.run([self._binary, "config", "current-context"], check=False)
        current = result.stdout.strip()
        return current if current else None

    def contexts(self) -> list[str]:
        try:
            result = self.run([self._binary, "config", "get-contexts", "-o", "name"], check=True)
        except subprocess.CalledProcessError as exc:
            raise KubectlError(exc.stderr.strip() or "Failed to list contexts.") from exc
        contexts = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if not contexts:
            raise KubectlError("No kubectl contexts found. Configure kubeconfig first.")
        return contexts

    def namespaces(self, context: str) -> list[str]:
        try:
            result = self.run(
                [self._binary, "--context", context, "get", "namespaces", "-o", "name"],
                check=True,
            )
        except subprocess.CalledProcessError:
            return []
        namespaces: list[str] = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.startswith("namespace/"):
                namespaces.append(line.split("/", 1)[1])
        return namespaces
