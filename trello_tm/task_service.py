from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any


class TaskServiceError(Exception):
    """Base exception class for task service errors."""

    pass


class TaskNotFoundError(TaskServiceError):
    """Raised when a requested task is not found."""

    def __init__(self, project_name: str, title: str):
        self.project_name = project_name
        self.title = title
        super().__init__(f"Task '{title}' not found in project '{project_name}'.")


class ProjectNotFoundError(TaskServiceError):
    """Raised when a requested project is not found."""

    def __init__(self, project_name: str):
        self.project_name = project_name
        super().__init__(f"Project '{project_name}' not found.")


class ChecklistNotFoundError(TaskServiceError):
    """Raised when a requested checklist is not found."""

    def __init__(self, checklist_name: str, title: str):
        self.checklist_name = checklist_name
        self.title = title
        super().__init__(f"Checklist '{checklist_name}' not found for task '{title}'.")


class ChecklistItemNotFoundError(TaskServiceError):
    """Raised when a requested checklist item is not found."""

    def __init__(self, item_name: str, title: str):
        self.item_name = item_name
        self.title = title
        super().__init__(f"Checklist item '{item_name}' not found for task '{title}'.")


class NoAvailableTasksError(TaskServiceError):
    """Raised when no available tasks are found in a project."""

    def __init__(self, project_name: str):
        self.project_name = project_name
        super().__init__(f"No available tasks found in project '{project_name}'.")


class InvalidTaskStatusError(TaskServiceError):
    """Raised when an invalid task status is provided."""

    def __init__(self, status: str):
        self.status = status
        valid_statuses = ["todo", "wip", "done"]
        super().__init__(f"Invalid task status '{status}'. Valid statuses are: {', '.join(valid_statuses)}.")


class TaskServiceConnectionError(TaskServiceError):
    """Raised when there's a connection issue with the task service backend."""

    def __init__(self, backend_name: str, details: str = ""):
        self.backend_name = backend_name
        self.details = details
        message = f"Connection error with {backend_name} backend"
        if details:
            message += f": {details}"
        super().__init__(message)


class TaskServiceAuthenticationError(TaskServiceError):
    """Raised when authentication fails with the task service backend."""

    def __init__(self, backend_name: str):
        self.backend_name = backend_name
        super().__init__(f"Authentication failed with {backend_name} backend. Please check your credentials.")


@dataclass
class ChecklistItem:
    """
    Represents a single item in a task checklist.
    """

    name: str
    checked: bool = False
    id: str | None = None


@dataclass
class Checklist:
    """
    Represents a checklist associated with a task.
    """

    name: str
    items: list[ChecklistItem]
    id: str | None = None

    def add_item(self, item_name: str) -> ChecklistItem:
        """Add a new item to the checklist."""
        item = ChecklistItem(name=item_name)
        self.items.append(item)
        return item

    def complete_item(self, item_name: str) -> bool:
        """Mark an item as completed. Returns True if item was found and completed."""
        for item in self.items:
            if item.name == item_name:
                item.checked = True
                return True
        return False

    def get_next_unchecked_item(self) -> ChecklistItem | None:
        """Get the next unchecked item in the checklist."""
        for item in self.items:
            if not item.checked:
                return item
        return None

    def is_complete(self) -> bool:
        """Check if all items in the checklist are completed."""
        return all(item.checked for item in self.items)


@dataclass
class Task:
    """
    Represents a task in the task management system.
    """

    title: str
    description: str
    project_name: str
    status: str = "todo"  # 'todo', 'wip', 'done'
    checklists: list[Checklist] = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    id: str | None = None

    def __post_init__(self):
        """Initialize default values after object creation."""
        if self.checklists is None:
            self.checklists = []
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()

    def add_checklist(self, checklist_name: str, items: list[str] | None = None) -> Checklist:
        """Add a new checklist to the task."""
        checklist_items = [ChecklistItem(name=item) for item in (items or [])]
        checklist = Checklist(name=checklist_name, items=checklist_items)
        self.checklists.append(checklist)
        self.updated_at = datetime.now()
        return checklist

    def get_checklist(self, checklist_name: str) -> Checklist | None:
        """Get a checklist by name."""
        for checklist in self.checklists:
            if checklist.name == checklist_name:
                return checklist
        return None

    def update_status(self, new_status: str) -> None:
        """Update the task status."""
        if new_status not in ["todo", "wip", "done"]:
            raise InvalidTaskStatusError(new_status)
        self.status = new_status
        self.updated_at = datetime.now()

    def is_complete(self) -> bool:
        """Check if the task is marked as complete."""
        return self.status == "done"

    def are_all_checklists_complete(self) -> bool:
        """Check if all checklists in the task are complete."""
        return all(checklist.is_complete() for checklist in self.checklists)


