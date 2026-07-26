"""Pure text transforms shared by the capsys override and the CLI runner fixtures.

Keep this module free of pytest imports so the transforms stay directly testable
and reusable from any context.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

ANSI_PATTERN = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from a string.

    Args:
        text: The string potentially containing ANSI escape sequences.

    Returns:
        The string with all ANSI SGR sequences removed.
    """
    return ANSI_PATTERN.sub("", text)


def strip_tmp_path(text: str, tmp_path: Path) -> str:
    r"""Remove tmp_path prefix occurrences from a string.

    Strip the prefix together with its trailing separator, then any bare
    remainder, so that paths nested under ``tmp_path`` collapse to their
    relative portion. Both separators are tried because a Windows
    ``str(tmp_path)`` uses ``\`` while the bare prefix alone would leave a
    leading separator behind.

    Args:
        text: The captured output string.
        tmp_path: The pytest ``tmp_path`` fixture value to strip.

    Returns:
        The string with tmp_path prefixes removed.
    """
    tmp_str = str(tmp_path)
    for separator in ("/", "\\"):
        text = text.replace(f"{tmp_str}{separator}", "")
    return text.replace(tmp_str, "")


def strip_trailing_whitespace(text: str) -> str:
    r"""Remove trailing whitespace from every line of a string.

    Rich renders panels and tables by padding every line out to the full
    terminal width, which makes exact-match assertions against CLI help output
    impractical. Splitting on ``"\n"`` rather than using ``splitlines()``
    preserves the presence or absence of a trailing newline.

    Args:
        text: The string to right-trim line by line.

    Returns:
        The string with trailing whitespace removed from each line.
    """
    return "\n".join(line.rstrip() for line in text.split("\n"))
