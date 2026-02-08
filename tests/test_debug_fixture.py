"""Tests for the debug fixture."""


def test_debug_fixture_exists(pytester):
    """Verify debug fixture is available in tests."""
    # Given: a test that uses the debug fixture
    pytester.makepyfile("""
        def test_use_debug(debug):
            debug("hello")
    """)

    # When: running the test
    result = pytester.runpytest()

    # Then: the test passes
    result.assert_outcomes(passed=1)


def test_debug_output_on_failure(pytester):
    """Verify debug output is shown when a test fails."""
    # Given: a test that uses debug and then fails
    pytester.makepyfile("""
        def test_fail_with_debug(debug):
            debug({"key": "value"})
            assert False
    """)

    # When: running the test
    result = pytester.runpytest("-s")

    # Then: the debug output appears in stderr
    result.assert_outcomes(failed=1)
    result.stderr.fnmatch_lines(["*key*value*"])


def test_debug_output_hidden_on_pass(pytester):
    """Verify debug output is hidden when a test passes."""
    # Given: a test that uses debug and passes
    pytester.makepyfile("""
        def test_pass_with_debug(debug):
            debug("should not appear")
            assert True
    """)

    # When: running the test
    result = pytester.runpytest("-s")

    # Then: the debug output does NOT appear
    result.assert_outcomes(passed=1)
    assert "should not appear" not in result.stderr.str()


def test_debug_print_always_flag(pytester):
    """Verify --print-debug shows output even on passing tests."""
    # Given: a test that uses debug and passes
    pytester.makepyfile("""
        def test_pass_with_debug(debug):
            debug("always visible")
            assert True
    """)

    # When: running with --print-debug
    result = pytester.runpytest("-s", "--print-debug")

    # Then: the debug output appears
    result.assert_outcomes(passed=1)
    result.stderr.fnmatch_lines(["*always visible*"])


def test_debug_with_title(pytester):
    """Verify debug output uses custom title in rule separators."""
    # Given: a test that uses debug with a title
    pytester.makepyfile("""
        def test_titled_debug(debug):
            debug("data", title="My Title")
            assert False
    """)

    # When: running the test
    result = pytester.runpytest("-s")

    # Then: the title appears in the output
    result.assert_outcomes(failed=1)
    result.stderr.fnmatch_lines(["*My Title*"])


def test_debug_multiple_args(pytester):
    """Verify debug handles multiple arguments."""
    # Given: a test that passes multiple args to debug
    pytester.makepyfile("""
        def test_multi_debug(debug):
            debug("first", "second", [1, 2, 3])
            assert False
    """)

    # When: running the test
    result = pytester.runpytest("-s")

    # Then: all arguments appear in output
    result.assert_outcomes(failed=1)
    stderr = result.stderr.str()
    assert "first" in stderr
    assert "second" in stderr


def test_debug_show_type(pytester):
    """Verify show_type displays type annotations."""
    # Given: a test that uses debug with show_type
    pytester.makepyfile("""
        def test_typed_debug(debug):
            debug({"key": "value"}, show_type=True)
            assert False
    """)

    # When: running the test
    result = pytester.runpytest("-s")

    # Then: the type appears in output
    result.assert_outcomes(failed=1)
    result.stderr.fnmatch_lines(["*dict*"])


def test_debug_strip_tmp_path(pytester):
    """Verify strip_tmp_path removes tmp_path prefix from Path objects."""
    # Given: a test that debugs a path inside tmp_path
    pytester.makepyfile("""
        def test_path_debug(debug, tmp_path):
            test_file = tmp_path / "subdir" / "file.txt"
            test_file.parent.mkdir(parents=True)
            test_file.write_text("content")
            debug(test_file)
            assert False
    """)

    # When: running the test (strip_tmp_path defaults to True)
    result = pytester.runpytest("-s")

    # Then: output shows relative path, not full tmp_path
    result.assert_outcomes(failed=1)
    stderr = result.stderr.str()
    assert "subdir/file.txt" in stderr or "subdir\\\\file.txt" in stderr


def test_debug_no_strip_tmp_path(pytester):
    """Verify --no-debug-strip-tmp-path preserves full path."""
    # Given: a test that debugs a path inside tmp_path
    pytester.makepyfile("""
        def test_path_debug(debug, tmp_path):
            test_file = tmp_path / "file.txt"
            test_file.write_text("content")
            debug(test_file)
            assert False
    """)

    # When: running with --no-debug-strip-tmp-path
    result = pytester.runpytest("-s", "--no-debug-strip-tmp-path")

    # Then: output shows full absolute path (not just the filename)
    result.assert_outcomes(failed=1)
    stderr = result.stderr.str()
    # With stripping disabled, the full path should include directory separators
    # beyond just the filename, indicating it's an absolute path
    assert "pytest" in stderr.lower() or "/" in stderr.replace("─", "")


def test_debug_list_dir_contents(pytester):
    """Verify list_dir_contents shows directory tree."""
    # Given: a test with a directory containing files
    pytester.makepyfile("""
        def test_dir_debug(debug, tmp_path):
            (tmp_path / "a.txt").write_text("a")
            (tmp_path / "b.txt").write_text("b")
            sub = tmp_path / "subdir"
            sub.mkdir()
            (sub / "c.txt").write_text("c")
            debug(tmp_path, list_dir_contents=True)
            assert False
    """)

    # When: running the test
    result = pytester.runpytest("-s")

    # Then: output shows directory tree
    result.assert_outcomes(failed=1)
    stderr = result.stderr.str()
    assert "a.txt" in stderr
    assert "b.txt" in stderr
    assert "subdir" in stderr
    assert "c.txt" in stderr


def test_debug_max_depth(pytester):
    """Verify max_depth limits nesting in debug output."""
    # Given: a test with deeply nested data
    pytester.makepyfile("""
        def test_depth_debug(debug):
            data = {"a": {"b": {"c": {"d": "deep"}}}}
            debug(data, max_depth=2)
            assert False
    """)

    # When: running the test
    result = pytester.runpytest("-s")

    # Then: the test fails and deep value is truncated
    result.assert_outcomes(failed=1)
    stderr = result.stderr.str()
    assert "..." in stderr


def test_debug_max_length(pytester):
    """Verify max_length truncates long collections in debug output."""
    # Given: a test with a long list
    pytester.makepyfile("""
        def test_length_debug(debug):
            data = list(range(100))
            debug(data, max_length=5)
            assert False
    """)

    # When: running the test
    result = pytester.runpytest("-s")

    # Then: the output is truncated
    result.assert_outcomes(failed=1)
    stderr = result.stderr.str()
    assert "..." in stderr
