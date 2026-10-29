import os
from hashlib import sha256
import csv
import io
import math
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from passlib.hash import pbkdf2_sha256
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from flask import request
from flask_restx import Api, Resource, fields
from flask_jwt_extended import JWTManager, create_access_token
from functools import wraps
from flask import g
from datetime import timedelta
from sqlalchemy.exc import IntegrityError
from flask_jwt_extended.exceptions import JWTExtendedException, NoAuthorizationError
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
from werkzeug.datastructures import FileStorage
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import or_, event
from datetime import date
import re
import json
from io import BytesIO
from flask import send_file
from datetime import date
from matplotlib.figure import Figure
import matplotlib.dates as mdates


app = Flask(__name__) # Flask application

# ============================================================
# Requirement Set 1: User Management and Access Control
# ============================================================

# ------------------------------------------------------------
# 1. Database Configuration and Initialisation
# ------------------------------------------------------------

# Database configuration
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///assignment2.db"

db = SQLAlchemy(app) # Initialise ORM

# Account model
class Account(db.Model):
    __tablename__ = "accounts"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    role = db.Column(
        db.String(10),
        nullable=False
    )

    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True
    )

    __table_args__ = (
        db.CheckConstraint(
            "role IN ('Admin', 'User')",
            name="ck_accounts_role"
        ),
        db.CheckConstraint(
            "is_active IN (0, 1)",
            name="ck_accounts_is_active"
        ),
    )

# Database initialisation
def init_db():
    with app.app_context():
        # Create missing database tables
        db.create_all()

        # Check if any account already exists
        existing_id = db.session.scalar(
            db.select(Account.id).limit(1)
        )

        # Only seed accounts when the table is empty
        if existing_id is not None:
            return

        # Create default accounts
        admin = Account(
            username="admin",
            password_hash=pbkdf2_sha256.hash("admin"),
            role="Admin",
            is_active=True
        )

        user = Account(
            username="user",
            password_hash=pbkdf2_sha256.hash("user"),
            role="User",
            is_active=True
        )

        # Save both accounts in one transaction
        db.session.add_all([admin, user])
        db.session.commit()


# ------------------------------------------------------------
# 2. API Configuration and Swagger Metadata
# ------------------------------------------------------------

authorizations = {
    "BearerAuth": {
        "type": "apiKey",
        "in": "header",
        "name": "Authorization",
        "description": "Enter: Bearer <access_token>"
    }
}

api = Api(
    app,
    title="Airline Travel Planning API",
    version="1.0",
    description=(
        "A RESTful API for managing airline travel data and "
        "personal travel plans."
    ),
    # default="General",
    # default_label="General operations",
    authorizations=authorizations,
    doc="/"
)

# ------------------------------------------------------------
# 3. Authentication and Role-Based Access Control
# ------------------------------------------------------------
app.config["JWT_SECRET_KEY"] = os.environ.get(
    "JWT_SECRET_KEY",
    "local-assignment2-development-key-for-z5596858"
)
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)

jwt = JWTManager(app)


@api.errorhandler(JWTExtendedException)
def handle_jwt_request_error(error):
    """Return JWT request errors consistently in all application modes."""
    status = 401 if isinstance(error, NoAuthorizationError) else 422
    return {"message": str(error)}, status


@api.errorhandler(InvalidTokenError)
def handle_invalid_token(error):
    """Return HTTP 401 for expired tokens and 422 for malformed tokens."""
    status = 401 if isinstance(error, ExpiredSignatureError) else 422
    return {"message": str(error)}, status


# Reusable authentication and role-based access control
def account_required(role=None):
    """
    Require an active authenticated account.

    Optionally restrict access to a specified account role.
    """

    def decorator(func):

        @wraps(func)
        @jwt_required()
        def wrapper(*args, **kwargs):

            # Get the account ID from the JWT
            account_id = get_jwt_identity()

            if (
                not isinstance(account_id, str)
                or not account_id.isascii()
                or not account_id.isdecimal()
                or len(account_id) > 19
                or not 0 < int(account_id) <= 9223372036854775807
            ):
                return {"message": "Invalid account identity"}, 401

            # Query the current account
            account = db.session.get(Account, int(account_id))

            if account is None:
                return {"message": "Account not found"}, 401

            # Bind tokens to credentials because SQLite can reuse deleted IDs.
            account_key = sha256(account.password_hash.encode()).hexdigest()
            if get_jwt().get("account_key") != account_key:
                return {"message": "Account credentials changed; log in again"}, 401

            if not account.is_active:
                return {"message": "Account deactivated"}, 403

            # Check role if required
            if role is not None and account.role != role:
                return {"message": "Insufficient permissions"}, 403

            # Make the account available to the endpoint
            g.current_account = account

            return func(*args, **kwargs)

        return wrapper

    return decorator


accounts_ns = api.namespace(
    "Accounts",
    description="Administrator-only user account management.",
    path="/accounts"
)

account_model = accounts_ns.model("AccountResponse", {
    "id": fields.Integer(
        description="Unique account ID"
    ),
    "username": fields.String(
        description="Account username"
    ),
    "role": fields.String(
        description="Account role: Admin or User"
    ),
    "is_active": fields.Boolean(
        description="Whether the account is active"
    )
})

create_account_model = accounts_ns.model(
    "CreateAccountRequest",
    {
        "username": fields.String(
            required=True,
            description="Unique username for the new account",
            example="alice"
        ),
        "password": fields.String(
            required=True,
            description="Password for the new account"
        )
    },
    strict=True
)

account_status_model = accounts_ns.model(
    "UpdateAccountStatusRequest",
    {
        "is_active": fields.Boolean(
            required=True,
            description="New account status: true or false"
        )
    },
    strict=True
)

# Login model for API documentation
login_model = api.model("Login", {
    "username": fields.String(required=True),
    "password": fields.String(required=True)
})

login_response_model = api.model("LoginResponse", {
    "access_token": fields.String(required=True, description="JWT access token")
})

auth_ns = api.namespace(
    "Authentication",
    description="User authentication and JWT token management.",
    path="/auth"
)


@auth_ns.route("/login")
class Login(Resource):
    """
    Handle user authentication.
    """
    @auth_ns.doc(security=[])
    @auth_ns.expect(login_model, validate=True)
    @auth_ns.response(200, "Login successful", login_response_model)
    @auth_ns.response(400, "Invalid request")
    @auth_ns.response(415, "JSON content type required")
    @auth_ns.response(401, "Invalid credentials")
    @auth_ns.response(403, "Account deactivated")
    def post(self):
        """
        Authenticate a user and generate a JWT access token.

        Validates the submitted credentials, checks the account status, and returns an access token if authentication is successful.
        """
        data = request.get_json()

        username = data["username"]
        password = data["password"]

        if not username or len(username) > 100 or not password or len(password) > 128:
            return {"message": "Invalid credentials"}, 401

        # Query account by username
        account = db.session.scalar(
            db.select(Account).filter_by(username=username)
        )

        # Validate credentials and account status
        if account is None or not pbkdf2_sha256.verify(
            password, account.password_hash
        ):
            return {"message": "Invalid credentials"}, 401

        if not account.is_active:
            return {"message": "Account deactivated"}, 403

        token = create_access_token(
            identity=str(account.id),
            additional_claims={
                "account_key": sha256(account.password_hash.encode()).hexdigest()
            }
        )

        return {"access_token": token}, 200

