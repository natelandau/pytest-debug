"""Tests for terminal column width feature."""


def test_columns_not_set_by_default(pytester, monkeypatch):
    """Verify COLUMNS env var is not set when no config is provided."""
    # Given: a known COLUMNS value in the environment
    monkeypatch.setenv("COLUMNS", "999")
    pytester.makepyfile("""
        import os

        def test_check_columns():
            # Plugin should not override COLUMNS when disabled (the default)
            assert os.environ.get("COLUMNS") == "999"
    """)

    # When: running without any columns config
    result = pytester.runpytest()

    # Then: the test passes (plugin did not override COLUMNS)
    result.assert_outcomes(passed=1)


def test_columns_cli_flag(pytester):
    """Verify --columns flag sets COLUMNS env var."""
    # Given: a test that checks the COLUMNS env var
    pytester.makepyfile("""
        import os

        def test_check_columns():
            assert os.environ.get("COLUMNS") == "200"
    """)

    # When: running with --columns
    result = pytester.runpytest("--columns=200")

    # Then: the test passes
    result.assert_outcomes(passed=1)


def test_columns_ini_enabled(pytester):
    """Verify set_columns ini option enables COLUMNS with default value."""
    # Given: ini config enables column setting
    pytester.makeini("""
        [pytest]
        set_columns = true
    """)
    pytester.makepyfile("""
        import os

        def test_check_columns():
            assert os.environ.get("COLUMNS") == "180"
    """)

    # When: running the test
    result = pytester.runpytest()

    # Then: the test passes
    result.assert_outcomes(passed=1)


def test_columns_ini_custom_value(pytester):
    """Verify columns ini option sets a custom value."""
    # Given: ini config enables columns with a custom value
    pytester.makeini("""
        [pytest]
        set_columns = true
        columns = 250
    """)
    pytester.makepyfile("""
        import os

        def test_check_columns():
            assert os.environ.get("COLUMNS") == "250"
    """)

    # When: running the test
    result = pytester.runpytest()

    # Then: the test passes
    result.assert_outcomes(passed=1)


def test_columns_cli_overrides_ini(pytester):
    """Verify --columns CLI flag overrides ini value."""
    # Given: ini config sets one value, CLI sets another
    pytester.makeini("""
        [pytest]
        set_columns = true
        columns = 250
    """)
    pytester.makepyfile("""
        import os

        def test_check_columns():
            assert os.environ.get("COLUMNS") == "300"
    """)

    # When: running with --columns overriding the ini value
    result = pytester.runpytest("--columns=300")

    # Then: CLI wins
    result.assert_outcomes(passed=1)
