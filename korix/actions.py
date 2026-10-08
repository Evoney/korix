from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from .commands import is_mutating_command

ActionScope = Literal["cluster", "namespaced", "raw"]


@dataclass(frozen=True)
class ActionSpec:
    label: str
    args: list[str]
    scope: ActionScope = "namespaced"
    requires_confirmation: bool = False
    preview_only: bool = False


def from_translated_command(args: Sequence[str]) -> ActionSpec:
    return ActionSpec(
        label="Natural-language command",
        args=list(args),
        scope="raw",
        requires_confirmation=is_mutating_command(args),
    )


def describe_resource(kind: str, name: str, namespaced: bool = True) -> ActionSpec:
    return ActionSpec(
        label=f"Describe {kind} {name}", args=["describe", kind, name], scope=_scope(namespaced)
    )


def logs_pod(name: str, previous: bool = False) -> ActionSpec:
    args = ["logs", name]
    if previous:
        args.append("--previous")
    return ActionSpec(label=f"Logs for pod {name}", args=args)


def delete_pod(name: str) -> ActionSpec:
    return ActionSpec(
        label=f"Delete pod {name}",
        args=["delete", "pod", name],
        requires_confirmation=True,
    )


def rollout_restart(kind: str, name: str) -> ActionSpec:
    return ActionSpec(
        label=f"Restart {kind} {name}",
        args=["rollout", "restart", kind, name],
        requires_confirmation=True,
    )


def rollout_restart_deployment(name: str) -> ActionSpec:
    return rollout_restart("deployment", name)


def rollout_status(kind: str, name: str) -> ActionSpec:
    return ActionSpec(
        label=f"Rollout status for {kind} {name}",
        args=["rollout", "status", kind, name],
    )


def rollout_history(kind: str, name: str) -> ActionSpec:
    return ActionSpec(
        label=f"Rollout history for {kind} {name}",
        args=["rollout", "history", kind, name],
    )


def rollout_undo(kind: str, name: str) -> ActionSpec:
    return ActionSpec(
        label=f"Rollout undo for {kind} {name}",
        args=["rollout", "undo", kind, name],
        requires_confirmation=True,
    )


def port_forward_resource(kind: str, name: str, mapping: str) -> ActionSpec:
    return ActionSpec(
        label=f"Port-forward {kind} {name}",
        args=["port-forward", f"{kind}/{name}", mapping],
        preview_only=True,
    )


def exec_pod(name: str, command: Sequence[str]) -> ActionSpec:
    return ActionSpec(
        label=f"Exec in pod {name}",
        args=["exec", "-it", name, "--", *command],
        preview_only=True,
    )


def scale_deployment(name: str, replicas: int) -> ActionSpec:
    return ActionSpec(
        label=f"Scale deployment {name} to {replicas}",
        args=["scale", "deployment", name, "--replicas", str(replicas)],
        requires_confirmation=True,
    )


def cordon_node(name: str) -> ActionSpec:
    return ActionSpec(
        label=f"Cordon node {name}",
        args=["cordon", name],
        scope="cluster",
        requires_confirmation=True,
    )


def uncordon_node(name: str) -> ActionSpec:
    return ActionSpec(
        label=f"Uncordon node {name}",
        args=["uncordon", name],
        scope="cluster",
        requires_confirmation=True,
    )


def _scope(namespaced: bool) -> ActionScope:
    return "namespaced" if namespaced else "cluster"
