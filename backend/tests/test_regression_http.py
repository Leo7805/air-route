import csv
import io
import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest
import requests

pytestmark = pytest.mark.usefixtures("isolated_http_server")

BASE_URL = "http://127.0.0.1:5000"


# ============================================================
# Requirement Set 1: User Management and Access Control
# ============================================================

# Test Helper: Login and Authorization

def login(username, password):
    """
    Authenticate a user and return the JWT Authorization header.

    This helper is shared by tests requiring an authenticated user.
    """

    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={
            "username": username,
            "password": password
        },
        timeout=5
    )

    assert response.status_code == 200, response.text

    token = response.json()["access_token"]

    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def account_cleanup():
    """Remove only accounts registered by the current test, even on failure."""
    accounts = []
    yield accounts
    if accounts:
        headers = login("admin", "admin")
        for account in reversed(accounts):
            response = requests.get(
                f"{BASE_URL}/accounts", headers=headers, timeout=5
            )
            assert response.status_code == 200, response.text
            # An earlier deletion may have allowed SQLite to reuse this ID.
            if any(item["id"] == account["id"] and
                   item["username"] == account["username"]
                   for item in response.json()):
                deleted = requests.delete(
                    f"{BASE_URL}/accounts/{account['id']}",
                    headers=headers, timeout=5
                )
                assert deleted.status_code == 204, deleted.text


@pytest.fixture
def temporary_account(account_cleanup):
    """Create an independent User account and register it for cleanup."""
    headers = login("admin", "admin")
    response = requests.post(
        f"{BASE_URL}/accounts", headers=headers,
        json={"username": f"test_{uuid4().hex}", "password": "TestPassword123"},
        timeout=5
    )
    assert response.status_code == 201, response.text
    account_cleanup.append(response.json())
    return response.json()


# ------------------------------------------------------------
# 1. Authentication Tests
# ------------------------------------------------------------

def test_login_admin():
    """Verify that Admin can log in and retrieve account details."""

    headers = login("admin", "admin")

    response = requests.get(
        f"{BASE_URL}/auth/me",
        headers=headers,
        timeout=5
    )

    assert response.status_code == 200, response.text
    assert response.json()["username"] == "admin"
    assert response.json()["role"] == "Admin"


def test_login_user():
    """Verify that User can log in and retrieve account details."""

    headers = login("user", "user")

    response = requests.get(
        f"{BASE_URL}/auth/me",
        headers=headers,
        timeout=5
    )

    assert response.status_code == 200, response.text
    assert response.json()["username"] == "user"
    assert response.json()["role"] == "User"


def test_missing_token():
    """Verify that requests without a JWT are rejected with HTTP 401."""

    response = requests.get(
        f"{BASE_URL}/auth/me",
        timeout=5
    )

    assert response.status_code == 401, response.text


def test_invalid_token():
    """Verify that malformed JWT tokens are rejected with HTTP 422."""

    response = requests.get(
        f"{BASE_URL}/auth/me",
        headers={"Authorization": "Bearer invalid-token"},
        timeout=5
    )

    # Flask-JWT-Extended defaults to HTTP 422 for malformed JWTs.
    assert response.status_code == 422, response.text


# ------------------------------------------------------------
# 2. User Account Management Tests
# ------------------------------------------------------------

def test_admin_can_list_accounts():
    """Requirement 1: Admin can retrieve all accounts."""

    headers = login("admin", "admin")

    response = requests.get(
        f"{BASE_URL}/accounts",
        headers=headers,
        timeout=5
    )

    assert response.status_code == 200, response.text

    accounts = response.json()

    assert isinstance(accounts, list)

    usernames = {account["username"] for account in accounts}

    assert "admin" in usernames
    assert "user" in usernames

    # Password hashes must never be exposed
    for account in accounts:
        assert "password" not in account
        assert "password_hash" not in account
        assert "id" in account
        assert "role" in account
        assert "is_active" in account


def test_user_cannot_list_accounts():
    """Requirement 1: Regular users cannot list accounts."""

    headers = login("user", "user")

    response = requests.get(
        f"{BASE_URL}/accounts",
        headers=headers,
        timeout=5
    )

    assert response.status_code == 403, response.text


def test_unauthenticated_cannot_list_accounts():
    """Requirement 1: Unauthenticated requests are rejected."""

    response = requests.get(
        f"{BASE_URL}/accounts",
        timeout=5
    )

    assert response.status_code == 401, response.text



def test_admin_can_create_user(account_cleanup):
    """Verify that Admin can create a new active User account."""

    headers = login("admin", "admin")
    username = f"test_{uuid4().hex[:12]}"

    response = requests.post(
        f"{BASE_URL}/accounts",
        headers=headers,
        json={
            "username": username,
            "password": "TestPassword123"
        },
        timeout=5
    )

    assert response.status_code == 201, response.text
    account_cleanup.append(response.json())

    account = response.json()

    assert account["username"] == username
    assert account["role"] == "User"
    assert account["is_active"] is True
    assert isinstance(account["id"], int)
    assert "password_hash" not in account

    # Verify that the new account can log in
    new_headers = login(username, "TestPassword123")

    me = requests.get(
        f"{BASE_URL}/auth/me",
        headers=new_headers,
        timeout=5
    )

    assert me.status_code == 200, me.text
    assert me.json()["username"] == username


def test_user_cannot_create_account():
    """Verify that regular users cannot create accounts."""

    headers = login("user", "user")

    response = requests.post(
        f"{BASE_URL}/accounts",
        headers=headers,
        json={
            "username": f"test_{uuid4().hex[:12]}",
            "password": "TestPassword123"
        },
        timeout=5
    )

    assert response.status_code == 403, response.text


def test_duplicate_username(account_cleanup):
    """Verify that duplicate usernames are rejected."""

    headers = login("admin", "admin")
    username = f"test_{uuid4().hex[:12]}"

    payload = {
        "username": username,
        "password": "TestPassword123"
    }

    first = requests.post(
        f"{BASE_URL}/accounts",
        headers=headers,
        json=payload,
        timeout=5
    )

    assert first.status_code == 201, first.text
    account_cleanup.append(first.json())

    second = requests.post(
        f"{BASE_URL}/accounts",
        headers=headers,
        json=payload,
        timeout=5
    )

    assert second.status_code == 409, second.text


def test_missing_username():
    """Verify that account creation requires a username."""

    headers = login("admin", "admin")

    response = requests.post(
        f"{BASE_URL}/accounts",
        headers=headers,
        json={"password": "TestPassword123"},
        timeout=5
    )

    assert response.status_code == 400, response.text


def test_admin_can_deactivate_and_reactivate_user(account_cleanup):
    """
    Verify that Admin can deactivate and reactivate a User.

    A deactivated account must be denied access even when
    the user already holds a valid JWT.
    """

    # Create a test account
    admin_headers = login("admin", "admin")
    username = f"test_{uuid4().hex[:12]}"
    password = "TestPassword123"

    created = requests.post(
        f"{BASE_URL}/accounts",
        headers=admin_headers,
        json={"username": username, "password": password},
        timeout=5
    )

    assert created.status_code == 201, created.text
    account_cleanup.append(created.json())
    account_id = created.json()["id"]

    # Log in before deactivation
    user_headers = login(username, password)

    # Deactivate the user
    response = requests.patch(
        f"{BASE_URL}/accounts/{account_id}",
        headers=admin_headers,
        json={"is_active": False},
        timeout=5
    )

    assert response.status_code == 200, response.text
    assert response.json()["is_active"] is False

    # The existing JWT must no longer grant access
    blocked = requests.get(
        f"{BASE_URL}/auth/me",
        headers=user_headers,
        timeout=5
    )

    assert blocked.status_code == 403, blocked.text

    # Deactivated user cannot log in again
    login_response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"username": username, "password": password},
        timeout=5
    )

    assert login_response.status_code == 403

    # Reactivate the user
    response = requests.patch(
        f"{BASE_URL}/accounts/{account_id}",
        headers=admin_headers,
        json={"is_active": True},
        timeout=5
    )

    assert response.status_code == 200, response.text
    assert response.json()["is_active"] is True

    # The user can log in again
    restored_headers = login(username, password)

    restored = requests.get(
        f"{BASE_URL}/auth/me",
        headers=restored_headers,
        timeout=5
    )

    assert restored.status_code == 200, restored.text



