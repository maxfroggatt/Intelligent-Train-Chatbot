import csv
import sqlite3
import os

# Connect to SQLite database
conn = sqlite3.connect('train_data.db')
cursor = conn.cursor()

# Create stations table
cursor.execute('''
CREATE TABLE IF NOT EXISTS stations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    longname TEXT,
    name_alias TEXT,
    alpha3 TEXT,
    tiploc TEXT
)
''')

# Create ticket_results table
cursor.execute('''
CREATE TABLE IF NOT EXISTS ticket_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    origin TEXT,
    destination TEXT,
    is_return BOOLEAN,
    departure_date TEXT,
    return_date TEXT,
    cheapest_price REAL,
    booking_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

# Create journey_queries table
cursor.execute('''
CREATE TABLE IF NOT EXISTS journey_queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_input TEXT,
    origin TEXT,
    destination TEXT,
    departure_date TEXT,
    return_date TEXT,
    departure_time TEXT,
    return_time TEXT,
    adults INTEGER,
    children INTEGER,
    is_return BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

# Create darwin_journeys table with foreign key
cursor.execute('''
CREATE TABLE IF NOT EXISTS darwin_journeys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    journey_query_id INTEGER,
    origin TEXT,
    destination TEXT,
    departure_time TEXT,
    tiploc_route TEXT,
    matched BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (journey_query_id) REFERENCES journey_queries(id)
)
''')

# Get path to stations.csv
csv_path = os.path.join(os.path.dirname(__file__), 'stations.csv')

# Load stations.csv and insert rows into stations table
with open(csv_path, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    next(reader)  # Skip header
    for row in reader:
        name, longname, name_alias, alpha3, tiploc = row
        cursor.execute('''
            INSERT INTO stations (name, longname, name_alias, alpha3, tiploc)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            name,
            longname,
            name_alias if name_alias != r'\N' else None,
            alpha3 if alpha3 != r'\N' else None,
            tiploc if tiploc != r'\N' else None
        ))

# Finalize and close
conn.commit()
conn.close()
print("Database initialized and all tables created (including journey_queries).")