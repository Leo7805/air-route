from datetime import date, timedelta
from pathlib import Path

import pytest

from backend.airroute import create_app
from backend.airroute.exports import (
    export_plan_to_dict,
    generate_travel_plans_image,
)
from backend.airroute.extensions import db
from backend.airroute.models import (
    Account,
    Airline,
    Airport,
    Route,
    TravelPlan,
    TravelPlanRoute,
)
from backend.airroute.travel_plans import create_plan


@pytest.fixture
def app(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{Path(tmp_path) / 'exports.db'}",
            "JWT_SECRET_KEY": "modular-exports-test-secret",
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
                Airport(airport_id=1, name="Airport", iata_code="APT"),
                Airline(airline_id=1, name="Airline", iata_code="AL"),
                Route(
                    route_id=1,
                    airline_id=1,
                    airline_iata="AL",
                    origin_airport_id=1,
                    origin_iata="APT",
                    destination_airport_id=1,
                    destination_iata="APT",
                    stops=0,
                ),
            ]
        )
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


def make_plan(account_id, name, departure_date):
    return create_plan(
        account_id,
        {
            "name": name,
            "departure_date": departure_date.isoformat(),
            "return_date": (departure_date + timedelta(days=1)).isoformat(),
        },
    )


def test_json_export_serializes_related_route_details(app):
    with app.app_context():
        plan = make_plan(1, "Trip", date(2026, 1, 1))
        plan.route_links.append(TravelPlanRoute(route_id=1))
        db.session.commit()

        exported = export_plan_to_dict(plan)

        assert exported["routes"][0]["route_id"] == 1
        assert exported["routes"][0]["airline"]["airline_id"] == 1


def test_png_generation_returns_valid_png(app):
    with app.app_context():
        plan = make_plan(1, "Trip", date(2026, 1, 1))
        image = generate_travel_plans_image([plan])
        assert image.read(8) == b"\x89PNG\r\n\x1a\n"


def test_export_plan_query_can_limit_future_plans_to_five(app):
    with app.app_context():
        for index in range(6):
            make_plan(1, f"Trip {index}", date(2026, 1, index + 1))
        plans = db.session.scalars(
            db.select(TravelPlan)
            .where(TravelPlan.account_id == 1)
            .order_by(TravelPlan.departure_date, TravelPlan.plan_id)
            .limit(5)
        ).all()
        assert len(plans) == 5
        assert [plan.name for plan in plans] == [f"Trip {i}" for i in range(5)]
