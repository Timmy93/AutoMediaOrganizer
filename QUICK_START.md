# Quick Start Guide - Database Integration

## Prerequisites

1. **MariaDB/MySQL Server** installed and running
2. **Python 3.12+** installed
3. **AutoMediaOrganizer** repository cloned

## Step-by-Step Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- `requests` (for TMDB API)
- `pymysql` (for MariaDB connection)

### 2. Set Up MariaDB Database

Run the provided SQL script:

```bash
mysql -u root -p < database_setup.sql
```

Or manually execute:

```sql
CREATE DATABASE automediaorganizer CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'automedia_user'@'localhost' IDENTIFIED BY 'your_secure_password';
GRANT ALL PRIVILEGES ON automediaorganizer.* TO 'automedia_user'@'localhost';
FLUSH PRIVILEGES;
```

### 3. Configure the Application

Create `Config/config.toml` based on the example file:

```bash
mkdir -p Config
cp config.toml.example Config/config.toml
```

Edit `Config/config.toml` and set your database credentials:

```toml
[database]
enabled = true
host = "localhost"
port = 3306
user = "automedia_user"
password = "your_secure_password"
database = "automediaorganizer"

[tmdb]
api_key = "your_tmdb_api_key"
language = "it-IT"

# ... other settings ...
```

Also create `Config/scan_config.toml`:

```bash
cp scan_config.toml.example Config/scan_config.toml
```

### 4. Run the Application

```bash
python main.py
```

On first run, the application will:
1. Connect to the database
2. Automatically create all necessary tables
3. Start processing your media files
4. Save all metadata to the database

## Verifying Database Integration

### Check Tables Were Created

```sql
USE automediaorganizer;
SHOW TABLES;
```

You should see:
- `movies`
- `tv_shows`
- `episodes`
- `files`

### Check Processed Files

```sql
SELECT COUNT(*) FROM files;
SELECT * FROM movies LIMIT 5;
SELECT * FROM tv_shows LIMIT 5;
```

## Features in Action

### Duplicate Detection

When a file is processed:
1. The system calculates its SHA256 hash
2. Checks if the same path or hash exists in database
3. Skips the file if it's a duplicate
4. Logs the duplicate detection

Example log output:
```
INFO: File già presente nel database, saltato: /path/to/movie.mkv
WARNING: Rilevato duplicato per hash: /path/to/duplicate.mkv
WARNING: File originale: /original/path/movie.mkv
```

### Movie Processing

When a movie is processed:
1. TMDB metadata is fetched
2. Movie is inserted/updated in `movies` table
3. File is organized and linked/copied
4. File record is created in `files` table

### TV Show Processing

When a TV episode is processed:
1. TV show is inserted/updated in `tv_shows` table
2. Episode details are inserted/updated in `episodes` table
3. File is organized and linked/copied
4. File record is created in `files` table

## Disabling Database (Optional)

To run without database integration:

```toml
[database]
enabled = false
```

The application will continue to work normally without database features.

## Troubleshooting

### Connection Refused

If you see:
```
Error connecting to MariaDB: (2003, "Can't connect to MySQL server")
```

Check:
- MariaDB service is running: `systemctl status mariadb`
- Correct host and port in config
- Firewall allows connections

### Access Denied

If you see:
```
Error connecting to MariaDB: (1045, "Access denied")
```

Check:
- Username and password are correct
- User has privileges: `SHOW GRANTS FOR 'automedia_user'@'localhost';`

### Unknown Database

If you see:
```
Error connecting to MariaDB: (1049, "Unknown database")
```

- Create the database using the setup script
- Or manually: `CREATE DATABASE automediaorganizer;`

## Monitoring

### Check Logs

Logs are written to `Config/AutoMediaOrganizer.log`:

```bash
tail -f Config/AutoMediaOrganizer.log
```

Look for:
- `"Connected to MariaDB database: automediaorganizer"`
- `"Table 'movies' created or already exists"`
- `"Inserted new movie: ..."` or `"Updated movie: ..."`
- `"Inserted new file record: ..."`

### Database Queries

Monitor what's being stored:

```sql
-- Recent movies
SELECT title, release_date, created_at FROM movies ORDER BY created_at DESC LIMIT 10;

-- Recent TV shows
SELECT name, first_air_date, created_at FROM tv_shows ORDER BY created_at DESC LIMIT 10;

-- Files processed today
SELECT file_path, media_type, processed_at FROM files 
WHERE DATE(processed_at) = CURDATE();

-- Duplicate files (same hash)
SELECT file_hash, COUNT(*) as count FROM files 
GROUP BY file_hash HAVING count > 1;
```

## Next Steps

- Customize naming patterns in `Config/config.toml`
- Add preprocessing patterns in `Config/scan_config.toml`
- Build queries to analyze your media library
- Create backup routines for the database

## Need Help?

- Read `DATABASE_INTEGRATION.md` for detailed documentation
- Check `IMPLEMENTATION_SUMMARY.md` for technical details
- Review example configs: `config.toml.example` and `scan_config.toml.example`
