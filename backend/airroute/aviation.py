from sqlalchemy import event, or_

from .extensions import db


def is_sqlite_integer(value):
    return -(2**63) <= value <= 2**63 - 1


def sqlite_query_integer(value):
    value = int(value)
    if not is_sqlite_integer(value):
        raise ValueError("Must fit a signed 64-bit integer")
    return value


sqlite_query_integer.__schema__ = {"type": "integer", "format": "int64"}


def register_unicode_casefold(connection, connection_record):
    connection.create_function(
        "unicode_casefold",
        1,
        lambda value: value.casefold() if value is not None else None,
        deterministic=True,
    )


def register_database_functions(app):
    with app.app_context():
        event.listen(db.engine, "connect", register_unicode_casefold)


def unicode_search_condition(search, *columns):
    pattern = f"%{search.casefold()}%"
    return or_(
        *(db.func.unicode_casefold(column).like(pattern) for column in columns)
    )


def model_to_dict(record):
    return {
        column.name: getattr(record, column.name)
        for column in record.__table__.columns
    }


def airport_to_dict(airport):
    result = model_to_dict(airport)
    airport_id = airport.airport_id
    result["links"] = {
        "self": f"/airports/{airport_id}",
        "airlines": f"/airlines?airport_id={airport_id}",
        "departing_routes": f"/routes?origin_airport_id={airport_id}",
    }
    return result


def airline_to_dict(airline):
    result = model_to_dict(airline)
    airline_id = airline.airline_id
    result["links"] = {
        "self": f"/airlines/{airline_id}",
        "routes": f"/routes?airline_id={airline_id}",
    }
    return result


def route_to_dict(route, include_related=False):
    from .models import Airline, Airport

    result = model_to_dict(route)
    result["links"] = {
        "self": f"/routes/{route.route_id}",
        "airline": f"/airlines/{route.airline_id}",
        "origin_airport": f"/airports/{route.origin_airport_id}",
        "destination_airport": f"/airports/{route.destination_airport_id}",
    }
    if include_related:
        airline = db.session.get(Airline, route.airline_id)
        origin = db.session.get(Airport, route.origin_airport_id)
        destination = db.session.get(Airport, route.destination_airport_id)
        result["airline"] = airline_to_dict(airline) if airline else None
        result["origin_airport"] = airport_to_dict(origin) if origin else None
        result["destination_airport"] = (
            airport_to_dict(destination) if destination else None
        )
    return result
