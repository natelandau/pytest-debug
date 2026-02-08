"""Make invisible whitespace characters visible in assertion failure diffs.

Replace tabs, carriage returns, trailing spaces, and newlines with visible
Unicode symbols so that whitespace-only differences in string comparisons
are immediately obvious in pytest assertion output.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

TRAILING_SPACES_PATTERN = re.compile(r" +$", re.MULTILINE)


def add_options(parser: pytest.Parser) -> None:
    """Register CLI options for whitespace visibility.

    Args:
        parser: The pytest option parser to add options to.
    """
    group = parser.getgroup("devtools-whitespace", "Whitespace visibility in assertions")
    group.addoption(
        "--no-show-whitespace",
        action="store_true",
        default=False,
        help="Disable visible whitespace symbols in assertion failure diffs",
    )
    parser.addini(
        "show_whitespace",
        type="bool",
        default=True,
        help="Enable/disable whitespace visibility in assertion diffs (default: true)",
    )


def _is_enabled(config: pytest.Config) -> bool:
    """Check whether whitespace visibility is enabled.

    Args:
        config: The pytest config object.

    Returns:
        True if whitespace visibility is enabled.
    """
    if config.getoption("no_show_whitespace", default=False):
        return False

    return config.getini("show_whitespace")


def make_whitespace_visible(text: str) -> str:
    """Replace invisible whitespace characters with visible symbols.

    Replace tabs with arrows, carriage returns with left arrows, trailing
    spaces with middle dots, and newlines with return symbols.

    Args:
        text: The string in which to make whitespace visible.

    Returns:
        The string with whitespace characters replaced by visible symbols.
    """
    text = text.replace("\t", "\u2192")
    text = text.replace("\r", "\u2190")
    text = TRAILING_SPACES_PATTERN.sub(lambda m: "\u00b7" * len(m.group()), text)
    return text.replace("\n", "\u21b5\n")


def pytest_assertrepr_compare(
    config: pytest.Config,
    op: str,
    left: object,
    right: object,
) -> list[str] | None:
    """Provide custom assertion failure output with visible whitespace.

    When comparing strings with ==, generate comparison lines that show
    invisible whitespace as visible Unicode symbols.

    Args:
        config: The pytest config object.
        op: The comparison operator (e.g. "==").
        left: The left operand.
        right: The right operand.

    Returns:
        A list of explanation strings, or None to use default behavior.
    """
    if not _is_enabled(config):
        return None

    if op != "==" or not isinstance(left, str) or not isinstance(right, str):
        return None

    visible_left = make_whitespace_visible(left)
    visible_right = make_whitespace_visible(right)

    # Only activate if whitespace replacement actually changed something
    if visible_left == left and visible_right == right:
        return None

    return [
        f"'{visible_left}' == '{visible_right}'",
        "",
        "Whitespace-visible comparison:",
        f"  Left:  '{visible_left}'",
        f"  Right: '{visible_right}'",
    ]
