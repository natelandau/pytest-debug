"""Tests for ANSI stripping from capsys."""


def test_capsys_strips_ansi_from_stdout(pytester):
    """Verify ANSI codes are stripped from captured stdout by default."""
    # Given: a test that prints ANSI-colored output
    pytester.makepyfile("""
        def test_ansi_stdout(capsys):
            print("\\x1b[31mred text\\x1b[0m")
            captured = capsys.readouterr()
            assert captured.out == "red text\\n"
    """)

    # When: running the test
    result = pytester.runpytest()

    # Then: the test passes (ANSI was stripped)
    result.assert_outcomes(passed=1)


def test_capsys_strips_ansi_from_stderr(pytester):
    """Verify ANSI codes are stripped from captured stderr by default."""
    # Given: a test that prints ANSI-colored output to stderr
    pytester.makepyfile("""
        import sys

        def test_ansi_stderr(capsys):
            print("\\x1b[32mgreen text\\x1b[0m", file=sys.stderr)
            captured = capsys.readouterr()
            assert captured.err == "green text\\n"
    """)

    # When: running the test
    result = pytester.runpytest()

    # Then: the test passes (ANSI was stripped)
    result.assert_outcomes(passed=1)


def test_capsys_no_strip_ansi_flag(pytester):
    """Verify --no-strip-ansi disables ANSI stripping."""
    # Given: a test that expects raw ANSI codes
    pytester.makepyfile("""
        def test_raw_ansi(capsys):
            print("\\x1b[31mred\\x1b[0m")
            captured = capsys.readouterr()
            assert "\\x1b[31m" in captured.out
    """)

    # When: running with --no-strip-ansi
    result = pytester.runpytest("--no-strip-ansi")

    # Then: the test passes (ANSI was preserved)
    result.assert_outcomes(passed=1)


def test_capsys_keep_ansi_marker(pytester):
    """Verify @pytest.mark.keep_ansi disables stripping for one test."""
    # Given: two tests, one with keep_ansi marker
    pytester.makepyfile("""
        import pytest

        @pytest.mark.keep_ansi
        def test_raw(capsys):
            print("\\x1b[31mred\\x1b[0m")
            captured = capsys.readouterr()
            assert "\\x1b[31m" in captured.out

        def test_stripped(capsys):
            print("\\x1b[31mred\\x1b[0m")
            captured = capsys.readouterr()
            assert captured.out == "red\\n"
    """)

    # When: running the tests
    result = pytester.runpytest()

    # Then: both tests pass
    result.assert_outcomes(passed=2)


def test_capsys_strips_complex_ansi_sequences(pytester):
    """Verify complex ANSI sequences (bold, bg color, multi-param) are stripped."""
    # Given: a test with complex ANSI sequences
    pytester.makepyfile("""
        def test_complex_ansi(capsys):
            print("\\x1b[1;31;42mbold red on green\\x1b[0m normal")
            captured = capsys.readouterr()
            assert captured.out == "bold red on green normal\\n"
    """)

    # When: running the test
    result = pytester.runpytest()

    # Then: the test passes
    result.assert_outcomes(passed=1)


def test_capsys_ini_disable(pytester):
    """Verify strip_ansi ini option disables stripping."""
    # Given: ini config disables stripping
    pytester.makeini("""
        [pytest]
        strip_ansi = false
    """)
    pytester.makepyfile("""
        def test_raw(capsys):
            print("\\x1b[31mred\\x1b[0m")
            captured = capsys.readouterr()
            assert "\\x1b[31m" in captured.out
    """)

    # When: running the test
    result = pytester.runpytest()

    # Then: the test passes
    result.assert_outcomes(passed=1)
