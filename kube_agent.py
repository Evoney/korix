#!/usr/bin/env python3
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

RESOURCE_ALIASES = {
    "pod": "pod",
    "pods": "pod",
    "deployment": "deployment",
    "deployments": "deployment",
    "deploy": "deployment",
    "service": "service",
    "services": "service",
    "svc": "service",
    "configmap": "configmap",
    "configmaps": "configmap",
    "cm": "configmap",
    "secret": "secret",
    "secrets": "secret",
    "namespace": "namespace",
    "namespaces": "namespace",
    "ns": "namespace",
    "node": "node",
    "nodes": "node",
    "ingress": "ingress",
    "ingresses": "ingress",
    "job": "job",
    "jobs": "job",
    "cronjob": "cronjob",
    "cronjobs": "cronjob",
    "statefulset": "statefulset",
    "statefulsets": "statefulset",
    "daemonset": "daemonset",
    "daemonsets": "daemonset",
    "replicaset": "replicaset",
    "replicasets": "replicaset",
    "pvc": "pvc",
    "pv": "pv",
    "persistentvolume": "pv",
    "persistentvolumeclaim": "pvc",
}

VERB_ALIASES = {
    "get": "get",
    "list": "get",
    "show": "get",
    "describe": "describe",
    "logs": "logs",
    "log": "logs",
    "apply": "apply",
    "create": "create",
    "delete": "delete",
    "remove": "delete",
    "scale": "scale",
}

STOP_WORDS = {
    "in",
    "from",
    "for",
    "with",
    "on",
    "namespace",
    "namespaces",
    "ns",
    "context",
    "cluster",
    "all",
    "of",
    "the",
    "a",
    "an",
    "to",
    "and",
    "named",
    "called",
    "by",
}

DEFAULT_NAMESPACE = "default"
DESTRUCTIVE_ACTIONS = {"apply", "create", "delete", "scale"}
CONTEXT_FLAGS = {"--context"}
NAMESPACE_FLAGS = {"-n", "--namespace"}
ALL_NAMESPACE_FLAGS = {"-A", "--all-namespaces"}
BUILTIN_COMMANDS = {
    "annotate",
    "api-resources",
    "api-versions",
    "apply",
    "attach",
    "auth",
    "autoscale",
    "cluster-info",
    "completion",
    "config",
    "cordon",
    "cp",
    "create",
    "debug",
    "delete",
    "describe",
    "diff",
    "drain",
    "edit",
    "exec",
    "explain",
    "expose",
    "get",
    "kustomize",
    "label",
    "logs",
    "patch",
    "port-forward",
    "proxy",
    "replace",
    "rollout",
    "run",
    "scale",
    "set",
    "taint",
    "top",
    "uncordon",
    "version",
    "wait",
}

CODEX_BIN = os.environ.get("KUBE_AGENT_CODEX_BIN", "codex")
CODEX_MODEL = os.environ.get("KUBE_AGENT_CODEX_MODEL")
CODEX_MODE = os.environ.get("KUBE_AGENT_CODEX_MODE", "").strip().lower()
CODEX_OSS = os.environ.get("KUBE_AGENT_CODEX_OSS", "1").lower() in {"1", "true", "yes"}
CODEX_LOCAL_PROVIDER = os.environ.get("KUBE_AGENT_CODEX_LOCAL_PROVIDER")
CODEX_TIMEOUT_SECONDS = int(os.environ.get("KUBE_AGENT_CODEX_TIMEOUT", "60"))
CODEX_SKIP_GIT_REPO_CHECK = os.environ.get("KUBE_AGENT_CODEX_SKIP_GIT_REPO_CHECK", "1").lower() in {
    "1",
    "true",
    "yes",
}

LLM_PROMPT = textwrap.dedent(
    """
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
    """
).strip()


class UserAbort(Exception):
    pass


@dataclass(frozen=True)
class CommandSpec:
    action: str
    args: List[str]


def prompt(text: str) -> str:
    try:
        return input(text)
    except (EOFError, KeyboardInterrupt):
        raise UserAbort


