#!/usr/bin/env python3
"""
Project Source Code Consolidation Script
Consolidates all project source code into a single auditable text file.

Features:
- Excludes binaries, compiled files, dependencies, caches
- Includes metadata and file headers
- Handles sensitive files (existence check without content)
- Generates comprehensive project snapshot for auditing
- Version and timestamp-based output filename
"""

import argparse
import logging
import mimetypes
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Project root - dynamically determined
# Default to script's parent, but can be overridden.
PROJECT_ROOT = Path(__file__).parent.absolute()

# Output file pattern for gitignore
OUTPUT_FILE_PATTERN = "*_merged_sources*.txt"

# Exclude patterns (directories and files to skip)
# Note: Explicit list avoids accidentally excluding important dirs like .github
EXCLUDE_DIRS: Set[str] = {
    ".venv",
    "node_modules",
    "__pycache__",
    ".next",
    "venv",
    "env",
    ".git",
    ".vscode",
    ".idea",
    "dist",
    "build",
    "coverage",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".eggs",
    "postgres_data",
    "migrations/__pycache__",
    "playwright-report",
    "test-results",
    ".turbo",
    "temp",
    "tmp",
}

EXCLUDE_FILES: Set[str] = {
    ".DS_Store",
    "Thumbs.db",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "*.so",
    "*.dll",
    "*.dylib",
    "*.exe",
    "*.log",
    "*.pid",
    "*.seed",
    "*.pid.lock",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "*.min.js",
    "*.min.css",
    "*.map",
}

EXCLUDE_EXTENSIONS: Set[str] = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".so",
    ".dll",
    ".dylib",
    ".exe",
    ".o",
    ".a",
    ".lib",
    ".obj",
    ".class",
    ".jar",
    ".war",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".svg",
    ".webp",
    ".mp4",
    ".avi",
    ".mov",
    ".wmv",
    ".flv",
    ".webm",
    ".mp3",
    ".wav",
    ".ogg",
    ".flac",
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".7z",
    ".rar",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".otf",
    ".lock",
    ".map",
}

# Sensitive file patterns (check existence, don't include content)
SENSITIVE_PATTERNS: List[str] = [
    r"\.env(\.[a-z]+)?$",
    r".*\.key$",
    r".*\.pem$",
    r".*\.crt$",
    r".*\.cert$",
    r".*secrets.*",
    r".*credentials.*",
    r".*password.*",
]

# Files to always include even if binary
FORCE_INCLUDE_FILES: Set[str] = {
    "Dockerfile",
    "docker-compose.yml",
    ".dockerignore",
    ".gitignore",
    ".gitattributes",
    "requirements.txt",
    "package.json",
    "tsconfig.json",
    "README.md",
    "LICENSE",
    "CHANGELOG.md",
}

# Maximum file size to include (10,000,000 bytes = 10 MB approx)
# Use 10_000_000 to match test expectations
MAX_FILE_SIZE: int = 10_000_000


