from flask_restx import Resource, fields

from ..auth import account_required
from ..aviation import (
    airline_to_dict,
    is_sqlite_integer,
    register_database_functions,
    sqlite_query_integer,
    unicode_search_condition,
)
from ..extensions import db
from ..models import Airline, Airport, Route


def register_airlines(api, app):
    namespace = getattr(api, "modular_namespace", api.namespace)(
        "airlines",
        path="/airlines",
        description="Browse and search airlines. Available to all active accounts.",
    )
    links = namespace.model("AirlineLinks", {"self": fields.String, "routes": fields.String})
    response_model = namespace.model(
        "AirlineDetails",
        {
            "airline_id": fields.Integer,
            "name": fields.String,
            "iata_code": fields.String,
            "icao_code": fields.String,
            "country": fields.String,
            "links": fields.Nested(links),
        },
    )
    list_model = namespace.model(
        "AirlineList",
        {
            "total": fields.Integer,
            "limit": fields.Integer,
            "offset": fields.Integer,
            "items": fields.List(fields.Nested(response_model)),
        },
    )
    parser = namespace.parser()
    parser.add_argument("q", type=str, location="args", help="Case-insensitive partial search by name, country, IATA or ICAO")
    parser.add_argument("airport_id", type=sqlite_query_integer, location="args", help="Filter airlines with routes departing from this airport")
    parser.add_argument("limit", type=sqlite_query_integer, location="args", default=20, help="Page size (1–100)")
    parser.add_argument("offset", type=sqlite_query_integer, location="args", default=0, help="Number of records to skip (0 or greater)")

    @namespace.route("")
    class AirlineListResource(Resource):
        @namespace.doc(
            security="BearerAuth",
            description="List and search airlines. Optionally filter by departure airport. Admin and User can access.",
        )
        @namespace.expect(parser)
        @namespace.response(200, "Airline list", list_model)
        @namespace.response(400, "Invalid query parameters")
        @namespace.response(401, "Authentication required")
        @namespace.response(403, "Account inactive or access denied")
        @namespace.response(422, "Malformed access token")
        @namespace.response(404, "Airport not found")
        @account_required()
        def get(self):
            args = parser.parse_args()
            search = (args["q"] or "").strip()
            airport_id, limit, offset = args["airport_id"], args["limit"], args["offset"]
            if not 1 <= limit <= 100 or offset < 0:
                return {"message": "Invalid limit or offset"}, 400
            query = db.select(Airline)
            count_query = db.select(db.func.count()).select_from(Airline)
            if airport_id is not None:
                if db.session.get(Airport, airport_id) is None:
                    return {"message": "Airport not found"}, 404
                ids = db.select(Route.airline_id).where(Route.origin_airport_id == airport_id)
                query = query.where(Airline.airline_id.in_(ids))
                count_query = count_query.where(Airline.airline_id.in_(ids))
            if search:
                condition = unicode_search_condition(
                    search, Airline.name, Airline.country,
                    Airline.iata_code, Airline.icao_code,
                )
                query = query.where(condition)
                count_query = count_query.where(condition)
            total = db.session.scalar(count_query)
            airlines = db.session.scalars(
                query.order_by(Airline.airline_id).limit(limit).offset(offset)
            ).all()
            return {
                "total": total, "limit": limit, "offset": offset,
                "items": [airline_to_dict(item) for item in airlines],
            }, 200

    @namespace.route("/<int:airline_id>")
    class AirlineDetailResource(Resource):
        @namespace.doc(
            security="BearerAuth",
            description="Retrieve an airline by ID. Admin and User can access.",
        )
        @namespace.response(200, "Airline details", response_model)
        @namespace.response(401, "Authentication required")
        @namespace.response(403, "Account inactive or access denied")
        @namespace.response(422, "Malformed access token")
        @namespace.response(404, "Airline not found")
        @account_required()
        def get(self, airline_id):
            if not is_sqlite_integer(airline_id):
                return {"message": "Airline not found"}, 404
            airline = db.session.get(Airline, airline_id)
            if airline is None:
                return {"message": "Airline not found"}, 404
            return airline_to_dict(airline), 200

    register_database_functions(app)
