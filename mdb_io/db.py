import sqlite3
import logging
import traceback

class Mouse_DB:
    def __init__(self):
        self.path = None
        self.conn = None

    def set_db_path(self, db_path):
        self.path = db_path
        try:
            self._reload_db(self)
        except Exception:
            pass # Insert logging and traceback here

    def _reload_db(self):
        logging.debug(f"Connecting to DB: {self.path}")
    