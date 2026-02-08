"""Set COLUMNS environment variable for test runs.

Prevent code under test (including Rich-based applications) from detecting
a narrow terminal width and introducing unwanted line wraps in captured output.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from _pytest.config import Config

DEFAULT_COLUMNS = 180


def add_options(parser: pytest.Parser) -> None:
    """Register CLI options for terminal column width management.

    Args:
        parser: The pytest option parser to add options to.
    """
    group = parser.getgroup("devtools-columns", "Terminal column width")
    group.addoption(
        "--columns",
        action="store",
        type=int,
        default=None,
        help=f"Set COLUMNS environment variable to this value (default: {DEFAULT_COLUMNS})",
    )
    parser.addini(
        "set_columns",
        type="bool",
        default=False,
        help="Enable setting COLUMNS environment variable (default: false)",
    )
    parser.addini(
        "columns",
        default=str(DEFAULT_COLUMNS),
        help=f"Value for COLUMNS environment variable (default: {DEFAULT_COLUMNS})",
    )


def _get_columns_value(config: Config) -> int | None:
    """Determine the COLUMNS value from CLI and ini options.

    Args:
        config: The pytest config object.

    Returns:
        The column width to set, or None if columns should not be set.
    """
    cli_value: int | None = config.getoption("columns", default=None)
    if cli_value is not None:
        return cli_value

    if not config.getini("set_columns"):
        return None

    ini_value: str = config.getini("columns")
    return int(ini_value)


@pytest.fixture(autouse=True)
def _set_columns(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Set COLUMNS environment variable for each test.

    Args:
        request: The pytest fixture request object.
        monkeypatch: The pytest monkeypatch fixture.
    """
    columns = _get_columns_value(request.config)
    if columns is not None:
        monkeypatch.setenv("COLUMNS", str(columns))
