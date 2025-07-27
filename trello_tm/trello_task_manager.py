import datetime
import os

from dotenv import load_dotenv
from trello import TrelloClient

load_dotenv()

TRELLO_API_KEY = os.getenv("TRELLO_API_KEY")
TRELLO_API_TOKEN = os.getenv("TRELLO_API_TOKEN")
BOARD_NAME_TO_MATCH = os.getenv("TRELLO_BOARD_NAME")

# Default label definitions
DEFAULT_LABELS = {"WIP": "blue"}
WIP_LABEL_NAME = "WIP"
DEFAULT_CHECKLIST_NAME = "Checklist"


class TaskNotFoundError(Exception):
    def __init__(self, project_name, title):
        self.project_name = project_name
        self.title = title
        super().__init__(f"Task '{title}' not found in project '{project_name}'.")


class ChecklistNotFoundError(Exception):
    def __init__(self, checklist_name, title):
        self.checklist_name = checklist_name
        self.title = title
        super().__init__(f"Checklist '{checklist_name}' not found for task '{title}'.")


class ChecklistItemNotFoundError(Exception):
    def __init__(self, title):
        self.title = title
        super().__init__(f"No unchecked checklist items found for task '{title}'.")


class TrelloTaskManager:
    selected_board_list = None
    wip_label = None

    def __init__(self):
        self.client = TrelloClient(
            api_key=TRELLO_API_KEY,
            api_secret=TRELLO_API_TOKEN,
        )
        self.selected_board = next(
            (board for board in self.client.list_boards() if board.name == BOARD_NAME_TO_MATCH), None
        )
        self.labels = {}
        if self.selected_board:
            self._create_default_labels()

    def add_task(self, project_name, title, description):
        self.selected_board_list = self._find_existing_list(project_name)

        if self.selected_board_list is None:
            self.selected_board_list = self.selected_board.add_list(project_name)

        card_added = self.selected_board_list.add_card(name=f"{title}", desc=description, position="bottom")
        return card_added, f"Added new task '{title}' to {project_name}"

    def get_next_task(self, project_name):
        wip_label = self.labels.get(WIP_LABEL_NAME)
        if not wip_label:
            return "WIP label has not been set up on the board."

        for card in self.selected_board_list.list_cards():
            card.fetch()

            has_wip = any(label.id == wip_label.id for label in card.labels)

            if not has_wip and not card.is_due_complete:
                return card, f"Next available task: {card.name} - {card.description}"

        return None, f"No available tasks found in '{project_name}'."

    def mark_as_in_progress(self, project_name, title):
        card_to_update = next((card for card in self.selected_board_list.list_cards() if card.name == title), None)
        if not card_to_update:
            raise TaskNotFoundError(project_name, title)

        if WIP_LABEL_NAME in self.labels:
            card_to_update.add_label(self.labels[WIP_LABEL_NAME])

        return card_to_update, f"Task '{title}' in project '{project_name}' marked as in progress."

    def mark_as_completed(self, project_name, title):
        card_to_close = next((card for card in self.selected_board_list.list_cards() if card.name == title), None)
        if not card_to_close:
            raise TaskNotFoundError(project_name, title)

        if WIP_LABEL_NAME in self.labels and self.labels[WIP_LABEL_NAME] in card_to_close.labels:
            card_to_close.remove_label(self.labels[WIP_LABEL_NAME])
        card_to_close.set_due_complete()

        return card_to_close, f"Task '{title}' in project '{project_name}' has been completed."

    def update_task_description(self, project_name, title, description):
        card_to_update = next((card for card in self.selected_board_list.list_cards() if card.name == title), None)
        if not card_to_update:
            raise TaskNotFoundError(project_name, title)

        # Fetch current description to preserve it
        card_to_update.fetch()
        existing_description = card_to_update.description or ""

        # Add timestamp and new description
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if existing_description:
            updated_description = f"{existing_description}\n\n--- Updated on {timestamp} ---\n{description}"
        else:
            updated_description = f"--- Created on {timestamp} ---\n{description}"

        card_to_update.set_description(updated_description)

        return card_to_update, f"Description updated for task '{title}' in project '{project_name}'."

    def update_task_with_checklist(self, project_name, title, checklist_items):
        card_to_update = next((card for card in self.selected_board_list.list_cards() if card.name == title), None)
        if not card_to_update:
            raise TaskNotFoundError(project_name, title)

        # You can customize the checklist title if needed
        card_to_update.add_checklist(DEFAULT_CHECKLIST_NAME, checklist_items)

        return card_to_update, f"Checklist added to task '{title}' in project '{project_name}'."

    def complete_checklist_item(self, project_name, title, checklist_item_name):
        card_to_update = next((card for card in self.selected_board_list.list_cards() if card.name == title), None)
        if not card_to_update:
            raise TaskNotFoundError(project_name, title)

        card_to_update.fetch_checklists()
        for checklist in card_to_update.checklists:
            if checklist.name == DEFAULT_CHECKLIST_NAME:
                checklist.set_checklist_item(checklist_item_name, True)
                return (
                    card_to_update,
                    f"Checklist item '{checklist_item_name}' in task '{title}' in project '{project_name}' completed.",
                )

        raise ChecklistNotFoundError(DEFAULT_CHECKLIST_NAME, title)

    def get_next_unchecked_checklist_item(self, project_name, title):
        card_to_check = next((card for card in self.selected_board_list.list_cards() if card.name == title), None)
        if not card_to_check:
            raise TaskNotFoundError(project_name, title)

        card_to_check.fetch_checklists()

        for checklist in card_to_check.checklists:
            if checklist.name == DEFAULT_CHECKLIST_NAME:
                # Find the first unchecked item
                for item in checklist.items:
                    if not item.get("checked", False):
                        return (item, f"Next unchecked checklist item for task '{title}': {item['name']}")

                # If we get here, all items are checked
                raise ChecklistItemNotFoundError(title)

        # If we get here, no checklist was found
        raise ChecklistNotFoundError(DEFAULT_CHECKLIST_NAME, title)

    def get_tasks(self, project_name, filter_type="all"):
        cards = self.selected_board_list.list_cards()
        filtered_tasks = []
        wip_label = self.labels.get(WIP_LABEL_NAME)

        for card in cards:
            card.fetch()
            status = self._get_task_status(card, wip_label)

            if self._should_include_task(status, filter_type):
                filtered_tasks.append(self._create_task_dict(card, status))

        message = self._generate_result_message(filtered_tasks, filter_type, project_name)
        return filtered_tasks, message

    def delete_all_tasks(self, project_name: str) -> str:
        cards = self.selected_board_list.list_cards()
        for c in cards:
            c.delete()

        return f"All tasks in project '{project_name}' have been deleted."

    def _create_task_dict(self, card, status):
        """Create a task dictionary from a card."""
        return {"name": card.name, "description": card.description, "status": status, "id": card.id}

    def _get_task_status(self, card, wip_label):
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

    def _should_include_task(self, status, filter_type):
        """Check if a task should be included based on filter."""
        filter_conditions = {"all": True, "wip": status == "wip", "done": status == "done"}
        return filter_conditions.get(filter_type, False)

    def _generate_result_message(self, filtered_tasks, filter_type, project_name):
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

    def _create_default_labels(self):
        try:
            existing_labels = {label.name: label for label in self.selected_board.get_labels()}
            for label_name, label_color in DEFAULT_LABELS.items():
                if label_name not in existing_labels:
                    new_label = self.selected_board.add_label(label_name, label_color)
                    self.labels[label_name] = new_label
                else:
                    self.labels[label_name] = existing_labels[label_name]
        except Exception as e:
            print(f"Error creating default labels: {e}")

    def _find_existing_list(self, project_name):
        return next(
            (board_list for board_list in self.selected_board.all_lists() if board_list.name == project_name), None
        )


