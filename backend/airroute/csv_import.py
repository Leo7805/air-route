import csv
import io
import math

from sqlalchemy.exc import SQLAlchemyError

from .extensions import db
from .models import Airline, Airport, Route, TravelPlanRoute

CSV_SCHEMAS = {
    "airports": {
        "airport_id": int,
        "name": str,
        "city": str,
        "country": str,
        "iata_code": str,
        "icao_code": str,
        "latitude": float,
        "longitude": float,
        "altitude": int,
        "timezone": str,
    },
    "airlines": {
        "airline_id": int,
        "name": str,
        "iata_code": str,
        "icao_code": str,
        "country": str,
    },
    "routes": {
        "route_id": int,
        "airline_id": int,
        "airline_iata": str,
        "origin_airport_id": int,
        "origin_iata": str,
        "destination_airport_id": int,
        "destination_iata": str,
        "codeshare": str,
        "stops": int,
        "equipment": str,
    },
}

PRIMARY_KEYS = {
    "airports": "airport_id",
    "airlines": "airline_id",
    "routes": "route_id",
}

REQUIRED_COLUMNS = {
    "airports": {"airport_id", "name"},
    "airlines": {"airline_id", "name"},
    "routes": {
        "route_id",
        "airline_id",
        "origin_airport_id",
        "destination_airport_id",
        "stops",
    },
}

DATASET_MODELS = {
    "airports": Airport,
    "airlines": Airline,
    "routes": Route,
}


class ReferenceConflictError(ValueError):
    """Indicate a missing or protected dataset reference."""


def parse_csv(dataset, content):
    schema = CSV_SCHEMAS[dataset]
    primary_key = PRIMARY_KEYS[dataset]

    try:
        text = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text), strict=True)
        columns = reader.fieldnames

        if (
            columns is None
            or len(columns) != len(schema)
            or set(columns) != set(schema)
        ):
            raise ValueError(
                f"Invalid columns in {dataset}. Expected: {list(schema)}"
            )

        records = []
        seen_ids = set()

        for row_number, row in enumerate(reader, start=2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"{dataset}, row {row_number}: Invalid column count")

            record = {}
            for column, data_type in schema.items():
                value = row[column].strip()
                if not value:
                    if column in REQUIRED_COLUMNS[dataset]:
                        raise ValueError(
                            f"{dataset}, row {row_number}: Missing {column}"
                        )
                    record[column] = None
                    continue

                try:
                    converted = data_type(value)
                except (ValueError, OverflowError):
                    raise ValueError(
                        f"{dataset}, row {row_number}: Invalid {column}: {value}"
                    ) from None

                if data_type is int and not -(2**63) <= converted <= 2**63 - 1:
                    raise ValueError(
                        f"{dataset}, row {row_number}: "
                        f"{column} is outside the signed 64-bit integer range"
                    )
                if data_type is float and not math.isfinite(converted):
                    raise ValueError(f"{dataset}, row {row_number}: Invalid {column}")
                record[column] = converted

            if dataset == "airports":
                latitude = record["latitude"]
                longitude = record["longitude"]
                if latitude is not None and not -90 <= latitude <= 90:
                    raise ValueError(f"airports, row {row_number}: Invalid latitude")
                if longitude is not None and not -180 <= longitude <= 180:
                    raise ValueError(f"airports, row {row_number}: Invalid longitude")
            elif dataset == "routes":
                if record["stops"] < 0:
                    raise ValueError(f"routes, row {row_number}: Invalid stops")
                for field in (
                    "airline_id",
                    "origin_airport_id",
                    "destination_airport_id",
                ):
                    if record[field] <= 0:
                        raise ValueError(
                            f"routes, row {row_number}: Invalid {field}"
                        )

            record_id = record[primary_key]
            if record_id <= 0:
                raise ValueError(f"{dataset}, row {row_number}: Invalid ID")
            if record_id in seen_ids:
                raise ValueError(
                    f"{dataset}, row {row_number}: Duplicate ID {record_id}"
                )
            seen_ids.add(record_id)
            records.append(record)

        return records
    except (UnicodeDecodeError, csv.Error) as error:
        raise ValueError(f"Cannot parse {dataset} CSV: {error}") from error