@auth_ns.route("/me")
class CurrentAccount(Resource):
    """
    Retrieve the current authenticated account.
    """
    @auth_ns.doc(security="BearerAuth")
    @auth_ns.response(200, "Account details retrieved", account_model)
    @auth_ns.response(401, "Missing or invalid access token")
    @auth_ns.response(403, "Account deactivated")
    @auth_ns.response(422, "Malformed access token")
    @account_required()
    def get(self):
        """
        Retrieve the current authenticated account.

        Validates the JWT access token and checks the account's existence and active status. Returns account details without exposing the password hash.
        """
        account = g.current_account

        return {
            "id": account.id,
            "username": account.username,
            "role": account.role,
            "is_active": account.is_active
        }, 200

# ------------------------------------------------------------
# 4. User Account Management
# ------------------------------------------------------------
@accounts_ns.route("")
class Accounts(Resource):
    """
    Manage user accounts.

    Provides administrator-only access to account
    information and management operations.
    """

    @accounts_ns.doc(security="BearerAuth")
    @accounts_ns.response(
        200, "Accounts retrieved successfully", [account_model]
    )
    @accounts_ns.response(401, "Authentication required")
    @accounts_ns.response(403, "Admin access required")
    @accounts_ns.response(422, "Malformed access token")
    @account_required(role="Admin")
    def get(self):
        """
        Retrieve all user accounts.

        Returns account details ordered by ID, excluding password hashes.
        """

        # Query all accounts ordered by ID
        accounts = db.session.scalars(
            db.select(Account).order_by(Account.id)
        ).all()

        # Return account details without password hashes
        return [
            {
                "id": account.id,
                "username": account.username,
                "role": account.role,
                "is_active": account.is_active
            }
            for account in accounts
        ], 200

    @accounts_ns.doc(security="BearerAuth")
    @accounts_ns.response(415, "JSON content type required")
    @accounts_ns.expect(create_account_model, validate=True)
    @accounts_ns.response(201, "Account created", account_model)
    @accounts_ns.response(400, "Invalid account details")
    @accounts_ns.response(401, "Authentication required")
    @accounts_ns.response(403, "Admin access required")
    @accounts_ns.response(409, "Username already exists")
    @accounts_ns.response(422, "Malformed access token")
    @account_required(role="Admin")
    def post(self):
        """
        Create a new user account.

        Allows administrators to create an active User account
        with a unique username and securely hashed password.
        """

        # Read request data
        data = request.get_json()
        username = data["username"].strip()
        password = data["password"]

        # Validate username and password
        if not username or len(username) > 100:
            return {"message": "Invalid username"}, 400

        if not password.strip() or len(password) > 128:
            return {"message": "Invalid password"}, 400

        # Check whether username already exists
        existing = db.session.scalar(
            db.select(Account.id).filter_by(username=username)
        )

        if existing is not None:
            return {"message": "Username already exists"}, 409

        # Create a new active User account
        account = Account(
            username=username,
            password_hash=pbkdf2_sha256.hash(password),
            role="User",
            is_active=True
        )

        # Save account to database
        try:
            db.session.add(account)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return {"message": "Username already exists"}, 409

        # Return new account details
        return {
            "id": account.id,
            "username": account.username,
            "role": account.role,
            "is_active": account.is_active
        }, 201
    

@accounts_ns.route("/<int:account_id>")
class AccountDetail(Resource):
    """
    Manage an individual user account.

    Provides administrator-only operations for updating
    or deleting a specific user account.
    """

    @accounts_ns.doc(security="BearerAuth")
    @accounts_ns.response(415, "JSON content type required")
    @accounts_ns.expect(account_status_model, validate=True)
    @accounts_ns.response(200, "Account status updated", account_model)
    @accounts_ns.response(400, "Invalid request")
    @accounts_ns.response(401, "Authentication required")
    @accounts_ns.response(403, "Operation not permitted")
    @accounts_ns.response(404, "Account not found")
    @accounts_ns.response(500, "Account deletion failed")
    @accounts_ns.response(422, "Malformed access token")
    @account_required(role="Admin")
    def patch(self, account_id):
        """
        Activate or deactivate a user account.

        Allows administrators to change a User account's
        active status. The Admin account cannot be deactivated.
        """

        # SQLite integer IDs cannot exceed the signed 64-bit range.
        if account_id > 9223372036854775807:
            return {"message": "Account not found"}, 404

        # Find the target account
        account = db.session.get(Account, account_id)

        if account is None:
            return {"message": "Account not found"}, 404

        # Protect the Admin account
        if account.role == "Admin":
            return {"message": "Admin account cannot be modified"}, 403

        # Read the requested status
        data = request.get_json()
        new_status = data["is_active"]

        # Update and save the account
        account.is_active = new_status
        db.session.commit()

        # Return updated account details
        return {
            "id": account.id,
            "username": account.username,
            "role": account.role,
            "is_active": account.is_active
        }, 200

    
    @accounts_ns.doc(
        security="BearerAuth",
        params={"account_id": "ID of the account to delete"}
    )
    @accounts_ns.response(204, "Account deleted successfully")
    @accounts_ns.response(401, "Authentication required")
    @accounts_ns.response(403, "Operation not permitted")
    @accounts_ns.response(404, "Account not found")
    @accounts_ns.response(422, "Malformed access token")
    @account_required(role="Admin")
    def delete(self, account_id):
        """
        Delete a user account.

        Allows administrators to permanently delete a User
        account. The Admin account cannot be deleted.
        """

        # SQLite integer IDs cannot exceed the signed 64-bit range.
        if account_id > 9223372036854775807:
            return {"message": "Account not found"}, 404

        # Find the target account
        account = db.session.get(Account, account_id)

        if account is None:
            return {"message": "Account not found"}, 404

        # Protect the Admin account
        if account.role == "Admin":
            return {"message": "Admin account cannot be deleted"}, 403

        # Delete plans and associations before the account, but never routes.
        # Keep all deletions in the same transaction.
        try:
            plan_ids = db.session.scalars(
                db.select(TravelPlan.plan_id).where(
                    TravelPlan.account_id == account_id
                )
            ).all()
            if plan_ids:
                db.session.execute(
                    db.delete(TravelPlanRoute).where(
                        TravelPlanRoute.plan_id.in_(plan_ids)
                    )
                )
                db.session.execute(
                    db.delete(TravelPlan).where(
                        TravelPlan.plan_id.in_(plan_ids)
                    )
                )
            db.session.delete(account)
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            return {"message": "Account deletion failed"}, 500

        # Return success without a response body
        return "", 204



# ============================================================
# Requirement Set 2: Data Import
# ============================================================

# ------------------------------------------------------------
# 1. Database Models
# ------------------------------------------------------------

class Airport(db.Model):
    """Store airport information imported from airports.csv."""

    __tablename__ = "airports"

    airport_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(100))
    country = db.Column(db.String(100))
    iata_code = db.Column(db.String(3))
    icao_code = db.Column(db.String(4))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    altitude = db.Column(db.Integer)
    timezone = db.Column(db.String(100))


class Airline(db.Model):
    """Store airline information imported from airlines.csv."""

    __tablename__ = "airlines"

    airline_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    iata_code = db.Column(db.String(2))
    icao_code = db.Column(db.String(3))
    country = db.Column(db.String(100))


class Route(db.Model):
    """Store flight routes imported from routes.csv."""

    __tablename__ = "routes"

    route_id = db.Column(db.Integer, primary_key=True)

    airline_id = db.Column(db.Integer, nullable=False)
    airline_iata = db.Column(db.String(2))

    origin_airport_id = db.Column(
        db.Integer, nullable=False
    )
    origin_iata = db.Column(db.String(3))

    destination_airport_id = db.Column(
        db.Integer, nullable=False
    )
    destination_iata = db.Column(db.String(3))

    codeshare = db.Column(db.String(10))
    stops = db.Column(db.Integer, nullable=False)
    equipment = db.Column(db.String(100))

# ------------------------------------------------------------
# 2. CSV Parsing and Validation
# ------------------------------------------------------------

