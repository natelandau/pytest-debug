"""CliRunner fixtures for click and typer with output post-processing.

``CliRunner.invoke()`` replaces ``sys.stdout`` and ``sys.stderr`` with its own
in-memory buffers, so output produced inside it never reaches pytest's capture
machinery and the ``capsys`` override cannot see it. These fixtures apply the
same post-processing to the runner's own ``Result`` instead.

Neither click nor typer is imported at module scope; both are optional extras.
"""

from __future__ import annotations

import contextlib
import importlib.util
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from devtools._options import resolve_option, should_strip_ansi
from devtools._text import strip_ansi, strip_tmp_path, strip_trailing_whitespace
from devtools.columns import get_columns_value
from devtools.debug_fixture import phase_report_key

MIN_CLICK_VERSION = "8.2"
MIN_TYPER_VERSION = "0.25"

# Remembers a tmp_path materialized on demand, which never lands in item.funcargs.
_tmp_path_key: pytest.StashKey[Path] = pytest.StashKey()


def _has_click() -> bool:
    """Report whether click is importable.

    Exists as a named seam so tests can simulate the library's absence without
    uninstalling it.
    """
    return importlib.util.find_spec("click") is not None


def _has_typer() -> bool:
    """Report whether typer is importable.

    Exists as a named seam so tests can simulate the library's absence without
    uninstalling it.
    """
    return importlib.util.find_spec("typer") is not None


def _installed_version(dist: str) -> str:
    """Return the installed version string for a distribution.

    Exists as a named seam so tests can simulate an outdated install without
    downgrading anything.

    Args:
        dist: The distribution name to look up.

    Returns:
        The installed version string.
    """
    from importlib.metadata import version  # noqa: PLC0415

    return version(dist)


def _check_min_version(dist: str, minimum: str) -> None:
    """Fail the test if an installed framework predates the supported floor.

    The optional extras cannot enforce this: the fixtures activate on a lazy
    import probe, so a project that already depends on click or typer gets them
    at whatever version it happens to pin. Below the floor click's Result mixes
    stderr into stdout and raises on ``.stderr``, which surfaces far from the
    real cause.

    Args:
        dist: The distribution name to check.
        minimum: The minimum supported version.
    """
    from packaging.version import Version  # noqa: PLC0415

    installed = _installed_version(dist)
    if Version(installed) < Version(minimum):
        pytest.fail(
            f"pytest-devtools CLI runner fixtures require {dist}>={minimum}, "
            f"but {dist} {installed} is installed.",
            pytrace=False,
        )


def add_options(parser: pytest.Parser) -> None:
    """Register CLI options for CLI runner output processing.

    Args:
        parser: The pytest option parser to add options to.
    """
    group = parser.getgroup("devtools-cli-runner", "CLI runner output processing")
    group.addoption(
        "--cli-runner-strip-tmp-path",
        action="store_true",
        default=None,
        dest="cli_runner_strip_tmp_path",
        help="Strip tmp_path prefix from CLI runner output (default: false)",
    )
    group.addoption(
        "--no-cli-runner-strip-tmp-path",
        action="store_false",
        dest="cli_runner_strip_tmp_path",
        help="Don't strip tmp_path prefix from CLI runner output",
    )
    group.addoption(
        "--cli-runner-strip-trailing-whitespace",
        action="store_true",
        default=None,
        dest="cli_runner_strip_trailing_whitespace",
        help="Right-trim every line of CLI runner output (default: false)",
    )
    group.addoption(
        "--no-cli-runner-strip-trailing-whitespace",
        action="store_false",
        dest="cli_runner_strip_trailing_whitespace",
        help="Don't right-trim lines of CLI runner output",
    )
    group.addoption(
        "--cli-runner-patch-result",
        action="store_true",
        default=None,
        dest="cli_runner_patch_result",
        help="Post-process Result output for runners the plugin did not create",
    )
    group.addoption(
        "--no-cli-runner-patch-result",
        action="store_false",
        dest="cli_runner_patch_result",
        help="Don't patch Result for externally created runners",
    )
    parser.addini(
        "cli_runner_strip_tmp_path",
        type="bool",
        default=False,
        help="Strip tmp_path prefix from CLI runner output (default: false)",
    )
    parser.addini(
        "cli_runner_strip_trailing_whitespace",
        type="bool",
        default=False,
        help="Right-trim every line of CLI runner output (default: false)",
    )
    parser.addini(
        "cli_runner_patch_result",
        type="bool",
        default=False,
        help="Post-process Result output for externally created runners (default: false)",
    )


