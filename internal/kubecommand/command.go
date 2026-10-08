package kubecommand

import (
	"errors"
	"slices"
	"strings"

	"github.com/evoneymendonca/korix/internal/constants"
)

var mutatingCommands = map[string]struct{}{
	"annotate": {},
	"apply":    {},
	"cordon":   {},
	"create":   {},
	"delete":   {},
	"drain":    {},
	"edit":     {},
	"label":    {},
	"patch":    {},
	"replace":  {},
	"scale":    {},
	"set":      {},
	"taint":    {},
	"uncordon": {},
}

var shellControlTokens = map[string]struct{}{
	";": {}, "&&": {}, "||": {}, "|": {}, ">": {}, ">>": {}, "<": {},
}

func BuildKubectlCommand(args []string, context, namespace string, allNamespaces bool) []string {
	cmd := []string{"kubectl", "--context", context}
	if isPluginCommand(args) {
		return append([]string{"kubectl"}, args...)
	}
	if HasFlag(args, constants.ContextFlags) {
		cmd = []string{"kubectl"}
	}
	if allNamespaces {
		if !HasFlag(args, constants.NamespaceFlags) && !HasFlag(args, constants.AllNamespaceFlags) {
			cmd = append(cmd, "-A")
		}
	} else if namespace != "" {
		if !HasFlag(args, union(constants.AllNamespaceFlags, constants.NamespaceFlags)) {
			cmd = append(cmd, "--namespace", namespace)
		}
	}
	return append(cmd, args...)
}

func BuildScopedCommand(
	args []string,
	context string,
	namespace string,
	allNamespaces bool,
	namespaced bool,
) []string {
	cmd := []string{"kubectl", "--context", context}
	if namespaced {
		if allNamespaces {
			cmd = append(cmd, "-A")
		} else if namespace != "" {
			cmd = append(cmd, "--namespace", namespace)
		}
	}
	return append(cmd, args...)
}

func RenderCommand(args []string) string {
	parts := make([]string, 0, len(args))
	for _, arg := range args {
		parts = append(parts, quote(arg))
	}
	return strings.Join(parts, " ")
}

func HasFlag(args []string, flags map[string]struct{}) bool {
	for _, arg := range args {
		if _, ok := flags[arg]; ok {
			return true
		}
		base, _, found := strings.Cut(arg, "=")
		if found {
			if _, ok := flags[base]; ok {
				return true
			}
		}
		if _, ok := flags["-n"]; ok && strings.HasPrefix(arg, "-n") && arg != "-n" {
			return true
		}
	}
	return false
}

func FirstCommandArg(args []string) string {
	for _, arg := range args {
		if !strings.HasPrefix(arg, "-") {
			return arg
		}
	}
	return ""
}

func ValidateTranslatedArgs(args []string) error {
	if len(args) == 0 {
		return errors.New("LLM provider returned an empty kubectl command")
	}
	for _, arg := range args {
		if _, ok := shellControlTokens[arg]; ok {
			return errors.New("LLM provider returned shell control syntax")
		}
		if strings.ContainsRune(arg, '\x00') {
			return errors.New("LLM provider returned an invalid command argument")
		}
	}
	if FirstCommandArg(args) == "" {
		return errors.New("LLM provider returned flags without a kubectl subcommand")
	}
	return nil
}

func IsMutatingCommand(args []string) bool {
	action := FirstCommandArg(args)
	if _, ok := mutatingCommands[action]; ok {
		return true
	}
	if action == "rollout" {
		nonFlags := make([]string, 0, len(args))
		for _, arg := range args {
			if !strings.HasPrefix(arg, "-") {
				nonFlags = append(nonFlags, arg)
			}
		}
		return len(nonFlags) >= 2 && slices.Contains([]string{"restart", "undo"}, nonFlags[1])
	}
	return false
}

func isPluginCommand(args []string) bool {
	cmd := FirstCommandArg(args)
	if cmd == "" {
		return false
	}
	_, ok := constants.BuiltinCommands[cmd]
	return !ok
}

func union(a, b map[string]struct{}) map[string]struct{} {
	out := make(map[string]struct{}, len(a)+len(b))
	for key := range a {
		out[key] = struct{}{}
	}
	for key := range b {
		out[key] = struct{}{}
	}
	return out
}

func quote(value string) string {
	if value == "" {
		return "''"
	}
	if strings.ContainsAny(value, " \t\n'\"\\$`!*?[]{}();&|<>") {
		return "'" + strings.ReplaceAll(value, "'", "'\\''") + "'"
	}
	return value
}
