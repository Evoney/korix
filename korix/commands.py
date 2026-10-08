import shlex
from collections.abc import Iterable, Sequence

from .constants import ALL_NAMESPACE_FLAGS, BUILTIN_COMMANDS, CONTEXT_FLAGS, NAMESPACE_FLAGS

SHELL_CONTROL_TOKENS = {";", "&&", "||", "|", ">", ">>", "<"}

MUTATING_COMMANDS = {
    "annotate",
    "apply",
    "cordon",
    "create",
    "delete",
    "drain",
    "edit",
    "label",
    "patch",
    "replace",
    "scale",
    "set",
    "taint",
    "uncordon",
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


def first_command_arg(args: Sequence[str]) -> str | None:
    for arg in args:
        if not arg.startswith("-"):
            return arg
    return None


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
    for arg in args:
        if not arg.startswith("-"):
            return arg
    return "raw"


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
        non_flags = [arg for arg in args if not arg.startswith("-")]
        return len(non_flags) >= 2 and non_flags[1] in {"restart", "undo"}
    return False
