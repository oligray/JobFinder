import sqlite3
from datetime import datetime, timezone


def get_connection(db_path: str = "jobs.db") -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: str = "jobs.db") -> None:
    conn = get_connection(db_path)
    conn.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                url          TEXT NOT NULL UNIQUE,
                title        TEXT,
                company      TEXT,
                location     TEXT,
                description  TEXT,
                posted_date  TEXT,
                first_seen   TEXT NOT NULL,
                status       TEXT NOT NULL DEFAULT 'new'
                                 CHECK(status IN ('new','saved','applied','rejected','interviewing','declined')),
                notes        TEXT,
                snapshot_at  TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
            CREATE INDEX IF NOT EXISTS idx_jobs_posted ON jobs(posted_date DESC);

            CREATE TABLE IF NOT EXISTS search_runs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                run_at      TEXT NOT NULL,
                jobs_found  INTEGER,
                jobs_new    INTEGER
            );
        """)
    conn.close()


def upsert_job(conn: sqlite3.Connection, url: str, title: str | None,
               company: str | None, location: str | None,
               description: str | None, posted_date: str | None) -> tuple[int, bool]:
    existing = conn.execute("SELECT id FROM jobs WHERE url = ?", (url,)).fetchone()
    if existing is None:
        now = datetime.now(timezone.utc).isoformat()
        cursor = conn.execute(
            "INSERT INTO jobs (url, title, company, location, description, posted_date, first_seen) VALUES (?,?,?,?,?,?,?)",
            (url, title, company, location, description, posted_date, now)
        )
        conn.commit()
        return cursor.lastrowid, True
    conn.execute(
        """UPDATE jobs SET
               title       = COALESCE(title,       ?),
               company     = COALESCE(company,     ?),
               location    = COALESCE(location,    ?),
               description = COALESCE(description, ?),
               posted_date = COALESCE(posted_date, ?)
           WHERE url = ?""",
        (title, company, location, description, posted_date, url)
    )
    conn.commit()
    return existing["id"], False


def get_jobs(conn: sqlite3.Connection, statuses: list[str] | None = None,
             order_by: str = "CASE WHEN posted_date IS NULL THEN 1 ELSE 0 END, posted_date DESC, first_seen DESC") -> list[sqlite3.Row]:
    if statuses:
        placeholders = ",".join("?" * len(statuses))
        return conn.execute(
            f"SELECT * FROM jobs WHERE status IN ({placeholders}) ORDER BY {order_by}",
            statuses
        ).fetchall()
    return conn.execute(f"SELECT * FROM jobs ORDER BY {order_by}").fetchall()


def get_job(conn: sqlite3.Connection, job_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()


def update_job_status(conn: sqlite3.Connection, job_id: int, status: str) -> None:
    conn.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job_id))
    conn.commit()


def update_job_notes(conn: sqlite3.Connection, job_id: int, notes: str) -> None:
    conn.execute("UPDATE jobs SET notes = ? WHERE id = ?", (notes, job_id))
    conn.commit()


def update_job_snapshot(conn: sqlite3.Connection, job_id: int, snapshot_at: str) -> None:
    conn.execute("UPDATE jobs SET snapshot_at = ? WHERE id = ?", (snapshot_at, job_id))
    conn.commit()


def migrate_db(db_path: str = "jobs.db") -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")

    def _schema() -> str | None:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='jobs'"
        ).fetchone()
        return row[0] if row else None

    schema = _schema()
    if not schema:
        conn.close()
        return

    # Phase 1: rejected → declined
    if "'declined'" not in schema:
        conn.executescript("""
            PRAGMA foreign_keys=OFF;
            CREATE TABLE jobs_new (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                url          TEXT NOT NULL UNIQUE,
                title        TEXT,
                company      TEXT,
                location     TEXT,
                description  TEXT,
                posted_date  TEXT,
                first_seen   TEXT NOT NULL,
                status       TEXT NOT NULL DEFAULT 'new'
                                 CHECK(status IN ('new','saved','applied','rejected','interviewing','declined')),
                notes        TEXT
            );
            INSERT INTO jobs_new SELECT id, url, title, company, location, description,
                posted_date, first_seen,
                CASE WHEN status = 'rejected' THEN 'declined' ELSE status END,
                notes FROM jobs;
            DROP TABLE jobs;
            ALTER TABLE jobs_new RENAME TO jobs;
            CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
            CREATE INDEX IF NOT EXISTS idx_jobs_posted ON jobs(posted_date DESC);
            PRAGMA foreign_keys=ON;
        """)
        schema = _schema()

    # Phase 2: add snapshot_at column
    if schema and "snapshot_at" not in schema:
        conn.executescript("""
            PRAGMA foreign_keys=OFF;
            CREATE TABLE jobs_new (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                url          TEXT NOT NULL UNIQUE,
                title        TEXT,
                company      TEXT,
                location     TEXT,
                description  TEXT,
                posted_date  TEXT,
                first_seen   TEXT NOT NULL,
                status       TEXT NOT NULL DEFAULT 'new'
                                 CHECK(status IN ('new','saved','applied','rejected','interviewing','declined')),
                notes        TEXT,
                snapshot_at  TEXT
            );
            INSERT INTO jobs_new
                SELECT id, url, title, company, location, description,
                       posted_date, first_seen, status, notes, NULL
                FROM jobs;
            DROP TABLE jobs;
            ALTER TABLE jobs_new RENAME TO jobs;
            CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
            CREATE INDEX IF NOT EXISTS idx_jobs_posted ON jobs(posted_date DESC);
            PRAGMA foreign_keys=ON;
        """)

    conn.close()


def get_jobs_for_pattern_analysis(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, title, company, status FROM jobs WHERE status IN ('saved', 'declined', 'applied')"
    ).fetchall()


def record_search_run(conn: sqlite3.Connection, jobs_found: int, jobs_new: int) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO search_runs (run_at, jobs_found, jobs_new) VALUES (?, ?, ?)",
        (now, jobs_found, jobs_new)
    )
    conn.commit()
