"""Tests for the click and typer CliRunner fixtures."""

CLICK_APP = '''
import click
from rich.console import Console


@click.command()
@click.option("--path", default="")
@click.option("--pad", is_flag=True)
@click.option("--code", default=0, type=int)
@click.option("--boom", is_flag=True)
@click.option(
    "--long-option-name",
    default="",
    help="A help string long enough that the formatter must wrap it somewhere, which makes the wrap width observable in the rendered help output.",
)
def app(path, pad, code, boom, long_option_name):
    """Emit styled output for testing."""
    Console(force_terminal=True).print("[red]red out[/red]")
    Console(force_terminal=True, stderr=True).print("[green]green err[/green]")
    if path:
        click.echo(f"wrote {path}")
        click.echo(f"logged {path}", err=True)
    if pad:
        click.echo("padded   ")
        click.echo("also padded\\t")
    if boom:
        raise RuntimeError("boom")
    if code:
        raise SystemExit(code)
'''

TYPER_APP = '''
import typer
from rich.console import Console

app = typer.Typer()


@app.command()
def main(
    path: str = "",
    pad: bool = False,
    code: int = 0,
    long_option_name: str = typer.Option(
        "",
        help="A help string long enough that the formatter must wrap it somewhere, which makes the wrap width observable in the rendered help output.",
    ),
):
    """Emit styled output for testing."""
    Console(force_terminal=True).print("[red]red out[/red]")
    Console(force_terminal=True, stderr=True).print("[green]green err[/green]")
    if path:
        typer.echo(f"wrote {path}")
        typer.echo(f"logged {path}", err=True)
    if pad:
        typer.echo("padded   ")
    if code:
        raise SystemExit(code)
'''


def test_cli_runner_strips_ansi_from_output(pytester):
    """Verify ANSI codes are stripped from Result.output by default."""
    # Given a click app emitting Rich-styled output through a forced terminal
    pytester.makepyfile(
        CLICK_APP
        + """
def test_output(cli_runner):
    result = cli_runner.invoke(app, [])
    assert "\\x1b[" not in result.output
    assert "red out" in result.output
"""
    )

    # When running the test with default settings
    result = pytester.runpytest()

    # Then the test passes
    result.assert_outcomes(passed=1)


def test_cli_runner_strips_ansi_from_stdout_and_stderr(pytester):
    """Verify ANSI codes are stripped from the separate stdout and stderr strings."""
    # Given a click app styling both streams
    pytester.makepyfile(
        CLICK_APP
        + """
def test_streams(cli_runner):
    result = cli_runner.invoke(app, [])
    assert "\\x1b[" not in result.stdout
    assert "\\x1b[" not in result.stderr
    assert "red out" in result.stdout
    assert "green err" in result.stderr
"""
    )

    # When running the test
    result = pytester.runpytest()

    # Then the test passes
    result.assert_outcomes(passed=1)


def test_cli_runner_strips_ansi_when_color_true(pytester):
    """Verify stripping still applies when invoke() is called with color=True."""
    # Given a click app invoked with click's color passthrough enabled
    pytester.makepyfile(
        CLICK_APP
        + """
def test_color(cli_runner):
    result = cli_runner.invoke(app, [], color=True)
    assert "\\x1b[" not in result.output
"""
    )

    # When running the test
    result = pytester.runpytest()

    # Then the test passes
    result.assert_outcomes(passed=1)


def test_cli_runner_keep_ansi_marker_preserves_codes(pytester):
    """Verify @pytest.mark.keep_ansi disables stripping for one test."""
    # Given two tests, one marked keep_ansi
    pytester.makepyfile(
        CLICK_APP
        + """
import pytest

@pytest.mark.keep_ansi
def test_raw(cli_runner):
    result = cli_runner.invoke(app, [])
    assert "\\x1b[" in result.output

def test_stripped(cli_runner):
    result = cli_runner.invoke(app, [])
    assert "\\x1b[" not in result.output
"""
    )

    # When running the tests
    result = pytester.runpytest()

    # Then both pass
    result.assert_outcomes(passed=2)


