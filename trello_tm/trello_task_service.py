import datetime
import os
from typing import Any

from dotenv import load_dotenv
from trello import TrelloClient

from .task_service import (
    ChecklistItemNotFoundError,
    ChecklistNotFoundError,
    InvalidTaskStatusError,
    NoAvailableTasksError,
    TaskNotFoundError,
    TaskService,
    TaskServiceAuthenticationError,
    TaskServiceConnectionError,
)

load_dotenv()

# Default label definitions
DEFAULT_LABELS = {"WIP": "blue"}
WIP_LABEL_NAME = "WIP"
DEFAULT_CHECKLIST_NAME = "Checklist"


class TrelloTaskService(TaskService):
    """Trello implementation of the TaskService interface."""

    def __init__(self):
        """Initialize the Trello task service."""
        self.api_key = os.getenv("TRELLO_API_KEY")
        self.api_token = os.getenv("TRELLO_API_TOKEN")
        self.board_name = os.getenv("TRELLO_BOARD_NAME")

        if not all([self.api_key, self.api_token, self.board_name]):
            raise TaskServiceAuthenticationError("Trello")

        try:
            self.client = TrelloClient(
                api_key=self.api_key,
                api_secret=self.api_token,
            )
            self.selected_board = self._get_board()
        except Exception as e:
            raise TaskServiceConnectionError("Trello", str(e)) from e

        self.labels = {}
        self._create_default_labels()

    def add_task(self, project_name: str, title: str, description: str) -> tuple[Any, str]:
        """Add a new task to the specified project."""
        try:
            board_list = self._find_or_create_list(project_name)
            card = board_list.add_card(name=title, desc=description, position="bottom")
        except Exception as e:
            raise TaskServiceConnectionError("Trello", f"Failed to add task: {e!s}") from e
        else:
            return card, f"Added new task '{title}' to {project_name}"

    def get_next_task(self, project_name: str) -> tuple[Any | None, str]:
        """Get the next available task from the specified project."""
        try:
            wip_label = self._get_wip_label()
            board_list = self._get_list_for_next_task(project_name)
            card = self._find_next_available_card(board_list, wip_label)
        except (NoAvailableTasksError, TaskServiceConnectionError):
            raise
        except Exception as e:
            raise TaskServiceConnectionError("Trello", f"Failed to get next task: {e!s}") from e
        else:
            return card, f"Next available task: {card.name} - {card.description}"

    def mark_as_in_progress(self, project_name: str, title: str) -> tuple[Any, str]:
        """Mark a task as in progress."""
        try:
            card = self._find_card_or_raise(project_name, title)
            if WIP_LABEL_NAME in self.labels:
                card.add_label(self.labels[WIP_LABEL_NAME])
        except TaskNotFoundError:
            raise
        except Exception as e:
            raise TaskServiceConnectionError("Trello", f"Failed to mark task as in progress: {e!s}") from e
        else:
            return card, f"Task '{title}' in project '{project_name}' marked as in progress."

    def mark_as_completed(self, project_name: str, title: str) -> tuple[Any, str]:
        """Mark a task as completed."""
        try:
            card = self._find_card_or_raise(project_name, title)
            if WIP_LABEL_NAME in self.labels and self.labels[WIP_LABEL_NAME] in card.labels:
                card.remove_label(self.labels[WIP_LABEL_NAME])
            card.set_due_complete()
        except TaskNotFoundError:
            raise
        except Exception as e:
            raise TaskServiceConnectionError("Trello", f"Failed to mark task as completed: {e!s}") from e
        else:
            return card, f"Task '{title}' in project '{project_name}' has been completed."

    def update_task_description(self, project_name: str, title: str, description: str) -> tuple[Any, str]:
        """Update the description of an existing task."""
        try:
            card = self._find_card_or_raise(project_name, title)
            # Fetch current description to preserve it
            card.fetch()
            existing_description = card.description or ""

            # Add timestamp and new description
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if existing_description:
                updated_description = f"{existing_description}\n\n--- Updated on {timestamp} ---\n{description}"
            else:
                updated_description = f"--- Created on {timestamp} ---\n{description}"

            card.set_description(updated_description)
        except TaskNotFoundError:
            raise
        except Exception as e:
            raise TaskServiceConnectionError("Trello", f"Failed to update task description: {e!s}") from e
        else:
            return card, f"Description updated for task '{title}' in project '{project_name}'."

    def update_task_with_checklist(self, project_name: str, title: str, checklist_items: list[str]) -> tuple[Any, str]:
        """Add or update a checklist for a task."""
        try:
            card = self._find_card_or_raise(project_name, title)
            # Fetch existing checklists
            card.fetch_checklists()

            existing_checklist = None
            for checklist in card.checklists:
                if checklist.name == DEFAULT_CHECKLIST_NAME:
                    existing_checklist = checklist
                    break

            if existing_checklist:
                # Append items to existing checklist
                for item in checklist_items:
                    existing_checklist.add_checklist_item(item)
                return card, f"Items appended to existing checklist in task '{title}' in project '{project_name}'."
            else:
                # Create new checklist
                card.add_checklist(DEFAULT_CHECKLIST_NAME, checklist_items)
        except TaskNotFoundError:
            raise
        except Exception as e:
            raise TaskServiceConnectionError("Trello", f"Failed to update task checklist: {e!s}") from e
        else:
            return card, f"New checklist created for task '{title}' in project '{project_name}'."

    def complete_checklist_item(self, project_name: str, title: str, checklist_item_name: str) -> tuple[Any, str]:
        """Mark a checklist item as completed."""
        try:
            card = self._find_card_or_raise(project_name, title)
            card.fetch_checklists()
            for checklist in card.checklists:
                if checklist.name == DEFAULT_CHECKLIST_NAME:
                    checklist.set_checklist_item(checklist_item_name, True)
                    return (
                        card,
                        f"Checklist item '{checklist_item_name}' in task '{title}' in project '{project_name}' completed.",
                    )

        except (TaskNotFoundError, ChecklistNotFoundError):
            raise
        except Exception as e:
            raise TaskServiceConnectionError("Trello", f"Failed to complete checklist item: {e!s}") from e
        else:
            raise ChecklistNotFoundError(DEFAULT_CHECKLIST_NAME, title)

    def get_next_unchecked_checklist_item(self, project_name: str, title: str) -> tuple[dict[str, Any], str]:
        """Get the next unchecked checklist item for a task."""
        try:
            card = self._find_card_or_raise(project_name, title)
            card.fetch_checklists()
            return self._find_next_unchecked_item(card, title)
        except (TaskNotFoundError, ChecklistNotFoundError, ChecklistItemNotFoundError):
            raise
        except Exception as e:
            raise TaskServiceConnectionError("Trello", f"Failed to get next unchecked checklist item: {e!s}") from e

    def get_tasks(self, project_name: str, filter_type: str = "all") -> tuple[list[dict[str, Any]], str]:
        """Get tasks from a project with optional filtering."""
        try:
            board_list = self._find_existing_list(project_name)
            if not board_list:
                return [], f"No tasks found in project '{project_name}'."

            cards = board_list.list_cards()
            filtered_tasks = []
            wip_label = self.labels.get(WIP_LABEL_NAME)

            for card in cards:
                card.fetch()
                status = self._get_task_status(card, wip_label)

                if self._should_include_task(status, filter_type):
                    filtered_tasks.append(self._create_task_dict(card, status))

            message = self._generate_result_message(filtered_tasks, filter_type, project_name)
        except Exception as e:
            raise TaskServiceConnectionError("Trello", f"Failed to get tasks: {e!s}") from e
        else:
            return filtered_tasks, message

    def get_task_status(self, project_name: str, title: str) -> tuple[str, str]:
        """Get the current status of a task."""
        try:
            card = self._find_card_or_raise(project_name, title)
            card.fetch()
            wip_label = self.labels.get(WIP_LABEL_NAME)
            status = self._get_task_status(card, wip_label)
        except TaskNotFoundError:
            raise
        except Exception as e:
            raise TaskServiceConnectionError("Trello", f"Failed to get task status: {e!s}") from e
        else:
            return status, f"Task '{title}' status: {status}"

    def set_task_status(self, project_name: str, title: str, status: str) -> tuple[Any, str]:
        """Set the status of a task."""
        if status not in ["todo", "wip", "done"]:
            raise InvalidTaskStatusError(status)

        try:
            card = self._find_card_or_raise(project_name, title)

            wip_label = self.labels.get(WIP_LABEL_NAME)

            # Remove WIP label if present
            if wip_label and wip_label in card.labels:
                card.remove_label(wip_label)

            # Set completion status to false
            if card.is_due_complete:
                card.set_due_complete(False)

            # Apply new status
            if status == "wip" and wip_label:
                card.add_label(wip_label)
            elif status == "done":
                card.set_due_complete()
        except (TaskNotFoundError, InvalidTaskStatusError):
            raise
        except Exception as e:
            raise TaskServiceConnectionError("Trello", f"Failed to set task status: {e!s}") from e
        else:
            return card, f"Task '{title}' status set to '{status}'"

    def delete_all_tasks(self, project_name: str) -> str:
        """Delete all tasks in the specified project."""
        try:
            board_list = self._find_existing_list(project_name)
            if not board_list:
                return f"Project '{project_name}' not found."

            cards = board_list.list_cards()
            for card in cards:
                card.delete()

        except Exception as e:
            raise TaskServiceConnectionError("Trello", f"Failed to delete tasks: {e!s}") from e
        else:
            return f"All tasks in project '{project_name}' have been deleted."

    # Helper methods

    def _get_board(self):
        selected_board = next((board for board in self.client.list_boards() if board.name == self.board_name), None)
        if not selected_board:
            raise TaskServiceConnectionError("Trello", f"Board '{self.board_name}' not found")
        return selected_board

    def _get_wip_label(self):
        wip_label = self.labels.get(WIP_LABEL_NAME)
        if not wip_label:
            raise TaskServiceConnectionError("Trello", "WIP label not found")
        return wip_label

    def _get_list_for_next_task(self, project_name):
        board_list = self._find_existing_list(project_name)
        if not board_list:
            raise NoAvailableTasksError(project_name)
        return board_list

    def _find_next_available_card(self, board_list, wip_label):
        for card in board_list.list_cards():
            card.fetch()
            has_wip = any(label.id == wip_label.id for label in card.labels)
            if not has_wip and not card.is_due_complete:
                return card
        raise NoAvailableTasksError(board_list.name)

    def _find_card_or_raise(self, project_name: str, title: str):
        """Find a card by name or raise TaskNotFoundError."""
        board_list = self._find_existing_list(project_name)
        if not board_list:
            raise TaskNotFoundError(project_name, title)

        card = next((card for card in board_list.list_cards() if card.name == title), None)
        if not card:
            raise TaskNotFoundError(project_name, title)

        return card

    def _find_next_unchecked_item(self, card, title: str) -> tuple[dict[str, Any], str]:
        """Find the next unchecked checklist item."""
        for checklist in card.checklists:
            if checklist.name == DEFAULT_CHECKLIST_NAME:
                # Find the first unchecked item
                for item in checklist.items:
                    if not item.get("checked", False):
                        return item, f"Next unchecked checklist item for task '{title}': {item['name']}"

        # No checklist found
        raise ChecklistNotFoundError(DEFAULT_CHECKLIST_NAME, title)

    def _find_or_create_list(self, project_name: str):
        """Find an existing list or create a new one."""
        board_list = self._find_existing_list(project_name)
        if board_list is None:
            board_list = self.selected_board.add_list(project_name)
        return board_list

    def _find_existing_list(self, project_name: str):
        """Find an existing list by name."""
        return next(
            (board_list for board_list in self.selected_board.all_lists() if board_list.name == project_name), None
        )

    def _create_default_labels(self):
        """Create default labels on the board."""
        try:
            existing_labels = {label.name: label for label in self.selected_board.get_labels()}
            for label_name, label_color in DEFAULT_LABELS.items():
                if label_name not in existing_labels:
                    new_label = self.selected_board.add_label(label_name, label_color)
                    self.labels[label_name] = new_label
                else:
                    self.labels[label_name] = existing_labels[label_name]
        except Exception as e:
            raise TaskServiceConnectionError("Trello", f"Failed to create labels: {e!s}") from e

    def _create_task_dict(self, card, status: str) -> dict[str, Any]:
        """Create a task dictionary from a card."""
        return {"name": card.name, "description": card.description, "status": status, "id": card.id}

    def _get_task_status(self, card, wip_label) -> str:
        """Determine the status of a task card."""
        has_wip = False
        if wip_label:
            has_wip = any(label.id == wip_label.id for label in card.labels)

        is_completed = card.is_due_complete

        if is_completed:
            return "done"
        elif has_wip:
            return "wip"
        else:
            return "todo"

    def _should_include_task(self, status: str, filter_type: str) -> bool:
        """Check if a task should be included based on filter."""
        filter_conditions = {"all": True, "wip": status == "wip", "done": status == "done"}
        return filter_conditions.get(filter_type, False)

    def _generate_result_message(self, filtered_tasks: list, filter_type: str, project_name: str) -> str:
        """Generate appropriate result message based on filter and results."""
        if not filtered_tasks:
            no_tasks_messages = {
                "all": f"No tasks found in project '{project_name}'.",
                "wip": f"No work in progress tasks found in project '{project_name}'.",
                "done": f"No completed tasks found in project '{project_name}'.",
            }
            return no_tasks_messages.get(
                filter_type, f"No tasks found with filter '{filter_type}' in project '{project_name}'."
            )
        else:
            task_count = len(filtered_tasks)
            found_tasks_messages = {
                "all": f"Found {task_count} task(s) in project '{project_name}'.",
                "wip": f"Found {task_count} work in progress task(s) in project '{project_name}'.",
                "done": f"Found {task_count} completed task(s) in project '{project_name}'.",
            }
            return found_tasks_messages.get(
                filter_type, f"Found {task_count} task(s) with filter '{filter_type}' in project '{project_name}'"
            )
