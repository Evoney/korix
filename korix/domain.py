from dataclasses import dataclass


@dataclass(frozen=True)
class CommandSpec:
    action: str
    args: list[str]
