import logging
import hashlib
from typing import Optional, Dict, Any, List
import pymysql
from pymysql.cursors import DictCursor
from datetime import datetime


class Database:
    """Singleton class for MariaDB database management"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls, config: dict = None):
        """Implement singleton pattern"""
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, config: dict = None):
        """Initialize database connection"""
        # Only initialize once
        if self._initialized:
            return
            
        if config is None:
            raise ValueError("Database configuration is required for first initialization")
        
        self.logger = logging.getLogger(__name__)
        self.config = config.get('database', {})
        self.connection = None
        self._initialized = True
        
        # Connect to database
        self._connect()
        
        # Create tables if they don't exist
        self.create_tables()
    
    def _connect(self):
        """Establish connection to MariaDB database"""
        try:
            self.connection = pymysql.connect(
                host=self.config.get('host', 'localhost'),
                port=self.config.get('port', 3306),
                user=self.config.get('user', 'root'),
                password=self.config.get('password', ''),
                database=self.config.get('database', 'automediaorganizer'),
                charset='utf8mb4',
                cursorclass=DictCursor,
                autocommit=False
            )
            self.logger.info(f"Connected to MariaDB database: {self.config.get('database')}")
        except pymysql.Error as e:
            self.logger.error(f"Error connecting to MariaDB: {e}")
            raise
    
    def _ensure_connection(self):
        """Ensure database connection is alive"""
        try:
            if self.connection is None:
                self._connect()
            else:
                self.connection.ping(reconnect=True)
        except pymysql.Error as e:
            self.logger.error(f"Error checking connection: {e}")
            self._connect()
    
    def create_tables(self):
        """Create all necessary tables in the database"""
        self._ensure_connection()
        
        tables = {
            'movies': """
                CREATE TABLE IF NOT EXISTS movies (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    tmdb_id INT UNIQUE,
                    title VARCHAR(500) NOT NULL,
                    original_title VARCHAR(500),
                    release_date DATE,
                    overview TEXT,
                    poster_path VARCHAR(500),
                    backdrop_path VARCHAR(500),
                    vote_average DECIMAL(3,1),
                    vote_count INT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_title (title),
                    INDEX idx_tmdb_id (tmdb_id),
                    INDEX idx_release_date (release_date)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            'tv_shows': """
                CREATE TABLE IF NOT EXISTS tv_shows (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    tmdb_id INT UNIQUE,
                    name VARCHAR(500) NOT NULL,
                    original_name VARCHAR(500),
                    first_air_date DATE,
                    overview TEXT,
                    poster_path VARCHAR(500),
                    backdrop_path VARCHAR(500),
                    vote_average DECIMAL(3,1),
                    vote_count INT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_name (name),
                    INDEX idx_tmdb_id (tmdb_id),
                    INDEX idx_first_air_date (first_air_date)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            'episodes': """
                CREATE TABLE IF NOT EXISTS episodes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    tv_show_id INT NOT NULL,
                    season_number INT NOT NULL,
                    episode_number INT NOT NULL,
                    name VARCHAR(500),
                    overview TEXT,
                    air_date DATE,
                    still_path VARCHAR(500),
                    vote_average DECIMAL(3,1),
                    vote_count INT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (tv_show_id) REFERENCES tv_shows(id) ON DELETE CASCADE,
                    UNIQUE KEY unique_episode (tv_show_id, season_number, episode_number),
                    INDEX idx_tv_show_season (tv_show_id, season_number),
                    INDEX idx_air_date (air_date)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            'files': """
                CREATE TABLE IF NOT EXISTS files (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    file_path VARCHAR(1000) NOT NULL UNIQUE,
                    file_hash VARCHAR(64) NOT NULL,
                    file_size BIGINT,
                    media_type ENUM('movie', 'tv') NOT NULL,
                    movie_id INT NULL,
                    tv_show_id INT NULL,
                    episode_id INT NULL,
                    destination_path VARCHAR(1000),
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE SET NULL,
                    FOREIGN KEY (tv_show_id) REFERENCES tv_shows(id) ON DELETE SET NULL,
                    FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE SET NULL,
                    INDEX idx_file_hash (file_hash),
                    INDEX idx_media_type (media_type),
                    INDEX idx_processed_at (processed_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        }
        
        try:
            with self.connection.cursor() as cursor:
                for table_name, create_sql in tables.items():
                    cursor.execute(create_sql)
                    self.logger.info(f"Table '{table_name}' created or already exists")
                self.connection.commit()
        except pymysql.Error as e:
            self.logger.error(f"Error creating tables: {e}")
            self.connection.rollback()
            raise
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of a file"""
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                # Read file in chunks to handle large files
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            self.logger.error(f"Error calculating file hash: {e}")
            # Return hash of file path as fallback
            return hashlib.sha256(file_path.encode()).hexdigest()
    
    def insert_movie(self, movie_data: Dict[str, Any]) -> Optional[int]:
        """Insert or update movie data in database"""
        self._ensure_connection()
        
        try:
            with self.connection.cursor() as cursor:
                # Check if movie already exists
                cursor.execute(
                    "SELECT id FROM movies WHERE tmdb_id = %s",
                    (movie_data.get('id'),)
                )
                result = cursor.fetchone()
                
                if result:
                    # Update existing movie
                    movie_id = result['id']
                    cursor.execute("""
                        UPDATE movies SET
                            title = %s,
                            original_title = %s,
                            release_date = %s,
                            overview = %s,
                            poster_path = %s,
                            backdrop_path = %s,
                            vote_average = %s,
                            vote_count = %s
                        WHERE id = %s
                    """, (
                        movie_data.get('title'),
                        movie_data.get('original_title'),
                        movie_data.get('release_date'),
                        movie_data.get('overview'),
                        movie_data.get('poster_path'),
                        movie_data.get('backdrop_path'),
                        movie_data.get('vote_average'),
                        movie_data.get('vote_count'),
                        movie_id
                    ))
                    self.logger.debug(f"Updated movie: {movie_data.get('title')} (ID: {movie_id})")
                else:
                    # Insert new movie
                    cursor.execute("""
                        INSERT INTO movies (
                            tmdb_id, title, original_title, release_date,
                            overview, poster_path, backdrop_path,
                            vote_average, vote_count
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        movie_data.get('id'),
                        movie_data.get('title'),
                        movie_data.get('original_title'),
                        movie_data.get('release_date'),
                        movie_data.get('overview'),
                        movie_data.get('poster_path'),
                        movie_data.get('backdrop_path'),
                        movie_data.get('vote_average'),
                        movie_data.get('vote_count')
                    ))
                    movie_id = cursor.lastrowid
                    self.logger.info(f"Inserted new movie: {movie_data.get('title')} (ID: {movie_id})")
                
                self.connection.commit()
                return movie_id
                
        except pymysql.Error as e:
            self.logger.error(f"Error inserting/updating movie: {e}")
            self.connection.rollback()
            return None
    
    def insert_tv_show(self, tv_data: Dict[str, Any]) -> Optional[int]:
        """Insert or update TV show data in database"""
        self._ensure_connection()
        
        try:
            with self.connection.cursor() as cursor:
                # Check if TV show already exists
                cursor.execute(
                    "SELECT id FROM tv_shows WHERE tmdb_id = %s",
                    (tv_data.get('id'),)
                )
                result = cursor.fetchone()
                
                if result:
                    # Update existing TV show
                    tv_show_id = result['id']
                    cursor.execute("""
                        UPDATE tv_shows SET
                            name = %s,
                            original_name = %s,
                            first_air_date = %s,
                            overview = %s,
                            poster_path = %s,
                            backdrop_path = %s,
                            vote_average = %s,
                            vote_count = %s
                        WHERE id = %s
                    """, (
                        tv_data.get('name'),
                        tv_data.get('original_name'),
                        tv_data.get('first_air_date'),
                        tv_data.get('overview'),
                        tv_data.get('poster_path'),
                        tv_data.get('backdrop_path'),
                        tv_data.get('vote_average'),
                        tv_data.get('vote_count'),
                        tv_show_id
                    ))
                    self.logger.debug(f"Updated TV show: {tv_data.get('name')} (ID: {tv_show_id})")
                else:
                    # Insert new TV show
                    cursor.execute("""
                        INSERT INTO tv_shows (
                            tmdb_id, name, original_name, first_air_date,
                            overview, poster_path, backdrop_path,
                            vote_average, vote_count
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        tv_data.get('id'),
                        tv_data.get('name'),
                        tv_data.get('original_name'),
                        tv_data.get('first_air_date'),
                        tv_data.get('overview'),
                        tv_data.get('poster_path'),
                        tv_data.get('backdrop_path'),
                        tv_data.get('vote_average'),
                        tv_data.get('vote_count')
                    ))
                    tv_show_id = cursor.lastrowid
                    self.logger.info(f"Inserted new TV show: {tv_data.get('name')} (ID: {tv_show_id})")
                
                self.connection.commit()
                return tv_show_id
                
        except pymysql.Error as e:
            self.logger.error(f"Error inserting/updating TV show: {e}")
            self.connection.rollback()
            return None
    
    def insert_episode(self, tv_show_id: int, episode_data: Dict[str, Any], 
                      season_number: int, episode_number: int) -> Optional[int]:
        """Insert or update episode data in database"""
        self._ensure_connection()
        
        try:
            with self.connection.cursor() as cursor:
                # Check if episode already exists
                cursor.execute(
                    "SELECT id FROM episodes WHERE tv_show_id = %s AND season_number = %s AND episode_number = %s",
                    (tv_show_id, season_number, episode_number)
                )
                result = cursor.fetchone()
                
                if result:
                    # Update existing episode
                    episode_id = result['id']
                    cursor.execute("""
                        UPDATE episodes SET
                            name = %s,
                            overview = %s,
                            air_date = %s,
                            still_path = %s,
                            vote_average = %s,
                            vote_count = %s
                        WHERE id = %s
                    """, (
                        episode_data.get('name') if episode_data else None,
                        episode_data.get('overview') if episode_data else None,
                        episode_data.get('air_date') if episode_data else None,
                        episode_data.get('still_path') if episode_data else None,
                        episode_data.get('vote_average') if episode_data else None,
                        episode_data.get('vote_count') if episode_data else None,
                        episode_id
                    ))
                    self.logger.debug(f"Updated episode: S{season_number:02d}E{episode_number:02d} (ID: {episode_id})")
                else:
                    # Insert new episode
                    cursor.execute("""
                        INSERT INTO episodes (
                            tv_show_id, season_number, episode_number,
                            name, overview, air_date, still_path,
                            vote_average, vote_count
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        tv_show_id,
                        season_number,
                        episode_number,
                        episode_data.get('name') if episode_data else None,
                        episode_data.get('overview') if episode_data else None,
                        episode_data.get('air_date') if episode_data else None,
                        episode_data.get('still_path') if episode_data else None,
                        episode_data.get('vote_average') if episode_data else None,
                        episode_data.get('vote_count') if episode_data else None
                    ))
                    episode_id = cursor.lastrowid
                    self.logger.info(f"Inserted new episode: S{season_number:02d}E{episode_number:02d} (ID: {episode_id})")
                
                self.connection.commit()
                return episode_id
                
        except pymysql.Error as e:
            self.logger.error(f"Error inserting/updating episode: {e}")
            self.connection.rollback()
            return None
    
    def insert_file(self, file_path: str, destination_path: str, media_type: str,
                   movie_id: Optional[int] = None, tv_show_id: Optional[int] = None,
                   episode_id: Optional[int] = None) -> Optional[int]:
        """Insert or update file record in database"""
        self._ensure_connection()
        
        try:
            # Calculate file hash and size
            file_hash = self._calculate_file_hash(file_path)
            try:
                import os
                file_size = os.path.getsize(file_path)
            except:
                file_size = None
            
            with self.connection.cursor() as cursor:
                # Check if file already exists (by path or hash)
                cursor.execute(
                    "SELECT id FROM files WHERE file_path = %s OR file_hash = %s",
                    (file_path, file_hash)
                )
                result = cursor.fetchone()
                
                if result:
                    # Update existing file record
                    file_id = result['id']
                    cursor.execute("""
                        UPDATE files SET
                            file_hash = %s,
                            file_size = %s,
                            media_type = %s,
                            movie_id = %s,
                            tv_show_id = %s,
                            episode_id = %s,
                            destination_path = %s,
                            processed_at = %s
                        WHERE id = %s
                    """, (
                        file_hash,
                        file_size,
                        media_type,
                        movie_id,
                        tv_show_id,
                        episode_id,
                        destination_path,
                        datetime.now(),
                        file_id
                    ))
                    self.logger.info(f"Updated file record: {file_path} (ID: {file_id})")
                else:
                    # Insert new file record
                    cursor.execute("""
                        INSERT INTO files (
                            file_path, file_hash, file_size, media_type,
                            movie_id, tv_show_id, episode_id, destination_path
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        file_path,
                        file_hash,
                        file_size,
                        media_type,
                        movie_id,
                        tv_show_id,
                        episode_id,
                        destination_path
                    ))
                    file_id = cursor.lastrowid
                    self.logger.info(f"Inserted new file record: {file_path} (ID: {file_id})")
                
                self.connection.commit()
                return file_id
                
        except pymysql.Error as e:
            self.logger.error(f"Error inserting/updating file: {e}")
            self.connection.rollback()
            return None
    
    def is_file_processed(self, file_path: str) -> bool:
        """Check if a file has already been processed"""
        self._ensure_connection()
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM files WHERE file_path = %s",
                    (file_path,)
                )
                result = cursor.fetchone()
                return result is not None
        except pymysql.Error as e:
            self.logger.error(f"Error checking if file is processed: {e}")
            return False
    
    def is_duplicate_by_hash(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Check if a file with the same hash already exists"""
        self._ensure_connection()
        
        try:
            file_hash = self._calculate_file_hash(file_path)
            
            with self.connection.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM files WHERE file_hash = %s",
                    (file_hash,)
                )
                result = cursor.fetchone()
                return result
        except pymysql.Error as e:
            self.logger.error(f"Error checking for duplicate by hash: {e}")
            return None
    
    def get_movie_by_tmdb_id(self, tmdb_id: int) -> Optional[Dict[str, Any]]:
        """Get movie data by TMDB ID"""
        self._ensure_connection()
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM movies WHERE tmdb_id = %s",
                    (tmdb_id,)
                )
                return cursor.fetchone()
        except pymysql.Error as e:
            self.logger.error(f"Error getting movie by TMDB ID: {e}")
            return None
    
    def get_tv_show_by_tmdb_id(self, tmdb_id: int) -> Optional[Dict[str, Any]]:
        """Get TV show data by TMDB ID"""
        self._ensure_connection()
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM tv_shows WHERE tmdb_id = %s",
                    (tmdb_id,)
                )
                return cursor.fetchone()
        except pymysql.Error as e:
            self.logger.error(f"Error getting TV show by TMDB ID: {e}")
            return None
    
    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            self.logger.info("Database connection closed")
