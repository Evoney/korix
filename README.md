# Korix

Terminal control plane for Kubernetes operations.

Korix is a modern terminal console for Kubernetes inspection, incident
response, and guarded cluster actions. The default interface is a fullscreen
TUI built with the Python standard library, so it runs in a plain terminal
without extra UI dependencies.

The tool provides:

- cluster overview with unhealthy pods, deployments at risk, node readiness, and warning events
- section views for pods, deployments, nodes, events, and namespaces
- resource inspection with `describe` and logs
- guarded actions such as pod delete, deployment restart, deployment scale, and node cordon or uncordon
- a natural-language command box that translates requests into `kubectl`, previews the exact command, and confirms mutating actions before execution

## Supported OS

Korix supports:

- Linux
- macOS

Korix does not currently support native Windows. For Windows use WSL2.

## Installation

The recommended install path is the bundled installer. It creates a dedicated
virtual environment under `~/.local/share/korix`, installs Korix into it, and
places a `korix` launcher in `~/.local/bin`.

Requirements for installation:

- `bash`
- `python3` 3.11 or newer
- `python3 -m venv`

Install from a cloned repository:

```bash
git clone <your-repo-url> korix
cd korix
bash install/install-korix.sh
```

After install, run:

```bash
korix
```

Optional installer overrides:

```bash
KORIX_INSTALL_ROOT="$HOME/.local/share/korix" \
KORIX_BIN_DIR="$HOME/.local/bin" \
KORIX_PYTHON_BIN=python3 \
bash install/install-korix.sh
```

## Usage

Run the installed command:

```bash
korix
```

For local development without installing, start the TUI directly:

```bash
python3 korix.py
```

Or:

```bash
python3 -m korix
```

Run the original prompt-based interface:

```bash
python3 -m korix --legacy-cli
```

## TUI Keys

- `Tab`: switch focus between sections and item list
- `Up` / `Down`: move selection
- `Enter`: inspect current selection
- `g`: refresh data
- `C`: change context
- `n`: change namespace scope
- `:`: open the natural-language command prompt
- `q`: quit

Section-specific keys:

- Pods: `d` describe, `l` logs, `p` previous logs, `x` delete pod
- Deployments: `d` describe, `r` rollout restart, `s` scale
- Nodes: `d` describe, `c` cordon, `u` uncordon

## LLM configuration

Korix is provider-agnostic for natural-language translation.

V1 providers:

- `cli`
- `openai-compatible`

You can configure the active provider in the TUI under the `LLM` section.
Korix lets you choose the provider and model there, and for hosted providers
you can also paste the API key and base URL directly in the UI. API keys entered
in the UI are kept in memory for the current session only.

Environment variables are also supported as startup defaults:

```bash
export KORIX_LLM_PROVIDER=openai-compatible
export KORIX_LLM_MODEL=gpt-4.1-mini
export KORIX_LLM_BASE_URL=https://api.openai.com/v1
export KORIX_LLM_API_KEY=your_api_key_here
export KORIX_LLM_TIMEOUT=60
```

For CLI-based providers:

```bash
export KORIX_LLM_PROVIDER=cli
export KORIX_LLM_BIN=llm
export KORIX_LLM_MODEL=your-local-model
export KORIX_LLM_MODE=auto
export KORIX_LLM_LOCAL_PROVIDER=ollama
export KORIX_LLM_SKIP_GIT_REPO_CHECK=1
```

## Requirements

- Python 3.11+
- `kubectl` available on PATH
- an LLM provider configured if you want the natural-language command box

## Development

Run tests:

```bash
python3 -m unittest discover -s tests
```

The TUI can still start even if natural-language translation is unavailable. In
that case, the dashboard and explicit operator actions remain usable.

## Releases

Korix publishes GitHub releases automatically when you push a version tag in
the form `vX.Y.Z`.

Release flow:

1. Update `project.version` in `pyproject.toml`.
2. Commit the version change.
3. Create the tag from the checked-in version:

```bash
bash scripts/create-release-tag.sh --push
```

The helper script reads the version from `pyproject.toml`, requires a clean git
worktree, creates an annotated tag like `v0.1.1`, and can push it to `origin`.

When the tag reaches GitHub, the `Release` workflow:

- validates that the tag matches `pyproject.toml`
- runs `ruff`, `black --check`, unit tests, and `python -m build`
- publishes a GitHub Release with the built wheel and source distribution