def test_user_cannot_update_account_status():
    """Verify that regular users cannot change account status."""

    headers = login("user", "user")

    me = requests.get(
        f"{BASE_URL}/auth/me",
        headers=headers,
        timeout=5
    )

    assert me.status_code == 200, me.text
    account_id = me.json()["id"]

    response = requests.patch(
        f"{BASE_URL}/accounts/{account_id}",
        headers=headers,
        json={"is_active": False},
        timeout=5
    )

    assert response.status_code == 403, response.text



def test_admin_cannot_deactivate_admin():
    """Verify that the Admin account cannot be deactivated."""

    headers = login("admin", "admin")

    me = requests.get(
        f"{BASE_URL}/auth/me",
        headers=headers,
        timeout=5
    )

    assert me.status_code == 200, me.text
    admin_id = me.json()["id"]

    response = requests.patch(
        f"{BASE_URL}/accounts/{admin_id}",
        headers=headers,
        json={"is_active": False},
        timeout=5
    )

    assert response.status_code == 403, response.text

    # Admin should remain active
    verify = requests.get(
        f"{BASE_URL}/auth/me",
        headers=headers,
        timeout=5
    )

    assert verify.status_code == 200, verify.text
    assert verify.json()["is_active"] is True


def test_admin_can_delete_user(account_cleanup):
    """
    Verify that Admin can delete a User account.

    Deleted users must lose access to protected APIs
    and must not be able to log in again.
    """

    admin_headers = login("admin", "admin")
    username = f"test_{uuid4().hex[:12]}"
    password = "TestPassword123"

    # Create a user
    created = requests.post(
        f"{BASE_URL}/accounts",
        headers=admin_headers,
        json={
            "username": username,
            "password": password
        },
        timeout=5
    )

    assert created.status_code == 201, created.text
    account_cleanup.append(created.json())
    account_id = created.json()["id"]

    # Obtain a JWT before deleting the account
    user_headers = login(username, password)

    # Delete the user
    deleted = requests.delete(
        f"{BASE_URL}/accounts/{account_id}",
        headers=admin_headers,
        timeout=5
    )

    assert deleted.status_code == 204, deleted.text
    assert deleted.content == b""

    # Existing JWT must no longer grant access
    response = requests.get(
        f"{BASE_URL}/auth/me",
        headers=user_headers,
        timeout=5
    )

    assert response.status_code == 401, response.text

    # Deleted account cannot log in again
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={
            "username": username,
            "password": password
        },
        timeout=5
    )

    assert response.status_code == 401, response.text

    # Deleting the same account again returns 404
    response = requests.delete(
        f"{BASE_URL}/accounts/{account_id}",
        headers=admin_headers,
        timeout=5
    )

    assert response.status_code == 404, response.text


def test_deleting_user_removes_private_plans_but_preserves_routes(
    account_cleanup, imported_baseline
):
    """RS1/RS4: Deleting a user removes plans without deleting aviation routes."""
    admin_headers = login("admin", "admin")
    username = f"test_{uuid4().hex[:12]}"
    password = "TestPassword123"

    created = requests.post(
        f"{BASE_URL}/accounts",
        headers=admin_headers,
        json={"username": username, "password": password},
        timeout=5
    )
    assert created.status_code == 201, created.text
    account_cleanup.append(created.json())
    user_headers = login(username, password)

    plan = requests.post(
        f"{BASE_URL}/travel-plans",
        headers=user_headers,
        json={
            "name": "Deleted user's private plan",
            "departure_date": "2027-01-01",
            "return_date": "2027-01-02",
        },
        timeout=10
    )
    assert plan.status_code == 201, plan.text
    plan_id = plan.json()["plan_id"]
    linked = requests.post(
        f"{BASE_URL}/travel-plans/{plan_id}/routes",
        headers=user_headers,
        json={"route_id": 1},
        timeout=10
    )
    assert linked.status_code == 201, linked.text

    deleted = requests.delete(
        f"{BASE_URL}/accounts/{created.json()['id']}",
        headers=admin_headers,
        timeout=10
    )
    assert deleted.status_code == 204, deleted.text

    assert requests.get(
        f"{BASE_URL}/travel-plans/{plan_id}",
        headers=user_headers,
        timeout=10
    ).status_code == 401

    replacement = requests.post(
        f"{BASE_URL}/accounts",
        headers=admin_headers,
        json={"username": username, "password": password},
        timeout=5
    )
    assert replacement.status_code == 201, replacement.text
    replacement_headers = login(username, password)
    exported = requests.get(
        f"{BASE_URL}/travel-plans/export",
        headers=replacement_headers,
        params={"format": "json"},
        timeout=10
    )
    assert exported.status_code == 200, exported.text
    assert exported.json()["plans"] == []

    routes = requests.get(
        f"{BASE_URL}/routes/1",
        headers=replacement_headers,
        timeout=10
    )
    assert routes.status_code == 200, routes.text
    account_cleanup.append(replacement.json())


def test_user_cannot_delete_account():
    """Verify that regular users cannot delete accounts."""

    headers = login("user", "user")

    me = requests.get(
        f"{BASE_URL}/auth/me",
        headers=headers,
        timeout=5
    )

    assert me.status_code == 200, me.text
    account_id = me.json()["id"]

    response = requests.delete(
        f"{BASE_URL}/accounts/{account_id}",
        headers=headers,
        timeout=5
    )

    assert response.status_code == 403, response.text



def test_admin_cannot_delete_admin():
    """Verify that the Admin account cannot be deleted."""

    headers = login("admin", "admin")

    me = requests.get(
        f"{BASE_URL}/auth/me",
        headers=headers,
        timeout=5
    )

    assert me.status_code == 200, me.text
    admin_id = me.json()["id"]

    response = requests.delete(
        f"{BASE_URL}/accounts/{admin_id}",
        headers=headers,
        timeout=5
    )

    assert response.status_code == 403, response.text

    # Verify that Admin still exists
    response = requests.get(
        f"{BASE_URL}/auth/me",
        headers=headers,
        timeout=5
    )

    assert response.status_code == 200, response.text
    assert response.json()["role"] == "Admin"


@pytest.mark.parametrize("field,value", [
    ("username", ""), ("username", "   "), ("username", "x" * 101),
    ("username", None), ("username", 12), ("username", True),
    ("username", []), ("username", {}),
    ("password", ""), ("password", " \t"), ("password", "x" * 129),
    ("password", None), ("password", 12), ("password", False),
    ("password", []), ("password", {}),
])
def test_invalid_account_values(field, value, account_cleanup):
    """Reject invalid credentials without creating an account or returning 500."""
    payload = {"username": f"test_{uuid4().hex}", "password": "TestPassword123"}
    payload[field] = value
    response = requests.post(
        f"{BASE_URL}/accounts", headers=login("admin", "admin"),
        json=payload, timeout=5
    )
    if response.status_code == 201:
        account_cleanup.append(response.json())
    assert response.status_code == 400, response.text