def test_cli_runner_no_strip_ansi_flag_preserves_codes(pytester):
    """Verify --no-strip-ansi disables stripping for runner output."""
    # Given a test expecting raw escape codes
    pytester.makepyfile(
        CLICK_APP
        + """
def test_raw(cli_runner):
    result = cli_runner.invoke(app, [])
    assert "\\x1b[" in result.output
"""
    )

    # When running with --no-strip-ansi
    result = pytester.runpytest("--no-strip-ansi")

    # Then the test passes
    result.assert_outcomes(passed=1)


def test_cli_runner_strip_ansi_ini_false_preserves_codes(pytester):
    """Verify the strip_ansi ini option disables stripping for runner output."""
    # Given ini config disabling stripping
    pytester.makeini("""
        [pytest]
        strip_ansi = false
    """)
    pytester.makepyfile(
        CLICK_APP
        + """
def test_raw(cli_runner):
    result = cli_runner.invoke(app, [])
    assert "\\x1b[" in result.output
"""
    )

    # When running the test
    result = pytester.runpytest()

    # Then the test passes
    result.assert_outcomes(passed=1)


def test_cli_runner_preserves_exit_code_and_exception(pytester):
    """Verify non-output Result attributes pass through the wrapper untouched."""
    # Given an app that can exit non-zero or raise
    pytester.makepyfile(
        CLICK_APP
        + """
def test_exit_code(cli_runner):
    result = cli_runner.invoke(app, ["--code", "3"])
    assert result.exit_code == 3

def test_exception(cli_runner):
    result = cli_runner.invoke(app, ["--boom"])
    assert result.exit_code == 1
    assert isinstance(result.exception, RuntimeError)
"""
    )

    # When running the tests
    result = pytester.runpytest()

    # Then both pass
    result.assert_outcomes(passed=2)


def test_cli_runner_strip_tmp_path_default_off(pytester):
    """Verify tmp_path is preserved in runner output by default."""
    # Given a test printing a tmp_path-rooted path with no opt-in
    pytester.makepyfile(
        CLICK_APP
        + """
def test_keeps(cli_runner, tmp_path):
    result = cli_runner.invoke(app, ["--path", str(tmp_path / "f.txt")])
    assert str(tmp_path) in result.output
"""
    )

    # When running with no tmp_path flags
    result = pytester.runpytest()

    # Then the test passes
    result.assert_outcomes(passed=1)


def test_cli_runner_strip_tmp_path_flag_strips_output(pytester):
    """Verify --cli-runner-strip-tmp-path strips the prefix from output."""
    # Given a test printing a path nested under tmp_path
    pytester.makepyfile(
        CLICK_APP
        + """
def test_strips(cli_runner, tmp_path):
    result = cli_runner.invoke(app, ["--path", str(tmp_path / "sub" / "f.txt")])
    assert "wrote sub/f.txt" in result.output
"""
    )

    # When running with the flag
    result = pytester.runpytest("--cli-runner-strip-tmp-path")

    # Then the test passes
    result.assert_outcomes(passed=1)


def test_cli_runner_strip_tmp_path_ini_strips_stderr(pytester):
    """Verify the cli_runner_strip_tmp_path ini option strips the stderr prefix."""
    # Given ini config enabling tmp_path stripping
    pytester.makeini("""
        [pytest]
        cli_runner_strip_tmp_path = true
    """)
    pytester.makepyfile(
        CLICK_APP
        + """
def test_strips_err(cli_runner, tmp_path):
    result = cli_runner.invoke(app, ["--path", str(tmp_path / "log.txt")])
    assert "logged log.txt" in result.stderr
"""
    )

    # When running the test
    result = pytester.runpytest()

    # Then the test passes
    result.assert_outcomes(passed=1)


def test_cli_runner_no_strip_tmp_path_flag_overrides_ini(pytester):
    """Verify --no-cli-runner-strip-tmp-path overrides an ini-enabled setting."""
    # Given ini config enabling tmp_path stripping but CLI disabling it
    pytester.makeini("""
        [pytest]
        cli_runner_strip_tmp_path = true
    """)
    pytester.makepyfile(
        CLICK_APP
        + """
def test_keeps(cli_runner, tmp_path):
    result = cli_runner.invoke(app, ["--path", str(tmp_path / "sub" / "f.txt")])
    assert str(tmp_path) in result.output
"""
    )

    # When running with the --no- flag
    result = pytester.runpytest("--no-cli-runner-strip-tmp-path")

    # Then the CLI flag overrides the ini and the test passes
    result.assert_outcomes(passed=1)


