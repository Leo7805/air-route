from flask_restx import Resource, fields

from ..auth import account_required
from ..aviation import (
    airport_to_dict,
    is_sqlite_integer,
    register_database_functions,
    sqlite_query_integer,
    unicode_search_condition,
)
from ..extensions import db
from ..models import Airport


def register_airports(api, app):
    namespace = getattr(api, "modular_namespace", api.namespace)(
        "airports",
        path="/airports",
        description="Browse and search airports. Available to all active accounts.",
    )
    airport_links = namespace.model(
        "AirportLinks",
        {
            "self": fields.String,
            "airlines": fields.String,
            "departing_routes": fields.String,
        },
    )
    airport_response = namespace.model(
        "AirportDetails",
        {
            "airport_id": fields.Integer,
            "name": fields.String,
            "city": fields.String,
            "country": fields.String,
            "iata_code": fields.String,
            "icao_code": fields.String,
            "latitude": fields.Float,
            "longitude": fields.Float,
            "altitude": fields.Integer,
            "timezone": fields.String,
            "links": fields.Nested(airport_links),
        },
    )
    airport_list = namespace.model(
        "AirportList",
        {
            "total": fields.Integer,
            "limit": fields.Integer,
            "offset": fields.Integer,
            "items": fields.List(fields.Nested(airport_response)),
        },
    )
    parser = namespace.parser()
    parser.add_argument("q", type=str, location="args", help="Case-insensitive partial search by name, city, country or IATA")
    parser.add_argument("limit", type=sqlite_query_integer, location="args", default=20, help="Page size (1–100)")
    parser.add_argument("offset", type=sqlite_query_integer, location="args", default=0, help="Number of records to skip (0 or greater)")

    @namespace.route("")
    class AirportListResource(Resource):
        @namespace.doc(
            security="BearerAuth",
            description="List and search airports. Admin and User can access.",
        )
        @namespace.expect(parser)
        @namespace.response(200, "Airport list", airport_list)
        @namespace.response(400, "Invalid query parameters")
        @namespace.response(401, "Authentication required")
        @namespace.response(403, "Account inactive or access denied")
        @namespace.response(422, "Malformed access token")
        @account_required()
        def get(self):
            args = parser.parse_args()
            search = (args["q"] or "").strip()
            limit, offset = args["limit"], args["offset"]
            if not 1 <= limit <= 100 or offset < 0:
                return {"message": "Invalid limit or offset"}, 400
            query = db.select(Airport)
            count_query = db.select(db.func.count()).select_from(Airport)
            if search:
                condition = unicode_search_condition(
                    search, Airport.name, Airport.city,
                    Airport.country, Airport.iata_code,
                )
                query = query.where(condition)
                count_query = count_query.where(condition)
            total = db.session.scalar(count_query)
            airports = db.session.scalars(
                query.order_by(Airport.airport_id).limit(limit).offset(offset)
            ).all()
            return {
                "total": total,
                "limit": limit,
                "offset": offset,
                "items": [airport_to_dict(item) for item in airports],
            }, 200

    @namespace.route("/<int:airport_id>")
    class AirportDetailResource(Resource):
        @namespace.doc(
            security="BearerAuth",
            description="Retrieve an airport by ID. Admin and User can access.",
        )
        @namespace.response(200, "Airport details", airport_response)
        @namespace.response(401, "Authentication required")
        @namespace.response(403, "Account inactive or access denied")
        @namespace.response(422, "Malformed access token")
        @namespace.response(404, "Airport not found")
        @account_required()
        def get(self, airport_id):
            if not is_sqlite_integer(airport_id):
                return {"message": "Airport not found"}, 404
            airport = db.session.get(Airport, airport_id)
            if airport is None:
                return {"message": "Airport not found"}, 404
            return airport_to_dict(airport), 200

    register_database_functions(app)