@pytest.mark.parametrize("payload", [
    {}, {"username": "missing_password"},
    {"username": "forbidden_role", "password": "TestPassword123", "role": "Admin"},
    {"username": "forbidden_status", "password": "TestPassword123", "is_active": False},
    [{"username": "array_account", "password": "TestPassword123"}],
])
def test_invalid_account_request(payload, account_cleanup):
    """Require credentials in a JSON object and reject extra fields."""
    if isinstance(payload, dict) and "username" in payload:
        payload = dict(payload, username=f"test_{uuid4().hex}")
    response = requests.post(
        f"{BASE_URL}/accounts", headers=login("admin", "admin"),
        json=payload, timeout=5
    )
    if response.status_code == 201:
        account_cleanup.append(response.json())
    assert response.status_code == 400, response.text


@pytest.mark.parametrize("value", [None, 0, 1, "false", "true", [], {}])
def test_invalid_account_status(value, temporary_account):
    """Status updates require an actual JSON boolean and preserve the account."""
    headers = login("admin", "admin")
    response = requests.patch(
        f"{BASE_URL}/accounts/{temporary_account['id']}", headers=headers,
        json={"is_active": value}, timeout=5
    )
    assert response.status_code == 400, response.text
    accounts = requests.get(f"{BASE_URL}/accounts", headers=headers, timeout=5)
    assert accounts.status_code == 200, accounts.text
    assert next(a for a in accounts.json()
                if a["id"] == temporary_account["id"])["is_active"] is True


@pytest.mark.parametrize("payload", [{}, {"is_active": True, "role": "Admin"},
                                    [{"is_active": True}]])
def test_invalid_status_request(payload, temporary_account):
    """Reject missing status, additional fields, and non-object payloads."""
    response = requests.patch(
        f"{BASE_URL}/accounts/{temporary_account['id']}",
        headers=login("admin", "admin"), json=payload, timeout=5
    )
    assert response.status_code == 400, response.text


@pytest.mark.parametrize("method", ["patch", "delete"])
@pytest.mark.parametrize("oversized", [False, True])
def test_nonexistent_account(method, oversized):
    """Return 404 when an administrator targets a missing account."""
    headers = login("admin", "admin")
    accounts = requests.get(f"{BASE_URL}/accounts", headers=headers, timeout=5)
    assert accounts.status_code == 200, accounts.text
    missing_id = 10 ** 30 if oversized else max(a["id"] for a in accounts.json()) + 1000000
    response = requests.request(
        method, f"{BASE_URL}/accounts/{missing_id}", headers=headers,
        **({"json": {"is_active": False}} if method == "patch" else {}),
        timeout=5
    )
    assert response.status_code == 404, response.text


@pytest.mark.parametrize("method,path,payload", [
    ("get", "/auth/me", None), ("get", "/accounts", None),
    ("post", "/accounts", {"username": "permission_check", "password": "test"}),
    ("patch", "/accounts/1", {"is_active": False}),
    ("delete", "/accounts/1", None),
])
@pytest.mark.parametrize("headers,expected", [
    ({}, 401), ({"Authorization": "Bearer invalid-token"}, 422)
])
def test_protected_endpoint_authentication(method, path, payload, headers, expected):
    """Apply missing and malformed JWT handling to every protected operation."""
    response = requests.request(
        method, f"{BASE_URL}{path}", headers=headers,
        **({"json": payload} if payload is not None else {}), timeout=5
    )
    assert response.status_code == expected, response.text


@pytest.mark.parametrize("payload,expected", [
    ({"username": "admin", "password": "incorrect"}, 401),
    ({"username": "admin", "password": "x" * 5000}, 401),
    ({"username": "admin"}, 400),
    ({"username": None, "password": "admin"}, 400),
    ({"username": "admin", "password": 42}, 400),
    ([{"username": "admin", "password": "admin"}], 400),
])
def test_invalid_login(payload, expected):
    """Reject invalid login requests consistently without requiring a JWT."""
    response = requests.post(f"{BASE_URL}/auth/login", json=payload, timeout=5)
    assert response.status_code == expected, response.text


def test_deleted_token_cannot_access_replacement(temporary_account, account_cleanup):
    """A deleted account's token must remain invalid after SQLite ID reuse."""
    old_headers = login(temporary_account["username"], "TestPassword123")
    headers = login("admin", "admin")
    deleted = requests.delete(
        f"{BASE_URL}/accounts/{temporary_account['id']}", headers=headers, timeout=5
    )
    assert deleted.status_code == 204, deleted.text
    created = requests.post(
        f"{BASE_URL}/accounts", headers=headers,
        json={"username": f"test_{uuid4().hex}", "password": "TestPassword123"},
        timeout=5
    )
    assert created.status_code == 201, created.text
    account_cleanup.append(created.json())
    response = requests.get(f"{BASE_URL}/auth/me", headers=old_headers, timeout=5)
    assert response.status_code == 401, response.text
    assert login(created.json()["username"], "TestPassword123")


def test_swagger_documentation():
    """Document success schemas, security, and errors for all implemented APIs."""
    response = requests.get(f"{BASE_URL}/swagger.json", timeout=5)
    assert response.status_code == 200, response.text
    spec = response.json()
    operations = [
        ("/auth/login", "post", "200", "LoginResponse"),
        ("/auth/me", "get", "200", "AccountResponse"),
        ("/accounts", "get", "200", "AccountResponse"),
        ("/accounts", "post", "201", "AccountResponse"),
        ("/accounts/{account_id}", "patch", "200", "AccountResponse"),
        ("/accounts/{account_id}", "delete", "204", None),
    ]
    for path, method, status, model in operations:
        operation = spec["paths"][path][method]
        assert operation.get("summary")
        assert operation.get("description")
        assert operation.get("tags")
        assert {"401", "403", status} <= operation["responses"].keys()
        if path == "/auth/login":
            assert not operation.get("security", spec.get("security"))
        else:
            assert operation["security"] == [{"BearerAuth": []}]
            assert "422" in operation["responses"]
        if model:
            schema = operation["responses"][status]["schema"]
            if method == "get" and path == "/accounts":
                assert schema["type"] == "array"
                schema = schema["items"]
            assert schema["$ref"] == f"#/definitions/{model}"
        else:
            assert "schema" not in operation["responses"][status]
        if method in ("post", "patch"):
            assert any(p["in"] == "body" for p in operation["parameters"])
            assert {"400", "415"} <= operation["responses"].keys()
    assert "access_token" in spec["definitions"]["LoginResponse"]["properties"]
    assert set(spec["definitions"]["AccountResponse"]["properties"]) == {
        "id", "username", "role", "is_active"
    }



def test_account_credential_boundaries(account_cleanup):
    """Accept maximum credential lengths and trim surrounding username spaces."""
    username = "test_" + uuid4().hex + "x" * 63
    password = "x" * 128
    headers = login("admin", "admin")
    created = requests.post(
        f"{BASE_URL}/accounts", headers=headers,
        json={"username": f" {username} ", "password": password}, timeout=5
    )
    assert created.status_code == 201, created.text
    account_cleanup.append(created.json())
    assert created.json()["username"] == username
    assert set(created.json()) == {"id", "username", "role", "is_active"}
    me = requests.get(
        f"{BASE_URL}/auth/me", headers=login(username, password), timeout=5
    )
    assert me.status_code == 200, me.text
    assert me.json() == created.json()
    duplicate = requests.post(
        f"{BASE_URL}/accounts", headers=headers,
        json={"username": username, "password": password}, timeout=5
    )
    assert duplicate.status_code == 409, duplicate.text

# ============================================================
# Requirement Set 2: Data Import
# ============================================================

# ------------------------------------------------------------
# 1. Import API Tests
# ------------------------------------------------------------

