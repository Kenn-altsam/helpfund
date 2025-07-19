#!/usr/bin/env python3
"""
Optimized Index Creation Script

This script runs the optimized index creation to replace conflicting indexes
with a more efficient strategy.
"""

import sys
import os

# Add the src directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.database import engine
from core.database_config import create_indexes

def main():
    """Run the optimized index creation"""
    print("🚀 Starting Optimized Index Creation")
    print("=" * 50)
    print("This will:")
    print("1. Drop existing conflicting composite indexes")
    print("2. Create a single optimized composite index")
    print("3. Add essential GIN indexes for full-text search")
    print("4. Add simple indexes for individual column filtering")
    print()
    
    try:
        create_indexes(engine)
        print("\n✅ Index optimization completed successfully!")
        print("\n💡 Next steps:")
        print("1. Run the analyze_indexes.py script to verify the changes")
        print("2. Monitor query performance to ensure improvements")
        print("3. Consider running VACUUM ANALYZE if needed")
        
    except Exception as e:
        print(f"❌ Index optimization failed: {e}")
        print("Make sure you're running this outside of the application context")

if __name__ == "__main__":
    main() 