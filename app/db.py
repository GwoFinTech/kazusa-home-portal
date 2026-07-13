"""PostgreSQL connection pool + migration runner."""
from contextlib import contextmanager
import logging
import os
import psycopg2
import psycopg2.pool
import psycopg2.extras
from . import config

_pool: psycopg2.pool.ThreadedConnectionPool | None = None
logger = logging.getLogger(__name__)

MIGRATIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "migrations")


def _ensure_migrations_table(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS home_migrations (
                id         SERIAL PRIMARY KEY,
                filename   TEXT UNIQUE NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
    conn.commit()


# Existing deployments that pre-date the migration runner should set this to the
# last migration that was already applied manually. New migrations after this
# will be executed normally.
BASELINE_MIGRATION = "002_api_tokens.sql"


def _baseline_if_needed(conn):
    """If home_migrations is empty but core tables already exist (manual setup),
    record migrations up to BASELINE_MIGRATION as already applied."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT 1 FROM home_migrations LIMIT 1")
        if cur.fetchone():
            return
        cur.execute("SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'home_users' LIMIT 1")
        if not cur.fetchone():
            return  # fresh DB, run migrations normally

    # Existing DB: mark baseline migrations as applied
    files = sorted(f for f in os.listdir(MIGRATIONS_DIR) if f.endswith(".sql"))
    baseline_files = [f for f in files if f <= BASELINE_MIGRATION]
    with conn.cursor() as cur:
        for filename in baseline_files:
            cur.execute(
                "INSERT INTO home_migrations (filename, applied_at) VALUES (%s, now()) ON CONFLICT (filename) DO NOTHING",
                (filename,),
            )
    conn.commit()
    logger.info("Baselined %d existing migrations", len(baseline_files))


def run_migrations():
    """Apply pending SQL migrations in app/migrations sorted by filename."""
    if not os.path.isdir(MIGRATIONS_DIR):
        return

    # Use a standalone connection for migrations (pool may not be ready)
    conn = psycopg2.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        database=config.DB_NAME,
        user=config.DB_USER,
        password=config.DB_PASSWORD or None,
    )
    try:
        _ensure_migrations_table(conn)
        _baseline_if_needed(conn)

        files = sorted(f for f in os.listdir(MIGRATIONS_DIR) if f.endswith(".sql"))
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT filename FROM home_migrations")
            applied = {row["filename"] for row in cur.fetchall()}

        for filename in files:
            if filename in applied:
                continue
            path = os.path.join(MIGRATIONS_DIR, filename)
            with open(path, "r", encoding="utf-8") as f:
                sql = f.read()
            with conn.cursor() as cur:
                logger.info("Applying migration: %s", filename)
                cur.execute(sql)
                cur.execute(
                    "INSERT INTO home_migrations (filename) VALUES (%s)",
                    (filename,),
                )
            conn.commit()
            logger.info("Migration applied: %s", filename)
    finally:
        conn.close()


def init_pool(min_conn: int = 2, max_conn: int = 10):
    """Create the connection pool and run pending migrations. Call once at startup."""
    global _pool
    if _pool is not None:
        return

    # Run migrations before creating the pool
    run_migrations()

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
    cur = None
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if cur is not None:
            cur.close()
        _pool.putconn(conn)
