import os
from datetime import timedelta


class Config:
    APP_ENV = "production"
    SQLALCHEMY_DATABASE_URI = "sqlite:///airroute.db"
    JWT_SECRET_KEY = None
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    TESTING = False

    @classmethod
    def from_env(cls):
        """Read environment overrides when an application is created."""
        settings = {key: getattr(cls, key) for key in dir(cls) if key.isupper()}
        settings.update(
            APP_ENV=os.environ.get("AIRROUTE_ENV", cls.APP_ENV),
            SQLALCHEMY_DATABASE_URI=os.environ.get(
                "DATABASE_URL", cls.SQLALCHEMY_DATABASE_URI
            ),
            JWT_SECRET_KEY=os.environ.get("JWT_SECRET_KEY"),
        )
        return settings


class TestingConfig(Config):
    TESTING = True
