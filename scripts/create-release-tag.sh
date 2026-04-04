#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/create-release-tag.sh [--push] [version]

Creates an annotated release tag in the form vX.Y.Z.

Rules:
  - If version is omitted, the script reads project.version from pyproject.toml.
  - If version is provided, it must match pyproject.toml.
  - The git worktree must be clean before tagging.
  - Use --push to push the tag to origin after creating it.
EOF
}

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

push_tag=0
version_arg=""

for arg in "$@"; do
  case "${arg}" in
    --push)
      push_tag=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [[ -n "${version_arg}" ]]; then
        echo "Only one version argument is allowed." >&2
        usage >&2
        exit 1
      fi
      version_arg="${arg}"
      ;;
  esac
done

if [[ -n "$(git status --short)" ]]; then
  echo "Git worktree is not clean. Commit or stash changes before tagging." >&2
  exit 1
fi

project_version="$(
  python3 - <<'PY'
import pathlib
import tomllib

pyproject = pathlib.Path("pyproject.toml")
project = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]
print(project["version"])
PY
)"

if [[ -n "${version_arg}" && "${version_arg}" != "${project_version}" ]]; then
  echo "Version ${version_arg} does not match pyproject.toml version ${project_version}." >&2
  exit 1
fi

version="${version_arg:-${project_version}}"

if [[ ! "${version}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Version must use semantic version format X.Y.Z." >&2
  exit 1
fi

tag="v${version}"

if git rev-parse "${tag}" >/dev/null 2>&1; then
  echo "Tag ${tag} already exists." >&2
  exit 1
fi

git tag -a "${tag}" -m "Korix ${version}"
echo "Created tag ${tag}"

if [[ "${push_tag}" -eq 1 ]]; then
  git push origin "${tag}"
  echo "Pushed tag ${tag} to origin"
else
  echo "Tag not pushed. Run: git push origin ${tag}"
fi
