"""
Unit tests for FileWalker.is_excluded_dir.
"""

from pathlib import Path

import pytest

from consolidate_project_sources import FileWalker


@pytest.mark.parametrize(
    "dirname,expected",
    [
        ("node_modules", True),
        (".git", True),
        (".github", False),
        ("src", False),
        ("venv", True),
        (".venv", True),
    ],
)
def test_is_excluded_dir_parametrized(dirname: str, expected: bool):
    """
    Test is_excluded_dir returns correct boolean for various directory names.
    """
    file_walker = FileWalker(Path("."))
    assert file_walker.is_excluded_dir(dirname) is expected
