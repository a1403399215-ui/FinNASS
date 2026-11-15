import os
from datetime import datetime, timedelta, timezone

import click
from flask import Flask, jsonify, request, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine
from werkzeug.security import generate_password_hash


app = Flask(__name__)

# use new database, backup health.db
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL",
    "sqlite:///health_csv_hourly_v4.db",
)

db = SQLAlchemy(app)


# SQLite open foreign key detection, otherwise foreign key constraints will not work.
@event.listens_for(Engine, "connect")
def enable_foreign_keys(connection, connection_record):
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# ---------- 1. astrountant_table ----------

class User(db.Model):
    __tablename__ = "user_table"

    user_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer)
    gender = db.Column(db.String(30))

    account_number = db.Column(
        db.String(100),
        unique=True,
        nullable=False,
    )

    password_hash = db.Column(db.String(255), nullable=False)


# ---------- 2. mission_table ----------

class Mission(db.Model):
    __tablename__ = "mission_table"

    mission_id = db.Column(db.Integer, primary_key=True)
    mission_description = db.Column(db.Text, nullable=False)
    mission_date = db.Column(db.Date, nullable=False)
    mission_type = db.Column(db.String(50), nullable=False)

    # time use UTC ISO format, e.g. 2024-06-01T12:00:00Z
    ended_at = db.Column(db.String(40))


# ---------- 3. mission_members ----------

class MissionMember(db.Model):
    __tablename__ = "mission_members"

    mission_id = db.Column(
        db.Integer,
        db.ForeignKey("mission_table.mission_id"),
        primary_key=True,
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user_table.user_id"),
        primary_key=True,
    )


# ---------- 4. indicator_table ----------

class Indicator(db.Model):
    __tablename__ = "indicator_table"

    indicator_id = db.Column(db.Integer, primary_key=True)

    indicator_code = db.Column(
        db.String(50),
        unique=True,
        nullable=False,
    )

    display_name = db.Column(db.String(100), nullable=False)
    unit = db.Column(db.String(20), nullable=False)
    value_type = db.Column(db.String(20), nullable=False)


# ---------- 5. environment_table ----------

class Environment(db.Model):
    __tablename__ = "environment_table"

    environment_id = db.Column(db.Integer, primary_key=True)
    environment_name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    gravity_condition = db.Column(db.String(50), nullable=False)
    protection = db.Column(db.String(100), nullable=False)

    is_isolated = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    is_confined = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    description = db.Column(db.Text)


# ---------- 6. measurement_table ----------

class Measurement(db.Model):
    __tablename__ = "measurement_table"

    measurement_id = db.Column(db.Integer, primary_key=True)

    observed_at = db.Column(
        db.String(40),
        nullable=False,
        index=True,
    )

    # Readings from public sensors inside the spacecraft need not be attributed
    # to any specific astronaut. so user_id can be NULL.
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user_table.user_id"),
        nullable=True,
    )

    mission_id = db.Column(
        db.Integer,
        db.ForeignKey("mission_table.mission_id"),
        nullable=False,
    )

    indicator_id = db.Column(
        db.Integer,
        db.ForeignKey("indicator_table.indicator_id"),
        nullable=False,
    )

    environment_id = db.Column(
        db.Integer,
        db.ForeignKey("environment_table.environment_id"),
        nullable=False,
    )

    # The systolic and diastolic blood pressure values ​​from the same measurement 
    # are assigned the same group number.
    observation_group_id = db.Column(db.Integer)

    sensor_label = db.Column(db.String(100), nullable=False)
    sensor_location = db.Column(db.String(100), nullable=False)

    value = db.Column(db.Float, nullable=False)
    source = db.Column(db.String(50), nullable=False)

    quality_status = db.Column(
        db.String(30),
        nullable=False,
        default="valid",
    )

    #when user_id is not NULL,require that the astronaut actually belongs to the mission.
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["mission_id", "user_id"],
            [
                "mission_members.mission_id",
                "mission_members.user_id",
            ],
        ),
    )


# ---------- home page----------

@app.get("/")
def home():
    return send_from_directory(app.static_folder, "index.html")


# ---------- measurements history API ----------

@app.get("/api/measurements")
def get_measurements():
    metric_code = request.args.get("metric_code", "heart_rate")
    user_id = request.args.get("user_id", default=1, type=int)
    mission_id = request.args.get("mission_id", default=10, type=int)

    statement = (
        db.select(Measurement, Indicator, Environment)
        .join(
            Indicator,
            Measurement.indicator_id == Indicator.indicator_id,
        )
        .join(
            Environment,
            Measurement.environment_id == Environment.environment_id,
        )
        .where(
            Indicator.indicator_code == metric_code,
            Measurement.user_id == user_id,
            Measurement.mission_id == mission_id,
        )
        .order_by(
            Measurement.observed_at,
            Measurement.measurement_id,
        )
    )

    records = db.session.execute(statement).all()

    return jsonify([
        {
            "id": measurement.measurement_id,
            "metric_code": indicator.indicator_code,
            "value": measurement.value,
            "unit": indicator.unit,
            "observed_at": measurement.observed_at,
            "source": measurement.source,
            "sensor_label": measurement.sensor_label,
            "environment_id": environment.environment_id,
            "environment_name": environment.environment_name,
        }
        for measurement, indicator, environment in records
    ])


# ---------- home overview API ----------

@app.get("/api/overview")
def overview():
    user_id = request.args.get("user_id", default=1, type=int)
    mission_id = request.args.get("mission_id", default=10, type=int)

    statement = (
        db.select(Measurement)
        .join(
            Indicator,
            Measurement.indicator_id == Indicator.indicator_id,
        )
        .where(
            Indicator.indicator_code == "heart_rate",
            Measurement.user_id == user_id,
            Measurement.mission_id == mission_id,
        )
        .order_by(
            Measurement.observed_at.desc(),
            Measurement.measurement_id.desc(),
        )
        .limit(1)
    )

    latest = db.session.execute(statement).scalar_one_or_none()

    return jsonify({
        "heart_rate": latest.value if latest else None,
        "observed_at": latest.observed_at if latest else None,
        "source": latest.source if latest else None,
    })


# ---------- create database tables ----------

@app.cli.command("init-db")
def init_db():
    db.create_all()
    click.echo("6 database tables created.")

    
from dashboard_api import install_dashboard_api
install_dashboard_api(app, db, Measurement, Indicator, Environment)