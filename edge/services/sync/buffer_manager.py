"""
Store-and-Forward Buffer Manager
Manages queue of unsync

ed data for cloud upload
Persists to database for durability across restarts
"""
import asyncio
import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class BufferManager:
    """
    Manages store-and-forward buffer for cloud sync.
    
    Features:
    - Queue unsynced ring summaries, predictions, warnings
    - Persist to database for durability
    - Priority-based retrieval (oldest first)
    - Automatic retry management
    - Disk space monitoring
    """

    def __init__(
        self,
        db_manager,
        max_buffer_size: int = 10000,
        max_retry_attempts: int = 3
    ):
        """
        Initialize buffer manager.

        Args:
            db_manager: DatabaseManager instance
            max_buffer_size: Maximum items in buffer before dropping old items
            max_retry_attempts: Maximum retry attempts before giving up
        """
        self.db_manager = db_manager
        self.max_buffer_size = max_buffer_size
        self.max_retry_attempts = max_retry_attempts

        # Statistics
        self._stats = {
            'items_added': 0,
            'items_removed': 0,
            'items_dropped': 0,
            'sync_attempts': 0,
            'sync_successes': 0,
            'sync_failures': 0
        }

    async def initialize(self) -> None:
        """Initialize buffer (create tables if needed)"""
        with self.db_manager.transaction() as conn:
            # Create sync_buffer table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sync_buffer (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_type VARCHAR(50) NOT NULL,  -- ring_summary, prediction, warning
                    item_id INTEGER NOT NULL,  -- ID in source table
                    payload TEXT NOT NULL,  -- JSON payload
                    priority INTEGER DEFAULT 0,  -- Higher = more urgent
                    retry_count INTEGER DEFAULT 0,
                    last_attempt_at REAL,
                    created_at REAL DEFAULT (julianday('now')),
                    metadata TEXT  -- Additional JSON metadata
                )
            """)

            # Index for retrieval order
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sync_buffer_priority_created 
                ON sync_buffer(priority DESC, created_at ASC)
            """)

            # Index for item lookup
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sync_buffer_item 
                ON sync_buffer(item_type, item_id)
            """)

        logger.info("Buffer manager initialized")

    async def add_item(
        self,
        item_type: str,
        item_id: int,
        payload: Dict[str, Any],
        priority: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Add item to sync buffer.

        Args:
            item_type: Type of item (ring_summary, prediction, warning)
            item_id: ID of item in source table
            payload: JSON-serializable data to sync
            priority: Priority level (higher = more urgent)
            metadata: Additional metadata

        Returns:
            True if added successfully
        """
        try:
            # Check if already in buffer
            with self.db_manager.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT id FROM sync_buffer 
                    WHERE item_type = ? AND item_id = ?
                    """,
                    (item_type, item_id)
                )
                existing = cursor.fetchone()

            if existing:
                logger.debug(f"Item {item_type}:{item_id} already in buffer")
                return False

            # Check buffer size and purge if needed
            await self._enforce_buffer_limit()

            # Add to buffer
            with self.db_manager.transaction() as conn:
                conn.execute(
                    """
                    INSERT INTO sync_buffer 
                    (item_type, item_id, payload, priority, metadata)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        item_type,
                        item_id,
                        json.dumps(payload),
                        priority,
                        json.dumps(metadata) if metadata else None
                    )
                )

            self._stats['items_added'] += 1
            logger.debug(f"Added to buffer: {item_type}:{item_id} (priority {priority})")
            return True

        except Exception as e:
            logger.error(f"Error adding item to buffer: {e}", exc_info=True)
            return False

    async def get_batch(
        self,
        batch_size: int = 100,
        item_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get batch of items for syncing (highest priority first, then oldest).

        Args:
            batch_size: Maximum items to retrieve
            item_type: Filter by item type (optional)

        Returns:
            List of buffer items with id, type, payload, etc.
        """
        try:
            with self.db_manager.get_connection() as conn:
                if item_type:
                    cursor = conn.execute(
                        """
                        SELECT * FROM sync_buffer 
                        WHERE item_type = ? AND retry_count < ?
                        ORDER BY priority DESC, created_at ASC
                        LIMIT ?
                        """,
                        (item_type, self.max_retry_attempts, batch_size)
                    )
                else:
                    cursor = conn.execute(
                        """
                        SELECT * FROM sync_buffer 
                        WHERE retry_count < ?
                        ORDER BY priority DESC, created_at ASC
                        LIMIT ?
                        """,
                        (self.max_retry_attempts, batch_size)
                    )

                rows = cursor.fetchall()

            items = []
            for row in rows:
                items.append({
                    'id': row['id'],
                    'item_type': row['item_type'],
                    'item_id': row['item_id'],
                    'payload': json.loads(row['payload']),
                    'priority': row['priority'],
                    'retry_count': row['retry_count'],
                    'last_attempt_at': row['last_attempt_at'],
                    'created_at': row['created_at'],
                    'metadata': json.loads(row['metadata']) if row['metadata'] else None
                })

            return items

        except Exception as e:
            logger.error(f"Error getting batch: {e}", exc_info=True)
            return []

    async def mark_synced(self, buffer_id: int) -> bool:
        """
        Remove successfully synced item from buffer.

        Args:
            buffer_id: ID in sync_buffer table

        Returns:
            True if removed successfully
        """
        try:
            with self.db_manager.transaction() as conn:
                conn.execute(
                    "DELETE FROM sync_buffer WHERE id = ?",
                    (buffer_id,)
                )

            self._stats['items_removed'] += 1
            self._stats['sync_successes'] += 1
            return True

        except Exception as e:
            logger.error(f"Error marking synced: {e}", exc_info=True)
            return False

    async def mark_failed(self, buffer_id: int) -> bool:
        """
        Mark sync attempt failed (increment retry count).

        Args:
            buffer_id: ID in sync_buffer table

        Returns:
            True if updated successfully
        """
        try:
            now = datetime.now().timestamp()

            with self.db_manager.transaction() as conn:
                conn.execute(
                    """
                    UPDATE sync_buffer 
                    SET retry_count = retry_count + 1,
                        last_attempt_at = ?
                    WHERE id = ?
                    """,
                    (now, buffer_id)
                )

                # Check if max retries reached
                cursor = conn.execute(
                    "SELECT retry_count FROM sync_buffer WHERE id = ?",
                    (buffer_id,)
                )
                row = cursor.fetchone()

                if row and row['retry_count'] >= self.max_retry_attempts:
                    # Remove from buffer after max retries
                    conn.execute("DELETE FROM sync_buffer WHERE id = ?", (buffer_id,))
                    logger.warning(f"Item {buffer_id} removed after {self.max_retry_attempts} failed attempts")
                    self._stats['sync_failures'] += 1

            self._stats['sync_attempts'] += 1
            return True

        except Exception as e:
            logger.error(f"Error marking failed: {e}", exc_info=True)
            return False

    async def get_buffer_size(self) -> int:
        """Get current buffer size (number of items)"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) as count FROM sync_buffer")
                result = cursor.fetchone()
                return result['count'] if result else 0

        except Exception as e:
            logger.error(f"Error getting buffer size: {e}", exc_info=True)
            return 0

    async def get_buffer_size_by_type(self) -> Dict[str, int]:
        """Get buffer size grouped by item type"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT item_type, COUNT(*) as count 
                    FROM sync_buffer 
                    GROUP BY item_type
                """)
                rows = cursor.fetchall()

            return {row['item_type']: row['count'] for row in rows}

        except Exception as e:
            logger.error(f"Error getting buffer size by type: {e}", exc_info=True)
            return {}

    async def _enforce_buffer_limit(self) -> None:
        """Remove oldest items if buffer exceeds limit"""
        try:
            current_size = await self.get_buffer_size()

            if current_size >= self.max_buffer_size:
                # Remove oldest items (lowest priority, oldest created_at)
                items_to_remove = current_size - self.max_buffer_size + 100

                with self.db_manager.transaction() as conn:
                    conn.execute(
                        """
                        DELETE FROM sync_buffer 
                        WHERE id IN (
                            SELECT id FROM sync_buffer 
                            ORDER BY priority ASC, created_at ASC 
                            LIMIT ?
                        )
                        """,
                        (items_to_remove,)
                    )

                self._stats['items_dropped'] += items_to_remove
                logger.warning(f"Buffer full: dropped {items_to_remove} oldest items")

        except Exception as e:
            logger.error(f"Error enforcing buffer limit: {e}", exc_info=True)

    async def clear_buffer(self, item_type: Optional[str] = None) -> int:
        """
        Clear buffer (remove all items or specific type).

        Args:
            item_type: Clear only this type (optional)

        Returns:
            Number of items removed
        """
        try:
            with self.db_manager.transaction() as conn:
                if item_type:
                    cursor = conn.execute(
                        "DELETE FROM sync_buffer WHERE item_type = ?",
                        (item_type,)
                    )
                else:
                    cursor = conn.execute("DELETE FROM sync_buffer")

                removed = cursor.rowcount

            logger.info(f"Cleared {removed} items from buffer")
            return removed

        except Exception as e:
            logger.error(f"Error clearing buffer: {e}", exc_info=True)
            return 0

    def get_statistics(self) -> Dict[str, Any]:
        """Get buffer statistics"""
        return dict(self._stats)

    def reset_statistics(self) -> None:
        """Reset statistics counters"""
        self._stats = {
            'items_added': 0,
            'items_removed': 0,
            'items_dropped': 0,
            'sync_attempts': 0,
            'sync_successes': 0,
            'sync_failures': 0
        }
