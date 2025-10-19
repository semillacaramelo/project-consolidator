"""
Tests for CLI, argument parsing, and utility functions.
"""
import argparse
import sys
from pathlib import Path

import pytest
from consolidate_project_sources import (
    OUTPUT_FILE_PATTERN,
    detect_project_root,
    ensure_gitignore_entry,
    main,
    parse_arguments,
)


def test_parse_arguments_defaults(mocker):
    """Test parse_arguments with default values."""
    mocker.patch.object(sys, "argv", ["script.py"])
    args = parse_arguments()
    assert args.output is None
    assert args.project_root is None
    assert not args.verbose
    assert not args.no_update_gitignore
    assert not args.no_list_env_keys


def test_parse_arguments_custom(mocker):
    """Test parse_arguments with custom arguments."""
    mocker.patch.object(
        sys,
        "argv",
        [
            "script.py",
            "--output",
            "test.txt",
            "--project-root",
            "/tmp",
            "--verbose",
            "--no-update-gitignore",
            "--no-list-env-keys",
        ],
    )
    args = parse_arguments()
    assert args.output == Path("test.txt")
    assert args.project_root == Path("/tmp")
    assert args.verbose
    assert args.no_update_gitignore
    assert args.no_list_env_keys


def test_ensure_gitignore_entry_creates_file(tmp_path):
    """Test that ensure_gitignore_entry creates .gitignore if it doesn't exist."""
    project_root = tmp_path
    # Temporarily patch PROJECT_ROOT for the test
    original_project_root = "consolidate_project_sources.PROJECT_ROOT"
    with pytest.MonkeyPatch.context() as m:
        m.setattr(original_project_root, project_root)
        ensure_gitignore_entry(update_gitignore=True)

    gitignore_path = project_root / ".gitignore"
    assert gitignore_path.exists()
    content = gitignore_path.read_text()
    assert OUTPUT_FILE_PATTERN in content


def test_ensure_gitignore_entry_appends_to_existing_file(tmp_path):
    """Test that ensure_gitignore_entry appends to an existing .gitignore."""
    project_root = tmp_path
    gitignore_path = project_root / ".gitignore"
    gitignore_path.write_text("node_modules/\n")

    original_project_root = "consolidate_project_sources.PROJECT_ROOT"
    with pytest.MonkeyPatch.context() as m:
        m.setattr(original_project_root, project_root)
        ensure_gitignore_entry(update_gitignore=True)

    content = gitignore_path.read_text()
    assert "node_modules/" in content
    assert OUTPUT_FILE_PATTERN in content


def test_ensure_gitignore_entry_does_not_duplicate(tmp_path):
    """Test that ensure_gitignore_entry doesn't add a duplicate pattern."""
    project_root = tmp_path
    gitignore_path = project_root / ".gitignore"
    initial_content = f"node_modules/\n{OUTPUT_FILE_PATTERN}\n"
    gitignore_path.write_text(initial_content)

    original_project_root = "consolidate_project_sources.PROJECT_ROOT"
    with pytest.MonkeyPatch.context() as m:
        m.setattr(original_project_root, project_root)
        ensure_gitignore_entry(update_gitignore=True)

    content = gitignore_path.read_text()
    assert content.count(OUTPUT_FILE_PATTERN) == 1


def test_detect_project_root(tmp_path):
    """Test detect_project_root finds the correct root directory."""
    # Create a nested structure: root -> level1 -> level2
    project_root = tmp_path
    (project_root / ".git").mkdir()
    level1 = project_root / "level1"
    level1.mkdir()
    level2 = level1 / "level2"
    level2.mkdir()

    # Temporarily patch __file__ to simulate running from level2
    original_file = "consolidate_project_sources.__file__"
    with pytest.MonkeyPatch.context() as m:
        m.setattr(original_file, str(level2 / "script.py"))
        detected_root = detect_project_root()

    assert detected_root == project_root


def test_main_function(mocker, tmp_path):
    """Test the main function for a successful run."""
    # Mock sys.argv to control command-line arguments
    mocker.patch.object(
        sys,
        "argv",
        ["script.py", "--project-root", str(tmp_path), "--output", str(tmp_path / "output.txt")],
    )

    # Create a dummy file in the project
    (tmp_path / "test_file.txt").write_text("Hello, world!")

    # Run the main function and check the exit code
    exit_code = main()
    assert exit_code == 0

    # Verify that the output file was created and has content
    output_file = tmp_path / "output.txt"
    assert output_file.exists()
    content = output_file.read_text()
    assert "Hello, world!" in content
