import importlib.util
import pathlib
import sys
from pathlib import Path
from uuid import uuid4

import flask
import pytest


PROJECT_ROOT = Path(__file__).parents[2]
FIXTURE_DIR = Path(__file__).parent / "fixtures"
API_SOURCE = PROJECT_ROOT / "z5596858_api.py"
DATASET_NAMES = {"airports.csv", "airlines.csv", "routes.csv"}


def load_isolated_api(tmp_path, monkeypatch):
    module_name = f"airroute_test_api_{uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, API_SOURCE)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)

    original_flask = flask.Flask
    with monkeypatch.context() as setup:
        setup.setattr(
            flask,
            "Flask",
            lambda name: original_flask(name, instance_path=str(tmp_path)),
        )
        spec.loader.exec_module(module)

    return module


def fixture_path_class():
    base_path_class = type(Path())

    class FixturePath(base_path_class):
        def __new__(cls, *args):
            if len(args) == 1 and str(args[0]) in DATASET_NAMES:
                args = (FIXTURE_DIR / str(args[0]),)
            return super().__new__(cls, *args)

        def with_name(self, name):
            if name in DATASET_NAMES:
                return self.__class__(FIXTURE_DIR / name)
            return super().with_name(name)

    return FixturePath


@pytest.fixture(autouse=True)
def isolated_coursework_environment(tmp_path, monkeypatch, request):
    """Run imported coursework tests against a temporary database and fixtures."""
    import z5596858_test_unit as test_module

    api_module = load_isolated_api(tmp_path, monkeypatch)

    monkeypatch.chdir(FIXTURE_DIR)
    monkeypatch.setitem(sys.modules, "z5596858_api", api_module)

    for name in ("app", "db", "Account", "CSV_SCHEMAS", "init_db"):
        monkeypatch.setattr(test_module, name, getattr(api_module, name))
    monkeypatch.setattr(pathlib, "Path", fixture_path_class())

    yield

    with api_module.app.app_context():
        api_module.db.session.remove()
        api_module.db.engine.dispose()
