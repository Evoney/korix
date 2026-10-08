# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Korix is a terminal control plane for Kubernetes: a fullscreen TUI that shells out to `kubectl`, plus a natural-language box that translates requests into a single `kubectl` command through a pluggable LLM provider. There are two implementations that ship side by side:

- **Python** (`korix/`): the default `korix` launcher. Uses only the standard library (curses TUI, no runtime dependencies).
- **Go** (`cmd/korix-go`, `internal/`): a parallel port installed as `korix-go`, built on `tview`/`tcell`. The Python app stays the default until the Go port reaches release parity.

Most Python modules have a Go counterpart with the same name and responsibilities (`commands.py` ↔ `internal/kubecommand`, `actions.py` ↔ `internal/actions`, `dashboard.py` ↔ `internal/dashboard`, `translation.py` ↔ `internal/translation`, `llm.py`+`config.py` ↔ `internal/llm`, `tui.py` ↔ `internal/tui`). **When you change behavior in one, check whether the other needs the same change.** Design notes for the port and features live in `docs/plans/`.

## Commands

Use the venv's interpreter with `-m` (`.venv/bin/python -m ...`). Wrapper scripts like `.venv/bin/black` can break after the repo directory moves.

```bash
# Python: these must all pass, since CI and the release workflow run the same checks
.venv/bin/python -m ruff check .
.venv/bin/python -m black --check .
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m build

# Single Python test
.venv/bin/python -m unittest tests.test_commands
.venv/bin/python -m unittest tests.test_commands.CommandsTest.test_build_kubectl_command_adds_all_namespaces

# Go
go test ./...
go test ./internal/kubecommand -run TestBuildKubectlCommandAddsAllNamespaces
go build -o /tmp/korix-go ./cmd/korix-go
go mod tidy && git diff --exit-code -- go.mod go.sum   # CI fails if not tidy

# Run locally
python3 -m korix               # TUI
python3 -m korix --legacy-cli  # original prompt-based interface (korix/legacy_cli.py)
go run ./cmd/korix-go
```

Ruff (`E,F,I,UP`) and black both use line length 100 and target py311. Tests use `unittest`, not pytest.

## Architecture

Layering, which is the same in both languages:

1. **Command building** (`commands.py` / `kubecommand`): builds the final `kubectl` argv. It injects `--context` and `--namespace`/`-A` from the TUI's current scope unless the args already carry those flags. Plugin commands (anything not in `BUILTIN_COMMANDS` in `constants`) get no injected context. This layer also owns `is_mutating_command`, which decides whether a command needs confirmation, and `validate_translated_args`, which rejects shell control tokens in LLM output. Commands are always run as argv lists with no shell.
2. **Actions** (`actions.py` / `actions`): typed `ActionSpec`s for the TUI's guarded operations (delete pod, rollout restart/undo, scale, cordon, and so on). Each spec carries `requires_confirmation`. Exec and port-forward are only rendered as previews and are never run inside the TUI.
3. **Dashboard** (`dashboard.py` / `dashboard`): fetches `kubectl get ... -o json` per section and parses it into domain records with an `issue` or severity used for overview health.
4. **Translation + LLM** (`translation.py`, `llm.py`, `config.py`): `Translator` passes raw `kubectl ...` input straight through. Anything else goes to an `LLMProvider` (`cli`, which invokes `<bin> exec --output-last-message <file>`, or `openai-compatible` over HTTP). The first `kubectl` line is extracted from the reply, and `ERROR:` replies are surfaced to the user. The config comes from `KORIX_LLM_*` environment variables (see README). API keys entered in the TUI are kept in memory only.
5. **TUI** (`tui.py` / `tui`): section navigation, key bindings, command history, and the confirm-before-mutate flow. `kubectl.py` / `internal/kubectl` is the thin subprocess wrapper.

## Releases

Version source of truth is `project.version` in `pyproject.toml`. Bump it, commit, then `bash scripts/create-release-tag.sh --push` (this needs a clean worktree, and the tag must not already exist). Pushing a `vX.Y.Z` tag triggers `.github/workflows/release.yml`. That workflow validates the tag against pyproject, reruns all Python and Go checks, and publishes the wheel/sdist plus `korix-go` binaries for linux-amd64, darwin-amd64 and darwin-arm64 to a GitHub Release.

## Workflow

`main`-based: short-lived branches and small PRs back to `main` (see CONTRIBUTING.md). Commits follow Conventional Commits (`feat:`, `docs:`, ...).
