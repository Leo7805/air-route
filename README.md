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

Local setup instructions will be finalised after the project structure is reorganised.

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

Start the backend from the project root:

```bash
python z5596858_api.py
```

The current test files are not yet safe to run directly: the unit test
module contains a test that initialises the default `assignment2.db`, and
the required `airports.csv`, `airlines.csv`, and `routes.csv` fixtures are
not present in this checkout. Before running tests, move database setup into
a temporary-database fixture and restore the CSV fixtures under a dedicated
test fixture directory.

After that preparation, run the unit tests with:

```bash
python -m pytest z5596858_test_unit.py -q
```

The HTTP integration tests also require the backend to be running at
`http://127.0.0.1:5000` in a separate terminal and should use an isolated
test database:

```bash
python -m pytest z5596858_tests.py -q
```