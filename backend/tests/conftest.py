import socket
import threading
from pathlib import Path
from types import ModuleType

import pytest
import requests
from werkzeug.serving import make_server

from backend.airroute import create_app, init_db
from backend.airroute.api import travel_plans as travel_plans_api
from backend.airroute.csv_import import (
    CSV_SCHEMAS,
    DATASET_MODELS,
    PRIMARY_KEYS,
    ReferenceConflictError,
    load_dataset,
    parse_csv,
    validate_references,
)
from backend.airroute.exports import generate_travel_plans_image
from backend.airroute.extensions import db
from backend.airroute.models import (
    Account,
    Airline,
    Airport,
    Route,
    TravelPlan,
    TravelPlanRoute,
)

PROJECT_ROOT = Path(__file__).parents[2]
FIXTURE_DIR = Path(__file__).parent / "fixtures"
DATASET_NAMES = {"airports.csv", "airlines.csv", "routes.csv"}


class ModularTestModule(ModuleType):
    def __init__(self, app):
        super().__init__("z5596858_api")
        self.app = app
        self.db = db
        self.Account = Account
        self.Airline = Airline
        self.Airport = Airport
        self.Route = Route
        self.TravelPlan = TravelPlan
        self.TravelPlanRoute = TravelPlanRoute
        self.CSV_SCHEMAS = CSV_SCHEMAS
        self.DATASET_MODELS = DATASET_MODELS
        self.PRIMARY_KEYS = PRIMARY_KEYS
        self.ReferenceConflictError = ReferenceConflictError
        self.load_dataset = load_dataset
        self.parse_csv = parse_csv
        self.validate_references = validate_references
        self.generate_travel_plans_image = generate_travel_plans_image

    def init_db(self):
        init_db(self.app)

    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)
        if name == "validate_references":
            import backend.airroute.csv_import as csv_import

            csv_import.validate_references = value
        elif name == "generate_travel_plans_image":
            travel_plans_api.generate_travel_plans_image = value


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


def load_modular_api(tmp_path):
    database_uri = f"sqlite:///{tmp_path / 'assignment2.db'}"
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": database_uri,
            "JWT_SECRET_KEY": "isolated-test-secret-key-32-bytes-long",
        }
    )
    return ModularTestModule(app), app


@pytest.fixture(scope="session")
def isolated_http_server(tmp_path_factory):
    """Run the original HTTP tests against a temporary database and port."""
    monkeypatch = pytest.MonkeyPatch()
    port = 5055
    probe = socket.socket()
    try:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(("127.0.0.1", port))
    except OSError as error:
        pytest.fail(f"Dedicated HTTP test port {port} is occupied: {error}")
    finally:
        probe.close()

    import z5596858_tests as test_module

    tmp_path = tmp_path_factory.mktemp("http-database")
    api_module, app = load_modular_api(tmp_path)
    with app.app_context():
        database_path = Path(api_module.db.engine.url.database)
    expected_database_path = tmp_path / "assignment2.db"
    if database_path != expected_database_path:
        pytest.fail(
            f"HTTP test database is not isolated: {database_path} "
            f"(expected {expected_database_path})"
        )

    api_module.init_db()
    monkeypatch.chdir(FIXTURE_DIR)
    monkeypatch.setattr(test_module, "BASE_URL", f"http://127.0.0.1:{port}")
    monkeypatch.setattr(test_module, "PROJECT_DIR", FIXTURE_DIR)
    monkeypatch.setattr(test_module, "DB_PATH", database_path)

    server = make_server("127.0.0.1", port, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        response = requests.get(f"http://127.0.0.1:{port}/", timeout=5)
        if response.status_code >= 500:
            pytest.fail(f"Isolated HTTP test server is unhealthy: {response.status_code}")
        yield
    finally:
        server.shutdown()
        thread.join(timeout=5)
        with app.app_context():
            api_module.db.session.remove()
            api_module.db.engine.dispose()
        monkeypatch.undo()