class ProjectConsolidator:
    """Consolidates project source code into a single auditable file."""

    def __init__(self, project_root: Path, list_env_keys: bool = True) -> None:
        """
        Initialize the consolidator.

        Args:
            project_root: Root directory of the project to consolidate
            list_env_keys: Whether to list environment variable keys in output
        """
        self.project_root = project_root
        self.list_env_keys = list_env_keys
        self.stats: Dict[str, int | Dict[str, int]] = {
            "total_files": 0,
            "included_files": 0,
            "excluded_files": 0,
            "sensitive_files": 0,
            "total_lines": 0,
            "languages": {},
        }
        self.file_tree: List[str] = []
        # Cache for file stats to avoid redundant stat() calls (Issue #3)
        self._file_stats_cache: Dict[Path, os.stat_result] = {}

    def _get_file_stat(self, file_path: Path) -> Optional[os.stat_result]:
        """
        Get file stat with caching to avoid redundant system calls.

        Args:
            file_path: Path to the file

        Returns:
            os.stat_result or None if stat fails
        """
        if file_path not in self._file_stats_cache:
            try:
                self._file_stats_cache[file_path] = file_path.stat()
            except OSError as e:
                logger.error(f"Error accessing {file_path}: {e}")
                return None
        return self._file_stats_cache[file_path]

    def is_excluded_dir(self, dir_name: str) -> bool:
        """
        Check if directory should be excluded.

        Note: Uses explicit exclusion list, not broad pattern matching,
        to avoid excluding important directories like .github, .devcontainer,
        etc.

        Args:
            dir_name: Name of the directory to check

        Returns:
            True if directory should be excluded, False otherwise
        """
        # FIXED: Removed overly broad .startswith(".") check (Issue #4)
        # Now only excludes directories explicitly listed in EXCLUDE_DIRS
        # Normalize to handle dot-prefixed virtualenv dirs like ".venv"
        normalized = dir_name.lstrip(".")
        return dir_name in EXCLUDE_DIRS or normalized in EXCLUDE_DIRS

    def is_excluded_file(
        self,
        file_path: Path,
        file_size: Optional[int] = None,
    ) -> bool:
        """
        Check if file should be excluded.

        Args:
            file_path: Path to the file to check
            file_size: Optional file size in bytes (to avoid redundant stat
                       calls)

        Returns:
            True if file should be excluded, False otherwise
        """
        # Allow callers to pass a string filename for convenience in tests
        if not isinstance(file_path, Path):
            file_path = Path(file_path)

        # CRITICAL FIX: Force include certain files FIRST (Issue #1)
        # This must be checked before size limits or other exclusions.
        if file_path.name in FORCE_INCLUDE_FILES:
            return False

        # Check extension
        if file_path.suffix.lower() in EXCLUDE_EXTENSIONS:
            return True

        # Check filename patterns
        for pattern in EXCLUDE_FILES:
            if "*" in pattern:
                regex = (
                    pattern.replace(".", r"\.")
                    .replace("*", ".*")
                )
                if re.match(regex, file_path.name):
                    return True
            elif file_path.name == pattern:
                return True

        # Check file size (use provided size to avoid redundant stat calls)
        if file_size is None:
            # Prefer os.path.getsize for monkeypatching in tests
            try:
                file_size = os.path.getsize(str(file_path))
            except OSError:
                try:
                    file_size = file_path.stat().st_size
                except OSError as e:
                    logger.error(f"Error accessing file {file_path}: {e}")
                    return True

        if file_size >= MAX_FILE_SIZE:
            log_msg = "File %s exceeds size limit (%s bytes), excluding"
            logger.warning(
                log_msg,
                file_path.relative_to(self.project_root),
                f"{file_size:,}",
            )
            return True

        # Check if binary
        if not self.is_text_file(file_path):
            return True

        return False

    @staticmethod
    def is_sensitive_file(file_path: Path | str) -> bool:
        """
        Check if file contains sensitive information.

        Args:
            file_path: Path to the file to check

        Returns:
            True if file is sensitive, False otherwise
        """
        # Accept either a Path or a string filename/path
        if not isinstance(file_path, Path):
            file_str = str(file_path)
        else:
            file_str = str(file_path)

        for pattern in SENSITIVE_PATTERNS:
            if re.search(pattern, file_str, re.IGNORECASE):
                return True
        return False

    def is_text_file(self, file_path: Path) -> bool:
        """
        Check if file is text (not binary).

        Args:
            file_path: Path to the file to check

        Returns:
            True if file is text, False otherwise
        """
        # Force include certain files
        if file_path.name in FORCE_INCLUDE_FILES:
            return True

        # Check by mime type
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type and mime_type.startswith("text"):
            return True

        # Check by extension
        text_extensions = {
            ".txt",
            ".md",
            ".rst",
            ".json",
            ".yaml",
            ".yml",
            ".toml",
            ".ini",
            ".cfg",
            ".conf",
            ".config",
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".css",
            ".scss",
            ".html",
            ".xml",
            ".sql",
            ".sh",
            ".bash",
            ".zsh",
            ".go",
            ".rs",
            ".java",
            ".c",
            ".cpp",
            ".h",
            ".hpp",
            ".rb",
            ".php",
            ".lua",
            ".pl",
            ".r",
            ".m",
            ".vim",
            ".el",
            ".clj",
            ".ex",
            ".exs",
            ".Dockerfile",
            ".gitignore",
            ".dockerignore",
        }
        if file_path.suffix.lower() in text_extensions:
            return True

        # Try to read as text
        try:
            with open(file_path, encoding="utf-8") as f:
                f.read(512)  # Read first 512 bytes
            return True
        except (OSError, UnicodeDecodeError):
            return False

    @staticmethod
    def get_file_language(file_path: Path | str) -> str:
        """
        Detect file language/type.

        Args:
            file_path: Path to the file

        Returns:
            Detected language/type as string
        """
        # Accept either a Path or string
        if not isinstance(file_path, Path):
            name = str(file_path)
            ext = Path(name).suffix.lower()
        else:
            ext = file_path.suffix.lower()
            name = file_path.name

        # Special-case known filenames
        if name == "Dockerfile":
            return "Docker"
        language_map = {
            ".py": "Python",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".jsx": "React JSX",
            ".tsx": "React TSX",
            ".css": "CSS",
            ".scss": "SCSS",
            ".html": "HTML",
            ".json": "JSON",
            ".yaml": "YAML",
            ".yml": "YAML",
            ".toml": "TOML",
            ".md": "Markdown",
            ".sql": "SQL",
            ".sh": "Shell",
            ".bash": "Bash",
            ".go": "Go",
            ".rs": "Rust",
            ".java": "Java",
            ".c": "C",
            ".cpp": "C++",
            ".h": "C Header",
            ".hpp": "C++ Header",
        }

        # Default to 'Text' for unknown text-like files
        return language_map.get(ext, "Text")

    def get_git_info(self) -> Dict[str, str]:
        """
        Get current git commit information.

        Returns:
            Dictionary with commit hash, date, and branch
        """
        try:
            commit_hash = subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=self.project_root,
                stderr=subprocess.PIPE,  # Capture errors for logging
                text=True,
            ).strip()

            commit_date = subprocess.check_output(
                ["git", "log", "-1", "--format=%cd", "--date=iso"],
                cwd=self.project_root,
                stderr=subprocess.PIPE,
                text=True,
            ).strip()

            branch = subprocess.check_output(
                ["git", "branch", "--show-current"],
                cwd=self.project_root,
                stderr=subprocess.PIPE,
                text=True,
            ).strip()

            return {
                "commit": commit_hash[:8],
                "date": commit_date,
                "branch": branch,
            }
        except subprocess.CalledProcessError as e:
            if e.stderr:
                stderr = e.stderr.strip()
            else:
                stderr = "No error details"
            logger.warning(f"Git command failed: {stderr}")
            return {
                "commit": "unknown",
                "date": "unknown",
                "branch": "unknown",
            }
        except FileNotFoundError:
            logger.warning(
                "Git executable not found. Please ensure git is installed."
            )
            return {
                "commit": "unknown",
                "date": "unknown",
                "branch": "unknown",
            }

    def analyze_sensitive_file(
        self,
        file_path: Path,
        list_env_keys: bool = True,
    ) -> Dict[str, str | int | List[str] | bool]:
        """
        Analyze sensitive file without exposing content.

        Args:
            file_path: Path to the sensitive file
            list_env_keys: Whether to list environment variable keys (default: True)

        Returns:
            Dictionary with file metadata
        """
        info = {
            "exists": True,
            "size": file_path.stat().st_size,
            "type": self.get_file_language(file_path),
        }

        # For .env files, optionally list keys without values
        # SECURITY NOTE: Key names can be sensitive (Issue #5)
        if file_path.name.startswith(".env") and self.list_env_keys:
            try:
                with open(file_path, encoding="utf-8") as f:
                    lines = f.readlines()

                keys = []
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key = line.split("=")[0].strip()
                        # Redact middle portion of key name for security
                        if len(key) > 8:
                            redacted = f"{key[:4]}...{key[-2:]}={{Exists}}"
                        else:
                            redacted = f"{key}={{Exists}}"
                        keys.append(redacted)

                info["keys"] = keys
            except OSError as e:
                logger.error(f"Error reading sensitive file {file_path}: {e}")
                info["keys"] = ["<Unable to read>"]

        return info

    def build_file_tree(
        self, directory: Path, prefix: str = "", is_last: bool = True
    ) -> List[str]:
        """
        Build a visual tree structure of the project.

        Args:
            directory: Directory to build tree from
            prefix: Current line prefix for tree formatting
            is_last: Whether this is the last item in current level

        Returns:
            List of tree lines
        """
        tree_lines = []

        try:
            items = sorted(
                directory.iterdir(), key=lambda x: (not x.is_dir(), x.name)
            )
            items = [
                item for item in items if not self.is_excluded_dir(item.name)
            ]

            for i, item in enumerate(items):
                is_last_item = i == len(items) - 1

                # Tree characters
                connector = "└── " if is_last_item else "├── "
                extension = "    " if is_last_item else "│   "

                # Add item
                if item.is_dir():
                    tree_lines.append(f"{prefix}{connector}{item.name}/")
                    # Recurse into directory
                    sub_tree = self.build_file_tree(
                        item, prefix + extension, is_last_item
                    )
                    tree_lines.extend(sub_tree)
                elif not self.is_excluded_file(item):
                    tree_lines.append(f"{prefix}{connector}{item.name}")
        except PermissionError as e:
            logger.warning(f"Permission denied accessing {directory}: {e}")

        return tree_lines

    def consolidate(self, output_file: Path) -> None:
        """
        Consolidate all project files into output file.

        Args:
            output_file: Path where consolidated output will be written
        """
        logger.info("Starting project consolidation...")
        logger.info(f"Project: {self.project_root}")
        logger.info(f"Output:  {output_file}")

        git_info = self.get_git_info()
        timestamp = datetime.now()

        try:
            # Store the output file path so it can be excluded during processing
            try:
                self._output_file = output_file.resolve()
            except Exception:
                # Fallback to the raw path if resolve() fails
                self._output_file = output_file

            with open(output_file, "w", encoding="utf-8") as out:
                # Write header
                self._write_header(out, timestamp, git_info)

                # Write file tree
                self._write_file_tree(out)

                # Walk through project
                self._process_files(out)

                # Write statistics
                self._write_statistics(out, timestamp)

            logger.info("Consolidation complete!")
            logger.info(f"Output file: {output_file}")
            logger.info(f"Total files processed: {self.stats['total_files']}")
            logger.info(f"Files included: {self.stats['included_files']}")
            logger.info(f"Total lines: {self.stats['total_lines']:,}")

        except OSError as e:
            logger.error(f"Error writing to output file {output_file}: {e}")
            raise

    def _write_header(
        self, out, timestamp: datetime, git_info: Dict[str, str]
    ) -> None:
        """Write file header."""
        out.write("=" * 80 + "\n")
        out.write("PROJECT SOURCE CODE CONSOLIDATION\n")
        out.write("=" * 80 + "\n\n")

        out.write("Project:          Talos Algo AI\n")
        time_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
        out.write(f"Consolidation:    {time_str}\n")
        out.write(f"Git Commit:       {git_info['commit']}\n")
        out.write(f"Git Branch:       {git_info['branch']}\n")
        out.write(f"Commit Date:      {git_info['date']}\n")
        out.write(f"Project Root:     {self.project_root}\n")

        out.write("\n" + "=" * 80 + "\n")
        out.write("PURPOSE\n")
        out.write("=" * 80 + "\n\n")
        out.write(
            "This file contains a complete consolidation of the project "
            "source code,\nconfiguration files, and documentation for "
            "auditing and reproduction purposes.\n"
        )
        out.write("\n")
        out.write("Exclusions:\n")
        out.write(
            "  - Binary files (images, compiled code, executables)\n"
        )
        out.write("  - Dependencies (node_modules, venv, etc.)\n")
        out.write("  - Generated files (.next, dist, build)\n")
        out.write("  - Cache and temporary files\n")
        out.write("  - Large files (> 10 MB)\n")
        out.write("\n")
        out.write(
            "Sensitive files are listed with metadata but content is not included.\n"
        )
        out.write("\n")

    def _write_file_tree(self, out) -> None:
        """Write project file tree."""
        out.write("=" * 80 + "\n")
        out.write("PROJECT STRUCTURE\n")
        out.write("=" * 80 + "\n\n")

        tree_lines = self.build_file_tree(self.project_root)
        out.write(f"{self.project_root.name}/\n")
        for line in tree_lines:
            out.write(line + "\n")

        out.write("\n")

    def _process_files(self, out) -> None:
        """Process and write all files."""
        out.write("=" * 80 + "\n")
        out.write("SOURCE FILES\n")
        out.write("=" * 80 + "\n\n")

        for root, dirs, files in os.walk(self.project_root):
            # Filter out excluded directories
            dirs[:] = [d for d in dirs if not self.is_excluded_dir(d)]

            root_path = Path(root)

            for file in sorted(files):
                file_path = root_path / file

                # Skip the consolidation script itself and output files
                if file_path.name == Path(__file__).name:
                    continue
                # Skip any previously written consolidated output file
                try:
                    is_output_file = (
                        hasattr(self, "_output_file")
                        and file_path.resolve() == self._output_file
                    )
                    if is_output_file:
                        continue
                except Exception:
                    # If resolve fails for any reason, fall back to
                    # name-based pattern
                    pattern = r".*_merged_sources.*\.txt$"
                    if re.match(pattern, file_path.name):
                        continue

                self.stats["total_files"] += 1

                # Get file stat once and cache it (Issue #3 fix)
                file_stat = self._get_file_stat(file_path)
                if file_stat is None:
                    self.stats["excluded_files"] += 1
                    continue

                file_size = file_stat.st_size

                # Check if excluded (passing file_size to avoid redundant stat)
                if self.is_excluded_file(file_path, file_size):
                    self.stats["excluded_files"] += 1
                    continue

                # Check if sensitive
                if self.is_sensitive_file(file_path):
                    # Write metadata for sensitive files but do not include content
                    # and avoid inflating included file numbers.
                    self._write_sensitive_file(out, file_path, file_stat)
                    self.stats["sensitive_files"] += 1
                    continue

                # Write regular file
                self._write_regular_file(out, file_path, file_stat)
                self.stats["included_files"] += 1

        logger.info(f"Processed {self.stats['total_files']} files")

    def _write_sensitive_file(
        self, out, file_path: Path, file_stat: os.stat_result
    ) -> None:
        """Write sensitive file metadata without content."""
        rel_path = file_path.relative_to(self.project_root)

        out.write("\n" + "-" * 80 + "\n")
        out.write(f"FILE: {rel_path}\n")
        out.write("-" * 80 + "\n")
        out.write("Type:      SENSITIVE (content not included)\n")
        out.write(f"Location:  {rel_path}\n")
        out.write(f"Size:      {file_stat.st_size} bytes\n")
        out.write(f"Language:  {self.get_file_language(file_path)}\n")

        # Analyze sensitive file
        info = self.analyze_sensitive_file(file_path, self.list_env_keys)

        if "keys" in info:
            out.write("\nEnvironment Variables:\n")
            for key in info["keys"]:
                out.write(f"  {key}\n")

        out.write("\nNOTE: This is a sensitive file. ")
        out.write("Content is not included for security.\n")
        out.write(
            "      The file exists and should be " "configured separately.\n"
        )
        out.write("\n")

        logger.info(f"🔒 Sensitive: {rel_path}")

    def _write_regular_file(
        self, out, file_path: Path, file_stat: os.stat_result
    ) -> None:
        """Write regular file with content."""
        rel_path = file_path.relative_to(self.project_root)
        language = self.get_file_language(file_path)

        # Update language statistics
        lang_stats = self.stats["languages"]
        lang_stats[language] = lang_stats.get(language, 0) + 1

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            lines = content.split("\n")
            line_count = len(lines)
            self.stats["total_lines"] += line_count

            out.write("\n" + "-" * 80 + "\n")
            out.write(f"FILE: {rel_path}\n")
            out.write("-" * 80 + "\n")
            out.write(f"Location:   {rel_path}\n")
            out.write(f"Language:   {language}\n")
            out.write(f"Lines:      {line_count}\n")
            out.write(f"Size:       {file_stat.st_size} bytes\n")
            out.write("-" * 80 + "\n\n")

            out.write(content)

            if not content.endswith("\n"):
                out.write("\n")

            out.write("\n")

            logger.debug(f"✓ Included: {rel_path} ({line_count} lines)")

        except Exception as e:
            out.write(f"\nERROR: Unable to read file: {e}\n\n")
            logger.error(f"✗ Error reading {rel_path}: {e}")

    def _write_statistics(self, out, timestamp: datetime) -> None:
        """Write consolidation statistics."""
        out.write("=" * 80 + "\n")
        out.write("CONSOLIDATION STATISTICS\n")
        out.write("=" * 80 + "\n\n")

        out.write(
            f"Completion Time: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
        )
        out.write(f"Total Files Scanned: {self.stats['total_files']}\n")
        out.write(f"Files Included: {self.stats['included_files']}\n")
        out.write(f"Files Excluded: {self.stats['excluded_files']}\n")
        out.write(f"Sensitive Files: {self.stats['sensitive_files']}\n")
        out.write(f"Total Lines of Code: {self.stats['total_lines']:,}\n")
        out.write("\n")

        out.write("Language Distribution:\n")
        sorted_langs = sorted(
            self.stats["languages"].items(), key=lambda x: x[1], reverse=True
        )
        for lang, count in sorted_langs:
            out.write(f"  {lang:20s} {count:4d} files\n")

        out.write("\n")
        out.write("=" * 80 + "\n")
        out.write("END OF CONSOLIDATION\n")
        out.write("=" * 80 + "\n")


