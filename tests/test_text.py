"""Tests for the shared text transforms."""

from pathlib import PureWindowsPath

from devtools._text import strip_tmp_path, strip_trailing_whitespace


def test_strip_tmp_path_removes_the_windows_separator():
    """Verify a backslash-separated prefix collapses to a relative path."""
    # Given output naming a file under a Windows-style tmp_path
    tmp_path = PureWindowsPath(r"C:\Temp\pytest-0\test_x0")
    text = rf"wrote {tmp_path}\sub\f.txt"

    # When stripping the tmp_path prefix
    result = strip_tmp_path(text, tmp_path)

    # Then no leading separator is left behind
    assert result == r"wrote sub\f.txt"


def test_strip_trailing_whitespace_removes_per_line_padding():
    """Verify trailing spaces and tabs are removed from every line."""
    # Given text whose lines carry trailing padding
    text = "alpha   \nbeta\t\ngamma\n"

    # When stripping trailing whitespace
    result = strip_trailing_whitespace(text)

    # Then every line is right-trimmed and the trailing newline survives
    assert result == "alpha\nbeta\ngamma\n"


def test_strip_trailing_whitespace_preserves_blank_line_structure():
    """Verify whitespace-only lines collapse without changing the line count."""
    # Given text with a whitespace-only line and no trailing newline
    text = "one  \n\n   \ntwo  "

    # When stripping trailing whitespace
    result = strip_trailing_whitespace(text)

    # Then whitespace-only lines become empty and the line count is unchanged
    assert result == "one\n\n\ntwo"
    assert len(result.split("\n")) == len(text.split("\n"))
