from datetime import date
from pathlib import Path

import pytest

from backend.airroute import create_app
from backend.airroute.extensions import db
from backend.airroute.models import Account, Airline, Airport, Route, TravelPlanRoute
from backend.airroute.travel_plans import (
    add_route,
    create_plan,
    get_owned_plan,
    remove_route,
    validate_plan_data,
)


@pytest.fixture
def app(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{Path(tmp_path) / 'plans.db'}",
            "JWT_SECRET_KEY": "modular-plans-test-secret",
        }
    )
    with app.app_context():
        db.create_all()
        db.session.add_all(
            [
                Account(
                    id=1,
                    username="one",
                    password_hash="hash",
                    role="User",
                    is_active=True,
                ),
                Account(
                    id=2,
                    username="two",
                    password_hash="hash",
                    role="User",
                    is_active=True,
                ),
                Airport(airport_id=1, name="Airport"),
                Airline(airline_id=1, name="Airline"),
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
        yield app
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


def test_plan_validation_and_ownership(app):
    with app.app_context():
        with pytest.raises(ValueError, match="Return date"):
            validate_plan_data(
                {
                    "name": "Trip",
                    "departure_date": "2026-02-01",
                    "return_date": "2026-01-01",
                }
            )

        plan = create_plan(
            1,
            {
                "name": "  Trip  ",
                "departure_date": "2026-01-01",
                "return_date": "2026-01-02",
            },
        )
        assert plan.name == "Trip"
        assert get_owned_plan(plan.plan_id, 1) is plan
        assert get_owned_plan(plan.plan_id, 2) is None
        assert plan.departure_date == date(2026, 1, 1)


def test_route_association_rejects_duplicates_and_can_be_removed(app):
    with app.app_context():
        plan = create_plan(
            1,
            {
                "name": "Trip",
                "departure_date": "2026-01-01",
                "return_date": "2026-01-02",
            },
        )
        add_route(plan.plan_id, 1)
        assert db.session.get(TravelPlanRoute, (plan.plan_id, 1)) is not None

        with pytest.raises(FileExistsError, match="already"):
            add_route(plan.plan_id, 1)

        remove_route(plan.plan_id, 1)
        assert db.session.get(TravelPlanRoute, (plan.plan_id, 1)) is None