def ensure_gitignore_entry(update_gitignore: bool = True) -> None:
    """
    Ensure the output file pattern is in .gitignore.
    Creates .gitignore if it doesn't exist.

    Args:
        update_gitignore: Whether to actually update the gitignore (default: True)
    """
    if not update_gitignore:
        logger.debug("Skipping .gitignore update (disabled by user)")
        return

    gitignore_path = PROJECT_ROOT / ".gitignore"

    try:
        # Read existing .gitignore content
        if gitignore_path.exists():
            with open(gitignore_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Check if pattern already exists
            if OUTPUT_FILE_PATTERN in content:
                logger.debug(
                    f".gitignore already contains {OUTPUT_FILE_PATTERN}"
                )
                return

            # Append pattern
            with open(gitignore_path, "a", encoding="utf-8") as f:
                if not content.endswith("\n"):
                    f.write("\n")
                f.write("\n# Exclude consolidated source files\n")
                f.write(f"{OUTPUT_FILE_PATTERN}\n")

            logger.info(f"Added {OUTPUT_FILE_PATTERN} to .gitignore")
        else:
            # Create new .gitignore
            with open(gitignore_path, "w", encoding="utf-8") as f:
                f.write("# Exclude consolidated source files\n")
                f.write(f"{OUTPUT_FILE_PATTERN}\n")

            logger.info(f"Created .gitignore with {OUTPUT_FILE_PATTERN}")

    except OSError as e:
        logger.warning(f"Could not update .gitignore: {e}")


def detect_project_root() -> Path:
    """
    Detect the project root directory by looking for common markers.

    Returns:
        Path to detected project root, or script directory as fallback
    """
    current = Path(__file__).parent.absolute()

    # Common project root markers
    root_markers = {
        ".git",
        "package.json",
        "requirements.txt",
        "pyproject.toml",
        "setup.py",
        "Cargo.toml",
        "go.mod",
        ".gitignore",
    }

    # Walk up the directory tree looking for markers
    max_depth = 5
    for _ in range(max_depth):
        # Check if any marker exists in current directory
        for marker in root_markers:
            if (current / marker).exists():
                logger.debug(f"Detected project root via {marker}: {current}")
                return current

        # Move up one level
        parent = current.parent
        if parent == current:  # Reached filesystem root
            break
        current = parent

    # Fallback to script directory
    fallback = Path(__file__).parent.absolute()
    logger.debug(
        f"No project root markers found, using script directory: {fallback}"
    )
    return fallback


def parse_arguments() -> argparse.Namespace:
    """
    Parse command line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Consolidate project source code into a single file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Run with defaults
  %(prog)s --output custom.txt      # Specify custom output file
  %(prog)s --verbose                # Enable verbose logging
  %(prog)s --project-root /path     # Specify project root directory
        """,
    )

    parser.add_argument(
        "--output",
        type=Path,
        help="Output file path (default: auto-generated with timestamp)",
        metavar="FILE",
    )

    parser.add_argument(
        "--project-root",
        type=Path,
        help="Project root directory (default: auto-detect or script directory)",
        metavar="DIR",
    )

    parser.add_argument(
        "--verbose", action="store_true", help="Enable verbose output"
    )

    parser.add_argument(
        "--no-update-gitignore",
        action="store_true",
        help="Don't automatically update .gitignore (Issue #6)",
    )

    parser.add_argument(
        "--no-list-env-keys",
        action="store_true",
        help="Don't list .env file keys (more secure)",
    )

    parser.add_argument(
        "--max-file-size",
        type=int,
        default=MAX_FILE_SIZE,
        help=(
            "Maximum file size to include in bytes "
            f"(default: {MAX_FILE_SIZE:,})"
        ),
        metavar="BYTES",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 2.1 (with audit fixes)",
    )

    return parser.parse_args()


