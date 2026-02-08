# pytest-devtools Plugin Design

## Overview

A custom pytest plugin that provides debugging utilities and output improvements for pytest test suites. The plugin is distributed as an installable package (`pytest-devtools`) discovered automatically via the `pytest11` entry point.

**Dependencies:** `rich`, `pytest >= 7.0`

## Package Structure

```
pytest-devtools/
├── pyproject.toml
├── src/
│   └── pytest_devtools/
│       ├── __init__.py
│       ├── plugin.py              # Hook registration, CLI options, marker registration
│       ├── debug_fixture.py       # debug() callable fixture
│       ├── capsys_strip.py        # ANSI stripping for capsys
│       ├── whitespace.py          # Visible whitespace in assertion diffs
│       └── columns.py             # COLUMNS env var setting
└── tests/
    ├── conftest.py
    ├── test_debug_fixture.py
    ├── test_capsys_strip.py
    ├── test_whitespace.py
    └── test_columns.py
```

Entry point in `pyproject.toml`:

```toml
[project.entry-points.pytest11]
pytest-devtools = "pytest_devtools.plugin"
```

## Feature 1: Debug Fixture

### Purpose

Provide a callable `debug` fixture that pretty-prints variables using Rich, with output shown only on test failure by default.

### Usage

```python
def test_something(debug, tmp_path):
    data = {"users": ["alice", "bob"], "count": 2}
    debug(data)
    debug(data, title="User Data")

    data_dir = tmp_path / "output"
    data_dir.mkdir()
    (data_dir / "result.json").write_text("{}")
    debug(data_dir, title="Output Dir", list_dir_contents=True)

    assert data["count"] == 3  # fails -> debug output shown
```

### Callable Signature

```python
def debug(
    *args: Any,
    title: str | None = None,
    strip_tmp_path: bool | None = None,
    list_dir_contents: bool | None = None,
    max_depth: int | None = None,
    max_length: int | None = None,
    show_type: bool | None = None,
) -> None
```

-   `*args` — One or more objects to pretty-print. Each formatted with `rich.pretty.pretty_repr()`.
-   `title` — Optional string used in `Console.rule(title)`. Defaults to `"Debug"` if not provided.
-   `strip_tmp_path` — When `True`, strip the pytest `tmp_path` prefix from Path objects, showing only the relative portion. Per-call `None` defers to global default.
-   `list_dir_contents` — When `True`, if an argument is a Path pointing to an existing directory, display a tree of its contents using `rich.tree.Tree`. Per-call `None` defers to global default.
-   `max_depth` — Limit nesting depth for nested structures. Maps to `rich.pretty.pretty_repr(max_depth=...)`. Per-call `None` defers to global default.
-   `max_length` — Truncate long collections after N items. Maps to `rich.pretty.pretty_repr(max_length=...)`. Per-call `None` defers to global default.
-   `show_type` — Print the type annotation above each value. Per-call `None` defers to global default.

### Configuration

All options configurable via CLI flags, `pyproject.toml` ini options, and per-call keyword arguments. Per-call values take precedence over global defaults.

| CLI Flag | ini Option | Default | Effect |
| --- | --- | --- | --- |
| `--print-debug` | `print_debug = true` | `false` | Always show debug output (not just on failure) |
| `--debug-strip-tmp-path` / `--no-debug-strip-tmp-path` | `debug_strip_tmp_path = true/false` | `true` | Strip tmp_path prefix from paths |
| `--debug-list-dir-contents` / `--no-debug-list-dir-contents` | `debug_list_dir_contents = true/false` | `false` | Tree-list directories |
| `--debug-max-depth=N` | `debug_max_depth = N` | None (unlimited) | Limit nesting depth |
| `--debug-max-length=N` | `debug_max_length = N` | None (unlimited) | Truncate long collections |
| `--debug-show-type` / `--no-debug-show-type` | `debug_show_type = true/false` | `false` | Show type of each value |

### Internal Behavior

1. The fixture yields a callable `DebugPrinter` instance.
2. Each `debug(...)` call renders the Rich-formatted output to an internal `StringIO` buffer and stores it in a list.
3. On fixture teardown (after `yield`):
    - If `--print-debug` was passed: always print all collected output.
    - Otherwise: check if the current test failed (via `request.node.rep_call` populated by a `pytest_runtest_makereport` hook). If failed, print. If passed, discard.
4. Output is written directly to `sys.stderr` (bypassing pytest capture) and wrapped in `Console.rule()` separators.

### Output Format

With no title:

