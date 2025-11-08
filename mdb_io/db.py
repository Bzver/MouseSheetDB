import sqlite3
import os
import logging
import traceback
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Union

class MouseDB:
    def __init__(self, db_path: Optional[str] = None):
        self.path = None
        self.conn = None
        self._schema_file = "schema.sql"
        self._export_pending_file = "export_pending.sql"
        
        if db_path:
            self.set_db_path(db_path)

    def set_db_path(self, db_path: str):
        """Set database path and (re)connect."""
        self.path = Path(db_path).resolve()
        try:
            self._reload_db()
            logging.info(f"Database connected: {self.path}")
        except Exception as e:
            logging.error(f"Failed to connect to DB {self.path}: {e}")
            logging.debug(traceback.format_exc())
            raise

    def _reload_db(self):
        """Initialize or reload database connection and ensure schema."""
        if self.conn:
            self.conn.close()

        # Ensure DB directory exists
        self.path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row  # Enable column access by name
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")

        # Apply schema
        self._apply_schema()

    def _apply_schema(self):
        """Load and execute schema.sql if exists."""
        schema_path = Path(__file__).parent / self._schema_file
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")

        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()

        try:
            with self.conn:  # Auto-commits or rolls back
                self.conn.executescript(schema_sql)
            logging.debug("Schema applied successfully.")
        except sqlite3.Error as e:
            logging.error(f"Schema application failed: {e}")
            raise

    @contextmanager
    def _get_cursor(self):
        """Context manager for safe cursor usage."""
        if not self.conn:
            raise RuntimeError("Database not initialized. Call set_db_path() first.")
        try:
            cur = self.conn.cursor()
            yield cur
        except Exception:
            self.conn.rollback()
            raise
        else:
            self.conn.commit()

    def get_mouse(self, mouse_id: str) -> Optional[Dict[str, Any]]:
        """Get mouse by ID."""
        with self._get_cursor() as cur:
            cur.execute("SELECT * FROM mice WHERE id = ?", (mouse_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def add_mouse(self, mouse_data: Dict[str, Any]) -> str:
        """Insert new mouse. Returns inserted ID."""
        columns = [k for k in mouse_data.keys() if k != 'id']
        placeholders = ", ".join(["?"] * len(columns))
        cols = ", ".join(columns)
        
        sql = f"INSERT INTO mice (id, {cols}) VALUES (?, {placeholders})"
        values = [mouse_data['id']] + [mouse_data.get(c) for c in columns]

        with self._get_cursor() as cur:
            cur.execute(sql, values)
            return mouse_data['id']

    def update_mouse(self, mouse_id: str, updates: Dict[str, Any]):
        """Update mouse fields."""
        if not updates:
            return
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        sql = f"UPDATE mice SET {set_clause} WHERE id = ?"
        values = list(updates.values()) + [mouse_id]
        with self._get_cursor() as cur:
            cur.execute(sql, values)

    def get_pending_actions(self, only_unexecuted: bool = True) -> List[Dict[str, Any]]:
        """Get pending actions (default: only unexecuted)."""
        sql = "SELECT * FROM pending_actions"
        if only_unexecuted:
            sql += " WHERE executed_at IS NULL"
        sql += " ORDER BY planned_at, mouse_id"

        with self._get_cursor() as cur:
            cur.execute(sql)
            return [dict(row) for row in cur.fetchall()]

    def add_pending_action(
        self,
        action_type: str,
        mouse_id: str,
        new_cage_id: Optional[str] = None,
        old_cage_id: Optional[str] = None,
        details: Optional[str] = None
    ) -> int:
        """Add a pending action. Returns action_id."""
        sql = """
        INSERT INTO pending_actions 
        (action_type, mouse_id, old_cage_id, new_cage_id, details)
        VALUES (?, ?, ?, ?, ?)
        """
        with self._get_cursor() as cur:
            cur.execute(sql, (action_type, mouse_id, old_cage_id, new_cage_id, details))
            return cur.lastrowid

    def mark_action_executed(
        self,
        action_id: int,
        executor: str,
        observed_status: Optional[str] = None,
        observed_notes: Optional[str] = None,
        corrected_action_type: Optional[str] = None,
        corrected_new_cage_id: Optional[str] = None
    ):
        """Mark action as executed and record observations."""
        sql = """
        UPDATE pending_actions
        SET 
            executed_at = datetime('now'),
            executor = ?,
            observed_status = ?,
            observed_notes = ?,
            corrected_action_type = ?,
            corrected_new_cage_id = ?
        WHERE action_id = ?
        """
        with self._get_cursor() as cur:
            cur.execute(sql, (
                executor, observed_status, observed_notes,
                corrected_action_type, corrected_new_cage_id, action_id
            ))

    def export_pending_actions(self, output_path: Optional[str] = None) -> str:
        """
        Export pending (unexecuted) actions using export_pending.sql.
        Returns path to exported CSV.
        """
        script_path = Path(__file__).parent / self._export_pending_file
        if not script_path.exists():
            raise FileNotFoundError(f"Export script not found: {script_path}")

        with open(script_path, 'r') as f:
            sql = f.read()

        if not output_path:
            stem = self.path.stem
            ts = self.conn.execute("SELECT strftime('%Y%m%d_%H%M','now')").fetchone()[0]
            output_path = self.path.parent / f"{stem}_pending_{ts}.csv"

        if ".output" not in sql:
            sql = f".headers on\n.mode csv\n.output {output_path}\n" + sql + f"\n.output stdout"

        if ".output" in sql or ".mode" in sql:
            select_sql = sql.split("SELECT", 1)[-1].split(";")[0].strip()
            if not select_sql.endswith(";"):
                select_sql += ";"
            full_select = "SELECT " + select_sql

            try:
                with self._get_cursor() as cur:
                    cur.execute(full_select)
                    rows = cur.fetchall()
                    columns = [desc[0] for desc in cur.description]

                import csv
                with open(output_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(columns)
                    writer.writerows(rows)
                logging.info(f"Pending actions exported to: {output_path}")
                return str(output_path)
            except Exception as e:
                logging.error(f"Export failed: {e}")
                raise
        else:
            with self._get_cursor() as cur:
                cur.executescript(sql)
            return str(output_path)

    def get_reconciliation_queue(self) -> List[Dict[str, Any]]:
        """Get actions needing review (annotated but not executed)."""
        with self._get_cursor() as cur:
            cur.execute("SELECT * FROM reconciliation_queue")
            return [dict(row) for row in cur.fetchall()]

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logging.debug("Database connection closed.")

    def __del__(self):
        self.close()