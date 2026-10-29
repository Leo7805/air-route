import sys

import pytest
from conftest import ModularTestModule

from backend.airroute import create_app

_collection_module = ModularTestModule(
    create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "JWT_SECRET_KEY": "collection-test-secret",
        }
    )
)
_collection_module.init_db()
sys.modules["z5596858_api"] = _collection_module

from z5596858_test_unit import *  # noqa: E402,F403


@pytest.fixture(autouse=True)
def coursework_fixture_paths(monkeypatch):
    import pathlib

    from conftest import FIXTURE_DIR, fixture_path_class

    monkeypatch.chdir(FIXTURE_DIR)
    monkeypatch.setattr(pathlib, "Path", fixture_path_class())


@pytest.fixture
def isolated_import_api(tmp_path, monkeypatch):
    import pathlib

    from conftest import FIXTURE_DIR, fixture_path_class, load_modular_api

    api_module, _ = load_modular_api(tmp_path)
    monkeypatch.chdir(FIXTURE_DIR)
    monkeypatch.setattr(pathlib, "Path", fixture_path_class())
    api_module.init_db()
    yield api_module
    with api_module.app.app_context():
        api_module.db.session.remove()
        api_module.db.engine.dispose()


@pytest.fixture
def import_client(isolated_import_api):
    client = isolated_import_api.app.test_client()
    response = client.post(
        "/auth/login", json={"username": "admin", "password": "admin"}
    )
    assert response.status_code == 200, response.json
    return client, {"Authorization": f"Bearer {response.json['access_token']}"}
