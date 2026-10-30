from pathlib import Path

import pytest

from backend.airroute import create_app, init_db
from backend.airroute.config import Config
from backend.airroute.extensions import db
from backend.airroute.models import Account


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for key in ("AIRROUTE_ENV", "DATABASE_URL", "JWT_SECRET_KEY"):
        monkeypatch.delenv(key, raising=False)


def test_factory_requires_a_production_secret_by_default():
    with pytest.raises(ValueError, match="Production requires JWT_SECRET_KEY"):
        create_app()


@pytest.mark.parametrize("secret", ["", "short", "local-airroute-development-key"])
def test_production_rejects_missing_or_weak_secret(secret):
    with pytest.raises(ValueError, match="at least 32 bytes"):
        create_app({"JWT_SECRET_KEY": secret})


def test_environment_overrides_are_read_for_each_factory_call(monkeypatch, tmp_path):
    monkeypatch.setenv("AIRROUTE_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'override.db'}")
    monkeypatch.setenv("JWT_SECRET_KEY", "configured-development-secret")
    app = create_app()
    assert app.config["JWT_SECRET_KEY"] == "configured-development-secret"
    with app.app_context():
        assert Path(db.engine.url.database) == tmp_path / "override.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'second.db'}")
    second = create_app()
    with second.app_context():
        assert Path(db.engine.url.database) == tmp_path / "second.db"


def test_default_sqlite_filename_resolves_under_explicit_instance_path(tmp_path):
    app = create_app({"TESTING": True}, instance_path=str(tmp_path))
    assert Config.SQLALCHEMY_DATABASE_URI == "sqlite:///airroute.db"
    with app.app_context():
        assert Path(db.engine.url.database) == tmp_path / "airroute.db"


def test_development_seeds_accounts_once_and_uses_an_ephemeral_secret(tmp_path):
    app = create_app({"APP_ENV": "development"}, instance_path=str(tmp_path))
    assert len(app.config["JWT_SECRET_KEY"]) >= 32
    second = create_app({"APP_ENV": "development"}, instance_path=str(tmp_path))
    assert app.config["JWT_SECRET_KEY"] != second.config["JWT_SECRET_KEY"]
    init_db(app)
    with app.app_context():
        admin = db.session.scalar(db.select(Account).filter_by(username="admin"))
        assert admin is not None
        admin.is_active = False
        db.session.commit()
    init_db(app)
    with app.app_context():
        accounts = db.session.scalars(db.select(Account)).all()
        assert len(accounts) == 2
        assert {account.role for account in accounts} == {"Admin", "User"}
        assert not next(a for a in accounts if a.username == "admin").is_active


def test_production_initialisation_creates_no_demo_accounts(tmp_path):
    app = create_app({"JWT_SECRET_KEY": "x" * 32}, instance_path=str(tmp_path))
    init_db(app)
    with app.app_context():
        assert db.session.scalars(db.select(Account)).all() == []
    assert not app.debug


def test_production_does_not_modify_existing_accounts(tmp_path):
    uri = f"sqlite:///{tmp_path / 'shared.db'}"
    local = create_app({"APP_ENV": "development", "SQLALCHEMY_DATABASE_URI": uri})
    init_db(local)
    with local.app_context():
        before = [
            (a.id, a.username, a.password_hash)
            for a in db.session.scalars(db.select(Account))
        ]
    production = create_app(
        {"JWT_SECRET_KEY": "x" * 32, "SQLALCHEMY_DATABASE_URI": uri}
    )
    init_db(production)
    with production.app_context():
        after = [
            (a.id, a.username, a.password_hash)
            for a in db.session.scalars(db.select(Account))
        ]
    assert after == before


def test_unknown_environment_is_rejected(monkeypatch):
    monkeypatch.setenv("AIRROUTE_ENV", "prodution")
    with pytest.raises(ValueError, match="AIRROUTE_ENV"):
        create_app({"TESTING": True})
