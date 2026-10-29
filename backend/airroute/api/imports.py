from flask import request
from flask_restx import Resource, fields
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.datastructures import FileStorage

from ..auth import account_required
from ..csv_import import (
    DATASET_MODELS,
    ReferenceConflictError,
    import_uploaded_datasets,
)


def register_imports(api):
    namespace = getattr(api, "modular_namespace", api.namespace)(
        "Data Import",
        description="Admin-only CSV imports.",
        path="/imports",
    )
    import_counts_model = namespace.model(
        "ImportCounts",
        {
            dataset: fields.Integer(description=f"Number of imported {dataset}")
            for dataset in ("airports", "airlines", "routes")
        },
    )
    import_response_model = namespace.model(
        "ImportResponse",
        {
            "message": fields.String(required=True),
            "datasets": fields.List(fields.String, required=True),
            "counts": fields.Nested(import_counts_model, required=True),
        },
    )
    upload_parser = namespace.parser()
    for dataset in ("airports", "airlines", "routes"):
        upload_parser.add_argument(
            dataset,
            type=FileStorage,
            location="files",
            required=False,
            help=f"Upload {dataset}.csv",
        )

    @namespace.route("")
    class DataImport(Resource):
        @namespace.doc(
            security="BearerAuth",
            description=(
                "Admin-only CSV import with atomic dataset replacement. "
                "Referenced Travel Plan routes cannot be removed or changed "
                "(HTTP 409)."
            ),
        )
        @namespace.expect(upload_parser)
        @namespace.response(200, "Datasets imported successfully", import_response_model)
        @namespace.response(400, "Invalid CSV or upload request")
        @namespace.response(401, "Authentication required")
        @namespace.response(403, "Admin access required")
        @namespace.response(409, "Referential integrity conflict")
        @namespace.response(415, "Multipart form data required")
        @namespace.response(422, "Malformed access token")
        @namespace.response(500, "Database import failed, including lock timeout")
        @account_required(role="Admin")
        def post(self):
            if request.mimetype != "multipart/form-data":
                return {"message": "Expected multipart/form-data"}, 415
            if not request.files:
                return {"message": "No CSV files uploaded"}, 400
            unknown = set(request.files) - set(DATASET_MODELS)
            if unknown:
                return {"message": f"Unknown datasets: {sorted(unknown)}"}, 400

            uploaded = {}
            try:
                for dataset in request.files:
                    files = request.files.getlist(dataset)
                    if len(files) != 1 or not files[0].filename:
                        raise ValueError(
                            f"Exactly one file is required for {dataset}"
                        )
                    uploaded[dataset] = files[0].read()
                replacements = import_uploaded_datasets(uploaded)
            except ReferenceConflictError as error:
                return {"message": str(error)}, 409
            except ValueError as error:
                return {"message": str(error)}, 400
            except SQLAlchemyError:
                return {"message": "Database import failed"}, 500

            return {
                "message": "Import completed successfully",
                "datasets": list(replacements),
                "counts": {
                    dataset: len(records)
                    for dataset, records in replacements.items()
                },
            }, 200

    return namespace