def test_cli_runner_strip_trailing_whitespace_default_off(pytester):
    """Verify trailing whitespace is preserved in runner output by default."""
    # Given an app emitting padded lines with no opt-in
    pytester.makepyfile(
        CLICK_APP
        + """
def test_keeps_padding(cli_runner):
    result = cli_runner.invoke(app, ["--pad"])
    assert "padded   \\n" in result.output
"""
    )

    # When running with no trailing-whitespace flags
    result = pytester.runpytest()

    # Then the test passes
    result.assert_outcomes(passed=1)


def test_cli_runner_strip_trailing_whitespace_flag_strips_padding(pytester):
    """Verify --cli-runner-strip-trailing-whitespace right-trims every line."""
    # Given an app emitting space- and tab-padded lines
    pytester.makepyfile(
        CLICK_APP
        + """
def test_strips_padding(cli_runner):
    result = cli_runner.invoke(app, ["--pad"])
    assert "padded\\n" in result.output
    assert "also padded\\n" in result.output
    assert not any(
        line.endswith((" ", "\\t")) for line in result.output.split("\\n")
    )
"""
    )

    # When running with the flag
    result = pytester.runpytest("--cli-runner-strip-trailing-whitespace")

    # Then the test passes
    result.assert_outcomes(passed=1)


def test_cli_runner_no_strip_trailing_whitespace_flag_overrides_ini(pytester):
    """Verify --no-cli-runner-strip-trailing-whitespace overrides an ini-enabled setting."""
    # Given ini config enabling trailing-whitespace stripping but CLI disabling it
    pytester.makeini("""
        [pytest]
        cli_runner_strip_trailing_whitespace = true
    """)
    pytester.makepyfile(
        CLICK_APP
        + """
def test_keeps_padding(cli_runner):
    result = cli_runner.invoke(app, ["--pad"])
    assert "padded   \\n" in result.output
"""
    )

    # When running with the --no- flag
    result = pytester.runpytest("--no-cli-runner-strip-trailing-whitespace")

    # Then the CLI flag overrides the ini and the test passes
    result.assert_outcomes(passed=1)


def test_cli_runner_exposes_isolated_filesystem(pytester):
    """Verify the fixture is a real CliRunner subclass with its methods intact."""
    # Given a test using a native CliRunner method
    pytester.makepyfile(
        CLICK_APP
        + """
from pathlib import Path

def test_isolated_fs(cli_runner):
    with cli_runner.isolated_filesystem() as td:
        assert Path(td).is_dir()
"""
    )

    # When running the test
    result = pytester.runpytest()

    # Then the test passes
    result.assert_outcomes(passed=1)


def test_cli_runner_terminal_width_follows_columns_option(pytester):
    """Verify --columns widens click's help output via terminal_width."""
    # Given a test measuring the widest help line
    pytester.makepyfile(
        CLICK_APP
        + """
def test_wide_help(cli_runner):
    result = cli_runner.invoke(app, ["--help"])
    assert max(len(line) for line in result.output.splitlines()) > 100
"""
    )

    # When running with --columns 180
    result = pytester.runpytest("--columns", "180")

    # Then the test passes
    result.assert_outcomes(passed=1)


def test_cli_runner_terminal_width_absent_when_columns_disabled(pytester):
    """Verify help output keeps click's 80-column default when columns is off."""
    # Given a test measuring the widest help line
    pytester.makepyfile(
        CLICK_APP
        + """
def test_default_help(cli_runner):
    result = cli_runner.invoke(app, ["--help"])
    assert max(len(line) for line in result.output.splitlines()) <= 80
"""
    )

    # When running with the columns feature disabled
    result = pytester.runpytest()

    # Then the test passes
    result.assert_outcomes(passed=1)


