from pathlib import Path

import pytest
from sqlalchemy import event

from backend.airroute import create_app
from backend.airroute.csv_import import (
    ReferenceConflictError,
    import_uploaded_datasets,
    parse_csv,
)
from backend.airroute.extensions import db
from backend.airroute.models import Airline, Airport, Route


@pytest.fixture
def app(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{Path(tmp_path) / 'import.db'}",
            "JWT_SECRET_KEY": "modular-import-test-secret",
        }
    )
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


def test_parse_csv_preserves_validation_contract():
    content = (
        "airport_id,name,city,country,iata_code,icao_code,latitude,"
        "longitude,altitude,timezone\n"
        "1,Test Airport,Test City,Test Country,TST,TEST,1.0,2.0,3,UTC\n"
    ).encode()

    records = parse_csv("airports", content)

    assert records[0]["airport_id"] == 1
    assert records[0]["latitude"] == 1.0


def test_import_replaces_datasets_atomically(app):
    with app.app_context():
        db.session.add_all(
            [
                Airport(airport_id=1, name="Old Airport"),
                Airline(airline_id=1, name="Old Airline"),
                Route(
                    route_id=1,
                    airline_id=1,
                    origin_airport_id=1,
                    destination_airport_id=1,
                    stops=0,
                ),
            ]
        )
        db.session.commit()

        import_uploaded_datasets(
            {
                "airports": (
                    "airport_id,name,city,country,iata_code,icao_code,latitude,"
                    "longitude,altitude,timezone\n"
                    "2,New Airport,,,,,0,0,,\n"
                ).encode(),
                "airlines": (
                    "airline_id,name,iata_code,icao_code,country\n"
                    "2,New Airline,,,\n"
                ).encode(),
                "routes": (
                    "route_id,airline_id,airline_iata,origin_airport_id,"
                    "origin_iata,destination_airport_id,destination_iata,"
                    "codeshare,stops,equipment\n"
                    "2,2,,2,,2,,,0,\n"
                ).encode(),
            }
        )

        assert db.session.get(Airport, 1) is None
        assert db.session.get(Airport, 2).name == "New Airport"
        assert db.session.get(Route, 2).airline_id == 2


def test_invalid_import_rolls_back_without_changes(app):
    with app.app_context():
        db.session.add(Airport(airport_id=1, name="Existing Airport"))
        db.session.commit()

        with pytest.raises(ValueError, match="Missing name"):
            import_uploaded_datasets(
                {
                    "airports": (
                        "airport_id,name,city,country,iata_code,icao_code,"
                        "latitude,longitude,altitude,timezone\n"
                        "2,,,,,,,,,\n"
                    ).encode()
                }
            )

        assert db.session.get(Airport, 1).name == "Existing Airport"
        assert db.session.get(Airport, 2) is None


def test_import_rejects_changes_to_planned_routes(app):
    with app.app_context():
        db.session.add_all(
            [
                Airport(airport_id=1, name="Airport One", iata_code="ONE"),
                Airline(airline_id=1, name="Airline One", iata_code="ON"),
                Route(
                    route_id=1,
                    airline_id=1,
                    airline_iata="ON",
                    origin_airport_id=1,
                    origin_iata="ONE",
                    destination_airport_id=1,
                    destination_iata="ONE",
                    stops=0,
                ),
            ]
        )
        db.session.commit()
        connection = db.engine.connect()
        connection.exec_driver_sql(
            "INSERT INTO travel_plans "
            "(plan_id, account_id, name, departure_date, return_date) "
            "VALUES (1, 1, 'Plan', '2026-01-01', '2026-01-02')"
        )
        connection.exec_driver_sql(
            "INSERT INTO travel_plan_routes (plan_id, route_id) VALUES (1, 1)"
        )
        connection.commit()
        connection.close()

        with pytest.raises(ReferenceConflictError, match="cannot be modified"):
            import_uploaded_datasets(
                {
                    "routes": (
                        "route_id,airline_id,airline_iata,origin_airport_id,"
                        "origin_iata,destination_airport_id,destination_iata,"
                        "codeshare,stops,equipment\n"
                        "1,1,ON,1,ONE,1,ONE,,1,\n"
                    ).encode()
                }
            )


def test_import_acquires_sqlite_write_lock(app):
    statements = []

    def observe_lock(connection, cursor, statement, parameters, context, many):
        if statement == "BEGIN IMMEDIATE":
            statements.append(statement)

    with app.app_context():
        event.listen(db.engine, "before_cursor_execute", observe_lock)
        try:
            import_uploaded_datasets(
                {
                    "airports": (
                        "airport_id,name,city,country,iata_code,icao_code,"
                        "latitude,longitude,altitude,timezone\n"
                        "1,Airport,,,,,0,0,,\n"
                    ).encode()
                }
            )
        finally:
            event.remove(db.engine, "before_cursor_execute", observe_lock)

    assert statements == ["BEGIN IMMEDIATE"]
