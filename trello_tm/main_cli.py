import asyncio
import os

from dotenv import load_dotenv
from mcp.server.fastmcp import Context, FastMCP

from trello_tm.trello_task_manager import TrelloTaskManager

load_dotenv()


def create_mcp() -> FastMCP:
    """Create a new MCP instance with task management tools."""
    mcp = FastMCP(
        "TASK MANAGER",
        description="Trello Task Manager",
        host=os.getenv("HOST", "127.0.0.1"),
        port=os.getenv("PORT", "8050"),
    )

    manager = TrelloTaskManager()

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
        try:
            _, message = manager.add_task(project_name, title, description)
        except Exception as e:
            return f"Error adding task: {e!s}"
        else:
            return message

    @mcp.tool()
    async def get_next_available_task(ctx: Context, project_name: str) -> str:
        """Get the next available task from a project.

        An available task is one that is not marked as 'in progress' and not completed.

        Args:
            project_name: Name of the project

        Returns:
            The name of the next available task or a message if no task is available.
        """
        try:
            _, message = manager.get_next_task(project_name)
        except Exception as e:
            return f"Error getting next available task: {e!s}"
        else:
            return message

    @mcp.tool()
    async def mark_as_in_progress(ctx: Context, project_name: str, title: str) -> str:
        """Mark a task as in progress.

        Args:
            project_name: Name of the project
            title: Task title to be marked as in progress

        Returns:
            Confirmation message
        """
        try:
            _, message = manager.mark_as_in_progress(project_name, title)
        except Exception as e:
            return f"Error marking task as in progress: {e!s}"
        else:
            return message

    @mcp.tool()
    async def mark_as_completed(ctx: Context, project_name: str, title: str) -> str:
        """Mark a task as completed.

        Args:
            project_name: Name of the project
            title: Task title to be marked as completed

        Returns:
            Confirmation message
        """
        try:
            _, message = manager.mark_as_completed(project_name, title)
        except Exception as e:
            return f"Error marking task as completed: {e!s}"
        else:
            return message

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
