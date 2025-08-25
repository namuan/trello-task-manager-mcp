import asyncio
import json
import os
import subprocess
import sys
import tempfile

from dotenv import load_dotenv
from mcp.server.fastmcp import Context, FastMCP

from trello_tm.trello_task_manager import TrelloTaskManager

load_dotenv()


def handle_task_operation(operation_func, error_prefix: str, *args):
    """Generic handler for task operations.

    Args:
        operation_func: The task operation function to execute
        error_prefix: Prefix for error messages
        *args: Arguments to pass to the operation function

    Returns:
        Operation result message
    """
    try:
        _, message = operation_func(*args)
    except Exception as e:
        return f"{error_prefix}: {e!s}"
    else:
        return message


def _create_basic_task_tools(mcp: FastMCP, manager: TrelloTaskManager):
    """Create basic task management tools."""

    @mcp.tool()
    async def add_task(ctx: Context, project_name: str, title: str, description: str) -> str:
        """Add a new task to a project's task file.

        Args:
            project_name: Name of the project
            title: Task title
            description: Task description

        Returns:
            Confirmation message
        """
        return handle_task_operation(manager.add_task, "Error adding task", project_name, title, description)

    @mcp.tool()
    async def get_next_available_task(ctx: Context, project_name: str) -> str:
        """Get the next available task from a project.

        An available task is one that is not marked as 'in progress' and not completed.

        Args:
            project_name: Name of the project

        Returns:
            The name of the next available task or a message if no task is available.
        """
        return handle_task_operation(manager.get_next_task, "Error getting next available task", project_name)

    @mcp.tool()
    async def mark_as_in_progress(ctx: Context, project_name: str, title: str) -> str:
        """Mark a task as in progress.

        Args:
            project_name: Name of the project
            title: Task title to be marked as in progress

        Returns:
            Confirmation message
        """
        return handle_task_operation(
            manager.mark_as_in_progress, "Error marking task as in progress", project_name, title
        )

    @mcp.tool()
    async def mark_as_completed(ctx: Context, project_name: str, title: str) -> str:
        """Mark a task as completed.

        Args:
            project_name: Name of the project
            title: Task title to be marked as completed

        Returns:
            Confirmation message
        """
        return handle_task_operation(manager.mark_as_completed, "Error marking task as completed", project_name, title)

    @mcp.tool()
    async def update_task_description(ctx: Context, project_name: str, title: str, description: str) -> str:
        """Update the description of an existing task.

        Args:
            project_name: Name of the project
            title: Task title to update
            description: New description for the task

        Returns:
            Confirmation message
        """
        return handle_task_operation(
            manager.update_task_description, "Error updating task description", project_name, title, description
        )


def _create_checklist_tools(mcp: FastMCP, manager: TrelloTaskManager):
    """Create checklist management tools."""

    @mcp.tool()
    async def update_task_with_checklist(
        ctx: Context, project_name: str, title: str, checklist_items: list[str]
    ) -> str:
        """Add or update a checklist for a task.

        If a checklist already exists, the items will be appended to it.
        If no checklist exists, a new one will be created with the provided items.

        Args:
            project_name: Name of the project
            title: Task title
            checklist_items: A list of strings for the checklist items to add.

        Returns:
            Confirmation message
        """
        return handle_task_operation(
            manager.update_task_with_checklist,
            "Error updating task with checklist",
            project_name,
            title,
            checklist_items,
        )

    @mcp.tool()
    async def complete_checklist_item(ctx: Context, project_name: str, title: str, checklist_item_name: str) -> str:
        """Complete a checklist item for a task.

        Args:
            project_name: Name of the project
            title: Task title
            checklist_item_name: The name of the checklist item to complete.

        Returns:
            Confirmation message
        """
        return handle_task_operation(
            manager.complete_checklist_item,
            "Error completing checklist item",
            project_name,
            title,
            checklist_item_name,
        )

    @mcp.tool()
    async def get_next_unchecked_checklist_item(ctx: Context, project_name: str, title: str) -> str:
        """Get the next unchecked checklist item for a task.

        Args:
            project_name: Name of the project
            title: Task title

        Returns:
            The name of the next unchecked checklist item or an error message
        """
        return handle_task_operation(
            manager.get_next_unchecked_checklist_item,
            "Error getting next unchecked checklist item",
            project_name,
            title,
        )


def _create_task_query_tools(mcp: FastMCP, manager: TrelloTaskManager):
    """Create task query tools."""

    @mcp.tool()
    async def get_tasks(ctx: Context, project_name: str, filter_type: str = "all") -> str:
        """Get tasks from a project with optional filtering.

        Args:
            project_name: Name of the project
            filter_type: Filter type - 'all' (default), 'wip' (work in progress), or 'done'

        Returns:
            A formatted list of tasks matching the filter criteria
        """
        try:
            tasks, message = manager.get_tasks(project_name, filter_type)
            if not tasks:
                return message

            # Format the tasks for display
            result = [message]
            for i, task in enumerate(tasks, 1):
                status_emoji = "✅" if task["status"] == "done" else ("🔄" if task["status"] == "wip" else "📋")
                result.append(f"{i}. {status_emoji} {task['name']} - {task['description']} (Status: {task['status']})")

            return "\n".join(result)
        except Exception as e:
            return f"Error getting tasks: {e!s}"


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
            result = json.load(f)
        os.unlink(output_file)
        return result
    except Exception:
        if os.path.exists(output_file):
            os.unlink(output_file)
        raise


def first_line(text: str) -> str:
    """Extract the first line from text."""
    return text.split("\n")[0].strip()


def _create_feedback_tools(mcp: FastMCP):
    """Create interactive feedback tools."""

    @mcp.tool()
    async def interactive_feedback(ctx: Context, project_directory: str, summary: str) -> dict[str, str]:
        """Request interactive feedback for a given project directory and summary.

        Args:
            project_directory: Full path to the project directory
            summary: Short, one-line summary of the changes

        Returns:
            Dictionary containing command logs and interactive feedback
        """
        try:
            return launch_feedback_ui(first_line(project_directory), first_line(summary))
        except Exception as e:
            return {"error": f"Error launching feedback UI: {e!s}"}


def create_task_tools(mcp: FastMCP, manager: TrelloTaskManager):
    """Create and register task management tools with MCP instance.

    Args:
        mcp: FastMCP instance
        manager: TrelloTaskManager instance
    """
    _create_basic_task_tools(mcp, manager)
    _create_checklist_tools(mcp, manager)
    _create_task_query_tools(mcp, manager)
    _create_feedback_tools(mcp)


def create_mcp() -> FastMCP:
    """Create a new MCP instance with task management tools.

    Returns:
        Configured FastMCP instance
    """
    mcp = FastMCP(
        "TASK MANAGER",
        description="Trello Task Manager",
        host=os.getenv("HOST", "127.0.0.1"),
        port=os.getenv("PORT", "8050"),
    )

    manager = TrelloTaskManager()
    create_task_tools(mcp, manager)

    return mcp


async def async_main():
    # Create a fresh MCP instance
    mcp = create_mcp()

    transport = os.getenv("TRANSPORT", "sse")
    if transport == "sse":
        # Run the MCP server with sse transport
        await mcp.run_sse_async()
    else:
        # Run the MCP server with stdio transport
        await mcp.run_stdio_async()


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
