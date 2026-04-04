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


def rollout_restart_deployment(name: str) -> ActionSpec:
    return ActionSpec(
        label=f"Restart deployment {name}",
        args=["rollout", "restart", "deployment", name],
        requires_confirmation=True,
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