def validate_references(airports, airlines, routes):
    airport_by_id = {airport["airport_id"]: airport for airport in airports}
    airline_by_id = {airline["airline_id"]: airline for airline in airlines}

    for route in routes:
        route_id = route["route_id"]
        references = [
            ("airline", route["airline_id"], route["airline_iata"], airline_by_id),
            (
                "origin airport",
                route["origin_airport_id"],
                route["origin_iata"],
                airport_by_id,
            ),
            (
                "destination airport",
                route["destination_airport_id"],
                route["destination_iata"],
                airport_by_id,
            ),
        ]
        for label, reference_id, iata, lookup in references:
            if reference_id not in lookup:
                raise ReferenceConflictError(
                    f"Route {route_id}: {label} ID {reference_id} does not exist"
                )
            expected_iata = lookup[reference_id]["iata_code"]
            if iata is not None and iata != expected_iata:
                raise ValueError(
                    f"Route {route_id}: {label} IATA mismatch "
                    f"(expected {expected_iata}, got {iata})"
                )


def load_dataset(dataset):
    model = DATASET_MODELS[dataset]
    records = db.session.scalars(db.select(model)).all()
    return [
        {
            column.name: getattr(record, column.name)
            for column in model.__table__.columns
        }
        for record in records
    ]


def replace_datasets(replacements):
    """Validate and atomically replace the selected datasets."""
    db.session.rollback()
    db.session.connection().exec_driver_sql("BEGIN IMMEDIATE")

    combined = {
        dataset: replacements[dataset]
        if dataset in replacements
        else load_dataset(dataset)
        for dataset in DATASET_MODELS
    }
    validate_references(
        combined["airports"], combined["airlines"], combined["routes"]
    )

    preserved_route_ids = set()
    if "routes" in replacements:
        referenced_route_ids = set(
            db.session.scalars(db.select(TravelPlanRoute.route_id).distinct()).all()
        )
        uploaded_routes = {
            route["route_id"]: route for route in combined["routes"]
        }
        route_columns = tuple(column.name for column in Route.__table__.columns)
        for route_id in referenced_route_ids:
            existing_route = db.session.get(Route, route_id)
            uploaded_route = uploaded_routes.get(route_id)
            if uploaded_route is None:
                raise ReferenceConflictError(
                    f"Route {route_id} referenced by a Travel Plan "
                    "does not exist in the imported dataset"
                )
            existing_values = {
                column: getattr(existing_route, column) for column in route_columns
            }
            if any(
                existing_values[column] != uploaded_route[column]
                for column in route_columns
            ):
                raise ReferenceConflictError(
                    f"Route {route_id} referenced by a Travel Plan "
                    "cannot be modified"
                )
            preserved_route_ids.add(route_id)

    if "routes" in replacements:
        db.session.execute(
            db.delete(Route).where(~Route.route_id.in_(preserved_route_ids))
        )
    for dataset in ("airports", "airlines"):
        if dataset in replacements:
            db.session.execute(db.delete(DATASET_MODELS[dataset]))

    for dataset in ("airports", "airlines", "routes"):
        if dataset in replacements and replacements[dataset]:
            records = replacements[dataset]
            if dataset == "routes" and preserved_route_ids:
                records = [
                    route
                    for route in records
                    if route["route_id"] not in preserved_route_ids
                ]
            if records:
                db.session.execute(db.insert(DATASET_MODELS[dataset]), records)
    db.session.commit()


def import_uploaded_datasets(uploaded):
    try:
        replacements = {
            dataset: parse_csv(dataset, content)
            for dataset, content in uploaded.items()
        }
        replace_datasets(replacements)
    except (ReferenceConflictError, ValueError):
        db.session.rollback()
        raise
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return replacements
