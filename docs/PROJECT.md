# AirRoute — Project Documentation

> **Product:** Airline Route Explorer & Travel Planner  
> **Tagline:** Explore airline networks. Organise your travel plans.  
> **Status:** Completed local full-stack application with a modular Flask backend and React frontend.

## 1. Project Goal

- **Problem:** Raw airport, airline and route datasets are difficult to explore. Users also need a straightforward way to organise selected routes into personal travel plans.
- **Target Users:**
  - **User:** Explore aviation data; create, manage and export their own travel plans.
  - **Admin:** Do the same for their own plans, plus manage accounts and import aviation datasets. Admins cannot access other users' private plans.
- **Goal:** Build a lightweight full-stack application for exploring aviation route networks and managing personal travel plans.
- **MVP Scope:** Searchable aviation catalogue, authenticated personal plans, validated CSV imports, JSON/PNG exports, documented REST API and a small web interface.
- **Non-goals:** Live schedules, real-time fares, ticket booking, payments, AI assistance, Google Maps and production-scale infrastructure.

**Data boundary:** The current aviation records are **CSV-imported demonstration data**, not a live airline service. Integration with an external aviation-data provider is a possible future extension, not a feature of this MVP.

## 2. Requirements

| ID | Feature | Priority | Acceptance Criteria | Status |
| --- | --- | --- | --- | --- |
| R1 | Authentication & Account Management | Must | JWT login; Admin account management; active-account and role checks; private plans remain private, including after account deletion. | Complete |
| R2 | Aviation Data Import | Must | Admin can import airport, airline and route CSV files; invalid imports roll back; routes referenced by plans cannot be removed or changed. | Complete |
| R3 | Aviation Explorer | Must | Authenticated users can browse, search, filter and inspect airports, airlines and routes, including related records. | Complete |
| R4 | Personal Travel Plans | Must | Users can create, list, view, update and delete their own plans; add/remove existing routes; validate date ranges and ownership. | Complete |
| R5 | Export | Must | Export only the current account's plans as self-contained JSON; display a PNG timeline of up to five nearest future plans; handle empty results. | Complete |
| R6 | API Documentation & Testing | Must | Document operations in Swagger/OpenAPI and verify normal, invalid and unauthorised requests with automated tests. | Complete |
| R7 | Lightweight Web Frontend | Must | React UI supports authentication, exploration, plan management, route selection, exports, imports and Admin account management through real API endpoints. | Complete |

## 3. Technical Design

### 3.1 Technology Stack

| Area | Technology | Status |
| --- | --- | --- |
| Frontend | React, TypeScript, Vite, Tailwind CSS | Implemented |
| Backend / REST | Python, Flask, Flask-RESTX | Implemented |
| Authentication | JWT (Flask-JWT-Extended), hashed passwords | Implemented |
| Database | SQLite, SQLAlchemy / Flask-SQLAlchemy | Implemented |
| Visualisation | Matplotlib (PNG timeline) | Implemented |
| Testing | pytest, requests | Implemented |
| Deployment | Local development; public deployment not required for MVP | Local only |

### 3.2 High-Level Architecture

```mermaid
flowchart LR
    Client["Swagger / HTTP Clients"] --> API["Flask-RESTX API"]
    UI["React Frontend"] -- "HTTP + JWT" --> API
    CSV["CSV Datasets"] --> Import["Import & Validation"]
    API --> Auth["Authentication & Accounts"]
    API --> Explorer["Aviation Explorer"]
    API --> Plans["Travel Plans & Export"]
    API --> Import
    Auth --> DB[(SQLite)]
    Explorer --> DB
    Plans --> DB
    Import --> DB
```

### 3.3 Modules & Project Structure

The backend uses a lightweight application package under `backend/airroute/`.
The application runs directly from this package. Regression adapters and CSV
fixtures live under `backend/tests/` and use isolated temporary databases.

| Module | Responsibility | Current / Planned Location |
| --- | --- | --- |
| Application factory | Flask, extensions, configuration and namespace registration | `backend/airroute/__init__.py` |
| Configuration and extensions | Runtime settings and unbound Flask extensions | `backend/airroute/config.py`, `backend/airroute/extensions.py` |
| Canonical models | Six SQLAlchemy models and relationships | `backend/airroute/models.py` |
| Authentication & Accounts | JWT login, roles, account management | `backend/airroute/auth.py`, `backend/airroute/api/auth.py`, `backend/airroute/api/accounts.py` |
| Aviation Catalogue | Airport, airline and route queries | `backend/airroute/aviation.py`, `backend/airroute/api/` |
| Data Import | CSV parsing, validation and transactional replacement | `backend/airroute/csv_import.py`, `backend/airroute/api/imports.py` |
| Travel Plans | Ownership, plan CRUD, route associations | `backend/airroute/travel_plans.py`, `backend/airroute/api/travel_plans.py` |
| Export | JSON and PNG generation | `backend/airroute/exports.py`, `backend/airroute/api/travel_plans.py` |
| Web UI | Browser-based interaction with the existing API | `frontend/` |
| Tests | Isolated unit and HTTP regression adapters | `backend/tests/` |

