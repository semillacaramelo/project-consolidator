"""
conftest.py: Centralized fixtures for tests.
"""
import subprocess
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture
def dummy_project(tmp_path: Path) -> Generator[Path, None, None]:
    """
    Creates a dummy project structure in a temporary directory, initializes it
    as a Git repository, and commits the files.
    Includes:
      - app.py
      - .env (sensitive)
      - README.md
      - node_modules/react.js (excluded dir)
      - .github/workflows/ci.yml
    """
    (tmp_path / "app.py").write_text('print("hello")')
    (tmp_path / ".env").write_text("SECRET=123")
    (tmp_path / "README.md").write_text("This is a test.")
    node_modules = tmp_path / "node_modules"
    node_modules.mkdir()
    (node_modules / "react.js").write_text("// react mock")
    github_wf = tmp_path / ".github" / "workflows"
    github_wf.mkdir(parents=True)
    (github_wf / "ci.yml").write_text("name: CI\n")

    # Initialize Git repo to make sure Git-related functions work
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"], cwd=tmp_path, check=True
    )

    yield tmp_path


@pytest.fixture
def consolidator_factory() -> Generator:
    """
    Returns a factory to create ProjectConsolidator instances.
    Imports the ProjectConsolidator from the package entry-point module.
    """
    from consolidate_project_sources import ProjectConsolidator

    def _factory(
        root_path: Path,
    ) -> "ProjectConsolidator":
        return ProjectConsolidator(root_path)

    yield _factory
