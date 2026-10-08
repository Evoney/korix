package translation

import (
	"errors"
	"strings"

	"github.com/evoneymendonca/korix/internal/kubecommand"
	"github.com/evoneymendonca/korix/internal/llm"
)

const prompt = `You are a CLI assistant that converts natural-language Kubernetes requests into a single kubectl command.
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
- Prefer concise, direct commands.`

const errorOutputPrefix = "ERROR:"

type CommandSpec struct {
	Action string
	Args   []string
}

type Translator struct {
	Provider llm.Provider
}

func (t Translator) Translate(text string) (CommandSpec, error) {
	raw := strings.TrimSpace(text)
	if raw == "" {
		return CommandSpec{}, errors.New("empty input")
	}
	if strings.HasPrefix(strings.ToLower(raw), "kubectl ") {
		parts, err := splitCommandLine(raw)
		if err != nil {
			return CommandSpec{}, err
		}
		return CommandSpec{Action: "raw", Args: parts[1:]}, nil
	}
	output, err := t.Provider.Run(prompt + "\n\nRequest: " + raw + "\n")
	if err != nil {
		return CommandSpec{}, err
	}
	line := ExtractKubectlLine(output)
	if line == "" {
		return CommandSpec{}, errors.New("LLM provider did not return a kubectl command")
	}
	if strings.HasPrefix(line, errorOutputPrefix) {
		reason := strings.TrimSpace(strings.TrimPrefix(line, errorOutputPrefix))
		if reason == "" {
			reason = "unable to translate request"
		}
		return CommandSpec{}, errors.New(reason)
	}
	parts, err := splitCommandLine(line)
	if err != nil {
		return CommandSpec{}, err
	}
	if len(parts) == 0 || parts[0] != "kubectl" {
		return CommandSpec{}, errors.New("LLM provider returned a non-kubectl command")
	}
	args := parts[1:]
	if err := kubecommand.ValidateTranslatedArgs(args); err != nil {
		return CommandSpec{}, err
	}
	return CommandSpec{Action: "raw", Args: args}, nil
}

func ExtractKubectlLine(output string) string {
	if output == "" {
		return ""
	}
	for _, line := range strings.Split(output, "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		line = strings.Trim(line, "`")
		line = strings.TrimPrefix(line, "$ ")
		line = strings.TrimPrefix(line, "> ")
		if strings.HasPrefix(line, "kubectl ") || line == "kubectl" {
			return line
		}
		if index := strings.Index(line, "kubectl "); index >= 0 {
			return line[index:]
		}
	}
	if strings.HasPrefix(output, errorOutputPrefix) {
		return output
	}
	return ""
}

func splitCommandLine(input string) ([]string, error) {
	args := []string{}
	var current strings.Builder
	var quote rune
	escaped := false
	for _, char := range input {
		switch {
		case escaped:
			current.WriteRune(char)
			escaped = false
		case char == '\\':
			escaped = true
		case quote != 0:
			if char == quote {
				quote = 0
			} else {
				current.WriteRune(char)
			}
		case char == '\'' || char == '"':
			quote = char
		case char == ' ' || char == '\t' || char == '\n':
			if current.Len() > 0 {
				args = append(args, current.String())
				current.Reset()
			}
		default:
			current.WriteRune(char)
		}
	}
	if escaped {
		current.WriteRune('\\')
	}
	if quote != 0 {
		return nil, errors.New("could not parse command: unclosed quote")
	}
	if current.Len() > 0 {
		args = append(args, current.String())
	}
	return args, nil
}
