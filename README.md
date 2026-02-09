# pytest-devtools

Small pytest plugin that provides some niceties for writing and debugging tests.

## Features

-   **Debug fixture** -- Pretty-print variables, paths, and data structures with Rich. Output appears only when tests fail (or always with `--print-debug`).
-   **ANSI-stripped capsys** -- Automatically strip ANSI escape sequences from captured output so assertions don't break on color codes.
-   **Visible whitespace** -- Replace invisible whitespace characters (tabs, trailing spaces, carriage returns, newlines) with Unicode symbols in assertion failure diffs.
-   **Terminal column width** -- Optionally set the `COLUMNS` environment variable so Rich and other terminal-aware libraries don't introduce unwanted line wraps.

## Installation

```bash
# Using uv
uv add pytest-devtools

# Using pip
pip install pytest-devtools
```

**Requirements:** Python 3.11+ and pytest 7.0+

The plugin activates automatically once installed. No `conftest.py` changes are needed.

## Debug Fixture

The `debug` fixture gives you a callable that pretty-prints any Python object using Rich. Output is collected during the test and flushed to stderr only when the test fails.

### Basic Usage

```python
def test_user_creation(debug, tmp_path):
    user = {"name": "Alice", "roles": ["admin", "editor"]}
    debug(user)

    config_path = tmp_path / "config.toml"
    config_path.write_text("[settings]\nverbose = true")
    debug(config_path)

    assert user["name"] == "Alice"
```

On failure, stderr shows the Rich-formatted output between rule separators:

```
──────────────────────────── Debug ─────────────────────────────
{'name': 'Alice', 'roles': ['admin', 'editor']}
──────────────────────────── Debug ─────────────────────────────
```

### Multiple Values and Titles

Pass multiple arguments in a single call, and use `title` to label sections:

```python
def test_transform(debug):
    before = [1, 2, 3]
    after = [x * 2 for x in before]
    debug(before, after, title="Transform")
```

### Per-Call Options

Every option can be overridden on a per-call basis:

```python
def test_deep_structure(debug, tmp_path):
    nested = {"a": {"b": {"c": {"d": "deep"}}}}

    # Limit nesting depth
    debug(nested, max_depth=2)

    # Limit collection length
    debug(list(range(100)), max_length=5)

    # Show type annotations
    debug(nested, show_type=True)

    # Show directory tree for Path objects
    debug(tmp_path, list_dir_contents=True)

    # Disable tmp_path prefix stripping
    debug(tmp_path / "output.txt", strip_tmp_path=False)
```

### Path Handling

When you pass a `pathlib.Path` to `debug`:

-   **tmp_path stripping** (default: on) -- If the path is inside `tmp_path`, only the relative portion is shown. A path like `/var/folders/.../pytest-1234/test_foo0/subdir/file.txt` displays as `subdir/file.txt`.
-   **Directory listing** (default: off) -- When enabled and the path is a directory, a Rich tree shows the full directory contents recursively.

### CLI Options

| Flag                           | Description                                         |
| ------------------------------ | --------------------------------------------------- |
| `--print-debug`                | Always show debug output, even on passing tests     |
| `--debug-strip-tmp-path`       | Strip `tmp_path` prefix from Path objects (default) |
| `--no-debug-strip-tmp-path`    | Show full absolute paths                            |
| `--debug-list-dir-contents`    | Show directory tree for Path directories            |
| `--no-debug-list-dir-contents` | Don't list directory contents (default)             |
| `--debug-max-depth=N`          | Limit nesting depth in pretty-printed output        |
| `--debug-max-length=N`         | Limit collection length in pretty-printed output    |
| `--debug-show-type`            | Show type annotations above each value              |
| `--no-debug-show-type`         | Don't show type annotations (default)               |

### INI Options

Add these to `pyproject.toml` under `[tool.pytest.ini_options]`:

```toml
[tool.pytest.ini_options]
print_debug = true
debug_strip_tmp_path = true
debug_list_dir_contents = false
debug_max_depth = 4
debug_max_length = 20
debug_show_type = false
```

### Option Precedence

Per-call arguments take highest priority, then CLI flags, then INI settings:

```
per-call override  >  CLI flag  >  INI option  >  built-in default
```

## ANSI-Stripped capsys

By default, `capsys.readouterr()` returns output with ANSI escape sequences removed. This makes assertions simpler when testing code that uses colored output (Rich, Click, Colorama, etc.).

### Basic Usage

```python
def test_greeting(capsys):
    # Imagine this function uses Rich to print colored output
    print("\x1b[32mHello, world!\x1b[0m")

    captured = capsys.readouterr()
    assert captured.out == "Hello, world!\n"  # No ANSI codes to worry about
```

### Keeping ANSI Codes

For tests that need to verify color output, disable stripping per-test with a marker:

```python
import pytest

@pytest.mark.keep_ansi
def test_color_codes(capsys):
    print("\x1b[32mgreen\x1b[0m")
    captured = capsys.readouterr()
    assert "\x1b[32m" in captured.out
```

Or disable stripping globally with a CLI flag:

```bash
pytest --no-strip-ansi
```

### INI Option

```toml
[tool.pytest.ini_options]
strip_ansi = false
```

## Visible Whitespace in Assertions

When two strings differ only by whitespace, pytest's default diff is hard to read. This plugin replaces invisible characters with visible Unicode symbols in assertion failure output.

### Symbol Reference

| Character              | Symbol | Name             |
| ---------------------- | ------ | ---------------- |
| Trailing space         | `·`    | Middle dot       |
| Tab (`\t`)             | `→`    | Rightwards arrow |
| Carriage return (`\r`) | `←`    | Leftwards arrow  |
| Newline (`\n`)         | `↵`    | Return symbol    |

### Example Output

For a test like:

```python
def test_output():
    assert "hello " == "hello"
```

The failure message shows:

```
AssertionError: 'hello·' == 'hello'

Whitespace-visible comparison:
  Left:  'hello·'
  Right: 'hello'
```

### Disabling

Disable with the `--no-show-whitespace` CLI flag or in INI:

```toml
[tool.pytest.ini_options]
show_whitespace = false
```

> **Note:** Whitespace visibility only activates for `==` comparisons between strings, and only when the replacement actually changes the display. Non-string comparisons and strings without special whitespace are unaffected.

## Terminal Column Width

Many terminal-aware libraries (Rich, Click, etc.) detect the terminal width at runtime. In test environments, the detected width is often very small, causing unwanted line wraps in captured output. This plugin can set the `COLUMNS` environment variable for every test to prevent this.

This feature is **disabled by default**. Enable it with the `--columns` CLI flag or via INI options.

### CLI Option

Set `COLUMNS` for a single run:

```bash
pytest --columns=180
```

### INI Options

Enable permanently in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
set_columns = true   # Enable the feature
columns = 180        # Value to set (default when enabled)
```

The `--columns` CLI flag overrides the INI `columns` value when both are present.

## Configuration Summary

All features can be configured via CLI flags, `pyproject.toml` INI options, or (for the debug fixture) per-call arguments.

| Feature            | Enabled by default     | Enable/Disable with                                 |
| ------------------ | ---------------------- | --------------------------------------------------- |
| Debug fixture      | Output on failure only | N/A (always available)                              |
| ANSI stripping     | Yes                    | `--no-strip-ansi` or `strip_ansi = false`           |
| Visible whitespace | Yes                    | `--no-show-whitespace` or `show_whitespace = false` |
| Column width       | No                     | `--columns=N` or `set_columns = true`               |

## License

MIT