if __name__ == "__main__":
    # Testing
    tm = TrelloTaskManager()

    project_name = "Some Project"
    new_task_title = f"New Task at {datetime.datetime.now()}"
    tm.add_task(project_name, new_task_title, "This is a test task.")
    t1, _ = tm.get_next_task(project_name)
    print(t1.name)

    tm.update_task_with_checklist(project_name, new_task_title, ["Item 1", "Item 2", "Item 3"])
    print("Checklist set.")

    # Test getting next unchecked item
    _, next_item_msg = tm.get_next_unchecked_checklist_item(project_name, new_task_title)
    print(next_item_msg)

    _, m = tm.complete_checklist_item(project_name, new_task_title, "Item 1")
    print(m)

    # Test getting next unchecked item after completing one
    _, next_item_msg2 = tm.get_next_unchecked_checklist_item(project_name, new_task_title)
    print(next_item_msg2)

    # Test get_tasks with different filters
    print("\n=== Testing get_tasks method ===")

    # Get all tasks
    all_tasks, msg = tm.get_tasks(project_name, "all")
    print(f"All tasks: {msg}")
    for task in all_tasks:
        print(f"  - {task['name']} (Status: {task['status']})")

    # Mark task as in progress and test WIP filter
    tm.mark_as_in_progress(project_name, new_task_title)
    wip_tasks, msg = tm.get_tasks(project_name, "wip")
    print(f"\nWIP tasks: {msg}")
    for task in wip_tasks:
        print(f"  - {task['name']} (Status: {task['status']})")

    # Complete task and test done filter
    completed_card, _ = tm.mark_as_completed(project_name, new_task_title)
    done_tasks, msg = tm.get_tasks(project_name, "done")
    print(f"\nCompleted tasks: {msg}")
    for task in done_tasks:
        print(f"  - {task['name']} (Status: {task['status']})")

    # Test next available task
    _, m1 = tm.get_next_task(project_name)
    print(f"\nNext available task: {m1}")

    # Test update_task_description with timestamp preservation
    print("\n=== Testing update_task_description ===\n")
    test_task_title = f"Description Test Task at {datetime.datetime.now()}"
    tm.add_task(project_name, test_task_title, "Initial description")

    # Update description first time
    tm.update_task_description(project_name, test_task_title, "First update to the description")
    print("First description update completed")

    # Update description second time to test preservation
    tm.update_task_description(project_name, test_task_title, "Second update to the description")
    print("Second description update completed")

    input("Press Enter to continue...")
    tm.delete_all_tasks("Some project")
