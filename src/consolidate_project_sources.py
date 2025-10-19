#!/usr/bin/env python3
"""
Project Source Code Consolidation Script
"""
import argparse
import fnmatch
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
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.absolute()
OUTPUT_FILE_PATTERN = "*_merged_sources*.txt"
OUTPUT_FILE_REGEX = re.compile(fnmatch.translate(OUTPUT_FILE_PATTERN))

EXCLUDE_DIRS: Set[str] = {
    # Python
    "venv", ".venv", "env", "ENV", "env.bak", "venv.bak", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".eggs",

    # Node
    "node_modules", ".next",

    # General
    ".git", ".vscode", ".idea", "dist", "build", "coverage", "postgres_data",
    "migrations/__pycache__", "playwright-report", "test-results", ".turbo",
    "temp", "tmp",
}
EXCLUDE_FILES: Set[str] = {
    ".DS_Store", "Thumbs.db", "*.pyc", "*.pyo", "*.pyd", "*.so", "*.dll",
    "*.dylib", "*.exe", "*.log", "*.pid", "*.seed", "*.pid.lock",
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "*.min.js",
    "*.min.css", "*.map",
}
EXCLUDE_EXTENSIONS: Set[str] = {
    ".pyc", ".pyo", ".pyd", ".so", ".dll", ".dylib", ".exe", ".o", ".a", ".lib",
    ".obj", ".class", ".jar", ".war", ".png", ".jpg", ".jpeg", ".gif", ".ico",
    ".svg", ".webp", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm", ".mp3",
    ".wav", ".ogg", ".flac", ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".woff", ".woff2", ".ttf",
    ".eot", ".otf", ".lock", ".map",
}
SENSITIVE_PATTERNS: List[str] = [
    r"\.env(\.[a-z]+)?$", r".*\.key$", r".*\.pem$", r".*\.crt$", r".*\.cert$",
    r".*secrets.*", r".*credentials.*", r".*password.*",
]
FORCE_INCLUDE_FILES: Set[str] = {
    "Dockerfile", "docker-compose.yml", ".dockerignore", ".gitignore",
    ".gitattributes", "requirements.txt", "package.json", "tsconfig.json",
    "README.md", "LICENSE", "CHANGELOG.md",
}
MAX_FILE_SIZE: int = 10_000_000

TEXT_EXTENSIONS = {
    ".txt", ".md", ".rst", ".json", ".yaml", ".yml", ".toml", ".ini",
    ".cfg", ".conf", ".config", ".py", ".js", ".ts", ".jsx", ".tsx",
    ".css", ".scss", ".html", ".xml", ".sql", ".sh", ".bash", ".zsh",
    ".go", ".rs", ".java", ".c", ".cpp", ".h", ".hpp", ".rb", ".php",
    ".lua", ".pl", ".r", ".m", ".vim", ".el", ".clj", ".ex", ".exs",
    ".Dockerfile", ".gitignore", ".dockerignore",
}
LANGUAGE_MAP = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
    ".jsx": "React JSX", ".tsx": "React TSX", ".css": "CSS", ".scss": "SCSS",
    ".html": "HTML", ".json": "JSON", ".yaml": "YAML", ".yml": "YAML",
    ".toml": "TOML", ".md": "Markdown", ".sql": "SQL", ".sh": "Shell",
    ".bash": "Bash", ".go": "Go", ".rs": "Rust", ".java": "Java",
    ".c": "C", ".cpp": "C++", ".h": "C Header", ".hpp": "C++ Header",
}

class GitInfoProvider:
    def __init__(self, project_root: Path):
        self.project_root = project_root

    def get_git_info(self) -> Dict[str, str]:
        try:
            commit_hash = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.project_root, stderr=subprocess.PIPE, text=True).strip()
            commit_date = subprocess.check_output(["git", "log", "-1", "--format=%cd", "--date=iso"], cwd=self.project_root, stderr=subprocess.PIPE, text=True).strip()
            branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=self.project_root, stderr=subprocess.PIPE, text=True).strip()
            return {"commit": commit_hash[:8], "date": commit_date, "branch": branch}
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.warning(f"Git command failed: {e}")
            return {"commit": "unknown", "date": "unknown", "branch": "unknown"}

