"""PostgreSQL connection pool."""
from contextlib import contextmanager
import psycopg2
import psycopg2.pool
import psycopg2.extras
from . import config

_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def init_pool(min_conn: int = 2, max_conn: int = 10):
    """Create the connection pool. Call once at startup."""
    global _pool
    if _pool is not None:
        return
    _pool = psycopg2.pool.ThreadedConnectionPool(
        min_conn,
        max_conn,
        host=config.DB_HOST,
        port=config.DB_PORT,
        database=config.DB_NAME,
        user=config.DB_USER,
        password=config.DB_PASSWORD or None,
    )


def close_pool():
    """Close all connections. Call at shutdown."""
    global _pool
    if _pool:
        _pool.closeall()
        _pool = None


@contextmanager
def db_cursor():
    if _pool is None:
        init_pool()
    assert _pool is not None, "Connection pool failed to initialize"
    conn = _pool.getconn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        _pool.putconn(conn)
