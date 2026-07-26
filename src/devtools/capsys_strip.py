"""ANSI escape sequence stripping for capsys captured output.

Override pytest's built-in capsys fixture to automatically strip ANSI escape
sequences from captured stdout and stderr, making assertions against captured
output simpler and more reliable.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

import pytest
from _pytest.capture import CaptureFixture, CaptureResult

from devtools._options import resolve_option, should_strip_ansi
from devtools._text import strip_ansi as strip_ansi  # noqa: PLC0414
from devtools._text import strip_tmp_path as strip_tmp_path  # noqa: PLC0414

if TYPE_CHECKING:
    from pathlib import Path

    from _pytest.config import Config


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
    group.addoption(
        "--capsys-strip-tmp-path",
        action="store_true",
        default=None,
        dest="capsys_strip_tmp_path",
        help="Strip tmp_path prefix from capsys output (default: false)",
    )
    group.addoption(
        "--no-capsys-strip-tmp-path",
        action="store_false",
        dest="capsys_strip_tmp_path",
        help="Don't strip tmp_path prefix from capsys output",
    )
    parser.addini(
        "strip_ansi",
        type="bool",
        default=True,
        help="Enable/disable ANSI stripping from capsys output (default: true)",
    )
    parser.addini(
        "capsys_strip_tmp_path",
        type="bool",
        default=False,
        help="Strip tmp_path prefix from capsys output (default: false)",
    )


def configure(config: Config) -> None:
    """Register the keep_ansi marker.

    Args:
        config: The pytest config object.
    """
    config.addinivalue_line(
        "markers",
        "keep_ansi: disable ANSI stripping for this test",
    )


class StrippedCaptureFixture:
    """Wrapper around CaptureFixture that strips noise from readouterr() results.

    Delegate all attribute access to the underlying CaptureFixture, intercepting
    only readouterr() to optionally strip ANSI escape sequences and/or the
    tmp_path prefix from captured stdout/stderr.
    """

    def __init__(
        self,
        original: CaptureFixture[str],
        *,
        request: pytest.FixtureRequest,
        ansi: bool,
        tmp_path: bool,
    ) -> None:
        self._original = original
        self._request = request
        self._strip_ansi_enabled = ansi
        self._strip_tmp_path_enabled = tmp_path

    def readouterr(self) -> CaptureResult[str]:
        """Read captured output, applying configured post-processing."""
        result = self._original.readouterr()
        out, err = result.out, result.err

        if self._strip_ansi_enabled:
            out = strip_ansi(out)
            err = strip_ansi(err)

        if self._strip_tmp_path_enabled:
            tmp_path: Path | None = None
            with contextlib.suppress(pytest.FixtureLookupError):
                tmp_path = self._request.getfixturevalue("tmp_path")
            if tmp_path is not None:
                out = strip_tmp_path(out, tmp_path)
                err = strip_tmp_path(err, tmp_path)

        return CaptureResult(out=out, err=err)

    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to the wrapped capsys fixture."""
        return getattr(self._original, name)


@pytest.fixture
def capsys(
    request: pytest.FixtureRequest,
    capsys: CaptureFixture[str],
) -> CaptureFixture[str] | StrippedCaptureFixture:
    """Override built-in capsys to optionally strip ANSI and/or tmp_path.

    When either ANSI stripping (default on) or tmp_path stripping (default off)
    is enabled, wrap the original capsys fixture so that readouterr() returns
    post-processed output.

    Args:
        request: The pytest fixture request object.
        capsys: The original pytest capsys fixture.

    Returns:
        Either the original capsys or a wrapped version that post-processes output.
    """
    ansi = should_strip_ansi(request)
    tmp_path = bool(resolve_option(request, "capsys_strip_tmp_path"))

    if not ansi and not tmp_path:
        return capsys

    return StrippedCaptureFixture(capsys, request=request, ansi=ansi, tmp_path=tmp_path)
