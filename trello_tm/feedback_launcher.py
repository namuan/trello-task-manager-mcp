"""Launcher for the interactive feedback UI.

This module provides a function to invoke the Qt-based feedback UI implemented
in `feedback_ui.py` as a separate subprocess, returning the collected result
back to the caller.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

__all__ = ["launch_feedback_ui"]


def launch_feedback_ui(project_directory: str, summary: str) -> dict[str, str]:
    """Launch the feedback UI and return the result.

    Args:
        project_directory: Full path to the project directory
        summary: Short summary of the changes

    Returns:
        Dictionary containing command_logs and interactive_feedback
    """
    # Create a temporary file for the feedback result
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        output_file = tmp.name

    try:
        # Get the path to feedback_ui.py relative to this script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        feedback_ui_path = os.path.join(script_dir, "feedback_ui.py")

        # Run feedback_ui.py as a separate process
        args = [
            sys.executable,
            "-u",
            feedback_ui_path,
            "--project-directory",
            project_directory,
            "--prompt",
            summary,
            "--output-file",
            output_file,
        ]
        result = subprocess.run(  # noqa: S603
            args,
            check=False,
            shell=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            close_fds=True,
        )
        if result.returncode != 0:
            raise Exception(f"Failed to launch feedback UI: {result.returncode}")

        # Read the result from the temporary file
        with open(output_file) as f:
            res = json.load(f)
        os.unlink(output_file)
        return res
    except Exception:
        if os.path.exists(output_file):
            os.unlink(output_file)
        raise