class FileWalker:
    def __init__(self, project_root: Path):
        self.project_root = project_root

    def is_excluded_dir(self, dir_name: str) -> bool:
        return dir_name in EXCLUDE_DIRS

    def is_excluded_file(self, file_path: Path, file_size: Optional[int] = None) -> bool:
        if file_path.name in FORCE_INCLUDE_FILES:
            return False
        if file_path.suffix.lower() in EXCLUDE_EXTENSIONS:
            return True
        for pattern in EXCLUDE_FILES:
            if fnmatch.fnmatch(file_path.name, pattern):
                return True
        if file_size is None:
            try:
                file_size = file_path.stat().st_size
            except OSError as e:
                logger.error(f"Error accessing file {file_path}: {e}")
                return True
        if file_size >= MAX_FILE_SIZE:
            logger.warning(f"File {file_path.relative_to(self.project_root)} exceeds size limit, excluding")
            return True
        if not self.is_text_file(file_path):
            return True
        return False

    def is_text_file(self, file_path: Path) -> bool:
        if file_path.name in FORCE_INCLUDE_FILES:
            return True
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type and mime_type.startswith("text"):
            return True
        if file_path.suffix.lower() in TEXT_EXTENSIONS:
            return True
        try:
            with open(file_path, encoding="utf-8") as f:
                f.read(512)
            return True
        except (OSError, UnicodeDecodeError):
            return False

    @staticmethod
    def get_file_language(file_path: Path | str) -> str:
        name = file_path.name if isinstance(file_path, Path) else Path(file_path).name
        ext = Path(name).suffix.lower()
        if name == "Dockerfile":
            return "Docker"
        return LANGUAGE_MAP.get(ext, "Text")

    def build_file_tree(self, directory: Path, prefix: str = "") -> List[str]:
        tree_lines = []
        try:
            items = sorted(directory.iterdir(), key=lambda x: (not x.is_dir(), x.name))
            items = [item for item in items if not self.is_excluded_dir(item.name)]
            for i, item in enumerate(items):
                connector = "└── " if i == len(items) - 1 else "├── "
                if item.is_dir():
                    tree_lines.append(f"{prefix}{connector}{item.name}/")
                    extension = "    " if i == len(items) - 1 else "│   "
                    tree_lines.extend(self.build_file_tree(item, prefix + extension))
                elif not self.is_excluded_file(item):
                    tree_lines.append(f"{prefix}{connector}{item.name}")
        except PermissionError as e:
            logger.warning(f"Permission denied accessing {directory}: {e}")
        return tree_lines

