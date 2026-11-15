import psycopg2
import pandas as pd

# 1: Connect to database:
conn = psycopg2.connect(
    dbname="nasa", 
    user="halima", 
    host="localhost", 
    port="5432", 
    password="1234"
)

cur = conn.cursor()
excel_path = "LIST OF PARAMETERS.xlsx"
def_param = pd.read_excel(excel_path, sheet_name="PARAMETER", skiprows=1)

print("Importing parameter definitions...")
for _, row in def_param.iterrows():
    param_name = row.iloc[3]
    if pd.isna(param_name):
        continue
    category = row.iloc[2]
    unit = row.iloc[3]
    upper_limit = pd.to_numeric(row.iloc[5], errors="coerce")
    lower_limit = pd.to_numeric(row.iloc[6], errors="coerce")
    explination = row.iloc[7]

    cur.execute("""
        INSERT INTO parameter (param_name, category, unit, upper_limit, lower_limit, explination)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (param_name) DO NOTHING;
    """, (str(param_name), str(category), str(unit), upper_limit, lower_limit, str(explination)))

conn.commit()

print("Setting up environments and astronaut...")
scenarios = [
    ("Normal Mission",), 
    ("Psychological Stress",),
    ("Environmental Incident",), 
    ("CARDIAC Incident",)
]

for scenario in scenarios:
    cur.execute("""
        INSERT INTO envi (mission_name) VALUES (%s)
        ON CONFLICT (mission_name) DO NOTHING;
    """, scenario)

# CRITICAL: Commit the environments to the database first!
conn.commit()

# Insert the astronaut referencing envi_id = 1
cur.execute("""
    INSERT INTO astro (astro_name, envi_id) 
    VALUES ('Commander Alex', 1);
""")
conn.commit()

# FIXED: Correctly fetch the newly created astro_id
cur.execute("SELECT astro_id FROM astro ORDER BY astro_id DESC LIMIT 1;")
astro_id = cur.fetchone()[0]

sheet_scenario_map = {
    'Normal Mission Dataset': 1,
    'Psychological stress dataset': 2,
    'Environmental Incident dataset ': 3,
    'Cardiac incident ': 4
}

base_date = pd.Timestamp("2026-11-15")

for sheet_name, envi_id in sheet_scenario_map.items():
    print(f"Importing sheet: {sheet_name}...")
    df = pd.read_excel(excel_path, sheet_name=sheet_name)
    df.columns = df.columns.str.strip()
    
    for _, row in df.iterrows():
        if pd.isna(row['Time']):
            continue
        # Cleanly split time string
        time_raw = str(row['Time'])
        time_str = time_raw.split()[0] if ' ' in time_raw else time_raw
        time_parts = time_str.split(':')
        
        recorded_at = base_date + pd.Timedelta(
            hours=int(time_parts[0]), 
            minutes=int(time_parts[1])
        )
        
        # 1. Insert Biological Data
        cur.execute("""
            INSERT INTO bio_data (astro_id, envi_id, time, bpm, sys, dia, temperature, rmssd)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
        """, (
            astro_id,
            envi_id,
            recorded_at,
            int(row['BPM']),
            int(row['SYS']),
            int(row['DIA']),
            float(row.get('Temp °C', 36.5)),
            float(row.get('RMSSD ms', 50.0))
        ))
        
        # 2. Insert Psychological Data
        cur.execute("""
            INSERT INTO psycho_data (astro_id, envi_id, time, work, team, mood)
            VALUES (%s, %s, %s, %s, %s, %s);
        """, (
            astro_id,
            envi_id,
            recorded_at,
            int(row.get('Work', 3)),
            int(row.get('Team', 3)),
            int(row.get('Mood', 3))
        ))
        
        # 3. Insert Environmental Data
        cur.execute("""
            INSERT INTO envi_data (envi_id, time, humidity, radiation, o2)
            VALUES (%s, %s, %s, %s, %s);
        """, (
            envi_id,
            recorded_at,
            float(row.get('Hum %', 50.0)),
            float(row.get('Radiation µSv/h', 17.0)),
            float(row.get('O2 %', 20.9))
        ))

conn.commit()
cur.close()
conn.close()
print("All datasets successfully imported from Excel into PostgreSQL!")