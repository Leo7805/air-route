from flask_restx import Resource, fields

from ..auth import account_required
from ..aviation import (
    is_sqlite_integer,
    register_database_functions,
    route_to_dict,
    sqlite_query_integer,
)
from ..extensions import db
from ..models import Airline, Airport, Route


def register_routes(api, app):
    namespace = getattr(api, "modular_namespace", api.namespace)(
        "routes",
        path="/routes",
        description="Browse and filter routes. Available to all active accounts.",
    )
    links = namespace.model(
        "RouteLinks",
        {
            "self": fields.String,
            "airline": fields.String,
            "origin_airport": fields.String,
            "destination_airport": fields.String,
        },
    )
    summary = namespace.model(
        "RouteSummary",
        {
            "route_id": fields.Integer,
            "airline_id": fields.Integer,
            "airline_iata": fields.String,
            "origin_airport_id": fields.Integer,
            "origin_iata": fields.String,
            "destination_airport_id": fields.Integer,
            "destination_iata": fields.String,
            "codeshare": fields.String,
            "stops": fields.Integer,
            "equipment": fields.String,
            "links": fields.Nested(links),
        },
    )
    airport_links = namespace.model(
        "RouteAirportLinks",
        {"self": fields.String, "airlines": fields.String, "departing_routes": fields.String},
    )
    airport_detail = namespace.model(
        "RouteAirportDetails",
        {
            "airport_id": fields.Integer, "name": fields.String,
            "city": fields.String, "country": fields.String,
            "iata_code": fields.String, "icao_code": fields.String,
            "latitude": fields.Float, "longitude": fields.Float,
            "altitude": fields.Integer, "timezone": fields.String,
            "links": fields.Nested(airport_links),
        },
    )
    airline_links = namespace.model(
        "RouteAirlineLinks",
        {"self": fields.String, "routes": fields.String},
    )
    airline_detail = namespace.model(
        "RouteAirlineDetails",
        {
            "airline_id": fields.Integer, "name": fields.String,
            "iata_code": fields.String, "icao_code": fields.String,
            "country": fields.String, "links": fields.Nested(airline_links),
        },
    )
    detail = namespace.inherit(
        "RouteDetails",
        summary,
        {
            "airline": fields.Nested(airline_detail),
            "origin_airport": fields.Nested(airport_detail),
            "destination_airport": fields.Nested(airport_detail),
        },
    )
    list_model = namespace.model(
        "RouteList",
        {
            "total": fields.Integer, "limit": fields.Integer,
            "offset": fields.Integer,
            "items": fields.List(fields.Nested(summary)),
        },
    )
    parser = namespace.parser()
    parser.add_argument("airline_id", type=sqlite_query_integer, location="args", help="Filter by airline ID")
    parser.add_argument("origin_airport_id", type=sqlite_query_integer, location="args", help="Filter by departure airport ID")
    parser.add_argument("destination_airport_id", type=sqlite_query_integer, location="args", help="Filter by destination airport ID")
    parser.add_argument("limit", type=sqlite_query_integer, location="args", default=20, help="Page size (1–100)")
    parser.add_argument("offset", type=sqlite_query_integer, location="args", default=0, help="Number of records to skip (0 or greater)")

    @namespace.route("")
    class RouteListResource(Resource):
        @namespace.doc(
            security="BearerAuth",
            description="List routes with optional airline, origin airport, and destination airport filters. Filters can be combined. Available to Admin and User.",
        )
        @namespace.expect(parser)
        @namespace.response(200, "Route list", list_model)
        @namespace.response(400, "Invalid query parameters")
        @namespace.response(401, "Authentication required")
        @namespace.response(403, "Account inactive or access denied")
        @namespace.response(422, "Malformed access token")
        @namespace.response(404, "Referenced airline or airport not found")
        @account_required()
        def get(self):
            args = parser.parse_args()
            limit, offset = args["limit"], args["offset"]
            if not 1 <= limit <= 100 or offset < 0:
                return {"message": "Invalid limit or offset"}, 400
            filters = [
                (args["airline_id"], Airline, Route.airline_id, "Airline"),
                (args["origin_airport_id"], Airport, Route.origin_airport_id, "Origin airport"),
                (args["destination_airport_id"], Airport, Route.destination_airport_id, "Destination airport"),
            ]
            conditions = []
            for value, model, column, label in filters:
                if value is not None:
                    if db.session.get(model, value) is None:
                        return {"message": f"{label} not found"}, 404
                    conditions.append(column == value)
            query = db.select(Route).where(*conditions)
            count = db.select(db.func.count()).select_from(Route).where(*conditions)
            total = db.session.scalar(count)
            routes = db.session.scalars(
                query.order_by(Route.route_id).limit(limit).offset(offset)
            ).all()
            return {
                "total": total, "limit": limit, "offset": offset,
                "items": [route_to_dict(item) for item in routes],
            }, 200

    @namespace.route("/<int:route_id>")
    class RouteDetailResource(Resource):
        @namespace.doc(
            security="BearerAuth",
            description="Retrieve a route with full airline, origin airport, and destination airport details. Available to Admin and User.",
        )
        @namespace.response(200, "Route details", detail)
        @namespace.response(401, "Authentication required")
        @namespace.response(403, "Account inactive or access denied")
        @namespace.response(422, "Malformed access token")
        @namespace.response(404, "Route not found")
        @account_required()
        def get(self, route_id):
            if not is_sqlite_integer(route_id):
                return {"message": "Route not found"}, 404
            route = db.session.get(Route, route_id)
            if route is None:
                return {"message": "Route not found"}, 404
            return route_to_dict(route, include_related=True), 200

    register_database_functions(app)
