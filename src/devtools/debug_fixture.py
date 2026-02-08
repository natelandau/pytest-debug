"""Debug fixture for pretty-printing variables using Rich.

Provide a callable fixture that collects Rich-formatted debug output during
a test and displays it on failure (or always with --print-debug).
"""

from __future__ import annotations

import contextlib
import sys
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Generator

import pytest
from rich.console import Console
from rich.pretty import pretty_repr
from rich.tree import Tree

phase_report_key = pytest.StashKey[dict[str, pytest.CollectReport]]()


def add_options(parser: pytest.Parser) -> None:
    """Register CLI options for the debug fixture.

    Args:
        parser: The pytest option parser to add options to.
    """
    group = parser.getgroup("devtools-debug", "Debug fixture options")
    group.addoption(
        "--print-debug",
        action="store_true",
        default=False,
        help="Always show debug output, not just on test failure",
    )
    group.addoption(
        "--debug-strip-tmp-path",
        action="store_true",
        default=None,
        dest="debug_strip_tmp_path",
        help="Strip tmp_path prefix from Path objects (default: true)",
    )
    group.addoption(
        "--no-debug-strip-tmp-path",
        action="store_false",
        dest="debug_strip_tmp_path",
        help="Don't strip tmp_path prefix from Path objects",
    )
    group.addoption(
        "--debug-list-dir-contents",
        action="store_true",
        default=None,
        dest="debug_list_dir_contents",
        help="List directory contents for Path directories (default: false)",
    )
    group.addoption(
        "--no-debug-list-dir-contents",
        action="store_false",
        dest="debug_list_dir_contents",
        help="Don't list directory contents",
    )
    group.addoption(
        "--debug-max-depth",
        action="store",
        type=int,
        default=None,
        help="Max nesting depth for debug pretty-printing",
    )
    group.addoption(
        "--debug-max-length",
        action="store",
        type=int,
        default=None,
        help="Max collection length for debug pretty-printing",
    )
    group.addoption(
        "--debug-show-type",
        action="store_true",
        default=None,
        dest="debug_show_type",
        help="Show type annotations in debug output",
    )
    group.addoption(
        "--no-debug-show-type",
        action="store_false",
        dest="debug_show_type",
        help="Don't show type annotations in debug output",
    )
    parser.addini("print_debug", type="bool", default=False, help="Always show debug output")
    parser.addini("debug_strip_tmp_path", type="bool", default=True, help="Strip tmp_path prefix")
    parser.addini("debug_list_dir_contents", type="bool", default=False, help="List dir contents")
    parser.addini("debug_max_depth", default="", help="Max nesting depth")
    parser.addini("debug_max_length", default="", help="Max collection length")
    parser.addini("debug_show_type", type="bool", default=False, help="Show type annotations")


def _resolve_option(
    request: pytest.FixtureRequest,
    name: str,
    per_call: bool | int | None,  # noqa: FBT001
) -> Any:
    """Resolve a config option with per-call override.

    Per-call value takes precedence, then CLI flag, then ini option.

    Args:
        request: The pytest fixture request.
        name: The option name (matching both getoption dest and ini key).
        per_call: The per-call override value, or None to use global default.

    Returns:
        The resolved option value.
    """
    if per_call is not None:
        return per_call

    cli_value = request.config.getoption(name, default=None)
    if cli_value is not None:
        return cli_value

    return request.config.getini(name)


def _build_dir_tree(path: Path, base_name: str) -> Tree:
    """Build a Rich Tree showing directory contents.

    Args:
        path: The directory path to list.
        base_name: The display name for the root of the tree.

    Returns:
        A Rich Tree object representing the directory structure.
    """
    tree = Tree(f"{base_name}/")
    for child in sorted(path.iterdir()):
        if child.is_dir():
            subtree = _build_dir_tree(child, child.name)
            tree.add(subtree)
        else:
            tree.add(child.name)
    return tree


class DebugPrinter:
    """Callable debug printer that collects Rich-formatted output.

    Collect formatted output during a test and flush it to stderr on
    demand (on test failure or when --print-debug is active).
    """

    def __init__(self, request: pytest.FixtureRequest) -> None:
        self._request = request
        self._entries: list[str] = []

    def __call__(
        self,
        *args: Any,
        title: str | None = None,
        strip_tmp_path: bool | None = None,
        list_dir_contents: bool | None = None,
        max_depth: int | None = None,
        max_length: int | None = None,
        show_type: bool | None = None,
    ) -> None:
        """Pretty-print one or more values and store the output.

        Args:
            *args: Objects to pretty-print.
            title: Optional title for the Console.rule() separators.
            strip_tmp_path: Override global strip_tmp_path setting.
            list_dir_contents: Override global list_dir_contents setting.
            max_depth: Override global max_depth setting.
            max_length: Override global max_length setting.
            show_type: Override global show_type setting.
        """
        resolved_strip = _resolve_option(self._request, "debug_strip_tmp_path", strip_tmp_path)
        resolved_list_dir = _resolve_option(
            self._request, "debug_list_dir_contents", list_dir_contents
        )
        resolved_depth_raw = _resolve_option(self._request, "debug_max_depth", max_depth)
        resolved_length_raw = _resolve_option(self._request, "debug_max_length", max_length)
        resolved_show_type = _resolve_option(self._request, "debug_show_type", show_type)

        resolved_depth = int(resolved_depth_raw) if resolved_depth_raw else None
        resolved_length = int(resolved_length_raw) if resolved_length_raw else None

        tmp_path: Path | None = None
        if resolved_strip:
            with contextlib.suppress(pytest.FixtureLookupError):
                tmp_path = self._request.getfixturevalue("tmp_path")

        buf = StringIO()
        console = Console(file=buf, force_terminal=True)

        rule_title = title or "Debug"
        console.rule(rule_title)

        for arg in args:
            if resolved_show_type:
                console.print(f"[dim]({type(arg).__name__})[/dim]")

            if isinstance(arg, Path):
                display_path = arg
                if tmp_path and resolved_strip:
                    with contextlib.suppress(ValueError):
                        display_path = arg.relative_to(tmp_path)

                if arg.is_dir() and resolved_list_dir:
                    dir_tree = _build_dir_tree(arg, str(display_path))
                    console.print(dir_tree)
                else:
                    console.print(str(display_path))
            else:
                formatted = pretty_repr(
                    arg,
                    max_depth=resolved_depth,
                    max_length=resolved_length,
                )
                console.print(formatted)

        closing_title = f"/{title}" if title else "Debug"
        console.rule(closing_title)

        self._entries.append(buf.getvalue())

    def flush(self) -> None:
        """Write all collected debug entries to stderr."""
        if self._entries:
            output = "\n".join(self._entries)
            sys.stderr.write(output)
            sys.stderr.flush()


@pytest.fixture
def debug(request: pytest.FixtureRequest) -> Generator[DebugPrinter, None, None]:
    """Provide a callable debug printer for pretty-printing variables.

    Collect Rich-formatted output during the test. On teardown, flush
    the output to stderr if the test failed or --print-debug is active.

    Args:
        request: The pytest fixture request.

    Yields:
        A callable DebugPrinter instance.
    """
    printer = DebugPrinter(request)
    yield printer

    always_print = request.config.getoption("print_debug", default=False) or request.config.getini(
        "print_debug"
    )

    if always_print:
        printer.flush()
        return

    report = request.node.stash.get(phase_report_key, {})
    if report.get("call") and report["call"].failed:
        printer.flush()
