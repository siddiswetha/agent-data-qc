"""SQLite storage helpers. One small table per service.

Each service keeps its own database file, so a failure in one
service does not corrupt another service's records.
"""
import json
import sqlite3


def connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_intake_db(db_path):
    conn = connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS batches ("
        "batch_id TEXT PRIMARY KEY, vendor TEXT, count INTEGER, "
        "received_at TEXT, payload TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS trajectories ("
        "trajectory_id TEXT PRIMARY KEY, batch_id TEXT, vendor TEXT, payload TEXT)"
    )
    conn.commit()
    conn.close()


def init_validator_db(db_path):
    conn = connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS validations ("
        "trajectory_id TEXT PRIMARY KEY, defective INTEGER, "
        "anomaly_score REAL, defects TEXT, checked_at TEXT)"
    )
    conn.commit()
    conn.close()


def init_auditor_db(db_path):
    conn = connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS reports ("
        "batch_id TEXT PRIMARY KEY, report TEXT, created_at TEXT)"
    )
    conn.commit()
    conn.close()


def store_json(conn, table, row):
    columns = ", ".join(row.keys())
    placeholders = ", ".join("?" for _ in row)
    values = [json.dumps(v) if isinstance(v, (dict, list)) else v for v in row.values()]
    conn.execute(f"INSERT OR REPLACE INTO {table} ({columns}) VALUES ({placeholders})", values)
    conn.commit()