# Expected CSV columns and data types
CSV_SCHEMAS = {
    "airports": {
        "airport_id": int,
        "name": str,
        "city": str,
        "country": str,
        "iata_code": str,
        "icao_code": str,
        "latitude": float,
        "longitude": float,
        "altitude": int,
        "timezone": str,
    },
    "airlines": {
        "airline_id": int,
        "name": str,
        "iata_code": str,
        "icao_code": str,
        "country": str,
    },
    "routes": {
        "route_id": int,
        "airline_id": int,
        "airline_iata": str,
        "origin_airport_id": int,
        "origin_iata": str,
        "destination_airport_id": int,
        "destination_iata": str,
        "codeshare": str,
        "stops": int,
        "equipment": str,
    },
}

PRIMARY_KEYS = {
    "airports": "airport_id",
    "airlines": "airline_id",
    "routes": "route_id",
}

REQUIRED_COLUMNS = {
    "airports": {"airport_id", "name"},
    "airlines": {"airline_id", "name"},
    "routes": {
        "route_id",
        "airline_id",
        "origin_airport_id",
        "destination_airport_id",
        "stops",
    },
}


def parse_csv(dataset, content):
    """
    Parse and validate an uploaded CSV dataset.

    Checks column names, data types, required values,
    and duplicate primary keys without modifying the database.
    """

    schema = CSV_SCHEMAS[dataset]
    primary_key = PRIMARY_KEYS[dataset]

    try:
        # Decode CSV bytes and read rows
        text = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text), strict=True)

        # Validate column names
        columns = reader.fieldnames

        if (
            columns is None
            or len(columns) != len(schema)
            or set(columns) != set(schema)
        ):
            raise ValueError(
                f"Invalid columns in {dataset}. Expected: {list(schema)}"
            )

        records = []
        seen_ids = set()

        for row_number, row in enumerate(reader, start=2):

            # Reject malformed rows
            if None in row or any(value is None for value in row.values()):
                raise ValueError(
                    f"{dataset}, row {row_number}: Invalid column count"
                )

            record = {}

            for column, data_type in schema.items():
                value = row[column].strip()

                # Handle missing values
                if not value:
                    if column in REQUIRED_COLUMNS[dataset]:
                        raise ValueError(
                            f"{dataset}, row {row_number}: "
                            f"Missing {column}"
                        )

                    record[column] = None
                    continue

                # Convert data types
                try:
                    converted = data_type(value)
                except (ValueError, OverflowError):
                    raise ValueError(
                        f"{dataset}, row {row_number}: "
                        f"Invalid {column}: {value}"
                    )

                # SQLite INTEGER values must fit in a signed 64-bit integer.
                if data_type is int and not -(2 ** 63) <= converted <= 2 ** 63 - 1:
                    raise ValueError(
                        f"{dataset}, row {row_number}: "
                        f"{column} is outside the signed 64-bit integer range"
                    )

                # Reject NaN and Infinity
                if data_type is float and not math.isfinite(converted):
                    raise ValueError(
                        f"{dataset}, row {row_number}: Invalid {column}"
                    )

                record[column] = converted

            # Validate dataset-specific field constraints
            if dataset == "airports":
                latitude = record["latitude"]
                longitude = record["longitude"]

                if latitude is not None and not -90 <= latitude <= 90:
                    raise ValueError(
                        f"airports, row {row_number}: Invalid latitude"
                    )

                if longitude is not None and not -180 <= longitude <= 180:
                    raise ValueError(
                        f"airports, row {row_number}: Invalid longitude"
                    )

            elif dataset == "routes":
                if record["stops"] < 0:
                    raise ValueError(
                        f"routes, row {row_number}: Invalid stops"
                    )

                for field in (
                    "airline_id",
                    "origin_airport_id",
                    "destination_airport_id",
                ):
                    if record[field] <= 0:
                        raise ValueError(
                            f"routes, row {row_number}: Invalid {field}"
                        )

            # Validate primary key
            record_id = record[primary_key]

            if record_id <= 0:
                raise ValueError(
                    f"{dataset}, row {row_number}: Invalid ID"
                )

            if record_id in seen_ids:
                raise ValueError(
                    f"{dataset}, row {row_number}: Duplicate ID {record_id}"
                )

            seen_ids.add(record_id)
            records.append(record)

        return records

    except (UnicodeDecodeError, csv.Error) as error:
        raise ValueError(
            f"Cannot parse {dataset} CSV: {error}"
        ) from error


class ReferenceConflictError(ValueError):
    """Indicate a missing reference between datasets."""

def validate_references(airports, airlines, routes):
    """
    Validate relationships between airlines, airports, and routes.
    """

    # Build lookup dictionaries by primary key
    airport_by_id = {
        airport["airport_id"]: airport
        for airport in airports
    }

    airline_by_id = {
        airline["airline_id"]: airline
        for airline in airlines
    }

    # Validate every route
    for route in routes:
        route_id = route["route_id"]

        references = [
            (
                "airline",
                route["airline_id"],
                route["airline_iata"],
                airline_by_id,
            ),
            (
                "origin airport",
                route["origin_airport_id"],
                route["origin_iata"],
                airport_by_id,
            ),
            (
                "destination airport",
                route["destination_airport_id"],
                route["destination_iata"],
                airport_by_id,
            ),
        ]

        for label, reference_id, iata, lookup in references:

            # Check whether the referenced record exists
            if reference_id not in lookup:
                raise ReferenceConflictError(
                    f"Route {route_id}: "
                    f"{label} ID {reference_id} does not exist"
                )

            # Check whether the IATA code matches
            expected_iata = lookup[reference_id]["iata_code"]

            if iata is not None and iata != expected_iata:
                raise ValueError(
                    f"Route {route_id}: "
                    f"{label} IATA mismatch "
                    f"(expected {expected_iata}, got {iata})"
                )

# ------------------------------------------------------------
# 3. Multipart Import and Atomic Replacement
# ------------------------------------------------------------

imports_ns = api.namespace(
    "Data Import",
    description= "Admin-only CSV imports.",
    path="/imports"
)

import_counts_model = imports_ns.model("ImportCounts", {
    dataset: fields.Integer(description=f"Number of imported {dataset}")
    for dataset in ("airports", "airlines", "routes")
})

import_response_model = imports_ns.model("ImportResponse", {
    "message": fields.String(required=True),
    "datasets": fields.List(fields.String, required=True),
    "counts": fields.Nested(
        import_counts_model, required=True,
        description="Record counts for uploaded datasets only"
    )
})

upload_parser = imports_ns.parser()

for dataset in ("airports", "airlines", "routes"):
    upload_parser.add_argument(
        dataset,
        type=FileStorage,
        location="files",
        required=False,
        help=f"Upload {dataset}.csv"
    )

DATASET_MODELS = {
    "airports": Airport,
    "airlines": Airline,
    "routes": Route,
}

def load_dataset(dataset):
    """Load existing dataset records as dictionaries."""

    model = DATASET_MODELS[dataset]

    records = db.session.scalars(
        db.select(model)
    ).all()

    return [
        {
            column.name: getattr(record, column.name)
            for column in model.__table__.columns
        }
        for record in records
    ]


