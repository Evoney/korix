package actions

import (
	"errors"
	"regexp"
	"strconv"
	"strings"
)

type Scope string

const (
	ScopeCluster    Scope = "cluster"
	ScopeNamespaced Scope = "namespaced"
	ScopeRaw        Scope = "raw"
)

type Spec struct {
	Label                string
	Args                 []string
	Scope                Scope
	RequiresConfirmation bool
	PreviewOnly          bool
}

func FromTranslatedCommand(args []string, mutating bool) Spec {
	return Spec{
		Label:                "Natural-language command",
		Args:                 append([]string(nil), args...),
		Scope:                ScopeRaw,
		RequiresConfirmation: mutating,
	}
}

func DescribeResource(kind, name string, namespaced bool) Spec {
	scope := ScopeCluster
	if namespaced {
		scope = ScopeNamespaced
	}
	return Spec{
		Label: "Describe " + kind + " " + name,
		Args:  []string{"describe", kind, name},
		Scope: scope,
	}
}

func LogsPod(name string, previous bool) Spec {
	args := []string{"logs", name}
	if previous {
		args = append(args, "--previous")
	}
	return Spec{Label: "Logs for pod " + name, Args: args, Scope: ScopeNamespaced}
}

func DeletePod(name string) Spec {
	return Spec{
		Label:                "Delete pod " + name,
		Args:                 []string{"delete", "pod", name},
		Scope:                ScopeNamespaced,
		RequiresConfirmation: true,
	}
}

func RolloutRestart(kind, name string) Spec {
	return Spec{
		Label:                "Restart " + kind + " " + name,
		Args:                 []string{"rollout", "restart", kind, name},
		Scope:                ScopeNamespaced,
		RequiresConfirmation: true,
	}
}

func RolloutStatus(kind, name string) Spec {
	return Spec{
		Label: "Rollout status for " + kind + " " + name,
		Args:  []string{"rollout", "status", kind, name},
		Scope: ScopeNamespaced,
	}
}

func RolloutHistory(kind, name string) Spec {
	return Spec{
		Label: "Rollout history for " + kind + " " + name,
		Args:  []string{"rollout", "history", kind, name},
		Scope: ScopeNamespaced,
	}
}

func RolloutUndo(kind, name string) Spec {
	return Spec{
		Label:                "Rollout undo for " + kind + " " + name,
		Args:                 []string{"rollout", "undo", kind, name},
		Scope:                ScopeNamespaced,
		RequiresConfirmation: true,
	}
}

func ScaleDeployment(name string, replicas int) Spec {
	return Spec{
		Label:                "Scale deployment " + name + " to " + strconv.Itoa(replicas),
		Args:                 []string{"scale", "deployment", name, "--replicas", strconv.Itoa(replicas)},
		Scope:                ScopeNamespaced,
		RequiresConfirmation: true,
	}
}

func PortForwardResource(kind, name, mapping string) (Spec, error) {
	if !validPortMapping(mapping) {
		return Spec{}, errors.New("port mapping must look like local:remote, for example 8080:80")
	}
	return Spec{
		Label:       "Port-forward " + kind + " " + name,
		Args:        []string{"port-forward", kind + "/" + name, mapping},
		Scope:       ScopeNamespaced,
		PreviewOnly: true,
	}, nil
}

func ExecPod(name string, command []string) (Spec, error) {
	if len(command) == 0 {
		return Spec{}, errors.New("exec command cannot be empty")
	}
	args := append([]string{"exec", "-it", name, "--"}, command...)
	return Spec{
		Label:       "Exec in pod " + name,
		Args:        args,
		Scope:       ScopeNamespaced,
		PreviewOnly: true,
	}, nil
}

func CordonNode(name string) Spec {
	return Spec{
		Label:                "Cordon node " + name,
		Args:                 []string{"cordon", name},
		Scope:                ScopeCluster,
		RequiresConfirmation: true,
	}
}

func UncordonNode(name string) Spec {
	return Spec{
		Label:                "Uncordon node " + name,
		Args:                 []string{"uncordon", name},
		Scope:                ScopeCluster,
		RequiresConfirmation: true,
	}
}

var portMappingPattern = regexp.MustCompile(`^\d+:\d+$`)

func validPortMapping(mapping string) bool {
	return portMappingPattern.MatchString(strings.TrimSpace(mapping))
}
