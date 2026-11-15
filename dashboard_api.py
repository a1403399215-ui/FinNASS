"""Register a read-only dashboard endpoint for the six-table Flask app."""
from datetime import datetime, timedelta, timezone
from flask import jsonify, request
from sqlalchemy import and_, or_, func
from demo_clock import demo_mode_enabled, resolve_clock

CODES = (
    'heart_rate', 'oxygen_concentration', 'radiation_dose_rate',
    'systolic_bp', 'diastolic_bp', 'body_temperature', 'humidity',
    'rmssd', 'ambient_temperature',
)
CABIN_CODES = ('oxygen_concentration', 'humidity', 'ambient_temperature')


def install_dashboard_api(app, db, Measurement, Indicator, Environment):
    def dashboard_data():
        # This demo is not an authentication or authorization mechanism.
        user_id = request.args.get('user_id', default=1, type=int)
        mission_id = request.args.get('mission_id', default=10, type=int)
        if user_id is None or mission_id is None or user_id < 1 or mission_id < 1:
            return jsonify({'error': 'Positive user_id and mission_id required'}), 400
        scope = (
            Measurement.mission_id == mission_id,
            Indicator.indicator_code.in_(CODES),
            Measurement.quality_status == 'valid',
            or_(
                and_(Indicator.indicator_code.in_(CABIN_CODES),
                     Measurement.user_id.is_(None)),
                and_(Indicator.indicator_code.notin_(CABIN_CODES),
                     Measurement.user_id == user_id),
            ),
        )
        latest_statement = (
            db.select(func.max(Measurement.observed_at))
            .join(Indicator, Measurement.indicator_id == Indicator.indicator_id)
            .where(*scope)
        )
        latest = db.session.execute(latest_statement).scalar_one_or_none()
        clock = resolve_clock(latest, demo_mode_enabled())
        end = datetime.fromisoformat(clock['window_end'])
        start = end - timedelta(days=7)
        statement = (
            db.select(Measurement, Indicator, Environment)
            .join(Indicator, Measurement.indicator_id == Indicator.indicator_id)
            .join(Environment, Measurement.environment_id == Environment.environment_id)
            .where(
                *scope,
                Measurement.observed_at > start.isoformat(timespec='seconds'),
                Measurement.observed_at <= end.isoformat(timespec='seconds'),
            )
            .order_by(Measurement.observed_at, Measurement.measurement_id)
        )
        metrics = {code: [] for code in CODES}
        for sample, indicator, environment in db.session.execute(statement).all():
            metrics[indicator.indicator_code].append({
                'id': sample.measurement_id,
                'metric_code': indicator.indicator_code,
                'value': sample.value,
                'unit': indicator.unit,
                'observed_at': sample.observed_at,
                'source': sample.source,
                'sensor_label': sample.sensor_label,
                'sensor_location': sample.sensor_location,
                'environment_id': environment.environment_id,
                'environment_name': environment.environment_name,
                'observation_group_id': sample.observation_group_id,
                'user_id': sample.user_id,
                'mission_id': sample.mission_id,
                'quality_status': sample.quality_status,
            })
        return jsonify({
            **clock,
            'window_start': start.isoformat(timespec='seconds'),
            'user_id': user_id,
            'mission_id': mission_id,
            'metrics': metrics,
        })

    # Allows a repeated installer call without duplicate route registration.
    if 'dashboard_data' not in app.view_functions:
        app.add_url_rule('/api/dashboard-data', 'dashboard_data', dashboard_data,
                         methods=['GET'])
