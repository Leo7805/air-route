# AirRoute

**Airline Route Explorer & Travel Planner**

Explore aviation networks, discover airline routes, and organise personal travel plans.

## Overview

AirRoute is a RESTful application for exploring aviation data and managing personal travel plans.

It provides searchable airport, airline, and route information, along with user authentication, travel plan management, data imports, and export capabilities.

## Key Features

- **Aviation Explorer** — Browse and filter airports, airlines, and routes.
- **Travel Plans** — Create and manage private travel plans with selected routes.
- **Data Management** — Import and validate aviation datasets from CSV files.
- **User Management** — JWT authentication and role-based access control.
- **Data Export** — Export travel plans as JSON or PNG visualisations.

## Tech Stack

- **Backend:** Python, Flask-RESTX
- **Database:** SQLite, SQLAlchemy
- **Authentication:** JWT
- **Visualisation:** Matplotlib
- **Testing:** Pytest, Requests

## Data Source

AirRoute currently uses imported aviation datasets rather than live airline services.

The application is designed to support future integration with external aviation data providers. Live flight schedules, ticket prices, and bookings are not currently supported.

## Documentation

- [Project Documentation](docs/PROJECT.md)
- [API Reference](docs/API.md)

## Getting Started

Create a Python 3.13 environment and install the project:

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

Start the modular backend from the project root:

```bash
PYTHONPATH=. .venv/bin/python backend/run.py
```

The server listens on `http://127.0.0.1:5000` and exposes Swagger UI at `/`.

## Code quality

The repository includes shared formatting and linting configuration:

- **Prettier** — formats JavaScript, TypeScript, JSON, and other supported frontend files.
- **Black** — formats Python files in VS Code on save.
- **Ruff** — runs Python lint checks and import sorting from the command line.
- **VS Code** — the workspace settings enable format-on-save for Black and Prettier.

Install the corresponding tools in the project environment before using them:

```bash
python -m pip install ".[dev]"
```

Run them from the project root:

```bash
ruff format .
ruff check .
```

Run the complete isolated suite:

```bash
PYTHONPATH=. .venv/bin/python -m pytest -q
```

The adapters under `backend/tests/` preserve the original coursework
assertions while targeting the standalone modular application, temporary
SQLite databases, and an isolated HTTP server on port `5055`. Run HTTP
tests sequentially to avoid competing for that port.