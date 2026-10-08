package kubecommand

import (
	"errors"
	"slices"
	"strings"

	"github.com/evoneymendonca/korix/internal/constants"
)

var mutatingCommands = map[string]struct{}{
	"annotate":  {},
	"apply":     {},
	"attach":    {},
	"autoscale": {},
	"cordon":    {},
	"cp":        {},
	"create":    {},
	"debug":     {},
	"delete":    {},
	"drain":     {},
	"edit":      {},
	"exec":      {},
	"expose":    {},
	"label":     {},
	"patch":     {},
	"replace":   {},
	"run":       {},
	"scale":     {},
	"set":       {},
	"taint":     {},
	"uncordon":  {},
}

var mutatingRolloutSubcommands = []string{"pause", "restart", "resume", "undo"}

// Global flags whose value may follow as a separate argument, e.g. `-n prod`.
var valueFlags = map[string]struct{}{
	"-n": {}, "--namespace": {}, "--context": {}, "--kubeconfig": {}, "--cluster": {},
	"--user": {}, "-s": {}, "--server": {}, "--as": {}, "--as-group": {}, "--token": {},
	"--request-timeout": {},
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

func positionalArgs(args []string) []string {
	positionals := make([]string, 0, len(args))
	skipNext := false
	for _, arg := range args {
		if skipNext {
			skipNext = false
			continue
		}
		if arg == "--" {
			break
		}
		if strings.HasPrefix(arg, "-") {
			_, skipNext = valueFlags[arg]
			continue
		}
		positionals = append(positionals, arg)
	}
	return positionals
}

func FirstCommandArg(args []string) string {
	positionals := positionalArgs(args)
	if len(positionals) == 0 {
		return ""
	}
	return positionals[0]
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
		positionals := positionalArgs(args)
		return len(positionals) >= 2 && slices.Contains(mutatingRolloutSubcommands, positionals[1])
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
