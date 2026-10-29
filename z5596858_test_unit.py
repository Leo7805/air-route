
from passlib.hash import pbkdf2_sha256
from z5596858_api import app, db, Account, init_db, CSV_SCHEMAS
import pytest


def test_database_initialisation():
    # Initialise database
    init_db()

    with app.app_context():
        # Query default accounts
        admin = db.session.scalar(
            db.select(Account).filter_by(username="admin")
        )

        user = db.session.scalar(
            db.select(Account).filter_by(username="user")
        )

        # Check default accounts
        assert admin is not None
        assert user is not None

        assert admin.role == "Admin"
        assert user.role == "User"

        assert admin.is_active is True
        assert user.is_active is True

        # Verify password hashes
        assert pbkdf2_sha256.verify(
            "admin", admin.password_hash
        )

        assert pbkdf2_sha256.verify(
            "user", user.password_hash
        )


# ============================================================
# Requirement Set 2: Data Import
# ============================================================

# ------------------------------------------------------------
# 1. Database Model Tests
# ------------------------------------------------------------

def test_import_tables_created(isolated_import_api):
    """
    Verify that the Airport, Airline, and Route tables
    are created successfully in the SQLite database.
    """

    from sqlalchemy import inspect
    app = isolated_import_api.app
    db = isolated_import_api.db
    init_db = isolated_import_api.init_db

    # Initialise the database
    init_db()

    with app.app_context():
        # Retrieve all existing table names
        tables = set(inspect(db.engine).get_table_names())

        # Verify the required tables exist
        expected_tables = {
            "airports",
            "airlines",
            "routes"
        }

        assert expected_tables.issubset(tables), (
            f"Missing tables: {expected_tables - tables}"
        )



# ------------------------------------------------------------
# 2. CSV Parsing and Validation Tests
# ------------------------------------------------------------

def test_csv_parsing():
    """
    Verify that all three CSV datasets can be parsed.

    Checks that records are loaded and primary keys
    are converted to integers.
    """

    from pathlib import Path
    from z5596858_api import parse_csv

    primary_keys = {
        "airports": "airport_id",
        "airlines": "airline_id",
        "routes": "route_id",
    }

    for dataset, primary_key in primary_keys.items():

        # Read CSV file
        content = Path(f"{dataset}.csv").read_bytes()

        # Parse and validate
        records = parse_csv(dataset, content)

        assert len(records) > 0

        # Verify ID types
        for record in records:
            assert isinstance(record[primary_key], int)

        print(f"{dataset}: {len(records)} records parsed")



# ------------------------------------------------------------
# 3. Cross-Dataset Validation Tests
# ------------------------------------------------------------

def test_valid_references():
    """Verify that the provided CSV datasets have valid references."""

    from pathlib import Path
    from z5596858_api import parse_csv, validate_references

    airports = parse_csv("airports", Path("airports.csv").read_bytes())
    airlines = parse_csv("airlines", Path("airlines.csv").read_bytes())
    routes = parse_csv("routes", Path("routes.csv").read_bytes())

    # Should complete without raising an exception
    validate_references(airports, airlines, routes)


def test_missing_airline_reference():
    """Verify that routes cannot reference missing airlines."""

    import pytest
    from pathlib import Path
    from z5596858_api import (
        parse_csv,
        validate_references,
        ReferenceConflictError,
    )

    airports = parse_csv("airports", Path("airports.csv").read_bytes())
    airlines = parse_csv("airlines", Path("airlines.csv").read_bytes())
    routes = parse_csv("routes", Path("routes.csv").read_bytes())

    # Replace an existing airline ID with an invalid ID
    routes[0]["airline_id"] = 999999

    with pytest.raises(ReferenceConflictError):
        validate_references(airports, airlines, routes)


def test_mismatched_airport_iata():
    """Verify that airport IDs and IATA codes must match."""

    import pytest
    from pathlib import Path
    from z5596858_api import parse_csv, validate_references

    airports = parse_csv("airports", Path("airports.csv").read_bytes())
    airlines = parse_csv("airlines", Path("airlines.csv").read_bytes())
    routes = parse_csv("routes", Path("routes.csv").read_bytes())

    # Sydney Airport ID with an incorrect IATA code
    routes[0]["origin_iata"] = "XXX"

    with pytest.raises(ValueError, match="IATA mismatch"):
        validate_references(airports, airlines, routes)


