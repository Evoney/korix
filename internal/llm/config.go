package llm

import (
	"errors"
	"os"
	"strconv"
	"strings"
)

const DefaultOpenAICompatibleBaseURL = "https://api.openai.com/v1"

var SupportedProviders = []string{"cli", "openai-compatible"}

type Config struct {
	Provider         string
	BinPath          string
	Model            string
	Mode             string
	LocalProvider    string
	TimeoutSeconds   int
	SkipGitRepoCheck bool
	BaseURL          string
	APIKey           string
}

func LoadConfigFromEnv() (Config, error) {
	return LoadConfig(os.LookupEnv)
}

func LoadConfig(lookup func(string) (string, bool)) (Config, error) {
	timeoutValue := valueOrDefault(lookup, "KORIX_LLM_TIMEOUT", "60")
	timeout, err := strconv.Atoi(timeoutValue)
	if err != nil {
		return Config{}, errors.New("KORIX_LLM_TIMEOUT must be an integer")
	}
	return Config{
		Provider:         strings.ToLower(valueOrDefault(lookup, "KORIX_LLM_PROVIDER", "cli")),
		BinPath:          valueOrDefault(lookup, "KORIX_LLM_BIN", "llm"),
		Model:            valueOrDefault(lookup, "KORIX_LLM_MODEL", ""),
		Mode:             valueOrDefault(lookup, "KORIX_LLM_MODE", ""),
		LocalProvider:    valueOrDefault(lookup, "KORIX_LLM_LOCAL_PROVIDER", ""),
		TimeoutSeconds:   timeout,
		SkipGitRepoCheck: truthy(valueOrDefault(lookup, "KORIX_LLM_SKIP_GIT_REPO_CHECK", "1")),
		BaseURL:          valueOrDefault(lookup, "KORIX_LLM_BASE_URL", ""),
		APIKey:           valueOrDefault(lookup, "KORIX_LLM_API_KEY", ""),
	}, nil
}

func (c Config) ResolveCLIMode() (bool, string, error) {
	mode := strings.ToLower(c.Mode)
	if mode == "" {
		mode = "online"
	}
	switch mode {
	case "auto":
		return c.LocalProvider != "", c.LocalProvider, nil
	case "online":
		return false, "", nil
	case "offline":
		if c.LocalProvider == "" {
			return false, "", errors.New("offline mode requires KORIX_LLM_LOCAL_PROVIDER")
		}
		return true, c.LocalProvider, nil
	default:
		return false, "", errors.New("invalid KORIX_LLM_MODE; use offline, online, or auto")
	}
}

func valueOrDefault(lookup func(string) (string, bool), key, fallback string) string {
	if value, ok := lookup(key); ok && value != "" {
		return value
	}
	return fallback
}

func truthy(value string) bool {
	switch strings.ToLower(value) {
	case "1", "true", "yes":
		return true
	default:
		return false
	}
}
