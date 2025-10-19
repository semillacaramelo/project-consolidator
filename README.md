# Project Consolidator

Professional Python CLI tool for consolidating project source code into a single auditable file.

## Features

- 🔍 Smart project root detection
- 📁 Excludes binaries, dependencies, caches
- 🔒 Secure handling of sensitive files (.env)
- 📊 Detailed statistics and file tree
- ⚡ Performance optimized with stat caching
- 🎯 Type-hinted and well-documented
- 🛡️ Security-first (key redaction)

## Quick Start

```bash
# Basic usage
python3 consolidate_project_sources.py

# With options
python3 consolidate_project_sources.py --verbose --no-list-env-keys
```

## Installation

```bash
git clone https://github.com/semillacaramelo/project-consolidator.git
cd project-consolidator
python3 -m pip install -r requirements-dev.txt  # For testing
```

## Usage

```bash
# Auto-detect project root
python3 consolidate_project_sources.py

# Specify project root
python3 consolidate_project_sources.py --project-root /path/to/project

# Custom output file
python3 consolidate_project_sources.py --output backup.txt

# Security options
python3 consolidate_project_sources.py --no-list-env-keys --no-update-gitignore

# Custom file size limit (50MB)
python3 consolidate_project_sources.py --max-file-size 52428800
```

## Command-Line Options

| Flag | Description | Default |
|------|-------------|---------|
| `--output FILE` | Output file path | Auto-generated |
| `--project-root DIR` | Project directory | Auto-detect |
| `--verbose` | Enable debug logging | Off |
| `--no-update-gitignore` | Skip .gitignore update | Updates |
| `--no-list-env-keys` | Hide env var keys | Shows (redacted) |
| `--max-file-size BYTES` | Max file size | 10MB |

## Output Structure

```
================================================================================
PROJECT SOURCE CODE CONSOLIDATION
================================================================================
- Metadata (timestamp, git info, statistics)
- Project file tree
- Source files with headers
- Sensitive files (metadata only)
- Final statistics
```

## Exclusions

**Automatically excludes:**
- Binary files (images, executables, archives)
- Dependencies (node_modules, venv, __pycache__)
- Build artifacts (.next, dist, build)
- Large files (>10MB by default)
- Cache directories

**Includes important files:**
- Dockerfile, docker-compose.yml
- package.json, requirements.txt
- README, LICENSE, CHANGELOG
- Configuration files

## Testing

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# With coverage
pytest --cov=consolidate_project_sources
```

## Security

- Sensitive files (.env, .key, .pem) are detected automatically
- Content is **never included** in output
- Environment variable keys are **redacted** by default
- Use `--no-list-env-keys` for maximum security

## Contributing

Contributions are highly welcome! To ensure a smooth development process, please follow these guidelines:

1.  **Fork & Branch**: Fork the repository and create a new feature branch for your work.
2.  **Setup**: Install development dependencies and set up the pre-commit hooks:
    ```bash
    pip install -r requirements-dev.txt
    pre-commit install
    ```
3.  **Code**: Write clean, well-documented code. Ensure all new logic is accompanied by tests.
4.  **Test**: Run the full test suite to ensure your changes don't break existing functionality.
    ```bash
    pytest
    ```
5.  **Submit**: Push your changes and submit a pull request. The CI pipeline will automatically run linting and test checks.

## License

MIT License - See LICENSE file for details

## Changelog

### v3.0 (2025-10-19) - Architectural Refactor
- **Major Refactoring**: Decomposed the monolithic `ProjectConsolidator` class into smaller, single-responsibility classes (`GitInfoProvider`, `FileWalker`, `ReportGenerator`) for improved maintainability and testability.
- **CI Enhancements**:
    - Added a `lint` job to the CI pipeline using `pre-commit` to enforce code style.
    - Enforced an 85% test coverage threshold to prevent regressions.
- **Code Hardening**:
    - Replaced naive wildcard matching with `fnmatch` for robust file exclusion.
    - Improved project root detection to be more reliable.
    - Standardized dependency files (`requirements.txt` and `requirements-dev.txt`).
- **Increased Test Coverage**: Added comprehensive tests for CLI, utility functions, and error handling, bringing coverage to >85%.

### v2.1 (2025-10-18)
- Fixed force-include logic bug
- Added stat caching for performance
- Fixed directory exclusion pattern
- Enhanced security (key redaction)
- Added configurable options
- Improved error handling

### v2.0 (2025-10-18)
- Added type hints
- Implemented logging system
- Added CLI argument parser
- Auto-detect project root
- Auto-update .gitignore

## Support

Issues: https://github.com/semillacaramelo/project-consolidator/issues