@imports_ns.route("")
class DataImport(Resource):
    """
    Import airport, airline, and route datasets.

    Supports independent or combined CSV uploads.
    """

    @imports_ns.doc(
        security="BearerAuth",
        description=(
            "Admin-only CSV import with atomic dataset replacement. "
            "Referenced Travel Plan routes cannot be removed or changed "
            "(HTTP 409)."
        )
    )
    @imports_ns.expect(upload_parser)
    @imports_ns.response(200, "Datasets imported successfully", import_response_model)
    @imports_ns.response(400, "Invalid CSV or upload request")
    @imports_ns.response(401, "Authentication required")
    @imports_ns.response(403, "Admin access required")
    @imports_ns.response(409, "Referential integrity conflict")
    @imports_ns.response(415, "Multipart form data required")
    @imports_ns.response(422, "Malformed access token")
    @imports_ns.response(500, "Database import failed, including lock timeout")
    @account_required(role="Admin")
    def post(self):
        """
        Import and replace selected CSV datasets.
        """

        # Require multipart/form-data
        if request.mimetype != "multipart/form-data":
            return {"message": "Expected multipart/form-data"}, 415

        # Require at least one uploaded file
        if not request.files:
            return {"message": "No CSV files uploaded"}, 400

        # Reject unexpected file fields
        unknown = set(request.files) - set(DATASET_MODELS)

        if unknown:
            return {
                "message": f"Unknown datasets: {sorted(unknown)}"
            }, 400

        replacements = {}

        try:
            # Step 1: Parse all uploaded CSV files
            for dataset in request.files:

                files = request.files.getlist(dataset)

                if len(files) != 1 or not files[0].filename:
                    raise ValueError(
                        f"Exactly one file is required for {dataset}"
                    )

                replacements[dataset] = parse_csv(
                    dataset,
                    files[0].read()
                )

            # End the read-only transaction started by authentication before
            # acquiring SQLite's write reservation. Commit/rollback releases it.
            db.session.rollback()
            db.session.connection().exec_driver_sql("BEGIN IMMEDIATE")

            # Step 2: Build the combined final dataset under the write lock
            combined = {}

            for dataset in DATASET_MODELS:
                if dataset in replacements:
                    combined[dataset] = replacements[dataset]
                else:
                    combined[dataset] = load_dataset(dataset)

            # Step 3: Validate all references
            validate_references(
                combined["airports"],
                combined["airlines"],
                combined["routes"]
            )

            # Referenced routes are immutable while they belong to a Travel
            # Plan. Check them before replacing the uploaded routes dataset.
            preserved_route_ids = set()
            if "routes" in replacements:
                referenced_route_ids = set(db.session.scalars(
                    db.select(TravelPlanRoute.route_id).distinct()
                ).all())
                uploaded_routes = {
                    route["route_id"]: route
                    for route in combined["routes"]
                }
                route_columns = tuple(column.name for column in Route.__table__.columns)

                for route_id in referenced_route_ids:
                    existing_route = db.session.get(Route, route_id)
                    uploaded_route = uploaded_routes.get(route_id)

                    if uploaded_route is None:
                        raise ReferenceConflictError(
                            f"Route {route_id} referenced by a Travel Plan "
                            "does not exist in the imported dataset"
                        )

                    existing_values = {
                        column: getattr(existing_route, column)
                        for column in route_columns
                    }
                    if any(
                        existing_values[column] != uploaded_route[column]
                        for column in route_columns
                    ):
                        raise ReferenceConflictError(
                            f"Route {route_id} referenced by a Travel Plan "
                            "cannot be modified"
                        )

                    preserved_route_ids.add(route_id)

            # Step 4: Replace only uploaded datasets
            # Delete routes not protected by a Travel Plan before replacing
            # parent datasets. Protected route rows remain in place.
            if "routes" in replacements:
                db.session.execute(
                    db.delete(Route).where(
                        ~Route.route_id.in_(preserved_route_ids)
                    )
                )

            for dataset in ("airports", "airlines"):
                if dataset in replacements:
                    db.session.execute(
                        db.delete(DATASET_MODELS[dataset])
                    )

            # Insert parent datasets before routes
            for dataset in ("airports", "airlines", "routes"):
                if dataset in replacements and replacements[dataset]:
                    records = replacements[dataset]
                    if dataset == "routes" and preserved_route_ids:
                        records = [
                            route for route in records
                            if route["route_id"] not in preserved_route_ids
                        ]
                    if not records:
                        continue
                    db.session.execute(
                        db.insert(DATASET_MODELS[dataset]),
                        records
                    )

            # Step 5: Commit all changes together
            db.session.commit()

        except ReferenceConflictError as error:
            db.session.rollback()
            return {"message": str(error)}, 409

        except ValueError as error:
            db.session.rollback()
            return {"message": str(error)}, 400

        except SQLAlchemyError:
            db.session.rollback()
            return {"message": "Database import failed"}, 500

        return {
            "message": "Import completed successfully",
            "datasets": list(replacements),
            "counts": {
                dataset: len(records)
                for dataset, records in replacements.items()
            }
        }, 200


# ============================================================
# Requirement Set 3: Data Exploration
# ============================================================

def is_sqlite_integer(value):
    """Check whether an integer fits SQLite's signed 64-bit range."""
    return -(2 ** 63) <= value <= 2 ** 63 - 1


def sqlite_query_integer(value):
    """Parse a query integer and reject overflow before any database query."""
    value = int(value)
    if not is_sqlite_integer(value):
        raise ValueError("Must fit a signed 64-bit integer")
    return value


sqlite_query_integer.__schema__ = {"type": "integer", "format": "int64"}


def register_unicode_casefold(connection, connection_record):
    """Register a dedicated Unicode function on each application DB connection."""
    connection.create_function(
        "unicode_casefold", 1,
        lambda value: value.casefold() if value is not None else None,
        deterministic=True
    )


with app.app_context():
    event.listen(db.engine, "connect", register_unicode_casefold)


def unicode_search_condition(search, *columns):
    """Build a case-insensitive partial match for both results and counts."""
    pattern = f"%{search.casefold()}%"
    return or_(*(db.func.unicode_casefold(column).like(pattern) for column in columns))


# ------------------------------------------------------------
# 1. Airport Exploration
# ------------------------------------------------------------
airports_ns = api.namespace(
    "airports",
    path="/airports",
    description="Browse and search airports. Available to all active accounts."
)

airport_links_model = airports_ns.model(
    "AirportLinks",
    {
        "self": fields.String,
        "airlines": fields.String,
        "departing_routes": fields.String,
    }
)

airport_response_model = airports_ns.model(
    "AirportDetails",
    {
        "airport_id": fields.Integer,
        "name": fields.String,
        "city": fields.String,
        "country": fields.String,
        "iata_code": fields.String,
        "icao_code": fields.String,
        "latitude": fields.Float,
        "longitude": fields.Float,
        "altitude": fields.Integer,
        "timezone": fields.String,
        "links": fields.Nested(airport_links_model),
    }
)

airport_list_model = airports_ns.model(
    "AirportList",
    {
        "total": fields.Integer,
        "limit": fields.Integer,
        "offset": fields.Integer,
        "items": fields.List(fields.Nested(airport_response_model)),
    }
)

airport_query_parser = airports_ns.parser()

airport_query_parser.add_argument(
    "q", type=str, location="args",
    help="Case-insensitive partial search by name, city, country or IATA"
)
airport_query_parser.add_argument(
    "limit", type=sqlite_query_integer, location="args", default=20,
    help="Page size (1–100)"
)
airport_query_parser.add_argument(
    "offset", type=sqlite_query_integer, location="args", default=0,
    help="Number of records to skip (0 or greater)"
)

def airport_to_dict(airport):
    """Convert an Airport record into an API response."""

    result = {
        column.name: getattr(airport, column.name)
        for column in Airport.__table__.columns
    }

    airport_id = airport.airport_id

    result["links"] = {
        "self": f"/airports/{airport_id}",
        "airlines": f"/airlines?airport_id={airport_id}",
        "departing_routes": f"/routes?origin_airport_id={airport_id}",
    }

    return result