def test_admin_can_import_all_datasets():
    """Verify that Admin can import all three CSV datasets."""


    headers = login("admin", "admin")

    with (
        open("airports.csv", "rb") as airports,
        open("airlines.csv", "rb") as airlines,
        open("routes.csv", "rb") as routes
    ):
        response = requests.post(
            f"{BASE_URL}/imports",
            headers=headers,
            files={
                "airports": ("airports.csv", airports, "text/csv"),
                "airlines": ("airlines.csv", airlines, "text/csv"),
                "routes": ("routes.csv", routes, "text/csv")
            },
            timeout=15
        )

    assert response.status_code == 200, response.text

    result = response.json()

    assert set(result) == {"message", "datasets", "counts"}
    assert set(result["datasets"]) == {"airports", "airlines", "routes"}
    assert result["counts"]["airports"] == 46
    assert result["counts"]["airlines"] == 15
    assert result["counts"]["routes"] == 260


# Test Helpers

PROJECT_DIR = Path(__file__).resolve().parent
DB_PATH = PROJECT_DIR / "instance" / "airroute.db"


def read_csv_rows(dataset):
    """Read an original CSV file into dictionaries."""

    path = PROJECT_DIR / f"{dataset}.csv"

    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return reader.fieldnames, list(reader)


def make_csv_bytes(columns, rows):
    """Generate CSV bytes from test records."""

    output = io.StringIO(newline="")

    writer = csv.DictWriter(
        output,
        fieldnames=columns,
        lineterminator="\n"
    )

    writer.writeheader()
    writer.writerows(rows)

    return output.getvalue().encode("utf-8")


def aviation_snapshot():
    """
    Read all aviation records without modifying the database.

    Used to verify that rejected imports preserve existing data.
    """

    assert DB_PATH.exists(), f"Database not found: {DB_PATH}"

    snapshot = {}

    with sqlite3.connect(DB_PATH) as connection:
        for table, primary_key in (
            ("airports", "airport_id"),
            ("airlines", "airline_id"),
            ("routes", "route_id"),
        ):
            snapshot[table] = connection.execute(
                f"SELECT * FROM {table} ORDER BY {primary_key}"
            ).fetchall()

    return snapshot


@pytest.fixture
def imported_baseline():
    """Import the original datasets before each validation test."""

    headers = login("admin", "admin")

    with (
        (PROJECT_DIR / "airports.csv").open("rb") as airports,
        (PROJECT_DIR / "airlines.csv").open("rb") as airlines,
        (PROJECT_DIR / "routes.csv").open("rb") as routes
    ):
        response = requests.post(
            f"{BASE_URL}/imports",
            headers=headers,
            files={
                "airports": ("airports.csv", airports, "text/csv"),
                "airlines": ("airlines.csv", airlines, "text/csv"),
                "routes": ("routes.csv", routes, "text/csv"),
            },
            timeout=15
        )

    assert response.status_code == 200, response.text

    return headers


# ------------------------------------------------------------
# 2. Import Validation Tests
# ------------------------------------------------------------

def test_import_airports_only(imported_baseline):
    """Verify independent import preserves omitted datasets."""

    before = aviation_snapshot()

    response = requests.post(
        f"{BASE_URL}/imports",
        headers=imported_baseline,
        files={
            "airports": (
                "airports.csv",
                (PROJECT_DIR / "airports.csv").read_bytes(),
                "text/csv"
            )
        },
        timeout=15
    )

    assert response.status_code == 200, response.text
    assert response.json()["counts"]["airports"] == 46

    # Reimporting identical airports must preserve all data
    assert aviation_snapshot() == before


def test_user_cannot_import():
    """Verify that regular Users cannot import CSV datasets."""

    response = requests.post(
        f"{BASE_URL}/imports",
        headers=login("user", "user"),
        files={
            "airports": (
                "airports.csv",
                (PROJECT_DIR / "airports.csv").read_bytes(),
                "text/csv"
            )
        },
        timeout=15
    )

    assert response.status_code == 403, response.text


def test_invalid_csv_columns(imported_baseline):
    """Reject invalid CSV columns without modifying the database."""

    before = aviation_snapshot()

    response = requests.post(
        f"{BASE_URL}/imports",
        headers=imported_baseline,
        files={
            "airports": (
                "airports.csv",
                b"wrong_column,name\n1,Sydney\n",
                "text/csv"
            )
        },
        timeout=15
    )

    assert response.status_code == 400, response.text
    assert aviation_snapshot() == before


def test_duplicate_airport_id(imported_baseline):
    """Reject duplicate primary keys without changing stored data."""

    columns, rows = read_csv_rows("airports")

    rows[1]["airport_id"] = rows[0]["airport_id"]

    before = aviation_snapshot()

    response = requests.post(
        f"{BASE_URL}/imports",
        headers=imported_baseline,
        files={
            "airports": (
                "airports.csv",
                make_csv_bytes(columns, rows),
                "text/csv"
            )
        },
        timeout=15
    )

    assert response.status_code == 400, response.text
    assert aviation_snapshot() == before


def test_import_mismatched_iata(imported_baseline):
    """Reject a route whose airport ID and IATA code disagree."""

    columns, rows = read_csv_rows("routes")

    rows[0]["origin_iata"] = "XXX"

    before = aviation_snapshot()

    response = requests.post(
        f"{BASE_URL}/imports",
        headers=imported_baseline,
        files={
            "routes": (
                "routes.csv",
                make_csv_bytes(columns, rows),
                "text/csv"
            )
        },
        timeout=15
    )

    assert response.status_code == 400, response.text
    assert aviation_snapshot() == before


def test_import_missing_airport_reference(imported_baseline):
    """Reject replacement airports that break existing routes."""

    columns, rows = read_csv_rows("airports")

    # Remove Sydney Airport, which existing routes reference
    rows = [
        row for row in rows
        if row["airport_id"] != "1"
    ]

    before = aviation_snapshot()

    response = requests.post(
        f"{BASE_URL}/imports",
        headers=imported_baseline,
        files={
            "airports": (
                "airports.csv",
                make_csv_bytes(columns, rows),
                "text/csv"
            )
        },
        timeout=15
    )

    assert response.status_code == 409, response.text
    assert aviation_snapshot() == before


def test_multi_file_import_atomicity(imported_baseline):
    """
    Reject the entire batch when one uploaded dataset is invalid.

    Even a valid uploaded dataset must not replace existing data.
    """

    airport_columns, airport_rows = read_csv_rows("airports")
    route_columns, route_rows = read_csv_rows("routes")

    # Valid airport modification
    airport_rows[0]["name"] = "Temporary Test Airport"

    # Invalid route IATA
    route_rows[0]["origin_iata"] = "XXX"

    before = aviation_snapshot()

    response = requests.post(
        f"{BASE_URL}/imports",
        headers=imported_baseline,
        files={
            "airports": (
                "airports.csv",
                make_csv_bytes(airport_columns, airport_rows),
                "text/csv"
            ),
            "routes": (
                "routes.csv",
                make_csv_bytes(route_columns, route_rows),
                "text/csv"
            )
        },
        timeout=15
    )

    assert response.status_code == 400, response.text

    # Every table must remain unchanged
    assert aviation_snapshot() == before


def test_import_swagger_response():
    """Requirement 2: document import responses and the Travel Plans policy."""
    response = requests.get(f"{BASE_URL}/swagger.json", timeout=5)
    assert response.status_code == 200, response.text
    spec = response.json()
    operation = spec["paths"]["/imports"]["post"]
    assert operation["responses"]["200"]["schema"] == {
        "$ref": "#/definitions/ImportResponse"
    }
    assert "500" in operation["responses"]
    model = spec["definitions"]["ImportResponse"]
    assert set(model["required"]) == {"message", "datasets", "counts"}
    properties = model["properties"]
    assert properties["message"]["type"] == "string"
    assert properties["datasets"]["type"] == "array"
    assert properties["datasets"]["items"]["type"] == "string"
    counts_schema = properties["counts"]
    counts_ref = "#/definitions/ImportCounts"
    assert (counts_schema.get("$ref") == counts_ref or
            {"$ref": counts_ref} in counts_schema.get("allOf", []))
    counts = spec["definitions"]["ImportCounts"]
    assert set(counts["properties"]) == {"airports", "airlines", "routes"}
    assert all(field["type"] == "integer" for field in counts["properties"].values())
    assert "Referenced Travel Plan routes cannot be removed or changed" in operation["description"]
    assert "HTTP 409" in operation["description"]


