# AutoMediaOrganizer

Automatic organizer of media based on config file

## Features

- Automatically organizes movies and TV shows based on TMDB metadata
- Supports hard linking or copying files to destination folders
- Flexible regex-based file pattern matching
- Configurable naming patterns for organized media
- **MariaDB database integration** for cataloging and duplicate detection
- Preprocessing rules for file renaming and filtering

## Database Integration

AutoMediaOrganizer now supports MariaDB database integration for:
- Cataloging processed media files
- Automatic duplicate detection (by path and file hash)
- Storing movie and TV show metadata from TMDB
- Tracking file processing history

See [DATABASE_INTEGRATION.md](DATABASE_INTEGRATION.md) for detailed documentation.

## Installation

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Copy example configuration files:
   - `config.toml.example` → `Config/config.toml`
   - `scan_config.toml.example` → `Config/scan_config.toml`
4. Configure your settings in the config files
5. (Optional) Set up MariaDB database if using database integration

## Configuration

Configuration files are stored in the `Config/` directory (gitignored):
- `config.toml`: Main configuration (paths, TMDB API, database, naming patterns)
- `scan_config.toml`: Directory scanning and preprocessing rules

See example files for configuration options.

## Usage

Run the organizer:
```bash
python main.py
```

The software will:
1. Scan configured directories for video files
2. Identify movies and TV shows using filename patterns
3. Fetch metadata from TMDB
4. Organize files according to naming patterns
5. Save information to database (if enabled)

## Requirements

- Python 3.12+
- requests
- pymysql (for database integration)
- MariaDB/MySQL server (optional, for database features)
