FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    DEMO_MODE=true \
    DATABASE_URL="sqlite:///file:/app/instance/health_csv_hourly_v4.db?mode=ro&uri=true"

WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY app.py dashboard_api.py demo_clock.py wsgi.py gunicorn.conf.py ./
COPY static/ ./static/
COPY csv_data_hourly/ ./csv_data_hourly/

# Build a reproducible, fixed snapshot from CSV. Do not shift timestamps at startup.
RUN mkdir -p instance \
    && python csv_data_hourly/import_csv.py --database /app/instance/health_csv_hourly_v4.db \
    && chmod 0444 /app/instance/health_csv_hourly_v4.db \
    && useradd --uid 10001 --create-home appuser \
    && chmod 0555 /app/instance

USER appuser
EXPOSE 8080
CMD ["gunicorn", "--config", "gunicorn.conf.py", "wsgi:app"]