# Airport list and detail endpoints with search, pagination, and authentication
@airports_ns.route("")
class AirportListResource(Resource):

    @airports_ns.doc(
        security="BearerAuth",
        description="List and search airports. Admin and User can access."
    )
    @airports_ns.expect(airport_query_parser)
    @airports_ns.response(200, "Airport list", airport_list_model)
    @airports_ns.response(400, "Invalid query parameters")
    @airports_ns.response(401, "Authentication required")
    @airports_ns.response(403, "Account inactive or access denied")
    @airports_ns.response(422, "Malformed access token")
    @account_required()
    def get(self):
        """List airports with optional search and pagination."""

        args = airport_query_parser.parse_args()
        search = (args["q"] or "").strip()
        limit = args["limit"]
        offset = args["offset"]

        if not 1 <= limit <= 100 or offset < 0:
            return {"message": "Invalid limit or offset"}, 400

        query = db.select(Airport)
        count_query = db.select(db.func.count()).select_from(Airport)

        if search:
            condition = unicode_search_condition(
                search,
                Airport.name,
                Airport.city,
                Airport.country,
                Airport.iata_code,
            )

            query = query.where(condition)
            count_query = count_query.where(condition)

        total = db.session.scalar(count_query)

        airports = db.session.scalars(
            query.order_by(Airport.airport_id)
                 .limit(limit)
                 .offset(offset)
        ).all()

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": [
                airport_to_dict(airport)
                for airport in airports
            ],
        }, 200


@airports_ns.route("/<int:airport_id>")
class AirportDetailResource(Resource):

    @airports_ns.doc(
        security="BearerAuth",
        description="Retrieve an airport by ID. Admin and User can access."
    )
    @airports_ns.response(200, "Airport details", airport_response_model)
    @airports_ns.response(401, "Authentication required")
    @airports_ns.response(403, "Account inactive or access denied")
    @airports_ns.response(422, "Malformed access token")
    @airports_ns.response(404, "Airport not found")
    @account_required()
    def get(self, airport_id):
        """Retrieve detailed information about one airport."""

        if not is_sqlite_integer(airport_id):
            return {"message": "Airport not found"}, 404

        airport = db.session.get(Airport, airport_id)

        if airport is None:
            return {"message": "Airport not found"}, 404

        return airport_to_dict(airport), 200


# ------------------------------------------------------------
# 2. Airline Exploration
# ------------------------------------------------------------

airlines_ns = api.namespace(
    "airlines",
    path="/airlines",
    description="Browse and search airlines. Available to all active accounts."
)

airline_links_model = airlines_ns.model(
    "AirlineLinks",
    {
        "self": fields.String,
        "routes": fields.String,
    }
)

airline_response_model = airlines_ns.model(
    "AirlineDetails",
    {
        "airline_id": fields.Integer,
        "name": fields.String,
        "iata_code": fields.String,
        "icao_code": fields.String,
        "country": fields.String,
        "links": fields.Nested(airline_links_model),
    }
)

airline_list_model = airlines_ns.model(
    "AirlineList",
    {
        "total": fields.Integer,
        "limit": fields.Integer,
        "offset": fields.Integer,
        "items": fields.List(fields.Nested(airline_response_model)),
    }
)

airline_query_parser = airlines_ns.parser()

airline_query_parser.add_argument(
    "q", type=str, location="args",
    help="Case-insensitive partial search by name, country, IATA or ICAO"
)

airline_query_parser.add_argument(
    "airport_id", type=sqlite_query_integer, location="args",
    help="Filter airlines with routes departing from this airport"
)

airline_query_parser.add_argument(
    "limit", type=sqlite_query_integer, location="args", default=20,
    help="Page size (1–100)"
)

airline_query_parser.add_argument(
    "offset", type=sqlite_query_integer, location="args", default=0,
    help="Number of records to skip (0 or greater)"
)

def airline_to_dict(airline):
    """Convert an Airline record into an API response."""

    result = {
        column.name: getattr(airline, column.name)
        for column in Airline.__table__.columns
    }

    airline_id = airline.airline_id

    result["links"] = {
        "self": f"/airlines/{airline_id}",
        "routes": f"/routes?airline_id={airline_id}",
    }

    return result


@airlines_ns.route("")
class AirlineListResource(Resource):

    @airlines_ns.doc(
        security="BearerAuth",
        description=(
            "List and search airlines. Optionally filter by "
            "departure airport. Admin and User can access."
        )
    )
    @airlines_ns.expect(airline_query_parser)
    @airlines_ns.response(200, "Airline list", airline_list_model)
    @airlines_ns.response(400, "Invalid query parameters")
    @airlines_ns.response(401, "Authentication required")
    @airlines_ns.response(403, "Account inactive or access denied")
    @airlines_ns.response(422, "Malformed access token")
    @airlines_ns.response(404, "Airport not found")
    @account_required()
    def get(self):
        """List airlines with search, airport filtering and pagination."""

        args = airline_query_parser.parse_args()

        search = (args["q"] or "").strip()
        airport_id = args["airport_id"]
        limit = args["limit"]
        offset = args["offset"]

        if not 1 <= limit <= 100 or offset < 0:
            return {"message": "Invalid limit or offset"}, 400

        query = db.select(Airline)
        count_query = db.select(db.func.count()).select_from(Airline)

        # Filter airlines operating from a specific airport
        if airport_id is not None:

            if db.session.get(Airport, airport_id) is None:
                return {"message": "Airport not found"}, 404

            airline_ids = (
                db.select(Route.airline_id)
                .where(Route.origin_airport_id == airport_id)
            )

            query = query.where(
                Airline.airline_id.in_(airline_ids)
            )

            count_query = count_query.where(
                Airline.airline_id.in_(airline_ids)
            )

        # Case-insensitive partial search
        if search:
            condition = unicode_search_condition(
                search,
                Airline.name,
                Airline.country,
                Airline.iata_code,
                Airline.icao_code,
            )

            query = query.where(condition)
            count_query = count_query.where(condition)

        total = db.session.scalar(count_query)

        airlines = db.session.scalars(
            query.order_by(Airline.airline_id)
                 .limit(limit)
                 .offset(offset)
        ).all()

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": [
                airline_to_dict(airline)
                for airline in airlines
            ],
        }, 200


@airlines_ns.route("/<int:airline_id>")
class AirlineDetailResource(Resource):

    @airlines_ns.doc(
        security="BearerAuth",
        description="Retrieve an airline by ID. Admin and User can access."
    )
    @airlines_ns.response(200, "Airline details", airline_response_model)
    @airlines_ns.response(401, "Authentication required")
    @airlines_ns.response(403, "Account inactive or access denied")
    @airlines_ns.response(422, "Malformed access token")
    @airlines_ns.response(404, "Airline not found")
    @account_required()
    def get(self, airline_id):
        """Retrieve detailed information about one airline."""

        if not is_sqlite_integer(airline_id):
            return {"message": "Airline not found"}, 404

        airline = db.session.get(Airline, airline_id)

        if airline is None:
            return {"message": "Airline not found"}, 404

        return airline_to_dict(airline), 200


# ------------------------------------------------------------
# 3. Route Exploration
# ------------------------------------------------------------
routes_ns = api.namespace(
    "routes",
    path="/routes",
    description="Browse and filter routes. Available to all active accounts."
)

route_links_model = routes_ns.model(
    "RouteLinks",
    {
        "self": fields.String,
        "airline": fields.String,
        "origin_airport": fields.String,
        "destination_airport": fields.String,
    }
)

route_response_model = routes_ns.model(
    "RouteSummary",
    {
        "route_id": fields.Integer,
        "airline_id": fields.Integer,
        "airline_iata": fields.String,
        "origin_airport_id": fields.Integer,
        "origin_iata": fields.String,
        "destination_airport_id": fields.Integer,
        "destination_iata": fields.String,
        "codeshare": fields.String,
        "stops": fields.Integer,
        "equipment": fields.String,
        "links": fields.Nested(route_links_model),
    }
)