def test_import_rejects_removing_a_referenced_route(imported_baseline):
    """RS4: A route used by a travel plan cannot be removed by import."""
    user_headers = login("user", "user")
    admin_headers = login("admin", "admin")
    created = requests.post(
        f"{BASE_URL}/travel-plans",
        headers=user_headers,
        json={
            "name": "Protected import route",
            "departure_date": "2027-09-01",
            "return_date": "2027-09-02",
        },
        timeout=10,
    )
    assert created.status_code == 201, created.text
    plan_id = created.json()["plan_id"]
    try:
        linked = requests.post(
            f"{BASE_URL}/travel-plans/{plan_id}/routes",
            headers=user_headers,
            json={"route_id": 1},
            timeout=10,
        )
        assert linked.status_code == 201, linked.text
        columns, rows = read_csv_rows("routes")
        removed = make_csv_bytes(
            columns, [row for row in rows if row["route_id"] != "1"]
        )
        response = requests.post(
            f"{BASE_URL}/imports",
            headers=admin_headers,
            files={"routes": ("routes.csv", removed, "text/csv")},
            timeout=15,
        )
        assert response.status_code == 409, response.text
        assert "Route 1" in response.json()["message"]
        assert requests.get(
            f"{BASE_URL}/travel-plans/{plan_id}",
            headers=user_headers,
            timeout=10,
        ).status_code == 200
    finally:
        requests.delete(
            f"{BASE_URL}/travel-plans/{plan_id}",
            headers=user_headers,
            timeout=10,
        )


# ============================================================
# Requirement Set 3: Data Exploration
# ============================================================

# ------------------------------------------------------------
# 1. Airport Exploration Tests
# ------------------------------------------------------------

def test_airport_list_and_search(imported_baseline):
    """RS3: Verify airport listing and case-insensitive search."""

    headers = login("user", "user")

    response = requests.get(
        f"{BASE_URL}/airports",
        headers=headers,
        timeout=10
    )

    assert response.status_code == 200, response.text

    data = response.json()
    assert data["total"] == 46
    assert len(data["items"]) <= 20

    response = requests.get(
        f"{BASE_URL}/airports",
        headers=headers,
        params={"q": "sYd"},
        timeout=10
    )

    assert response.status_code == 200, response.text
    assert response.json()["total"] >= 1


def test_airport_detail(imported_baseline):
    """RS3: Verify airport details and missing airport handling."""

    headers = login("user", "user")

    response = requests.get(
        f"{BASE_URL}/airports/1",
        headers=headers,
        timeout=10
    )

    assert response.status_code == 200, response.text

    data = response.json()
    assert data["airport_id"] == 1
    assert data["iata_code"] == "SYD"
    assert "links" in data

    missing = requests.get(
        f"{BASE_URL}/airports/999999",
        headers=headers,
        timeout=10
    )

    assert missing.status_code == 404
    assert "message" in missing.json()


# ------------------------------------------------------------
# 2. Airline Exploration Tests
# ------------------------------------------------------------

def test_airline_list_and_search(imported_baseline):
    """RS3: Verify airline listing and case-insensitive search."""

    headers = login("user", "user")

    response = requests.get(
        f"{BASE_URL}/airlines",
        headers=headers,
        timeout=10
    )

    assert response.status_code == 200, response.text

    data = response.json()
    assert data["total"] == 15
    assert len(data["items"]) == 15

    # Search for Qantas using mixed case
    response = requests.get(
        f"{BASE_URL}/airlines",
        headers=headers,
        params={"q": "qAn"},
        timeout=10
    )

    assert response.status_code == 200, response.text
    assert any(
        airline["name"] == "Qantas"
        for airline in response.json()["items"]
    )


def test_airlines_by_airport(imported_baseline):
    """RS3: Verify airlines operating from a specific airport."""

    headers = login("user", "user")

    response = requests.get(
        f"{BASE_URL}/airlines",
        headers=headers,
        params={"airport_id": 1},
        timeout=10
    )

    assert response.status_code == 200, response.text

    data = response.json()

    # All returned airlines must operate routes from airport 1
    _, route_rows = read_csv_rows("routes")

    expected_ids = {
        int(route["airline_id"])
        for route in route_rows
        if route["origin_airport_id"] == "1"
    }

    actual_ids = {
        airline["airline_id"]
        for airline in data["items"]
    }

    assert actual_ids == expected_ids
    assert data["total"] == len(expected_ids)

    # Unknown airport
    missing = requests.get(
        f"{BASE_URL}/airlines",
        headers=headers,
        params={"airport_id": 999999},
        timeout=10
    )

    assert missing.status_code == 404


def test_airline_detail(imported_baseline):
    """RS3: Verify airline details and missing airline handling."""

    headers = login("user", "user")

    response = requests.get(
        f"{BASE_URL}/airlines/1",
        headers=headers,
        timeout=10
    )

    assert response.status_code == 200, response.text

    data = response.json()
    assert data["airline_id"] == 1
    assert data["iata_code"] == "QF"
    assert "links" in data

    missing = requests.get(
        f"{BASE_URL}/airlines/999999",
        headers=headers,
        timeout=10
    )

    assert missing.status_code == 404
    assert "message" in missing.json()



# ------------------------------------------------------------
# 3. Route Exploration Tests
# ------------------------------------------------------------

