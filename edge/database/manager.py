"""
T055: Database Manager Utility
Manages SQLite connection, transaction handling, and WAL mode enforcement
"""
import sqlite3
import logging
from typing import Any, Dict, List, Optional, Tuple
from contextlib import contextmanager
from pathlib import Path

# SQLAlchemy for ORM usage (warning system, models)
try:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker, Session as SASession
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    SASession = None

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    SQLite database manager with connection pooling and WAL mode enforcement.

    Ensures:
    - Write-Ahead Logging (WAL) mode for concurrent readers/writers
    - Proper transaction management
    - Connection safety with context managers
    - Query result handling with row_factory
    """

    def __init__(self, db_path: str = "data/edge.db"):
        """
        Initialize database manager.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._ensure_database_exists()
        self._connection: Optional[sqlite3.Connection] = None

        # SQLAlchemy support for ORM usage
        self._engine = None
        self._SessionLocal = None

    def _ensure_database_exists(self) -> None:
        """Create database directory if it doesn't exist"""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        """
        Establish database connection with proper configuration.

        Returns:
            SQLite connection with WAL mode and row_factory
        """
        if self._connection is None:
            self._connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,  # Allow multi-threaded access
                timeout=30.0  # 30 second timeout for locks
            )

            # Configure row_factory for dict-like access
            self._connection.row_factory = sqlite3.Row

            # Enable WAL mode for better concurrency
            self._connection.execute("PRAGMA journal_mode=WAL")

            # Set synchronous mode to NORMAL for performance
            self._connection.execute("PRAGMA synchronous=NORMAL")

            # Increase cache size to 10MB
            self._connection.execute("PRAGMA cache_size=-10000")

            # Enable foreign keys
            self._connection.execute("PRAGMA foreign_keys=ON")

            logger.info(f"Database connected: {self.db_path} (WAL mode enabled)")

        return self._connection

    @contextmanager
    def get_connection(self):
        """
        Provide a context manager compatible connection handle.

        Returns:
            SQLite connection usable within a `with` block.
        """
        conn = self.connect()
        try:
            yield conn
        finally:
            # Connection is kept open for pooling; do not close here.
            pass

    def close(self) -> None:
        """Close database connection and SQLAlchemy engine"""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.info("Database connection closed")

        if self._engine:
            self._engine.dispose()
            self._engine = None
            self._SessionLocal = None
            logger.info("SQLAlchemy engine disposed")

    def _get_sqlalchemy_engine(self):
        """
        Get or create SQLAlchemy engine for ORM usage

        Returns:
            SQLAlchemy Engine instance
        """
        if not SQLALCHEMY_AVAILABLE:
            raise ImportError(
                "SQLAlchemy is not available. Install with: pip install sqlalchemy"
            )

        if self._engine is None:
            self._engine = create_engine(
                f"sqlite:///{self.db_path}",
                connect_args={"check_same_thread": False},
                echo=False,  # Set to True for SQL logging
            )
            self._SessionLocal = sessionmaker(
                bind=self._engine,
                autocommit=False,
                autoflush=False
            )
            logger.info(f"SQLAlchemy engine created: {self.db_path}")

        return self._engine

    @contextmanager
    def get_session(self):
        """
        Provide SQLAlchemy ORM session for model operations

        Usage:
            from edge.database.manager import DatabaseManager
            from edge.services.warning.warning_engine import WarningEngine

            db = DatabaseManager("data/edge.db")
            with db.get_session() as session:
                engine = WarningEngine(session)
                warnings = engine.evaluate_ring(ring_number, indicators)

        Yields:
            SQLAlchemy Session instance

        The session automatically commits on success and rolls back on exception.
        """
        if not SQLALCHEMY_AVAILABLE:
            raise ImportError(
                "SQLAlchemy is not available. Install with: pip install sqlalchemy"
            )

        # Ensure engine is created
        if self._SessionLocal is None:
            self._get_sqlalchemy_engine()

        session = self._SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @contextmanager
    def transaction(self):
        """
        Context manager for transaction handling.

        Usage:
            with db.transaction():
                db.execute("INSERT ...")
                db.execute("UPDATE ...")
            # Automatically commits on success, rolls back on exception
        """
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Transaction rolled back: {e}")
            raise

    def execute(
        self,
        query: str,
        params: Optional[Tuple] = None
    ) -> sqlite3.Cursor:
        """
        Execute a SQL query (INSERT, UPDATE, DELETE).

        Args:
            query: SQL query string
            params: Query parameters (optional)

        Returns:
            SQLite cursor
        """
        conn = self.connect()
        cursor = conn.cursor()

        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor
        except sqlite3.Error as e:
            logger.error(f"Query execution failed: {e}\nQuery: {query}\nParams: {params}")
            raise

    def query(
        self,
        query: str,
        params: Optional[Tuple] = None
    ) -> sqlite3.Cursor:
        """
        Execute a SELECT query.

        Args:
            query: SQL query string
            params: Query parameters (optional)

        Returns:
            SQLite cursor with results
        """
        return self.execute(query, params)

    def fetchone(self, query: str, params: Optional[Tuple] = None) -> Optional[sqlite3.Row]:
        """
        Execute query and fetch one result.

        Args:
            query: SQL query string
            params: Query parameters (optional)

        Returns:
            Single row as dict-like Row object, or None
        """
        cursor = self.query(query, params)
        return cursor.fetchone()

    def fetchall(self, query: str, params: Optional[Tuple] = None) -> List[sqlite3.Row]:
        """
        Execute query and fetch all results.

        Args:
            query: SQL query string
            params: Query parameters (optional)

        Returns:
            List of rows as dict-like Row objects
        """
        cursor = self.query(query, params)
        return cursor.fetchall()

    def commit(self) -> None:
        """Commit current transaction"""
        if self._connection:
            self._connection.commit()

    def rollback(self) -> None:
        """Rollback current transaction"""
        if self._connection:
            self._connection.rollback()

    def execute_many(
        self,
        query: str,
        params_list: List[Tuple]
    ) -> sqlite3.Cursor:
        """
        Execute query with multiple parameter sets (batch insert/update).

        Args:
            query: SQL query string with placeholders
            params_list: List of parameter tuples

        Returns:
            SQLite cursor
        """
        conn = self.connect()
        cursor = conn.cursor()

        try:
            cursor.executemany(query, params_list)
            return cursor
        except sqlite3.Error as e:
            logger.error(f"Batch execution failed: {e}\nQuery: {query}")
            raise

    def run_migration(self, migration_file: str) -> None:
        """
        Run a SQL migration file.

        Args:
            migration_file: Path to .sql migration file
        """
        with open(migration_file, 'r') as f:
            sql_script = f.read()

        conn = self.connect()
        try:
            conn.executescript(sql_script)
            conn.commit()
            logger.info(f"Migration applied: {migration_file}")
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Migration failed: {migration_file} - {e}")
            raise

    def get_table_info(self, table_name: str) -> List[Tuple]:
        """
        Get table schema information.

        Args:
            table_name: Name of table

        Returns:
            List of column information tuples
        """
        cursor = self.query(f"PRAGMA table_info({table_name})")
        return cursor.fetchall()

    def get_table_names(self) -> List[str]:
        """
        Get all table names in database.

        Returns:
            List of table names
        """
        cursor = self.query(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        return [row['name'] for row in cursor.fetchall()]

    def vacuum(self) -> None:
        """Run VACUUM to reclaim space and optimize database"""
        conn = self.connect()
        conn.execute("VACUUM")
        logger.info("Database vacuumed")

    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