def main() -> int:
    """
    Main execution function.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Parse arguments
    args = parse_arguments()

    # Configure logging level
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Determine project root
    if args.project_root:
        project_root = args.project_root.absolute()
    else:
        project_root = detect_project_root()

    # Validate project root exists
    if not project_root.exists():
        logger.error(f"Project root does not exist: {project_root}")
        return 1

    # Generate output filename if not provided
    if args.output:
        output_path = args.output
    else:
        timestamp = datetime.now()
        project_name = project_root.name.replace(" ", "_").lower()
        date_str = timestamp.strftime("%Y%m%d_%H%M")
        output_filename = f"{project_name}_{date_str}_merged_sources.txt"
        output_path = project_root / output_filename

    logger.info("=" * 80)
    logger.info("PROJECT SOURCE CONSOLIDATION TOOL")
    logger.info("=" * 80)

    # Update max file size if provided (Issue #7)
    global MAX_FILE_SIZE
    if args.max_file_size != MAX_FILE_SIZE:
        MAX_FILE_SIZE = args.max_file_size
        logger.info(f"Using custom max file size: {MAX_FILE_SIZE:,} bytes")

    # Ensure gitignore contains output pattern (unless disabled)
    ensure_gitignore_entry(update_gitignore=not args.no_update_gitignore)

    # Create consolidator with options
    consolidator = ProjectConsolidator(
        project_root, list_env_keys=not args.no_list_env_keys
    )

    # Run consolidation
    try:
        consolidator.consolidate(output_path)

        # Print summary
        logger.info("=" * 80)
        logger.info("CONSOLIDATION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Output File:        {output_path}")
        logger.info(
            f"File Size:          " f"{output_path.stat().st_size:,} bytes"
        )
        logger.info(f"Total Files:        {consolidator.stats['total_files']}")
        logger.info(
            f"Included:           {consolidator.stats['included_files']}"
        )
        logger.info(
            f"Excluded:           {consolidator.stats['excluded_files']}"
        )
        logger.info(
            f"Sensitive:          {consolidator.stats['sensitive_files']}"
        )
        logger.info(
            f"Total Lines:        {consolidator.stats['total_lines']:,}"
        )

        logger.info("\nTop Languages:")
        sorted_langs = sorted(
            consolidator.stats["languages"].items(),
            key=lambda x: x[1],
            reverse=True,
        )[:5]
        for lang, count in sorted_langs:
            logger.info(f"  {lang:20s} {count:4d} files")

        logger.info("\n✅ Consolidation completed successfully!")
        return 0

    except Exception as e:
        logger.exception("Error during consolidation: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