```
────────────────────────────────
{'users': ['alice', 'bob'], 'count': 2}
────────────────────────────────
```

With a title:

```
──────────────── User Data ────────────────
{'users': ['alice', 'bob'], 'count': 2}
──────────────── /User Data ────────────────
```

With `list_dir_contents=True` on a directory Path:

```
──────────────── Output Dir ────────────────
output/
├── result.json
──────────────── /Output Dir ────────────────
```

## Feature 2: ANSI Stripping from capsys

### Purpose

Automatically strip ANSI escape sequences from stdout and stderr captured by pytest's `capsys` fixture, so assertions against captured output don't need to account for color codes.

### Implementation

Override pytest's built-in `capsys` fixture by defining a fixture with the same name. The replacement:

1. Wraps the original `readouterr()` method.
2. Strips ANSI sequences from both `.out` and `.err` using a compiled regex: `re.compile(r'\x1b\[[0-9;]*m')`.
3. Returns a `CaptureResult` namedtuple with cleaned strings.

```python
original_result = original_readouterr()
return CaptureResult(
    out=strip_ansi(original_result.out),
    err=strip_ansi(original_result.err),
)
```

### Configuration

| Mechanism                                       | Effect                                |
| ----------------------------------------------- | ------------------------------------- |
| Default (no flags)                              | ANSI stripping is **on**              |
| `--no-strip-ansi` / `strip_ansi = false` in ini | Disables stripping globally           |
| `@pytest.mark.keep_ansi` marker on a test       | Disables stripping for that test only |

When stripping is disabled (globally or per-test), the original unmodified `capsys` is returned.

## Feature 3: Whitespace Visibility in Assertion Failures

### Purpose

Make invisible whitespace characters visible in assertion failure diffs so that whitespace-only differences are immediately obvious.

### Symbol Mapping

| Character              | Symbol              | When Replaced                         |
| ---------------------- | ------------------- | ------------------------------------- |
| Space (` `)            | `·` (middle dot)    | Trailing spaces only (to avoid noise) |
| Tab (`\t`)             | `→` (arrow)         | Always                                |
| Newline (`\n`)         | `↵` (return symbol) | Shown at line ends                    |
| Carriage return (`\r`) | `←` (left arrow)    | Always                                |

### Implementation

Use the `pytest_assertrepr_compare` hook. When `op == "=="` and both operands are strings, generate custom comparison lines with whitespace made visible, returning them directly from the hook.

Spaces are only replaced when trailing (end of a line) or when the strings differ only in whitespace, to keep output readable.

### Configuration

| Mechanism                                                 | Effect                          |
| --------------------------------------------------------- | ------------------------------- |
| Default (no flags)                                        | Whitespace visibility is **on** |
| `--no-show-whitespace` / `show_whitespace = false` in ini | Disables it globally            |

## Feature 4: Terminal Column Width

### Purpose

Set the `COLUMNS` environment variable for test runs so that code under test (including Rich-based applications) uses a wider terminal width and doesn't introduce unwanted line wraps in captured output.

### Implementation

Use a session-scoped autouse fixture that calls `monkeypatch.setenv("COLUMNS", str(N))` where N defaults to 180.

### Configuration

| CLI Flag           | ini Option            | Default               | Effect                  |
| ------------------ | --------------------- | --------------------- | ----------------------- |
| `--no-set-columns` | `set_columns = false` | `true` (sets COLUMNS) | Disable setting COLUMNS |
| `--columns=N`      | `columns = N`         | `180`                 | Custom column width     |

## CLI Flags Summary

| Flag | Default Behavior | Flag Effect |
| --- | --- | --- |
| `--print-debug` | Debug output on failure only | Always show debug output |
| `--debug-strip-tmp-path` / `--no-debug-strip-tmp-path` | Strip tmp_path (on) | Toggle tmp_path stripping |
| `--debug-list-dir-contents` / `--no-debug-list-dir-contents` | Don't list dirs (off) | Toggle directory listing |
| `--debug-max-depth=N` | Unlimited | Limit nesting depth |
| `--debug-max-length=N` | Unlimited | Truncate collections |
| `--debug-show-type` / `--no-debug-show-type` | Don't show types (off) | Toggle type display |
| `--no-strip-ansi` | ANSI stripping on | Disable ANSI stripping |
| `--no-show-whitespace` | Whitespace visibility on | Disable whitespace visibility |
| `--no-set-columns` | COLUMNS=180 set | Don't set COLUMNS |
| `--columns=N` | 180 | Custom column width |
