"""
Database configuration and connection management.

Single point of access to PostgreSQL for the whole backend: reads credentials
from db.ini (gitignored, never committed) and exposes get_db_connection() /
execute_query() as the shared helpers every service uses instead of managing
psycopg2 connections directly.
"""

import os
import queue
import threading
import configparser
import psycopg2
from psycopg2 import Error
from typing import Optional


class DatabaseConfig:
    """Database configuration loader from db.ini file."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize database configuration.
        
        Args:
            config_path: Path to db.ini file. Defaults to backend/db.ini
        """
        if config_path is None:
            # Get the backend directory path
            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(backend_dir, "db.ini")
        
        self.config_path = config_path
        self.config = configparser.ConfigParser()
        
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Database configuration file not found: {config_path}")
        
        self.config.read(config_path)
        
        if not self.config.has_section("postgresql"):
            raise ValueError("Missing [postgresql] section in db.ini")
    
    def get_connection_params(self) -> dict:
        """
        Get database connection parameters.
        
        Returns:
            Dictionary with database connection parameters
        """
        section = "postgresql"
        return {
            "host": self.config.get(section, "host"),
            "database": self.config.get(section, "database"),
            "user": self.config.get(section, "user"),
            "password": self.config.get(section, "password"),
            "port": self.config.getint(section, "port", fallback=5432)  # standard Postgres port
        }


def get_db_connection():
    """
    Establish and return a brand-new, non-pooled PostgreSQL database
    connection (a fresh psycopg2.connect() call each time).

    Used directly (not through execute_query()) by services/auth_service.py,
    which manages its own connection.commit()/.rollback()/.close() calls
    around each of its methods. Left as a raw connection deliberately - see
    the pooling note on execute_query() below for why.

    Returns:
        psycopg2 connection object

    Raises:
        Exception: If connection fails
    """
    try:
        config = DatabaseConfig()
        params = config.get_connection_params()
        connection = psycopg2.connect(**params)
        return connection
    except Error as e:
        raise Exception(f"Database connection failed: {str(e)}")
    except Exception as e:
        raise Exception(f"Configuration error: {str(e)}")


# --- Connection pool used internally by execute_query() --------------------
#
# Found during a 200-concurrent-user scalability audit: execute_query()
# used to open a brand-new psycopg2 connection (fresh TCP handshake + auth)
# for every single query, across every service that uses it - which is most
# of this app's read traffic (mastery/dashboard, notes, discussion,
# reflection, engagement, learning path stats...). Postgres here is capped
# at 100 connections (`SHOW max_connections`); under real concurrent load,
# connect-per-query either burns most of the time on connection setup
# instead of the query itself, or exhausts that cap outright. A small pool
# of already-open connections fixes both.
#
# get_db_connection() above is left untouched on purpose. It's used
# directly by services/auth_service.py (register/login/profile/password),
# which calls connection.close() itself in its own finally blocks - pooling
# it would mean every one of those close() calls needs to become a
# pool.putconn() instead, a more invasive change to the app's most
# security-sensitive code path for comparatively low-traffic endpoints
# (login/register aren't hit on every page render the way dashboard queries
# are). Pooling is added here, where the volume actually is.
#
# Implemented as a plain queue.Queue of open connections, NOT
# psycopg2.pool.ThreadedConnectionPool - that class keys checked-out
# connections by threading.get_ident(), which is only safe with long-lived
# worker threads. Verified directly (40 concurrent ad-hoc threads hammering
# execute_query()) that ThreadedConnectionPool raises "trying to put
# unkeyed connection" once a thread's numeric ident gets reused after an
# earlier thread exits - a real, reproducible failure, not a theoretical
# one. A queue-based pool has no notion of "which thread" at all, so it
# can't hit that failure mode regardless of how the WSGI server schedules
# request threads.
_POOL_MAXCONN = 20  # well under Postgres's max_connections=100 (SHOW max_connections)
_pool_queue: Optional["queue.Queue"] = None
_pool_size = 0
_pool_lock = threading.Lock()


def _get_connection_from_pool():
    """
    Borrow an open connection: reuse one sitting idle in the queue, open a
    new one if the pool hasn't reached _POOL_MAXCONN yet, or block for one
    to be returned if it has (mirrors a normal bounded connection pool).
    """
    global _pool_queue, _pool_size
    with _pool_lock:
        if _pool_queue is None:
            _pool_queue = queue.Queue(maxsize=_POOL_MAXCONN)

    try:
        return _pool_queue.get_nowait()
    except queue.Empty:
        pass

    with _pool_lock:
        if _pool_size < _POOL_MAXCONN:
            params = DatabaseConfig().get_connection_params()
            connection = psycopg2.connect(**params)
            _pool_size += 1
            return connection

    # Pool is at capacity and nothing idle right now - wait for one to free up.
    return _pool_queue.get()


def _return_connection_to_pool(connection) -> None:
    """Return a connection to the queue, or drop+replace it if it died."""
    global _pool_size
    if connection.closed:
        # Connection is dead (e.g. dropped by the server) - don't recycle
        # it; free its slot so the next borrower opens a fresh one instead.
        with _pool_lock:
            _pool_size -= 1
        return
    _pool_queue.put(connection)


def execute_query(query: str, params: tuple = None, fetch: bool = False):
    """
    Execute a database query with proper error handling.

    Args:
        query: SQL query string
        params: Query parameters tuple (for parameterized queries to prevent SQL injection)
        fetch: If True, returns results; if False, commits transaction

    Returns:
        Query results if fetch=True, else None

    Raises:
        Exception: If query execution fails
    """
    # Pooled: borrows a connection from the pool instead of opening a new
    # one, and returns it to the pool in `finally` instead of closing it.
    # A rollback() before returning a connection that hit an error keeps it
    # in a clean state for whichever caller borrows it next.
    connection = None
    try:
        connection = _get_connection_from_pool()
        cursor = connection.cursor()

        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)

        if fetch:
            result = cursor.fetchall()
            cursor.close()
            return result
        else:
            connection.commit()
            cursor.close()
            return None

    except Error as e:
        if connection:
            connection.rollback()
        raise Exception(f"Query execution failed: {str(e)}")
    finally:
        if connection:
            _return_connection_to_pool(connection)
