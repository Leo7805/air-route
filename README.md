# AirRoute

Explore airline networks and organise personal travel plans.

![AirRoute Aviation Explorer](docs/screenshots/aviation-explorer.png)

AirRoute is a local full-stack application for browsing imported airport,
airline and route data, saving routes to private travel plans, and exporting
upcoming trips. Aviation records are demonstration data, not live flight schedules.

## Features

- JWT login with User and Admin roles
- Searchable, paginated airport, airline and route explorer with non-modal details
- Private travel-plan CRUD with route associations
- JSON exports and PNG timelines for upcoming plans
- Admin CSV imports with validation, atomic replacement and route protection
- Admin account creation, activation, deactivation and deletion
- Swagger/OpenAPI documentation for the Flask API

## Application preview

Captured from the real React frontend and Flask API using an isolated SQLite
database populated with the repository's CSV fixtures. The temporary User account
owns all three demonstration plans; each contains two valid routes.
Select a gallery image to view it at full resolution.

| Travel Plans | Admin Data Import |
| --- | --- |
| [![Travel Plans with two associated routes](docs/screenshots/travel-plans.png)](docs/screenshots/travel-plans.png) | [![Admin CSV import with three fixture files selected](docs/screenshots/data-import.png)](docs/screenshots/data-import.png) |
| Manage saved routes, browse the network, and export plans. | Select airport, airline and route CSVs with clear replacement rules. |

### Upcoming travel timeline

The unmodified PNG returned by `GET /travel-plans/export?format=image`, showing
three future plans and their associated routes.

![Backend-generated travel plans timeline](docs/screenshots/travel-timeline.png)

<details>
<summary>Route Details: inspect a route while keeping the table accessible</summary>

The non-modal drawer keeps the table at normal brightness and offers Add to Plan.

![Non-modal Route Details drawer](docs/screenshots/route-details.png)

</details>

## Stack and structure

- **Backend:** Python 3.13, Flask, Flask-RESTX, SQLAlchemy, SQLite
- **Frontend:** React, TypeScript, Vite
- **Authentication:** Flask-JWT-Extended and hashed passwords
- **PNG export:** Matplotlib
- **Tests:** pytest, requests, frontend TypeScript/ESLint checks

```text
backend/airroute/   Flask application, API resources, services and models
backend/tests/      Isolated unit and HTTP regression tests
frontend/src/       React application and API client
docs/               Project and API documentation
```

## Local setup

Prerequisites: Python 3.13, Node.js 20.19+ (20.x) or 22.12+ (Vite 7), npm,
and a shell that supports the activation command below.

From the repository root, create and activate the Python environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` installs the project and its existing `dev` extra from
`pyproject.toml`, including the backend tests and quality tools. Editable
installation is optional; it is not required to run the application. For a
runtime-only installation without test and quality tools, use `pip install .`
instead.

Start the local backend from the project root in the activated environment:

```bash
python3 backend/run.py
```

The API and Swagger UI are available at <http://127.0.0.1:5000/>.
The local entry point binds to loopback with the debugger disabled.

In a second terminal, start the frontend:

```bash
cd frontend
npm install
npm run dev
```

The web UI is available at <http://127.0.0.1:5173/> and proxies `/api` to the
backend.

### Database and local accounts

Direct startup creates `instance/airroute.db` at the repository root and, only
when the account table is empty, seeds `admin`/`admin` and `user`/`user` in local
development mode. These are disposable development accounts, not production
credentials. Import the CSV demonstration files in `backend/tests/fixtures/`
through **Data Import** to populate a new database.

Set `DATABASE_URL` to override the database location. Use an absolute SQLite
URI for an explicit path; relative SQLite URIs resolve beneath Flask's instance
directory. Direct startup uses the repository-root `instance/` directory.

### Environment and security

- `AIRROUTE_ENV`: `backend/run.py` defaults to `development`; the application
  factory defaults to `production`. Set `production` explicitly outside local
  development. Unknown mode names are rejected.
- `DATABASE_URL`: optional SQLAlchemy database URI; overrides the default.
- `PORT`: optional local backend port; defaults to `5000`. If changed, configure
  the frontend proxy for the same port.
- `JWT_SECRET_KEY`: use a high-entropy secret of at least 32 bytes in production.
  Non-development, non-test factory creation rejects missing or shorter values.
  Local development uses a random process-local secret when none is configured,
  so restarting the backend invalidates existing tokens.

Demo accounts are seeded only in development or explicit test mode; existing
accounts are never removed by startup. Production must use a separate database,
not a development database containing default accounts. Configure an explicit
production `DATABASE_URL`, provision an administrator securely, and keep the
production JWT secret persistent across restarts. The local Flask server is not
a production deployment; configuring production mode alone does not make it one.

## Importing CSV data

Sign in as an Admin, open **Data Import**, and select one or more supported
`airports.csv`, `airlines.csv` and `routes.csv` files. Each selected dataset
replaces its existing records; unselected datasets remain unchanged. Imports
are validated and atomic, and routes referenced by a travel plan cannot be
removed or modified.

## Verification

From the project root:

```bash
source .venv/bin/activate
python3 -m pytest -q
```

Frontend checks:

```bash
cd frontend
npm run lint
npm run typecheck
npm run build
npm run test:auth
```

## Limitations

The application uses imported demonstration data rather than live schedules.
It does not provide fares, booking, payments or a public deployment.

See [docs/PROJECT.md](docs/PROJECT.md) for architecture and [docs/API.md](docs/API.md)
for the concise endpoint index. Swagger remains the detailed API source of truth.
