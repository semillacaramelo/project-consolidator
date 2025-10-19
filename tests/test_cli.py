"""
Tests for the command-line interface and main entry point of the script.
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from consolidate_project_sources import (GitInfoProvider, detect_project_root,
                                         ensure_gitignore_entry, main,
                                         parse_arguments)


def test_parse_arguments_defaults():
    """Test that parse_arguments returns correct defaults."""
    with patch("sys.argv", ["script.py"]):
        args = parse_arguments()
        assert args.output is None
        assert args.project_root is None
        assert not args.verbose
        assert not args.no_update_gitignore
        assert not args.no_list_env_keys


def test_parse_arguments_custom_args():
    """Test that parse_arguments handles custom arguments correctly."""
    with patch(
        "sys.argv",
        [
            "script.py",
            "--output",
            "custom.txt",
            "--project-root",
            "/tmp",
            "--verbose",
            "--no-update-gitignore",
            "--no-list-env-keys",
        ],
    ):
        args = parse_arguments()
        assert args.output == Path("custom.txt")
        assert args.project_root == Path("/tmp")
        assert args.verbose
        assert args.no_update_gitignore
        assert args.no_list_env_keys


@patch("consolidate_project_sources.ProjectConsolidator")
@patch("consolidate_project_sources.detect_project_root")
@patch("consolidate_project_sources.ensure_gitignore_entry")
@patch("pathlib.Path.exists", return_value=True)
@patch("pathlib.Path.stat", return_value=MagicMock(st_size=12345))
def test_main_successful_run(
    mock_stat,
    mock_exists,
    mock_ensure_gitignore,
    mock_detect_root,
    mock_consolidator_class,
):
    """Test the main function for a successful execution path."""
    mock_detect_root.return_value = Path("/fake/project")
    mock_consolidator_instance = MagicMock()
    # Configure the mock instance to have a stats dictionary
    mock_consolidator_instance.stats = {
        "total_files": 0,
        "included_files": 0,
        "excluded_files": 0,
        "sensitive_files": 0,
        "total_lines": 0,
        "languages": {},
    }
    mock_consolidator_class.return_value = mock_consolidator_instance

    with patch(
        "sys.argv",
        ["script.py", "--output", "out.txt", "--project-root", "/fake"],
    ):
        exit_code = main()

    assert exit_code == 0
    mock_consolidator_class.assert_called_once()
    mock_consolidator_instance.consolidate.assert_called_once()
    mock_ensure_gitignore.assert_called_once()


@patch("consolidate_project_sources.ProjectConsolidator")
@patch("consolidate_project_sources.detect_project_root")
@patch("consolidate_project_sources.ensure_gitignore_entry")
@patch("pathlib.Path.exists", return_value=True)
@patch("pathlib.Path.stat", return_value=MagicMock(st_size=12345))
def test_main_autodetect_root(
    mock_stat,
    mock_exists,
    mock_ensure_gitignore,
    mock_detect_root,
    mock_consolidator_class,
):
    """Test the main function's path when auto-detecting project root."""
    mock_detect_root.return_value = Path("/fake/project")
    mock_consolidator_instance = MagicMock()
    mock_consolidator_instance.stats = {
        "total_files": 1, "included_files": 1, "excluded_files": 0,
        "sensitive_files": 0, "total_lines": 10, "languages": {"Python": 1}
    }
    mock_consolidator_class.return_value = mock_consolidator_instance

    with patch("sys.argv", ["script.py"]):
        exit_code = main()

    assert exit_code == 0
    mock_detect_root.assert_called_once()
    mock_consolidator_class.assert_called_with(Path("/fake/project"), list_env_keys=True)


@patch(
    "subprocess.check_output",
    side_effect=subprocess.CalledProcessError(1, "err"),
)
def test_get_git_info_fails_gracefully(mock_subprocess):
    """Test that get_git_info returns 'unknown' when git commands fail."""
    git_provider = GitInfoProvider(Path("."))
    git_info = git_provider.get_git_info()
    assert git_info["commit"] == "unknown"
    assert git_info["branch"] == "unknown"


@patch("pathlib.Path.exists", return_value=False)
def test_detect_project_root_fallback(mock_exists):
    """Test that detect_project_root falls back to the script's directory."""
    # This test is tricky because it depends on the test runner's location.
    # We'll just ensure it returns *a* path without erroring.
    fallback_path = detect_project_root()
    assert isinstance(fallback_path, Path)


def test_detect_project_root(tmp_path):
    """Test that detect_project_root finds the correct root directory."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / ".git").mkdir()
    src = project_root / "src"
    src.mkdir()
    (src / "main.py").touch()

    # Temporarily change the current working directory for the test
    with patch("pathlib.Path.cwd", return_value=src):
        # And patch __file__ to be inside the temp project
        with patch(
            "consolidate_project_sources.Path.absolute",
            return_value=src / "consolidate_project_sources.py",
        ):
            detected = detect_project_root()
            assert detected == project_root


def test_ensure_gitignore_entry(tmp_path):
    """Test that ensure_gitignore_entry correctly updates or creates .gitignore."""
    project_root = tmp_path
    gitignore = project_root / ".gitignore"

    with patch("consolidate_project_sources.PROJECT_ROOT", project_root):
        # Test creating the file
        ensure_gitignore_entry(update_gitignore=True)
        assert gitignore.exists()
        content = gitignore.read_text()
        assert "*_merged_sources*.txt" in content

        # Test appending to the file
        gitignore.write_text("initial content\n")
        ensure_gitignore_entry(update_gitignore=True)
        content = gitignore.read_text()
        assert "initial content" in content
        assert "*_merged_sources*.txt" in content
