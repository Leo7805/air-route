from secrets import token_hex

from flask import Flask
from flask_restx import Api
from passlib.hash import pbkdf2_sha256

from .api import (
    register_accounts,
    register_airlines,
    register_airports,
    register_auth,
    register_imports,
    register_routes,
    register_travel_plans,
)
from .auth import register_error_handlers
from .config import Config
from .extensions import db, jwt
from .models import Account

AUTHORISATIONS = {
    "BearerAuth": {
        "type": "apiKey",
        "in": "header",
        "name": "Authorization",
        "description": "Enter: ******",
    }
}


def create_app(config=None, *, instance_path=None):
    settings = Config.from_env()
    if config is not None:
        settings.update(config if isinstance(config, dict) else vars(config))

    if settings["APP_ENV"] not in {"development", "production"}:
        raise ValueError("AIRROUTE_ENV must be development or production")
    local_mode = settings["APP_ENV"] == "development" or settings["TESTING"]
    secret = settings["JWT_SECRET_KEY"]
    if local_mode:
        settings["JWT_SECRET_KEY"] = secret or token_hex(32)
    elif not isinstance(secret, str) or len(secret.encode("utf-8")) < 32:
        raise ValueError("Production requires JWT_SECRET_KEY of at least 32 bytes")

    app = Flask(__name__, instance_path=instance_path)
    app.config.from_mapping(settings)
    db.init_app(app)
    jwt.init_app(app)

    api = Api(
        app,
        title="AirRoute API",
        version="1.0",
        description=(
            "A RESTful API for managing airline travel data and personal travel plans."
        ),
        authorizations=AUTHORISATIONS,
        doc="/",
    )
    register_error_handlers(api)
    register_auth(api)
    register_accounts(api)
    register_airports(api, app)
    register_airlines(api, app)
    register_routes(api, app)
    register_imports(api)
    register_travel_plans(api)
    app.extensions["airroute_api"] = api
    return app


def init_db(app):
    with app.app_context():
        db.create_all()
        if app.config["APP_ENV"] != "development" and not app.testing:
            return
        if db.session.scalar(db.select(Account.id).limit(1)) is not None:
            return
        db.session.add_all(
            [
                Account(
                    username="admin",
                    password_hash=pbkdf2_sha256.hash("admin"),
                    role="Admin",
                    is_active=True,
                ),
                Account(
                    username="user",
                    password_hash=pbkdf2_sha256.hash("user"),
                    role="User",
                    is_active=True,
                ),
            ]
        )
        db.session.commit()


__all__ = ["create_app"]