def test_cli_runner_explicit_terminal_width_overrides_columns(pytester):
    """Verify a caller-supplied terminal_width wins over the columns setting."""
    # Given a test passing terminal_width explicitly
    pytester.makepyfile(
        CLICK_APP
        + """
def test_explicit_width(cli_runner):
    result = cli_runner.invoke(app, ["--help"], terminal_width=40)
    assert max(len(line) for line in result.output.splitlines()) < 60
"""
    )

    # When running with a conflicting --columns value
    result = pytester.runpytest("--columns", "180")

    # Then the explicit width applies and the test passes
    result.assert_outcomes(passed=1)


def test_typer_runner_strips_ansi_from_output(pytester):
    """Verify ANSI codes are stripped from typer Result.output by default."""
    # Given a typer app emitting Rich-styled output through a forced terminal
    pytester.makepyfile(
        TYPER_APP
        + """
def test_output(typer_runner):
    result = typer_runner.invoke(app, [])
    assert "\\x1b[" not in result.output
    assert "red out" in result.output
"""
    )

    # When running the test
    result = pytester.runpytest()

    # Then the test passes
    result.assert_outcomes(passed=1)


def test_typer_runner_strips_ansi_when_color_true(pytester):
    """Verify stripping still applies when typer invoke() gets color=True."""
    # Given a typer app invoked with color passthrough enabled
    pytester.makepyfile(
        TYPER_APP
        + """
def test_color(typer_runner):
    result = typer_runner.invoke(app, [], color=True)
    assert "\\x1b[" not in result.output
"""
    )

    # When running the test
    result = pytester.runpytest()

    # Then the test passes
    result.assert_outcomes(passed=1)


def test_typer_runner_keep_ansi_marker_preserves_codes(pytester):
    """Verify @pytest.mark.keep_ansi disables typer stripping for one test."""
    # Given two tests, one marked keep_ansi
    pytester.makepyfile(
        TYPER_APP
        + """
import pytest

@pytest.mark.keep_ansi
def test_raw(typer_runner):
    result = typer_runner.invoke(app, [])
    assert "\\x1b[" in result.output

def test_stripped(typer_runner):
    result = typer_runner.invoke(app, [])
    assert "\\x1b[" not in result.output
"""
    )

    # When running the tests
    result = pytester.runpytest()

    # Then both pass
    result.assert_outcomes(passed=2)


def test_typer_runner_strip_tmp_path_flag_strips_output(pytester):
    """Verify --cli-runner-strip-tmp-path strips the prefix from typer output."""
    # Given a typer test printing a path nested under tmp_path
    pytester.makepyfile(
        TYPER_APP
        + """
def test_strips(typer_runner, tmp_path):
    result = typer_runner.invoke(app, ["--path", str(tmp_path / "sub" / "f.txt")])
    assert "wrote sub/f.txt" in result.output
"""
    )

    # When running with the flag
    result = pytester.runpytest("--cli-runner-strip-tmp-path")

    # Then the test passes
    result.assert_outcomes(passed=1)


def test_typer_runner_rich_help_is_padded_by_default(pytester):
    """Verify typer's Rich help really does pad lines, so the next test is not vacuous."""
    # Given a typer app whose help renders through a Rich panel
    pytester.makepyfile(
        TYPER_APP
        + """
def test_padded(typer_runner):
    result = typer_runner.invoke(app, ["--help"])
    assert any(line.endswith(" ") for line in result.output.split("\\n"))
"""
    )

    # When running without the trailing-whitespace flag
    result = pytester.runpytest()

    # Then padding is present and the test passes
    result.assert_outcomes(passed=1)


def test_typer_runner_strip_trailing_whitespace_strips_rich_help_padding(pytester):
    """Verify the flag removes Rich help padding while keeping the help content."""
    # Given a typer app whose help renders through a Rich panel
    pytester.makepyfile(
        TYPER_APP
        + """
def test_unpadded(typer_runner):
    result = typer_runner.invoke(app, ["--help"])
    assert "Usage" in result.output
    assert not any(line.endswith(" ") for line in result.output.split("\\n"))
"""
    )

    # When running with the trailing-whitespace flag
    result = pytester.runpytest("--cli-runner-strip-trailing-whitespace")

    # Then the test passes
    result.assert_outcomes(passed=1)


