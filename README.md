# pytest-devtools

[![Automated Tests](https://github.com/natelandau/pytest-devtools/actions/workflows/automated-tests.yml/badge.svg)](https://github.com/natelandau/pytest-devtools/actions/workflows/automated-tests.yml)
[![codecov](https://codecov.io/gh/natelandau/pytest-devtools/graph/badge.svg)](https://codecov.io/gh/natelandau/pytest-devtools)

A pytest plugin that smooths over a few common annoyances when writing and debugging tests.

## Features

- **Debug fixture**: pretty-prints variables, paths, and data structures with [Rich](https://rich.readthedocs.io/), and only shows the output when a test fails.
- **Stripped `capsys` output**: removes ANSI escape codes (and optionally the `tmp_path` prefix) from captured stdout/stderr so assertions stay readable.
- **Visible whitespace in diffs**: replaces tabs, trailing spaces, carriage returns, and newlines with Unicode symbols when an assertion fails.
- **Terminal column width control**: sets `COLUMNS` for every test so libraries that auto-wrap (Rich, Click, etc.) produce stable output.
- **CLI runner output post-processing**: `cli_runner` and `typer_runner` fixtures strip ANSI codes, `tmp_path` prefixes, and trailing whitespace from `click`/`typer` `CliRunner` results, the same way `capsys` does for regular captured output.

## Installation

```bash
# uv
uv add pytest-devtools

# pip
pip install pytest-devtools
```

**Requirements:** Python 3.10+ and pytest 7.0+.

The plugin registers itself through the `pytest11` entry point, so no `conftest.py` changes are needed.

## Debug Fixture

The `debug` fixture is a callable that pretty-prints any Python object using Rich. Output is buffered during the test and written to stderr only if the test fails (or always, with `--print-debug`).

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

When the test fails, stderr shows the buffered output between rule separators:

```
──────────────────────────── Debug ─────────────────────────────
{'name': 'Alice', 'roles': ['admin', 'editor']}
──────────────────────────── Debug ─────────────────────────────
```

### Multiple Values and Titles

Pass several arguments in a single call, and use `title` to label the section:

```python
def test_transform(debug):
    before = [1, 2, 3]
    after = [x * 2 for x in before]
    debug(before, after, title="Transform")
```

### Per-Call Options

Override any option on a single call:

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

When you pass a `pathlib.Path`:

- `tmp_path` stripping (default: on). If the path is inside `tmp_path`, only the relative portion is shown. A path like `/var/folders/.../pytest-1234/test_foo0/subdir/file.txt` displays as `subdir/file.txt`.
- Directory listing (default: off). When enabled and the path is a directory, a Rich tree shows the directory contents recursively.

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

Per-call arguments win, then CLI flags, then INI settings:

```
per-call override  >  CLI flag  >  INI option  >  built-in default
```

## Stripped `capsys` Output

The plugin overrides the built-in `capsys` fixture so that `readouterr()` returns post-processed strings. Two transformations are available:

- ANSI escape stripping (default: on)
- `tmp_path` prefix stripping (default: off, opt-in)

Both can be disabled or enabled independently, and they compose when both are active.

### ANSI Escape Stripping

Tests that exercise code printing colored output (Rich, Click, Colorama, etc.) usually don't care about the escape codes. By default, they're removed before you see the captured string:

```python
def test_greeting(capsys):
    print("\x1b[32mHello, world!\x1b[0m")

    captured = capsys.readouterr()
    assert captured.out == "Hello, world!\n"
```

To keep the codes for a single test, mark it with `@pytest.mark.keep_ansi`:

```python
import pytest

@pytest.mark.keep_ansi
def test_color_codes(capsys):
    print("\x1b[32mgreen\x1b[0m")
    captured = capsys.readouterr()
    assert "\x1b[32m" in captured.out
```

To turn stripping off globally:

```bash
pytest --no-strip-ansi
```

### `tmp_path` Stripping

Code that prints a `tmp_path`-rooted file produces output like `/var/folders/.../pytest-1234/test_foo0/file.txt`, which is awkward to assert on. Opt in to capsys `tmp_path` stripping to collapse those prefixes to their relative portion:

```python
def test_writes_log(capsys, tmp_path):
    log = tmp_path / "app.log"
    print(f"wrote {log}")

    captured = capsys.readouterr()
    assert captured.out == "wrote app.log\n"
```

Enable it for one run:

```bash
pytest --capsys-strip-tmp-path
```

Or globally in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
capsys_strip_tmp_path = true
```

`--no-capsys-strip-tmp-path` overrides the INI setting for a single run. Stripping applies to both `captured.out` and `captured.err`.

> [!NOTE]
> When both transformations are active, ANSI codes are stripped first, then `tmp_path` prefixes. The order matters only if your output mixes the two, but the combined result is what you'd expect.

### INI Options

```toml
[tool.pytest.ini_options]
strip_ansi = true                # default: true
capsys_strip_tmp_path = false    # default: false
```

## CLI Runner Output

`click.testing.CliRunner` and `typer.testing.CliRunner` replace `sys.stdout` and `sys.stderr` with their own in-memory buffers while a command runs. Nothing a CLI writes inside `invoke()` reaches pytest's capture machinery, so the `capsys` override above cannot see it and `result.output` arrives unprocessed.

The `cli_runner` and `typer_runner` fixtures are drop-in replacements that post-process the runner's own `Result`.

```bash
# uv
uv add --dev "pytest-devtools[click]"
uv add --dev "pytest-devtools[typer]"

# pip
pip install "pytest-devtools[click]"
pip install "pytest-devtools[typer]"
```

Neither extra is strictly required. A project testing a CLI already depends on click or typer directly, and the fixtures activate whenever the library is importable. The extras exist to record the supported versions:

| Fixture        | Requires      |
| -------------- | ------------- |
| `cli_runner`   | `click>=8.2`  |
| `typer_runner` | `typer>=0.25` |

Those floors are where the runner exposes stdout and stderr as separate strings. Below them, `result.stderr` raises `ValueError: stderr not separately captured` and `result.output` silently returns the two streams mixed together. Both fixtures check the installed version at setup and fail with an explicit message rather than letting that surface later.

### click

```python
from myapp.cli import main


def test_greeting(cli_runner):
    result = cli_runner.invoke(main, ["--name", "world"])

    assert result.exit_code == 0
    assert result.output == "Hello world\n"
```

### typer

```python
from myapp.cli import app


def test_greeting(typer_runner):
    result = typer_runner.invoke(app, ["--name", "world"])

    assert result.exit_code == 0
    assert result.output == "Hello world\n"
```

Both fixtures are real subclasses of their framework's runner, so `isolated_filesystem()` and every other runner method work as usual. Only `invoke()` changes.

When a transform is active, `invoke()` returns a transparent proxy over the framework's `Result`: `isinstance(result, click.testing.Result)` and a `-> Result` annotation both hold, but `type(result)` reports the proxy, not the framework's class.

### ANSI Escape Stripping

On by default, and controlled by the same settings as `capsys`: `--no-strip-ansi`, `strip_ansi = false`, and `@pytest.mark.keep_ansi` for a single test.

This matters most for CLIs that print through Rich. Click strips its own `echo()` styling inside the runner already, but a `Console(force_terminal=True)` writes escape codes straight past that.

### `tmp_path` Stripping

Off by default. Enable with `--cli-runner-strip-tmp-path` or `cli_runner_strip_tmp_path = true` to collapse paths under `tmp_path` to their relative portion:

```python
def test_writes_file(cli_runner, tmp_path):
    result = cli_runner.invoke(main, ["--out", str(tmp_path / "sub" / "report.txt")])

    assert "wrote sub/report.txt" in result.output
```

### Trailing Whitespace Stripping

Off by default. Enable with `--cli-runner-strip-trailing-whitespace` or `cli_runner_strip_trailing_whitespace = true`.

Typer renders help through a Rich panel, which pads every line out to the full terminal width. At a wide `--columns` setting that means lines of mostly blanks, which makes asserting on `--help` output impractical:

```python
def test_help(typer_runner):
    result = typer_runner.invoke(app, ["--help"])

    assert "Usage" in result.output
    assert not any(line.endswith(" ") for line in result.output.split("\n"))
```

### Terminal Width

Click's help formatter caps at 80 columns and ignores the `COLUMNS` environment variable, so the `--columns` setting alone never reached help text. When the column width feature is enabled, both fixtures pass it to `invoke()` as the `terminal_width` context setting. An explicit `terminal_width` argument always wins:

```python
def test_narrow_help(cli_runner):
    result = cli_runner.invoke(main, ["--help"], terminal_width=40)
```

### Runners You Construct Yourself

If runners come from your own conftest fixture and you would rather not switch to `cli_runner`, opt into patching instead. With `cli_runner_patch_result = true` or `--cli-runner-patch-result`, the same post-processing applies to every `Result` for the duration of each test, whoever built the runner:

```toml
[tool.pytest.ini_options]
cli_runner_patch_result = true
```

Three caveats:

- Terminal width injection does not reach externally built runners. Only the `cli_runner` and `typer_runner` fixtures' own `invoke()` passes `terminal_width` through; a runner you construct yourself keeps whatever width it would normally use.
- Enabling patch mode changes what `cli_runner.invoke()` and `typer_runner.invoke()` return too: once the `Result` classes are patched, the fixtures' own `invoke()` skips its wrapping and returns the framework's `Result` directly instead of the proxy.
- The patch is undone by `monkeypatch`, whose finalizer runs after every function-scoped fixture's teardown but before any session- or module-scoped one. A session- or module-scoped fixture that reads a `Result` during its own teardown therefore sees the raw, unprocessed output.

## Visible Whitespace in Assertions

When two strings differ only in whitespace, pytest's default diff is hard to read. This plugin replaces invisible characters with visible Unicode symbols in the assertion failure message.

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

Use the `--no-show-whitespace` CLI flag, or set the INI option:

```toml
[tool.pytest.ini_options]
show_whitespace = false
```

> [!NOTE]
> Whitespace visibility activates only for `==` comparisons between strings, and only when the replacement actually changes how the string displays. Non-string comparisons and strings without notable whitespace are unaffected.

## Terminal Column Width

Many terminal-aware libraries (Rich, Click, etc.) detect terminal width at runtime. In test environments, the detected width is often very small, which causes unwanted line wraps in captured output. This plugin can set the `COLUMNS` environment variable for every test to keep output stable.

The feature is **disabled by default**. Enable it with the `--columns` CLI flag or via INI options.

### CLI Option

Set `COLUMNS` for a single run:

```bash
pytest --columns=180
```

### INI Options

Enable it permanently in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
set_columns = true   # turn the feature on
columns = 180        # value to set when enabled
```

The `--columns` CLI flag overrides the INI `columns` value when both are present.

## Configuration Summary

Every feature is configurable through CLI flags and `pyproject.toml` INI options. The debug fixture additionally supports per-call arguments.

| Feature                | Default               | Toggle with                                                       |
| ---------------------- | --------------------- | ----------------------------------------------------------------- |
| Debug fixture          | Output on failure     | Always available; `--print-debug` to also show on success         |
| ANSI stripping         | On                    | `--no-strip-ansi` or `strip_ansi = false`                         |
| `tmp_path` in `capsys` | Off                   | `--capsys-strip-tmp-path` or `capsys_strip_tmp_path = true`       |
| Visible whitespace     | On                    | `--no-show-whitespace` or `show_whitespace = false`               |
| Column width           | Off                   | `--columns=N` or `set_columns = true`                             |
| CLI runner ANSI        | On                    | Shares `--no-strip-ansi` / `strip_ansi = false`                    |
| `tmp_path` in runner   | Off                   | `--cli-runner-strip-tmp-path` or `cli_runner_strip_tmp_path = true` |
| Runner trailing space  | Off                   | `--cli-runner-strip-trailing-whitespace` or `cli_runner_strip_trailing_whitespace = true` |
| Patch external runners | Off                   | `--cli-runner-patch-result` or `cli_runner_patch_result = true`     |

## AI Policy

All AI generated content is and always will be meticulously reviewed and approved by the author.

## License

MIT
