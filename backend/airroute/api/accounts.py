from flask import request
from flask_restx import Resource, fields
from passlib.hash import pbkdf2_sha256
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from ..auth import account_required
from ..extensions import db
from ..models import Account, TravelPlan, TravelPlanRoute
from .auth import _account_response


def register_accounts(api):
    namespace = getattr(api, "modular_namespace", api.namespace)(
        "Accounts",
        description="Administrator-only user account management.",
        path="/accounts",
    )
    account_model = namespace.model(
        "AccountResponse",
        {
            "id": fields.Integer(description="Unique account ID"),
            "username": fields.String(description="Account username"),
            "role": fields.String(description="Account role: Admin or User"),
            "is_active": fields.Boolean(description="Whether the account is active"),
        },
    )
    create_account_model = namespace.model(
        "CreateAccountRequest",
        {
            "username": fields.String(
                required=True,
                description="Unique username for the new account",
                example="alice",
            ),
            "password": fields.String(
                required=True,
                description="Password for the new account",
            ),
        },
        strict=True,
    )
    account_status_model = namespace.model(
        "UpdateAccountStatusRequest",
        {
            "is_active": fields.Boolean(
                required=True,
                description="New account status: true or false",
            )
        },
        strict=True,
    )

    @namespace.route("")
    class Accounts(Resource):
        """Manage user accounts."""

        @namespace.doc(security="BearerAuth")
        @namespace.doc(
            summary="List accounts",
            description="Return all accounts ordered by ID.",
        )
        @namespace.response(200, "Accounts retrieved successfully", [account_model])
        @namespace.response(401, "Authentication required")
        @namespace.response(403, "Admin access required")
        @namespace.response(422, "Malformed access token")
        @account_required(role="Admin")
        def get(self):
            """Retrieve all user accounts ordered by ID."""
            accounts = db.session.scalars(
                db.select(Account).order_by(Account.id)
            ).all()
            return [_account_response(account) for account in accounts], 200

        @namespace.doc(security="BearerAuth")
        @namespace.doc(
            summary="Create an account",
            description="Create an active User account.",
        )
        @namespace.response(415, "JSON content type required")
        @namespace.expect(create_account_model, validate=True)
        @namespace.response(201, "Account created", account_model)
        @namespace.response(400, "Invalid account details")
        @namespace.response(401, "Authentication required")
        @namespace.response(403, "Admin access required")
        @namespace.response(409, "Username already exists")
        @namespace.response(422, "Malformed access token")
        @account_required(role="Admin")
        def post(self):
            """Create a new active User account."""
            data = request.get_json()
            username = data["username"].strip()
            password = data["password"]

            if not username or len(username) > 100:
                return {"message": "Invalid username"}, 400
            if not password.strip() or len(password) > 128:
                return {"message": "Invalid password"}, 400

            existing = db.session.scalar(
                db.select(Account.id).filter_by(username=username)
            )
            if existing is not None:
                return {"message": "Username already exists"}, 409

            account = Account(
                username=username,
                password_hash=pbkdf2_sha256.hash(password),
                role="User",
                is_active=True,
            )
            try:
                db.session.add(account)
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                return {"message": "Username already exists"}, 409

            return _account_response(account), 201

    @namespace.route("/<int:account_id>")
    class AccountDetail(Resource):
        """Manage an individual user account."""

        @namespace.doc(security="BearerAuth")
        @namespace.doc(
            summary="Update account status",
            description="Activate or deactivate a User account.",
        )
        @namespace.response(415, "JSON content type required")
        @namespace.expect(account_status_model, validate=True)
        @namespace.response(200, "Account status updated", account_model)
        @namespace.response(400, "Invalid request")
        @namespace.response(401, "Authentication required")
        @namespace.response(403, "Operation not permitted")
        @namespace.response(404, "Account not found")
        @namespace.response(500, "Account deletion failed")
        @namespace.response(422, "Malformed access token")
        @account_required(role="Admin")
        def patch(self, account_id):
            """Activate or deactivate a User account."""
            if account_id > 9223372036854775807:
                return {"message": "Account not found"}, 404
            account = db.session.get(Account, account_id)
            if account is None:
                return {"message": "Account not found"}, 404
            if account.role == "Admin":
                return {"message": "Admin account cannot be modified"}, 403

            account.is_active = request.get_json()["is_active"]
            db.session.commit()
            return _account_response(account), 200

        @namespace.doc(
            security="BearerAuth",
            params={"account_id": "ID of the account to delete"},
        )
        @namespace.doc(
            summary="Delete an account",
            description="Delete a User account and its private plans.",
        )
        @namespace.response(204, "Account deleted successfully")
        @namespace.response(401, "Authentication required")
        @namespace.response(403, "Operation not permitted")
        @namespace.response(404, "Account not found")
        @namespace.response(422, "Malformed access token")
        @account_required(role="Admin")
        def delete(self, account_id):
            """Delete a User account and its private plans."""
            if account_id > 9223372036854775807:
                return {"message": "Account not found"}, 404
            account = db.session.get(Account, account_id)
            if account is None:
                return {"message": "Account not found"}, 404
            if account.role == "Admin":
                return {"message": "Admin account cannot be deleted"}, 403

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

            return "", 204
