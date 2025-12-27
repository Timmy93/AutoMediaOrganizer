import threading
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
                cur.execute("""CREATE TABLE IF NOT EXISTS directories (
                                                                          id INT AUTO_INCREMENT PRIMARY KEY,
                                                                          path VARCHAR(1024) NOT NULL UNIQUE
                    )""")

                cur.execute("""CREATE TABLE IF NOT EXISTS files (
                                                                    id INT AUTO_INCREMENT PRIMARY KEY,
                                                                    directory_id INT NOT NULL,
                                                                    filename VARCHAR(1024) NOT NULL,
                    file_hash CHAR(64),
                    skipped BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (directory_id, filename),
                    FOREIGN KEY (directory_id) REFERENCES directories(id)
                    ON DELETE CASCADE
                    )""")

                cur.execute("""CREATE TABLE IF NOT EXISTS preprocessings (
                                                                             id CHAR(64) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL
                    )""")

                cur.execute("""CREATE TABLE IF NOT EXISTS file_preprocessing_outcomes (
                                                                                          id INT AUTO_INCREMENT PRIMARY KEY,
                                                                                          file_id INT NOT NULL,
                                                                                          preprocessing_id CHAR(64) NOT NULL,
                    applied BOOLEAN NOT NULL,
                    error TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (file_id, preprocessing_id),
                    FOREIGN KEY (file_id) REFERENCES files(id)
                    ON DELETE CASCADE,
                    FOREIGN KEY (preprocessing_id) REFERENCES preprocessings(id)
                    ON DELETE CASCADE
                    )""")

                cur.execute("""CREATE TABLE IF NOT EXISTS file_processing_outcomes (
                                                                                       id INT AUTO_INCREMENT PRIMARY KEY,
                                                                                       file_id INT NOT NULL UNIQUE,
                                                                                       outcome BOOLEAN NOT NULL,
                                                                                       error TEXT,
                                                                                       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                                                                       FOREIGN KEY (file_id) REFERENCES files(id)
                    ON DELETE CASCADE
                    )""")
            self._disconnect()

    def _get_or_create_directory(self, path):
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT IGNORE INTO directories(path) VALUES (%s)",
                (path,)
            )
            cur.execute(
                "SELECT id FROM directories WHERE path=%s",
                (path,)
            )
            return cur.fetchone()["id"]

    def _get_or_create_file(self, directory_id, filename, skipped=False, file_hash=None):
        with self.conn.cursor() as cur:
            cur.execute("""
                        INSERT IGNORE INTO files(directory_id, filename, skipped, file_hash)
                VALUES (%s, %s, %s, %s)
                        """, (directory_id, filename, skipped, file_hash))
            cur.execute("""
                        SELECT id FROM files
                        WHERE directory_id=%s AND filename=%s
                        """, (directory_id, filename))
            return cur.fetchone()["id"]

    def _insert_preprocessing(self, preprocessing_id, name):
        with self.conn.cursor() as cur:
            cur.execute("""
                        INSERT IGNORE INTO preprocessings(id, name)
                VALUES (%s, %s)
                        """, (preprocessing_id, name))

    def _insert_file_preprocessing_outcome(self, file_id, preprocessing_id, applied, error):
        with self.conn.cursor() as cur:
            cur.execute("""
                        INSERT INTO file_preprocessing_outcomes
                            (file_id, preprocessing_id, applied, error)
                        VALUES (%s, %s, %s, %s)
                            ON DUPLICATE KEY UPDATE
                                                 applied=VALUES(applied),
                                                 error=VALUES(error)
                        """, (file_id, preprocessing_id, applied, error))

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

    def insert_media_entry(self, entry):
        with self.lock:
            self._connect()
            self._insert_media_entry(entry)
            self._disconnect()

    def _insert_media_entry(self, entry):
        full_path = entry["name"]
        directory, filename = os.path.split(full_path)
        directory_id = self._get_or_create_directory(directory)
        file_id = self._get_or_create_file(
            directory_id,
            filename,
            skipped=entry.get("skipped", False)
        )

        # Preprocessing
        for prep in entry.get("preprocessing_outcome", []):
            self._insert_preprocessing(prep["id"], prep["pattern"])
            self._insert_file_preprocessing_outcome(
                file_id=file_id,
                preprocessing_id=prep["id"],
                applied=prep["applied"],
                error=prep["error"]
            )

        # Processing finale
        proc = entry.get("processing_outcome")
        if proc:
            self._insert_processing_outcome(
                file_id=file_id,
                outcome=proc["outcome"],
                error=proc["error"]
            )

    def _load_query_results(self, query, params=None):
        with self.lock:
            self._connect()
            with self.conn.cursor() as cur:
                cur.execute(query, params or ())
                results = cur.fetchall()
            self._disconnect()
            return results

    def load_processed_files(self) -> list:
        sql = """
              SELECT d.path, f.filename
              FROM files f
                       JOIN directories d ON d.id = f.directory_id
                       LEFT JOIN file_processing_outcomes fpr ON f.id = fpr.file_id
              WHERE fpr.outcome = 1
              ORDER BY f.id;
        """
        results = self._load_query_results(sql)
        return [os.path.join(row["path"], row["filename"]) for row in results]