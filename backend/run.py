import os
from pathlib import Path

from airroute import create_app, init_db

# Direct execution is the local development entry point. The factory itself
# defaults to production settings, including a required explicit JWT secret.
app = create_app(
    {"APP_ENV": os.environ.get("AIRROUTE_ENV", "development")},
    instance_path=str(Path(__file__).resolve().parent.parent / "instance"),
)


if __name__ == "__main__":
    init_db(app)
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
