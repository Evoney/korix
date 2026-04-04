import os
import sys
import textwrap

from .codex_client import CodexClient
from .commands import (
    build_kubectl_command,
    detect_action_from_args,
    is_mutating_command,
    render_command,
)
from .config import load_codex_config
from .constants import DEFAULT_NAMESPACE
from .domain import CommandSpec
from .errors import CodexError, KubectlError, TranslationError
from .kubectl import KubectlClient
from .translation import Translator


class UserAbort(Exception):
    pass


def prompt(text: str) -> str:
    try:
        return input(text)
    except (EOFError, KeyboardInterrupt):
        raise UserAbort


def choose_context(kubectl: KubectlClient) -> str:
    contexts = kubectl.contexts()
    current = kubectl.current_context()
    print("Available contexts:")
    for idx, ctx in enumerate(contexts, start=1):
        marker = " (current)" if current and ctx == current else ""
        print(f"  {idx}. {ctx}{marker}")
    prompt_text = "Choose context by number or name"
    if current:
        prompt_text += f" (enter={current})"
    prompt_text += ": "
    while True:
        choice = prompt(prompt_text).strip()
        if not choice:
            if current:
                return current
            continue
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(contexts):
                return contexts[idx - 1]
        if choice in contexts:
            return choice
        print("Invalid context. Try again.")


def choose_namespace(kubectl: KubectlClient, context: str) -> tuple[str | None, bool]:
    namespaces_cache = None
    prompt_text = f"Namespace (enter={DEFAULT_NAMESPACE}, '-'=none, '*'=all, '?'=list): "
    while True:
        raw = prompt(prompt_text).strip()
        if raw == "":
            return DEFAULT_NAMESPACE, False
        if raw == "-":
            return None, False
        if raw == "*":
            return None, True
        if raw == "?":
            if namespaces_cache is None:
                namespaces_cache = kubectl.namespaces(context)
            if namespaces_cache:
                print("Namespaces:")
                for idx, name in enumerate(namespaces_cache, start=1):
                    print(f"  {idx}. {name}")
            else:
                print("No namespaces found or unable to list. Enter a namespace name.")
            continue
        if namespaces_cache and raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(namespaces_cache):
                return namespaces_cache[idx - 1], False
        return raw, False


def confirm_dangerous(action: str, cmd) -> bool:
    print("Proposed command:")
    print("  " + render_command(cmd))
    while True:
        answer = prompt(f"{action.title()} is destructive. Proceed? [y/N]: ").strip().lower()
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no", ""}:
            return False
        print("Please answer yes or no.")


def print_help():
    print(textwrap.dedent("""
        Examples:
          list pods
          describe deployment api
          logs pod api-123
          logs api-123 follow
          apply ./manifest.yaml
          create ./manifest.yaml
          delete service web
          scale deployment api to 3 replicas

        Tips:
          - Use '?' during namespace prompt to list namespaces.
          - Type 'kubectl ...' to run a raw kubectl command.
          - Type 'exit' to quit.
          - Set KORIX_CODEX_MODE=online to use Codex cloud auth.
          - Offline translation requires KORIX_CODEX_LOCAL_PROVIDER.
        """).strip())


def translate_request(translator: Translator, text: str) -> CommandSpec:
    lower = text.strip().lower()
    if lower in {"exit", "quit", "q"}:
        return CommandSpec(action="exit", args=[])
    if lower in {"help", "?"}:
        return CommandSpec(action="help", args=[])
    return translator.translate(text)


def main() -> None:
    print("Korix legacy CLI ready. Type 'help' for examples.")
    kubectl = KubectlClient()
    try:
        kubectl.ensure_installed()
    except KubectlError as exc:
        print(str(exc))
        sys.exit(1)

    try:
        config = load_codex_config(os.environ)
        translator = Translator(CodexClient(config))
    except CodexError as exc:
        print(str(exc))
        sys.exit(1)

    while True:
        try:
            text = prompt("korix> ").strip()
        except UserAbort:
            print("\nExiting.")
            break

        try:
            result = translate_request(translator, text)
        except TranslationError as exc:
            print(str(exc))
            continue

        if result.action == "exit":
            break
        if result.action == "help":
            print_help()
            continue

        try:
            context = choose_context(kubectl)
            namespace, all_namespaces = choose_namespace(kubectl, context)
        except (UserAbort, KubectlError) as exc:
            print(f"\n{exc}" if str(exc) else "\nExiting.")
            break

        cmd = build_kubectl_command(result.args, context, namespace, all_namespaces)
        action = result.action if result.action != "raw" else detect_action_from_args(result.args)
        if is_mutating_command(result.args):
            if not confirm_dangerous(action, cmd):
                print("Skipped.")
                continue
        else:
            print("Proposed command:")
            print("  " + render_command(cmd))

        try:
            completed = kubectl.run(cmd, check=False)
        except FileNotFoundError:
            print("kubectl is not installed or not on PATH.")
            sys.exit(1)
        if completed.stdout:
            print(completed.stdout.rstrip())
        if completed.stderr:
            print(completed.stderr.rstrip())
        if completed.returncode != 0:
            print(f"Command exited with status {completed.returncode}.")
