# Parallel Go Port Design

## Goal

Add a Go implementation of Korix alongside the current Python application. The
Python CLI remains the default while the Go port reaches feature parity.

## Architecture

- `go.mod` defines the Go module.
- `cmd/korix-go/main.go` is the development entrypoint.
- `internal/kubectl` shells out to `kubectl`, loads JSON, and handles contexts.
- `internal/dashboard` owns typed resource rows and Kubernetes JSON parsers.
- `internal/actions` owns action specs, command builders, scoping, mutating
  detection, and preview-only operations.
- `internal/llm` owns provider configuration and provider execution.
- `internal/translation` owns prompt construction, command extraction, and
  translated command validation.
- `internal/tui` owns the terminal UI.

## TUI Direction

Use Go's `tview` and `tcell` stack for the terminal UI. This is the pragmatic
Go equivalent for a richer terminal application and avoids recreating curses
behavior manually.

## Migration Behavior

- Keep the Python package and `korix` launcher unchanged.
- Run the Go port during development with `go run ./cmd/korix-go`.
- After parity is proven, update installation and release packaging to build a
  native `korix` binary.

## Feature Parity Target

The Go port should match the current Python behavior:

- dashboard sections for overview, pods, deployments, services, ingresses,
  statefulsets, daemonsets, jobs, cronjobs, nodes, events, namespaces, LLM
  settings, history, and actions
- describe, logs, previous logs, delete pod, scale deployment, cordon, uncordon
- rollout restart, status, history, and undo
- preview-only port-forward and pod exec
- natural-language command translation, validation, command history, and
  mutating command confirmation

## Testing

Add Go unit tests for parser behavior, command scoping, mutating detection,
action builders, and translation extraction/validation. Keep the Python tests in
place while both implementations coexist.
