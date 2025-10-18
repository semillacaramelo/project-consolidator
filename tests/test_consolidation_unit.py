"""
Unit tests for ProjectConsolidator.is_excluded_dir.
"""
import pytest
from pathlib import Path
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
    Test that is_excluded_dir returns correct boolean for various directory names.
    """
    consolidator = ProjectConsolidator(Path("."))
    assert consolidator.is_excluded_dir(dirname) is expected
