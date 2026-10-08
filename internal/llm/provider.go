package llm

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
)

type Provider interface {
	Run(prompt string) (string, error)
}

func BuildProvider(config Config) (Provider, error) {
	switch strings.ToLower(config.Provider) {
	case "", "cli":
		return CLIProvider{Config: config}, nil
	case "openai-compatible":
		if config.Model == "" {
			return nil, errors.New("model is required for the openai-compatible provider")
		}
		if config.APIKey == "" {
			return nil, errors.New("api key is required for the openai-compatible provider")
		}
		return OpenAICompatibleProvider{Config: config}, nil
	default:
		return nil, errors.New("unsupported LLM provider: " + config.Provider)
	}
}

type CLIProvider struct {
	Config Config
}

func (p CLIProvider) Run(prompt string) (string, error) {
	useLocal, localProvider, err := p.Config.ResolveCLIMode()
	if err != nil {
		return "", err
	}
	tmpDir, err := os.MkdirTemp("", "korix-llm-*")
	if err != nil {
		return "", err
	}
	defer os.RemoveAll(tmpDir)

	outputPath := filepath.Join(tmpDir, "llm-output.txt")
	args := []string{"exec"}
	if p.Config.SkipGitRepoCheck {
		args = append(args, "--skip-git-repo-check")
	}
	if useLocal {
		args = append(args, "--oss")
	}
	if localProvider != "" {
		args = append(args, "--local-provider", localProvider)
	}
	if p.Config.Model != "" {
		args = append(args, "--model", p.Config.Model)
	}
	args = append(args, "--output-last-message", outputPath)

	ctx, cancel := context.WithTimeout(context.Background(), timeout(p.Config))
	defer cancel()

	cmd := exec.CommandContext(ctx, p.Config.BinPath, args...)
	cmd.Stdin = strings.NewReader(prompt)
	var stderr bytes.Buffer
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		if ctx.Err() == context.DeadlineExceeded {
			return "", errors.New("LLM request timed out")
		}
		if stderr.Len() > 0 {
			return "", errors.New(strings.TrimSpace(stderr.String()))
		}
		return "", err
	}
	output, err := os.ReadFile(outputPath)
	if err != nil {
		return "", errors.New("LLM provider failed to produce output")
	}
	trimmed := strings.TrimSpace(string(output))
	if trimmed == "" {
		return "", errors.New("LLM provider returned empty output")
	}
	return trimmed, nil
}

type OpenAICompatibleProvider struct {
	Config Config
}

func (p OpenAICompatibleProvider) Run(prompt string) (string, error) {
	baseURL := strings.TrimRight(p.Config.BaseURL, "/")
	if baseURL == "" {
		baseURL = DefaultOpenAICompatibleBaseURL
	}
	body := map[string]any{
		"model":       p.Config.Model,
		"messages":    []map[string]string{{"role": "user", "content": prompt}},
		"temperature": 0,
	}
	payload, err := json.Marshal(body)
	if err != nil {
		return "", err
	}
	ctx, cancel := context.WithTimeout(context.Background(), timeout(p.Config))
	defer cancel()
	request, err := http.NewRequestWithContext(
		ctx,
		http.MethodPost,
		baseURL+"/chat/completions",
		bytes.NewReader(payload),
	)
	if err != nil {
		return "", err
	}
	request.Header.Set("Authorization", "Bearer "+p.Config.APIKey)
	request.Header.Set("Content-Type", "application/json")

	response, err := http.DefaultClient.Do(request)
	if err != nil {
		return "", err
	}
	defer response.Body.Close()
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		return "", errors.New("provider HTTP error: " + response.Status)
	}
	var decoded struct {
		Choices []struct {
			Message struct {
				Content string `json:"content"`
			} `json:"message"`
		} `json:"choices"`
	}
	if err := json.NewDecoder(response.Body).Decode(&decoded); err != nil {
		return "", errors.New("provider returned an unexpected response shape")
	}
	if len(decoded.Choices) == 0 {
		return "", errors.New("provider returned no choices")
	}
	output := strings.TrimSpace(decoded.Choices[0].Message.Content)
	if output == "" {
		return "", errors.New("provider returned empty output")
	}
	return output, nil
}

func TestProviderConnection(provider Provider) (string, error) {
	return provider.Run("Reply with exactly: OK")
}

func timeout(config Config) time.Duration {
	if config.TimeoutSeconds <= 0 {
		return 60 * time.Second
	}
	return time.Duration(config.TimeoutSeconds) * time.Second
}