@dataclass(frozen=True)
class _Transforms:
    """Resolved set of post-processing steps to apply to runner output."""

    ansi: bool
    tmp_path: Path | None
    trailing_whitespace: bool

    @property
    def active(self) -> bool:
        """Report whether any transform would change the output."""
        return self.ansi or self.tmp_path is not None or self.trailing_whitespace

    def apply(self, text: str) -> str:
        """Apply every enabled transform to a single output string.

        Strip ANSI first so tmp_path matching never has to contend with escape
        codes embedded in a path, and right-trim last so it also removes
        whitespace exposed by the earlier steps.

        Every transform is idempotent: applying it twice yields the same
        result as applying it once. That invariant is what lets patch mode
        and the fixtures' own wrapping coexist safely under any interleaving
        of runners and tests; a future non-idempotent transform would break
        that guarantee.

        Args:
            text: The raw output string from the runner Result.

        Returns:
            The post-processed string.
        """
        if self.ansi:
            text = strip_ansi(text)
        if self.tmp_path is not None:
            text = strip_tmp_path(text, self.tmp_path)
        if self.trailing_whitespace:
            text = strip_trailing_whitespace(text)
        return text


def _in_teardown(request: pytest.FixtureRequest) -> bool:
    """Report whether the current test item is in its teardown phase.

    ``request.getfixturevalue()`` for a fixture nothing requested during setup
    is only legal while the call phase is still running: pytest's internal
    setup/teardown stack drops the item before running its finalizers, so
    resolving a fixture for the first time from within another fixture's
    teardown code raises an assertion deep in pytest's runner. The call
    phase's report lands in ``item.stash`` only once that phase finishes, and
    a failed setup skips the call phase entirely and goes straight to
    teardown, so either signal reliably means teardown is underway.

    Args:
        request: The pytest fixture request object.

    Returns:
        True if the item is past setup and call, running teardown.
    """
    reports = request.node.stash.get(phase_report_key, {})
    if "call" in reports:
        return True
    setup = reports.get("setup")
    return setup is not None and not setup.passed


def _resolve_transforms(request: pytest.FixtureRequest) -> _Transforms:
    """Resolve which transforms apply to the current test.

    Prefers the already-resolved ``tmp_path`` value from ``item.funcargs``
    when the test's fixture closure requested it. That dict is filled once
    during setup and never cleared, so it holds the correct value through the
    whole test regardless of where ``tmp_path`` sits in the test's own
    argument order, and regardless of whether tmp_path's own finalizer has
    already run.

    Falls back to ``request.getfixturevalue()`` only during the call phase,
    for a test whose fixture closure never asked for ``tmp_path`` at all;
    that materializes it on demand so a Result read directly in the test body
    still gets stripped. ``getfixturevalue()`` does not record into
    ``funcargs``, so the value is stashed on the item: without that, the same
    Result would strip in the test body and come back unstripped from a
    teardown read, where the fallback is illegal and cannot run again.

    Args:
        request: The pytest fixture request object.

    Returns:
        The resolved transform set.
    """
    tmp_path: Path | None = None
    if resolve_option(request, "cli_runner_strip_tmp_path"):
        funcargs = request.node.funcargs
        stash = request.node.stash
        if "tmp_path" in funcargs:
            tmp_path = funcargs["tmp_path"]
        elif (stashed := stash.get(_tmp_path_key, None)) is not None:
            tmp_path = stashed
        elif not _in_teardown(request):
            with contextlib.suppress(pytest.FixtureLookupError):
                tmp_path = request.getfixturevalue("tmp_path")
                stash[_tmp_path_key] = tmp_path

    return _Transforms(
        ansi=should_strip_ansi(request),
        tmp_path=tmp_path,
        trailing_whitespace=bool(resolve_option(request, "cli_runner_strip_trailing_whitespace")),
    )