class TaskService(ABC):
    """
    Abstract base class defining the contract for task management services.

    This interface provides a standardized way to interact with different
    task management backends (e.g., Trello, Jira, local files, etc.).
    All implementations must provide concrete implementations of these methods.
    """

    @abstractmethod
    def add_task(self, project_name: str, title: str, description: str) -> tuple[Any, str]:
        """
        Add a new task to the specified project.

        Args:
            project_name: Name of the project to add the task to
            title: Title of the task
            description: Detailed description of the task

        Returns:
            Tuple containing the created task object and a confirmation message

        Raises:
            Exception: If task creation fails
        """
        pass

    @abstractmethod
    def get_next_task(self, project_name: str) -> tuple[Any | None, str]:
        """
        Get the next available task from the specified project.

        An available task is one that is not marked as 'in progress' and not completed.

        Args:
            project_name: Name of the project to search for tasks

        Returns:
            Tuple containing the next available task object (or None) and a message
        """
        pass

    @abstractmethod
    def mark_as_in_progress(self, project_name: str, title: str) -> tuple[Any, str]:
        """
        Mark a task as in progress.

        Args:
            project_name: Name of the project containing the task
            title: Title of the task to mark as in progress

        Returns:
            Tuple containing the updated task object and a confirmation message

        Raises:
            TaskNotFoundError: If the specified task is not found
        """
        pass

    @abstractmethod
    def mark_as_completed(self, project_name: str, title: str) -> tuple[Any, str]:
        """
        Mark a task as completed.

        Args:
            project_name: Name of the project containing the task
            title: Title of the task to mark as completed

        Returns:
            Tuple containing the updated task object and a confirmation message

        Raises:
            TaskNotFoundError: If the specified task is not found
        """
        pass

    @abstractmethod
    def update_task_description(self, project_name: str, title: str, description: str) -> tuple[Any, str]:
        """
        Update the description of an existing task.

        Args:
            project_name: Name of the project containing the task
            title: Title of the task to update
            description: New description content to add

        Returns:
            Tuple containing the updated task object and a confirmation message

        Raises:
            TaskNotFoundError: If the specified task is not found
        """
        pass

    @abstractmethod
    def update_task_with_checklist(self, project_name: str, title: str, checklist_items: list[str]) -> tuple[Any, str]:
        """
        Add or update a checklist for a task.

        If a checklist already exists, the items will be appended to it.
        If no checklist exists, a new one will be created with the provided items.

        Args:
            project_name: Name of the project containing the task
            title: Title of the task to update
            checklist_items: List of checklist item names to add

        Returns:
            Tuple containing the updated task object and a confirmation message

        Raises:
            TaskNotFoundError: If the specified task is not found
        """
        pass

    @abstractmethod
    def complete_checklist_item(self, project_name: str, title: str, checklist_item_name: str) -> tuple[Any, str]:
        """
        Mark a checklist item as completed.

        Args:
            project_name: Name of the project containing the task
            title: Title of the task containing the checklist item
            checklist_item_name: Name of the checklist item to complete

        Returns:
            Tuple containing the updated task object and a confirmation message

        Raises:
            TaskNotFoundError: If the specified task is not found
            ChecklistNotFoundError: If no checklist is found for the task
        """
        pass

    @abstractmethod
    def get_next_unchecked_checklist_item(self, project_name: str, title: str) -> tuple[dict[str, Any], str]:
        """
        Get the next unchecked checklist item for a task.

        Args:
            project_name: Name of the project containing the task
            title: Title of the task to check

        Returns:
            Tuple containing the checklist item dict and a message

        Raises:
            TaskNotFoundError: If the specified task is not found
            ChecklistNotFoundError: If no checklist is found for the task
            ChecklistItemNotFoundError: If no unchecked items are found
        """
        pass

    @abstractmethod
    def get_tasks(self, project_name: str, filter_type: str = "all") -> tuple[list[dict[str, Any]], str]:
        """
        Get tasks from a project with optional filtering.

        Args:
            project_name: Name of the project to get tasks from
            filter_type: Filter type - 'all' (default), 'wip' (work in progress), or 'done'

        Returns:
            Tuple containing a list of task dictionaries and a summary message
        """
        pass

    @abstractmethod
    def get_task_status(self, project_name: str, title: str) -> tuple[str, str]:
        """
        Get the current status of a task.

        Args:
            project_name: Name of the project containing the task
            title: Title of the task to check

        Returns:
            Tuple containing the task status ('todo', 'wip', 'done') and a message

        Raises:
            TaskNotFoundError: If the specified task is not found
        """
        pass

    @abstractmethod
    def set_task_status(self, project_name: str, title: str, status: str) -> tuple[Any, str]:
        """
        Set the status of a task.

        Args:
            project_name: Name of the project containing the task
            title: Title of the task to update
            status: New status for the task ('todo', 'wip', 'done')

        Returns:
            Tuple containing the updated task object and a confirmation message

        Raises:
            TaskNotFoundError: If the specified task is not found
            ValueError: If the status value is invalid
        """
        pass

    @abstractmethod
    def delete_all_tasks(self, project_name: str) -> str:
        """
        Delete all tasks in the specified project.

        Args:
            project_name: Name of the project to clear

        Returns:
            Confirmation message
        """
        pass