@pytest.mark.parametrize("dataset,column,value", [
    ("airports", "latitude", "120"),
    ("airports", "longitude", "200"),
    ("routes", "stops", "-1"),
    ("routes", "airline_id", "-10"),
])
def test_invalid_csv_field_values(dataset, column, value):
    """Reject invalid numeric values in imported CSV records."""

    import csv
    import io
    from pathlib import Path
    from z5596858_api import parse_csv

    with Path(f"{dataset}.csv").open(
        encoding="utf-8-sig", newline=""
    ) as file:
        reader = csv.DictReader(file)
        columns = reader.fieldnames
        rows = list(reader)

    rows[0][column] = value

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)

    with pytest.raises(ValueError):
        parse_csv(dataset, output.getvalue().encode("utf-8"))


# ------------------------------------------------------------
# 4. Isolated Import Regression Tests
# ------------------------------------------------------------

@pytest.fixture
def isolated_import_api(tmp_path, monkeypatch):
    """Load the API with its relative SQLite path confined to a temporary folder."""
    import importlib.util
    import sys
    from pathlib import Path
    from uuid import uuid4
    import flask

    name = f"import_test_{uuid4().hex}"
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).with_name("z5596858_api.py")
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    original_flask = flask.Flask
    with monkeypatch.context() as setup:
        setup.setattr(flask, "Flask", lambda name: original_flask(
            name, instance_path=str(tmp_path)
        ))
        spec.loader.exec_module(module)

    with module.app.app_context():
        assert Path(module.db.engine.url.database) == tmp_path / "assignment2.db"
    module.init_db()
    yield module
    with module.app.app_context():
        module.db.session.remove()
        module.db.engine.dispose()


@pytest.fixture
def import_client(isolated_import_api):
    """Authenticate against the isolated database using the normal login API."""
    client = isolated_import_api.app.test_client()
    response = client.post(
        "/auth/login", json={"username": "admin", "password": "admin"}
    )
    assert response.status_code == 200, response.json
    return client, {"Authorization": f"Bearer {response.json['access_token']}"}


def import_csv_bytes(dataset, updates=None):
    """Read a provided CSV and optionally change the first row for a regression."""
    import csv
    import io
    from pathlib import Path

    with Path(__file__).with_name(f"{dataset}.csv").open(newline="") as file:
        reader = csv.DictReader(file)
        columns, rows = reader.fieldnames, list(reader)
    if updates:
        rows[0].update(updates)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode()


def upload_import(client, headers, datasets):
    """Send a real multipart request through Flask's isolated test client."""
    import io

    return client.post(
        "/imports", headers=headers, content_type="multipart/form-data",
        data={name: (io.BytesIO(content), f"{name}.csv")
              for name, content in datasets.items()}
    )


def add_travel_plan_route(module, route_id=1):
    """Create one plan-to-route reference in the isolated database."""
    from datetime import date

    with module.app.app_context():
        plan = module.TravelPlan(
            account_id=1,
            name="Protected route plan",
            departure_date=date(2026, 1, 1),
            return_date=date(2026, 1, 2),
        )
        module.db.session.add(plan)
        module.db.session.flush()
        module.db.session.add(module.TravelPlanRoute(
            plan_id=plan.plan_id,
            route_id=route_id,
        ))
        module.db.session.commit()


def import_snapshot(module):
    """Read all aviation records from the isolated database in primary-key order."""
    with module.app.app_context():
        return {
            name: sorted(module.load_dataset(name),
                         key=lambda row: row[module.PRIMARY_KEYS[name]])
            for name in module.DATASET_MODELS
        }


INTEGER_COLUMNS = [
    (dataset, column)
    for dataset, schema in CSV_SCHEMAS.items()
    for column, data_type in schema.items()
    if data_type is int
]


@pytest.mark.parametrize("dataset,column", INTEGER_COLUMNS)
@pytest.mark.parametrize("value", [-(2 ** 63) - 1, 2 ** 63])
def test_import_integer_overflow(
    isolated_import_api, import_client, dataset, column, value
):
    """Requirement 2: reject every overflowing integer with 400 before any changes."""
    module = isolated_import_api
    client, headers = import_client
    baseline = {name: import_csv_bytes(name) for name in module.DATASET_MODELS}
    assert upload_import(client, headers, baseline).status_code == 200
    before = import_snapshot(module)
    response = upload_import(client, headers, {
        dataset: import_csv_bytes(dataset, {column: str(value)})
    })
    assert response.status_code == 400, response.json
    message = response.json["message"]
    assert dataset in message and "row 2" in message and column in message
    assert "signed 64-bit" in message
    assert import_snapshot(module) == before
    # A subsequent import must still succeed after rejection.
    assert upload_import(client, headers, baseline).status_code == 200


