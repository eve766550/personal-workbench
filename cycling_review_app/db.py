"""SQLite 数据库操作。

把数据库代码单独放在这里，是为了让 app.py 只关注网页请求和页面流程。
"""

import sqlite3
from pathlib import Path

from flask import current_app, g


SCHEMA = """
CREATE TABLE IF NOT EXISTS rides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ride_date TEXT NOT NULL,
    distance_km REAL NOT NULL,
    duration_minutes INTEGER NOT NULL,
    average_speed REAL,
    average_heart_rate INTEGER,
    max_heart_rate INTEGER,
    elevation_gain INTEGER,
    fatigue INTEGER,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS training_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_date TEXT NOT NULL,
    weeks INTEGER NOT NULL,
    rides_per_week INTEGER NOT NULL,
    goal TEXT NOT NULL,
    goal_label TEXT NOT NULL,
    baseline_weekly_km REAL NOT NULL,
    baseline_longest_km REAL NOT NULL,
    average_fatigue REAL,
    source_ride_count INTEGER NOT NULL,
    data_warning TEXT,
    rationale TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS training_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER NOT NULL,
    week_number INTEGER NOT NULL,
    session_number INTEGER NOT NULL,
    session_date TEXT NOT NULL,
    session_type TEXT NOT NULL,
    title TEXT NOT NULL,
    target_distance_km REAL NOT NULL,
    description TEXT NOT NULL,
    completed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (plan_id) REFERENCES training_plans (id) ON DELETE CASCADE
)
"""


def get_db():
    """取得当前请求使用的数据库连接。"""

    if "db" not in g:
        database_path = Path(current_app.config["DATABASE"])
        database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        g.db = connection
    return g.db


def close_db(_error=None):
    """请求结束时关闭数据库连接。"""

    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_db():
    """创建第一阶段所需的数据表。表已存在时不会覆盖数据。"""

    connection = get_db()
    connection.executescript(SCHEMA)
    connection.commit()


def list_rides():
    connection = get_db()
    return connection.execute(
        """
        SELECT id, ride_date, distance_km, duration_minutes,
               average_speed, average_heart_rate, max_heart_rate,
               elevation_gain, fatigue, notes
        FROM rides
        ORDER BY ride_date DESC, id DESC
        """
    ).fetchall()


def get_ride(ride_id):
    connection = get_db()
    return connection.execute(
        """
        SELECT id, ride_date, distance_km, duration_minutes,
               average_speed, average_heart_rate, max_heart_rate,
               elevation_gain, fatigue, notes
        FROM rides
        WHERE id = ?
        """,
        (ride_id,),
    ).fetchone()


def create_ride(ride):
    connection = get_db()
    cursor = connection.execute(
        """
        INSERT INTO rides (
            ride_date, distance_km, duration_minutes, average_speed,
            average_heart_rate, max_heart_rate, elevation_gain, fatigue, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ride["ride_date"],
            ride["distance_km"],
            ride["duration_minutes"],
            ride["average_speed"],
            ride["average_heart_rate"],
            ride["max_heart_rate"],
            ride["elevation_gain"],
            ride["fatigue"],
            ride["notes"],
        ),
    )
    connection.commit()
    return cursor.lastrowid


def update_ride(ride_id, ride):
    connection = get_db()
    cursor = connection.execute(
        """
        UPDATE rides
        SET ride_date = ?, distance_km = ?, duration_minutes = ?,
            average_speed = ?, average_heart_rate = ?, max_heart_rate = ?,
            elevation_gain = ?, fatigue = ?, notes = ?
        WHERE id = ?
        """,
        (
            ride["ride_date"],
            ride["distance_km"],
            ride["duration_minutes"],
            ride["average_speed"],
            ride["average_heart_rate"],
            ride["max_heart_rate"],
            ride["elevation_gain"],
            ride["fatigue"],
            ride["notes"],
            ride_id,
        ),
    )
    connection.commit()
    return cursor.rowcount


def delete_ride(ride_id):
    connection = get_db()
    cursor = connection.execute("DELETE FROM rides WHERE id = ?", (ride_id,))
    connection.commit()
    return cursor.rowcount


def create_training_plan(plan, sessions):
    """保存一份计划及其所有训练日，并返回计划 id。"""

    connection = get_db()
    cursor = connection.execute(
        """
        INSERT INTO training_plans (
            start_date, weeks, rides_per_week, goal, goal_label,
            baseline_weekly_km, baseline_longest_km, average_fatigue,
            source_ride_count, data_warning, rationale
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            plan["start_date"],
            plan["weeks"],
            plan["rides_per_week"],
            plan["goal"],
            plan["goal_label"],
            plan["baseline_weekly_km"],
            plan["baseline_longest_km"],
            plan["average_fatigue"],
            plan["source_ride_count"],
            plan["data_warning"],
            "\n".join(plan["rationale"]),
        ),
    )
    plan_id = cursor.lastrowid
    connection.executemany(
        """
        INSERT INTO training_sessions (
            plan_id, week_number, session_number, session_date, session_type,
            title, target_distance_km, description, completed
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                plan_id,
                session["week_number"],
                session["session_number"],
                session["session_date"],
                session["session_type"],
                session["title"],
                session["target_distance_km"],
                session["description"],
                session.get("completed", 0),
            )
            for session in sessions
        ],
    )
    connection.commit()
    return plan_id


def list_training_plans():
    connection = get_db()
    return connection.execute(
        """
        SELECT p.id, p.start_date, p.weeks, p.rides_per_week, p.goal,
               p.goal_label, p.source_ride_count, p.created_at,
               COUNT(s.id) AS session_count,
               COALESCE(SUM(s.completed), 0) AS completed_count
        FROM training_plans AS p
        LEFT JOIN training_sessions AS s ON s.plan_id = p.id
        GROUP BY p.id
        ORDER BY p.id DESC
        """
    ).fetchall()


def get_training_plan(plan_id):
    connection = get_db()
    return connection.execute(
        """
        SELECT id, start_date, weeks, rides_per_week, goal, goal_label,
               baseline_weekly_km, baseline_longest_km, average_fatigue,
               source_ride_count, data_warning, rationale, created_at
        FROM training_plans
        WHERE id = ?
        """,
        (plan_id,),
    ).fetchone()


def get_training_sessions(plan_id):
    connection = get_db()
    return connection.execute(
        """
        SELECT id, plan_id, week_number, session_number, session_date,
               session_type, title, target_distance_km, description, completed
        FROM training_sessions
        WHERE plan_id = ?
        ORDER BY week_number, session_number
        """,
        (plan_id,),
    ).fetchall()


def get_training_session(session_id, plan_id):
    connection = get_db()
    return connection.execute(
        """
        SELECT id, plan_id, week_number, session_number, session_date,
               session_type, title, target_distance_km, description, completed
        FROM training_sessions
        WHERE id = ? AND plan_id = ?
        """,
        (session_id, plan_id),
    ).fetchone()


def update_training_session(session_id, plan_id, target_distance_km, completed):
    connection = get_db()
    cursor = connection.execute(
        """
        UPDATE training_sessions
        SET target_distance_km = ?, completed = ?
        WHERE id = ? AND plan_id = ?
        """,
        (target_distance_km, int(bool(completed)), session_id, plan_id),
    )
    connection.commit()
    return cursor.rowcount

