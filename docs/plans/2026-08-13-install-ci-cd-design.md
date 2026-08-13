# Install Documentation and CI/CD Design

## Goal

Document installation for both Korix runtimes and update GitHub workflows so CI
and release builds verify the Python application and the parallel Go port.

## README

Keep the Python `korix` launcher as the default installation path. Add a
separate parallel Go port tutorial that explains how to install Go 1.22 or newer,
run Go tests, build `korix-go`, install it under `~/.local/share/korix-go`, link
it into `~/.local/bin`, and verify `korix-go --help`.

## CI

Update the existing CI workflow instead of adding separate workflow files. CI
should continue to run Python lint, format, tests, and package build. Add Go
setup, dependency consistency verification, `go test ./...`, and a Go build for
`./cmd/korix-go`.

## Release

Keep tag validation against `pyproject.toml`. Continue building and uploading
Python wheel/sdist artifacts. Add a Go release build matrix for Linux and macOS
binaries, uploading each `korix-go` binary as a release artifact before the
GitHub Release is created.

## Constraints

The Python implementation remains the default app during the migration. The Go
binary is published as `korix-go` until release parity and installer migration
are explicitly approved.
