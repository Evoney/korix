#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

KORIX_SOURCE_DIR="${KORIX_SOURCE_DIR:-${REPO_ROOT}}"
KORIX_INSTALL_ROOT="${KORIX_INSTALL_ROOT:-${HOME}/.local/share/korix}"
KORIX_BIN_DIR="${KORIX_BIN_DIR:-${HOME}/.local/bin}"
KORIX_PYTHON_BIN="${KORIX_PYTHON_BIN:-python3}"

usage() {
  cat <<'EOF'
Korix installer

Usage:
  bash install/install-korix.sh

Optional environment overrides:
  KORIX_SOURCE_DIR   Source directory to install from
  KORIX_INSTALL_ROOT Installation root for the dedicated virtualenv
  KORIX_BIN_DIR      Directory where the korix launcher symlink is created
  KORIX_PYTHON_BIN   Python executable to use (default: python3)

Example:
  KORIX_INSTALL_ROOT="$HOME/.local/share/korix" \
  KORIX_BIN_DIR="$HOME/.local/bin" \
  bash install/install-korix.sh
EOF
}

log() {
  printf '[korix-install] %s\n' "$1"
}

fail() {
  printf '[korix-install] ERROR: %s\n' "$1" >&2
  exit 1
}

check_platform() {
  local platform
  platform="$(uname -s)"
  case "${platform}" in
    Linux|Darwin)
      ;;
    *)
      fail "Unsupported OS: ${platform}. Korix installer currently supports Linux and macOS."
      ;;
  esac
}

check_dependencies() {
  command -v "${KORIX_PYTHON_BIN}" >/dev/null 2>&1 || fail "Python executable not found: ${KORIX_PYTHON_BIN}"
  command -v ln >/dev/null 2>&1 || fail "ln is required but not available."
  [[ -f "${KORIX_SOURCE_DIR}/pyproject.toml" ]] || fail "Korix source not found at ${KORIX_SOURCE_DIR}"
}

ensure_dirs() {
  mkdir -p "${KORIX_INSTALL_ROOT}" "${KORIX_BIN_DIR}"
}

create_venv() {
  local venv_dir="${KORIX_INSTALL_ROOT}/venv"
  if [[ ! -x "${venv_dir}/bin/python" ]]; then
    log "Creating virtual environment at ${venv_dir}"
    "${KORIX_PYTHON_BIN}" -m venv "${venv_dir}"
  else
    log "Reusing existing virtual environment at ${venv_dir}"
  fi
}

install_korix() {
  local venv_python="${KORIX_INSTALL_ROOT}/venv/bin/python"
  log "Upgrading pip in the Korix environment"
  "${venv_python}" -m pip install --upgrade pip >/dev/null
  log "Installing Korix from ${KORIX_SOURCE_DIR}"
  "${venv_python}" -m pip install --upgrade "${KORIX_SOURCE_DIR}"
}

link_launcher() {
  local target="${KORIX_INSTALL_ROOT}/venv/bin/korix"
  local link_path="${KORIX_BIN_DIR}/korix"
  [[ -x "${target}" ]] || fail "Korix launcher was not created at ${target}"
  ln -sf "${target}" "${link_path}"
  log "Linked ${link_path} -> ${target}"
}

verify_install() {
  local launcher="${KORIX_BIN_DIR}/korix"
  "${launcher}" --help >/dev/null
  log "Verified Korix launcher"
}

print_next_steps() {
  cat <<EOF

Korix installation complete.

Launcher:
  ${KORIX_BIN_DIR}/korix

Run:
  korix
EOF

  case ":${PATH}:" in
    *":${KORIX_BIN_DIR}:"*)
      ;;
    *)
      cat <<EOF

Your PATH does not currently include:
  ${KORIX_BIN_DIR}

Add this to your shell profile:
  export PATH="${KORIX_BIN_DIR}:\$PATH"
EOF
      ;;
  esac
}

main() {
  if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
  fi

  check_platform
  check_dependencies
  ensure_dirs
  create_venv
  install_korix
  link_launcher
  verify_install
  print_next_steps
}

main "$@"
