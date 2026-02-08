"""Central hook registration for pytest-devtools plugin."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

from devtools import capsys_strip, columns, debug_fixture, whitespace
from devtools.capsys_strip import capsys as capsys  # noqa: PLC0414
from devtools.columns import _set_columns as _set_columns  # noqa: PLC0414
from devtools.debug_fixture import debug as debug  # noqa: PLC0414
from devtools.debug_fixture import phase_report_key


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register CLI options for all pytest-devtools features."""
    columns.add_options(parser)
    capsys_strip.add_options(parser)
    whitespace.add_options(parser)
    debug_fixture.add_options(parser)


def pytest_configure(config: pytest.Config) -> None:
    """Register markers for all pytest-devtools features."""
    capsys_strip.configure(config)


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_makereport(
    item: pytest.Item,
    call: pytest.CallInfo[None],  # noqa: ARG001
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    """Store test phase reports for debug fixture teardown access.

    Args:
        item: The test item.
        call: The call information.

    Returns:
        The test report.
    """
    rep = yield
    item.stash.setdefault(phase_report_key, {})[rep.when] = rep
    return rep


def pytest_assertrepr_compare(
    config: pytest.Config,
    op: str,
    left: object,
    right: object,
) -> list[str] | None:
    """Delegate assertion comparison to whitespace module.

    Args:
        config: The pytest config object.
        op: The comparison operator.
        left: The left operand.
        right: The right operand.

    Returns:
        Custom explanation lines or None for default behavior.
    """
    return whitespace.pytest_assertrepr_compare(config, op, left, right)