route_detail_model = routes_ns.inherit(
    "RouteDetails",
    route_response_model,
    {
        "airline": fields.Nested(airline_response_model),
        "origin_airport": fields.Nested(airport_response_model),
        "destination_airport": fields.Nested(airport_response_model),
    }
)

route_list_model = routes_ns.model(
    "RouteList",
    {
        "total": fields.Integer,
        "limit": fields.Integer,
        "offset": fields.Integer,
        "items": fields.List(fields.Nested(route_response_model)),
    }
)


route_query_parser = routes_ns.parser()

route_query_parser.add_argument(
    "airline_id", type=sqlite_query_integer, location="args",
    help="Filter by airline ID"
)

route_query_parser.add_argument(
    "origin_airport_id", type=sqlite_query_integer, location="args",
    help="Filter by departure airport ID"
)

route_query_parser.add_argument(
    "destination_airport_id", type=sqlite_query_integer, location="args",
    help="Filter by destination airport ID"
)

route_query_parser.add_argument(
    "limit", type=sqlite_query_integer, location="args", default=20,
    help="Page size (1–100)"
)

route_query_parser.add_argument(
    "offset", type=sqlite_query_integer, location="args", default=0,
    help="Number of records to skip (0 or greater)"
)

def route_to_dict(route, include_related=False):
    """
    Convert a Route record into an API response.

    Optionally include full airline and airport details.
    """

    result = {
        column.name: getattr(route, column.name)
        for column in Route.__table__.columns
    }

    result["links"] = {
        "self": f"/routes/{route.route_id}",
        "airline": f"/airlines/{route.airline_id}",
        "origin_airport": f"/airports/{route.origin_airport_id}",
        "destination_airport": f"/airports/{route.destination_airport_id}",
    }

    if include_related:
        airline = db.session.get(Airline, route.airline_id)
        origin = db.session.get(Airport, route.origin_airport_id)
        destination = db.session.get(
            Airport, route.destination_airport_id
        )

        result["airline"] = airline_to_dict(airline) if airline else None
        result["origin_airport"] = (
            airport_to_dict(origin) if origin else None
        )
        result["destination_airport"] = (
            airport_to_dict(destination) if destination else None
        )

    return result


@routes_ns.route("")
class RouteListResource(Resource):

    @routes_ns.doc(
        security="BearerAuth",
        description=(
            "List routes with optional airline, origin airport, "
            "and destination airport filters. Filters can be combined. "
            "Available to Admin and User."
        )
    )
    @routes_ns.expect(route_query_parser)
    @routes_ns.response(200, "Route list", route_list_model)
    @routes_ns.response(400, "Invalid query parameters")
    @routes_ns.response(401, "Authentication required")
    @routes_ns.response(403, "Account inactive or access denied")
    @routes_ns.response(422, "Malformed access token")
    @routes_ns.response(404, "Referenced airline or airport not found")
    @account_required()
    def get(self):
        """List routes with filtering and pagination."""

        args = route_query_parser.parse_args()

        limit = args["limit"]
        offset = args["offset"]

        if not 1 <= limit <= 100 or offset < 0:
            return {"message": "Invalid limit or offset"}, 400

        # Filter settings: value, model, column, resource name
        filters = [
            (
                args["airline_id"],
                Airline,
                Route.airline_id,
                "Airline",
            ),
            (
                args["origin_airport_id"],
                Airport,
                Route.origin_airport_id,
                "Origin airport",
            ),
            (
                args["destination_airport_id"],
                Airport,
                Route.destination_airport_id,
                "Destination airport",
            ),
        ]

        conditions = []

        for resource_id, model, column, name in filters:
            if resource_id is not None:

                if db.session.get(model, resource_id) is None:
                    return {"message": f"{name} not found"}, 404

                conditions.append(column == resource_id)

        query = db.select(Route).where(*conditions)

        count_query = (
            db.select(db.func.count())
            .select_from(Route)
            .where(*conditions)
        )

        total = db.session.scalar(count_query)

        routes = db.session.scalars(
            query.order_by(Route.route_id)
                 .limit(limit)
                 .offset(offset)
        ).all()

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": [
                route_to_dict(route)
                for route in routes
            ],
        }, 200


@routes_ns.route("/<int:route_id>")
class RouteDetailResource(Resource):

    @routes_ns.doc(
        security="BearerAuth",
        description=(
            "Retrieve a route with full airline, origin airport, "
            "and destination airport details. Available to Admin and User."
        )
    )
    @routes_ns.response(200, "Route details", route_detail_model)
    @routes_ns.response(401, "Authentication required")
    @routes_ns.response(403, "Account inactive or access denied")
    @routes_ns.response(422, "Malformed access token")
    @routes_ns.response(404, "Route not found")
    @account_required()
    def get(self, route_id):
        """Retrieve a route with its related resources."""

        if not is_sqlite_integer(route_id):
            return {"message": "Route not found"}, 404

        route = db.session.get(Route, route_id)

        if route is None:
            return {"message": "Route not found"}, 404

        return route_to_dict(route, include_related=True), 200


# ============================================================
# Requirement Set 4: My Travel Plans
# ============================================================

# ------------------------------------------------------------
# 1. Database Models
# ------------------------------------------------------------

class TravelPlan(db.Model):
    """Store a private travel plan belonging to one account."""

    __tablename__ = "travel_plans"

    plan_id = db.Column(db.Integer, primary_key=True)

    account_id = db.Column(
        db.Integer,
        db.ForeignKey("accounts.id"),
        nullable=False,
        index=True
    )

    name = db.Column(db.String(255), nullable=False)
    departure_date = db.Column(db.Date, nullable=False)
    return_date = db.Column(db.Date, nullable=False)

    # Return date cannot precede departure date
    __table_args__ = (
        db.CheckConstraint(
            "return_date >= departure_date",
            name="ck_travel_plan_dates"
        ),
    )

    # One plan can contain multiple routes
    route_links = db.relationship(
        "TravelPlanRoute",
        back_populates="plan",
        cascade="all, delete-orphan"
    )


class TravelPlanRoute(db.Model):
    """Associate travel plans with their selected routes."""

    __tablename__ = "travel_plan_routes"

    plan_id = db.Column(
        db.Integer,
        db.ForeignKey("travel_plans.plan_id", ondelete="CASCADE"),
        primary_key=True
    )

    route_id = db.Column(
        db.Integer,
        db.ForeignKey("routes.route_id", ondelete="RESTRICT"),
        primary_key=True
    )

    plan = db.relationship(
        "TravelPlan",
        back_populates="route_links"
    )

    route = db.relationship("Route")


# ------------------------------------------------------------
# 2. Travel Plan CRUD
# ------------------------------------------------------------
travel_plans_ns = api.namespace(
    "travel-plans",
    path="/travel-plans",
    description="Manage private travel plans for the authenticated account."
)

travel_plan_request_model = travel_plans_ns.model(
    "CreateTravelPlanRequest",
    {
        "name": fields.String(required=True),
        "departure_date": fields.String(
            required=True,
            description="Date in YYYY-MM-DD format"
        ),
        "return_date": fields.String(
            required=True,
            description="Date in YYYY-MM-DD format"
        ),
    }
)

travel_plan_response_model = travel_plans_ns.model(
    "TravelPlanDetails",
    {
        "plan_id": fields.Integer,
        "name": fields.String,
        "departure_date": fields.String,
        "return_date": fields.String,
        "routes": fields.List(fields.Integer),
    }
)

travel_plan_list_model = travel_plans_ns.model(
    "TravelPlanList",
    {
        "total": fields.Integer,
        "items": fields.List(
            fields.Nested(travel_plan_response_model)
        ),
    }
)