@pytest.mark.parametrize("dataset,column,value", [
    (dataset, column, 2 ** 63 - 1) for dataset, column in INTEGER_COLUMNS
] + [("airports", "altitude", -(2 ** 63))])
def test_csv_integer_boundaries(dataset, column, value):
    """Requirement 2: accept SQLite integer endpoints where field constraints allow."""
    from z5596858_api import parse_csv

    records = parse_csv(dataset, import_csv_bytes(dataset, {column: str(value)}))
    assert records[0][column] == value


@pytest.mark.parametrize("first_dataset", ["routes", "airports"])
def test_concurrent_imports_preserve_references(
    isolated_import_api, import_client, monkeypatch, first_dataset
):
    """Requirement 2: concurrent route insertion and parent removal cannot both win."""
    import csv
    import io
    import threading
    from sqlalchemy import event

    module = isolated_import_api
    client, headers = import_client
    assert upload_import(client, headers, {
        name: import_csv_bytes(name) for name in ("airports", "airlines")
    }).status_code == 200
    # Remove airport 1, which the pending routes import references.
    reader = csv.DictReader(io.StringIO(import_csv_bytes("airports").decode()))
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=reader.fieldnames)
    writer.writeheader()
    writer.writerows(row for row in reader if row["airport_id"] != "1")
    uploads = {"airports": output.getvalue().encode(),
               "routes": import_csv_bytes("routes")}
    second_dataset = "airports" if first_dataset == "routes" else "routes"
    first_validated = threading.Event()
    second_lock_attempt = threading.Event()
    second_validated = threading.Event()
    release_first = threading.Event()
    responses, errors, connections = {}, [], set()
    validate = module.validate_references

    def gated_validation(*args):
        validate(*args)
        if threading.current_thread().name == "first-import":
            first_validated.set()
            assert release_first.wait(5), "Timed out waiting to release first import"
        else:
            second_validated.set()

    def observe_lock(connection, cursor, statement, parameters, context, many):
        if statement == "BEGIN IMMEDIATE":
            connections.add(id(connection.connection.dbapi_connection))
            if threading.current_thread().name == "second-import":
                second_lock_attempt.set()

    def run_import(label, dataset):
        try:
            responses[label] = upload_import(
                module.app.test_client(), headers, {dataset: uploads[dataset]}
            )
        except Exception as error:
            errors.append(error)

    monkeypatch.setattr(module, "validate_references", gated_validation)
    with module.app.app_context():
        engine = module.db.engine
    event.listen(engine, "before_cursor_execute", observe_lock)
    first = threading.Thread(target=run_import, args=("first", first_dataset),
                             name="first-import", daemon=True)
    second = threading.Thread(target=run_import, args=("second", second_dataset),
                              name="second-import", daemon=True)
    try:
        first.start()
        assert first_validated.wait(3), errors
        second.start()
        assert second_lock_attempt.wait(3), errors
        assert not second_validated.wait(0.1)
    finally:
        release_first.set()
        first.join(6)
        if second.ident is not None:
            second.join(6)
        event.remove(engine, "before_cursor_execute", observe_lock)
    assert not first.is_alive() and not second.is_alive()
    assert not errors, errors
    assert len(connections) == 2, "The imports must use independent connections"
    assert responses["first"].status_code == 200, responses["first"].json
    assert responses["second"].status_code == 409, responses["second"].json
    assert "does not exist" in responses["second"].json["message"]
    state = import_snapshot(module)
    validate(state["airports"], state["airlines"], state["routes"])
    if first_dataset == "routes":
        assert len(state["airports"]) == 46 and len(state["routes"]) == 260
    else:
        assert len(state["airports"]) == 45 and state["routes"] == []


def test_import_write_failure_rolls_back(isolated_import_api, import_client, monkeypatch):
    """Requirement 2: an INSERT failure restores deleted rows and releases the lock."""
    from sqlalchemy.exc import OperationalError

    module = isolated_import_api
    client, headers = import_client
    baseline = {name: import_csv_bytes(name) for name in module.DATASET_MODELS}
    assert upload_import(client, headers, baseline).status_code == 200
    before = import_snapshot(module)
    execute = module.db.session.execute

    def fail_insert(statement, *args, **kwargs):
        if getattr(statement, "is_insert", False):
            raise OperationalError("INSERT", {}, Exception("Injected failure"))
        return execute(statement, *args, **kwargs)

    with monkeypatch.context() as failure:
        failure.setattr(module.db.session, "execute", fail_insert)
        response = upload_import(client, headers, baseline)
    assert response.status_code == 500
    assert response.json["message"] == "Database import failed"
    assert import_snapshot(module) == before
    assert upload_import(client, headers, baseline).status_code == 200


