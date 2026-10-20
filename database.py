"""database.py — SQLAlchemy PostgreSQL engine & read-only execution helper."""

import os
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://poc_readonly_user:readonly_pass@localhost:5432/invoice_poc",
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    connect_args={"connect_timeout": 5},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def execute_readonly_query(sql: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Execute a validated SQL query in a read-only transaction with timeout.

    Enforces read-only status and a 3-second statement timeout.
    Returns rows as list of dicts with Decimal values formatted as fixed 2-decimal
    strings and dates/datetimes formatted as ISO-8601 strings.
    """
    if parameters is None:
        parameters = {}

    with engine.connect() as conn:
        with conn.begin():
            # Enforce read-only and statement timeout at transaction level
            conn.execute(text("SET TRANSACTION READ ONLY"))
            conn.execute(text("SET LOCAL statement_timeout = '3000ms'"))

            result = conn.execute(text(sql), parameters)
            columns = list(result.keys())
            rows: list[dict[str, Any]] = []

            for row in result.fetchall():
                row_dict: dict[str, Any] = {}
                for col, val in zip(columns, row):
                    if isinstance(val, Decimal):
                        row_dict[col] = f"{val:.2f}"
                    elif isinstance(val, (date, datetime)):
                        row_dict[col] = val.isoformat()
                    else:
                        row_dict[col] = val
                rows.append(row_dict)

            return rows


def check_db_connection() -> bool:
    """Ping the database. Returns True if connected, False otherwise."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