def test_typer_runner_preserves_exit_code(pytester):
    """Verify non-output typer Result attributes pass through the wrapper."""
    # Given a typer app exiting non-zero
    pytester.makepyfile(
        TYPER_APP
        + """
def test_exit_code(typer_runner):
    result = typer_runner.invoke(app, ["--code", "3"])
    assert result.exit_code == 3
"""
    )

    # When running the test
    result = pytester.runpytest()

    # Then the test passes
    result.assert_outcomes(passed=1)


def test_patch_result_strips_ansi_for_user_constructed_click_runner(pytester):
    """Verify the patch reaches a CliRunner the user built themselves."""
    # Given a test constructing click's own CliRunner directly
    pytester.makepyfile(
        CLICK_APP
        + """
from click.testing import CliRunner

def test_patched():
    result = CliRunner().invoke(app, [])
    assert "\\x1b[" not in result.output
    assert "red out" in result.output
"""
    )

    # When running with --cli-runner-patch-result
    result = pytester.runpytest("--cli-runner-patch-result")

    # Then the test passes
    result.assert_outcomes(passed=1)


def test_patch_result_strips_ansi_for_user_constructed_typer_runner(pytester):
    """Verify the patch reaches typer's Result, which is a separate class from 0.26."""
    # Given a test constructing typer's own CliRunner directly
    pytester.makepyfile(
        TYPER_APP
        + """
from typer.testing import CliRunner

def test_patched():
    result = CliRunner().invoke(app, [])
    assert "\\x1b[" not in result.output
    assert "red out" in result.output
"""
    )

    # When running with --cli-runner-patch-result
    result = pytester.runpytest("--cli-runner-patch-result")

    # Then the test passes
    result.assert_outcomes(passed=1)


def test_patch_result_default_off_leaves_result_untouched(pytester):
    """Verify a user-constructed runner is unaffected without the opt-in."""
    # Given a test constructing click's own CliRunner directly
    pytester.makepyfile(
        CLICK_APP
        + """
from click.testing import CliRunner

def test_unpatched():
    result = CliRunner().invoke(app, [])
    assert "\\x1b[" in result.output
"""
    )

    # When running with no patch flag
    result = pytester.runpytest()

    # Then escape codes survive and the test passes
    result.assert_outcomes(passed=1)


def test_cli_runner_invoke_skips_wrapping_when_patch_mode_active(pytester):
    """Verify the fixture's own invoke() returns the raw Result under patch mode.

    Discriminates on the returned object's type rather than its text: every
    transform is idempotent, so a test that only checks stripped output would
    pass whether or not the invoke()-level patch-mode guard actually runs.
    Once StrippedResult proxies __class__ for isinstance(), type() is what
    still tells a StrippedResult apart from the framework's own Result.
    """
    # Given a click app whose output would otherwise be wrapped for ANSI stripping
    pytester.makepyfile(
        CLICK_APP
        + """
from devtools.cli_runners import StrippedResult

def test_patched(cli_runner):
    result = cli_runner.invoke(app, [])
    assert type(result) is not StrippedResult
"""
    )

    # When running with --cli-runner-patch-result
    result = pytester.runpytest("--cli-runner-patch-result")

    # Then the test passes, proving invoke() skipped its own wrapping
    result.assert_outcomes(passed=1)


def test_patch_result_still_strips_fixture_runner_output(pytester):
    """Verify patch mode post-processes a Result from the plugin's own runner.

    Runs two inner sessions so the second re-imports click after pytester
    restores its ``sys.modules`` snapshot. A runner class cached across those
    sessions would build a Result from the evicted click copy while the patch
    lands on the fresh ``click.testing.Result``, leaving the output raw.
    """
    # Given one inner run that builds a click runner, then a second under patch mode
    pytester.makepyfile(
        CLICK_APP
        + """
def test_stripped(cli_runner):
    result = cli_runner.invoke(app, [])
    assert "\\x1b[" not in result.output
"""
    )
    pytester.runpytest().assert_outcomes(passed=1)

    # When running the second inner session with --cli-runner-patch-result
    result = pytester.runpytest("--cli-runner-patch-result")

    # Then the patch still reaches the fixture's Result and the test passes
    result.assert_outcomes(passed=1)


