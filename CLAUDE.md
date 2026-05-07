# pytest-devtools

## Overview

A pytest plugin (`pytest-devtools` on PyPI) providing four features: a Rich-powered debug fixture, ANSI-stripped capsys, visible whitespace in assertion diffs, and terminal column width management. Discovered automatically via the `pytest11` entry point.

## Commands

Run after every change:

```bash
uv run ruff check    # Lint (autofix enabled)
uv run ruff format   # Format
uv run ty check src/ # Type check
uv run pytest tests/ # Run tests
```

## Architecture

-   **Package name:** `pytest-devtools` (PyPI) / `devtools` (import name)
-   **Source layout:** `src/devtools/` with `uv_build` backend and `module-name = "devtools"`
-   **Entry point:** `[project.entry-points.pytest11] pytest-devtools = "devtools.plugin"`
-   **Python:** >=3.10 | **Dependencies:** pytest>=7, rich>=15.0.0

### Module Structure

| Module             | Purpose                                                                                                     |
| ------------------ | ----------------------------------------------------------------------------------------------------------- |
| `plugin.py`        | Central hook registration. Imports all feature modules and re-exports fixtures. All pytest hooks live here. |
| `debug_fixture.py` | `debug` fixture, `DebugPrinter` class, `phase_report_key` stash key, option registration                    |
| `capsys_strip.py`  | `capsys` fixture override, `StrippedCaptureFixture` wrapper, `keep_ansi` marker registration                |
| `columns.py`       | `_set_columns` autouse fixture, `COLUMNS` env var management                                                |
| `whitespace.py`    | `make_whitespace_visible()`, `pytest_assertrepr_compare` hook logic                                         |

### Key Design Patterns

-   **plugin.py is the single hook entry point.** Feature modules define `add_options()` functions and fixture/hook logic, but `plugin.py` calls them. Don't define pytest hooks directly in feature modules.
-   **Fixtures are re-exported from plugin.py** using the `from module import fixture as fixture # noqa: PLC0414` pattern to make them discoverable by pytest.
-   **`pytest_runtest_makereport`** uses `wrapper=True, tryfirst=True` to store phase reports in `item.stash` via `phase_report_key`. The `debug` fixture reads this during teardown to decide whether to flush output.
-   **Option resolution** follows precedence: per-call override > CLI flag > INI option > built-in default. See `_resolve_option()` in `debug_fixture.py`.

## Testing

-   All tests use the **pytester** fixture (subprocess-based pytest plugin testing). The `conftest.py` loads it via `pytest_plugins = ["pytester"]`.
-   Tests run pytester subprocesses which get their own plugin instance. Be aware that **environment variables from the parent process leak into pytester subprocesses** - use `monkeypatch` to control the environment when testing features that read env vars (see `test_columns_disabled`).
-   On **macOS**, `tmp_path` resolves to `/var/folders/.../T/`, not `/tmp/`. Don't assert on path strings containing "tmp" - use structural assertions instead.
-   **Pytest version floor is 7.0.** `pytest_runtest_makereport` uses pluggy's `wrapper=True` hookimpl, which needs pluggy >=1.4 — pytest 7+ resolves to a compatible pluggy transitively. CI's `reusable-tests.yml` matrix exercises pytest 7.x and 8.x in addition to the dev pin to catch regressions in this floor.

## Gotchas and Lessons Learned

-   **Generator return types for `ty`:** Fixtures using `yield` must annotate return type as `Generator[YieldType, None, None]`, not the yielded type directly. Hook wrappers using `yield` need `Generator[None, SendType, ReturnType]`. The `ty` type checker enforces this.
-   **`TYPE_CHECKING` imports:** Ruff rule TC003 requires `collections.abc.Generator` and similar stdlib imports to be inside `if TYPE_CHECKING:` blocks when `from __future__ import annotations` is present.
-   **Unused hook parameters:** The `call` parameter in `pytest_runtest_makereport` is required by the hook signature but unused - suppress with `# noqa: ARG001`.
-   **Boolean positional args:** `_resolve_option` accepts `bool | int | None` as a positional param - suppress ruff FBT001 with `# noqa: FBT001`.
-   **`contextlib.suppress` over try/except/pass:** Ruff SIM105 prefers `with contextlib.suppress(ExceptionType):` over empty except blocks.
-   **Pre-commit hooks:** All hook commands must use `uv run` prefix (e.g., `uv run pytest tests/`, `uv run ty check src/`) since tools are in the virtualenv. See `.pre-commit-config.yaml`.
