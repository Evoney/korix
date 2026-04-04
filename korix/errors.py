class KorixError(RuntimeError):
    """Base error for Korix failures."""


class LLMError(KorixError):
    """LLM provider failures."""


class TranslationError(KorixError):
    """Natural language translation failures."""


class KubectlError(KorixError):
    """kubectl command failures."""
