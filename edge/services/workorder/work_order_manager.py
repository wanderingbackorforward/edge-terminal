"""
Work Order Manager (T182-T183)
Manages work order lifecycle and synchronization with cloud
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text

from edge.services.workorder.work_order_generator import WorkOrderGenerator
from edge.models.warning_event import WarningEvent

logger = logging.getLogger(__name__)


class WorkOrderManager:
    """
    Manages work order lifecycle on edge device

    Responsibilities:
    - Receives warnings and generates work orders
    - Persists work orders to local SQLite database
    - Tracks work order status updates
    - Queues work orders for cloud synchronization
    - Handles verification tracking

    Implements edge-first autonomous operation:
    - Work orders stored locally when offline
    - Synced to cloud when connectivity available
    - Local status updates maintained
    """

    def __init__(
        self,
        db_session: Session,
        generator_rules: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        """
        Initialize work order manager

        Args:
            db_session: SQLite database session
            generator_rules: Custom work order generation rules
        """
        self.db = db_session
        self.generator = WorkOrderGenerator(db_session, generator_rules)

        # Ensure work_orders table exists
        self._ensure_table()

        logger.info("WorkOrderManager initialized")

    def _ensure_table(self):
        """Ensure work_orders table exists in SQLite"""
        try:
            self.db.execute(text("""
                CREATE TABLE IF NOT EXISTS work_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    work_order_id TEXT UNIQUE NOT NULL,
                    warning_id TEXT,
                    title TEXT NOT NULL,
                    description TEXT,
                    category TEXT NOT NULL,
                    priority TEXT NOT NULL DEFAULT 'medium',
                    ring_number INTEGER,
                    indicator_name TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    verification_required INTEGER DEFAULT 0,
                    verification_ring_count INTEGER DEFAULT 5,
                    created_at REAL NOT NULL,
                    updated_at REAL,
                    synced_to_cloud INTEGER DEFAULT 0,
                    metadata TEXT
                )
            """))
            self.db.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_work_orders_warning ON work_orders(warning_id)"
            ))
            self.db.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_work_orders_status ON work_orders(status)"
            ))
            self.db.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_work_orders_synced ON work_orders(synced_to_cloud)"
            ))
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to ensure work_orders table: {e}")
            self.db.rollback()

    def process_warning(self, warning: WarningEvent) -> Optional[Dict[str, Any]]:
        """
        Process a warning and potentially generate a work order

        Args:
            warning: Warning event to process

        Returns:
            Generated work order dict if created, None otherwise
        """
        # Generate work order if rules match
        work_order = self.generator.generate_from_warning(warning)

        if work_order:
            # Persist to local database
            self._persist_work_order(work_order)

        return work_order

    def process_warnings_batch(
        self,
        warnings: List[WarningEvent],
    ) -> List[Dict[str, Any]]:
        """
        Process multiple warnings and generate work orders

        Args:
            warnings: List of warning events

        Returns:
            List of generated work orders
        """
        work_orders = self.generator.generate_batch(warnings)

        for wo in work_orders:
            self._persist_work_order(wo)

        return work_orders

    def _persist_work_order(self, work_order: Dict[str, Any]) -> bool:
        """Persist work order to local SQLite database"""
        try:
            import json

            self.db.execute(text("""
                INSERT OR REPLACE INTO work_orders (
                    work_order_id, warning_id, title, description,
                    category, priority, ring_number, indicator_name,
                    status, verification_required, verification_ring_count,
                    created_at, updated_at, synced_to_cloud, metadata
                ) VALUES (
                    :work_order_id, :warning_id, :title, :description,
                    :category, :priority, :ring_number, :indicator_name,
                    :status, :verification_required, :verification_ring_count,
                    :created_at, :updated_at, 0, :metadata
                )
            """), {
                "work_order_id": work_order["work_order_id"],
                "warning_id": work_order.get("warning_id"),
                "title": work_order["title"],
                "description": work_order.get("description"),
                "category": work_order["category"],
                "priority": work_order["priority"],
                "ring_number": work_order.get("ring_number"),
                "indicator_name": work_order.get("indicator_name"),
                "status": work_order["status"],
                "verification_required": 1 if work_order.get("verification_required") else 0,
                "verification_ring_count": work_order.get("verification_ring_count", 5),
                "created_at": work_order["created_at"],
                "updated_at": datetime.utcnow().timestamp(),
                "metadata": json.dumps(work_order.get("metadata", {})),
            })
            self.db.commit()

            logger.debug(f"Persisted work order {work_order['work_order_id']}")
            return True

        except Exception as e:
            logger.error(f"Failed to persist work order: {e}", exc_info=True)
            self.db.rollback()
            return False

    def get_pending_sync(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get work orders pending cloud synchronization

        Args:
            limit: Maximum number to return

        Returns:
            List of work order dicts
        """
        try:
            import json

            result = self.db.execute(text("""
                SELECT
                    work_order_id, warning_id, title, description,
                    category, priority, ring_number, indicator_name,
                    status, verification_required, verification_ring_count,
                    created_at, metadata
                FROM work_orders
                WHERE synced_to_cloud = 0
                ORDER BY created_at ASC
                LIMIT :limit
            """), {"limit": limit})

            work_orders = []
            for row in result:
                work_orders.append({
                    "work_order_id": row[0],
                    "warning_id": row[1],
                    "title": row[2],
                    "description": row[3],
                    "category": row[4],
                    "priority": row[5],
                    "ring_number": row[6],
                    "indicator_name": row[7],
                    "status": row[8],
                    "verification_required": bool(row[9]),
                    "verification_ring_count": row[10],
                    "created_at": row[11],
                    "metadata": json.loads(row[12]) if row[12] else {},
                })

            return work_orders

        except Exception as e:
            logger.error(f"Failed to get pending sync work orders: {e}")
            return []

    def mark_synced(self, work_order_ids: List[str]) -> int:
        """
        Mark work orders as synced to cloud

        Args:
            work_order_ids: List of work order IDs to mark

        Returns:
            Number of records updated
        """
        if not work_order_ids:
            return 0

        try:
            # SQLite doesn't support array parameters well, so we use IN clause
            placeholders = ",".join(["?" for _ in work_order_ids])
            query = f"""
                UPDATE work_orders
                SET synced_to_cloud = 1
                WHERE work_order_id IN ({placeholders})
            """

            result = self.db.execute(text(query.replace("?", ":id")), {
                f"id": wo_id for wo_id in work_order_ids
            })

            # Alternative approach for SQLite
            for wo_id in work_order_ids:
                self.db.execute(text("""
                    UPDATE work_orders
                    SET synced_to_cloud = 1
                    WHERE work_order_id = :work_order_id
                """), {"work_order_id": wo_id})

            self.db.commit()

            count = len(work_order_ids)
            logger.info(f"Marked {count} work orders as synced")
            return count

        except Exception as e:
            logger.error(f"Failed to mark work orders as synced: {e}")
            self.db.rollback()
            return 0

    def get_work_order(self, work_order_id: str) -> Optional[Dict[str, Any]]:
        """Get a single work order by ID"""
        try:
            import json

            result = self.db.execute(text("""
                SELECT
                    work_order_id, warning_id, title, description,
                    category, priority, ring_number, indicator_name,
                    status, verification_required, verification_ring_count,
                    created_at, updated_at, synced_to_cloud, metadata
                FROM work_orders
                WHERE work_order_id = :work_order_id
            """), {"work_order_id": work_order_id})

            row = result.fetchone()
            if not row:
                return None

            return {
                "work_order_id": row[0],
                "warning_id": row[1],
                "title": row[2],
                "description": row[3],
                "category": row[4],
                "priority": row[5],
                "ring_number": row[6],
                "indicator_name": row[7],
                "status": row[8],
                "verification_required": bool(row[9]),
                "verification_ring_count": row[10],
                "created_at": row[11],
                "updated_at": row[12],
                "synced_to_cloud": bool(row[13]),
                "metadata": json.loads(row[14]) if row[14] else {},
            }

        except Exception as e:
            logger.error(f"Failed to get work order {work_order_id}: {e}")
            return None

    def list_work_orders(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        List work orders with optional filtering

        Args:
            status: Filter by status
            limit: Maximum records
            offset: Pagination offset

        Returns:
            List of work order dicts
        """
        try:
            import json

            if status:
                result = self.db.execute(text("""
                    SELECT
                        work_order_id, warning_id, title, description,
                        category, priority, ring_number, indicator_name,
                        status, verification_required, verification_ring_count,
                        created_at, updated_at, synced_to_cloud, metadata
                    FROM work_orders
                    WHERE status = :status
                    ORDER BY created_at DESC
                    LIMIT :limit OFFSET :offset
                """), {"status": status, "limit": limit, "offset": offset})
            else:
                result = self.db.execute(text("""
                    SELECT
                        work_order_id, warning_id, title, description,
                        category, priority, ring_number, indicator_name,
                        status, verification_required, verification_ring_count,
                        created_at, updated_at, synced_to_cloud, metadata
                    FROM work_orders
                    ORDER BY created_at DESC
                    LIMIT :limit OFFSET :offset
                """), {"limit": limit, "offset": offset})

            work_orders = []
            for row in result:
                work_orders.append({
                    "work_order_id": row[0],
                    "warning_id": row[1],
                    "title": row[2],
                    "description": row[3],
                    "category": row[4],
                    "priority": row[5],
                    "ring_number": row[6],
                    "indicator_name": row[7],
                    "status": row[8],
                    "verification_required": bool(row[9]),
                    "verification_ring_count": row[10],
                    "created_at": row[11],
                    "updated_at": row[12],
                    "synced_to_cloud": bool(row[13]),
                    "metadata": json.loads(row[14]) if row[14] else {},
                })

            return work_orders

        except Exception as e:
            logger.error(f"Failed to list work orders: {e}")
            return []

    def get_stats(self) -> Dict[str, int]:
        """Get work order statistics"""
        try:
            result = self.db.execute(text("""
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS pending,
                    SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) AS in_progress,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed,
                    SUM(CASE WHEN synced_to_cloud = 0 THEN 1 ELSE 0 END) AS pending_sync
                FROM work_orders
            """))

            row = result.fetchone()
            return {
                "total": row[0] or 0,
                "pending": row[1] or 0,
                "in_progress": row[2] or 0,
                "completed": row[3] or 0,
                "pending_sync": row[4] or 0,
            }

        except Exception as e:
            logger.error(f"Failed to get work order stats: {e}")
            return {}
