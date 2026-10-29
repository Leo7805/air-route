from hashlib import sha256

from flask import g, request
from flask_jwt_extended import create_access_token
from flask_restx import Resource, fields
from passlib.hash import pbkdf2_sha256

from ..auth import account_required
from ..extensions import db
from ..models import Account


def register_auth(api):
    namespace = getattr(api, "modular_namespace", api.namespace)(
        "Authentication",
        description="User authentication and JWT token management.",
        path="/auth",
    )
    account_model = _account_model(namespace)
    login_model = namespace.model(
        "Login",
        {
            "username": fields.String(required=True),
            "password": fields.String(required=True),
        },
    )
    login_response_model = namespace.model(
        "LoginResponse",
        {
            "access_token": fields.String(
                required=True,
                description="JWT access token",
            )
        },
    )

    @namespace.route("/login")
    class Login(Resource):
        """Handle user authentication."""

        @namespace.doc(security=[])
        @namespace.doc(
            summary="Authenticate a user",
            description="Validate credentials and return a JWT access token.",
        )
        @namespace.expect(login_model, validate=True)
        @namespace.response(200, "Login successful", login_response_model)
        @namespace.response(400, "Invalid request")
        @namespace.response(415, "JSON content type required")
        @namespace.response(401, "Invalid credentials")
        @namespace.response(403, "Account deactivated")
        def post(self):
            """Authenticate a user and generate a JWT access token."""
            data = request.get_json()
            username = data["username"]
            password = data["password"]

            if (
                not username
                or len(username) > 100
                or not password
                or len(password) > 128
            ):
                return {"message": "Invalid credentials"}, 401

            account = db.session.scalar(
                db.select(Account).filter_by(username=username)
            )
            if account is None or not pbkdf2_sha256.verify(
                password, account.password_hash
            ):
                return {"message": "Invalid credentials"}, 401

            if not account.is_active:
                return {"message": "Account deactivated"}, 403

            token = create_access_token(
                identity=str(account.id),
                additional_claims={
                    "account_key": sha256(
                        account.password_hash.encode()
                    ).hexdigest()
                },
            )
            return {"access_token": token}, 200

    @namespace.route("/me")
    class CurrentAccount(Resource):
        """Retrieve the current authenticated account."""

        @namespace.doc(security="BearerAuth")
        @namespace.doc(
            summary="Get the current account",
            description="Return the authenticated account details.",
        )
        @namespace.response(200, "Account details retrieved", account_model)
        @namespace.response(401, "Missing or invalid access token")
        @namespace.response(403, "Account deactivated")
        @namespace.response(422, "Malformed access token")
        @account_required()
        def get(self):
            """Retrieve the current authenticated account."""
            account = g.current_account
            return _account_response(account), 200


def _account_model(namespace):
    return namespace.model(
        "AccountResponse",
        {
            "id": fields.Integer(description="Unique account ID"),
            "username": fields.String(description="Account username"),
            "role": fields.String(description="Account role: Admin or User"),
            "is_active": fields.Boolean(description="Whether the account is active"),
        },
    )


def _account_response(account):
    return {
        "id": account.id,
        "username": account.username,
        "role": account.role,
        "is_active": account.is_active,
    }