add_route_request_model = travel_plans_ns.model(
    "AddPlanRouteRequest",
    {
        "route_id": fields.Integer(
            required=True,
            description="ID of an existing route"
        )
    }
)


def travel_plan_to_dict(plan):
    """Convert a travel plan into a JSON-compatible dictionary."""

    return {
        "plan_id": plan.plan_id,
        "name": plan.name,
        "departure_date": plan.departure_date.isoformat(),
        "return_date": plan.return_date.isoformat(),
        "routes": [
            link.route_id for link in plan.route_links
        ],
    }


def parse_plan_date(value, field_name):
    """Validate and parse an ISO-format travel date."""

    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}", value
    ):
        raise ValueError(
            f"{field_name} must use YYYY-MM-DD format"
        )

    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(
            f"{field_name} is not a valid date"
        ) from None


@travel_plans_ns.route("")
class TravelPlanListResource(Resource):

    @travel_plans_ns.doc(
        security="BearerAuth",
        description="Create a private travel plan for the current account."
    )
    @travel_plans_ns.expect(travel_plan_request_model)
    @travel_plans_ns.response(
        201, "Travel plan created", travel_plan_response_model
    )
    @travel_plans_ns.response(400, "Invalid plan details")
    @travel_plans_ns.response(401, "Authentication required")
    @travel_plans_ns.response(403, "Account inactive or access denied")
    @travel_plans_ns.response(422, "Invalid authentication token")
    @account_required()
    def post(self):
        """Create a travel plan."""

        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return {"message": "A JSON object is required"}, 400

        name = data.get("name")

        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 255:
            return {"message": "Invalid travel plan name"}, 400

        try:
            departure_date = parse_plan_date(
                data.get("departure_date"),
                "departure_date"
            )

            return_date = parse_plan_date(
                data.get("return_date"),
                "return_date"
            )

        except ValueError as error:
            return {"message": str(error)}, 400

        if return_date < departure_date:
            return {
                "message": "Return date cannot be earlier than departure date"
            }, 400

        # Ownership comes from the authenticated account, not the request.
        plan = TravelPlan(
            account_id=g.current_account.id,
            name=name.strip(),
            departure_date=departure_date,
            return_date=return_date,
        )

        db.session.add(plan)
        db.session.commit()

        return (
            travel_plan_to_dict(plan),
            201,
            {"Location": f"/travel-plans/{plan.plan_id}"}
        )

    
    @travel_plans_ns.doc(
        security="BearerAuth",
        description="List private travel plans belonging to the current account."
    )
    @travel_plans_ns.response(
        200, "Travel plans retrieved", travel_plan_list_model
    )
    @travel_plans_ns.response(401, "Authentication required")
    @travel_plans_ns.response(403, "Account inactive or access denied")
    @travel_plans_ns.response(422, "Invalid authentication token")
    @account_required()
    def get(self):
        """List my travel plans."""

        account_id = g.current_account.id

        plans = db.session.scalars(
            db.select(TravelPlan)
            .where(TravelPlan.account_id == account_id)
            .order_by(TravelPlan.departure_date, TravelPlan.plan_id)
        ).all()

        return {
            "total": len(plans),
            "items": [
                travel_plan_to_dict(plan)
                for plan in plans
            ],
        }, 200


@travel_plans_ns.route("/<int:plan_id>")
class TravelPlanDetailResource(Resource):

    @travel_plans_ns.doc(
        security="BearerAuth",
        description="Retrieve a travel plan owned by the current account."
    )
    @travel_plans_ns.response(
        200, "Travel plan details", travel_plan_response_model
    )
    @travel_plans_ns.response(401, "Authentication required")
    @travel_plans_ns.response(403, "Account inactive or access denied")
    @travel_plans_ns.response(404, "Travel plan not found")
    @travel_plans_ns.response(422, "Invalid authentication token")
    @account_required()
    def get(self, plan_id):
        """Retrieve one of my travel plans."""

        # An out-of-range SQLite ID cannot exist
        if plan_id > 9223372036854775807:
            return {"message": "Travel plan not found"}, 404

        plan = db.session.scalar(
            db.select(TravelPlan).where(
                TravelPlan.plan_id == plan_id,
                TravelPlan.account_id == g.current_account.id
            )
        )

        if plan is None:
            return {"message": "Travel plan not found"}, 404

        return travel_plan_to_dict(plan), 200

    
    @travel_plans_ns.doc(
        security="BearerAuth",
        description="Update a travel plan owned by the current account."
    )
    @travel_plans_ns.expect(travel_plan_request_model)
    @travel_plans_ns.response(
        200, "Travel plan updated", travel_plan_response_model
    )
    @travel_plans_ns.response(400, "Invalid plan details")
    @travel_plans_ns.response(401, "Authentication required")
    @travel_plans_ns.response(403, "Account inactive or access denied")
    @travel_plans_ns.response(404, "Travel plan not found")
    @travel_plans_ns.response(422, "Invalid authentication token")
    @account_required()
    def put(self, plan_id):
        """Update my travel plan."""

        # Check ownership
        if plan_id > 9223372036854775807:
            return {"message": "Travel plan not found"}, 404

        plan = db.session.scalar(
            db.select(TravelPlan).where(
                TravelPlan.plan_id == plan_id,
                TravelPlan.account_id == g.current_account.id
            )
        )

        if plan is None:
            return {"message": "Travel plan not found"}, 404

        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return {"message": "A JSON object is required"}, 400

        name = data.get("name")

        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 255:
            return {"message": "Invalid travel plan name"}, 400

        try:
            departure_date = parse_plan_date(
                data.get("departure_date"),
                "departure_date"
            )
            return_date = parse_plan_date(
                data.get("return_date"),
                "return_date"
            )
        except ValueError as error:
            return {"message": str(error)}, 400

        if return_date < departure_date:
            return {
                "message": "Return date cannot be earlier than departure date"
            }, 400

        # Update the existing record
        plan.name = name.strip()
        plan.departure_date = departure_date
        plan.return_date = return_date

        db.session.commit()

        return travel_plan_to_dict(plan), 200

    @travel_plans_ns.doc(
        security="BearerAuth",
        description="Delete a travel plan owned by the current account."
    )
    @travel_plans_ns.response(204, "Travel plan deleted")
    @travel_plans_ns.response(401, "Authentication required")
    @travel_plans_ns.response(403, "Account inactive or access denied")
    @travel_plans_ns.response(404, "Travel plan not found")
    @travel_plans_ns.response(422, "Invalid authentication token")
    @account_required()
    def delete(self, plan_id):
        """Delete my travel plan."""

        if plan_id > 9223372036854775807:
            return {"message": "Travel plan not found"}, 404

        plan = db.session.scalar(
            db.select(TravelPlan).where(
                TravelPlan.plan_id == plan_id,
                TravelPlan.account_id == g.current_account.id
            )
        )

        if plan is None:
            return {"message": "Travel plan not found"}, 404

        db.session.delete(plan)
        db.session.commit()

        return "", 204



# ------------------------------------------------------------
# 3. Travel Plan Route Management
# ------------------------------------------------------------