def _transforms_configured(request: pytest.FixtureRequest) -> bool:
    """Report whether any transform is enabled, without resolving tmp_path.

    Reads the tmp_path option flag directly rather than resolving the
    tmp_path fixture, so this check is safe to call from an autouse fixture
    before deciding whether to install the patch at all.

    Args:
        request: The pytest fixture request object.

    Returns:
        True if any transform would apply to this test.
    """
    return (
        should_strip_ansi(request)
        or bool(resolve_option(request, "cli_runner_strip_tmp_path"))
        or bool(resolve_option(request, "cli_runner_strip_trailing_whitespace"))
    )


def _patch_active(request: pytest.FixtureRequest) -> bool:
    """Report whether global Result patching is enabled for this test.

    Args:
        request: The pytest fixture request object.

    Returns:
        True if the Result classes should be patched.
    """
    return bool(resolve_option(request, "cli_runner_patch_result"))


class StrippedResult:
    """Wrapper around a runner Result that post-processes its output strings.

    ``Result.output``, ``.stdout`` and ``.stderr`` are read-only properties and
    cannot be reassigned per instance, so wrap the Result and forward everything
    else through ``__getattr__``.
    """

    def __init__(self, original: Any, transforms: _Transforms) -> None:
        self._original = original
        self._transforms = transforms

    @property
    def __class__(self) -> type:
        """Report the wrapped Result's class so isinstance() checks pass.

        CPython's isinstance() consults __class__ before falling back to the
        real type, so a user's isinstance(result, click.testing.Result) or
        -> Result annotation holds regardless of which transforms are active.
        type(result) still reports StrippedResult, since type() reads the
        real object header rather than this property.
        """
        return type(self._original)

    @property
    def output(self) -> str:
        """Return the interleaved stdout and stderr, post-processed."""
        return self._transforms.apply(self._original.output)

    @property
    def stdout(self) -> str:
        """Return the standard output, post-processed."""
        return self._transforms.apply(self._original.stdout)

    @property
    def stderr(self) -> str:
        """Return the standard error, post-processed."""
        return self._transforms.apply(self._original.stderr)

    def __repr__(self) -> str:
        """Delegate to the wrapped Result's repr."""
        return repr(self._original)

    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to the wrapped Result."""
        return getattr(self._original, name)


class _ResultPostProcessMixin:
    """Supply an ``invoke()`` that post-processes the returned Result.

    Mixed in ahead of the framework's own ``CliRunner`` so ``super().invoke()``
    resolves to the real implementation.
    """

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        """Invoke the CLI and post-process the resulting output.

        Args:
            *args: Positional arguments forwarded to the framework's invoke().
            **kwargs: Keyword arguments forwarded to the framework's invoke().

        Returns:
            A StrippedResult when any transform is enabled, else the original
            Result.
        """
        request: pytest.FixtureRequest | None = getattr(self, "_devtools_request", None)

        if request is None:
            return super().invoke(*args, **kwargs)  # ty: ignore[unresolved-attribute]

        # click's help formatter caps at 80 columns and ignores COLUMNS, so the
        # width has to travel in as a Context setting.
        width = get_columns_value(request.config)
        if width is not None:
            kwargs.setdefault("terminal_width", width)

        result = super().invoke(*args, **kwargs)  # ty: ignore[unresolved-attribute]

        if _patch_active(request):
            return result

        transforms = _resolve_transforms(request)
        return StrippedResult(result, transforms) if transforms.active else result


def _click_runner_class() -> type:
    """Build the click runner subclass, importing click lazily.

    Built fresh on every call rather than cached. A cached class pins the
    ``CliRunner`` from whichever click copy was importable first, and under
    ``pytester`` a later run re-imports click fresh. The runner would then
    build a ``Result`` from the stale copy while patch mode patches the fresh
    ``click.testing.Result``, silently dropping all post-processing.

    Returns:
        The ``DevtoolsClickRunner`` class.
    """
    from click.testing import CliRunner  # noqa: PLC0415

    return type("DevtoolsClickRunner", (_ResultPostProcessMixin, CliRunner), {})


@pytest.fixture
def cli_runner(request: pytest.FixtureRequest) -> Any:
    """Provide a click CliRunner whose Result output is post-processed.

    Use in place of ``click.testing.CliRunner()`` so that ANSI escape sequences
    and other configured noise are removed from ``result.output``,
    ``result.stdout`` and ``result.stderr``.

    Args:
        request: The pytest fixture request object.

    Returns:
        A CliRunner subclass instance.
    """
    if not _has_click():
        pytest.fail(
            "The cli_runner fixture requires click. Install pytest-devtools[click].",
            pytrace=False,
        )
    _check_min_version("click", MIN_CLICK_VERSION)

    runner = _click_runner_class()()
    runner._devtools_request = request  # noqa: SLF001
    return runner


def _typer_runner_class() -> type:
    """Build the typer runner subclass, importing typer lazily.

    Subclassing typer's own runner covers both typer eras: before 0.26 it is a
    click CliRunner subclass, from 0.26 an independent implementation over
    typer's vendored click.

    Built fresh on every call rather than cached, for the same reason as the
    click runner, plus one specific to typer: ``invoke()`` re-derives the click
    command via ``get_command()``, which resolves unset ``Typer()`` defaults
    with ``isinstance(value, DefaultPlaceholder)`` checks. Run against a
    freshly imported typer, those checks fail across the two module copies and
    let an unresolved placeholder leak through as real data.
    """
    from typer.testing import CliRunner  # noqa: PLC0415

    return type("DevtoolsTyperRunner", (_ResultPostProcessMixin, CliRunner), {})


@pytest.fixture
def typer_runner(request: pytest.FixtureRequest) -> Any:
    """Provide a typer CliRunner whose Result output is post-processed.

    Use in place of ``typer.testing.CliRunner()`` so that ANSI escape sequences
    and other configured noise are removed from ``result.output``,
    ``result.stdout`` and ``result.stderr``.

    Args:
        request: The pytest fixture request object.

    Returns:
        A typer CliRunner subclass instance.
    """
    if not _has_typer():
        pytest.fail(
            "The typer_runner fixture requires typer. Install pytest-devtools[typer].",
            pytrace=False,
        )
    _check_min_version("typer", MIN_TYPER_VERSION)

    runner = _typer_runner_class()()
    runner._devtools_request = request  # noqa: SLF001
    return runner


def _result_classes() -> list[type]:
    """Collect the installed frameworks' Result classes.

    Before typer 0.26 ``typer.testing.Result`` is ``click.testing.Result``, so
    de-duplicate by identity to avoid patching the same class twice.

    Returns:
        The distinct Result classes to patch.
    """
    classes: list[type] = []

    if _has_click():
        from click.testing import Result  # noqa: PLC0415

        classes.append(Result)

    if _has_typer():
        from typer.testing import Result as TyperResult  # noqa: PLC0415

        if TyperResult not in classes:
            classes.append(TyperResult)

    return classes


@pytest.fixture(autouse=True)
def _patch_cli_result(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Post-process Result output for runners this plugin did not create.

    Opt in with ``cli_runner_patch_result`` when runners are constructed
    elsewhere, for instance in a project's own conftest fixture. monkeypatch
    teardown restores the original properties after each test.

    The replacement properties resolve transforms on every read rather than
    once here, so ``tmp_path`` materializes only if a test actually reads a
    patched ``Result`` attribute, not for every test that merely has patching
    and tmp_path stripping enabled.

    Args:
        request: The pytest fixture request object.
        monkeypatch: The pytest monkeypatch fixture.
    """
    if not _patch_active(request):
        return

    if not _transforms_configured(request):
        return

    for result_cls in _result_classes():
        for name in ("output", "stdout", "stderr"):
            original = getattr(result_cls, name)
            monkeypatch.setattr(
                result_cls,
                name,
                property(
                    lambda self, _fget=original.fget: _resolve_transforms(request).apply(
                        _fget(self)
                    )
                ),
            )
