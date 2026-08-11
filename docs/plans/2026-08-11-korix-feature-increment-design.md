# Korix Feature Increment Design

## Goal

Expand Korix beyond the initial pod/deployment/node console into a broader
Kubernetes operations TUI while preserving the existing standard-library-only
runtime and guarded action model.

## Scope

- Add read-only dashboard sections for Services, Ingresses, StatefulSets,
  DaemonSets, Jobs, and CronJobs.
- Add describe support for every new resource section.
- Add higher-value operational actions: rollout status, rollout history,
  rollout undo, port-forward command preview, and exec command preview.
- Improve natural-language command execution with validation and in-memory
  command history.

## Architecture

The current code separates dashboard collection, action command construction,
command scoping, translation, and TUI rendering. The increment keeps those
boundaries:

- `dashboard.py` owns typed row models and parsers.
- `actions.py` owns small `ActionSpec` builders.
- `commands.py` owns command safety and scoping helpers.
- `translation.py` validates LLM output before it reaches execution.
- `tui.py` wires sections, key handling, prompts, previews, and detail text.

The implementation should reduce repeated TUI branching where practical, but it
should avoid a large declarative rewrite during this increment.

## Safety

Mutating actions remain explicitly confirmed. Riskier interactive workflows such
as port-forward and exec are emitted as preview commands rather than unmanaged
long-running sessions inside curses.

## Testing

Add focused unit tests for new parsers, action builders, and translation
validation. Run the existing unittest suite after implementation.
