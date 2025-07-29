import base64
import json
import logging
import os
from typing import Any

import requests
from dotenv import load_dotenv

from .task_service import (
    ChecklistItemNotFoundError,
    InvalidTaskStatusError,
    NoAvailableTasksError,
    TaskNotFoundError,
    TaskService,
    TaskServiceAuthenticationError,
    TaskServiceConnectionError,
)

load_dotenv()

# Setup logging
logger = logging.getLogger(__name__)


class JiraTaskService(TaskService):
    """JIRA implementation of the TaskService interface."""

    def __init__(self):
        """Initialize the JIRA task service."""
        self.server_url = os.getenv("JIRA_SERVER_URL")
        self.username = os.getenv("JIRA_USERNAME")
        self.api_token = os.getenv("JIRA_API_TOKEN")

        if not all([self.server_url, self.username, self.api_token]):
            raise TaskServiceAuthenticationError("JIRA")

        # Remove trailing slash from server URL if present
        self.server_url = self.server_url.rstrip("/")
        self.base_url = f"{self.server_url}/rest/api/3"

        # Setup authentication headers
        auth_string = f"{self.username}:{self.api_token}"
        auth_bytes = auth_string.encode("ascii")
        auth_b64 = base64.b64encode(auth_bytes).decode("ascii")

        self.headers = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Test connection
        try:
            logger.info("Testing JIRA connection...")
            self._test_connection()
            logger.info("JIRA connection successful")
        except Exception as e:
            logger.exception("JIRA connection failed")
            raise TaskServiceConnectionError("JIRA", str(e)) from e

    def _test_connection(self):
        """Test the JIRA connection."""
        response = requests.get(f"{self.base_url}/myself", headers=self.headers, timeout=10)
        if response.status_code != 200:
            raise TaskServiceConnectionError("JIRA", f"Authentication failed: {response.status_code} - {response.text}")

    def _make_request(self, method: str, endpoint: str, data: dict | None = None) -> dict:
        """Make a request to the JIRA API."""
        url = f"{self.base_url}{endpoint}"
        logger.debug(f"Making {method} request to {endpoint}")

        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=self.headers, timeout=30)
            elif method.upper() == "POST":
                response = requests.post(url, headers=self.headers, data=json.dumps(data) if data else None, timeout=30)
            elif method.upper() == "PUT":
                response = requests.put(url, headers=self.headers, data=json.dumps(data) if data else None, timeout=30)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=self.headers, timeout=30)
            else:
                raise ValueError(method)

            if response.status_code >= 400:
                raise TaskServiceConnectionError(
                    "JIRA", f"API request failed: {response.status_code} - {response.text}"
                )

            return response.json() if response.content else {}

        except requests.exceptions.RequestException as e:
            raise TaskServiceConnectionError("JIRA", f"Request failed: {e!s}") from e

    def _get_project_key(self, project_name: str) -> str:
        """Get the project key from project name."""
        # For simplicity, assume project_name is the project key
        # In a real implementation, you might want to search for projects
        return project_name.upper()

    def _search_issues(self, jql: str, fields: list[str] | None = None, max_results: int = 50) -> dict:
        """Search for issues using JQL."""
        data = {
            "jql": jql,
            "maxResults": max_results,
            "fields": fields or ["summary", "description", "status", "issuetype", "parent"],
        }
        return self._make_request("POST", "/search", data)

    def _get_issue_transitions(self, issue_key: str) -> list[dict]:
        """Get available transitions for an issue."""
        response = self._make_request("GET", f"/issue/{issue_key}/transitions")
        return response.get("transitions", [])

    def _transition_issue(self, issue_key: str, transition_id: str) -> dict:
        """Transition an issue to a new status."""
        data = {"transition": {"id": transition_id}}
        return self._make_request("POST", f"/issue/{issue_key}/transitions", data)

    def _find_transition_id(self, issue_key: str, target_status: str) -> str:
        """Find the transition ID for a target status."""
        transitions = self._get_issue_transitions(issue_key)
        for transition in transitions:
            if transition["to"]["name"].lower() == target_status.lower():
                return transition["id"]
        raise TaskServiceConnectionError(
            "JIRA", f"No transition found to status '{target_status}' for issue {issue_key}"
        )

    def add_task(self, project_name: str, title: str, description: str) -> tuple[Any, str]:
        """Add a new task to the specified project."""
        logger.info(f"Creating task '{title}' in project '{project_name}'")
        project_key = self._get_project_key(project_name)

        data = {
            "fields": {
                "project": {"key": project_key},
                "summary": title,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}],
                },
                "issuetype": {"name": "Task"},
            }
        }

        try:
            response = self._make_request("POST", "/issue", data)
            issue_key = response.get("key")
            logger.info(f"Task '{title}' created successfully with key {issue_key}")
        except Exception as e:
            logger.exception(f"Failed to create task '{title}'")
            raise TaskServiceConnectionError("JIRA", f"Failed to create task: {e!s}") from e
        else:
            return response, f"Task '{title}' created successfully with key {issue_key}"

    def get_next_task(self, project_name: str) -> tuple[Any | None, str]:
        """Get the next available task from the specified project."""
        project_key = self._get_project_key(project_name)
        jql = f'project = "{project_key}" AND status = "To Do" ORDER BY priority DESC, created ASC'

        try:
            response = self._search_issues(jql, max_results=1)
            issues = response.get("issues", [])

            if not issues:
                self._raise_no_available_tasks(project_name)

            issue = issues[0]
            task_title = issue["fields"]["summary"]

        except NoAvailableTasksError:
            raise
        except Exception as e:
            raise TaskServiceConnectionError("JIRA", f"Failed to get next task: {e!s}") from e
        else:
            return issue, f"Next available task: {task_title}"

    def mark_as_in_progress(self, project_name: str, title: str) -> tuple[Any, str]:
        """Mark a task as in progress."""
        logger.info(f"Marking task '{title}' as in progress in project '{project_name}'")
        # First find the task
        project_key = self._get_project_key(project_name)
        jql = f'project = "{project_key}" AND summary ~ "{title}"'

        try:
            response = self._search_issues(jql, max_results=1)
            issues = response.get("issues", [])

            if not issues:
                self._raise_task_not_found(project_name, title)

            issue = issues[0]
            issue_key = issue["key"]

            # Find transition to "In Progress"
            transition_id = self._find_transition_id(issue_key, "In Progress")

            # Perform transition
            self._transition_issue(issue_key, transition_id)

        except (TaskNotFoundError, TaskServiceConnectionError):
            raise
        except Exception as e:
            raise TaskServiceConnectionError("JIRA", f"Failed to mark task as in progress: {e!s}") from e
        else:
            return issue, f"Task '{title}' marked as in progress"

    def mark_as_completed(self, project_name: str, title: str) -> tuple[Any, str]:
        """Mark a task as completed."""
        # First find the task
        project_key = self._get_project_key(project_name)
        jql = f'project = "{project_key}" AND summary ~ "{title}"'

        try:
            response = self._search_issues(jql, max_results=1)
            issues = response.get("issues", [])

            if not issues:
                self._raise_task_not_found(project_name, title)

            issue = issues[0]
            issue_key = issue["key"]

            # Find transition to "Done"
            transition_id = self._find_transition_id(issue_key, "Done")

            # Perform transition
            self._transition_issue(issue_key, transition_id)

        except (TaskNotFoundError, TaskServiceConnectionError):
            raise
        except Exception as e:
            raise TaskServiceConnectionError("JIRA", f"Failed to mark task as completed: {e!s}") from e
        else:
            return issue, f"Task '{title}' marked as completed"

    def update_task_description(self, project_name: str, title: str, description: str) -> tuple[Any, str]:
        """Update the description of an existing task."""
        # First find the task
        project_key = self._get_project_key(project_name)
        jql = f'project = "{project_key}" AND summary ~ "{title}"'

        try:
            response = self._search_issues(jql, max_results=1)
            issues = response.get("issues", [])

            if not issues:
                self._raise_task_not_found(project_name, title)

            issue = issues[0]
            issue_key = issue["key"]

            # Update description
            data = {
                "fields": {
                    "description": {
                        "type": "doc",
                        "version": 1,
                        "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}],
                    }
                }
            }

            self._make_request("PUT", f"/issue/{issue_key}", data)

        except (TaskNotFoundError, TaskServiceConnectionError):
            raise
        except Exception as e:
            raise TaskServiceConnectionError("JIRA", f"Failed to update task description: {e!s}") from e
        else:
            return issue, f"Task '{title}' description updated successfully"

    def update_task_with_checklist(self, project_name: str, title: str, checklist_items: list[str]) -> tuple[Any, str]:
        """Add or update a checklist for a task (implemented as subtasks)."""
        # First find the parent task
        project_key = self._get_project_key(project_name)
        jql = f'project = "{project_key}" AND summary ~ "{title}"'

        try:
            response = self._search_issues(jql, max_results=1)
            issues = response.get("issues", [])

            if not issues:
                self._raise_task_not_found(project_name, title)

            parent_issue = issues[0]
            parent_key = parent_issue["key"]

            # Create subtasks for each checklist item
            created_subtasks = []
            for item_name in checklist_items:
                subtask_data = {
                    "fields": {
                        "project": {"key": project_key},
                        "parent": {"key": parent_key},
                        "summary": item_name,
                        "issuetype": {"name": "Sub-task"},
                    }
                }

                subtask_response = self._make_request("POST", "/issue", subtask_data)
                created_subtasks.append(subtask_response.get("key"))

            return parent_issue, f"Added {len(checklist_items)} checklist items as subtasks to '{title}'"

        except (TaskNotFoundError, TaskServiceConnectionError):
            raise
        except Exception as e:
            raise TaskServiceConnectionError("JIRA", f"Failed to update task with checklist: {e!s}") from e

    def complete_checklist_item(self, project_name: str, title: str, checklist_item_name: str) -> tuple[Any, str]:
        """Mark a checklist item as completed (transition subtask to Done)."""
        logger.info(f"Completing checklist item '{checklist_item_name}' for task '{title}' in project '{project_name}'")
        # First find the parent task
        project_key = self._get_project_key(project_name)
        parent_jql = f'project = "{project_key}" AND summary ~ "{title}"'

        try:
            response = self._search_issues(parent_jql, max_results=1)
            issues = response.get("issues", [])

            if not issues:
                self._raise_task_not_found(project_name, title)

            parent_key = issues[0]["key"]

            # Find the subtask with matching summary
            subtask_jql = f'parent = "{parent_key}" AND summary ~ "{checklist_item_name}"'
            subtask_response = self._search_issues(subtask_jql, max_results=1)
            subtasks = subtask_response.get("issues", [])

            if not subtasks:
                self._raise_checklist_item_not_found(checklist_item_name, title)

            subtask = subtasks[0]
            subtask_key = subtask["key"]

            # Find transition to "Done"
            transition_id = self._find_transition_id(subtask_key, "Done")

            # Perform transition
            self._transition_issue(subtask_key, transition_id)

        except (TaskNotFoundError, ChecklistItemNotFoundError, TaskServiceConnectionError):
            raise
        except Exception as e:
            raise TaskServiceConnectionError("JIRA", f"Failed to complete checklist item: {e!s}") from e
        else:
            return subtask, f"Checklist item '{checklist_item_name}' marked as completed"

    def get_next_unchecked_checklist_item(self, project_name: str, title: str) -> tuple[dict[str, Any], str]:
        """Get the next unchecked checklist item for a task."""
        # First find the parent task
        project_key = self._get_project_key(project_name)
        parent_jql = f'project = "{project_key}" AND summary ~ "{title}"'

        try:
            response = self._search_issues(parent_jql, max_results=1)
            issues = response.get("issues", [])

            if not issues:
                self._raise_task_not_found(project_name, title)

            parent_key = issues[0]["key"]

            # Find uncompleted subtasks
            subtask_jql = f'parent = "{parent_key}" AND status != "Done" ORDER BY created ASC'
            subtask_response = self._search_issues(subtask_jql, max_results=1)
            subtasks = subtask_response.get("issues", [])

            if not subtasks:
                self._raise_no_unchecked_items(title)

            subtask = subtasks[0]
            item_name = subtask["fields"]["summary"]

            return {
                "name": item_name,
                "checked": False,
                "id": subtask["key"],
            }, f"Next unchecked checklist item for task '{title}': {item_name}"

        except (TaskNotFoundError, ChecklistItemNotFoundError, TaskServiceConnectionError):
            raise
        except Exception as e:
            raise TaskServiceConnectionError("JIRA", f"Failed to get next unchecked checklist item: {e!s}") from e

    def get_tasks(self, project_name: str, filter_type: str = "all") -> tuple[list[dict[str, Any]], str]:
        """Get tasks from a project with optional filtering."""
        project_key = self._get_project_key(project_name)

        # Build JQL based on filter type
        base_jql = f'project = "{project_key}"'
        if filter_type == "wip":
            jql = f'{base_jql} AND status = "In Progress"'
        elif filter_type == "done":
            jql = f'{base_jql} AND status = "Done"'
        else:  # all
            jql = base_jql

        try:
            response = self._search_issues(jql)
            issues = response.get("issues", [])

            tasks = []
            for issue in issues:
                tasks.append({
                    "title": issue["fields"]["summary"],
                    "description": self._extract_description_text(issue["fields"].get("description", {})),
                    "status": self._map_jira_status_to_internal(issue["fields"]["status"]["name"]),
                    "id": issue["key"],
                })

            return tasks, f"Found {len(tasks)} tasks in project '{project_name}' with filter '{filter_type}'"

        except Exception as e:
            raise TaskServiceConnectionError("JIRA", f"Failed to get tasks: {e!s}") from e

    def get_task_status(self, project_name: str, title: str) -> tuple[str, str]:
        """Get the current status of a task."""
        project_key = self._get_project_key(project_name)
        jql = f'project = "{project_key}" AND summary ~ "{title}"'

        try:
            response = self._search_issues(jql, max_results=1)
            issues = response.get("issues", [])

            if not issues:
                self._raise_task_not_found(project_name, title)

            issue = issues[0]
            jira_status = issue["fields"]["status"]["name"]
            internal_status = self._map_jira_status_to_internal(jira_status)

        except (TaskNotFoundError, TaskServiceConnectionError):
            raise
        except Exception as e:
            raise TaskServiceConnectionError("JIRA", f"Failed to get task status: {e!s}") from e
        else:
            return internal_status, f"Task '{title}' status: {internal_status}"

    def set_task_status(self, project_name: str, title: str, status: str) -> tuple[Any, str]:
        """Set the status of a task."""
        if status not in ["todo", "wip", "done"]:
            raise InvalidTaskStatusError(status)

        # Map internal status to JIRA status
        jira_status_map = {"todo": "To Do", "wip": "In Progress", "done": "Done"}
        target_status = jira_status_map[status]

        # First find the task
        project_key = self._get_project_key(project_name)
        jql = f'project = "{project_key}" AND summary ~ "{title}"'

        try:
            response = self._search_issues(jql, max_results=1)
            issues = response.get("issues", [])

            if not issues:
                self._raise_task_not_found(project_name, title)

            issue = issues[0]
            issue_key = issue["key"]

            # Find transition to target status
            transition_id = self._find_transition_id(issue_key, target_status)

            # Perform transition
            self._transition_issue(issue_key, transition_id)

        except (TaskNotFoundError, InvalidTaskStatusError, TaskServiceConnectionError):
            raise
        except Exception as e:
            raise TaskServiceConnectionError("JIRA", f"Failed to set task status: {e!s}") from e
        else:
            return issue, f"Task '{title}' status set to '{status}'"

    def delete_all_tasks(self, project_name: str) -> str:
        """Delete all tasks in the specified project."""
        project_key = self._get_project_key(project_name)
        jql = f'project = "{project_key}"'

        try:
            response = self._search_issues(jql, fields=["key"])
            issues = response.get("issues", [])

            deleted_count = 0
            for issue in issues:
                issue_key = issue["key"]
                self._make_request("DELETE", f"/issue/{issue_key}?deleteSubtasks=true")
                deleted_count += 1

        except Exception as e:
            raise TaskServiceConnectionError("JIRA", f"Failed to delete tasks: {e!s}") from e
        else:
            return f"Deleted {deleted_count} tasks from project '{project_name}'"

    def _extract_description_text(self, description_obj: dict) -> str:
        """Extract plain text from JIRA's ADF (Atlassian Document Format) description."""
        if not description_obj or not isinstance(description_obj, dict):
            return ""

        content = description_obj.get("content", [])
        text_parts = []

        for item in content:
            if item.get("type") == "paragraph":
                paragraph_content = item.get("content", [])
                for text_item in paragraph_content:
                    if text_item.get("type") == "text":
                        text_parts.append(text_item.get("text", ""))

        return " ".join(text_parts)

    def _raise_task_not_found(self, project_name: str, title: str) -> None:
        """Helper to raise TaskNotFoundError."""
        raise TaskNotFoundError(project_name, title)

    def _raise_no_unchecked_items(self, title: str) -> None:
        """Helper to raise ChecklistItemNotFoundError for no unchecked items."""
        raise ChecklistItemNotFoundError("none", title)

    def _raise_checklist_item_not_found(self, item_name: str, title: str) -> None:
        """Helper to raise ChecklistItemNotFoundError."""
        raise ChecklistItemNotFoundError(item_name, title)

    def _raise_no_available_tasks(self, project_name: str) -> None:
        """Helper to raise NoAvailableTasksError."""
        raise NoAvailableTasksError(project_name)

    def _map_jira_status_to_internal(self, jira_status: str) -> str:
        """Map JIRA status to internal status format."""
        status_map = {"to do": "todo", "in progress": "wip", "done": "done"}
        return status_map.get(jira_status.lower(), "todo")
