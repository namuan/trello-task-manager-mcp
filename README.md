# Trello Task Manager MCP

[Video Placeholder]

LLM Task management System that integrates as an MCP Server and uses Trello for managing tasks/cards.

## Features

- Create and manage tasks in Trello boards
- Mark tasks as in-progress or completed
- Get next available task

## Prerequisites

- Python 3.10 or higher
- A Trello account
- Trello API key and token

## Installation

1. Clone the repository:

   ```bash
   git clone [your-repository-url]
   cd trello-task-manager-mcp
   ```

2. Install dependencies:

   ```bash
   pip install -e .
   ```

3. Create a `.env` file in the project root with your Trello credentials:
   ```env
   TRELLO_API_KEY=your_api_key
   TRELLO_API_TOKEN=your_api_token
   TRELLO_BOARD_NAME=your_board_name
   HOST=127.0.0.1  # Optional, defaults to 127.0.0.1
   PORT=8050      # Optional, defaults to 8050
   ```

## MCP Integration

Add the following entry to your MCP configuration:

```json
"trello-task-manager": {
    "url": "http://localhost:8050/sse",
    "type": "sse"
}
```

## Usage

1. Start the Trello Task Manager:

   ```bash
   python -m trello_tm.main_cli
   ```

2. Use MCP commands to manage tasks:
   - `add_task`: Create a new task
   - `get_next_available_task`: Get the next available task
   - `mark_as_in_progress`: Mark a task as in progress
   - `mark_as_completed`: Mark a task as completed

## Development

### Setup Development Environment

This project uses `uv` for dependency management. Run the following command to set up your development environment:

```bash
make install
```

This will:

- Create a virtual environment using uv
- Install project dependencies
- Set up pre-commit hooks

### Development Commands

The project includes several helpful make commands:

```bash
make help     # Show all available commands with descriptions
make check    # Run code quality tools (lock file check and pre-commit)
make run      # Run the application
make build    # Build wheel file
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