def run_command(args: Sequence[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=check)


def run_codex(prompt_text: str) -> Tuple[Optional[str], Optional[str]]:
    mode = CODEX_MODE or "online"
    if mode == "auto":
        use_oss = bool(CODEX_LOCAL_PROVIDER)
        local_provider = CODEX_LOCAL_PROVIDER if use_oss else None
    elif mode == "online":
        use_oss = False
        local_provider = None
    elif mode == "offline":
        use_oss = True
        local_provider = CODEX_LOCAL_PROVIDER
    else:
        return None, "Invalid KUBE_AGENT_CODEX_MODE (use offline, online, or auto)."
    if use_oss and not local_provider:
        return (
            None,
            "Offline mode requires a local provider. Set KUBE_AGENT_CODEX_LOCAL_PROVIDER "
            "to ollama, ollama-chat, or lmstudio (or set KUBE_AGENT_CODEX_MODE=online).",
        )
    cmd = [CODEX_BIN, "exec"]
    if CODEX_SKIP_GIT_REPO_CHECK:
        cmd.append("--skip-git-repo-check")
    if use_oss:
        cmd.append("--oss")
    if local_provider:
        cmd.extend(["--local-provider", local_provider])
    if CODEX_MODEL:
        cmd.extend(["--model", CODEX_MODEL])
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        output_path = tmp.name
    cmd.extend(["--output-last-message", output_path])
    try:
        result = subprocess.run(
            cmd,
            input=prompt_text,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=CODEX_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError:
        return None, f"codex CLI not found at {CODEX_BIN}."
    except subprocess.TimeoutExpired:
        return None, f"codex request timed out after {CODEX_TIMEOUT_SECONDS}s."

    output = ""
    try:
        with open(output_path, "r", encoding="utf-8") as handle:
            output = handle.read()
    finally:
        try:
            os.remove(output_path)
        except OSError:
            pass

    if result.returncode != 0:
        error = result.stderr.strip() or "Codex failed to produce output."
        return None, error
    return output.strip(), None


def extract_kubectl_line(output: str) -> Optional[str]:
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
        if line.startswith("kubectl " ) or line == "kubectl":
            return line
        if "kubectl " in line:
            return line[line.find("kubectl ") :]
    if output.startswith("ERROR:"):
        return output
    return None


def translate_with_llm(text: str) -> Tuple[Optional[CommandSpec], Optional[str]]:
    prompt_text = f"{LLM_PROMPT}\n\nRequest: {text}\n"
    output, error = run_codex(prompt_text)
    if error:
        return None, error
    line = extract_kubectl_line(output or "")
    if not line:
        return None, "Codex did not return a kubectl command."
    if line.startswith("ERROR:"):
        return None, line[len("ERROR:") :].strip() or "Unable to translate request."
    try:
        parts = shlex.split(line)
    except ValueError as exc:
        return None, f"Could not parse command: {exc}"
    if not parts or parts[0] != "kubectl":
        return None, "Codex returned a non-kubectl command."
    return CommandSpec(action="raw", args=parts[1:]), None


def ensure_kubectl():
    if shutil.which("kubectl") is None:
        raise RuntimeError("kubectl is not installed or not on PATH.")


def get_current_context() -> Optional[str]:
    result = run_command(["kubectl", "config", "current-context"], check=False)
    current = result.stdout.strip()
    return current if current else None


def get_contexts() -> List[str]:
    try:
        result = run_command(["kubectl", "config", "get-contexts", "-o", "name"])
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(exc.stderr.strip() or "Failed to list contexts.")
    contexts = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not contexts:
        raise RuntimeError("No kubectl contexts found. Configure kubeconfig first.")
    return contexts


def choose_context() -> str:
    contexts = get_contexts()
    current = get_current_context()
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


def list_namespaces(context: str) -> List[str]:
    try:
        result = run_command(["kubectl", "--context", context, "get", "namespaces", "-o", "name"])
    except subprocess.CalledProcessError:
        return []
    namespaces = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("namespace/"):
            namespaces.append(line.split("/", 1)[1])
    return namespaces


def choose_namespace(context: str) -> Tuple[Optional[str], bool]:
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
                namespaces_cache = list_namespaces(context)
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


def detect_verb(lower_text: str) -> Optional[str]:
    for key, verb in VERB_ALIASES.items():
        if re.search(rf"\b{re.escape(key)}\b", lower_text):
            return verb
    return None


def parse_resource_and_name(tokens: Sequence[str]) -> Tuple[Optional[str], Optional[str]]:
    resource = None
    name = None
    for idx, token in enumerate(tokens):
        if token in RESOURCE_ALIASES:
            resource = RESOURCE_ALIASES[token]
            for j in range(idx + 1, len(tokens)):
                if tokens[j] in STOP_WORDS or tokens[j] in RESOURCE_ALIASES:
                    break
                name = tokens[j]
                break
            break
    return resource, name


def parse_name_after_verb(tokens: Sequence[str], verb: str) -> Optional[str]:
    for idx, token in enumerate(tokens):
        if token == verb:
            for j in range(idx + 1, len(tokens)):
                if tokens[j] in STOP_WORDS:
                    continue
                return tokens[j]
    return None


def parse_replicas(lower_text: str) -> Optional[int]:
    match = re.search(r"\b(\d+)\s*replicas?\b", lower_text)
    if match:
        return int(match.group(1))
    match = re.search(r"\breplicas?\s*(?:to|=)?\s*(\d+)\b", lower_text)
    if match:
        return int(match.group(1))
    match = re.search(r"\bto\s*(\d+)\b", lower_text)
    if match:
        return int(match.group(1))
    return None


def expand_path(path: str) -> str:
    return os.path.expanduser(path)


def parse_apply_file(text: str) -> Optional[str]:
    try:
        tokens = shlex.split(text)
    except ValueError:
        tokens = []
    for idx, token in enumerate(tokens):
        if token in {"-f", "--filename"} and idx + 1 < len(tokens):
            return expand_path(tokens[idx + 1])
        if token.startswith("--filename="):
            return expand_path(token.split("=", 1)[1])
        if token.startswith("-f="):
            return expand_path(token.split("=", 1)[1])
    for token in tokens:
        if token.lower().endswith((".yaml", ".yml")):
            return expand_path(token)
    match = re.search(r"(?P<path>(?:~|/|\./)[^\s]+\.ya?ml)\b", text)
    if match:
        return expand_path(match.group("path"))
    match = re.search(r"\bfile\s+(?P<path>[^\s]+)\b", text, re.IGNORECASE)
    if match:
        return expand_path(match.group("path"))
    return None


def translate_to_kubectl(text: str) -> Tuple[Optional[CommandSpec], Optional[str]]:
    raw = text.strip()
    if not raw:
        return None, "Empty input."

    lower = raw.lower().strip()
    if lower in {"exit", "quit", "q"}:
        return CommandSpec(action="exit", args=[]), None
    if lower in {"help", "?"}:
        return CommandSpec(action="help", args=[]), None

    if lower.startswith("kubectl "):
        try:
            args = shlex.split(raw)[1:]
        except ValueError as exc:
            return None, f"Could not parse command: {exc}"
        return CommandSpec(action="raw", args=args), None
    return translate_with_llm(raw)


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


def first_command_arg(args: Sequence[str]) -> Optional[str]:
    for arg in args:
        if arg.startswith("-"):
            continue
        return arg
    return None


def is_plugin_command(args: Sequence[str]) -> bool:
    cmd = first_command_arg(args)
    if not cmd:
        return False
    return cmd not in BUILTIN_COMMANDS


def build_command(
    args: Sequence[str], context: str, namespace: Optional[str], all_namespaces: bool
) -> List[str]:
    cmd = ["kubectl", "--context", context]
    if is_plugin_command(args):
        print("Note: kubectl plugin command detected; skipping context/namespace injection.")
        cmd = ["kubectl"]
        cmd.extend(args)
        return cmd
    if has_flag(args, CONTEXT_FLAGS):
        print("Note: command already specifies a context; using it.")
        cmd = ["kubectl"]
    if all_namespaces:
        if has_flag(args, NAMESPACE_FLAGS):
            print("Note: command already specifies a namespace; skipping -A.")
        elif not has_flag(args, ALL_NAMESPACE_FLAGS):
            cmd.append("-A")
    elif namespace:
        if not has_flag(args, ALL_NAMESPACE_FLAGS | NAMESPACE_FLAGS):
            cmd.extend(["--namespace", namespace])
    cmd.extend(args)
    return cmd


def render_command(cmd: Sequence[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


def confirm_dangerous(action: str, cmd: Sequence[str]) -> bool:
    print("Proposed command:")
    print("  " + render_command(cmd))
    while True:
        answer = prompt(f"{action.title()} is destructive. Proceed? [y/N]: ").strip().lower()
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no", ""}:
            return False
        print("Please answer yes or no.")


def detect_action_from_args(args: Sequence[str]) -> str:
    for arg in args:
        if arg.startswith("-"):
            continue
        return arg
    return "raw"


def print_help():
    print(
        textwrap.dedent(
            """
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
          - Set KUBE_AGENT_CODEX_MODE=online to use Codex cloud auth.
          - Offline translation requires KUBE_AGENT_CODEX_LOCAL_PROVIDER.
        """
        ).strip()
    )


def main():
    print("Kube agent ready. Type 'help' for examples.")
    try:
        ensure_kubectl()
    except RuntimeError as exc:
        print(str(exc))
        sys.exit(1)
    while True:
        try:
            text = prompt("kube-agent> ").strip()
        except UserAbort:
            print("\nExiting.")
            break

        result, error = translate_to_kubectl(text)
        if error:
            print(error)
            continue
        if result.action == "exit":
            break
        if result.action == "help":
            print_help()
            continue

        try:
            context = choose_context()
            namespace, all_namespaces = choose_namespace(context)
        except UserAbort:
            print("\nExiting.")
            break

        cmd = build_command(result.args, context, namespace, all_namespaces)

        action = result.action
        if action == "raw":
            action = detect_action_from_args(result.args)
        if action in DESTRUCTIVE_ACTIONS:
            if not confirm_dangerous(action, cmd):
                print("Skipped.")
                continue
        else:
            print("Proposed command:")
            print("  " + render_command(cmd))

        try:
            completed = run_command(cmd, check=False)
        except FileNotFoundError:
            print("kubectl is not installed or not on PATH.")
            sys.exit(1)
        if completed.stdout:
            print(completed.stdout.rstrip())
        if completed.stderr:
            print(completed.stderr.rstrip())
        if completed.returncode != 0:
            print(f"Command exited with status {completed.returncode}.")


if __name__ == "__main__":
    main()
