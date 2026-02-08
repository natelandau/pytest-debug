"""Tests for whitespace visibility in assertion failures."""


def test_trailing_spaces_visible(pytester):
    """Verify trailing spaces are shown as middle dots in assertion diffs."""
    # Given: a test comparing strings with trailing space difference
    pytester.makepyfile("""
        def test_trailing():
            assert "hello " == "hello"
    """)

    # When: running the test
    result = pytester.runpytest()

    # Then: output contains the middle dot symbol for trailing space
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*\u00b7*"])


def test_tab_visible(pytester):
    """Verify tabs are shown as arrow symbols in assertion diffs."""
    # Given: a test comparing strings with tab difference
    pytester.makepyfile("""
        def test_tabs():
            assert "hello\\tworld" == "hello world"
    """)

    # When: running the test
    result = pytester.runpytest()

    # Then: output contains the arrow symbol for tab
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*\u2192*"])


def test_carriage_return_visible(pytester):
    """Verify carriage returns are shown as left arrow in assertion diffs."""
    # Given: a test comparing strings with carriage return difference
    pytester.makepyfile("""
        def test_cr():
            assert "hello\\r\\n" == "hello\\n"
    """)

    # When: running the test
    result = pytester.runpytest()

    # Then: output contains the left arrow symbol for carriage return
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*\u2190*"])


def test_newline_visible(pytester):
    """Verify newlines are shown as return symbol in assertion diffs."""
    # Given: a test comparing strings with newline difference
    pytester.makepyfile("""
        def test_newline():
            assert "hello\\n" == "hello"
    """)

    # When: running the test
    result = pytester.runpytest()

    # Then: output contains the return symbol for newline
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*\u21b5*"])


def test_whitespace_disabled(pytester):
    """Verify --no-show-whitespace disables whitespace symbols."""
    # Given: a test comparing strings with trailing space
    pytester.makepyfile("""
        def test_trailing():
            assert "hello " == "hello"
    """)

    # When: running with --no-show-whitespace
    result = pytester.runpytest("--no-show-whitespace")

    # Then: output does NOT contain the middle dot symbol
    result.assert_outcomes(failed=1)
    assert "\u00b7" not in result.stdout.str()


def test_non_string_comparison_unchanged(pytester):
    """Verify non-string comparisons are not affected by whitespace feature."""
    # Given: a test comparing integers
    pytester.makepyfile("""
        def test_integers():
            assert 1 == 2
    """)

    # When: running the test
    result = pytester.runpytest()

    # Then: the test fails normally without whitespace symbols
    result.assert_outcomes(failed=1)


def test_whitespace_ini_disable(pytester):
    """Verify show_whitespace ini option disables the feature."""
    # Given: ini config disables whitespace visibility
    pytester.makeini("""
        [pytest]
        show_whitespace = false
    """)
    pytester.makepyfile("""
        def test_trailing():
            assert "hello " == "hello"
    """)

    # When: running the test
    result = pytester.runpytest()

    # Then: output does NOT contain the middle dot symbol
    result.assert_outcomes(failed=1)
    assert "\u00b7" not in result.stdout.str()
