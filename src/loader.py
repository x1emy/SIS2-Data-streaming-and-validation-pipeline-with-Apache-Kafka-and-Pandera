import os
import sqlite3
import pandas as pd

CLEANED_PATH = "data/cleaned_data.csv"
DB_PATH = "data/output.db"
TABLE = "collisions"

CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    collision_id                  TEXT PRIMARY KEY,
    crash_datetime                TEXT NOT NULL,
    crash_date                    TEXT NOT NULL,
    crash_time                    TEXT NOT NULL,
    borough                       TEXT NOT NULL,
    zip_code                      TEXT,
    latitude                      REAL,
    longitude                     REAL,
    on_street_name                TEXT,
    cross_street_name             TEXT,
    number_of_persons_injured     INTEGER NOT NULL CHECK (number_of_persons_injured >= 0),
    number_of_persons_killed      INTEGER NOT NULL CHECK (number_of_persons_killed >= 0),
    number_of_pedestrians_injured INTEGER NOT NULL,
    number_of_pedestrians_killed  INTEGER NOT NULL,
    number_of_cyclist_injured     INTEGER NOT NULL,
    number_of_cyclist_killed      INTEGER NOT NULL,
    number_of_motorist_injured    INTEGER NOT NULL,
    number_of_motorist_killed     INTEGER NOT NULL,
    contributing_factor_vehicle_1 TEXT,
    contributing_factor_vehicle_2 TEXT,
    vehicle_type_code1            TEXT,
    vehicle_type_code2            TEXT,
    num_vehicles                  INTEGER,
    hour                          INTEGER CHECK (hour BETWEEN 0 AND 23),
    day_of_week                   TEXT,
    is_weekend                    INTEGER CHECK (is_weekend IN (0, 1)),
    total_casualties              INTEGER,
    severity                      TEXT,
    time_of_day                   TEXT
);
"""

VERIFICATION_QUERIES = {
    "Total rows": f"SELECT COUNT(*) AS total_rows FROM {TABLE};",
    "Unique collision_id": f"SELECT COUNT(DISTINCT collision_id) AS unique_ids FROM {TABLE};",
    "Duplicate IDs (should be empty)": f"""
        SELECT collision_id, COUNT(*) AS n FROM {TABLE}
        GROUP BY collision_id HAVING COUNT(*) > 1;""",
    "Date range": f"SELECT MIN(crash_datetime) AS first_crash, MAX(crash_datetime) AS last_crash FROM {TABLE};",
    "Crashes and injuries by borough": f"""
        SELECT borough, COUNT(*) AS crashes, SUM(number_of_persons_injured) AS injured
        FROM {TABLE} GROUP BY borough ORDER BY crashes DESC;""",
    "Top 5 contributing factors": f"""
        SELECT contributing_factor_vehicle_1 AS factor, COUNT(*) AS crashes
        FROM {TABLE} GROUP BY factor ORDER BY crashes DESC LIMIT 5;""",
}


def get_columns(conn):
    return [row[1] for row in conn.execute(f"PRAGMA table_info({TABLE});")]


def prepare_rows(df, columns):
    df = df.copy()
    for col in columns:
        if col not in df.columns:
            df[col] = None
    df["is_weekend"] = df["is_weekend"].astype(int)
    df = df[columns].astype(object).where(df[columns].notna(), None)
    return [tuple(row) for row in df.itertuples(index=False)]


def count_rows(conn):
    return conn.execute(f"SELECT COUNT(*) FROM {TABLE};").fetchone()[0]


def load(df, db_path=DB_PATH):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(CREATE_TABLE_SQL)
        columns = get_columns(conn)
        rows = prepare_rows(df, columns)
        placeholders = ", ".join(["?"] * len(columns))
        before = count_rows(conn)
        conn.executemany(
            f"INSERT OR IGNORE INTO {TABLE} ({', '.join(columns)}) VALUES ({placeholders});", rows
        )
        conn.commit()
        after = count_rows(conn)
        return {"processed": len(rows), "before": before, "after": after, "inserted": after - before}
    except sqlite3.Error as error:
        conn.rollback()
        print(f"Database error: {error}")
        raise
    finally:
        conn.close()


def table_fingerprint(db_path=DB_PATH):
    with sqlite3.connect(db_path) as conn:
        return conn.execute(
            f"SELECT COUNT(*), SUM(number_of_persons_injured), SUM(num_vehicles), "
            f"MIN(crash_datetime), MAX(crash_datetime) FROM {TABLE};"
        ).fetchone()


def run_verification(db_path=DB_PATH):
    with sqlite3.connect(db_path) as conn:
        for title, query in VERIFICATION_QUERIES.items():
            print(f"\n-- {title}")
            result = pd.read_sql_query(query, conn)
            print(result.to_string(index=False) if not result.empty else "(no rows)")


if __name__ == "__main__":
    df = pd.read_csv(CLEANED_PATH, dtype={"zip_code": str})
    print(f"Processed records to load: {len(df)}")

    print("\n=== Load run 1 ===")
    run1 = load(df)
    print(run1)
    fingerprint_1 = table_fingerprint()

    print("\n=== Load run 2 (same data, idempotency test) ===")
    run2 = load(df)
    print(run2)
    fingerprint_2 = table_fingerprint()

    print(f"\nFingerprint after run 1: {fingerprint_1}")
    print(f"Fingerprint after run 2: {fingerprint_2}")
    print("Idempotency:", "PASSED" if run2["inserted"] == 0 and fingerprint_1 == fingerprint_2 else "FAILED")

    run_verification()

    stored = run2["after"]
    print(f"\nProcessed: {len(df)}, stored in SQLite: {stored}, "
          f"{'match' if stored == len(df) else 'MISMATCH'}")