def test_patch_result_no_flag_overrides_ini(pytester):
    """Verify --no-cli-runner-patch-result overrides an ini-enabled setting."""
    # Given ini config enabling patching but CLI disabling it
    pytester.makeini("""
        [pytest]
        cli_runner_patch_result = true
    """)
    pytester.makepyfile(
        CLICK_APP
        + """
from click.testing import CliRunner

def test_unpatched():
    result = CliRunner().invoke(app, [])
    assert "\\x1b[" in result.output
"""
    )

    # When running with the --no- flag
    result = pytester.runpytest("--no-cli-runner-patch-result")

    # Then the CLI flag overrides the ini and escape codes survive
    result.assert_outcomes(passed=1)


def test_patch_result_respects_keep_ansi_marker(pytester):
    """Verify keep_ansi suppresses the patch for a single test."""
    # Given a captured reference to the original property, a patch-active test,
    # and a keep_ansi test that should have the patch suppressed
    pytester.makepyfile(
        CLICK_APP
        + """
from click.testing import CliRunner
import click.testing
import pytest

ORIGINAL = click.testing.Result.output

def test_patched():
    assert click.testing.Result.output is not ORIGINAL

@pytest.mark.keep_ansi
def test_raw():
    result = CliRunner().invoke(app, [])
    assert "\\x1b[" in result.output
    assert click.testing.Result.output is ORIGINAL
"""
    )

    # When running with --cli-runner-patch-result
    result = pytester.runpytest("--cli-runner-patch-result")

    # Then both pass, proving the patch is installed but suppressed for keep_ansi
    result.assert_outcomes(passed=2)


def test_patch_result_tmp_path_read_during_teardown_does_not_crash(pytester):
    """Verify a patched Result read from a fixture's teardown does not error.

    tmp_path's own finalizer may already be off pytest's active setup/teardown
    stack by the time a later fixture's teardown reads a patched Result
    attribute. Resolving tmp_path at that point must not raise.
    """
    # Given a fixture that reads result.output only after yielding
    pytester.makepyfile(
        CLICK_APP
        + """
from click.testing import CliRunner
import pytest

@pytest.fixture
def reader():
    holder = {}
    yield holder
    print("teardown saw:", holder["r"].output)

def test_teardown_read(reader):
    reader["r"] = CliRunner().invoke(app, [])
"""
    )

    # When running with both patch mode and tmp_path stripping enabled
    result = pytester.runpytest("--cli-runner-patch-result", "--cli-runner-strip-tmp-path")

    # Then the test passes with no teardown error
    result.assert_outcomes(passed=1)


def test_patch_result_teardown_strip_is_order_independent(pytester):
    """Verify a teardown read strips tmp_path regardless of argument order.

    ``tmp_path`` resolves from ``item.funcargs``, which is filled once during
    setup no matter which order the test declares its arguments in. A
    ``getfixturevalue()`` fallback would instead depend on tmp_path still
    being active on pytest's teardown stack, which only holds when tmp_path
    is declared before the other fixture.
    """
    # Given a reader fixture whose teardown reads a patched Result, requested
    # both before and after tmp_path in two otherwise identical tests
    pytester.makepyfile(
        CLICK_APP
        + """
from click.testing import CliRunner
import pytest

@pytest.fixture
def reader():
    holder = {}
    yield holder
    assert str(holder["tmp_path"]) not in holder["r"].output

def test_tmp_path_before_reader(tmp_path, reader):
    reader["tmp_path"] = tmp_path
    reader["r"] = CliRunner().invoke(app, ["--path", str(tmp_path / "sub" / "f.txt")])

def test_reader_before_tmp_path(reader, tmp_path):
    reader["tmp_path"] = tmp_path
    reader["r"] = CliRunner().invoke(app, ["--path", str(tmp_path / "sub" / "f.txt")])
"""
    )

    # When running with both patch mode and tmp_path stripping enabled
    result = pytester.runpytest("--cli-runner-patch-result", "--cli-runner-strip-tmp-path")

    # Then both pass, proving the strip does not depend on argument order
    result.assert_outcomes(passed=2)


