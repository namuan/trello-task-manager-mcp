import asyncio
import os

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


def create_task_tools(mcp: FastMCP, manager: TrelloTaskManager):
    """Create and register task management tools with MCP instance.

    Args:
        mcp: FastMCP instance
        manager: TrelloTaskManager instance
    """

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
    async def update_task_with_checklist(
        ctx: Context, project_name: str, title: str, checklist_items: list[str]
    ) -> str:
        """Add or update a checklist for a task.

        Args:
            project_name: Name of the project
            title: Task title
            checklist_items: A list of strings for the checklist.

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
