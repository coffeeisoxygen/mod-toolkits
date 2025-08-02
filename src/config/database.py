"""Database connection helpers for Streamlit app.

Wrapper ini bertujuan untuk standarisasi akses database (read/write) dengan error handling dan auto-reset.
Jika butuh fitur advanced, gunakan get_db_conn() langsung.

Usage:
    from config.database import read_query, write_query, test_connection, get_db_conn
    # Fetch data (SELECT)
    df = read_query("SELECT * FROM users WHERE status = :status", params={"status": "active"})
    # Write data (INSERT/UPDATE/DELETE)
    write_query("UPDATE users SET status = :s WHERE id = :id", params={"s": "inactive", "id": 1})
    # Test connection
    if not test_connection():
        st.error("DB not connected!")
    # Advanced: akses SQLAlchemy/Streamlit connection langsung
    conn = get_db_conn()
    df = conn.query("SELECT ...")
"""

from typing import Any

import pandas as pd
import streamlit as st
from sqlalchemy import text
from streamlit.connections.sql_connection import SQLConnection

from utils.mlogger import logger

# Global logger with module context
db_logger = logger.bind(module="database")


def get_db_conn(name: str = "mssql") -> SQLConnection:
    """Get a Streamlit SQLConnection by name.

    Args:
        name (str): Connection name (default: "mssql").

    Returns:
        SQLConnection: Streamlit SQLConnection object.

    Usage:
        conn = get_db_conn()
        df = conn.query("SELECT ...")
    """
    return st.connection(name, type="sql")


def read_query(
    sql: str,
    params: dict[str, Any] | None = None,
    ttl: int | None = None,
    name: str = "mssql",
    req_id: str | None = None,
) -> pd.DataFrame:
    """Run a read-only query (SELECT) with auto-reset if connection is not healthy.

    Args:
        sql (str): SQL SELECT query.
        params (dict | None): Query parameters.
        ttl (int | None): Cache TTL in seconds.
        name (str): Connection name.
        req_id (str | None): Optional request id for log context.

    Returns:
        pd.DataFrame: Query result.

    Usage:
        df = read_query("SELECT * FROM users WHERE id = :id", params={"id": 1}, req_id="abc-123")
    """
    log = db_logger if req_id is None else db_logger.bind(request_id=req_id)
    conn = get_db_conn(name)
    try:
        log.debug(f"Executing query: {sql} with params: {params}")
        return conn.query(sql, params=params, ttl=ttl)
    except Exception as e:
        log.warning(f"Query failed, resetting connection: {e}")
        conn.reset()
        return conn.query(sql, params=params, ttl=ttl)


def write_query(
    sql: str,
    params: dict[str, Any] | None = None,
    name: str = "mssql",
    req_id: str | None = None,
) -> None:
    """Run a write (INSERT/UPDATE/DELETE) query with auto-reset if needed.

    Args:
        sql (str): SQL write query.
        params (dict | None): Query parameters.
        name (str): Connection name.
        req_id (str | None): Optional request id for log context.

    Usage:
        write_query("UPDATE users SET status = :s WHERE id = :id", params={"s": "active", "id": 1}, req_id="abc-123")
    """
    log = db_logger if req_id is None else db_logger.bind(request_id=req_id)
    conn = get_db_conn(name)
    try:
        with conn.session as session:
            log.debug(f"Executing write query: {sql} with params: {params}")
            session.execute(text(sql), params)
            session.commit()
    except Exception as e:
        log.warning(f"Write failed, resetting connection: {e}")
        conn.reset()
        with conn.session as session:
            session.execute(text(sql), params)
            session.commit()


def test_connection(name: str = "mssql", req_id: str | None = None) -> bool:
    """Test if the database connection is healthy.

    Args:
        name (str): Connection name.
        req_id (str | None): Optional request id for log context.

    Returns:
        bool: True if connection is healthy, False otherwise.

    Usage:
        if not test_connection():
            st.error("Database not connected!")
    """
    log = db_logger if req_id is None else db_logger.bind(request_id=req_id)
    conn = get_db_conn(name)
    try:
        log.debug("Testing database connection...")
        conn.query(sql="SELECT @@VERSION;")
    except Exception as e:
        log.warning(f"Connection test failed: {e}")
        return False
    else:
        return True
