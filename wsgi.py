"""Gunicorn entrypoint: imports your existing Flask application."""
from sqlalchemy import text
from app import app, db
from demo_clock import demo_mode_enabled

app.debug = False

# Fail at startup, rather than quietly serving an empty or missing database.
with app.app_context():
    result = db.session.execute(text(
        'SELECT COUNT(*) AS sample_count, MAX(observed_at) AS latest '
        'FROM measurement_table'
    )).one()
    if result._mapping['sample_count'] == 0:
        raise RuntimeError('Demo database is empty. Import the provided CSV dataset first.')


def healthz():
    return {'status': 'ok', 'mode': 'demo' if demo_mode_enabled() else 'live'}


if 'healthz' not in app.view_functions:
    app.add_url_rule('/healthz', 'healthz', healthz, methods=['GET'])