def test_patch_result_teardown_matches_body_for_on_demand_tmp_path(pytester):
    """Verify one Result reads the same in the test body and in a teardown.

    ``getfixturevalue("tmp_path")`` never lands in ``item.funcargs``, so
    without stashing the materialized value the teardown read would find
    nothing to strip and hand back the raw path the body had stripped.
    """
    # Given a test that materializes tmp_path on demand and a fixture that
    # reads the same Result after the test body has already read it
    pytester.makepyfile(
        CLICK_APP
        + """
from click.testing import CliRunner
import pytest

@pytest.fixture
def reader():
    holder = {}
    yield holder
    assert holder["r"].output == holder["body"]

def test_on_demand(request, reader):
    tmp = request.getfixturevalue("tmp_path")
    r = CliRunner().invoke(app, ["--path", str(tmp / "sub" / "f.txt")])
    reader["r"] = r
    reader["body"] = r.output
    assert "wrote sub/f.txt" in r.output
"""
    )

    # When running with both patch mode and tmp_path stripping enabled
    result = pytester.runpytest("--cli-runner-patch-result", "--cli-runner-strip-tmp-path")

    # Then both reads agree and the test passes
    result.assert_outcomes(passed=1)


def test_patch_result_tmp_path_does_not_leak_across_tests(pytester):
    """Verify one test's tmp_path never strips another test's output.

    ``tmp_path`` resolves from ``item.funcargs``, which is a distinct dict per
    test item, so each test's own tmp_path is what gets read, never a
    previous test's.
    """
    # Given two tests, each invoking a runner against a path under its own tmp_path
    pytester.makepyfile(
        CLICK_APP
        + """
from click.testing import CliRunner

def test_first(tmp_path):
    result = CliRunner().invoke(app, ["--path", str(tmp_path / "f.txt")])
    assert "wrote f.txt" in result.output
    assert str(tmp_path) not in result.output

def test_second(tmp_path):
    result = CliRunner().invoke(app, ["--path", str(tmp_path / "f.txt")])
    assert "wrote f.txt" in result.output
    assert str(tmp_path) not in result.output
"""
    )

    # When running with both patch mode and tmp_path stripping enabled
    result = pytester.runpytest("--cli-runner-patch-result", "--cli-runner-strip-tmp-path")

    # Then both pass, proving each test only ever strips its own tmp_path
    result.assert_outcomes(passed=2)


def test_patch_result_creates_no_temp_dir_without_a_result_read(pytester):
    """Verify patch mode plus tmp_path stripping stays inert for a test that reads no Result."""
    # Given a test that enables both flags but never touches a runner Result
    pytester.makepyfile("""
def test_no_result():
    assert True
""")
    basetemp = pytester.path / "base"

    # When running with both flags and an explicit basetemp
    result = pytester.runpytest(
        "--cli-runner-patch-result",
        "--cli-runner-strip-tmp-path",
        f"--basetemp={basetemp}",
    )

    # Then the test passes and pytest never materializes the basetemp directory
    result.assert_outcomes(passed=1)
    assert not basetemp.exists()


def test_patch_result_strips_tmp_path_when_result_read_in_body(pytester):
    """Verify tmp_path stripping actually strips output read during the test body."""
    # Given a test reading a patched Result's output within the test itself
    pytester.makepyfile(
        CLICK_APP
        + """
from click.testing import CliRunner

def test_reads_in_body(tmp_path):
    result = CliRunner().invoke(app, ["--path", str(tmp_path / "sub" / "f.txt")])
    assert "wrote sub/f.txt" in result.output
    assert str(tmp_path) not in result.output
"""
    )

    # When running with both patch mode and tmp_path stripping enabled
    result = pytester.runpytest("--cli-runner-patch-result", "--cli-runner-strip-tmp-path")

    # Then the test passes, proving the tmp_path prefix was actually stripped
    result.assert_outcomes(passed=1)


