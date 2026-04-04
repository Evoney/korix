class KubeAgentError(RuntimeError):
    """Base error for Korix failures."""


class CodexError(KubeAgentError):
    """Codex client failures."""


class TranslationError(KubeAgentError):
    """Natural language translation failures."""


class KubectlError(KubeAgentError):
    """kubectl command failures."""
