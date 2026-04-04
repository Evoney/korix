import shlex
import textwrap

from .domain import CommandSpec
from .errors import LLMError, TranslationError
from .llm import LLMProvider

LLM_PROMPT = textwrap.dedent("""
    You are a CLI assistant that converts natural-language Kubernetes requests into a single kubectl command.
    Return exactly one line with the command and nothing else (no backticks, no explanations).
    If you cannot translate the request, respond with: ERROR: <reason>

    Rules:
    - Use kubectl subcommands and flags correctly.
    - Use -A/--all-namespaces only if explicitly requested.
    - Use -n/--namespace only if explicitly requested.
    - Use --context only if explicitly requested.
    - Use -o yaml/json/wide when asked for those formats.
    - For logs, include -f when "follow" or "stream" is requested.
    - For exec, include "--" before the command.
    - Prefer concise, direct commands.
    """).strip()

KUBECTL_SYNTAX_LINES = "kubectl "
ERROR_OUTPUT_PREFIX = "ERROR:"


def extract_kubectl_line(output: str) -> str | None:
    if not output:
        return None
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        line = line.strip("`")
        if line.startswith("$ "):
            line = line[2:]
        if line.startswith("> "):
            line = line[2:]
        if line.startswith(KUBECTL_SYNTAX_LINES) or line == "kubectl":
            return line
        if KUBECTL_SYNTAX_LINES in line:
            return line[line.find(KUBECTL_SYNTAX_LINES) :]
    if output.startswith(ERROR_OUTPUT_PREFIX):
        return output
    return None


class Translator:
    def __init__(self, provider: LLMProvider):
        self._provider = provider

    def translate(self, text: str) -> CommandSpec:
        raw = text.strip()
        if not raw:
            raise TranslationError("Empty input.")

        lower = raw.lower().strip()
        if lower.startswith("kubectl "):
            try:
                args = shlex.split(raw)[1:]
            except ValueError as exc:
                raise TranslationError(f"Could not parse command: {exc}") from exc
            return CommandSpec(action="raw", args=args)

        try:
            output = self._provider.run(f"{LLM_PROMPT}\n\nRequest: {raw}\n")
        except LLMError as exc:
            raise TranslationError(str(exc)) from exc
        line = extract_kubectl_line(output)
        if not line:
            raise TranslationError("LLM provider did not return a kubectl command.")
        if line.startswith(ERROR_OUTPUT_PREFIX):
            reason = line[len(ERROR_OUTPUT_PREFIX) :].strip() or "Unable to translate request."
            raise TranslationError(reason)
        try:
            parts = shlex.split(line)
        except ValueError as exc:
            raise TranslationError(f"Could not parse command: {exc}") from exc
        if not parts or parts[0] != "kubectl":
            raise TranslationError("LLM provider returned a non-kubectl command.")
        return CommandSpec(action="raw", args=parts[1:])