def test_referenced_route_removed_returns_conflict(
    isolated_import_api, import_client
):
    module = isolated_import_api
    client, headers = import_client
    baseline = {name: import_csv_bytes(name) for name in module.DATASET_MODELS}
    assert upload_import(client, headers, baseline).status_code == 200
    add_travel_plan_route(module)

    import csv
    import io
    reader = csv.DictReader(io.StringIO(baseline["routes"].decode()))
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=reader.fieldnames)
    writer.writeheader()
    writer.writerows(row for row in reader if row["route_id"] != "1")

    response = upload_import(
        client, headers, {"routes": output.getvalue().encode()}
    )
    assert response.status_code == 409, response.json


def test_referenced_route_modified_returns_conflict(
    isolated_import_api, import_client
):
    module = isolated_import_api
    client, headers = import_client
    baseline = {name: import_csv_bytes(name) for name in module.DATASET_MODELS}
    assert upload_import(client, headers, baseline).status_code == 200
    add_travel_plan_route(module)

    response = upload_import(
        client, headers,
        {"routes": import_csv_bytes("routes", {"stops": "1"})}
    )
    assert response.status_code == 409, response.json


def test_identical_referenced_route_reimported_successfully(
    isolated_import_api, import_client
):
    module = isolated_import_api
    client, headers = import_client
    baseline = {name: import_csv_bytes(name) for name in module.DATASET_MODELS}
    assert upload_import(client, headers, baseline).status_code == 200
    add_travel_plan_route(module)

    response = upload_import(client, headers, {"routes": baseline["routes"]})
    assert response.status_code == 200, response.json
    with module.app.app_context():
        assert module.db.session.scalar(
            module.db.select(module.TravelPlanRoute.route_id)
        ) == 1


def test_unreferenced_routes_can_be_replaced(isolated_import_api, import_client):
    module = isolated_import_api
    client, headers = import_client
    baseline = {name: import_csv_bytes(name) for name in module.DATASET_MODELS}
    assert upload_import(client, headers, baseline).status_code == 200

    import csv
    import io
    reader = csv.DictReader(io.StringIO(baseline["routes"].decode()))
    first_route = next(reader)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=reader.fieldnames)
    writer.writeheader()
    writer.writerow(first_route)

    response = upload_import(
        client, headers, {"routes": output.getvalue().encode()}
    )
    assert response.status_code == 200, response.json
    with module.app.app_context():
        assert module.db.session.scalar(
            module.db.select(module.db.func.count()).select_from(module.Route)
        ) == 1


def test_failed_route_import_leaves_all_tables_unchanged(
    isolated_import_api, import_client
):
    module = isolated_import_api
    client, headers = import_client
    baseline = {name: import_csv_bytes(name) for name in module.DATASET_MODELS}
    assert upload_import(client, headers, baseline).status_code == 200
    add_travel_plan_route(module)
    with module.app.app_context():
        before = {
            name: sorted(
                module.load_dataset(name),
                key=lambda row: row[module.PRIMARY_KEYS[name]]
            )
            for name in module.DATASET_MODELS
        }
        before_plans = [
            (plan.plan_id, plan.account_id, plan.name,
             plan.departure_date, plan.return_date)
            for plan in module.db.session.scalars(
                module.db.select(module.TravelPlan)
            )
        ]
        before_links = [
            (link.plan_id, link.route_id)
            for link in module.db.session.scalars(
                module.db.select(module.TravelPlanRoute)
            )
        ]

    response = upload_import(
        client, headers,
        {"routes": import_csv_bytes("routes", {"stops": "1"})}
    )
    assert response.status_code == 409, response.json
    with module.app.app_context():
        assert {
            name: sorted(
                module.load_dataset(name),
                key=lambda row: row[module.PRIMARY_KEYS[name]]
            )
            for name in module.DATASET_MODELS
        } == before
        assert [
            (plan.plan_id, plan.account_id, plan.name,
             plan.departure_date, plan.return_date)
            for plan in module.db.session.scalars(
                module.db.select(module.TravelPlan)
            )
        ] == before_plans
        assert [
            (link.plan_id, link.route_id)
            for link in module.db.session.scalars(
                module.db.select(module.TravelPlanRoute)
            )
        ] == before_links


