#!/usr/bin/env bash
set -euo pipefail

ci_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
sdk_root="$(cd "$ci_dir/.." && pwd)"
python_bin="${RAPID_TEST_PYTHON:-python}"
minor="$("$python_bin" -S -c 'import sys; print("%d%d" % sys.version_info[:2])')"
case "$minor" in
    27|36|37) ;;
    *) echo "Unsupported Python version: $minor" >&2; exit 1 ;;
esac
if [ -n "${RAPID_TEST_VERSION:-}" ]; then
    actual="$("$python_bin" -S -c 'import platform; print(platform.python_version())')"
    [ "$actual" = "$RAPID_TEST_VERSION" ] || {
        echo "Expected Python $RAPID_TEST_VERSION, got $actual" >&2
        exit 1
    }
fi
lock_file="$ci_dir/requirements-py$minor.lock"
owned_deps=""
cleanup() {
    if [ -n "$owned_deps" ]; then
        rm -rf -- "$owned_deps"
    fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# A caller may supply an existing read-only dependency directory for local checks.
deps_dir="${RAPID_TEST_DEPS_DIR:-}"
if [ -z "$deps_dir" ]; then
    temp_root="$(cd "${TMPDIR:-/tmp}" && pwd)"
    owned_deps="$(mktemp -d "$temp_root/rapid-ci-deps-py$minor.XXXXXX")"
    deps_dir="$owned_deps"
    "$python_bin" -m pip install --disable-pip-version-check --no-cache-dir \
        --no-compile --target "$deps_dir" -r "$lock_file"
fi
deps_dir="$(cd "$deps_dir" && pwd)"
cd "$sdk_root"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$sdk_root:$deps_dir" \
    "$python_bin" -S "$ci_dir/run_rapid_tests.py" "$deps_dir" "$lock_file"
