from functools import wraps
from hashlib import sha256

from flask import g
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required
from flask_jwt_extended.exceptions import JWTExtendedException, NoAuthorizationError
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from .extensions import db
from .models import Account


def register_error_handlers(api):
    @api.errorhandler(JWTExtendedException)
    def handle_jwt_request_error(error):
        status = 401 if isinstance(error, NoAuthorizationError) else 422
        return {"message": str(error)}, status

    @api.errorhandler(InvalidTokenError)
    def handle_invalid_token(error):
        status = 401 if isinstance(error, ExpiredSignatureError) else 422
        return {"message": str(error)}, status


def account_required(role=None):
    """Require an active account and optionally a specific role."""

    def decorator(func):
        @wraps(func)
        @jwt_required()
        def wrapper(*args, **kwargs):
            account_id = get_jwt_identity()
            if (
                not isinstance(account_id, str)
                or not account_id.isascii()
                or not account_id.isdecimal()
                or len(account_id) > 19
                or not 0 < int(account_id) <= 9223372036854775807
            ):
                return {"message": "Invalid account identity"}, 401

            account = db.session.get(Account, int(account_id))
            if account is None:
                return {"message": "Account not found"}, 401

            account_key = sha256(account.password_hash.encode()).hexdigest()
            if get_jwt().get("account_key") != account_key:
                return {"message": "Account credentials changed; log in again"}, 401

            if not account.is_active:
                return {"message": "Account deactivated"}, 403

            if role is not None and account.role != role:
                return {"message": "Insufficient permissions"}, 403

            g.current_account = account
            return func(*args, **kwargs)

        return wrapper

    return decorator
