import sqlite3
import random
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Union
from datetime import date

import logging
import traceback

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

    def get_all_mice(self) -> Dict[str, Dict[str, Any]]:
        """Get all mice, returned as a dictionary keyed by mouse ID."""
        with self._get_cursor() as cur:
            cur.execute("SELECT * FROM mice")
            return {row['ID']: dict(row) for row in cur.fetchall()}

    def add_multiple_mice(self, mice_data: List[Dict[str, Any]]):
        """Insert multiple new mice."""
        if not mice_data:
            return

        # Assuming all mice_data dicts have the same keys for columns
        # and 'id' is always present.
        sample_mouse = mice_data[0]
        columns = [k for k in sample_mouse.keys() if k != 'ID']
        placeholders = ", ".join(["?"] * len(columns))
        cols = ", ".join(columns)

        sql = f"INSERT INTO mice (ID, {cols}) VALUES (?, {placeholders})"
        
        values_to_insert = []
        for mouse_data in mice_data:
            # Ensure 'ID' is present and handle potential missing keys by providing None
            row_values = [mouse_data.get('ID')] + [mouse_data.get(c) for c in columns]
            values_to_insert.append(row_values)

        with self._get_cursor() as cur:
            cur.executemany(sql, values_to_insert)
            logging.debug(f"Inserted {len(mice_data)} mice.")

    def clear_mice_table(self):
        """Clear all entries from the mice table."""
        with self._get_cursor() as cur:
            cur.execute("DELETE FROM mice")
        logging.info("Mice table cleared.")
    def add_mouse(self, mouse_data: Dict[str, Any]) -> str:
        """Insert new mouse. Generates ID if not provided. Returns inserted ID."""
        if not mouse_data.get('id'):
            # Generate ID if not provided
            genotype = mouse_data.get('genotype', '')
            birth_date_str = str(mouse_data.get('birthDate', date.today()))
            markings = mouse_data.get('markings', '')
            sex = mouse_data.get('sex', '')
            cage = mouse_data.get('cage_id', '')

            genoID = self._process_genotypeID(genotype)
            dobID = self._process_birthDateID(birth_date_str)
            toeID = self._process_toeID(markings if markings else "")
            sexID = self._process_sexID(sex)
            cageID = self._process_cageID(cage)
            generated_id = f"{genoID}{dobID}{toeID}{sexID}{cageID}"
            
            # Ensure generated ID is unique
            counter = 0
            final_id = generated_id
            while self.get_mouse(final_id):
                counter += 1
                final_id = f"{generated_id}_{counter}"
            mouse_data['id'] = final_id
            logging.debug(f"Generated ID for new mouse: {final_id}")

        columns = [k for k in mouse_data.keys() if k != 'id']
        placeholders = ", ".join(["?"] * len(columns))
        cols = ", ".join(columns)
        
        sql = f"INSERT INTO mice (id, {cols}) VALUES (?, {placeholders})"
        values = [mouse_data['id']] + [mouse_data.get(c) for c in columns]

        with self._get_cursor() as cur:
            cur.execute(sql, values)
            return mouse_data['id']

    def _process_genotypeID(self, genotype: str) -> str:
        """Convert genotype to numeric code"""
        genotype_map = {
            "hom-PP2A": "1",
            "PP2A(w/-)": "2",
            "PP2A(f/w)": "3",
            "NEX-CRE-PP2A(f/w)": "4",
            "CMV-CRE": "5",
            "NEX-CRE": "6",
            "CMV-CRE-PP2A(f/w)": "7"
        }
        return genotype_map.get(str(genotype), str(random.randint(8,9)))

    def _process_birthDateID(self, bdate: date) -> str:
        """Convert birthdate to YYMMDD format"""
        try:
            if isinstance(bdate, str):
                bdate = mio.convert_to_date(bdate) # Use io_helper's date conversion
            return bdate.strftime("%y%m%d") if bdate else "000000"
        except Exception as e:
            logging.error(f"Error processing birth date: {e}\n{traceback.format_exc()}")
            return "000000"

    def _process_toeID(self, toe: str) -> str:
        """Extract toe number or generate random if invalid"""
        toe_str = str(toe)
        toe_str = f"toe{toe_str}" if not toe_str.startswith("toe") else toe_str
        toe_num = toe_str.split("toe")[1]
        try:
            int(toe_num)
        except:
            return "69"
        if len(toe_num) == 1:
            return f"0{toe_num}"
        if len(toe_num) == 2:
            return toe_num
        return "69"

    def _process_sexID(self, sex: str) -> str:
        """Generate sex ID (odd for male, even for female)"""
        return str(random.choice([1, 3, 5, 7, 9])) if sex == "M" else str(random.choice([0, 2, 4, 6, 8]))

    def _process_cageID(self, cage: str) -> str:
        """Process cage number with consistent formatting.
        Rules:
        1. If no -A- or -B- designation, return random valid 6-digit number
        2. If -A- or -B- appears AND prefix is 2 or 8:
        - For -A-: Insert random 1-5
        - For -B-: Insert random 6-9
        3. Otherwise return random valid 6-digit number
        """
        cage_str = str(cage).strip()

        if "-A-" in cage_str:
            parts = cage_str.replace("-", "").split("A")
            prefix = parts[0]
            if prefix in ("2","8"):
                suffix = parts[1] if len(parts) > 1 else ""
                suffix_purged = self._purge_leading_zeros(suffix.zfill(4),4)
                return f"{prefix}{random.randint(1, 5)}{suffix_purged}"
        if "-B-" in cage_str:
            parts = cage_str.replace("-", "").split("B")
            prefix = parts[0]
            if prefix in ("2","8"):
                suffix = parts[1] if len(parts) > 1 else ""
                suffix_purged = self._purge_leading_zeros(suffix.zfill(4),4)
                return f"{prefix}{random.randint(6, 9)}{suffix_purged}"
            
        return str(self._roll_with_rickroll())

    def _generate_random_id(self):
        return "".join([str(random.randint(0, 9)) for _ in range(16)])

    def _roll_with_rickroll(self):
        while True:
            num = random.randint(100000, 999999)
            # Check if number is in forbidden ranges
            if (200000 <= num <= 299999) or (800000 <= num <= 899999):
                continue  # Re-roll
            else:
                return f"{num:06d}"  # Valid number
            
    def _purge_leading_zeros(self, s:str, digits:int):
        # Truncate if longer than required
        if len(s) > digits:
            s = s[-digits:]
        else:
            # Pad with zeros if shorter
            s = s.zfill(digits)
        result = []
        zero_run = True  # Track if we"re still in leading zeros
        for c in s:
            if c == "0" and zero_run:
                result.append(str(random.randint(1, 9)))
            else:
                result.append(c)
                zero_run = False
        return "".join(result)[:digits].ljust(digits, "0")

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