class ReportGenerator:
    def __init__(self, project_root: Path):
        self.project_root = project_root

    def write_header(self, out, timestamp: datetime, git_info: Dict[str, str]):
        out.write("=" * 80 + "\nPROJECT SOURCE CODE CONSOLIDATION\n" + "=" * 80 + "\n\n")
        out.write(f"Project:          Talos Algo AI\n")
        out.write(f"Consolidation:    {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n")
        out.write(f"Git Commit:       {git_info['commit']}\n")
        out.write(f"Git Branch:       {git_info['branch']}\n")
        out.write(f"Commit Date:      {git_info['date']}\n")
        out.write(f"Project Root:     {self.project_root}\n\n")

    def write_file_tree(self, out, tree_lines: List[str]):
        out.write("=" * 80 + "\nPROJECT STRUCTURE\n" + "=" * 80 + "\n\n")
        out.write(f"{self.project_root.name}/\n")
        for line in tree_lines:
            out.write(line + "\n")
        out.write("\n")

    def write_source_files_header(self, out):
        out.write("=" * 80 + "\nSOURCE FILES\n" + "=" * 80 + "\n\n")

    def write_sensitive_file(self, out, file_path: Path, file_stat: os.stat_result, info: Dict, language: str):
        rel_path = file_path.relative_to(self.project_root)
        out.write(f"\n" + "-" * 80 + f"\nFILE: {rel_path}\n" + "-" * 80 + "\n")
        out.write(f"Type:      SENSITIVE (content not included)\n")
        out.write(f"Location:  {rel_path}\nSize:      {file_stat.st_size} bytes\nLanguage:  {language}\n")
        if "keys" in info:
            out.write("\nEnvironment Variables:\n")
            for key in info["keys"]:
                out.write(f"  {key}\n")
        out.write("\nNOTE: This is a sensitive file. Content is not included for security.\n\n")

    def write_regular_file(self, out, file_path: Path, file_stat: os.stat_result, content: str, line_count: int, language: str):
        rel_path = file_path.relative_to(self.project_root)
        out.write(f"\n" + "-" * 80 + f"\nFILE: {rel_path}\n" + "-" * 80 + "\n")
        out.write(f"Location:   {rel_path}\nLanguage:   {language}\nLines:      {line_count}\nSize:       {file_stat.st_size} bytes\n" + "-" * 80 + "\n\n")
        out.write(content)
        if not content.endswith("\n"):
            out.write("\n")
        out.write("\n")

    def write_statistics(self, out, timestamp: datetime, stats: Dict):
        out.write("=" * 80 + "\nCONSOLIDATION STATISTICS\n" + "=" * 80 + "\n\n")
        out.write(f"Completion Time: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n")
        for key, value in stats.items():
            if key != "languages":
                out.write(f"{key.replace('_', ' ').title()}: {value}\n")
        out.write("\nLanguage Distribution:\n")
        sorted_langs = sorted(stats["languages"].items(), key=lambda x: x[1], reverse=True)
        for lang, count in sorted_langs:
            out.write(f"  {lang:20s} {count:4d} files\n")
        out.write("\n" + "=" * 80 + "\nEND OF CONSOLIDATION\n" + "=" * 80 + "\n")

class ProjectConsolidator:
    def __init__(self, project_root: Path, list_env_keys: bool = True):
        self.project_root = project_root
        self.list_env_keys = list_env_keys
        self.stats = {"total_files": 0, "included_files": 0, "excluded_files": 0, "sensitive_files": 0, "total_lines": 0, "languages": {}}
        self._file_stats_cache: Dict[Path, os.stat_result] = {}
        self._output_file: Optional[Path] = None
        self.git_info_provider = GitInfoProvider(project_root)
        self.file_walker = FileWalker(project_root)
        self.report_generator = ReportGenerator(project_root)

    def _get_file_stat(self, file_path: Path) -> Optional[os.stat_result]:
        if file_path not in self._file_stats_cache:
            try:
                self._file_stats_cache[file_path] = file_path.stat()
            except OSError as e:
                logger.error(f"Error accessing {file_path}: {e}")
                return None
        return self._file_stats_cache[file_path]

    @staticmethod
    def is_sensitive_file(file_path: Path | str) -> bool:
        file_str = str(file_path)
        return any(re.search(pattern, file_str, re.IGNORECASE) for pattern in SENSITIVE_PATTERNS)

    def analyze_sensitive_file(self, file_path: Path) -> Dict:
        info = {"exists": True, "size": file_path.stat().st_size, "type": self.file_walker.get_file_language(file_path)}
        if self.list_env_keys and file_path.name.startswith(".env"):
            try:
                with open(file_path, encoding="utf-8") as f:
                    keys = [line.split("=")[0].strip() for line in f if line.strip() and not line.startswith("#") and "=" in line]
                    info["keys"] = [f"{key[:4]}...{key[-2:]}=<REDACTED>" if len(key) > 8 else f"{key}=<REDACTED>" for key in keys]
            except OSError as e:
                logger.error(f"Error reading sensitive file {file_path}: {e}")
                info["keys"] = ["<Unable to read>"]
        return info

    def consolidate(self, output_file: Path):
        logger.info(f"Starting project consolidation for: {self.project_root}")
        self._output_file = output_file.resolve()
        git_info = self.git_info_provider.get_git_info()
        timestamp = datetime.now()

        with open(output_file, "w", encoding="utf-8") as out:
            self.report_generator.write_header(out, timestamp, git_info)
            tree_lines = self.file_walker.build_file_tree(self.project_root)
            self.report_generator.write_file_tree(out, tree_lines)
            self.report_generator.write_source_files_header(out)
            self._process_files(out)
            self.report_generator.write_statistics(out, timestamp, self.stats)
        logger.info(f"Consolidation complete: {output_file}")

    def _process_files(self, out):
        for root, dirs, files in os.walk(self.project_root):
            dirs[:] = [d for d in dirs if not self.file_walker.is_excluded_dir(d)]
            for file in sorted(files):
                file_path = Path(root) / file
                if file_path == self._output_file or OUTPUT_FILE_REGEX.match(file_path.name) or file_path.name == Path(__file__).name:
                    continue

                self.stats["total_files"] += 1
                file_stat = self._get_file_stat(file_path)
                if not file_stat:
                    self.stats["excluded_files"] += 1
                    continue

                if self.file_walker.is_excluded_file(file_path, file_stat.st_size):
                    self.stats["excluded_files"] += 1
                    continue

                language = self.file_walker.get_file_language(file_path)
                if self.is_sensitive_file(file_path):
                    self.stats["sensitive_files"] += 1
                    info = self.analyze_sensitive_file(file_path)
                    self.report_generator.write_sensitive_file(out, file_path, file_stat, info, language)
                    continue

                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    line_count = len(content.splitlines())
                    self.stats["total_lines"] += line_count
                    self.stats["included_files"] += 1
                    self.stats["languages"][language] = self.stats["languages"].get(language, 0) + 1
                    self.report_generator.write_regular_file(out, file_path, file_stat, content, line_count, language)
                except (OSError, UnicodeDecodeError) as e:
                    logger.error(f"Error reading {file_path.relative_to(self.project_root)}: {e}")
                    self.stats["excluded_files"] += 1