def test_cli_runner_fails_clearly_when_click_missing(pytester):
    """Verify a missing click produces a setup error naming the extra to install.

    The generated conftest patches the module-level probe directly (rather than
    via ``monkeypatch``) to avoid any question of fixture ordering against
    ``cli_runner``, then restores it itself with a session-scoped autouse
    fixture. Without that restoration the patch would outlive this inner
    pytest run: pytester's inprocess mode only snapshots which modules are
    present in ``sys.modules``, not attribute mutations on a module already
    imported before the snapshot, and ``devtools.cli_runners`` is already
    imported by the outer session.
    """
    # Given a conftest that makes the click probe report absence, restoring it
    # after the inner run so the mutation cannot leak into later tests
    pytester.makeconftest("""
        from devtools import cli_runners
        import pytest

        _original = cli_runners._has_click
        cli_runners._has_click = lambda: False


        @pytest.fixture(scope="session", autouse=True)
        def _restore_probe():
            yield
            cli_runners._has_click = _original
    """)
    pytester.makepyfile("""
        def test_needs_click(cli_runner):
            pass
    """)

    # When running the test
    result = pytester.runpytest()

    # Then setup errors with an actionable message
    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(["*requires click*"])


def test_typer_runner_fails_clearly_when_typer_missing(pytester):
    """Verify a missing typer produces a setup error naming the extra to install.

    See the click counterpart above for why the generated conftest restores
    the patched probe itself.
    """
    # Given a conftest that makes the typer probe report absence, restoring it
    # after the inner run so the mutation cannot leak into later tests
    pytester.makeconftest("""
        from devtools import cli_runners
        import pytest

        _original = cli_runners._has_typer
        cli_runners._has_typer = lambda: False


        @pytest.fixture(scope="session", autouse=True)
        def _restore_probe():
            yield
            cli_runners._has_typer = _original
    """)
    pytester.makepyfile("""
        def test_needs_typer(typer_runner):
            pass
    """)

    # When running the test
    result = pytester.runpytest()

    # Then setup errors with an actionable message
    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(["*requires typer*"])


def test_cli_runner_fails_clearly_when_click_too_old(pytester):
    """Verify a click below the floor errors with the installed version named."""
    # Given a conftest reporting an outdated click install, restoring the
    # stubbed lookup after the inner run so it cannot leak into later tests
    pytester.makeconftest("""
        from devtools import cli_runners
        import pytest

        _original = cli_runners._installed_version
        cli_runners._installed_version = lambda dist: "8.1.8"


        @pytest.fixture(scope="session", autouse=True)
        def _restore_probe():
            yield
            cli_runners._installed_version = _original
    """)
    pytester.makepyfile("""
        def test_needs_newer_click(cli_runner):
            pass
    """)

    # When running the test
    result = pytester.runpytest()

    # Then setup errors, naming both the floor and what is installed
    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(["*require click>=8.2*"])
    result.stdout.fnmatch_lines(["*click 8.1.8 is installed*"])


def test_typer_runner_fails_clearly_when_typer_too_old(pytester):
    """Verify a typer below the floor errors with the installed version named."""
    # Given a conftest reporting an outdated typer install, restoring the
    # stubbed lookup after the inner run so it cannot leak into later tests
    pytester.makeconftest("""
        from devtools import cli_runners
        import pytest

        _original = cli_runners._installed_version
        cli_runners._installed_version = lambda dist: "0.15.4"


        @pytest.fixture(scope="session", autouse=True)
        def _restore_probe():
            yield
            cli_runners._installed_version = _original
    """)
    pytester.makepyfile("""
        def test_needs_newer_typer(typer_runner):
            pass
    """)

    # When running the test
    result = pytester.runpytest()

    # Then setup errors, naming both the floor and what is installed
    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(["*require typer>=0.25*"])
    result.stdout.fnmatch_lines(["*typer 0.15.4 is installed*"])


def test_whitespace_diff_applies_to_cli_runner_output(pytester):
    """Verify assertion diffs on runner output show visible whitespace symbols."""
    # Given a failing equality assertion against padded runner output
    pytester.makepyfile(
        CLICK_APP
        + """
def test_diff(cli_runner):
    result = cli_runner.invoke(app, ["--pad"])
    assert result.output == "nope"
"""
    )

    # When running the test
    result = pytester.runpytest()

    # Then the failure renders newline and trailing-space markers
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*Whitespace-visible comparison:*"])
    assert "↵" in result.stdout.str()
    assert "·" in result.stdout.str()
