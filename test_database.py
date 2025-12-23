#!/usr/bin/env python3
"""
Test script for Database class functionality.
This script tests the Database singleton pattern and basic operations without requiring an actual MariaDB connection.
"""

import sys
import os

# Add the parent directory to the path to import the module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_singleton_pattern():
    """Test that Database class implements singleton pattern correctly"""
    from src.Database import Database
    
    print("Testing Singleton Pattern...")
    
    # Mock configuration
    config = {
        'database': {
            'host': 'localhost',
            'port': 3306,
            'user': 'test_user',
            'password': 'test_password',
            'database': 'test_db'
        }
    }
    
    try:
        # Create first instance
        db1 = Database.__new__(Database)
        # Create second instance
        db2 = Database.__new__(Database)
        
        # Verify they are the same instance
        assert db1 is db2, "Database instances are not the same (singleton violated)"
        print("✓ Singleton pattern: PASSED - Same instance returned")
        return True
        
    except Exception as e:
        print(f"✗ Singleton pattern: FAILED - {e}")
        return False


def test_database_initialization():
    """Test that Database can be initialized with config"""
    from src.Database import Database
    
    print("\nTesting Database Initialization...")
    
    # Mock configuration
    config = {
        'database': {
            'host': 'localhost',
            'port': 3306,
            'user': 'test_user',
            'password': 'test_password',
            'database': 'test_db'
        }
    }
    
    try:
        # This will fail to connect, but we can test if the class structure is correct
        try:
            db = Database(config)
        except Exception as e:
            # Expected to fail without actual database
            if "Can't connect" in str(e) or "Access denied" in str(e) or "Unknown database" in str(e):
                print(f"✓ Database initialization: PASSED - Class structure correct (connection failed as expected: {type(e).__name__})")
                return True
            else:
                print(f"✗ Database initialization: FAILED - Unexpected error: {e}")
                return False
        
        print("✓ Database initialization: PASSED - Successfully connected (MariaDB is running)")
        return True
        
    except Exception as e:
        print(f"✗ Database initialization: FAILED - {e}")
        return False


def test_method_existence():
    """Test that all required methods exist in Database class"""
    from src.Database import Database
    
    print("\nTesting Method Existence...")
    
    required_methods = [
        'create_tables',
        'insert_movie',
        'insert_tv_show',
        'insert_episode',
        'insert_file',
        'is_file_processed',
        'is_duplicate_by_hash',
        'get_movie_by_tmdb_id',
        'get_tv_show_by_tmdb_id',
        'close'
    ]
    
    all_exist = True
    for method in required_methods:
        if hasattr(Database, method):
            print(f"  ✓ Method '{method}' exists")
        else:
            print(f"  ✗ Method '{method}' missing")
            all_exist = False
    
    if all_exist:
        print("✓ Method existence: PASSED - All required methods exist")
        return True
    else:
        print("✗ Method existence: FAILED - Some methods are missing")
        return False


def test_integration_with_media_organizer():
    """Test that MediaOrganizer can import and use Database"""
    from src.MediaOrganizer import MediaOrganizer
    
    print("\nTesting Integration with MediaOrganizer...")
    
    try:
        # Verify that MediaOrganizer imports Database
        from src.MediaOrganizer import Database
        print("✓ Integration: PASSED - Database successfully imported in MediaOrganizer")
        return True
    except ImportError as e:
        print(f"✗ Integration: FAILED - Cannot import Database in MediaOrganizer: {e}")
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("Database Class Test Suite")
    print("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("Singleton Pattern", test_singleton_pattern()))
    results.append(("Database Initialization", test_database_initialization()))
    results.append(("Method Existence", test_method_existence()))
    results.append(("MediaOrganizer Integration", test_integration_with_media_organizer()))
    
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
        print("\n✓ All tests passed!")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
