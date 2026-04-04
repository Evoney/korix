from dataclasses import dataclass, field
from datetime import UTC, datetime

from .commands import build_scoped_command
from .errors import KubectlError
from .kubectl import KubectlClient


@dataclass(frozen=True)
class OverviewMetric:
    label: str
    value: int
    status: str


@dataclass(frozen=True)
class PodRow:
    namespace: str
    name: str
    status: str
    ready: str
    restarts: int
    node: str
    age: str
    issue: str


@dataclass(frozen=True)
class DeploymentRow:
    namespace: str
    name: str
    ready: str
    available: int
    age: str
    issue: str


@dataclass(frozen=True)
class NodeRow:
    name: str
    status: str
    roles: str
    age: str
    issue: str


@dataclass(frozen=True)
class EventRow:
    namespace: str
    type: str
    reason: str
    obj: str
    age: str
    message: str


@dataclass(frozen=True)
class DashboardSnapshot:
    overview: list[OverviewMetric] = field(default_factory=list)
    pods: list[PodRow] = field(default_factory=list)
    deployments: list[DeploymentRow] = field(default_factory=list)
    nodes: list[NodeRow] = field(default_factory=list)
    events: list[EventRow] = field(default_factory=list)
    namespaces: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)


class DashboardService:
    def __init__(self, kubectl: KubectlClient):
        self._kubectl = kubectl

    def refresh(
        self, context: str, namespace: str | None, all_namespaces: bool
    ) -> DashboardSnapshot:
        errors: dict[str, str] = {}
        pods: list[PodRow] = []
        deployments: list[DeploymentRow] = []
        nodes: list[NodeRow] = []
        events: list[EventRow] = []
        namespaces: list[str] = []

        try:
            pod_data = self._get_json(
                ["get", "pods", "-o", "json"], context, namespace, all_namespaces, namespaced=True
            )
            pods = parse_pods(pod_data)
        except KubectlError as exc:
            errors["pods"] = str(exc)

        try:
            deployment_data = self._get_json(
                ["get", "deployments", "-o", "json"],
                context,
                namespace,
                all_namespaces,
                namespaced=True,
            )
            deployments = parse_deployments(deployment_data)
        except KubectlError as exc:
            errors["deployments"] = str(exc)

        try:
            node_data = self._get_json(
                ["get", "nodes", "-o", "json"], context, namespace, all_namespaces, namespaced=False
            )
            nodes = parse_nodes(node_data)
        except KubectlError as exc:
            errors["nodes"] = str(exc)

        try:
            event_data = self._get_json(
                ["get", "events", "-o", "json"], context, namespace, all_namespaces, namespaced=True
            )
            events = parse_events(event_data)
        except KubectlError as exc:
            errors["events"] = str(exc)

        try:
            namespace_data = self._get_json(
                ["get", "namespaces", "-o", "json"],
                context,
                namespace,
                all_namespaces,
                namespaced=False,
            )
            namespaces = parse_namespaces(namespace_data)
        except KubectlError as exc:
            errors["namespaces"] = str(exc)

        return DashboardSnapshot(
            overview=build_overview(pods, deployments, nodes, events),
            pods=pods,
            deployments=deployments,
            nodes=nodes,
            events=events,
            namespaces=namespaces,
            errors=errors,
        )

    def _get_json(
        self,
        args: list[str],
        context: str,
        namespace: str | None,
        all_namespaces: bool,
        namespaced: bool,
    ) -> dict[str, object]:
        cmd = build_scoped_command(args, context, namespace, all_namespaces, namespaced=namespaced)
        resource = next(
            (part for part in args if not part.startswith("-") and part != "get"), "resource"
        )
        return self._kubectl.get_json(cmd, f"Failed to load {resource}.")