**Documentation rule:** Record major modules and key entry points only. Update this section and the architecture diagram when responsibilities or module relationships change—not whenever a file or function changes.

### 3.4 Database Design

**Core entities:** `Account`, `Airport`, `Airline`, `Route`, `TravelPlan`, `TravelPlanRoute`.

```mermaid
erDiagram
    ACCOUNT ||--o{ TRAVEL_PLAN : owns
    TRAVEL_PLAN ||--o{ TRAVEL_PLAN_ROUTE : contains
    ROUTE ||--o{ TRAVEL_PLAN_ROUTE : selected_in
    AIRLINE ||--o{ ROUTE : operates
    AIRPORT ||--o{ ROUTE : departure
    AIRPORT ||--o{ ROUTE : arrival
```

- **Ownership:** Each travel plan belongs to one account. Only its owner can access or modify it, including when the owner is an Admin.
- **Many-to-many:** A plan contains multiple routes; a route can appear in multiple plans. `TravelPlanRoute` is the junction table with a composite primary key (`plan_id`, `route_id`).
- **Local database:** Direct startup uses repository-root `instance/airroute.db`; `DATABASE_URL` can select another database. Existing database files are never automatically renamed or migrated.
- **Startup safety:** The local entry point enables development account seeding only for an empty account table; production mode requires an explicit JWT secret and never seeds demo accounts.
- **Integrity:** Plan return date cannot precede departure date. Duplicate route associations are rejected. CSV imports are atomic and protect routes already referenced by travel plans.
- **Implementation note:** The airline/airport connections shown above are **logical references** validated by application code; the original `Route` model does not declare database foreign keys for those IDs.

### 3.5 Design Decisions (ADR Lite)

#### D001 — SQLite + SQLAlchemy

- **Decision:** Store data locally in SQLite and access it using SQLAlchemy.
- **Reason:** Simple setup and persistence for a small self-contained application.
- **Alternatives:** PostgreSQL or MySQL.
- **Trade-off:** Limited concurrency and deployment flexibility compared with a server database.

#### D002 — Flask-RESTX REST API

- **Decision:** Use Flask-RESTX with Swagger/OpenAPI documentation.
- **Reason:** A small HTTP API with explicit endpoint contracts and interactive documentation.
- **Alternatives:** FastAPI, Django REST Framework.
- **Trade-off:** Request validation and service separation require deliberate implementation.

#### D003 — JWT Authentication and Per-Account Ownership

- **Decision:** Use JWT for protected API calls and enforce ownership on each plan query or mutation.
- **Reason:** Separate account administration from users' private travel data.
- **Alternatives:** Server-side sessions.
- **Trade-off:** Token expiry and account-state changes require additional handling.

#### D004 — Controlled CSV Import

- **Decision:** Validate CSV datasets and replace data transactionally, preserving referenced routes.
- **Reason:** Prevent partial imports and unexpected changes to saved travel plans.
- **Alternatives:** Direct edits or live third-party API synchronisation.
- **Trade-off:** Imported datasets require manual updates and do not represent live flight information.

#### D005 — Route Junction Table

- **Decision:** Model saved routes using `TravelPlanRoute` rather than embedding route IDs in a plan field.
- **Reason:** Support many-to-many relationships and prevent duplicate plan-route pairs.
- **Alternatives:** Serialised route-ID lists or copying route records into plans.
- **Trade-off:** Additional joins and referential-integrity checks.

## 4. API Design

See **[API Reference](API.md)** for the concise endpoint index. Swagger/OpenAPI is
the detailed source of truth for request and response schemas.

## 5. Testing & Delivery

- **Unit Tests:** Isolated pytest tests for validation, database rules and export boundaries.
- **API / Integration Tests:** `requests`-based HTTP tests for authentication, imports, exploration, travel plans, exports and failure cases. The suite uses temporary SQLite databases and verifies normal, invalid, ownership and role-based requests.
- **Frontend checks:** ESLint, TypeScript type checking, Vite production build and a headless Chrome authentication workflow.
- **Manual Acceptance Checks:** Log in; browse an airport, airline and route; create a plan; add a route; export JSON/PNG; confirm cross-account privacy; verify PNG display.
- **How to Run:**

  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  python3 backend/run.py
  # In another terminal, activate the same virtual environment:
  source .venv/bin/activate
  python3 -m pytest -q
  ```

  Swagger UI: `http://127.0.0.1:5000/`. The test adapters start the
  application with temporary SQLite databases and an isolated HTTP server.

- **Definition of Done:** The React frontend covers the existing API operations, documentation has reproducible setup instructions, and automated checks pass against isolated databases.
- **Known Limitations:** Imported demo data only; no live flight schedules, fares or booking; local runtime is the primary target; no hosted deployment is provided. Real application screenshots are included in `docs/screenshots/` and the README.
- **Delivery Rule:** Preserve existing endpoint behaviour and tests while keeping the modular application lightweight.
