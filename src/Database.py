import logging
import threading
from datetime import datetime
from pathlib import Path

from src.Tools import hash_this_file, get_relative_path
import pymysql
import os


class Database:
    def __init__(self, host, user, password, database, port=3306):
        self.conn = None
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.port = port
        self.logger = logging.getLogger(__name__)
        self.lock = threading.Lock()

    def _connect(self):
        if not self.conn:
            self.conn = pymysql.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database,
                port=self.port,
                autocommit=True,
                cursorclass=pymysql.cursors.DictCursor
            )

    def _disconnect(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def create_tables(self):
        with self.lock:
            self._connect()
            with self.conn.cursor() as cur:
                cur.execute("""CREATE TABLE IF NOT EXISTS input_files (
                                    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
                                    filename VARCHAR(255) NOT NULL,
                                    path VARCHAR(500) NOT NULL,
                                    last_mod DATETIME NOT NULL,
                                    size BIGINT UNSIGNED NOT NULL,
                                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                                    file_hash CHAR(64) NOT NULL,
                                    success TINYINT(1) NOT NULL DEFAULT 0,
                                    PRIMARY KEY (id),
                                    INDEX idx_path_filename (path, filename),
                                    INDEX idx_file_hash (file_hash)
                               ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                            """)
                cur.execute("""CREATE TABLE IF NOT EXISTS output_files (
                                                             output_file_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
                                                             input_file_id INT UNSIGNED NOT NULL,
                                                             name VARCHAR(255) NOT NULL,
                                                             relative_path VARCHAR(500) NOT NULL,
                                                             in_library TINYINT(1) NOT NULL DEFAULT 0,
                                                             created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                                                             PRIMARY KEY (output_file_id),
                                                             INDEX idx_input_file (input_file_id)
                               ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                            """)


            self._disconnect()

    def _insert_processing_outcome(self, file_id, outcome, error):
        with self.conn.cursor() as cur:
            cur.execute("""
                        INSERT INTO file_processing_outcomes
                            (file_id, outcome, error)
                        VALUES (%s, %s, %s)
                            ON DUPLICATE KEY UPDATE
                                                 outcome=VALUES(outcome),
                                                 error=VALUES(error)
                        """, (file_id, outcome, error))

    def insert_analyzed_media(self, entry: dict, result: dict):
        """Insert the analyzed media into the database. Inserts or updates records of input and output files as necessary."""
        with self.lock:
            self._connect()
            processed_correctly = result.get('processing_outcome', {}).get('outcome', False)
            ignored_entry = entry.get('ignore', False)
            if input_file_id := self._get_input_file_id(entry["original_path"].name, get_relative_path(entry)):
                # Existing record found
                entry["db_input_id"] = input_file_id
                if processed_correctly:
                    # Update existing record if processing was correct
                    self._update_processing_outcome(input_file_id, processed_correctly)
                    self.logger.info(f"Updated [{result.get('name').name}] -> Now correctly processed")
            else:
                # No existing record, insert new
                self._insert_input_file(entry, result)
                self.logger.info(f"Inserted input file [{result.get('name').name}]")
            if processed_correctly and not ignored_entry:
                self._insert_output_file(entry, result)
                self.logger.info(f"Inserted output file [{result.get('name').name}]")
            self._disconnect()

    def _get_input_file_id(self, filename: str, path: str) -> int|None:
        """Retrieve input file ID from the database"""
        with self.conn.cursor() as cur:
            cur.execute("""
                        SELECT id FROM input_files
                        WHERE filename=%s AND path=%s
                        """, (filename, path))
            row = cur.fetchone()
            return row["id"] if row else None

    def _insert_input_file(self, entry: dict, result: dict):
        """Insert input file record into the database"""
        filename = entry["original_path"].name
        relative_path = get_relative_path(entry)
        size = entry["size"]
        last_mod = datetime.fromtimestamp(entry["last_modify"])
        file_hash = entry.get("sha256") or hash_this_file(entry["original_path"])
        success = result.get("processing_outcome", {}).get("outcome", False)

        with self.conn.cursor() as cur:
            cur.execute("""
                        INSERT INTO input_files
                            (filename, path, last_mod, size, file_hash, success)
                        VALUES (%s, %s, %s, %s, %s, %s)

                        """, (filename, relative_path, last_mod, size, file_hash, success))

        inserted_entry = cur.lastrowid
        entry["db_input_id"] = inserted_entry

    def _update_processing_outcome(self, input_file_id: int, outcome: bool):
        """Update an input file status with a new status"""
        with self.conn.cursor() as cur:
            cur.execute("""
                        UPDATE input_files
                        SET success=%s
                        WHERE id=%s
                        """, (outcome, input_file_id))

    def _insert_output_file(self, entry: dict, result: dict):
        """Insert output file record into the database"""
        dest_path = result.get('processing_outcome', {}).get('destination_path')
        file_name = Path(dest_path).name if dest_path else None
        rel_path = get_relative_path({'source_folder': entry.get('destination_folder', ''), 'original_path': dest_path}) if dest_path else None
        input_file_id = entry.get("db_input_id")
        in_library = result.get('processing_outcome', {}).get("outcome", False)
        if input_file_id is None:
            self.logger.error("Input file ID is missing, cannot insert output file.")
            return
        if file_name is None or rel_path is None:
            self.logger.error("Output file name is missing, cannot insert output file.")
            return
        with self.conn.cursor() as cur:
            query = """
                        INSERT INTO output_files
                        (input_file_id, name, relative_path, in_library)
                        VALUES (%s, %s, %s, %s)
                    """
            cur.execute(
                query,
                (input_file_id, file_name, rel_path, in_library)
            )

    def load_processed_files(self) -> list:
        """Load all successfully processed input files"""
        sql = """
              SELECT id, filename, path, last_mod, size, file_hash
              FROM input_files
              WHERE success = 1
              ORDER BY id;
        """
        results = self._load_query_results(sql)
        return [{
            'id': row['id'],
            'file': row['filename'],
            'path': row['path'],
            'last_mod': row['last_mod'],
            'size': row['size'],
            'file_hash': row['file_hash']
        } for row in results]

    def _load_query_results(self, query, params=None):
        with self.lock:
            self._connect()
            with self.conn.cursor() as cur:
                cur.execute(query, params or ())
                results = cur.fetchall()
            self._disconnect()
            return results