def test_route_list(imported_baseline):
    """RS3: Verify route listing and pagination."""

    headers = login("user", "user")

    response = requests.get(
        f"{BASE_URL}/routes",
        headers=headers,
        timeout=10
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["total"] == 260
    assert len(data["items"]) == 20
    assert data["items"][0]["route_id"] == 1
    assert "links" in data["items"][0]

    # Verify pagination
    second_page = requests.get(
        f"{BASE_URL}/routes",
        headers=headers,
        params={"limit": 10, "offset": 10},
        timeout=10
    )

    assert second_page.status_code == 200
    assert len(second_page.json()["items"]) == 10
    assert second_page.json()["items"][0]["route_id"] == 11


def test_routes_by_airline(imported_baseline):
    """RS3: Verify route filtering by airline."""

    headers = login("user", "user")

    response = requests.get(
        f"{BASE_URL}/routes",
        headers=headers,
        params={"airline_id": 1, "limit": 100},
        timeout=10
    )

    assert response.status_code == 200, response.text

    data = response.json()

    _, rows = read_csv_rows("routes")
    expected_count = sum(
        row["airline_id"] == "1"
        for row in rows
    )

    assert data["total"] == expected_count
    assert all(
        route["airline_id"] == 1
        for route in data["items"]
    )


def test_routes_by_airport(imported_baseline):
    """RS3: Verify origin and destination airport filtering."""

    headers = login("user", "user")

    response = requests.get(
        f"{BASE_URL}/routes",
        headers=headers,
        params={
            "origin_airport_id": 1,
            "destination_airport_id": 2,
        },
        timeout=10
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["total"] >= 1

    for route in data["items"]:
        assert route["origin_airport_id"] == 1
        assert route["destination_airport_id"] == 2


def test_route_detail(imported_baseline):
    """RS3: Verify full route details and related resources."""

    headers = login("user", "user")

    response = requests.get(
        f"{BASE_URL}/routes/1",
        headers=headers,
        timeout=10
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["route_id"] == 1
    assert data["airline"]["iata_code"] == "QF"
    assert data["origin_airport"]["iata_code"] == "SYD"
    assert data["destination_airport"]["iata_code"] == "MEL"

    assert data["links"]["airline"] == "/airlines/1"

    missing = requests.get(
        f"{BASE_URL}/routes/999999",
        headers=headers,
        timeout=10
    )

    assert missing.status_code == 404
    assert "message" in missing.json()


def test_invalid_route_filters(imported_baseline):
    """RS3: Verify invalid pagination and unknown references."""

    headers = login("user", "user")

    invalid_limit = requests.get(
        f"{BASE_URL}/routes",
        headers=headers,
        params={"limit": 0},
        timeout=10
    )

    assert invalid_limit.status_code == 400

    missing_airport = requests.get(
        f"{BASE_URL}/routes",
        headers=headers,
        params={"origin_airport_id": 999999},
        timeout=10
    )

    assert missing_airport.status_code == 404


@pytest.mark.parametrize("path,parameter", [
    ("/airports", "limit"), ("/airports", "offset"),
    ("/airlines", "limit"), ("/airlines", "offset"),
    ("/airlines", "airport_id"),
    ("/routes", "limit"), ("/routes", "offset"),
    ("/routes", "airline_id"), ("/routes", "origin_airport_id"),
    ("/routes", "destination_airport_id"),
])
@pytest.mark.parametrize("value", [-(2 ** 63) - 1, 2 ** 63])
def test_exploration_integer_overflow(imported_baseline, path, parameter, value):
    """RS3: Reject overflowing query integers with 400 rather than a server error."""
    response = requests.get(
        f"{BASE_URL}{path}", headers=login("user", "user"),
        params={parameter: value}, timeout=10
    )
    assert response.status_code == 400, response.text
    assert parameter in response.json()["errors"]
    assert "signed 64-bit" in response.json()["errors"][parameter]


@pytest.mark.parametrize("resource", ["airports", "airlines", "routes"])
@pytest.mark.parametrize("resource_id", [2 ** 63, 10 ** 30, 2 ** 63 - 1])
def test_exploration_large_detail_ids(imported_baseline, resource, resource_id):
    """RS3: Large missing IDs, including the valid upper boundary, return 404."""
    response = requests.get(
        f"{BASE_URL}/{resource}/{resource_id}",
        headers=login("user", "user"), timeout=10
    )
    assert response.status_code == 404, response.text
    assert "not found" in response.json()["message"].lower()


@pytest.mark.parametrize("resource,total", [
    ("airports", 46), ("airlines", 15), ("routes", 260)
])
def test_exploration_maximum_offset(imported_baseline, resource, total):
    """RS3: The largest valid SQLite offset returns an empty page with its total."""
    response = requests.get(
        f"{BASE_URL}/{resource}", headers=login("user", "user"),
        params={"offset": 2 ** 63 - 1}, timeout=10
    )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "total": total, "limit": 20, "offset": 2 ** 63 - 1, "items": []
    }


@pytest.mark.parametrize("query", ["São", "são", "SÃO", "sÃo", "ÃO", "ãO"])
def test_airport_unicode_search(imported_baseline, query):
    """RS3: Unicode case and partial matching preserve search totals and pagination."""
    headers = login("user", "user")
    _, rows = read_csv_rows("airports")
    expected_ids = [
        int(row["airport_id"]) for row in rows
        if any(query.casefold() in row[column].casefold()
               for column in ("name", "city", "country", "iata_code"))
    ]
    assert expected_ids
    if query.casefold() == "são":
        assert expected_ids == [37]
    for offset in range(len(expected_ids) + 1):
        response = requests.get(
            f"{BASE_URL}/airports", headers=headers,
            params={"q": query, "limit": 1, "offset": offset}, timeout=10
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["total"] == len(expected_ids)
        assert data["limit"] == 1 and data["offset"] == offset
        assert [airport["airport_id"] for airport in data["items"]] == expected_ids[offset:offset + 1]


def test_airline_unicode_search(imported_baseline):
    """RS3: Airline search also casefolds Unicode while retaining airport filtering."""
    columns, rows = read_csv_rows("airlines")
    rows[0]["name"] = "São Straße Airways"
    try:
        uploaded = requests.post(
            f"{BASE_URL}/imports", headers=imported_baseline,
            files={"airlines": ("airlines.csv", make_csv_bytes(columns, rows), "text/csv")},
            timeout=15
        )
        assert uploaded.status_code == 200, uploaded.text
        headers = login("user", "user")
        for query in ["São", "são", "SÃO", "ÃO", "STRASSE"]:
            for offset, expected_ids in [(0, [1]), (1, [])]:
                response = requests.get(
                    f"{BASE_URL}/airlines", headers=headers,
                    params={"q": query, "airport_id": 1, "limit": 1, "offset": offset},
                    timeout=10
                )
                assert response.status_code == 200, response.text
                data = response.json()
                assert data["total"] == 1
                assert data["limit"] == 1 and data["offset"] == offset
                assert [airline["airline_id"] for airline in data["items"]] == expected_ids
    finally:
        restored = requests.post(
            f"{BASE_URL}/imports", headers=imported_baseline,
            files={"airlines": ("airlines.csv", (PROJECT_DIR / "airlines.csv").read_bytes(), "text/csv")},
            timeout=15
        )
        assert restored.status_code == 200, restored.text


def test_exploration_swagger_and_jwt_errors():
    """RS3: All six operations retain response schemas and document malformed JWTs."""
    response = requests.get(f"{BASE_URL}/swagger.json", timeout=5)
    assert response.status_code == 200, response.text
    spec = response.json()
    for path, model in [
        ("/airports", "AirportList"), ("/airports/{airport_id}", "AirportDetails"),
        ("/airlines", "AirlineList"), ("/airlines/{airline_id}", "AirlineDetails"),
        ("/routes", "RouteList"), ("/routes/{route_id}", "RouteDetails"),
    ]:
        operation = spec["paths"][path]["get"]
        assert "422" in operation["responses"]
        assert operation["responses"]["200"]["schema"] == {
            "$ref": f"#/definitions/{model}"
        }
        assert operation["security"] == [{"BearerAuth": []}]
        for parameter in operation.get("parameters", []):
            if parameter["name"] != "q":
                assert parameter["type"] == "integer"
        actual_path = (path.replace("{airport_id}", "1")
                      .replace("{airline_id}", "1").replace("{route_id}", "1"))
        rejected = requests.get(
            f"{BASE_URL}{actual_path}",
            headers={"Authorization": "Bearer invalid-token"}, timeout=5
        )
        assert rejected.status_code == 422, rejected.text
        assert "message" in rejected.json()

# ============================================================
# Requirement Set 4: My Travel Plans
# ============================================================

# ------------------------------------------------------------
# 1. Create Travel Plan Tests
# ------------------------------------------------------------

def test_create_travel_plan():
    """RS4: Verify that an authenticated User can create a plan."""

    headers = login("user", "user")

    payload = {
        "name": "Australia Holiday",
        "departure_date": "2026-12-20",
        "return_date": "2027-01-10",
    }

    response = requests.post(
        f"{BASE_URL}/travel-plans",
        headers=headers,
        json=payload,
        timeout=10
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert isinstance(data["plan_id"], int)
    assert data["name"] == "Australia Holiday"
    assert data["departure_date"] == "2026-12-20"
    assert data["return_date"] == "2027-01-10"
    assert data["routes"] == []


def test_invalid_travel_plan_dates():
    """RS4: Reject a return date earlier than departure date."""

    headers = login("user", "user")

    response = requests.post(
        f"{BASE_URL}/travel-plans",
        headers=headers,
        json={
            "name": "Invalid Holiday",
            "departure_date": "2027-01-10",
            "return_date": "2026-12-20",
        },
        timeout=10
    )

    assert response.status_code == 400
    assert "message" in response.json()


# ------------------------------------------------------------
# 2. Retrieve Travel Plan Tests
# ------------------------------------------------------------

def test_retrieve_own_travel_plan():
    """RS4: A User can list and retrieve their own travel plans."""

    headers = login("user", "user")

    # Create a plan for this test
    created = requests.post(
        f"{BASE_URL}/travel-plans",
        headers=headers,
        json={
            "name": "Retrieval Test Trip",
            "departure_date": "2027-03-01",
            "return_date": "2027-03-10",
        },
        timeout=10
    )

    assert created.status_code == 201, created.text
    plan_id = created.json()["plan_id"]

    # Retrieve all plans belonging to this User
    response = requests.get(
        f"{BASE_URL}/travel-plans",
        headers=headers,
        timeout=10
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["total"] == len(data["items"])
    assert any(
        plan["plan_id"] == plan_id
        for plan in data["items"]
    )

    # Retrieve the specific plan
    detail = requests.get(
        f"{BASE_URL}/travel-plans/{plan_id}",
        headers=headers,
        timeout=10
    )

    assert detail.status_code == 200, detail.text
    assert detail.json()["plan_id"] == plan_id
    assert detail.json()["name"] == "Retrieval Test Trip"
    assert detail.json()["routes"] == []


def test_travel_plan_privacy():
    """RS4: Admin and User cannot access each other's private plans."""

    user_headers = login("user", "user")
    admin_headers = login("admin", "admin")

    # Create a User-owned plan
    user_response = requests.post(
        f"{BASE_URL}/travel-plans",
        headers=user_headers,
        json={
            "name": "Private User Trip",
            "departure_date": "2027-04-01",
            "return_date": "2027-04-10",
        },
        timeout=10
    )

    assert user_response.status_code == 201, user_response.text
    user_plan_id = user_response.json()["plan_id"]

    # Admin must not see the User's plan
    admin_detail = requests.get(
        f"{BASE_URL}/travel-plans/{user_plan_id}",
        headers=admin_headers,
        timeout=10
    )

    assert admin_detail.status_code == 404

    admin_list = requests.get(
        f"{BASE_URL}/travel-plans",
        headers=admin_headers,
        timeout=10
    )

    assert admin_list.status_code == 200
    assert all(
        plan["plan_id"] != user_plan_id
        for plan in admin_list.json()["items"]
    )

    # Create an Admin-owned plan
    admin_response = requests.post(
        f"{BASE_URL}/travel-plans",
        headers=admin_headers,
        json={
            "name": "Private Admin Trip",
            "departure_date": "2027-05-01",
            "return_date": "2027-05-10",
        },
        timeout=10
    )

    assert admin_response.status_code == 201, admin_response.text
    admin_plan_id = admin_response.json()["plan_id"]

    # User must not see the Admin's plan
    user_detail = requests.get(
        f"{BASE_URL}/travel-plans/{admin_plan_id}",
        headers=user_headers,
        timeout=10
    )

    assert user_detail.status_code == 404


# ------------------------------------------------------------
# 3. Update and Delete Travel Plan Tests
# ------------------------------------------------------------

def test_update_and_delete_travel_plan():
    """RS4: Verify an owner can update and delete a travel plan."""

    headers = login("user", "user")

    # Create a plan
    created = requests.post(
        f"{BASE_URL}/travel-plans",
        headers=headers,
        json={
            "name": "Original Trip",
            "departure_date": "2027-03-01",
            "return_date": "2027-03-10",
        },
        timeout=10
    )

    assert created.status_code == 201, created.text
    plan_id = created.json()["plan_id"]

    # Update the plan
    updated = requests.put(
        f"{BASE_URL}/travel-plans/{plan_id}",
        headers=headers,
        json={
            "name": "Updated Trip",
            "departure_date": "2027-04-01",
            "return_date": "2027-04-15",
        },
        timeout=10
    )

    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Updated Trip"
    assert updated.json()["departure_date"] == "2027-04-01"

    # Verify the update was saved
    retrieved = requests.get(
        f"{BASE_URL}/travel-plans/{plan_id}",
        headers=headers,
        timeout=10
    )

    assert retrieved.status_code == 200
    assert retrieved.json()["name"] == "Updated Trip"

    # Delete the plan
    deleted = requests.delete(
        f"{BASE_URL}/travel-plans/{plan_id}",
        headers=headers,
        timeout=10
    )

    assert deleted.status_code == 204

    # Verify it no longer exists
    missing = requests.get(
        f"{BASE_URL}/travel-plans/{plan_id}",
        headers=headers,
        timeout=10
    )

    assert missing.status_code == 404


def test_cannot_modify_other_users_plan():
    """RS4: Admin cannot update or delete a User-owned plan."""

    user_headers = login("user", "user")
    admin_headers = login("admin", "admin")

    created = requests.post(
        f"{BASE_URL}/travel-plans",
        headers=user_headers,
        json={
            "name": "Private Trip",
            "departure_date": "2027-05-01",
            "return_date": "2027-05-10",
        },
        timeout=10
    )

    assert created.status_code == 201, created.text
    plan_id = created.json()["plan_id"]

    try:
        # Admin attempts to update User-owned plan
        updated = requests.put(
            f"{BASE_URL}/travel-plans/{plan_id}",
            headers=admin_headers,
            json={
                "name": "Hacked Trip",
                "departure_date": "2027-06-01",
                "return_date": "2027-06-10",
            },
            timeout=10
        )

        assert updated.status_code == 404

        # Admin attempts to delete User-owned plan
        deleted = requests.delete(
            f"{BASE_URL}/travel-plans/{plan_id}",
            headers=admin_headers,
            timeout=10
        )

        assert deleted.status_code == 404

        # Verify original plan is unchanged
        original = requests.get(
            f"{BASE_URL}/travel-plans/{plan_id}",
            headers=user_headers,
            timeout=10
        )

        assert original.status_code == 200
        assert original.json()["name"] == "Private Trip"

    finally:
        # Clean up using the actual owner
        requests.delete(
            f"{BASE_URL}/travel-plans/{plan_id}",
            headers=user_headers,
            timeout=10
        )



# ------------------------------------------------------------
# 4. Travel Plan Route Management Tests
# ------------------------------------------------------------

def test_add_and_remove_plan_routes(imported_baseline):
    """RS4: Add, reject duplicates, and remove plan routes."""

    headers = login("user", "user")

    created = requests.post(
        f"{BASE_URL}/travel-plans",
        headers=headers,
        json={
            "name": "Route Management Test",
            "departure_date": "2027-06-01",
            "return_date": "2027-06-10",
        },
        timeout=10
    )

    assert created.status_code == 201, created.text
    plan_id = created.json()["plan_id"]

    try:
        # Add Route 1
        added = requests.post(
            f"{BASE_URL}/travel-plans/{plan_id}/routes",
            headers=headers,
            json={"route_id": 1},
            timeout=10
        )

        assert added.status_code == 201, added.text
        assert 1 in added.json()["routes"]

        # Adding the same route again must fail
        duplicate = requests.post(
            f"{BASE_URL}/travel-plans/{plan_id}/routes",
            headers=headers,
            json={"route_id": 1},
            timeout=10
        )

        assert duplicate.status_code == 409

        # Add Route 2
        second = requests.post(
            f"{BASE_URL}/travel-plans/{plan_id}/routes",
            headers=headers,
            json={"route_id": 2},
            timeout=10
        )

        assert second.status_code == 201, second.text

        # Verify both routes are saved
        detail = requests.get(
            f"{BASE_URL}/travel-plans/{plan_id}",
            headers=headers,
            timeout=10
        )

        assert detail.status_code == 200
        assert set(detail.json()["routes"]) == {1, 2}

        # Remove Route 1
        removed = requests.delete(
            f"{BASE_URL}/travel-plans/{plan_id}/routes/1",
            headers=headers,
            timeout=10
        )

        assert removed.status_code == 204

        # Verify only Route 2 remains
        detail = requests.get(
            f"{BASE_URL}/travel-plans/{plan_id}",
            headers=headers,
            timeout=10
        )

        assert detail.status_code == 200
        assert detail.json()["routes"] == [2]

        # Nonexistent route must be rejected
        invalid = requests.post(
            f"{BASE_URL}/travel-plans/{plan_id}/routes",
            headers=headers,
            json={"route_id": 999999},
            timeout=10
        )

        assert invalid.status_code == 404

    finally:
        requests.delete(
            f"{BASE_URL}/travel-plans/{plan_id}",
            headers=headers,
            timeout=10
        )


def test_plan_route_ownership(imported_baseline):
    """RS4: Admin cannot change routes in a User-owned plan."""

    user_headers = login("user", "user")
    admin_headers = login("admin", "admin")

    created = requests.post(
        f"{BASE_URL}/travel-plans",
        headers=user_headers,
        json={
            "name": "Private Routes Test",
            "departure_date": "2027-07-01",
            "return_date": "2027-07-10",
        },
        timeout=10
    )

    assert created.status_code == 201, created.text
    plan_id = created.json()["plan_id"]

    try:
        denied_add = requests.post(
            f"{BASE_URL}/travel-plans/{plan_id}/routes",
            headers=admin_headers,
            json={"route_id": 1},
            timeout=10
        )

        assert denied_add.status_code == 404

        denied_delete = requests.delete(
            f"{BASE_URL}/travel-plans/{plan_id}/routes/1",
            headers=admin_headers,
            timeout=10
        )

        assert denied_delete.status_code == 404

    finally:
        requests.delete(
            f"{BASE_URL}/travel-plans/{plan_id}",
            headers=user_headers,
            timeout=10
        )


# ============================================================
# Requirement Set 5: Exporting Travel Plans
# ============================================================

# ------------------------------------------------------------
# 1. JSON Export Tests
# ------------------------------------------------------------

def test_export_travel_plans_json(imported_baseline):
    """RS5: Export owned plans with complete related route data."""

    headers = login("user", "user")

    created = requests.post(
        f"{BASE_URL}/travel-plans",
        headers=headers,
        json={
            "name": "JSON Export Test",
            "departure_date": "2027-08-01",
            "return_date": "2027-08-05"
        },
        timeout=10
    )

    assert created.status_code == 201, created.text
    plan_id = created.json()["plan_id"]

    try:
        # Add a route
        added = requests.post(
            f"{BASE_URL}/travel-plans/{plan_id}/routes",
            headers=headers,
            json={"route_id": 1},
            timeout=10
        )

        assert added.status_code == 201, added.text

        # Download JSON
        response = requests.get(
            f"{BASE_URL}/travel-plans/export",
            headers=headers,
            params={"format": "json"},
            timeout=10
        )

        assert response.status_code == 200, response.text
        assert "application/json" in response.headers["Content-Type"]
        assert "attachment" in response.headers["Content-Disposition"]

        data = response.json()
        plans = data["plans"]

        # All plans must be sorted by departure date
        dates = [plan["departure_date"] for plan in plans]
        assert dates == sorted(dates)

        # Find the plan created by this test
        exported = next(
            plan for plan in plans
            if plan["plan_id"] == plan_id
        )

        assert exported["name"] == "JSON Export Test"
        assert len(exported["routes"]) == 1

        # Check self-contained route details
        route = exported["routes"][0]

        assert route["route_id"] == 1
        assert route["airline"]["iata_code"] == "QF"
        assert route["origin_airport"]["iata_code"] == "SYD"
        assert route["destination_airport"]["iata_code"] == "MEL"

    finally:
        requests.delete(
            f"{BASE_URL}/travel-plans/{plan_id}",
            headers=headers,
            timeout=10
        )


def test_export_travel_plans_image():
    """RS5: Export upcoming travel plans as a PNG image."""

    from datetime import date, timedelta

    headers = login("user", "user")

    departure = date.today() + timedelta(days=30)
    return_date = departure + timedelta(days=4)

    created = requests.post(
        f"{BASE_URL}/travel-plans",
        headers=headers,
        json={
            "name": "Image Export Test",
            "departure_date": departure.isoformat(),
            "return_date": return_date.isoformat()
        },
        timeout=10
    )

    assert created.status_code == 201, created.text
    plan_id = created.json()["plan_id"]

    try:
        response = requests.get(
            f"{BASE_URL}/travel-plans/export",
            headers=headers,
            params={"format": "image"},
            timeout=20
        )

        assert response.status_code == 200, response.text
        assert "image/png" in response.headers["Content-Type"]
        assert "inline" in response.headers["Content-Disposition"]

        # Verify the PNG file signature
        assert response.content.startswith(
            b"\x89PNG\r\n\x1a\n"
        )

    finally:
        requests.delete(
            f"{BASE_URL}/travel-plans/{plan_id}",
            headers=headers,
            timeout=10
        )


def test_export_boundaries_and_account_privacy(imported_baseline):
    """RS5: Exports are private, reject unsupported formats, and render inline."""
    from datetime import date, timedelta

    admin_headers = login("admin", "admin")
    username = f"export_{uuid4().hex[:12]}"
    created_account = requests.post(
        f"{BASE_URL}/accounts",
        headers=admin_headers,
        json={"username": username, "password": "TestPassword123"},
        timeout=10,
    )
    assert created_account.status_code == 201, created_account.text
    account_id = created_account.json()["id"]
    user_headers = login(username, "TestPassword123")
    departure = date.today() + timedelta(days=30)
    created = requests.post(
        f"{BASE_URL}/travel-plans",
        headers=user_headers,
        json={
            "name": "Private export plan",
            "departure_date": departure.isoformat(),
            "return_date": (departure + timedelta(days=1)).isoformat(),
        },
        timeout=10,
    )
    assert created.status_code == 201, created.text
    plan_id = created.json()["plan_id"]
    try:
        exported = requests.get(
            f"{BASE_URL}/travel-plans/export",
            headers=user_headers,
            params={"format": "json"},
            timeout=10,
        )
        assert exported.status_code == 200, exported.text
        assert [plan["plan_id"] for plan in exported.json()["plans"]] == [plan_id]

        forbidden = requests.get(
            f"{BASE_URL}/travel-plans/export",
            headers=admin_headers,
            params={"format": "json"},
            timeout=10,
        )
        assert forbidden.status_code == 200, forbidden.text
        assert plan_id not in {
            plan["plan_id"] for plan in forbidden.json()["plans"]
        }

        image = requests.get(
            f"{BASE_URL}/travel-plans/export",
            headers=user_headers,
            params={"format": "image"},
            timeout=20,
        )
        assert image.status_code == 200, image.text
        assert "image/png" in image.headers["Content-Type"]
        assert "inline" in image.headers["Content-Disposition"]
        assert image.content.startswith(b"\x89PNG\r\n\x1a\n")

        unsupported = requests.get(
            f"{BASE_URL}/travel-plans/export",
            headers=user_headers,
            params={"format": "xml"},
            timeout=10,
        )
        assert unsupported.status_code == 400, unsupported.text
        assert unsupported.json()["message"] == "Unsupported export format"
    finally:
        requests.delete(
            f"{BASE_URL}/travel-plans/{plan_id}",
            headers=user_headers,
            timeout=10,
        )
        deleted_account = requests.delete(
            f"{BASE_URL}/accounts/{account_id}",
            headers=admin_headers,
            timeout=10,
        )
        assert deleted_account.status_code == 204, deleted_account.text
