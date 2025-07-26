import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("TrelloTaskManager")


def main():
    logging.info("Starting Trello Task Manager")


if __name__ == "__main__":
    main()
