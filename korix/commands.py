import shlex
from collections.abc import Iterable, Sequence

from .constants import ALL_NAMESPACE_FLAGS, BUILTIN_COMMANDS, CONTEXT_FLAGS, NAMESPACE_FLAGS

SHELL_CONTROL_TOKENS = {";", "&&", "||", "|", ">", ">>", "<"}

MUTATING_COMMANDS = {
    "annotate",
    "apply",
    "attach",
    "autoscale",
    "cordon",
    "cp",
    "create",
    "debug",
    "delete",
    "drain",
    "edit",
    "exec",
    "expose",
    "label",
    "patch",
    "replace",
    "run",
    "scale",
    "set",
    "taint",
    "uncordon",
}

MUTATING_ROLLOUT_SUBCOMMANDS = {"pause", "restart", "resume", "undo"}

# Global flags whose value may follow as a separate argument, e.g. `-n prod`.
VALUE_FLAGS = {
    "-n",
    "--namespace",
    "--context",
    "--kubeconfig",
    "--cluster",
    "--user",
    "-s",
    "--server",
    "--as",
    "--as-group",
    "--token",
    "--request-timeout",
}


def has_flag(args: Sequence[str], flags: Iterable[str]) -> bool:
    flag_set = set(flags)
    for arg in args:
        if arg in flag_set:
            return True
        base = arg.split("=", 1)[0]
        if base in flag_set:
            return True
        if "-n" in flag_set and arg.startswith("-n") and arg != "-n":
            return True
    return False


def positional_args(args: Sequence[str]) -> list[str]:
    positionals: list[str] = []
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
            continue
        if arg == "--":
            break
        if arg.startswith("-"):
            skip_next = arg in VALUE_FLAGS
            continue
        positionals.append(arg)
    return positionals


def first_command_arg(args: Sequence[str]) -> str | None:
    positionals = positional_args(args)
    return positionals[0] if positionals else None


def is_plugin_command(args: Sequence[str]) -> bool:
    cmd = first_command_arg(args)
    if not cmd:
        return False
    return cmd not in BUILTIN_COMMANDS


def build_kubectl_command(
    args: Sequence[str], context: str, namespace: str | None, all_namespaces: bool
) -> list[str]:
    cmd = ["kubectl", "--context", context]
    if is_plugin_command(args):
        cmd = ["kubectl"]
        cmd.extend(args)
        return cmd
    if has_flag(args, CONTEXT_FLAGS):
        cmd = ["kubectl"]
    if all_namespaces:
        if not has_flag(args, NAMESPACE_FLAGS) and not has_flag(args, ALL_NAMESPACE_FLAGS):
            cmd.append("-A")
    elif namespace:
        if not has_flag(args, ALL_NAMESPACE_FLAGS | NAMESPACE_FLAGS):
            cmd.extend(["--namespace", namespace])
    cmd.extend(args)
    return cmd


def build_scoped_command(
    args: Sequence[str],
    context: str,
    namespace: str | None,
    all_namespaces: bool,
    namespaced: bool,
) -> list[str]:
    cmd = ["kubectl", "--context", context]
    if namespaced:
        if all_namespaces:
            cmd.append("-A")
        elif namespace:
            cmd.extend(["--namespace", namespace])
    cmd.extend(args)
    return cmd


def render_command(cmd: Sequence[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


def detect_action_from_args(args: Sequence[str]) -> str:
    return first_command_arg(args) or "raw"


def validate_translated_args(args: Sequence[str]) -> None:
    if not args:
        raise ValueError("LLM provider returned an empty kubectl command.")
    for arg in args:
        if arg in SHELL_CONTROL_TOKENS:
            raise ValueError(
                "LLM provider returned shell control syntax, not a single kubectl command."
            )
        if "\x00" in arg:
            raise ValueError("LLM provider returned an invalid command argument.")
    action = first_command_arg(args)
    if not action:
        raise ValueError("LLM provider returned flags without a kubectl subcommand.")


def is_mutating_command(args: Sequence[str]) -> bool:
    action = detect_action_from_args(args)
    if action in MUTATING_COMMANDS:
        return True
    if action == "rollout":
        positionals = positional_args(args)
        return len(positionals) >= 2 and positionals[1] in MUTATING_ROLLOUT_SUBCOMMANDS
    return False