def parse_pods(payload: dict[str, object]) -> list[PodRow]:
    rows: list[PodRow] = []
    for item in payload.get("items", []):
        metadata = item.get("metadata", {})
        status = item.get("status", {})
        spec = item.get("spec", {})
        container_statuses = status.get("containerStatuses") or []
        restarts = sum(int(container.get("restartCount", 0)) for container in container_statuses)
        ready_count = sum(1 for container in container_statuses if container.get("ready"))
        total_count = len(container_statuses)
        pod_status, issue = summarize_pod_status(item)
        rows.append(
            PodRow(
                namespace=metadata.get("namespace", "default"),
                name=metadata.get("name", ""),
                status=pod_status,
                ready=f"{ready_count}/{total_count}",
                restarts=restarts,
                node=spec.get("nodeName", "-"),
                age=format_age(metadata.get("creationTimestamp")),
                issue=issue,
            )
        )
    return sorted(rows, key=lambda row: pod_sort_key(row))


def parse_deployments(payload: dict[str, object]) -> list[DeploymentRow]:
    rows: list[DeploymentRow] = []
    for item in payload.get("items", []):
        metadata = item.get("metadata", {})
        spec = item.get("spec", {})
        status = item.get("status", {})
        desired = int(spec.get("replicas", 0))
        ready = int(status.get("readyReplicas", 0))
        available = int(status.get("availableReplicas", 0))
        issue = "Healthy"
        if ready < desired:
            issue = "Ready replicas below desired"
        elif available < desired:
            issue = "Available replicas below desired"
        rows.append(
            DeploymentRow(
                namespace=metadata.get("namespace", "default"),
                name=metadata.get("name", ""),
                ready=f"{ready}/{desired}",
                available=available,
                age=format_age(metadata.get("creationTimestamp")),
                issue=issue,
            )
        )
    return sorted(rows, key=lambda row: (row.issue == "Healthy", row.namespace, row.name))


def parse_nodes(payload: dict[str, object]) -> list[NodeRow]:
    rows: list[NodeRow] = []
    for item in payload.get("items", []):
        metadata = item.get("metadata", {})
        labels = metadata.get("labels", {})
        ready, issue = summarize_node(item)
        roles = extract_node_roles(labels)
        rows.append(
            NodeRow(
                name=metadata.get("name", ""),
                status=ready,
                roles=roles,
                age=format_age(metadata.get("creationTimestamp")),
                issue=issue,
            )
        )
    return sorted(rows, key=lambda row: (row.status == "Ready", row.name))


def parse_events(payload: dict[str, object]) -> list[EventRow]:
    rows: list[EventRow] = []
    for item in payload.get("items", []):
        metadata = item.get("metadata", {})
        regarding = item.get("regarding") or item.get("involvedObject") or {}
        namespace = metadata.get("namespace") or regarding.get("namespace") or "-"
        message = item.get("note") or item.get("message") or ""
        reason = item.get("reason", "")
        event_type = item.get("type", "Normal")
        obj = f"{regarding.get('kind', '')}/{regarding.get('name', '')}".strip("/")
        timestamp = (
            item.get("eventTime")
            or metadata.get("creationTimestamp")
            or item.get("lastTimestamp")
            or item.get("firstTimestamp")
        )
        rows.append(
            EventRow(
                namespace=namespace,
                type=event_type,
                reason=reason,
                obj=obj or "-",
                age=format_age(timestamp),
                message=message,
            )
        )
    rows.sort(key=event_sort_key)
    return rows[:100]


def parse_namespaces(payload: dict[str, object]) -> list[str]:
    namespaces: list[str] = []
    for item in payload.get("items", []):
        metadata = item.get("metadata", {})
        name = metadata.get("name")
        if name:
            namespaces.append(name)
    return sorted(namespaces)


