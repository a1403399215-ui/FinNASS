"""Import the included synthetic CSVs into a NEW SQLite database (stdlib only)."""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parent
SCHEMA = '''
PRAGMA foreign_keys=ON;
CREATE TABLE user_table (
 user_id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL, age INTEGER,
 gender VARCHAR(30), account_number VARCHAR(100) NOT NULL UNIQUE,
 password_hash VARCHAR(255) NOT NULL);
CREATE TABLE mission_table (
 mission_id INTEGER PRIMARY KEY, mission_description TEXT NOT NULL,
 mission_date DATE NOT NULL, mission_type VARCHAR(50) NOT NULL,
 ended_at VARCHAR(40));
CREATE TABLE mission_members (
 mission_id INTEGER NOT NULL REFERENCES mission_table(mission_id),
 user_id INTEGER NOT NULL REFERENCES user_table(user_id),
 PRIMARY KEY(mission_id,user_id));
CREATE TABLE indicator_table (
 indicator_id INTEGER PRIMARY KEY, indicator_code VARCHAR(50) NOT NULL UNIQUE,
 display_name VARCHAR(100) NOT NULL, unit VARCHAR(20) NOT NULL,
 value_type VARCHAR(20) NOT NULL);
CREATE TABLE environment_table (
 environment_id INTEGER PRIMARY KEY, environment_name VARCHAR(100) NOT NULL,
 location VARCHAR(100) NOT NULL, gravity_condition VARCHAR(50) NOT NULL,
 protection VARCHAR(100) NOT NULL, is_isolated BOOLEAN NOT NULL,
 is_confined BOOLEAN NOT NULL, description TEXT);
CREATE TABLE measurement_table (
 measurement_id INTEGER PRIMARY KEY, observed_at VARCHAR(40) NOT NULL,
 user_id INTEGER REFERENCES user_table(user_id),
 mission_id INTEGER NOT NULL REFERENCES mission_table(mission_id),
 indicator_id INTEGER NOT NULL REFERENCES indicator_table(indicator_id),
 environment_id INTEGER NOT NULL REFERENCES environment_table(environment_id),
 observation_group_id INTEGER, sensor_label VARCHAR(100) NOT NULL,
 sensor_location VARCHAR(100) NOT NULL, value FLOAT NOT NULL,
 source VARCHAR(50) NOT NULL, quality_status VARCHAR(30) NOT NULL,
 FOREIGN KEY(mission_id,user_id) REFERENCES mission_members(mission_id,user_id));
CREATE INDEX ix_measurement_table_observed_at ON measurement_table(observed_at);
CREATE INDEX ix_measurement_lookup ON measurement_table(mission_id,user_id,indicator_id,observed_at);
'''
ORDER = ['user_table', 'mission_table', 'mission_members', 'indicator_table',
         'environment_table', 'measurement_table']
INTS = {'user_id', 'age', 'mission_id', 'indicator_id', 'environment_id',
        'measurement_id', 'observation_group_id'}
BOOLS = {'is_isolated', 'is_confined'}

