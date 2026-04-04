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

## Codex configuration

Natural-language translation uses the `codex` CLI. Configure offline mode with a
local provider or use online mode with Codex cloud auth.

By default, the agent uses online mode.

Offline mode:

```bash
export KORIX_CODEX_LOCAL_PROVIDER=ollama   # or ollama-chat, lmstudio
export KORIX_CODEX_MODEL=your-local-model  # optional
```

Online mode:

```bash
export KORIX_CODEX_MODE=online
```

Auto mode (offline when local provider is set, otherwise online):

```bash
export KORIX_CODEX_MODE=auto
```

Optional overrides:

```bash
export KORIX_CODEX_BIN=/path/to/codex
export KORIX_CODEX_TIMEOUT=60
export KORIX_CODEX_OSS=1   # legacy toggle, prefer KORIX_CODEX_MODE
export KORIX_CODEX_SKIP_GIT_REPO_CHECK=1
```

## Requirements

- Python 3.11+
- `kubectl` available on PATH
- `codex` CLI available on PATH and authenticated (online) or configured with a local provider (offline) if you want the natural-language command box

## Development

Run tests:

```bash
python3 -m unittest discover -s tests
```

The TUI can still start even if Codex translation is unavailable. In that case,
the dashboard and explicit operator actions remain usable.
