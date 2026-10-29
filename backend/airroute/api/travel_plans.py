from datetime import date

from flask import g, request
from flask_restx import Resource, fields

from ..auth import account_required
from ..exports import (
    generate_travel_plans_image,
    json_export_response,
    png_export_response,
)
from ..extensions import db
from ..models import TravelPlan
from ..travel_plans import (
    MAX_SQLITE_INTEGER,
    add_route,
    create_plan,
    delete_plan,
    get_owned_plan,
    list_plans,
    remove_route,
    travel_plan_to_dict,
    update_plan,
)


def register_travel_plans(api):
    namespace = getattr(api, "modular_namespace", api.namespace)(
        "travel-plans",
        path="/travel-plans",
        description="Manage private travel plans for the authenticated account.",
    )
    request_model = namespace.model(
        "CreateTravelPlanRequest",
        {
            "name": fields.String(required=True),
            "departure_date": fields.String(
                required=True, description="Date in YYYY-MM-DD format"
            ),
            "return_date": fields.String(
                required=True, description="Date in YYYY-MM-DD format"
            ),
        },
    )
    response_model = namespace.model(
        "TravelPlanDetails",
        {
            "plan_id": fields.Integer,
            "name": fields.String,
            "departure_date": fields.String,
            "return_date": fields.String,
            "routes": fields.List(fields.Integer),
        },
    )
    list_model = namespace.model(
        "TravelPlanList",
        {
            "total": fields.Integer,
            "items": fields.List(fields.Nested(response_model)),
        },
    )
    add_route_model = namespace.model(
        "AddPlanRouteRequest",
        {"route_id": fields.Integer(required=True, description="ID of an existing route")},
    )
    export_plan_model = namespace.model(
        "ExportTravelPlan",
        {
            "plan_id": fields.Integer,
            "name": fields.String,
            "departure_date": fields.String,
            "return_date": fields.String,
            "routes": fields.List(fields.Raw),
        },
    )
    export_response_model = namespace.model(
        "TravelPlansExport",
        {"plans": fields.List(fields.Nested(export_plan_model))},
    )
    export_query_parser = namespace.parser()
    export_query_parser.add_argument(
        "format",
        type=str,
        location="args",
        default="json",
        help="Export format: json for a JSON download or image for a PNG response",
    )

    @namespace.route("")
    class TravelPlanListResource(Resource):
        @namespace.doc(
            security="BearerAuth",
            description="Create a private travel plan for the current account.",
        )
        @namespace.expect(request_model)
        @namespace.response(201, "Travel plan created", response_model)
        @namespace.response(400, "Invalid plan details")
        @namespace.response(401, "Authentication required")
        @namespace.response(403, "Account inactive or access denied")
        @namespace.response(422, "Invalid authentication token")
        @account_required()
        def post(self):
            try:
                plan = create_plan(g.current_account.id, request.get_json(silent=True))
            except ValueError as error:
                return {"message": str(error)}, 400
            return travel_plan_to_dict(plan), 201, {
                "Location": f"/travel-plans/{plan.plan_id}"
            }

        @namespace.doc(
            security="BearerAuth",
            description="List private travel plans belonging to the current account.",
        )
        @namespace.response(200, "Travel plans retrieved", list_model)
        @namespace.response(401, "Authentication required")
        @namespace.response(403, "Account inactive or access denied")
        @namespace.response(422, "Invalid authentication token")
        @account_required()
        def get(self):
            plans = list_plans(g.current_account.id)
            return {
                "total": len(plans),
                "items": [travel_plan_to_dict(plan) for plan in plans],
            }, 200

    @namespace.route("/<int:plan_id>")
    class TravelPlanDetailResource(Resource):
        @namespace.doc(
            security="BearerAuth",
            description="Retrieve a travel plan owned by the current account.",
        )
        @namespace.response(200, "Travel plan details", response_model)
        @namespace.response(401, "Authentication required")
        @namespace.response(403, "Account inactive or access denied")
        @namespace.response(404, "Travel plan not found")
        @namespace.response(422, "Invalid authentication token")
        @account_required()
        def get(self, plan_id):
            plan = get_owned_plan(plan_id, g.current_account.id)
            if plan is None:
                return {"message": "Travel plan not found"}, 404
            return travel_plan_to_dict(plan), 200

        @namespace.expect(request_model)
        @namespace.response(200, "Travel plan updated", response_model)
        @namespace.response(400, "Invalid plan details")
        @namespace.response(401, "Authentication required")
        @namespace.response(403, "Account inactive or access denied")
        @namespace.response(404, "Travel plan not found")
        @namespace.response(422, "Invalid authentication token")
        @account_required()
        def put(self, plan_id):
            plan = get_owned_plan(plan_id, g.current_account.id)
            if plan is None:
                return {"message": "Travel plan not found"}, 404
            try:
                update_plan(plan, request.get_json(silent=True))
            except ValueError as error:
                return {"message": str(error)}, 400
            return travel_plan_to_dict(plan), 200

        @namespace.response(204, "Travel plan deleted")
        @namespace.response(401, "Authentication required")
        @namespace.response(403, "Account inactive or access denied")
        @namespace.response(404, "Travel plan not found")
        @namespace.response(422, "Invalid authentication token")
        @account_required()
        def delete(self, plan_id):
            plan = get_owned_plan(plan_id, g.current_account.id)
            if plan is None:
                return {"message": "Travel plan not found"}, 404
            delete_plan(plan)
            return "", 204

    @namespace.route("/<int:plan_id>/routes")
    class TravelPlanRoutesResource(Resource):
        @namespace.expect(add_route_model)
        @namespace.response(201, "Route added", response_model)
        @namespace.response(400, "Invalid route ID")
        @namespace.response(401, "Authentication required")
        @namespace.response(403, "Account inactive")
        @namespace.response(404, "Plan or route not found")
        @namespace.response(409, "Route already in plan")
        @namespace.response(422, "Invalid authentication token")
        @account_required()
        def post(self, plan_id):
            if not 1 <= plan_id <= MAX_SQLITE_INTEGER:
                return {"message": "Travel plan not found"}, 404
            plan = get_owned_plan(plan_id, g.current_account.id)
            if plan is None:
                return {"message": "Travel plan not found"}, 404
            data = request.get_json(silent=True)
            if not isinstance(data, dict):
                return {"message": "A JSON object is required"}, 400
            route_id = data.get("route_id")
            if type(route_id) is not int or not 1 <= route_id <= MAX_SQLITE_INTEGER:
                return {"message": "Invalid route_id"}, 400
            try:
                add_route(plan_id, route_id)
            except LookupError as error:
                return {"message": str(error)}, 404
            except FileExistsError as error:
                return {"message": str(error)}, 409
            return travel_plan_to_dict(plan), 201, {
                "Location": f"/travel-plans/{plan_id}/routes/{route_id}"
            }

    @namespace.route("/<int:plan_id>/routes/<int:route_id>")
    class TravelPlanRouteResource(Resource):
        @namespace.response(204, "Route removed")
        @namespace.response(401, "Authentication required")
        @namespace.response(403, "Account inactive")
        @namespace.response(404, "Plan or route association not found")
        @namespace.response(422, "Invalid authentication token")
        @account_required()
        def delete(self, plan_id, route_id):
            if get_owned_plan(plan_id, g.current_account.id) is None:
                return {"message": "Travel plan not found"}, 404
            try:
                remove_route(plan_id, route_id)
            except LookupError as error:
                return {"message": str(error)}, 404
            return "", 204

    @namespace.route("/export")
    class TravelPlanExportResource(Resource):
        @namespace.doc(
            security="BearerAuth",
            description=(
                "Export only the current account's travel plans. "
                "Use format=json for a JSON download or format=image for a "
                "viewable PNG image of up to five upcoming plans."
            ),
        )
        @namespace.expect(export_query_parser)
        @namespace.response(200, "JSON file download", export_response_model)
        @namespace.response(400, "Unsupported export format")
        @namespace.response(401, "Authentication required")
        @namespace.response(403, "Account inactive")
        @namespace.response(422, "Invalid authentication token")
        @account_required()
        def get(self):
            export_format = request.args.get("format", "json").lower()
            if export_format == "image":
                plans = db.session.scalars(
                    db.select(TravelPlan)
                    .where(
                        TravelPlan.account_id == g.current_account.id,
                        TravelPlan.departure_date > date.today(),
                    )
                    .order_by(TravelPlan.departure_date, TravelPlan.plan_id)
                    .limit(5)
                ).all()
                if not plans:
                    return {"message": "No upcoming travel plans"}, 404
                return png_export_response(plans, generate_travel_plans_image)

            if export_format != "json":
                return {"message": "Unsupported export format"}, 400

            plans = db.session.scalars(
                db.select(TravelPlan)
                .where(TravelPlan.account_id == g.current_account.id)
                .order_by(TravelPlan.departure_date, TravelPlan.plan_id)
            ).all()
            return json_export_response(plans)

    return namespace
