import re
from datetime import date

from .extensions import db
from .models import Route, TravelPlan, TravelPlanRoute

MAX_SQLITE_INTEGER = 9223372036854775807


def travel_plan_to_dict(plan):
    return {
        "plan_id": plan.plan_id,
        "name": plan.name,
        "departure_date": plan.departure_date.isoformat(),
        "return_date": plan.return_date.isoformat(),
        "routes": [link.route_id for link in plan.route_links],
    }


def parse_plan_date(value, field_name):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"{field_name} must use YYYY-MM-DD format")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{field_name} is not a valid date") from None


def validate_plan_data(data):
    if not isinstance(data, dict):
        raise ValueError("A JSON object is required")
    name = data.get("name")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 255:
        raise ValueError("Invalid travel plan name")
    departure_date = parse_plan_date(data.get("departure_date"), "departure_date")
    return_date = parse_plan_date(data.get("return_date"), "return_date")
    if return_date < departure_date:
        raise ValueError("Return date cannot be earlier than departure date")
    return name.strip(), departure_date, return_date


def get_owned_plan(plan_id, account_id):
    if plan_id > MAX_SQLITE_INTEGER:
        return None
    return db.session.scalar(
        db.select(TravelPlan).where(
            TravelPlan.plan_id == plan_id,
            TravelPlan.account_id == account_id,
        )
    )


def create_plan(account_id, data):
    name, departure_date, return_date = validate_plan_data(data)
    plan = TravelPlan(
        account_id=account_id,
        name=name,
        departure_date=departure_date,
        return_date=return_date,
    )
    db.session.add(plan)
    db.session.commit()
    return plan


def list_plans(account_id):
    return db.session.scalars(
        db.select(TravelPlan)
        .where(TravelPlan.account_id == account_id)
        .order_by(TravelPlan.departure_date, TravelPlan.plan_id)
    ).all()


def update_plan(plan, data):
    plan.name, plan.departure_date, plan.return_date = validate_plan_data(data)
    db.session.commit()
    return plan


def delete_plan(plan):
    db.session.delete(plan)
    db.session.commit()


def add_route(plan_id, route_id):
    if not 1 <= route_id <= MAX_SQLITE_INTEGER:
        raise ValueError("Invalid route_id")
    if db.session.get(Route, route_id) is None:
        raise LookupError("Route not found")
    if db.session.get(TravelPlanRoute, (plan_id, route_id)) is not None:
        raise FileExistsError("Route already in travel plan")
    db.session.add(TravelPlanRoute(plan_id=plan_id, route_id=route_id))
    db.session.commit()


def remove_route(plan_id, route_id):
    if not 1 <= plan_id <= MAX_SQLITE_INTEGER or not 1 <= route_id <= MAX_SQLITE_INTEGER:
        raise LookupError("Plan or route not found")
    link = db.session.get(TravelPlanRoute, (plan_id, route_id))
    if link is None:
        raise LookupError("Route not in travel plan")
    db.session.delete(link)
    db.session.commit()
