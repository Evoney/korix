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
    "plugin",
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
