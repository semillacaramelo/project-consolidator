"""
Integration test for full consolidation workflow.
"""

import pytest


@pytest.mark.integration
def test_full_consolidation_workflow(dummy_project, consolidator_factory):
    """
    Test the end-to-end consolidation process.
    """
    consolidator = consolidator_factory(dummy_project)
    output_path = dummy_project / "consolidated.txt"
    consolidator.consolidate(output_path)
    output = output_path.read_text()
    # Check included files
    assert 'print("hello")' in output  # app.py
    assert "name: CI" in output  # .github/workflows/ci.yml
    # Sensitive file placeholder
    assert (
        "SENSITIVE (content not included)" in output or "SENSITIVE" in output
    )
    # Excluded file not present
    assert "react mock" not in output  # node_modules/react.js
    # Statistics
    assert "Included Files: 3" in output
    assert "Sensitive Files: 1" in output
