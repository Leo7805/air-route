from .extensions import db


class Account(db.Model):
    __tablename__ = "accounts"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(10), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    __table_args__ = (
        db.CheckConstraint(
            "role IN ('Admin', 'User')",
            name="ck_accounts_role",
        ),
        db.CheckConstraint(
            "is_active IN (0, 1)",
            name="ck_accounts_is_active",
        ),
    )


class Airport(db.Model):
    __tablename__ = "airports"

    airport_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(100))
    country = db.Column(db.String(100))
    iata_code = db.Column(db.String(3))
    icao_code = db.Column(db.String(4))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    altitude = db.Column(db.Integer)
    timezone = db.Column(db.String(100))


class Airline(db.Model):
    __tablename__ = "airlines"

    airline_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    iata_code = db.Column(db.String(2))
    icao_code = db.Column(db.String(3))
    country = db.Column(db.String(100))


class Route(db.Model):
    __tablename__ = "routes"

    route_id = db.Column(db.Integer, primary_key=True)
    airline_id = db.Column(db.Integer, nullable=False)
    airline_iata = db.Column(db.String(2))
    origin_airport_id = db.Column(db.Integer, nullable=False)
    origin_iata = db.Column(db.String(3))
    destination_airport_id = db.Column(db.Integer, nullable=False)
    destination_iata = db.Column(db.String(3))
    codeshare = db.Column(db.String(10))
    stops = db.Column(db.Integer, nullable=False)
    equipment = db.Column(db.String(100))


class TravelPlan(db.Model):
    __tablename__ = "travel_plans"

    plan_id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(
        db.Integer,
        db.ForeignKey("accounts.id"),
        nullable=False,
        index=True,
    )
    name = db.Column(db.String(255), nullable=False)
    departure_date = db.Column(db.Date, nullable=False)
    return_date = db.Column(db.Date, nullable=False)

    __table_args__ = (
        db.CheckConstraint(
            "return_date >= departure_date",
            name="ck_travel_plan_dates",
        ),
    )

    route_links = db.relationship(
        "TravelPlanRoute",
        back_populates="plan",
        cascade="all, delete-orphan",
    )


class TravelPlanRoute(db.Model):
    __tablename__ = "travel_plan_routes"

    plan_id = db.Column(
        db.Integer,
        db.ForeignKey("travel_plans.plan_id", ondelete="CASCADE"),
        primary_key=True,
    )
    route_id = db.Column(
        db.Integer,
        db.ForeignKey("routes.route_id", ondelete="RESTRICT"),
        primary_key=True,
    )

    plan = db.relationship("TravelPlan", back_populates="route_links")
    route = db.relationship("Route")
