# kube-agent

Interactive Python agent that translates natural-language requests into `kubectl`
commands using Codex (online by default). It prompts for context and namespace
on every request and requires confirmation for apply/create/delete/scale.

## Usage

```
python3 kube_agent.py
```

## Codex configuration

The agent calls the `codex` CLI. Configure offline mode with a local provider or
use online mode with Codex cloud auth.

By default, the agent uses online mode.

Offline mode:

```
export KUBE_AGENT_CODEX_LOCAL_PROVIDER=ollama   # or ollama-chat, lmstudio
export KUBE_AGENT_CODEX_MODEL=your-local-model  # optional
```

Online mode:

```
export KUBE_AGENT_CODEX_MODE=online
```

Auto mode (offline when local provider is set, otherwise online):

```
export KUBE_AGENT_CODEX_MODE=auto
```

Optional overrides:

```
export KUBE_AGENT_CODEX_BIN=/path/to/codex
export KUBE_AGENT_CODEX_TIMEOUT=60
export KUBE_AGENT_CODEX_OSS=1   # legacy toggle, prefer KUBE_AGENT_CODEX_MODE
export KUBE_AGENT_CODEX_SKIP_GIT_REPO_CHECK=1
```

## Requirements

- Python 3.11+
- `kubectl` available on PATH
- `codex` CLI available on PATH and authenticated (online) or configured with a local provider (offline)

## Development

Format and lint:

```
python -m pip install black ruff
ruff check .
black .
```

## Examples

```
list pods
describe deployment api
logs pod api-123
apply ./manifest.yaml
delete service web
scale deployment api to 3 replicas
```
