import os
from datetime import timedelta


class Config:
    SQLALCHEMY_DATABASE_URI = "sqlite:///assignment2.db"
    JWT_SECRET_KEY = os.environ.get(
        "JWT_SECRET_KEY",
        "local-assignment2-development-key-for-z5596858",
    )
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    TESTING = False


class TestingConfig(Config):
    TESTING = True