@travel_plans_ns.route("/<int:plan_id>/routes")
class TravelPlanRoutesResource(Resource):

    @travel_plans_ns.doc(
        security="BearerAuth",
        description="Add an existing route to a travel plan owned by the current account."
    )
    @travel_plans_ns.expect(add_route_request_model)
    @travel_plans_ns.response(
        201, "Route added", travel_plan_response_model
    )
    @travel_plans_ns.response(400, "Invalid route ID")
    @travel_plans_ns.response(401, "Authentication required")
    @travel_plans_ns.response(403, "Account inactive")
    @travel_plans_ns.response(404, "Plan or route not found")
    @travel_plans_ns.response(409, "Route already in plan")
    @travel_plans_ns.response(422, "Invalid authentication token")
    @account_required()
    def post(self, plan_id):
        """Add a route to my travel plan."""

        # Validate the plan ID before querying SQLite
        if not 1 <= plan_id <= 9223372036854775807:
            return {"message": "Travel plan not found"}, 404

        # Find the plan and verify ownership
        plan = db.session.scalar(
            db.select(TravelPlan).where(
                TravelPlan.plan_id == plan_id,
                TravelPlan.account_id == g.current_account.id
            )
        )

        if plan is None:
            return {"message": "Travel plan not found"}, 404

        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return {"message": "A JSON object is required"}, 400

        route_id = data.get("route_id")

        if type(route_id) is not int or not (
            1 <= route_id <= 9223372036854775807
        ):
            return {"message": "Invalid route_id"}, 400

        # The route must exist
        if db.session.get(Route, route_id) is None:
            return {"message": "Route not found"}, 404

        # Reject duplicate associations
        existing = db.session.get(
            TravelPlanRoute, (plan_id, route_id)
        )

        if existing is not None:
            return {"message": "Route already in travel plan"}, 409

        # Create the association
        link = TravelPlanRoute(
            plan_id=plan_id,
            route_id=route_id
        )

        db.session.add(link)
        db.session.commit()

        return (
            travel_plan_to_dict(plan),
            201,
            {"Location": f"/travel-plans/{plan_id}/routes/{route_id}"}
        )


@travel_plans_ns.route("/<int:plan_id>/routes/<int:route_id>")
class TravelPlanRouteResource(Resource):

    @travel_plans_ns.doc(
        security="BearerAuth",
        description="Remove a route from a travel plan owned by the current account."
    )
    @travel_plans_ns.response(204, "Route removed")
    @travel_plans_ns.response(401, "Authentication required")
    @travel_plans_ns.response(403, "Account inactive")
    @travel_plans_ns.response(404, "Plan or route association not found")
    @travel_plans_ns.response(422, "Invalid authentication token")
    @account_required()
    def delete(self, plan_id, route_id):
        """Remove a route from my travel plan."""

        max_id = 9223372036854775807

        if not 1 <= plan_id <= max_id or not 1 <= route_id <= max_id:
            return {"message": "Plan or route not found"}, 404

        # Verify ownership
        plan = db.session.scalar(
            db.select(TravelPlan).where(
                TravelPlan.plan_id == plan_id,
                TravelPlan.account_id == g.current_account.id
            )
        )

        if plan is None:
            return {"message": "Travel plan not found"}, 404

        # Find the association
        link = db.session.get(
            TravelPlanRoute, (plan_id, route_id)
        )

        if link is None:
            return {"message": "Route not in travel plan"}, 404

        # Delete only the association
        db.session.delete(link)
        db.session.commit()

        return "", 204


# ============================================================
# Requirement Set 5: Exporting Travel Plans
# ============================================================

# ------------------------------------------------------------
# 1. JSON Export
# ------------------------------------------------------------
export_plan_model = travel_plans_ns.model(
    "ExportTravelPlan",
    {
        "plan_id": fields.Integer,
        "name": fields.String,
        "departure_date": fields.String,
        "return_date": fields.String,
        "routes": fields.List(
            fields.Nested(route_detail_model)
        ),
    }
)

export_response_model = travel_plans_ns.model(
    "TravelPlansExport",
    {
        "plans": fields.List(
            fields.Nested(export_plan_model)
        ),
    }
)

export_query_parser = travel_plans_ns.parser()
export_query_parser.add_argument(
    "format",
    type=str,
    location="args",
    default="json",
    help="Export format: json for a JSON download or image for a PNG response",
)


@travel_plans_ns.route("/export")
class TravelPlanExportResource(Resource):

    @travel_plans_ns.doc(
        security="BearerAuth",
        description=(
            "Export only the current account's travel plans. "
            "Use format=json for a JSON download or format=image for a "
            "viewable PNG image of up to five upcoming plans."
        )
    )
    @travel_plans_ns.expect(export_query_parser)
    @travel_plans_ns.response(
        200, "JSON file download", export_response_model
    )
    @travel_plans_ns.response(400, "Unsupported export format")
    @travel_plans_ns.response(401, "Authentication required")
    @travel_plans_ns.response(403, "Account inactive")
    @travel_plans_ns.response(422, "Invalid authentication token")
    @account_required()
    def get(self):
        """Export my travel plans."""

        export_format = request.args.get("format", "json").lower()

        if export_format == "image":
            today = date.today()

            # Select up to five future plans owned by this account
            plans = db.session.scalars(
                db.select(TravelPlan)
                .where(
                    TravelPlan.account_id == g.current_account.id,
                    TravelPlan.departure_date > today
                )
                .order_by(
                    TravelPlan.departure_date,
                    TravelPlan.plan_id
                )
                .limit(5)
            ).all()

            if not plans:
                return {"message": "No upcoming travel plans"}, 404

            image = generate_travel_plans_image(plans)

            return send_file(
                image,
                mimetype="image/png",
                as_attachment=False,
                download_name="upcoming-travel-plans.png"
            )

        if export_format != "json":
            return {"message": "Unsupported export format"}, 400


        # Retrieve only the current account's plans
        plans = db.session.scalars(
            db.select(TravelPlan)
            .where(
                TravelPlan.account_id == g.current_account.id
            )
            .order_by(
                TravelPlan.departure_date,
                TravelPlan.plan_id
            )
        ).all()

        exported_plans = []

        for plan in plans:
            plan_data = travel_plan_to_dict(plan)

            # Replace route IDs with complete route details
            plan_data["routes"] = [
                route_to_dict(link.route, include_related=True)
                for link in sorted(
                    plan.route_links,
                    key=lambda link: link.route_id
                )
            ]

            exported_plans.append(plan_data)

        # Generate a downloadable UTF-8 JSON file
        content = json.dumps(
            {"plans": exported_plans},
            ensure_ascii=False,
            indent=2
        ).encode("utf-8")

        return send_file(
            BytesIO(content),
            mimetype="application/json",
            as_attachment=True,
            download_name="travel-plans.json"
        )


# ------------------------------------------------------------
# 2. Image Export
# ------------------------------------------------------------

def generate_travel_plans_image(plans):
    """Generate a PNG timeline for up to five future travel plans."""

    fig = Figure(
        figsize=(11, max(3.5, len(plans) * 0.9 + 2)),
        dpi=120
    )
    ax = fig.add_subplot(111)

    for index, plan in enumerate(plans):
        start = mdates.date2num(plan.departure_date)
        duration = (
            plan.return_date - plan.departure_date
        ).days + 1

        ax.barh(
            index,
            duration,
            left=start,
            height=0.55,
            color="#4263B8"
        )

    labels = [
        f"{plan.name[:30]} ({len(plan.route_links)} routes)"
        for plan in plans
    ]

    ax.set_yticks(range(len(plans)), labels)
    ax.invert_yaxis()

    locator = mdates.AutoDateLocator(
        minticks=3,
        maxticks=7
    )

    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(
        mdates.DateFormatter("%b %Y")
    )

    ax.set_title(
        "Upcoming Travel Plans",
        fontsize=17,
        fontweight="bold",
        loc="left",
        pad=20
    )

    ax.set_xlabel("Travel dates")
    ax.grid(axis="x", alpha=0.2)
    ax.set_axisbelow(True)

    for side in ("top", "right"):
        ax.spines[side].set_visible(False)

    fig.tight_layout()

    image = BytesIO()
    fig.savefig(image, format="png")
    image.seek(0)

    return image


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
