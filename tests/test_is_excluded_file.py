"""
Unit tests for ProjectConsolidator.is_excluded_file.
"""

from pathlib import Path

import pytest

from consolidate_project_sources import FileWalker


@pytest.mark.parametrize(
    "filename,size,expected,reason",
    [
        ("Dockerfile", 10_000_000, False, "force-included regardless of size"),
        ("data.csv", 10_000_000, True, "excluded when over size limit"),
        ("module.pyc", 100, True, "excluded by extension"),
        ("package-lock.json", 100, True, "excluded by name"),
        ("main.py", 100, False, "normal source file included"),
    ],
)
def test_is_excluded_file_parametrized(
    monkeypatch, filename, size, expected, reason
):
    """
    Test is_excluded_file for various filenames, sizes, and exclusion rules.
    """
    file_walker = FileWalker(Path("."))
    # Mock the stat result to avoid needing a real file
    mock_stat = type("stat", (), {"st_size": size})
    monkeypatch.setattr("pathlib.Path.stat", lambda self: mock_stat)
    result = file_walker.is_excluded_file(Path(filename))
    assert result is expected, f"{filename}: {reason}"
