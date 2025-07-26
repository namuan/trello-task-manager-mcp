import os

from dotenv import load_dotenv
from trello import TrelloClient

load_dotenv()

TRELLO_API_KEY = os.getenv("TRELLO_API_KEY")
TRELLO_API_TOKEN = os.getenv("TRELLO_API_TOKEN")
BOARD_NAME_TO_MATCH = os.getenv("TRELLO_BOARD_NAME")


class TaskNotFoundError(Exception):
    """Exception raised when a task is not found in a project."""

    def __init__(self, project_name, title):
        self.project_name = project_name
        self.title = title
        super().__init__(f"Task '{title}' not found in project '{project_name}'.")


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
        if self.selected_board:
            self._create_default_labels()

    def add_task(self, project_name, title, description):
        self.selected_board_list = self._find_existing_list(project_name)

        if self.selected_board_list is None:
            self.selected_board_list = self.selected_board.add_list(project_name)

        card = self.selected_board_list.add_card(name=f"{title}", desc=description, position="bottom")

        if not self.wip_label:
            wip_label = next((label for label in self.selected_board.get_labels() if label.name == "WIP"), None)
            self.wip_label = wip_label

        card.add_label(self.wip_label)

        return card

    def mark_as_completed(self, project_name, title):
        card_to_close = next((card for card in self.selected_board_list.list_cards() if card.name == title), None)
        if not card_to_close:
            raise TaskNotFoundError(project_name, title)

        card_to_close.remove_label(self.wip_label)
        card_to_close.set_due_complete()

        return f"Task '{title}' in project '{project_name}' has been closed."

    def _create_default_labels(self):
        try:
            existing_labels = {label.name for label in self.selected_board.get_labels()}
            default_labels = {"WIP": "blue"}

            for label_name, label_color in default_labels.items():
                if label_name not in existing_labels:
                    self.selected_board.add_label(label_name, label_color)
        except Exception as e:
            print(f"Error creating default labels: {e}")

    def _find_existing_list(self, project_name):
        return next(
            (board_list for board_list in self.selected_board.all_lists() if board_list.name == project_name), None
        )


if __name__ == "__main__":
    # Testing
    tm = TrelloTaskManager()
    tm.add_task("Some project", "Project Title", "Project Description")
    tm.mark_as_completed("Some project", "Project Title")
