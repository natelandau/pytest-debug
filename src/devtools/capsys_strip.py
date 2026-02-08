"""ANSI escape sequence stripping for capsys captured output.

Override pytest's built-in capsys fixture to automatically strip ANSI escape
sequences from captured stdout and stderr, making assertions against captured
output simpler and more reliable.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import pytest
from _pytest.capture import CaptureFixture, CaptureResult

if TYPE_CHECKING:
    from _pytest.config import Config

ANSI_PATTERN = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from a string.

    Args:
        text: The string potentially containing ANSI escape sequences.

    Returns:
        The string with all ANSI SGR sequences removed.
    """
    return ANSI_PATTERN.sub("", text)


def add_options(parser: pytest.Parser) -> None:
    """Register CLI options for ANSI stripping.

    Args:
        parser: The pytest option parser to add options to.
    """
    group = parser.getgroup("devtools-capsys", "ANSI stripping for capsys")
    group.addoption(
        "--no-strip-ansi",
        action="store_true",
        default=False,
        help="Disable automatic ANSI escape sequence stripping from capsys output",
    )
    parser.addini(
        "strip_ansi",
        type="bool",
        default=True,
        help="Enable/disable ANSI stripping from capsys output (default: true)",
    )


def configure(config: Config) -> None:
    """Register the keep_ansi marker.

    Args:
        config: The pytest config object.
    """
    config.addinivalue_line(
        "markers",
        "keep_ansi: disable ANSI stripping from capsys for this test",
    )


def _should_strip(request: pytest.FixtureRequest) -> bool:
    """Determine whether ANSI stripping should be applied for this test.

    Args:
        request: The pytest fixture request object.

    Returns:
        True if ANSI codes should be stripped, False otherwise.
    """
    if request.config.getoption("no_strip_ansi", default=False):
        return False

    if not request.config.getini("strip_ansi"):
        return False

    return not request.node.get_closest_marker("keep_ansi")


class StrippedCaptureFixture:
    """Wrapper around CaptureFixture that strips ANSI from readouterr() results.

    Delegate all attribute access to the underlying CaptureFixture, intercepting
    only readouterr() to strip ANSI escape sequences.
    """

    def __init__(self, original: CaptureFixture[str]) -> None:
        self._original = original

    def readouterr(self) -> CaptureResult[str]:
        """Read and strip ANSI from captured output.

        Returns:
            CaptureResult with ANSI sequences removed from both out and err.
        """
        result = self._original.readouterr()
        return CaptureResult(
            out=strip_ansi(result.out),
            err=strip_ansi(result.err),
        )

    def __getattr__(self, name: str) -> Any:
        """Delegate all other attribute access to the original fixture.

        Args:
            name: The attribute name to look up.

        Returns:
            The attribute from the original CaptureFixture.
        """
        return getattr(self._original, name)


@pytest.fixture
def capsys(
    request: pytest.FixtureRequest,
    capsys: CaptureFixture[str],
) -> CaptureFixture[str] | StrippedCaptureFixture:
    """Override built-in capsys to optionally strip ANSI escape sequences.

    When ANSI stripping is enabled (the default), wrap the original capsys
    fixture so that readouterr() returns output with ANSI codes removed.

    Args:
        request: The pytest fixture request object.
        capsys: The original pytest capsys fixture.

    Returns:
        Either the original capsys or a wrapped version that strips ANSI codes.
    """
    if _should_strip(request):
        return StrippedCaptureFixture(capsys)
    return capsys