def build_overview(
    pods: list[PodRow],
    deployments: list[DeploymentRow],
    nodes: list[NodeRow],
    events: list[EventRow],
) -> list[OverviewMetric]:
    unhealthy_pods = sum(1 for row in pods if row.issue != "Healthy")
    failing_deployments = sum(1 for row in deployments if row.issue != "Healthy")
    not_ready_nodes = sum(1 for row in nodes if row.status != "Ready")
    warning_events = sum(1 for row in events if row.type == "Warning")
    return [
        OverviewMetric("Unhealthy pods", unhealthy_pods, severity(unhealthy_pods)),
        OverviewMetric("Deployments at risk", failing_deployments, severity(failing_deployments)),
        OverviewMetric("Not ready nodes", not_ready_nodes, severity(not_ready_nodes)),
        OverviewMetric("Warning events", warning_events, severity(warning_events)),
    ]


def severity(count: int) -> str:
    return "warning" if count > 0 else "ok"


def summarize_pod_status(item: dict[str, object]) -> tuple[str, str]:
    metadata = item.get("metadata", {})
    status = item.get("status", {})
    if metadata.get("deletionTimestamp"):
        return "Terminating", "Resource is being deleted"

    container_statuses = status.get("containerStatuses") or []
    for container in container_statuses:
        state = container.get("state") or {}
        waiting = state.get("waiting")
        if waiting:
            reason = waiting.get("reason", "Waiting")
            return reason, waiting.get("message") or reason
        terminated = state.get("terminated")
        if terminated:
            reason = terminated.get("reason", "Terminated")
            return reason, terminated.get("message") or reason

    phase = status.get("phase", "Unknown")
    if phase == "Running":
        ready_count = sum(1 for container in container_statuses if container.get("ready"))
        total_count = len(container_statuses)
        if total_count and ready_count != total_count:
            return "NotReady", "One or more containers are not ready"
        if sum(int(container.get("restartCount", 0)) for container in container_statuses) > 0:
            return "Running", "Containers restarted recently"
        return "Running", "Healthy"
    if phase == "Succeeded":
        return phase, "Completed"
    return phase, status.get("message") or phase


def summarize_node(item: dict[str, object]) -> tuple[str, str]:
    status = item.get("status", {})
    conditions = status.get("conditions") or []
    issues: list[str] = []
    ready_status = "Unknown"
    for condition in conditions:
        cond_type = condition.get("type")
        cond_status = condition.get("status")
        if cond_type == "Ready":
            ready_status = "Ready" if cond_status == "True" else "NotReady"
            if cond_status != "True":
                issues.append(condition.get("message") or "Node is not ready")
        elif cond_status == "True" and cond_type in {
            "DiskPressure",
            "MemoryPressure",
            "PIDPressure",
        }:
            issues.append(cond_type)
    issue = ", ".join(issues) if issues else "Healthy"
    return ready_status, issue


def extract_node_roles(labels: dict[str, str]) -> str:
    roles = []
    for label in labels:
        if label.startswith("node-role.kubernetes.io/"):
            role = label.split("/", 1)[1] or "worker"
            roles.append(role)
    if not roles:
        return "worker"
    return ",".join(sorted(set(roles)))


def format_age(timestamp: str | None) -> str:
    if not timestamp:
        return "-"
    dt = parse_timestamp(timestamp)
    if not dt:
        return "-"
    delta = datetime.now(UTC) - dt
    total_seconds = int(delta.total_seconds())
    if total_seconds < 60:
        return f"{total_seconds}s"
    if total_seconds < 3600:
        return f"{total_seconds // 60}m"
    if total_seconds < 86400:
        return f"{total_seconds // 3600}h"
    return f"{total_seconds // 86400}d"


def parse_timestamp(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def pod_sort_key(row: PodRow) -> tuple[int, int, str, str]:
    unhealthy = 0 if row.issue != "Healthy" else 1
    warning = (
        0 if row.status in {"CrashLoopBackOff", "ImagePullBackOff", "ErrImagePull", "Failed"} else 1
    )
    return (unhealthy, warning, row.namespace, row.name)


def event_sort_key(row: EventRow) -> tuple[int, str, str]:
    severity_rank = 0 if row.type == "Warning" else 1
    return (severity_rank, row.age, row.reason)