def test_import_lock_timeout(isolated_import_api, import_client):
    """Requirement 2: a busy database returns 500 unchanged and allows later imports."""
    from sqlalchemy import event

    module = isolated_import_api
    client, headers = import_client
    baseline = {name: import_csv_bytes(name) for name in module.DATASET_MODELS}
    assert upload_import(client, headers, baseline).status_code == 200
    before = import_snapshot(module)
    with module.app.app_context():
        engine = module.db.engine

    def short_timeout(connection, record):
        connection.execute("PRAGMA busy_timeout=50")

    event.listen(engine, "connect", short_timeout)
    try:
        with engine.connect() as writer:
            writer.exec_driver_sql("BEGIN IMMEDIATE")
            response = upload_import(client, headers, baseline)
            assert response.status_code == 500, response.json
            assert response.json["message"] == "Database import failed"
            writer.rollback()
    finally:
        event.remove(engine, "connect", short_timeout)
    assert import_snapshot(module) == before
    assert upload_import(client, headers, baseline).status_code == 200


def add_export_plan(module, account_id, name, departure_date, return_date=None):
    """Create an isolated travel plan for export boundary tests."""
    from datetime import timedelta

    with module.app.app_context():
        plan = module.TravelPlan(
            account_id=account_id,
            name=name,
            departure_date=departure_date,
            return_date=return_date or departure_date + timedelta(days=1),
        )
        module.db.session.add(plan)
        module.db.session.commit()
        return plan.plan_id


def login_isolated_account(module, client, username, password):
    """Authenticate an account through the normal login endpoint."""
    response = client.post(
        "/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.json
    token = response.json["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_image_export_without_future_plans_returns_meaningful_404(
    isolated_import_api, import_client
):
    module = isolated_import_api
    client, headers = import_client

    response = client.get(
        "/travel-plans/export",
        headers=headers,
        query_string={"format": "image"},
    )

    assert response.status_code == 404
    assert response.json["message"] == "No upcoming travel plans"


def test_image_export_selects_five_nearest_future_plans(
    isolated_import_api, import_client, monkeypatch
):
    from datetime import date, timedelta
    from io import BytesIO

    module = isolated_import_api
    client, headers = import_client
    today = date.today()
    plan_ids_by_offset = {
        offset: add_export_plan(
            module, 1, f"Future {offset}", today + timedelta(days=offset)
        )
        for offset in (70, 10, 50, 20, 40, 30)
    }
    add_export_plan(
        module, 1, "Past", today - timedelta(days=1)
    )
    selected = []

    def spy_generate(plans):
        selected.extend(plans)
        return BytesIO(b"mock-image")

    monkeypatch.setattr(module, "generate_travel_plans_image", spy_generate)
    response = client.get(
        "/travel-plans/export",
        headers=headers,
        query_string={"format": "image"},
    )

    assert response.status_code == 200
    assert response.data == b"mock-image"
    assert [plan.plan_id for plan in selected] == [
        plan_ids_by_offset[offset] for offset in (10, 20, 30, 40, 50)
    ]
    assert all(plan.departure_date > today for plan in selected)


def test_exports_are_isolated_to_authenticated_account(
    isolated_import_api, import_client, monkeypatch
):
    from datetime import date, timedelta
    from io import BytesIO

    module = isolated_import_api
    client, admin_headers = import_client
    user_headers = login_isolated_account(module, client, "user", "user")
    today = date.today()
    admin_plan_id = add_export_plan(
        module, 1, "Admin plan", today + timedelta(days=5)
    )
    user_plan_id = add_export_plan(
        module, 2, "User plan", today + timedelta(days=10)
    )

    user_json = client.get(
        "/travel-plans/export",
        headers=user_headers,
        query_string={"format": "json"},
    )
    assert user_json.status_code == 200
    assert [plan["plan_id"] for plan in user_json.json["plans"]] == [user_plan_id]

    admin_json = client.get(
        "/travel-plans/export",
        headers=admin_headers,
        query_string={"format": "json"},
    )
    assert admin_json.status_code == 200
    assert [plan["plan_id"] for plan in admin_json.json["plans"]] == [admin_plan_id]

    selected = []

    def spy_generate(plans):
        selected.extend(plans)
        return BytesIO(b"mock-image")

    monkeypatch.setattr(module, "generate_travel_plans_image", spy_generate)
    image_response = client.get(
        "/travel-plans/export",
        headers=user_headers,
        query_string={"format": "image"},
    )
    assert image_response.status_code == 200
    assert [plan.plan_id for plan in selected] == [user_plan_id]


def test_unsupported_export_format_returns_400(
    isolated_import_api, import_client
):
    module = isolated_import_api
    client, headers = import_client

    response = client.get(
        "/travel-plans/export",
        headers=headers,
        query_string={"format": "xml"},
    )

    assert response.status_code == 400
    assert response.json["message"] == "Unsupported export format"
