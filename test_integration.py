#!/usr/bin/env python3
"""
Test that MediaOrganizer works correctly when database is disabled.
"""

import sys
import os
import tempfile
from pathlib import Path

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_database_disabled():
    """Test MediaOrganizer initialization with database disabled"""
    from src.MediaOrganizer import MediaOrganizer
    
    print("Testing MediaOrganizer with Database Disabled...")
    
    # Create a temporary directory structure
    with tempfile.TemporaryDirectory() as tmpdir:
        source = Path(tmpdir) / "source"
        dest = Path(tmpdir) / "dest"
        config_dir = Path(tmpdir) / "Config"
        
        source.mkdir()
        dest.mkdir()
        config_dir.mkdir()
        
        # Create minimal scan_config.toml
        scan_config_path = config_dir / "scan_config.toml"
        scan_config_path.write_text("""
[[directories]]
path = "test"
pattern_list = ["generic"]

[patterns.generic]
""")
        
        # Mock configuration with database disabled
        config = {
            'database': {
                'enabled': False  # Database disabled
            },
            'tmdb': {
                'api_key': 'test_key',
                'language': 'it-IT'
            },
            'regex': {
                'tv_pattern': r'(?P<title>.+?)[\.\s]+[Ss](?P<season>\d{1,2})[Ee](?P<episode>\d{1,2})',
                'movie_pattern': r'(?P<title>.+?)[\.\s]+\((?P<year>\d{4})\)'
            },
            'paths': {
                'source_folder': str(source),
                'destination_folder': str(dest),
                'movie_folder': 'Movies',
                'tv_show_folder': 'TVShows',
                'scan_only_selected_subdir': False
            },
            'naming': {
                'movie_pattern': '{title} ({year})',
                'tv_show_pattern': '{title}/Season {season:02d}',
                'episode_pattern': '{title} - S{season:02d}E{episode:02d} - {episode_title}'
            },
            'options': {
                'video_extensions': ['.mkv', '.mp4', '.avi'],
                'create_directories': True,
                'skip_existing': True,
                'copy_instead_of_link': False,
                'episode_padding': 2,
                'season_padding': 2
            }
        }
        
        try:
            # Change to temp directory to find the Config directory
            original_dir = os.getcwd()
            os.chdir(tmpdir)
            
            organizer = MediaOrganizer(config)
            
            # Verify database is None when disabled
            if organizer.db is None:
                print("✓ Database disabled: PASSED - Database is None as expected")
                result = True
            else:
                print("✗ Database disabled: FAILED - Database should be None when disabled")
                result = False
            
            os.chdir(original_dir)
            return result
            
        except Exception as e:
            os.chdir(original_dir)
            print(f"✗ Database disabled: FAILED - Exception: {e}")
            import traceback
            traceback.print_exc()
            return False


def test_database_enabled_but_unavailable():
    """Test MediaOrganizer initialization with database enabled but unavailable"""
    from src.MediaOrganizer import MediaOrganizer
    
    print("\nTesting MediaOrganizer with Database Enabled but Unavailable...")
    
    # Create a temporary directory structure
    with tempfile.TemporaryDirectory() as tmpdir:
        source = Path(tmpdir) / "source"
        dest = Path(tmpdir) / "dest"
        config_dir = Path(tmpdir) / "Config"
        
        source.mkdir()
        dest.mkdir()
        config_dir.mkdir()
        
        # Create minimal scan_config.toml
        scan_config_path = config_dir / "scan_config.toml"
        scan_config_path.write_text("""
[[directories]]
path = "test"
pattern_list = ["generic"]

[patterns.generic]
""")
        
        # Mock configuration with database enabled but wrong connection info
        config = {
            'database': {
                'enabled': True,  # Database enabled
                'host': 'localhost',
                'port': 3306,
                'user': 'nonexistent_user',
                'password': 'wrong_password',
                'database': 'nonexistent_db'
            },
            'tmdb': {
                'api_key': 'test_key',
                'language': 'it-IT'
            },
            'regex': {
                'tv_pattern': r'(?P<title>.+?)[\.\s]+[Ss](?P<season>\d{1,2})[Ee](?P<episode>\d{1,2})',
                'movie_pattern': r'(?P<title>.+?)[\.\s]+\((?P<year>\d{4})\)'
            },
            'paths': {
                'source_folder': str(source),
                'destination_folder': str(dest),
                'movie_folder': 'Movies',
                'tv_show_folder': 'TVShows',
                'scan_only_selected_subdir': False
            },
            'naming': {
                'movie_pattern': '{title} ({year})',
                'tv_show_pattern': '{title}/Season {season:02d}',
                'episode_pattern': '{title} - S{season:02d}E{episode:02d} - {episode_title}'
            },
            'options': {
                'video_extensions': ['.mkv', '.mp4', '.avi'],
                'create_directories': True,
                'skip_existing': True,
                'copy_instead_of_link': False,
                'episode_padding': 2,
                'season_padding': 2
            }
        }
        
        try:
            # Change to temp directory to find the Config directory
            original_dir = os.getcwd()
            os.chdir(tmpdir)
            
            organizer = MediaOrganizer(config)
            
            # Should gracefully handle database connection failure
            if organizer.db is None:
                print("✓ Graceful fallback: PASSED - MediaOrganizer continues without database")
                result = True
            else:
                print("✗ Graceful fallback: FAILED - Database should be None after connection failure")
                result = False
            
            os.chdir(original_dir)
            return result
            
        except Exception as e:
            os.chdir(original_dir)
            print(f"✗ Graceful fallback: FAILED - Should not raise exception: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """Run all integration tests"""
    print("=" * 60)
    print("MediaOrganizer Database Integration Tests")
    print("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("Database Disabled", test_database_disabled()))
    results.append(("Graceful Fallback", test_database_enabled_but_unavailable()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "PASSED" if result else "FAILED"
        symbol = "✓" if result else "✗"
        print(f"{symbol} {test_name}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All integration tests passed!")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
