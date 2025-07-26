import os

from dotenv import load_dotenv
from trello import TrelloClient

load_dotenv()

TRELLO_API_KEY = os.getenv("TRELLO_API_KEY")
TRELLO_API_TOKEN = os.getenv("TRELLO_API_TOKEN")
BOARD_NAME_TO_MATCH = os.getenv("TRELLO_BOARD_NAME")


class TrelloTaskManager:
    selected_board_list = None

    def __init__(self):
        self.client = TrelloClient(
            api_key=TRELLO_API_KEY,
            api_secret=TRELLO_API_TOKEN,
        )
        self.selected_board = next(
            (board for board in self.client.list_boards() if board.name == BOARD_NAME_TO_MATCH), None
        )

    def add_task(self, project_name, title, description):
        self.selected_board_list = self._find_existing_list(project_name)

        if self.selected_board_list is None:
            self.selected_board_list = self.selected_board.add_list(project_name)

        card = self.selected_board_list.add_card(name=f"{title}", desc=description, position="bottom")
        return card

    def _find_existing_list(self, project_name):
        return next(
            (board_list for board_list in self.selected_board.all_lists() if board_list.name == project_name), None
        )


if __name__ == "__main__":
    # Testing
    tm = TrelloTaskManager()
    tm.add_task("Some project", "Project Title", "Project Description")