def ensure_gitignore_entry(project_root: Path, update_gitignore: bool = True):
    if not update_gitignore: return
    gitignore_path = project_root / ".gitignore"
    try:
        content = gitignore_path.read_text() if gitignore_path.exists() else ""
        if OUTPUT_FILE_PATTERN not in content:
            with open(gitignore_path, "a", encoding="utf-8") as f:
                f.write(f"\n# Exclude consolidated source files\n{OUTPUT_FILE_PATTERN}\n")
            logger.info(f"Added {OUTPUT_FILE_PATTERN} to .gitignore")
    except OSError as e:
        logger.warning(f"Could not update .gitignore: {e}")

def detect_project_root() -> Path:
    """
    Detects the project root by searching upwards from the script's location
    for common project markers.
    """
    current = Path(__file__).parent.absolute()
    root_markers = {".git", "pyproject.toml", "requirements.txt", ".gitignore"}

    # Traverse up until the filesystem root
    while current.parent != current:
        if any((current / marker).exists() for marker in root_markers):
            logger.debug(f"Project root detected at: {current}")
            return current
        current = current.parent

    # If no root is found, return the script's directory as a fallback
    fallback_path = Path(__file__).parent.absolute()
    logger.debug(f"No project root markers found. Falling back to {fallback_path}")
    return fallback_path

def parse_arguments():
    parser = argparse.ArgumentParser(description="Consolidate project source code.")
    parser.add_argument("--output", type=Path, help="Output file path.")
    parser.add_argument("--project-root", type=Path, help="Project root directory.")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output.")
    parser.add_argument("--no-update-gitignore", action="store_true", help="Don't update .gitignore.")
    parser.add_argument("--no-list-env-keys", action="store_true", help="Don't list .env file keys.")
    return parser.parse_args()

def main():
    args = parse_arguments()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    project_root = args.project_root.absolute() if args.project_root else detect_project_root()
    if not project_root.exists():
        logger.error(f"Project root does not exist: {project_root}")
        return 1

    output_path = args.output or project_root / f"{project_root.name}_{datetime.now().strftime('%Y%m%d_%H%M')}_merged_sources.txt"

    ensure_gitignore_entry(project_root, not args.no_update_gitignore)

    consolidator = ProjectConsolidator(project_root, list_env_keys=not args.no_list_env_keys)
    consolidator.consolidate(output_path)
    return 0

if __name__ == "__main__":
    sys.exit(main())
