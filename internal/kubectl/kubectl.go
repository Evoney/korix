package kubectl

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"os/exec"
	"strings"
	"time"
)

type Client struct {
	Binary  string
	Timeout time.Duration
}

type Result struct {
	Stdout   string
	Stderr   string
	ExitCode int
}

func New() Client {
	return Client{Binary: "kubectl", Timeout: 60 * time.Second}
}

func (c Client) EnsureInstalled() error {
	_, err := exec.LookPath(c.binary())
	if err != nil {
		return errors.New("kubectl is not installed or not on PATH")
	}
	return nil
}

func (c Client) Run(args []string) (Result, error) {
	ctx, cancel := context.WithTimeout(context.Background(), c.timeout())
	defer cancel()

	cmd := exec.CommandContext(ctx, args[0], args[1:]...)
	var stdout bytes.Buffer
	var stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err := cmd.Run()
	result := Result{
		Stdout: strings.TrimRight(stdout.String(), "\n"),
		Stderr: strings.TrimRight(stderr.String(), "\n"),
	}
	if err == nil {
		return result, nil
	}
	if ctx.Err() == context.DeadlineExceeded {
		return result, ctx.Err()
	}
	var exitErr *exec.ExitError
	if errors.As(err, &exitErr) {
		result.ExitCode = exitErr.ExitCode()
		return result, nil
	}
	return result, err
}

func (c Client) GetJSON(args []string, target any, errorMessage string) error {
	result, err := c.Run(args)
	if err != nil {
		return err
	}
	if result.ExitCode != 0 {
		if result.Stderr != "" {
			return errors.New(result.Stderr)
		}
		return errors.New(errorMessage)
	}
	if strings.TrimSpace(result.Stdout) == "" {
		return json.Unmarshal([]byte("{}"), target)
	}
	if err := json.Unmarshal([]byte(result.Stdout), target); err != nil {
		return errors.New(errorMessage)
	}
	return nil
}

func (c Client) CurrentContext() string {
	result, err := c.Run([]string{c.binary(), "config", "current-context"})
	if err != nil || result.ExitCode != 0 {
		return ""
	}
	return strings.TrimSpace(result.Stdout)
}

func (c Client) Contexts() ([]string, error) {
	result, err := c.Run([]string{c.binary(), "config", "get-contexts", "-o", "name"})
	if err != nil {
		return nil, err
	}
	if result.ExitCode != 0 {
		if result.Stderr != "" {
			return nil, errors.New(result.Stderr)
		}
		return nil, errors.New("failed to list contexts")
	}
	contexts := splitNonEmptyLines(result.Stdout)
	if len(contexts) == 0 {
		return nil, errors.New("no kubectl contexts found")
	}
	return contexts, nil
}

func (c Client) binary() string {
	if c.Binary == "" {
		return "kubectl"
	}
	return c.Binary
}

func (c Client) timeout() time.Duration {
	if c.Timeout == 0 {
		return 60 * time.Second
	}
	return c.Timeout
}

func splitNonEmptyLines(value string) []string {
	lines := strings.Split(value, "\n")
	out := make([]string, 0, len(lines))
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line != "" {
			out = append(out, line)
		}
	}
	return out
}