def read_time(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('Timestamp must specify its UTC offset')
    return dt.astimezone(timezone.utc)

def rows_for(table, columns, files):
    for item in files:
        with (ROOT / 'data' / item['file']).open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != columns:
                raise ValueError(f"Unexpected columns in {item['file']}")
            count = 0
            for line, row in enumerate(reader, 2):
                count += 1
                yield line, row
            if count != item['records']:
                raise ValueError(f"Unexpected row count in {item['file']}")

def import_data(database, align_now=False):
    database = Path(database).resolve()
    if database.exists():
        raise ValueError(f'Destination already exists; nothing changed: {database}. '
                         'Use --database instance/health_csv_2.db for a new import.')
    manifest = json.loads((ROOT / 'manifest.json').read_text(encoding='utf-8'))
    if manifest['synthetic'] is not True:
        raise ValueError('This importer expects the bundled synthetic dataset')
    expected = {table: [item for item in manifest['files'] if item['table'] == table] for table in ORDER}
    # Integrity checks prevent silently importing a modified or incomplete download.
    for item in manifest['files']:
        raw = (ROOT / 'data' / item['file']).read_bytes()
        if hashlib.sha256(raw).hexdigest() != item['sha256']:
            raise ValueError(f"Checksum mismatch: {item['file']}")
    shift = timedelta(0)
    if align_now:
        target = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        shift = target - read_time(manifest['end'])
    database.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix='.csv-import-', suffix='.db',
                                         dir=database.parent)
    os.close(handle)
    conn = None
    try:
        conn = sqlite3.connect(temporary)
        conn.executescript(SCHEMA)
        counts = {}
        with conn:
            for table in ORDER:
                columns = [r[1] for r in conn.execute(f'PRAGMA table_info({table})')]
                count = 0
                for line, row in rows_for(table, columns, expected[table]):
                    values = []
                    for key in columns:
                        value = row[key]
                        if value is None:
                            raise ValueError(f'{table}.csv line {line}: missing cell')
                        if value == '':
                            value = None
                        elif key in INTS:
                            value = int(value)
                        elif key in BOOLS:
                            if value not in ('0', '1'):
                                raise ValueError('Boolean must be 0 or 1')
                            value = int(value)
                        elif key == 'value':
                            value = float(value)
                            if not math.isfinite(value):
                                raise ValueError('Measurement value must be finite')
                        elif key in ('observed_at', 'ended_at'):
                            value = (read_time(value) + shift).isoformat(timespec='seconds')
                        elif key == 'mission_date':
                            value = (read_time(value + 'T00:00:00+00:00') + shift).date().isoformat()
                        values.append(value)
                    placeholders = ','.join('?' for _ in values)
                    conn.execute(f'INSERT INTO {table} ({",".join(columns)}) '
                                 f'VALUES ({placeholders})', values)
                    count += 1
                if count != sum(item['records'] for item in expected[table]):
                    raise ValueError(f'Unexpected row count in {table}')
                counts[table] = count
            if conn.execute('PRAGMA foreign_key_check').fetchall():
                raise ValueError('Foreign-key validation failed')
            invalid = conn.execute('''SELECT COUNT(*) FROM measurement_table m
                JOIN indicator_table i USING(indicator_id)
                WHERE i.value_type='INT' AND m.value != CAST(m.value AS INTEGER)''').fetchone()[0]
            if invalid:
                raise ValueError('Non-integer values found for an INT metric')
            bad_bp = conn.execute('''SELECT observation_group_id FROM measurement_table
                WHERE observation_group_id IS NOT NULL GROUP BY observation_group_id
                HAVING COUNT(*) != 2 OR COUNT(DISTINCT indicator_id) != 2
                OR MIN(indicator_id) != 4 OR MAX(indicator_id) != 5
                OR COUNT(DISTINCT user_id) != 1 OR COUNT(DISTINCT observed_at) != 1''').fetchall()
            if bad_bp:
                raise ValueError('Invalid blood pressure pairs')
        assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        print('Time range (UTC):', *conn.execute(
            'SELECT MIN(observed_at), MAX(observed_at) FROM measurement_table').fetchone())
        conn.close()
        conn = None
        # Exclusive publication: an existing destination is never overwritten.
        os.link(temporary, database)
        print('Created:', database)
        for table, count in counts.items():
            print(f'  {table}: {count:,} rows')
        print('Source: csv_simulation; synthetic testing data only.')
        return counts
    finally:
        if conn is not None:
            conn.close()
        Path(temporary).unlink(missing_ok=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', default='instance/health_csv_hourly_v4.db',
                        help='New database path, relative to your current project folder')
    parser.add_argument('--align-now', action='store_true',
                        help='Shift all timestamps equally so the latest sample is current')
    args = parser.parse_args()
    try:
        import_data(args.database, args.align_now)
    except (ValueError, OSError, sqlite3.Error, KeyError, csv.Error) as error:
        parser.exit(1, f'Import failed; destination not overwritten: {error}\n')
