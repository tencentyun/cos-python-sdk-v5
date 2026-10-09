# Rapid SDK regression tests

This directory contains the test runner and dependency lock files shared by
local checks and the upstream test suite. It does not configure a CI platform.

## Run the suite

From the repository root, in a Linux environment with Bash, the selected Python,
pip and C build tools:

```bash
RAPID_TEST_PYTHON=python bash .ci/run_rapid_tests.sh
```

The runner supports Python 2.7, 3.6 and 3.7. It runs one interpreter at a time;
unsupported versions fail explicitly. Installing dependencies requires access
to a package index, and the tests need permission to start loopback HTTP servers.

The script selects the matching lock file and installs dependencies into a
fresh temporary directory. It checks dependency versions and import locations,
loads the SDK from this checkout, runs with `-S` and disables bytecode. On exit,
it removes only the temporary dependency directory it created.

Optional environment variables:

- `RAPID_TEST_VERSION`: require an exact interpreter patch version.
- `RAPID_TEST_DEPS_DIR`: use an existing isolated dependency directory. Its
  contents are validated and treated as read-only; nothing is installed or deleted.

## Upstream test entry

`pytest ut/test.py` collects `test_rapid_regression`, which invokes this runner
in a subprocess using `sys.executable`. It runs only the current interpreter,
not a version matrix. A nonzero exit fails the pytest test, and subprocess
output is available in pytest's captured output. When coverage.py 5 or newer is active in the parent, the child explicitly
collects coverage with the same coverage package and branch mode. Its data is
merged into the active parent collector before pytest-cov writes its report.
The child still uses `-S` and the locked SDK dependencies; the parent site-packages
directory is not added to its import path. Temporary coverage data is removed
after merging. Without active coverage, the runner requires no coverage package.

The parent `ut/test.py` retains its existing COS environment requirements;
only the child suite is credential-free. The runner does not load `ut/test.py`,
so this entry does not recurse.

## Scope

The explicit suite contains `test_session_auth`, `test_gateway_lb`,
`test_gateway_lb_integration`, `test_encryption_rapid`, and `test_rapid_advanced`.
It includes ordinary-bucket isolation checks and uses local fixtures and
loopback HTTP servers. It requires no cloud credentials, real buckets or
running service stack.

Do not replace the explicit suite with broad `ut/` discovery, which includes
cloud-dependent tests. Failures, errors, skipped tests and an empty suite all
fail the runner. These tests do not replace real-service acceptance testing.

## Coverage bridge regression

With pytest, pytest-cov and coverage.py 5+ available to the parent interpreter:

```bash
RAPID_TEST_DEPS_DIR=/path/to/locked/dependencies \
  python -m pytest .ci/test_coverage_bridge.py --cov=./ --cov-report=xml
```

Add `--cov-branch` to verify branch-mode merging. This runs the actual upstream
entry and the full Rapid suite without constructing the cloud clients from
`ut/test.py`, then verifies that child-only modules reached the parent collector.
