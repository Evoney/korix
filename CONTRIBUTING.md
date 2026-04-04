# Contributing to Korix

Thanks for contributing to Korix.

Korix uses a main-based workflow. `main` is the only long-lived branch, and changes should reach it through small, reviewable pull requests.

## Development Setup

Korix currently targets Python 3.11+.

Typical local setup:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -e . black ruff build
```

If you are working on code changes, run the local checks before opening a pull request:

```bash
.venv/bin/ruff check .
.venv/bin/python -m black --check korix tests
python3 -m unittest discover -s tests
.venv/bin/python -m build
```

## How to Contribute

1. Start from the latest `main`.
2. Create a short-lived branch for your change.
3. Keep the change scoped and avoid unrelated cleanup.
4. Add or update tests when behavior changes.
5. Open a pull request back to `main`.

Good contributions usually have:

- one clear purpose
- a small and understandable diff
- passing local checks
- updated docs when user-facing behavior changes

## Pull Request Checklist

Before opening or merging a PR, make sure:

- the branch is based on current `main`
- lint, format, tests, and build pass locally
- the change is described clearly in the PR
- screenshots or terminal output are included when UI behavior changes
- docs are updated if commands, installation, or workflows changed

## CI

Every pull request and every push to `main` runs the `CI` workflow. It verifies:

- lint with `ruff`
- formatting with `black --check`
- unit tests
- package build

The goal is that `main` stays in a releasable state.

## Release Process

This section is for maintainers.

Korix releases are created from `main` with semantic version tags.

1. Update `project.version` in `pyproject.toml`.
2. Merge that version change into `main`.
3. Confirm `main` is green.
4. Create and push the release tag:

```bash
bash scripts/create-release-tag.sh --push
```

The helper script:

- reads the version from `pyproject.toml`
- requires a clean git worktree
- creates an annotated tag like `v0.1.0`
- can push the tag to `origin`

When the tag reaches GitHub, the `Release` workflow:

- checks that the tag matches `pyproject.toml`
- reruns lint, format, tests, and build
- publishes a GitHub Release with the built artifacts

## Versioning

Korix uses semantic versions in the form `MAJOR.MINOR.PATCH`.

- increment `PATCH` for fixes and small internal improvements
- increment `MINOR` for backward-compatible features
- increment `MAJOR` for breaking changes
