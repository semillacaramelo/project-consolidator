"""
Unit tests for ProjectConsolidator.is_excluded_dir.
"""

from pathlib import Path

import pytest

from consolidate_project_sources import ProjectConsolidator


@pytest.mark.parametrize(
    "dirname,expected",
    [
        ("node_modules", True),
        (".git", True),
        (".github", False),
        ("src", False),
    ],
)
def test_is_excluded_dir_parametrized(dirname: str, expected: bool):
    """
    Test is_excluded_dir returns correct boolean for various directory names.
    """
    consolidator = ProjectConsolidator(Path("."))
    assert consolidator.is_excluded_dir(dirname) is expected
