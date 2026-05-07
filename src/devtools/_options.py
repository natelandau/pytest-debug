"""Shared option resolution for pytest-devtools features."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pytest


def resolve_option(
    request: pytest.FixtureRequest,
    name: str,
    per_call: bool | int | None = None,  # noqa: FBT001
) -> Any:
    """Resolve a config option using per-call > CLI > INI precedence.

    Per-call takes priority, then CLI flag, then INI option. Use a single
    ``name`` for both the ``getoption`` dest and the INI key so call sites
    only have to spell the option once.

    Args:
        request: The pytest fixture request.
        name: The option name (matching both getoption dest and ini key).
        per_call: The per-call override value, or None to fall through to
            CLI/INI resolution.

    Returns:
        The resolved option value.
    """
    if per_call is not None:
        return per_call

    cli_value = request.config.getoption(name, default=None)
    if cli_value is not None:
        return cli_value

    return request.config.getini(name)
