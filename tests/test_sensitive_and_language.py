"""
Unit tests for sensitive file detection and language mapping.
"""
from pathlib import Path

import pytest

from consolidate_project_sources import FileWalker, ProjectConsolidator, ReportGenerator


@pytest.mark.parametrize(
    "filename,expected",
    [
        (".env", True),
        ("secrets.json", True),
        ("README.md", False),
        ("main.py", False),
        (".ENV", True),
        ("prod.SECRETS.json", True),
    ],
)
def test_is_sensitive_file(filename, expected):
    """
    Test is_sensitive_file for sensitive and non-sensitive filenames.
    """
    assert ProjectConsolidator.is_sensitive_file(Path(filename)) is expected


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("main.py", "Python"),
        ("app.js", "JavaScript"),
        ("Dockerfile", "Docker"),
        ("file.unknown", "Text"),  # or None, depending on implementation
    ],
)
def test_get_file_language(filename, expected):
    """
    Test get_file_language for various file extensions and names.
    """
    result = FileWalker.get_file_language(Path(filename))
    assert result == expected
